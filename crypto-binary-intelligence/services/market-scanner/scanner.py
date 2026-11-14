"""Scanners multinível (Fase 8 — SCN-001…SCN-003, especificação v4.1 §4).

Três níveis dinâmicos; os números são metas de dimensionamento, não
limites impostos pelas corretoras:

- Nível 1 — Discovery (``DiscoveryScanner``): catálogo, ticker, preço
  e variação, volume, candles de referência, liquidez estimada, novos
  pares. Meta ilustrativa: até 2.000 pares candidatos.
- Nível 2 — Active (``ActiveScanner``): trades, candles de alta
  resolução, indicadores simples (volatilidade, volume relativo),
  padrões de candle. Meta inicial: até 200 instrumentos.
- Nível 3 — Priority (``PriorityScanner``): trades detalhados, order
  book, bid/ask, CVD, imbalance, absorção, liquidity sweep. Meta
  inicial: até 50 ativos intensivos e até 20 com order book
  aprofundado.

Todos os scanners consomem o protocolo ``MarketDataSource`` (ver
``source.py``) — uma instância por exchange. Somente leitura pública;
nenhum método envia ordens ou usa chave de API.

Funções puras de métrica (``rel_volume``, ``atr_pct``,
``book_imbalance``, ``cvd`` etc.) são testáveis sem fonte e são
reutilizadas pela Fase 9 (indicadores) e pela Fase 10 (order flow).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from statistics import mean
from typing import Any, Optional

# Metas de dimensionamento (§4). Não são limites de corretora.
MAX_DISCOVERY = 2000
MAX_ACTIVE = 200
MAX_PRIORITY = 50
MAX_DEEP_BOOK = 20

ZERO = Decimal("0")


def _d(value: Any) -> Decimal:
    """Converte preço/volume (Decimal, int, float, str) para Decimal."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return ZERO
    return (numerator / denominator) * Decimal("100")


# ---------------------------------------------------------------------------
# Métricas puras (sem I/O)
# ---------------------------------------------------------------------------


def rel_volume(candles: list[Any]) -> Optional[Decimal]:
    """Volume do último candle / média dos volumes anteriores.

    Retorna None quando não há histórico suficiente (< 2 candles) ou
    a média anterior é zero.
    """
    if len(candles) < 2:
        return None
    volumes = [_d(c.volume) for c in candles]
    avg = mean(volumes[:-1])
    if avg == 0:
        return None
    return volumes[-1] / Decimal(str(avg))


def atr_pct(candles: list[Any]) -> Optional[Decimal]:
    """Volatilidade média: média de (high-low)/close em %, últimos candles."""
    if not candles:
        return None
    ranges = [
        _pct(_d(c.high) - _d(c.low), _d(c.close)) for c in candles
    ]
    return sum(ranges) / Decimal(len(ranges))


def price_change_pct(candles: list[Any]) -> Optional[Decimal]:
    """Variação do primeiro open ao último close, em %."""
    if not candles:
        return None
    first_open = _d(candles[0].open)
    last_close = _d(candles[-1].close)
    if first_open == 0:
        return None
    return _pct(last_close - first_open, first_open)


def spread_bps(book: Any) -> Optional[Decimal]:
    """Spread (best_ask - best_bid) / mid em basis points (1 bp = 0,01%)."""
    if book.best_bid is None or book.best_ask is None:
        return None
    mid = book.mid_price
    if mid is None or mid == 0:
        return None
    return (_d(book.spread) / _d(mid)) * Decimal("10000")


def book_depth_value(book: Any, depth: Optional[int] = None) -> Decimal:
    """Valor total (preço × qty) do book até ``depth`` níveis por lado."""
    total = ZERO
    for levels in (book.bids, book.asks):
        for price, qty in list(levels)[:depth]:
            total += _d(price) * _d(qty)
    return total


def book_imbalance(book: Any, depth: Optional[int] = None) -> Optional[Decimal]:
    """Imbalance (bid_qty - ask_qty) / (bid_qty + ask_qty), em [-1, 1].

    Positivo = pressão compradora no book; negativo = vendedora.
    """
    bid_qty = sum((_d(q) for _, q in list(book.bids)[:depth]), ZERO)
    ask_qty = sum((_d(q) for _, q in list(book.asks)[:depth]), ZERO)
    total = bid_qty + ask_qty
    if total == 0:
        return None
    return (bid_qty - ask_qty) / total


def cvd(trades: list[Any]) -> Decimal:
    """Cumulative Volume Delta: soma qty de buys menos qty de sells."""
    total = ZERO
    for t in trades:
        qty = _d(t.quantity)
        total += qty if t.side == "buy" else -qty
    return total


