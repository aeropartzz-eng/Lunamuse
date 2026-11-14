"""Modelos de dados do contrato universal (Fase 3 — CON-002).

Dataclasses imutáveis com validação em ``__post_init__``. Regras:

- Todos os timestamps são inteiros em **milissegundos UTC**
  (ver :mod:`normalization` para conversão).
- Preços devem ser > 0; volumes/quantidades devem ser >= 0.
- Candle: ``high >= max(open, close)`` e ``low <= min(open, close)``;
  ``close_time_ms > open_time_ms``.
- OrderBook: bids em ordem decrescente de preço, asks em ordem
  crescente; preços > 0 e quantidades >= 0.
- Símbolos já chegam aqui normalizados (``BTC/USDT``); a normalização
  em si vive em :mod:`normalization`.
- ``raw`` preserva o payload original da fonte (CEX-005) quando
  relevante; nunca conter credenciais.

Estes são modelos de **dados** — não executam ordens. ``Order``,
``Fill`` e ``Position`` existem para que as fases 7 e 15 (market data
e execução/testnet) compartilhem o mesmo vocabulário; nenhum método
aqui envia ordem a nenhuma exchange.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Optional

# Limites de sanidade para timestamps (ms UTC): 2010-01-01 .. 2100-01-01.
# Evitam timestamps em segundos confundidos com ms, ou datas absurdas,
# sem depender do relógio da máquina (testes determinísticos).
MIN_TIMESTAMP_MS = 1_262_304_000_000
MAX_TIMESTAMP_MS = 4_102_444_800_000

MarketType = Literal["spot", "perp", "futures", "options"]
Side = Literal["buy", "sell"]
OrderType = Literal["limit", "market", "stop_limit", "stop_market"]
OrderStatus = Literal[
    "new", "partially_filled", "filled", "cancelled", "rejected", "expired"
]
PositionSide = Literal["long", "short", "flat"]


def _check_timestamp_ms(value: int, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} deve ser int (ms UTC), recebido {value!r}")
    if not MIN_TIMESTAMP_MS <= value <= MAX_TIMESTAMP_MS:
        raise ValueError(
            f"{name} fora da faixa plausível (ms UTC): {value}"
        )


def _check_non_negative(value: Decimal, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} não pode ser negativo: {value}")


def _check_positive(value: Decimal, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} deve ser > 0: {value}")


@dataclass(frozen=True)
class Exchange:
    """Uma exchange do catálogo (§3)."""

    id: str
    name: str
    group: str = "priority"  # "priority" (Fase 4/5) ou "expansion"
    status: str = "scaffold"  # "scaffold" | "connected" | "degraded" | "down"

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise ValueError("Exchange precisa de id e name não vazios")


@dataclass(frozen=True)
class Market:
    """Um mercado listado por uma exchange (par + tipo + regras)."""

    exchange: str
    symbol: str  # normalizado, ex.: "BTC/USDT"
    base: str  # ex.: "BTC"
    quote: str  # ex.: "USDT"
    market_type: MarketType = "spot"
    active: bool = True
    tick_size: Optional[Decimal] = None
    min_qty: Optional[Decimal] = None
    raw: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if "/" not in self.symbol:
            raise ValueError(
                f"symbol deve estar normalizado (BASE/QUOTE): {self.symbol!r}"
            )
        if not self.base or not self.quote:
            raise ValueError("Market precisa de base e quote não vazios")
        if self.tick_size is not None:
            _check_positive(self.tick_size, "tick_size")
        if self.min_qty is not None:
            _check_positive(self.min_qty, "min_qty")


@dataclass(frozen=True)
class Instrument:
    """Um instrumento negociável (contrato) dentro de um mercado.

    Para spot, coincide com o Market; para derivativos carrega as
    especificações do contrato (tamanho, liquidação, funding).
    """

    market: Market
    instrument_id: str  # id nativo da exchange, ex.: "BTCUSDT" (Binance)
    contract_size: Decimal = Decimal("1")
    settlement: str = "USDT"  # moeda de liquidação
    leverage_max: Optional[Decimal] = None

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("Instrument precisa de instrument_id")
        _check_positive(self.contract_size, "contract_size")
        if self.leverage_max is not None:
            _check_positive(self.leverage_max, "leverage_max")

    @property
    def symbol(self) -> str:
        """Símbolo normalizado do mercado deste instrumento."""
        return self.market.symbol


@dataclass(frozen=True)
class Trade:
    """Um trade individual recebido da fonte (nunca simulado)."""

    exchange: str
    symbol: str  # normalizado
    trade_id: str
    price: Decimal
    quantity: Decimal
    side: Side  # lado do agressor ("buy" | "sell")
    timestamp_ms: int  # ms UTC
    raw: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _check_positive(self.price, "price")
        _check_non_negative(self.quantity, "quantity")
        if self.side not in ("buy", "sell"):
            raise ValueError(f"side inválido: {self.side!r}")
        _check_timestamp_ms(self.timestamp_ms, "timestamp_ms")
        if not self.trade_id:
            raise ValueError("Trade precisa de trade_id")


@dataclass(frozen=True)
class Candle:
    """Um candle OHLCV de granularidade real da fonte (§3).

    Granularidade nunca é inventada: só timeframes fornecidos pela
    fonte entram aqui. Não simular ticks nem candles de 1s a partir
    de fontes que não dão trades individuais.
    """

    exchange: str
    symbol: str  # normalizado
    timeframe: str  # ex.: "1m", "5m", "1h", "1d"
    open_time_ms: int
    close_time_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trades: Optional[int] = None
    raw: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _check_timestamp_ms(self.open_time_ms, "open_time_ms")
        _check_timestamp_ms(self.close_time_ms, "close_time_ms")
        if self.close_time_ms <= self.open_time_ms:
            raise ValueError("close_time_ms deve ser > open_time_ms")
        for name in ("open", "high", "low", "close"):
            _check_positive(getattr(self, name), name)
        _check_non_negative(self.volume, "volume")
        if self.high < max(self.open, self.close):
            raise ValueError(
                f"high ({self.high}) < max(open, close) "
                f"({max(self.open, self.close)})"
            )
        if self.low > min(self.open, self.close):
            raise ValueError(
                f"low ({self.low}) > min(open, close) "
                f"({min(self.open, self.close)})"
            )
        if self.trades is not None and self.trades < 0:
            raise ValueError("trades não pode ser negativo")


@dataclass(frozen=True)
class OrderBook:
    """Snapshot do livro de ofertas em um instante (ms UTC)."""

    exchange: str
    symbol: str  # normalizado
    timestamp_ms: int
    bids: tuple[tuple[Decimal, Decimal], ...]  # (preço, qty), decrescente
    asks: tuple[tuple[Decimal, Decimal], ...]  # (preço, qty), crescente
    sequence: Optional[int] = None
    raw: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _check_timestamp_ms(self.timestamp_ms, "timestamp_ms")
        for side_name, levels, descending in (
            ("bids", self.bids, True),
            ("asks", self.asks, False),
        ):
            previous: Optional[Decimal] = None
            for price, qty in levels:
                _check_positive(price, f"{side_name} price")
                _check_non_negative(qty, f"{side_name} qty")
                if previous is not None:
                    if descending and price >= previous:
                        raise ValueError("bids devem estar em ordem decrescente")
                    if not descending and price <= previous:
                        raise ValueError("asks devem estar em ordem crescente")
                previous = price

    @property
    def best_bid(self) -> Optional[Decimal]:
        """Maior preço de compra, ou None se o book estiver vazio."""
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask(self) -> Optional[Decimal]:
        """Menor preço de venda, ou None se o book estiver vazio."""
        return self.asks[0][0] if self.asks else None

    @property
    def spread(self) -> Optional[Decimal]:
        """best_ask - best_bid, ou None se algum lado estiver vazio."""
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    @property
    def mid_price(self) -> Optional[Decimal]:
        """Preço médio entre best bid e best ask."""
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2


@dataclass(frozen=True)
class Ticker:
    """Último preço / ticker de um símbolo (leitura pública)."""

    exchange: str
    symbol: str  # normalizado
    last: Decimal
    timestamp_ms: int
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    change_24h_pct: Optional[Decimal] = None
    raw: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _check_positive(self.last, "last")
        _check_timestamp_ms(self.timestamp_ms, "timestamp_ms")
        if self.bid is not None:
            _check_positive(self.bid, "bid")
        if self.ask is not None:
            _check_positive(self.ask, "ask")
        if self.volume_24h is not None:
            _check_non_negative(self.volume_24h, "volume_24h")


@dataclass(frozen=True)
class FundingRate:
    """Funding rate de um contrato perpétuo (leitura pública)."""

    exchange: str
    symbol: str  # normalizado
    rate: Decimal  # ex.: 0.0001 = 0,01%
    timestamp_ms: int
    next_funding_ms: Optional[int] = None
    raw: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _check_timestamp_ms(self.timestamp_ms, "timestamp_ms")
        if self.next_funding_ms is not None:
            _check_timestamp_ms(self.next_funding_ms, "next_funding_ms")


@dataclass(frozen=True)
class OpenInterest:
    """Open interest de um contrato (leitura pública)."""

    exchange: str
    symbol: str  # normalizado
    value: Decimal  # em contratos (ou moeda base, conforme a fonte)
    timestamp_ms: int
    raw: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _check_non_negative(self.value, "value")
        _check_timestamp_ms(self.timestamp_ms, "timestamp_ms")


@dataclass(frozen=True)
class Order:
    """Registro de uma ordem (modelo de dados; não envia ordens).

    O envio real de ordens só existe na Fase 15, em testnet, e continua
    bloqueado em LIVE. Este modelo serve para reconciliação, fills e
    posições nas fases 7 e 15.
    """

    order_id: str
    exchange: str
    symbol: str  # normalizado
    side: Side
    order_type: OrderType
    quantity: Decimal
    status: OrderStatus = "new"
    price: Optional[Decimal] = None  # obrigatório para limit/stop_limit
    filled_quantity: Decimal = Decimal("0")
    created_ms: Optional[int] = None
    updated_ms: Optional[int] = None
    raw: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.order_id:
            raise ValueError("Order precisa de order_id")
        if self.side not in ("buy", "sell"):
            raise ValueError(f"side inválido: {self.side!r}")
        if self.order_type not in ("limit", "market", "stop_limit", "stop_market"):
            raise ValueError(f"order_type inválido: {self.order_type!r}")
        _check_positive(self.quantity, "quantity")
        _check_non_negative(self.filled_quantity, "filled_quantity")
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity não pode exceder quantity")
        if self.price is not None:
            _check_positive(self.price, "price")
        if self.order_type in ("limit", "stop_limit") and self.price is None:
            raise ValueError(f"price é obrigatório para {self.order_type}")
        if self.created_ms is not None:
            _check_timestamp_ms(self.created_ms, "created_ms")
        if self.updated_ms is not None:
            _check_timestamp_ms(self.updated_ms, "updated_ms")


@dataclass(frozen=True)
class Fill:
    """Execução (parcial ou total) de uma ordem."""

    fill_id: str
    order_id: str
    exchange: str
    symbol: str  # normalizado
    price: Decimal
    quantity: Decimal
    fee: Decimal = Decimal("0")
    timestamp_ms: int = 0
    raw: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.fill_id or not self.order_id:
            raise ValueError("Fill precisa de fill_id e order_id")
        _check_positive(self.price, "price")
        _check_positive(self.quantity, "quantity")
        _check_non_negative(self.fee, "fee")
        _check_timestamp_ms(self.timestamp_ms, "timestamp_ms")


@dataclass(frozen=True)
class Position:
    """Posição aberta (ou fechada) em um instrumento."""

    exchange: str
    symbol: str  # normalizado
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    mark_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    updated_ms: Optional[int] = None
    raw: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.side not in ("long", "short", "flat"):
            raise ValueError(f"side inválido: {self.side!r}")
        _check_non_negative(self.quantity, "quantity")
        if self.side == "flat" and self.quantity != 0:
            raise ValueError("posição flat deve ter quantity 0")
        if self.side != "flat" and self.quantity == 0:
            raise ValueError("posição long/short deve ter quantity > 0")
        _check_positive(self.entry_price, "entry_price")
        if self.mark_price is not None:
            _check_positive(self.mark_price, "mark_price")
        if self.updated_ms is not None:
            _check_timestamp_ms(self.updated_ms, "updated_ms")
