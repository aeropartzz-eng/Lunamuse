"""Candle Builder — Fase 7 (DAT-003/DAT-004/DAT-005/DAT-006).

Constrói candles OHLCV próprios a partir de trades individuais
normalizados (:class:`models.Trade`) e agrega timeframes menores em
maiores. Regras da especificação (§3, §7):

- Só granularidades que a fonte realmente fornece: os 17 timeframes
  de :data:`normalization.ALLOWED_TIMEFRAMES`. ``validate_timeframe``
  rejeita qualquer outro — granularidade nunca é inventada.
- Sem simulação de ticks: um bucket só vira candle se recebeu ao
  menos um trade real. Buckets vazios não geram candle (não há dado
  inventado); a ausência é registrada como gap nas métricas.
- Sem look-ahead: só candles **fechados** são emitidos (o bucket
  seguinte começou) e só candles fechados entram na agregação.
- Validação cronológica (DAT-005): trade com timestamp anterior ao
  último trade aceito é rejeitado e contado — nunca reordena o
  passado.
- Detecção de gaps (DAT-006): buckets pulados e candles ausentes
  numa sequência são detectados e registrados; nunca preenchidos
  com dado inventado.

Os modelos consumidos vivem em ``services/exchange-connectors/``
(``models.py``, ``normalization.py``) — importar com esse diretório
no ``sys.path``, como em ``tests/conftest.py``.

Nenhum método aqui faz rede, usa chave de API ou envia ordens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from models import Candle, Trade
from normalization import ALLOWED_TIMEFRAMES, validate_timeframe

# Duração de cada timeframe em milissegundos (§3). Buckets alinhados
# à época Unix (``open_time_ms % tf_ms == 0``); a semana (1w) alinha
# à semana da época (quinta-feira 00:00 UTC).
TIMEFRAME_MS: dict[str, int] = {
    "1s": 1_000,
    "5s": 5_000,
    "15s": 15_000,
    "30s": 30_000,
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "1w": 604_800_000,
}

# Sanidade: a tabela acima deve cobrir exatamente os timeframes
# permitidos — se a especificação mudar, o erro aparece aqui.
assert set(TIMEFRAME_MS) == set(ALLOWED_TIMEFRAMES), (
    "TIMEFRAME_MS diverge de ALLOWED_TIMEFRAMES"
)


def bucket_start_ms(timestamp_ms: int, timeframe: str) -> int:
    """Início do bucket (ms UTC) que contém ``timestamp_ms``."""
    tf = validate_timeframe(timeframe)
    return (timestamp_ms // TIMEFRAME_MS[tf]) * TIMEFRAME_MS[tf]


@dataclass
class CandleBuilderMetrics:
    """Contadores do builder (§16 — métricas de mercado)."""

    trades_seen: int = 0
    trades_accepted: int = 0
    out_of_order_rejected: int = 0
    candles_closed: int = 0
    gap_buckets_skipped: int = 0  # buckets sem nenhum trade, pulados

    def as_dict(self) -> dict[str, int]:
        return {
            "trades_seen": self.trades_seen,
            "trades_accepted": self.trades_accepted,
            "out_of_order_rejected": self.out_of_order_rejected,
            "candles_closed": self.candles_closed,
            "gap_buckets_skipped": self.gap_buckets_skipped,
        }


@dataclass
class _Bucket:
    """Acumulador de um candle ainda aberto."""

    open_time_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")
    trades: int = 0

    def add(self, price: Decimal, quantity: Decimal) -> None:
        if self.trades == 0:
            self.open = price
            self.high = price
            self.low = price
            self.close = price
        else:
            if price > self.high:
                self.high = price
            if price < self.low:
                self.low = price
            self.close = price
        self.volume += quantity
        self.trades += 1

    def to_candle(
        self, *, exchange: str, symbol: str, timeframe: str
    ) -> Candle:
        tf_ms = TIMEFRAME_MS[timeframe]
        return Candle(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            open_time_ms=self.open_time_ms,
            close_time_ms=self.open_time_ms + tf_ms - 1,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            trades=self.trades,
        )


class CandleBuilder:
    """Constrói candles OHLCV a partir de trades, por timeframes.

    Um builder cobre **um** par (exchange, symbol) e um conjunto de
    timeframes. Trades de outro par são rejeitados (``ValueError``);
    trades fora de ordem são descartados e contados (DAT-005), nunca
    reordenados.

    Exemplo::

        builder = CandleBuilder("binance", "BTC/USDT", ["1m", "5m"])
        closed = builder.add_trade(trade)  # candles fechados pelo trade
    """

    def __init__(
        self,
        exchange: str,
        symbol: str,
        timeframes: list[str],
    ) -> None:
        if not timeframes:
            raise ValueError("CandleBuilder precisa de ao menos 1 timeframe")
        self.exchange = exchange
        self.symbol = symbol
        self.timeframes = [validate_timeframe(tf) for tf in timeframes]
        self._open: dict[str, Optional[_Bucket]] = {
            tf: None for tf in self.timeframes
        }
        self._last_trade_ms: Optional[int] = None
        self.metrics = CandleBuilderMetrics()

    # -- ingestão ------------------------------------------------------------

    def add_trade(self, trade: Trade) -> list[Candle]:
        """Ingere um trade; retorna os candles fechados por ele.

        Um trade só fecha o candle do bucket anterior quando chega
        num bucket posterior. Buckets intermediários sem trades são
        pulados (contados como gap, sem candle inventado).
        """
        self.metrics.trades_seen += 1
        if trade.exchange != self.exchange or trade.symbol != self.symbol:
            raise ValueError(
                f"trade de {trade.exchange}/{trade.symbol} não pertence "
                f"a este builder ({self.exchange}/{self.symbol})"
            )
        if (
            self._last_trade_ms is not None
            and trade.timestamp_ms < self._last_trade_ms
        ):
            # DAT-005: fora de ordem — rejeitar, não reordenar.
            self.metrics.out_of_order_rejected += 1
            return []
        self._last_trade_ms = trade.timestamp_ms
        self.metrics.trades_accepted += 1

        closed: list[Candle] = []
        for tf in self.timeframes:
            tf_ms = TIMEFRAME_MS[tf]
            bucket = (trade.timestamp_ms // tf_ms) * tf_ms
            current = self._open[tf]
            if current is None:
                self._open[tf] = _Bucket(
                    open_time_ms=bucket,
                    open=trade.price,
                    high=trade.price,
                    low=trade.price,
                    close=trade.price,
                )
                self._open[tf].add(trade.price, trade.quantity)
                continue
            if bucket == current.open_time_ms:
                current.add(trade.price, trade.quantity)
                continue
            if bucket < current.open_time_ms:  # não ocorre (check global)
                self.metrics.out_of_order_rejected += 1
                continue
            # Bucket posterior: fecha o atual; buckets intermediários
            # sem trades são gaps (DAT-006) — sem candle inventado.
            skipped = (bucket - current.open_time_ms) // tf_ms - 1
            if skipped > 0:
                self.metrics.gap_buckets_skipped += skipped
            closed.append(
                current.to_candle(
                    exchange=self.exchange,
                    symbol=self.symbol,
                    timeframe=tf,
                )
            )
            self.metrics.candles_closed += 1
            self._open[tf] = _Bucket(
                open_time_ms=bucket,
                open=trade.price,
                high=trade.price,
                low=trade.price,
                close=trade.price,
            )
            self._open[tf].add(trade.price, trade.quantity)
        return closed

    def add_trades(self, trades: list[Trade]) -> list[Candle]:
        """Ingere vários trades em ordem; retorna candles fechados."""
        closed: list[Candle] = []
        for trade in trades:
            closed.extend(self.add_trade(trade))
        return closed

    def flush(self, now_ms: int) -> list[Candle]:
        """Fecha buckets abertos cujo fim já passou em ``now_ms``.

        Só fecha buckets completos no tempo (``close_time <= now``).
        O bucket corrente (ainda recebendo trades) não é fechado.
        """
        closed: list[Candle] = []
        for tf in self.timeframes:
            current = self._open[tf]
            if current is None:
                continue
            close_time = current.open_time_ms + TIMEFRAME_MS[tf] - 1
            if close_time <= now_ms:
                closed.append(
                    current.to_candle(
                        exchange=self.exchange,
                        symbol=self.symbol,
                        timeframe=tf,
                    )
                )
                self.metrics.candles_closed += 1
                self._open[tf] = None
        return closed

    def open_candles(self) -> list[Candle]:
        """Snapshot dos candles ainda abertos (parciais, não fechados)."""
        out: list[Candle] = []
        for tf in self.timeframes:
            current = self._open[tf]
            if current is not None:
                out.append(
                    current.to_candle(
                        exchange=self.exchange,
                        symbol=self.symbol,
                        timeframe=tf,
                    )
                )
        return out

    def health(self) -> dict[str, object]:
        """Estado do builder + métricas."""
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "timeframes": list(self.timeframes),
            "open_buckets": {
                tf: (b.open_time_ms if b is not None else None)
                for tf, b in self._open.items()
            },
            "last_trade_ms": self._last_trade_ms,
            **self.metrics.as_dict(),
        }


# ---------------------------------------------------------------------------
# Agregação de timeframes (DAT-004) e detecção de gaps (DAT-006)
# ---------------------------------------------------------------------------

def aggregate_candles(
    candles: list[Candle], target_timeframe: str
) -> list[Candle]:
    """Agrega candles fechados de um timeframe menor num maior.

    Regras:

    - Só candles **fechados** entram (quem chama garante; candles
      parciais de ``open_candles()`` não devem ser passados).
    - ``target`` deve ser múltiplo exato do timeframe de origem
      (ex.: 1m -> 5m, 15m; 1h -> 4h; 1d -> 1w). Caso contrário,
      ``ValueError`` — nunca agregar por aproximação.
    - Todos os candles devem ser do mesmo par e timeframe de origem,
      ordenados por ``open_time_ms`` (a função ordena uma cópia).
    - Buckets de origem ausentes não são preenchidos: o candle
      agregado reflete só os candles recebidos; a ausência continua
      detectável por :func:`detect_gaps` no timeframe alvo.

    Retorna os candles agregados ordenados por ``open_time_ms``.
    """
    target = validate_timeframe(target_timeframe)
    if not candles:
        return []
    source_tf = candles[0].timeframe
    validate_timeframe(source_tf)
    source_ms = TIMEFRAME_MS[source_tf]
    target_ms = TIMEFRAME_MS[target]
    if target_ms <= source_ms or target_ms % source_ms != 0:
        raise ValueError(
            f"não é possível agregar {source_tf} -> {target}: "
            "o alvo deve ser múltiplo exato da origem"
        )
    exchange = candles[0].exchange
    symbol = candles[0].symbol
    for candle in candles:
        if candle.exchange != exchange or candle.symbol != symbol:
            raise ValueError("aggregate_candles exige um só par (exchange/symbol)")
        if candle.timeframe != source_tf:
            raise ValueError("aggregate_candles exige um só timeframe de origem")

    ordered = sorted(candles, key=lambda c: c.open_time_ms)
    grouped: dict[int, list[Candle]] = {}
    for candle in ordered:
        bucket = (candle.open_time_ms // target_ms) * target_ms
        grouped.setdefault(bucket, []).append(candle)

    out: list[Candle] = []
    for bucket in sorted(grouped):
        group = grouped[bucket]
        out.append(
            Candle(
                exchange=exchange,
                symbol=symbol,
                timeframe=target,
                open_time_ms=bucket,
                close_time_ms=bucket + target_ms - 1,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum((c.volume for c in group), Decimal("0")),
                trades=(
                    sum(c.trades for c in group if c.trades is not None)
                    if any(c.trades is not None for c in group)
                    else None
                ),
            )
        )
    return out


def detect_gaps(
    candles: list[Candle], timeframe: str
) -> list[int]:
    """Detecta candles ausentes numa sequência (DAT-006).

    Recebe candles (ordenados ou não) de um timeframe e retorna a
    lista de ``open_time_ms`` esperados entre o primeiro e o último
    que **não** estão presentes. Lista vazia = sequência íntegra.
    Gaps nunca são preenchidos com dado inventado — só reportados.
    """
    tf = validate_timeframe(timeframe)
    if len(candles) < 2:
        return []
    tf_ms = TIMEFRAME_MS[tf]
    present = {c.open_time_ms for c in candles}
    first = min(present)
    last = max(present)
    missing: list[int] = []
    cursor = first
    while cursor <= last:
        if cursor not in present:
            missing.append(cursor)
        cursor += tf_ms
    return missing