def detect_candle_pattern(candles: list[Any]) -> list[str]:
    """Padrões simples do último candle (Fase 10 aprofunda).

    - ``doji``: corpo <= 10% do range.
    - ``engulfing_bull`` / ``engulfing_bear``: corpo atual engole o
      anterior, com direção oposta.
    - ``hammer``: pavio inferior longo e corpo pequeno no topo.
    Um padrão isolado não gera entrada (§6); é só um sinal de triagem.
    """
    if len(candles) < 1:
        return []
    last = candles[-1]
    o, h, l, c = _d(last.open), _d(last.high), _d(last.low), _d(last.close)
    rng = h - l
    if rng <= 0:
        return []
    body = abs(c - o)
    patterns: list[str] = []
    if body <= rng * Decimal("0.1"):
        patterns.append("doji")
    lower_wick = min(o, c) - l
    if lower_wick >= body * 2 and body <= rng * Decimal("0.3"):
        patterns.append("hammer")
    if len(candles) >= 2:
        prev = candles[-2]
        po, pc = _d(prev.open), _d(prev.close)
        if c > o and pc < po and o <= pc and c >= po:
            patterns.append("engulfing_bull")
        elif c < o and pc > po and o >= pc and c <= po:
            patterns.append("engulfing_bear")
    return patterns


def detect_sweep(trades: list[Any], book: Any) -> bool:
    """Liquidity sweep (heurística): trade executado fora do top do book.

    Um trade de venda abaixo do best bid ou de compra acima do best
    ask varreu a liquidez do topo. Requer o book vigente no momento
    do trade; com snapshot posterior, é aproximação — documentado
    como heurística de triagem, não prova de sweep.
    """
    if book.best_bid is None or book.best_ask is None:
        return False
    for t in trades:
        price = _d(t.price)
        if t.side == "sell" and price < book.best_bid:
            return True
        if t.side == "buy" and price > book.best_ask:
            return True
    return False


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------


@dataclass
class DiscoveryRow:
    """Linha do Nível 1 para um (exchange, símbolo)."""

    exchange: str
    symbol: str
    price: Decimal
    change_24h_pct: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    liquidity_est_usd: Optional[Decimal] = None
    volatility_pct: Optional[Decimal] = None
    rel_volume: Optional[Decimal] = None
    is_new: bool = False
    score: Decimal = ZERO

    def to_dict(self) -> dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "price": str(self.price),
            "change_24h_pct": (
                str(self.change_24h_pct) if self.change_24h_pct is not None else None
            ),
            "volume_24h": (
                str(self.volume_24h) if self.volume_24h is not None else None
            ),
            "liquidity_est_usd": (
                str(self.liquidity_est_usd)
                if self.liquidity_est_usd is not None
                else None
            ),
            "volatility_pct": (
                str(self.volatility_pct) if self.volatility_pct is not None else None
            ),
            "rel_volume": (
                str(self.rel_volume) if self.rel_volume is not None else None
            ),
            "is_new": self.is_new,
            "score": str(self.score),
        }


@dataclass
class ActiveMetrics:
    """Métricas do Nível 2 para um (exchange, símbolo)."""

    exchange: str
    symbol: str
    price: Decimal
    change_pct: Optional[Decimal] = None
    rel_volume: Optional[Decimal] = None
    volatility_pct: Optional[Decimal] = None
    patterns: list[str] = field(default_factory=list)
    score: Decimal = ZERO


@dataclass
class PriorityMetrics:
    """Métricas do Nível 3 para um (exchange, símbolo)."""

    exchange: str
    symbol: str
    price: Decimal
    spread_bps: Optional[Decimal] = None
    imbalance: Optional[Decimal] = None
    cvd: Decimal = ZERO
    depth_value_usd: Decimal = ZERO
    absorption: bool = False
    sweep: bool = False
    score: Decimal = ZERO


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------


class DiscoveryScanner:
    """Nível 1 (SCN-001): varredura ampla e barata do catálogo.

    Por símbolo: 1 ticker + candles de referência (1h, 24). A
    liquidez é *estimada* como ``volume_24h × preço`` (assume volume
    em moeda base, como no modelo ``Ticker``); é triagem, não medida
    de profundidade — a profundidade real vem do book no Nível 3.
    """

    def __init__(self, reference_timeframe: str = "1h") -> None:
        self.reference_timeframe = reference_timeframe

    def scan(
        self,
        source: Any,
        exchange: str,
        symbols: list[str],
        previous_catalog: Optional[set[str]] = None,
    ) -> tuple[list[DiscoveryRow], list[str]]:
        """Varre ``symbols``; retorna (linhas, símbolos novos).

        Símbolos que a fonte rejeita (erro) são ignorados e contados
        em ``self.last_errors`` — o scanner nunca quebra por um par.
        """
        rows: list[DiscoveryRow] = []
        new_symbols: list[str] = []
        self.last_errors: list[str] = []
        for symbol in symbols[:MAX_DISCOVERY]:
            if previous_catalog is not None and symbol not in previous_catalog:
                new_symbols.append(symbol)
            try:
                ticker = source.get_ticker(symbol)
                candles = source.get_candles(
                    symbol, self.reference_timeframe, limit=24
                )
            except Exception as exc:  # fonte instável: pular o par
                self.last_errors.append(f"{exchange}:{symbol}: {exc}")
                continue
            vol = rel_volume(candles)
            volat = atr_pct(candles)
            liquidity = None
            if ticker.volume_24h is not None:
                liquidity = _d(ticker.volume_24h) * _d(ticker.last)
            # Score de triagem: atividade (volume relativo) +
            # movimento (variação e volatilidade). Sem unidade
            # financeira; só ordena a fila de promoção.
            score = ZERO
            if vol is not None:
                score += vol
            if ticker.change_24h_pct is not None:
                score += abs(_d(ticker.change_24h_pct)) / Decimal("10")
            if volat is not None:
                score += volat
            rows.append(
                DiscoveryRow(
                    exchange=exchange,
                    symbol=symbol,
                    price=_d(ticker.last),
                    change_24h_pct=(
                        _d(ticker.change_24h_pct)
                        if ticker.change_24h_pct is not None
                        else None
                    ),
                    volume_24h=(
                        _d(ticker.volume_24h)
                        if ticker.volume_24h is not None
                        else None
                    ),
                    liquidity_est_usd=liquidity,
                    volatility_pct=volat,
                    rel_volume=vol,
                    is_new=symbol in new_symbols,
                    score=score,
                )
            )
        rows.sort(key=lambda r: r.score, reverse=True)
        return rows, new_symbols


