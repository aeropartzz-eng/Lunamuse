"""Market Data — Fase 7 (DAT-001…DAT-010, especificação §2/§5/§11).

Camada 3: ingestão de trades via WebSocket público, deduplicação,
validação cronológica, detecção de gaps, Order Book Manager,
persistência nas tabelas da Fase 2 (``002_market.sql``) e política
de retenção (§11).

Somente **dados públicos de mercado**. Nenhuma chave de API é usada
(nem de teste), nenhum método envia ordens e nada aqui toca em conta
de exchange. A execução continua bloqueada (403) e o scaffold força
RESEARCH quando ``EXECUTION_MODE=LIVE``.

Componentes:

- :func:`parse_trade_message` — traduz mensagens nativas de trades
  (Binance, Bybit, OKX) para :class:`models.Trade`.
- :class:`TradePipeline` — ingestão + dedup + validação cronológica
  (DAT-001/002/005/006), sobre o ``ConnectionManager`` da Fase 3.
- :class:`OrderBookManager` — snapshot + deltas com sequência,
  detecção de divergência, spread e profundidade (DAT-007/008).
- :class:`MarketDataSource` — protocolo consumido pela Fase 8:
  ``get_ticker`` / ``get_candles`` / ``get_trades`` /
  ``get_order_book``.
- :class:`PostgresMarketDataRepository` — persistência contra o
  schema ``002_market.sql`` (código pronto; o banco real só existe
  na VPS — ver README). :class:`InMemoryMarketDataRepository` é o
  fake usado nos testes.
- :class:`RetentionPolicy` — retenção/expurgo por tabela e timeframe
  (§11), como código documentado (não executado aqui).
- :class:`LiveTradeFeed` — cliente WebSocket público (``websockets``)
  para Binance/Bybit/OKX, com reconexão via ``ConnectionManager``.

Os modelos vivem em ``services/exchange-connectors/`` (``models``,
``normalization``, ``connection``, ``errors``) — importar com esse
diretório no ``sys.path``, como em ``tests/conftest.py``.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from connection import ConnectionManager, next_backoff
from errors import ExchangeError
from models import Candle, OrderBook, Ticker, Trade
from normalization import (
    normalize_side,
    normalize_symbol,
    normalize_timestamp,
    validate_timeframe,
)

# ---------------------------------------------------------------------------
# Endpoints WebSocket públicos (sem chave) — DAT-001
# ---------------------------------------------------------------------------

WS_URLS: dict[str, str] = {
    # Binance: o stream vai na URL; sem mensagem de subscribe.
    "binance": "wss://stream.binance.com:9443/ws/{stream}",
    "bybit": "wss://stream.bybit.com/v5/public/spot",
    "okx": "wss://ws.okx.com:8443/ws/v5/public",
}


def binance_stream_name(symbol: str) -> str:
    """Nome do stream de trades da Binance: ``btcusdt@trade``."""
    native = normalize_symbol(symbol, exchange="binance").replace("/", "").lower()
    return f"{native}@trade"


def bybit_trade_topic(symbol: str) -> str:
    """Tópico de trades públicos da Bybit v5: ``publicTrade.BTCUSDT``."""
    native = normalize_symbol(symbol, exchange="bybit").replace("/", "").upper()
    return f"publicTrade.{native}"


def okx_inst_id(symbol: str) -> str:
    """Instrumento OKX: ``BTC-USDT``."""
    base, _, quote = normalize_symbol(symbol, exchange="okx").partition("/")
    return f"{base}-{quote}"


def subscribe_message(exchange_id: str, symbol: str) -> Optional[dict[str, Any]]:
    """Mensagem de subscribe do canal de trades (None = URL já assina)."""
    exchange_id = exchange_id.lower()
    if exchange_id == "binance":
        return None
    if exchange_id == "bybit":
        return {"op": "subscribe", "args": [bybit_trade_topic(symbol)]}
    if exchange_id == "okx":
        return {
            "op": "subscribe",
            "args": [{"channel": "trades", "instId": okx_inst_id(symbol)}],
        }
    raise ValueError(f"exchange sem feed de trades implementado: {exchange_id!r}")


def ws_url(exchange_id: str, symbol: str) -> str:
    """URL do WebSocket público de trades da exchange."""
    exchange_id = exchange_id.lower()
    if exchange_id not in WS_URLS:
        raise ValueError(f"exchange sem feed de trades implementado: {exchange_id!r}")
    if exchange_id == "binance":
        return WS_URLS["binance"].format(stream=binance_stream_name(symbol))
    return WS_URLS[exchange_id]


# ---------------------------------------------------------------------------
# Parsers de mensagens nativas de trades (DAT-001)
# ---------------------------------------------------------------------------

def _trade(
    *,
    exchange: str,
    symbol_raw: str,
    trade_id: str,
    price: Any,
    quantity: Any,
    side: str,
    timestamp_ms: Any,
    raw: Any,
) -> Trade:
    """Constrói um Trade normalizado; id sintético se a fonte não der."""
    symbol = normalize_symbol(symbol_raw, exchange=exchange)
    if isinstance(timestamp_ms, str) and timestamp_ms.strip().lstrip("-").isdigit():
        # OKX e outras fontes mandam o timestamp como string numérica;
        # normalize_timestamp a leria como ISO 8601 — converter antes.
        timestamp_ms = int(timestamp_ms)
    ts = normalize_timestamp(timestamp_ms)
    price_d = Decimal(str(price))
    qty_d = Decimal(str(quantity))
    tid = str(trade_id) if trade_id not in (None, "") else (
        f"synth-{ts}-{price_d}-{qty_d}"
    )
    return Trade(
        exchange=exchange,
        symbol=symbol,
        trade_id=tid,
        price=price_d,
        quantity=qty_d,
        side=normalize_side(side),
        timestamp_ms=ts,
        raw=raw,
    )


def _parse_binance_trade(payload: dict[str, Any]) -> list[Trade]:
    # {"e":"trade","s":"BTCUSDT","t":12345,"p":"...","q":"...","T":...,"m":bool}
    # "m" (buyer is maker) = true  -> o agressor vendeu.
    if payload.get("e") != "trade":
        return []
    return [
        _trade(
            exchange="binance",
            symbol_raw=payload["s"],
            trade_id=payload.get("t"),
            price=payload["p"],
            quantity=payload["q"],
            side="sell" if payload.get("m") else "buy",
            timestamp_ms=payload["T"],
            raw=payload,
        )
    ]


def _parse_bybit_trades(payload: dict[str, Any]) -> list[Trade]:
    # {"topic":"publicTrade.BTCUSDT","data":[{i,T,p,v,S}]}
    topic = str(payload.get("topic", ""))
    if not topic.startswith("publicTrade."):
        return []
    symbol_raw = topic.split(".", 1)[1]
    out: list[Trade] = []
    for row in payload.get("data") or []:
        out.append(
            _trade(
                exchange="bybit",
                symbol_raw=symbol_raw,
                trade_id=row.get("i"),
                price=row["p"],
                quantity=row["v"],
                side=row["S"],
                timestamp_ms=row["T"],
                raw=row,
            )
        )
    return out


def _parse_okx_trades(payload: dict[str, Any]) -> list[Trade]:
    # {"arg":{"channel":"trades","instId":"BTC-USDT"},"data":[{tradeId,px,sz,side,ts}]}
    arg = payload.get("arg") or {}
    if arg.get("channel") != "trades":
        return []
    symbol_raw = arg.get("instId", "")
    out: list[Trade] = []
    for row in payload.get("data") or []:
        out.append(
            _trade(
                exchange="okx",
                symbol_raw=symbol_raw,
                trade_id=row.get("tradeId"),
                price=row["px"],
                quantity=row["sz"],
                side=row["side"],
                timestamp_ms=row["ts"],
                raw=row,
            )
        )
    return out


_TRADE_PARSERS: dict[str, Callable[[dict[str, Any]], list[Trade]]] = {
    "binance": _parse_binance_trade,
    "bybit": _parse_bybit_trades,
    "okx": _parse_okx_trades,
}


def parse_trade_message(
    exchange_id: str, payload: str | dict[str, Any]
) -> list[Trade]:
    """Traduz uma mensagem WebSocket nativa para trades normalizados.

    Aceita o JSON como string ou dict já decodificado. Mensagens que
    não são trades (acks de subscribe, pong, snapshots de book etc.)
    retornam ``[]`` — não são erro. Exchange desconhecida levanta
    ``ValueError``; payload de trade malformado levanta o erro de
    validação do modelo/normalização (registrado como ``parse_errors``
    pelo :class:`TradePipeline`).
    """
    exchange_id = exchange_id.lower()
    parser = _TRADE_PARSERS.get(exchange_id)
    if parser is None:
        raise ValueError(
            f"exchange sem parser de trades: {exchange_id!r} "
            f"(implementados: {sorted(_TRADE_PARSERS)})"
        )
    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload
    if not isinstance(data, dict):
        raise ValueError(f"mensagem de trade deve ser um objeto JSON: {data!r}")
    return parser(data)


# ---------------------------------------------------------------------------
# Trade Pipeline (DAT-001/002/005/006)
# ---------------------------------------------------------------------------

@dataclass
class TradePipelineMetrics:
    """Contadores do pipeline (§16 — métricas de mercado)."""

    messages_seen: int = 0
    trades_seen: int = 0
    trades_accepted: int = 0
    duplicates_dropped: int = 0
    out_of_order_rejected: int = 0
    parse_errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "messages_seen": self.messages_seen,
            "trades_seen": self.trades_seen,
            "trades_accepted": self.trades_accepted,
            "duplicates_dropped": self.duplicates_dropped,
            "out_of_order_rejected": self.out_of_order_rejected,
            "parse_errors": self.parse_errors,
        }


class TradePipeline:
    """Ingestão de trades: parse, dedup, validação cronológica.

    Dedup (DAT-002) pela chave ``(exchange, symbol, trade_id)`` no
    ``MessageDeduplicator`` do ``ConnectionManager``; quando a fonte
    não informa id, o parser gera um id sintético
    ``synth-{ts}-{price}-{qty}``, o que equivale a dedup por
    (timestamp, preço, quantidade). Validação cronológica (DAT-005):
    trade com timestamp anterior ao último aceito do par é rejeitado
    e contado — o passado nunca é reordenado. Gaps de sequência
    (DAT-006) ficam com o ``SequenceTracker`` do manager quando a
    fonte informa sequência (trades públicos das 3 exchanges não
    trazem; o rastreio vale para o book, em :class:`OrderBookManager`).

    Assinantes (``subscribe``) recebem cada trade aceito — é assim
    que o Candle Builder se pluga no pipeline.
    """

    def __init__(
        self,
        exchange_id: str,
        *,
        connection_manager: Optional[ConnectionManager] = None,
    ) -> None:
        self.exchange_id = exchange_id.lower()
        self.manager = connection_manager or ConnectionManager(exchange_id)
        self._subscribers: list[Callable[[Trade], None]] = []
        self._last_ts: dict[str, int] = {}  # symbol -> último ts aceito
        self.metrics = TradePipelineMetrics()

    def subscribe(self, fn: Callable[[Trade], None]) -> None:
        """Registra um consumidor de trades aceitos (ex.: CandleBuilder)."""
        self._subscribers.append(fn)

    def ingest(
        self, payload: str | dict[str, Any], *, received_at_ms: Optional[int] = None
    ) -> list[Trade]:
        """Processa uma mensagem WS; retorna os trades aceitos."""
        self.metrics.messages_seen += 1
        try:
            trades = parse_trade_message(self.exchange_id, payload)
        except Exception:  # noqa: BLE001 - parse ruim vira métrica
            self.metrics.parse_errors += 1
            return []
        accepted: list[Trade] = []
        for trade in trades:
            self.metrics.trades_seen += 1
            # Dedup via ConnectionManager (conta em duplicates_dropped).
            outcome = self.manager.on_message(
                channel=f"trades:{trade.symbol}",
                dedup_key=(trade.exchange, trade.symbol, trade.trade_id),
                received_at_ms=received_at_ms,
            )
            if outcome["status"] == "duplicate":
                self.metrics.duplicates_dropped += 1
                continue
            last = self._last_ts.get(trade.symbol)
            if last is not None and trade.timestamp_ms < last:
                self.metrics.out_of_order_rejected += 1
                continue
            self._last_ts[trade.symbol] = trade.timestamp_ms
            self.metrics.trades_accepted += 1
            accepted.append(trade)
            for fn in self._subscribers:
                fn(trade)
        return accepted

    def health(self) -> dict[str, Any]:
        """Saúde da conexão + métricas do pipeline."""
        out = self.manager.health()
        out["pipeline"] = self.metrics.as_dict()
        return out


# ---------------------------------------------------------------------------
# Order Book Manager (DAT-007/008)
# ---------------------------------------------------------------------------

@dataclass
class OrderBookMetrics:
    """Contadores do book (§16 — qualidade do Order Book)."""

    snapshots_applied: int = 0
    updates_applied: int = 0
    duplicates_dropped: int = 0
    gaps_detected: int = 0
    divergences: int = 0
    updates_without_snapshot: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "snapshots_applied": self.snapshots_applied,
            "updates_applied": self.updates_applied,
            "duplicates_dropped": self.duplicates_dropped,
            "gaps_detected": self.gaps_detected,
            "divergences": self.divergences,
            "updates_without_snapshot": self.updates_without_snapshot,
        }


class OrderBookManager:
    """Livro de ofertas com snapshot + deltas sequenciados.

    Protocolo (§5, DAT-007/008):

    1. ``apply_snapshot`` estabelece o estado e a sequência base.
    2. ``apply_update`` só aceita o delta seguinte
       (``sequence == last_sequence + 1``). Delta antigo é duplicata;
       delta com salto de sequência é gap: **não** é aplicado — o
       book é marcado divergente e ``resync_required`` passa a True,
       exigindo novo snapshot. Aplicar delta fora de ordem corromperia
       o livro silenciosamente.
    3. Após cada aplicação, livro cruzado (``best_bid >= best_ask``)
       também marca divergência.
    4. Sem snapshot prévio, deltas são recusados
       (``updates_without_snapshot``).

    Deltas sem sequência (algumas fontes não informam) são aplicados
    sem checagem de ordem e retornam ``"ok_unsequenced"``.
    """

    def __init__(self, exchange: str, symbol: str, *, depth: int = 20) -> None:
        if depth <= 0:
            raise ValueError("depth deve ser > 0")
        self.exchange = exchange
        self.symbol = symbol
        self.depth = depth
        self._bids: dict[Decimal, Decimal] = {}
        self._asks: dict[Decimal, Decimal] = {}
        self._last_sequence: Optional[int] = None
        self._last_timestamp_ms: Optional[int] = None
        self._has_snapshot = False
        self.diverged = False
        self.resync_required = False
        self.metrics = OrderBookMetrics()

    # -- aplicação -----------------------------------------------------------

    def apply_snapshot(self, book: OrderBook) -> str:
        """Substitui o estado pelo snapshot; limpa divergência."""
        if book.exchange != self.exchange or book.symbol != self.symbol:
            raise ValueError(
                f"snapshot de {book.exchange}/{book.symbol} não pertence "
                f"a este book ({self.exchange}/{self.symbol})"
            )
        self._bids = {price: qty for price, qty in book.bids}
        self._asks = {price: qty for price, qty in book.asks}
        self._last_sequence = book.sequence
        self._last_timestamp_ms = book.timestamp_ms
        self._has_snapshot = True
        self.diverged = False
        self.resync_required = False
        self.metrics.snapshots_applied += 1
        if self._crossed():
            self.diverged = True
            self.metrics.divergences += 1
            return "diverged"
        return "snapshot"

    def apply_update(
        self,
        *,
        sequence: Optional[int],
        bids: list[tuple[Decimal, Decimal]],
        asks: list[tuple[Decimal, Decimal]],
        timestamp_ms: int,
    ) -> str:
        """Aplica um delta; retorna o status da aplicação."""
        if not self._has_snapshot:
            self.metrics.updates_without_snapshot += 1
            return "no_snapshot"
        if sequence is not None and self._last_sequence is not None:
            if sequence <= self._last_sequence:
                self.metrics.duplicates_dropped += 1
                return "duplicate"
            if sequence > self._last_sequence + 1:
                self.metrics.gaps_detected += 1
                self.diverged = True
                self.resync_required = True
                return "gap"
        for price, qty in bids:
            self._apply_level(self._bids, price, qty)
        for price, qty in asks:
            self._apply_level(self._asks, price, qty)
        if sequence is not None:
            self._last_sequence = sequence
        self._last_timestamp_ms = timestamp_ms
        self.metrics.updates_applied += 1
        if self._crossed():
            self.diverged = True
            self.metrics.divergences += 1
            return "diverged"
        return "ok" if sequence is not None else "ok_unsequenced"

    @staticmethod
    def _apply_level(
        side: dict[Decimal, Decimal], price: Decimal, qty: Decimal
    ) -> None:
        if qty == 0:
            side.pop(price, None)
        else:
            side[price] = qty

    def _crossed(self) -> bool:
        if not self._bids or not self._asks:
            return False
        return max(self._bids) >= min(self._asks)

    # -- leitura ---------------------------------------------------------------

    def snapshot(self, depth: Optional[int] = None) -> OrderBook:
        """Snapshot atual do livro (ordenado, limitado à profundidade)."""
        depth = depth or self.depth
        ts = self._last_timestamp_ms or int(time.time() * 1000)
        bids = tuple(
            sorted(self._bids.items(), reverse=True)[:depth]
        )
        asks = tuple(sorted(self._asks.items())[:depth])
        return OrderBook(
            exchange=self.exchange,
            symbol=self.symbol,
            timestamp_ms=ts,
            bids=bids,
            asks=asks,
            sequence=self._last_sequence,
        )

    @property
    def spread(self) -> Optional[Decimal]:
        """best_ask - best_bid (None se algum lado vazio)."""
        book = self.snapshot(depth=1)
        return book.spread

    @property
    def mid_price(self) -> Optional[Decimal]:
        """Preço médio entre best bid e best ask."""
        book = self.snapshot(depth=1)
        return book.mid_price

    def depth_quantity(self, side: str, levels: int = 10) -> Decimal:
        """Quantidade somada nos ``levels`` melhores níveis de um lado."""
        if side == "bid":
            levels_sorted = sorted(self._bids.items(), reverse=True)[:levels]
        elif side == "ask":
            levels_sorted = sorted(self._asks.items())[:levels]
        else:
            raise ValueError(f"side inválido: {side!r} (use 'bid'/'ask')")
        return sum((qty for _, qty in levels_sorted), Decimal("0"))

    def imbalance(self, levels: int = 10) -> Optional[Decimal]:
        """Imbalance (bid-ask)/(bid+ask) nos N melhores níveis.

        +1 = só bids; -1 = só asks; None se o book estiver vazio.
        """
        bid_qty = self.depth_quantity("bid", levels)
        ask_qty = self.depth_quantity("ask", levels)
        total = bid_qty + ask_qty
        if total == 0:
            return None
        return (bid_qty - ask_qty) / total

    def health(self) -> dict[str, Any]:
        """Estado do book + métricas."""
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "has_snapshot": self._has_snapshot,
            "last_sequence": self._last_sequence,
            "last_timestamp_ms": self._last_timestamp_ms,
            "diverged": self.diverged,
            "resync_required": self.resync_required,
            "bid_levels": len(self._bids),
            "ask_levels": len(self._asks),
            "spread": str(self.spread) if self.spread is not None else None,
            **self.metrics.as_dict(),
        }


# ---------------------------------------------------------------------------
# Protocolo MarketDataSource (Fase 8 vai consumir) — DAT-001…DAT-008
# ---------------------------------------------------------------------------

@runtime_checkable
class MarketDataSource(Protocol):
    """Fonte de dados de mercado normalizados (leitura pública).

    Contrato consumido pela Fase 8 (Scanner e Cross-Exchange).
    Implementações: :class:`RestMarketDataSource` (REST via
    ``ExchangeAdapter``) e :class:`InMemoryMarketDataSource` (memória,
    para testes e desenvolvimento). Métodos síncronos por ora; a
    variante assíncrona (streaming) é o :class:`LiveTradeFeed`.
    """

    def get_ticker(self, symbol: str) -> Ticker:
        """Último preço / ticker do símbolo."""
        ...

    def get_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[Candle]:
        """Candles OHLCV (só timeframes reais da fonte — §3)."""
        ...

    def get_trades(self, symbol: str, limit: int = 100) -> list[Trade]:
        """Trades recentes do símbolo (nunca simulados)."""
        ...

    def get_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        """Snapshot do livro de ofertas."""
        ...


class RestMarketDataSource:
    """MarketDataSource sobre o REST público de um ExchangeAdapter.

    Sem autenticação: delega aos métodos ``fetch_*`` do adapter
    (Fases 4–5). Mantém um cache curto em memória dos últimos trades
    e candles por símbolo, para a Fase 8 não refazer REST a cada
    leitura.
    """

    def __init__(self, adapter: Any, *, cache_size: int = 1_000) -> None:
        self.adapter = adapter
        self.cache_size = cache_size
        self._trades: dict[str, deque[Trade]] = {}
        self._candles: dict[tuple[str, str], deque[Candle]] = {}

    @property
    def exchange_id(self) -> str:
        return getattr(self.adapter, "exchange_id", "?")

    def get_ticker(self, symbol: str) -> Ticker:
        return self.adapter.fetch_ticker(normalize_symbol(symbol))

    def get_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[Candle]:
        tf = validate_timeframe(timeframe)
        if limit <= 0:
            raise ValueError("limit deve ser > 0")
        symbol = normalize_symbol(symbol)
        candles = self.adapter.fetch_ohlcv(symbol, tf, limit=limit)
        key = (symbol, tf)
        cache = self._candles.setdefault(key, deque(maxlen=self.cache_size))
        cache.clear()
        cache.extend(candles)
        return list(candles)

    def get_trades(self, symbol: str, limit: int = 100) -> list[Trade]:
        if limit <= 0:
            raise ValueError("limit deve ser > 0")
        symbol = normalize_symbol(symbol)
        trades = self.adapter.fetch_trades(symbol, limit=limit)
        cache = self._trades.setdefault(symbol, deque(maxlen=self.cache_size))
        seen = {t.trade_id for t in cache}
        for trade in trades:
            if trade.trade_id not in seen:
                cache.append(trade)
        return list(trades)

    def get_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        if depth <= 0:
            raise ValueError("depth deve ser > 0")
        return self.adapter.fetch_order_book(normalize_symbol(symbol), depth=depth)


class InMemoryMarketDataSource:
    """MarketDataSource em memória (testes, Fase 8 em desenvolvimento).

    Os dados são inseridos explicitamente — nada aqui é simulado a
    partir do nada: quem alimenta a fonte é responsável pela origem
    (trades reais, fixtures de teste ou candles do builder).
    """

    def __init__(self, exchange: str) -> None:
        self.exchange = exchange
        self._tickers: dict[str, Ticker] = {}
        self._candles: dict[tuple[str, str], list[Candle]] = {}
        self._trades: dict[str, list[Trade]] = {}
        self._books: dict[str, OrderBook] = {}

    def add_ticker(self, ticker: Ticker) -> None:
        self._tickers[ticker.symbol] = ticker

    def add_candles(self, candles: list[Candle]) -> None:
        for candle in candles:
            key = (candle.symbol, candle.timeframe)
            self._candles.setdefault(key, []).append(candle)
        for key in self._candles:
            self._candles[key].sort(key=lambda c: c.open_time_ms)

    def add_trades(self, trades: list[Trade]) -> None:
        for trade in trades:
            self._trades.setdefault(trade.symbol, []).append(trade)

    def set_order_book(self, book: OrderBook) -> None:
        self._books[book.symbol] = book

    def get_ticker(self, symbol: str) -> Ticker:
        symbol = normalize_symbol(symbol)
        if symbol not in self._tickers:
            raise ValueError(f"sem ticker em memória: {symbol}")
        return self._tickers[symbol]

    def get_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[Candle]:
        tf = validate_timeframe(timeframe)
        if limit <= 0:
            raise ValueError("limit deve ser > 0")
        symbol = normalize_symbol(symbol)
        return list(self._candles.get((symbol, tf), [])[-limit:])

    def get_trades(self, symbol: str, limit: int = 100) -> list[Trade]:
        if limit <= 0:
            raise ValueError("limit deve ser > 0")
        symbol = normalize_symbol(symbol)
        return list(self._trades.get(symbol, [])[-limit:])

    def get_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        symbol = normalize_symbol(symbol)
        if symbol not in self._books:
            raise ValueError(f"sem book em memória: {symbol}")
        book = self._books[symbol]
        return OrderBook(
            exchange=book.exchange,
            symbol=book.symbol,
            timestamp_ms=book.timestamp_ms,
            bids=tuple(book.bids[:depth]),
            asks=tuple(book.asks[:depth]),
            sequence=book.sequence,
        )


# ---------------------------------------------------------------------------
# Persistência (DAT-009) — contra infrastructure/database/002_market.sql
# ---------------------------------------------------------------------------

def _jsonable(value: Any) -> Optional[str]:
    """Serializa ``raw`` para JSONB; None quando não serializável."""
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return None


def _to_timestamp_sql() -> str:
    """Expressão SQL para converter ms UTC em TIMESTAMPTZ."""
    return "to_timestamp(%s / 1000.0)"


class MarketDataRepository(Protocol):
    """Persistência de dados de mercado (DAT-009).

    Implementações: :class:`PostgresMarketDataRepository` (PostgreSQL/
    TimescaleDB da VPS) e :class:`InMemoryMarketDataRepository`
    (fake em memória, para testes — sem banco).
    """

    def save_trades(self, trades: list[Trade]) -> int:
        """Grava trades; retorna linhas inseridas."""
        ...

    def save_candles(
        self, candles: list[Candle], *, source: str = "builder"
    ) -> int:
        """Grava candles; ``source`` é 'builder' ou 'exchange'."""
        ...

    def save_orderbook_snapshot(self, book: OrderBook) -> int:
        """Grava um snapshot completo do livro."""
        ...

    def save_orderbook_event(
        self,
        *,
        exchange: str,
        symbol: str,
        timestamp_ms: int,
        event_type: str,
        side: Optional[str],
        price: Optional[Decimal],
        quantity: Optional[Decimal],
        sequence: int,
    ) -> int:
        """Grava um evento incremental do livro."""
        ...

    def save_ticker(self, ticker: Ticker) -> int:
        """Grava um ticker (histórico curto; o corrente vive no Redis)."""
        ...


class PostgresMarketDataRepository:
    """Repositório real (PostgreSQL/TimescaleDB).

    Recebe uma conexão DB-API (ex.: ``psycopg``) — injetada, nunca
    criada aqui, para não embutir DSN/credencial no código. Cada
    método executa ``INSERT ... ON CONFLICT DO NOTHING`` com os PKs
    de ``002_market.sql``, então replays são idempotentes.

    Como plugar na VPS (ver README do serviço): criar a conexão com
    as credenciais do ``.env`` (``DATABASE_URL``), aplicar as
    migrações ``001_init.sql`` + ``002_market.sql`` e instanciar::

        repo = PostgresMarketDataRepository(conn)

    Os métodos ``build_*`` devolvem o ``(sql, params)`` sem executar
    — úteis para auditoria e para os testes (sem banco aqui).
    """

    def __init__(self, connection: Any) -> None:
        self.conn = connection

    # -- builders (SQL + params, sem executar) -------------------------------

    @staticmethod
    def build_save_trades(trades: list[Trade]) -> tuple[str, list[tuple]]:
        sql = (
            "INSERT INTO market_trades "
            "(time, exchange, symbol, trade_id, side, price, quantity, "
            " quote_quantity, is_buyer_maker, raw) VALUES "
            f"({_to_timestamp_sql()}, %s, %s, %s, %s, %s, %s, %s, %s, "
            "CAST(%s AS jsonb)) "
            "ON CONFLICT (time, exchange, symbol, trade_id) DO NOTHING"
        )
        params = [
            (
                t.timestamp_ms,
                t.exchange,
                t.symbol,
                t.trade_id,
                t.side,
                t.price,
                t.quantity,
                t.price * t.quantity,  # quote_quantity
                t.side == "sell",  # is_buyer_maker (agressor sell)
                _jsonable(t.raw),
            )
            for t in trades
        ]
        return sql, params

    @staticmethod
    def build_save_candles(
        candles: list[Candle], *, source: str = "builder"
    ) -> tuple[str, list[tuple]]:
        if source not in ("builder", "exchange"):
            raise ValueError(f"source inválido: {source!r}")
        sql = (
            "INSERT INTO market_candles "
            "(time, exchange, symbol, timeframe, open, high, low, close, "
            " volume, trades_count, source, is_closed) VALUES "
            f"({_to_timestamp_sql()}, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, TRUE) "
            "ON CONFLICT (time, exchange, symbol, timeframe) DO NOTHING"
        )
        params = [
            (
                c.open_time_ms,
                c.exchange,
                c.symbol,
                c.timeframe,
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume,
                c.trades,
                source,
            )
            for c in candles
        ]
        return sql, params

    @staticmethod
    def build_save_orderbook_snapshot(book: OrderBook) -> tuple[str, tuple]:
        sql = (
            "INSERT INTO orderbook_snapshots "
            "(time, exchange, symbol, bids, asks, best_bid, best_ask, "
            " spread, mid_price, sequence) VALUES "
            f"({_to_timestamp_sql()}, %s, %s, CAST(%s AS jsonb), "
            "CAST(%s AS jsonb), %s, %s, %s, %s, %s) "
            "ON CONFLICT (time, exchange, symbol) DO NOTHING"
        )
        params = (
            book.timestamp_ms,
            book.exchange,
            book.symbol,
            json.dumps([[str(p), str(q)] for p, q in book.bids]),
            json.dumps([[str(p), str(q)] for p, q in book.asks]),
            book.best_bid,
            book.best_ask,
            book.spread,
            book.mid_price,
            book.sequence,
        )
        return sql, params

    @staticmethod
    def build_save_orderbook_event(
        *,
        exchange: str,
        symbol: str,
        timestamp_ms: int,
        event_type: str,
        side: Optional[str],
        price: Optional[Decimal],
        quantity: Optional[Decimal],
        sequence: int,
    ) -> tuple[str, tuple]:
        if event_type not in ("snapshot", "update", "delete"):
            raise ValueError(f"event_type inválido: {event_type!r}")
        sql = (
            "INSERT INTO orderbook_events "
            "(time, exchange, symbol, event_type, side, price, quantity, "
            " sequence) VALUES "
            f"({_to_timestamp_sql()}, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (time, exchange, symbol, sequence) DO NOTHING"
        )
        return sql, (
            timestamp_ms,
            exchange,
            symbol,
            event_type,
            side,
            price,
            quantity,
            sequence,
        )

    @staticmethod
    def build_save_ticker(ticker: Ticker) -> tuple[str, tuple]:
        sql = (
            "INSERT INTO market_tickers "
            "(time, exchange, symbol, last_price, bid, ask, volume_24h) "
            f"VALUES ({_to_timestamp_sql()}, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (time, exchange, symbol) DO NOTHING"
        )
        return sql, (
            ticker.timestamp_ms,
            ticker.exchange,
            ticker.symbol,
            ticker.last,
            ticker.bid,
            ticker.ask,
            ticker.volume_24h,
        )

    # -- execução --------------------------------------------------------------

    def _execute(self, sql: str, params_list: list[tuple]) -> int:
        rows = 0
        with self.conn.cursor() as cur:
            for params in params_list:
                cur.execute(sql, params)
                rows += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        self.conn.commit()
        return rows

    def save_trades(self, trades: list[Trade]) -> int:
        if not trades:
            return 0
        sql, params = self.build_save_trades(trades)
        return self._execute(sql, params)

    def save_candles(
        self, candles: list[Candle], *, source: str = "builder"
    ) -> int:
        if not candles:
            return 0
        sql, params = self.build_save_candles(candles, source=source)
        return self._execute(sql, params)

    def save_orderbook_snapshot(self, book: OrderBook) -> int:
        sql, params = self.build_save_orderbook_snapshot(book)
        return self._execute(sql, [params])

    def save_orderbook_event(
        self,
        *,
        exchange: str,
        symbol: str,
        timestamp_ms: int,
        event_type: str,
        side: Optional[str],
        price: Optional[Decimal],
        quantity: Optional[Decimal],
        sequence: int,
    ) -> int:
        sql, params = self.build_save_orderbook_event(
            exchange=exchange,
            symbol=symbol,
            timestamp_ms=timestamp_ms,
            event_type=event_type,
            side=side,
            price=price,
            quantity=quantity,
            sequence=sequence,
        )
        return self._execute(sql, [params])

    def save_ticker(self, ticker: Ticker) -> int:
        sql, params = self.build_save_ticker(ticker)
        return self._execute(sql, [params])


class InMemoryMarketDataRepository:
    """Fake em memória do repositório (testes; sem Postgres).

    Guarda as linhas como dicts, com as mesmas colunas do schema
    ``002_market.sql``. ``rows(tabela)`` devolve cópia da lista.
    """

    TABLES = (
        "market_trades",
        "market_candles",
        "orderbook_snapshots",
        "orderbook_events",
        "market_tickers",
    )

    def __init__(self) -> None:
        self._store: dict[str, list[dict[str, Any]]] = {
            table: [] for table in self.TABLES
        }

    def rows(self, table: str) -> list[dict[str, Any]]:
        if table not in self._store:
            raise ValueError(f"tabela desconhecida: {table!r}")
        return list(self._store[table])

    def save_trades(self, trades: list[Trade]) -> int:
        seen = {
            (r["time"], r["exchange"], r["symbol"], r["trade_id"])
            for r in self._store["market_trades"]
        }
        count = 0
        for t in trades:
            key = (t.timestamp_ms, t.exchange, t.symbol, t.trade_id)
            if key in seen:
                continue
            seen.add(key)
            self._store["market_trades"].append(
                {
                    "time": t.timestamp_ms,
                    "exchange": t.exchange,
                    "symbol": t.symbol,
                    "trade_id": t.trade_id,
                    "side": t.side,
                    "price": t.price,
                    "quantity": t.quantity,
                    "quote_quantity": t.price * t.quantity,
                    "is_buyer_maker": t.side == "sell",
                    "raw": t.raw,
                }
            )
            count += 1
        return count

    def save_candles(
        self, candles: list[Candle], *, source: str = "builder"
    ) -> int:
        if source not in ("builder", "exchange"):
            raise ValueError(f"source inválido: {source!r}")
        seen = {
            (r["time"], r["exchange"], r["symbol"], r["timeframe"])
            for r in self._store["market_candles"]
        }
        count = 0
        for c in candles:
            key = (c.open_time_ms, c.exchange, c.symbol, c.timeframe)
            if key in seen:
                continue
            seen.add(key)
            self._store["market_candles"].append(
                {
                    "time": c.open_time_ms,
                    "exchange": c.exchange,
                    "symbol": c.symbol,
                    "timeframe": c.timeframe,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "trades_count": c.trades,
                    "source": source,
                    "is_closed": True,
                }
            )
            count += 1
        return count

    def save_orderbook_snapshot(self, book: OrderBook) -> int:
        self._store["orderbook_snapshots"].append(
            {
                "time": book.timestamp_ms,
                "exchange": book.exchange,
                "symbol": book.symbol,
                "bids": [[str(p), str(q)] for p, q in book.bids],
                "asks": [[str(p), str(q)] for p, q in book.asks],
                "best_bid": book.best_bid,
                "best_ask": book.best_ask,
                "spread": book.spread,
                "mid_price": book.mid_price,
                "sequence": book.sequence,
            }
        )
        return 1

    def save_orderbook_event(
        self,
        *,
        exchange: str,
        symbol: str,
        timestamp_ms: int,
        event_type: str,
        side: Optional[str],
        price: Optional[Decimal],
        quantity: Optional[Decimal],
        sequence: int,
    ) -> int:
        if event_type not in ("snapshot", "update", "delete"):
            raise ValueError(f"event_type inválido: {event_type!r}")
        self._store["orderbook_events"].append(
            {
                "time": timestamp_ms,
                "exchange": exchange,
                "symbol": symbol,
                "event_type": event_type,
                "side": side,
                "price": price,
                "quantity": quantity,
                "sequence": sequence,
            }
        )
        return 1

    def save_ticker(self, ticker: Ticker) -> int:
        self._store["market_tickers"].append(
            {
                "time": ticker.timestamp_ms,
                "exchange": ticker.exchange,
                "symbol": ticker.symbol,
                "last_price": ticker.last,
                "bid": ticker.bid,
                "ask": ticker.ask,
                "volume_24h": ticker.volume_24h,
            }
        )
        return 1


# ---------------------------------------------------------------------------
# Retenção e arquivamento (DAT-010, §11)
# ---------------------------------------------------------------------------

# Retenção por tabela (§11). Candles 1s: 30 dias; 1m/5m: 24 meses;
# demais timeframes: 3 anos. Sinais, ordens e auditoria têm retenção
# permanente e NÃO aparecem aqui.
RETENTION_POLICIES: dict[str, Any] = {
    "market_trades": timedelta(days=7),
    "orderbook_snapshots": timedelta(days=7),
    "orderbook_events": timedelta(days=7),
    "market_tickers": timedelta(days=30),
    "market_candles": {
        "1s": timedelta(days=30),
        "5s": timedelta(days=30),
        "15s": timedelta(days=30),
        "30s": timedelta(days=30),
        "1m": timedelta(days=730),  # 24 meses
        "3m": timedelta(days=730),
        "5m": timedelta(days=730),
        "15m": timedelta(days=1095),  # 3 anos
        "30m": timedelta(days=1095),
        "1h": timedelta(days=1095),
        "2h": timedelta(days=1095),
        "4h": timedelta(days=1095),
        "6h": timedelta(days=1095),
        "8h": timedelta(days=1095),
        "12h": timedelta(days=1095),
        "1d": timedelta(days=1095),
        "1w": timedelta(days=1095),
    },
    "funding_rates": timedelta(days=730),
    "open_interest": timedelta(days=730),
    "liquidations": timedelta(days=730),
    "onchain_events": timedelta(days=730),
}


def _format_interval(delta: timedelta) -> str:
    """Formata um timedelta como INTERVAL do PostgreSQL."""
    days = delta.days
    seconds = delta.seconds
    if seconds:
        return f"{days} days {seconds} seconds"
    return f"{days} days"


class RetentionPolicy:
    """Política de retenção (§11) como código — não executa nada.

    Gera o SQL de expurgo/arquivamento para rodar na VPS **somente
    depois** de confirmar o arquivamento externo (object storage),
    como já determinam os comentários de ``002_market.sql``. Nada
    aqui abre conexão nem apaga dados: os métodos devolvem strings
    SQL (e parâmetros) para revisão humana e execução controlada.
    """

    @staticmethod
    def retention_for(table: str, timeframe: Optional[str] = None) -> timedelta:
        """Retenção configurada para a tabela (e timeframe, se houver)."""
        if table not in RETENTION_POLICIES:
            raise ValueError(f"tabela sem política de retenção: {table!r}")
        policy = RETENTION_POLICIES[table]
        if isinstance(policy, dict):
            if timeframe is None:
                raise ValueError(
                    f"{table} exige timeframe (política por timeframe)"
                )
            tf = validate_timeframe(timeframe)
            return policy[tf]
        if timeframe is not None:
            raise ValueError(f"{table} não tem política por timeframe")
        return policy

    @staticmethod
    def retention_sql(table: str) -> str:
        """SQL TimescaleDB ``add_retention_policy`` (tabela inteira).

        Para ``market_candles`` a política é por timeframe e NÃO cabe
        num ``add_retention_policy`` único — use :meth:`purge_sql`
        por timeframe (job de expurgo) ou particione por timeframe.
        """
        if table == "market_candles":
            raise ValueError(
                "market_candles tem retenção por timeframe; "
                "use purge_sql(timeframe=...) ou particione a tabela"
            )
        delta = RetentionPolicy.retention_for(table)
        return (
            f"SELECT add_retention_policy('{table}', "
            f"INTERVAL '{_format_interval(delta)}');"
        )

    @staticmethod
    def purge_sql(
        table: str,
        *,
        timeframe: Optional[str] = None,
        before_ms: Optional[int] = None,
    ) -> tuple[str, tuple]:
        """DELETE parametrizado para expurgar linhas antigas.

        ``before_ms`` (ms UTC) é o corte: apaga ``time < before``.
        Sem ``before_ms``, o corte é ``now() - retenção``. Retorna
        ``(sql, params)`` — nada é executado aqui.
        """
        delta = RetentionPolicy.retention_for(table, timeframe)
        if timeframe is not None:
            if before_ms is not None:
                return (
                    f"DELETE FROM {table} WHERE timeframe = %s AND "
                    f"time < {_to_timestamp_sql()}",
                    (timeframe, before_ms),
                )
            return (
                f"DELETE FROM {table} WHERE timeframe = %s AND "
                f"time < now() - INTERVAL '{_format_interval(delta)}'",
                (timeframe,),
            )
        if before_ms is not None:
            return (
                f"DELETE FROM {table} WHERE time < {_to_timestamp_sql()}",
                (before_ms,),
            )
        return (
            f"DELETE FROM {table} WHERE "
            f"time < now() - INTERVAL '{_format_interval(delta)}'",
            (),
        )

    @staticmethod
    def export_sql(table: str, *, before_ms: int) -> tuple[str, tuple]:
        """SELECT para arquivar linhas antigas antes do expurgo.

        O fluxo na VPS é: ``COPY (SELECT ...) TO STDOUT`` -> object
        storage (100 GB, ~US$ 3/mês) -> só então o ``purge_sql``.
        """
        if table not in RETENTION_POLICIES:
            raise ValueError(f"tabela sem política de retenção: {table!r}")
        return (
            f"SELECT * FROM {table} WHERE time < {_to_timestamp_sql()} "
            "ORDER BY time",
            (before_ms,),
        )


# ---------------------------------------------------------------------------
# Feed ao vivo via WebSocket público (DAT-001)
# ---------------------------------------------------------------------------

class LiveTradeFeed:
    """Cliente WebSocket público de trades (Binance/Bybit/OKX).

    Sem chave de API. Usa ``websockets`` + o ``ConnectionManager``
    da Fase 3 para backoff de reconexão (``next_backoff``) e
    recuperação de assinatura (reenvia o subscribe a cada
    reconexão). Cada mensagem recebida vai para o ``TradePipeline``
    (parse, dedup, validação cronológica).

    ``connect_fn`` é injetável (``async fn(url, **kwargs) -> ws``)
    para testes com websocket fake — sem rede nos testes. Em
    produção usa ``websockets.asyncio.client.connect``.
    """

    def __init__(
        self,
        exchange_id: str,
        symbol: str,
        pipeline: TradePipeline,
        *,
        duration_s: Optional[float] = None,
        max_messages: Optional[int] = None,
        max_reconnects: int = 5,
        connect_fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.exchange_id = exchange_id.lower()
        if self.exchange_id not in _TRADE_PARSERS:
            raise ValueError(
                f"exchange sem feed de trades: {exchange_id!r}"
            )
        self.symbol = normalize_symbol(symbol, exchange=self.exchange_id)
        self.pipeline = pipeline
        self.duration_s = duration_s
        self.max_messages = max_messages
        self.max_reconnects = max_reconnects
        self._connect_fn = connect_fn
        self.messages_received = 0
        self.reconnects = 0

    def _proxy_kwargs(self) -> dict[str, Any]:
        """Proxy de egresso do sandbox, quando configurado no ambiente.

        Na VPS não há proxy: o dict volta vazio e o ``websockets``
        conecta direto. Não é credencial — só roteamento de rede.
        """
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        return {"proxy": proxy} if proxy else {}

    async def _default_connect(self, url: str) -> Any:
        from websockets.asyncio.client import connect

        return await connect(url, **self._proxy_kwargs())

    async def run(self) -> dict[str, Any]:
        """Roda o feed até ``duration_s`` ou ``max_messages``.

        Retorna estatísticas (mensagens, trades aceitos, reconexões).
        """
        url = ws_url(self.exchange_id, self.symbol)
        subscribe = subscribe_message(self.exchange_id, self.symbol)
        connect_fn = self._connect_fn or self._default_connect
        started = time.monotonic()
        attempt = 0
        connected_once = False
        last_error: Optional[BaseException] = None
        while True:
            if self.duration_s is not None and (
                time.monotonic() - started >= self.duration_s
            ):
                break
            if self.max_messages is not None and (
                self.messages_received >= self.max_messages
            ):
                break
            try:
                ws = await connect_fn(url)
            except Exception as exc:  # noqa: BLE001 - reconectar
                last_error = exc
                if attempt >= self.max_reconnects:
                    raise RuntimeError(
                        f"feed {self.exchange_id}: sem conexão após "
                        f"{self.max_reconnects} tentativas: {exc}"
                    ) from exc
                delay = next_backoff(attempt)
                attempt += 1
                self.reconnects += 1
                await asyncio.sleep(delay)
                continue
            attempt = 0
            connected_once = True
            try:
                if subscribe is not None:
                    await ws.send(json.dumps(subscribe))
                async for message in ws:
                    self.messages_received += 1
                    self.pipeline.ingest(message)
                    if self.max_messages is not None and (
                        self.messages_received >= self.max_messages
                    ):
                        break
                    if self.duration_s is not None and (
                        time.monotonic() - started >= self.duration_s
                    ):
                        break
                # Fim do stream sem erro (ex.: servidor fechou): tentar
                # reconectar dentro do limite, como queda de conexão.
                if self.duration_s is not None and (
                    time.monotonic() - started >= self.duration_s
                ):
                    break
                if self.max_messages is not None and (
                    self.messages_received >= self.max_messages
                ):
                    break
                if attempt >= self.max_reconnects:
                    break
                delay = next_backoff(attempt)
                attempt += 1
                self.reconnects += 1
                await asyncio.sleep(delay)
            finally:
                try:
                    await ws.close()
                except Exception:  # noqa: BLE001 - fechar não pode falhar
                    pass
        if not connected_once:
            # O prazo expirou sem nenhuma conexão bem-sucedida: não
            # é "0 mensagens", é falha de conexão — levantar, para o
            # chamador (smoke) cair no fallback em vez de fingir OK.
            raise RuntimeError(
                f"feed {self.exchange_id}: nenhuma conexão estabelecida "
                f"em {self.duration_s}s: {last_error}"
            )
        return {
            "exchange": self.exchange_id,
            "symbol": self.symbol,
            "messages_received": self.messages_received,
            "trades_accepted": self.pipeline.metrics.trades_accepted,
            "duplicates_dropped": self.pipeline.metrics.duplicates_dropped,
            "parse_errors": self.pipeline.metrics.parse_errors,
            "reconnects": self.reconnects,
        }