class ActiveScanner:
    """Nível 2 (SCN-002): análise de trades e candles de alta resolução."""

    def analyze(
        self,
        source: Any,
        exchange: str,
        symbol: str,
        timeframe: str = "5m",
        candle_limit: int = 50,
        trade_limit: int = 100,
    ) -> ActiveMetrics:
        candles = source.get_candles(symbol, timeframe, limit=candle_limit)
        # Trades lidos para validar disponibilidade do feed; as
        # métricas de fluxo (CVD etc.) vivem no Nível 3.
        try:
            source.get_trades(symbol, limit=trade_limit)
        except Exception:
            pass
        if not candles:
            raise ValueError(f"sem candles para {exchange}:{symbol}")
        price = _d(candles[-1].close)
        rv = rel_volume(candles)
        volat = atr_pct(candles)
        change = price_change_pct(candles)
        patterns = detect_candle_pattern(candles)
        score = ZERO
        if rv is not None:
            score += rv * 2
        if volat is not None:
            score += volat
        if change is not None:
            score += abs(change) / Decimal("10")
        score += Decimal(len(patterns))
        return ActiveMetrics(
            exchange=exchange,
            symbol=symbol,
            price=price,
            change_pct=change,
            rel_volume=rv,
            volatility_pct=volat,
            patterns=patterns,
            score=score,
        )


class PriorityScanner:
    """Nível 3 (SCN-003): order book, CVD, imbalance, absorção, sweep."""

    def analyze(
        self,
        source: Any,
        exchange: str,
        symbol: str,
        book_depth: int = 20,
        trade_limit: int = 200,
    ) -> PriorityMetrics:
        book = source.get_order_book(symbol, depth=book_depth)
        trades = source.get_trades(symbol, limit=trade_limit)
        price = book.mid_price if book.mid_price is not None else ZERO
        imb = book_imbalance(book)
        depth_value = book_depth_value(book)
        trade_cvd = cvd(trades)
        # Absorção (heurística): volume agressivo grande num lado com
        # variação de preço pequena nos trades — alguém absorveu a
        # pressão. Medido como: |CVD| alto e range de preços dos
        # trades < 0,2% do preço médio.
        absorption = False
        if trades:
            prices = [_d(t.price) for t in trades]
            total_qty = sum((_d(t.quantity) for t in trades), ZERO)
            avg_price = sum(prices) / Decimal(len(prices))
            if avg_price > 0:
                trade_range_pct = _pct(max(prices) - min(prices), avg_price)
                if abs(trade_cvd) >= total_qty * Decimal("0.7") and (
                    trade_range_pct < Decimal("0.2")
                ):
                    absorption = True
        score = ZERO
        if imb is not None:
            score += abs(imb) * 10
        if book.spread is not None and book.mid_price:
            score += max(ZERO, Decimal("20") - (spread_bps(book) or ZERO)) / 10
        return PriorityMetrics(
            exchange=exchange,
            symbol=symbol,
            price=_d(price),
            spread_bps=spread_bps(book),
            imbalance=imb,
            cvd=trade_cvd,
            depth_value_usd=depth_value,
            absorption=absorption,
            sweep=detect_sweep(trades, book),
            score=score,
        )


__all__ = [
    "MAX_DISCOVERY",
    "MAX_ACTIVE",
    "MAX_PRIORITY",
    "MAX_DEEP_BOOK",
    "rel_volume",
    "atr_pct",
    "price_change_pct",
    "spread_bps",
    "book_depth_value",
    "book_imbalance",
    "cvd",
    "detect_candle_pattern",
    "detect_sweep",
    "DiscoveryRow",
    "ActiveMetrics",
    "PriorityMetrics",
    "DiscoveryScanner",
    "ActiveScanner",
    "PriorityScanner",
]
