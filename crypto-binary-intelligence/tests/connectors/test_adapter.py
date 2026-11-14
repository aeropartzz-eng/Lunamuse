"""Testes do contrato universal — adapter, modelos, normalização e erros.

Fase 3 — CON-007. Somente mocks/fakes: nenhuma rede real, nenhuma
chave de API, nenhuma ordem enviada.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from base import ExchangeAdapter, normalize_symbol
from envelope import ResponseEnvelope, envelope_from_exception, error_response, ok_response
from errors import ErrorCode, ExchangeError, error_from_http_status
from models import (
    Candle,
    Fill,
    FundingRate,
    Instrument,
    Market,
    OpenInterest,
    Order,
    OrderBook,
    Position,
    Ticker,
    Trade,
)
from normalization import (
    canonical_asset,
    denormalize_symbol,
    normalize_order_type,
    normalize_side,
    normalize_symbol as norm_symbol,
    normalize_timestamp,
    validate_timeframe,
)

TS = 1_790_985_600_000  # 2026-10-03 00:00:00 UTC, em ms


# ---------------------------------------------------------------------------
# Fake adapter (implementação de referência do contrato)
# ---------------------------------------------------------------------------

class FakeAdapter(ExchangeAdapter):
    """Adapter fake: dados fixos, sem rede. Serve de referência."""

    exchange_id = "fake"
    name = "Fake"

    def __init__(self) -> None:
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def health(self) -> dict:
        return {
            "exchange": "fake",
            "connected": self.connected,
            "last_message_age_ms": 0,
        }

    def fetch_markets(self) -> list[Market]:
        return [
            Market(exchange="fake", symbol="BTC/USDT", base="BTC",
                   quote="USDT", market_type="spot"),
            Market(exchange="fake", symbol="ETH/USDT", base="ETH",
                   quote="USDT", market_type="spot"),
        ]

    def fetch_ticker(self, symbol: str) -> Ticker:
        if self.normalize(symbol) != "BTC/USDT":
            raise ExchangeError(
                ErrorCode.INVALID_SYMBOL, f"símbolo desconhecido: {symbol}",
                exchange="fake", symbol=symbol,
            )
        return Ticker(
            exchange="fake", symbol="BTC/USDT", last=Decimal("67000"),
            timestamp_ms=TS, bid=Decimal("66990"), ask=Decimal("67010"),
            volume_24h=Decimal("1234.5"),
        )

    def fetch_trades(self, symbol: str, limit: int = 100) -> list[Trade]:
        return [
            Trade(exchange="fake", symbol=self.normalize(symbol),
                  trade_id="t1", price=Decimal("67000"),
                  quantity=Decimal("0.01"), side="buy", timestamp_ms=TS)
        ][:limit]

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]:
        validate_timeframe(timeframe)
        return [
            Candle(
                exchange="fake", symbol=self.normalize(symbol),
                timeframe=timeframe, open_time_ms=TS,
                close_time_ms=TS + 60_000,
                open=Decimal("67000"), high=Decimal("67100"),
                low=Decimal("66900"), close=Decimal("67050"),
                volume=Decimal("12.5"),
            )
        ][:limit]

    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        return OrderBook(
            exchange="fake", symbol=self.normalize(symbol), timestamp_ms=TS,
            bids=((Decimal("67000"), Decimal("0.5")),
                  (Decimal("66990"), Decimal("1.0")))[:depth],
            asks=((Decimal("67010"), Decimal("0.4")),
                  (Decimal("67020"), Decimal("0.9")))[:depth],
        )

    def fetch_funding_rate(self, symbol: str) -> FundingRate:
        return FundingRate(
            exchange="fake", symbol=self.normalize(symbol),
            rate=Decimal("0.0001"), timestamp_ms=TS,
            next_funding_ms=TS + 8 * 3_600_000,
        )

    def fetch_open_interest(self, symbol: str) -> OpenInterest:
        return OpenInterest(
            exchange="fake", symbol=self.normalize(symbol),
            value=Decimal("123456"), timestamp_ms=TS,
        )


# ---------------------------------------------------------------------------
# Adapter: interface e ciclo de vida
# ---------------------------------------------------------------------------

def test_adapter_is_abstract_without_implementation():
    """ExchangeAdapter não pode ser instanciado sem os métodos."""
    with pytest.raises(TypeError):
        ExchangeAdapter()  # type: ignore[abstract]


def test_fake_adapter_connect_disconnect_health():
    adapter = FakeAdapter()
    assert adapter.health()["connected"] is False
    adapter.connect()
    assert adapter.health()["connected"] is True
    adapter.disconnect()
    assert adapter.health()["connected"] is False


def test_fetch_markets_returns_normalized_models():
    markets = FakeAdapter().fetch_markets()
    assert [m.symbol for m in markets] == ["BTC/USDT", "ETH/USDT"]
    assert all(isinstance(m, Market) for m in markets)


def test_fetch_ticker_and_invalid_symbol():
    adapter = FakeAdapter()
    ticker = adapter.fetch_ticker("btcusdt")
    assert ticker.symbol == "BTC/USDT"
    assert ticker.last == Decimal("67000")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("XXX/YYY")
    assert excinfo.value.code == ErrorCode.INVALID_SYMBOL
    assert excinfo.value.retryable is False


def test_fetch_trades_ohlcv_orderbook_funding_oi():
    adapter = FakeAdapter()
    assert adapter.fetch_trades("BTC/USDT")[0].side == "buy"
    candle = adapter.fetch_ohlcv("BTC/USDT", "1m")[0]
    assert candle.close == Decimal("67050")
    book = adapter.fetch_order_book("BTC/USDT")
    assert book.best_bid == Decimal("67000")
    assert book.spread == Decimal("10")
    assert adapter.fetch_funding_rate("BTC/USDT").rate == Decimal("0.0001")
    assert adapter.fetch_open_interest("BTC/USDT").value == Decimal("123456")


def test_legacy_wrappers_delegate_to_canonical_methods():
    """Nomes antigos do scaffold continuam funcionando (CON-001)."""
    adapter = FakeAdapter()
    assert adapter.list_markets()[0]["symbol"] == "BTC/USDT"
    assert adapter.get_ticker("BTCUSDT")["last"] == "67000"
    assert adapter.get_trades("btc-usdt")[0]["trade_id"] == "t1"
    assert adapter.get_candles("BTC/USDT", "1m")[0]["close"] == "67050"
    assert adapter.get_orderbook("BTC/USDT")["bids"][0][0] == "67000"
    with pytest.raises(NotImplementedError):
        adapter.subscribe(["ticker"])


def test_ohlcv_rejects_invented_timeframe():
    with pytest.raises(ValueError):
        FakeAdapter().fetch_ohlcv("BTC/USDT", "7m")


# ---------------------------------------------------------------------------
# Normalização de símbolos (CON-003)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("BTC/USDT", "BTC/USDT"),
        ("BTCUSDT", "BTC/USDT"),
        ("btc-usdt", "BTC/USDT"),
        ("BTC_USDT", "BTC/USDT"),
        ("btc usdt", "BTC/USDT"),
        ("ETHUSDC", "ETH/USDC"),
        ("BTC/USDT:USDT", "BTC/USDT:USDT"),
        ("BTCUSDT-PERP", "BTC/USDT:USDT"),
    ],
)
def test_normalize_symbol_variants(raw, expected):
    assert norm_symbol(raw) == expected
    assert normalize_symbol(raw) == expected  # compat scaffold (base.py)


def test_normalize_symbol_perp_market_type():
    assert norm_symbol("BTCUSDT", market_type="perp") == "BTC/USDT:USDT"
    assert norm_symbol("BTC/USDT", market_type="spot") == "BTC/USDT"


def test_normalize_symbol_invalid():
    for bad in ("", "BTC", "BTC/USDT/EXTRA", "XXXQQQ"):
        with pytest.raises(ExchangeError) as excinfo:
            norm_symbol(bad)
        assert excinfo.value.code == ErrorCode.INVALID_SYMBOL


def test_asset_alias_kraken_xbt():
    assert canonical_asset("XBT", "kraken") == "BTC"
    assert canonical_asset("XDG", "kraken") == "DOGE"
    assert norm_symbol("XBTUSD", "kraken") == "BTC/USD"
    assert denormalize_symbol("BTC/USD", "kraken") == "XBTUSD"
    assert denormalize_symbol("BTC/USDT", "binance") == "BTCUSDT"


# ---------------------------------------------------------------------------
# Normalização de timestamps, lados e tipos (CON-003)
# ---------------------------------------------------------------------------

def test_normalize_timestamp_variants():
    assert normalize_timestamp(1_790_985_600_000) == 1_790_985_600_000
    assert normalize_timestamp(1_790_985_600) == 1_790_985_600_000  # segundos
    assert normalize_timestamp("2026-10-03T00:00:00Z") == 1_790_985_600_000
    dt = datetime(2026, 10, 3, tzinfo=timezone.utc)
    assert normalize_timestamp(dt) == 1_790_985_600_000
    dt_naive = datetime(2026, 10, 3)  # naive = UTC
    assert normalize_timestamp(dt_naive) == 1_790_985_600_000
    with pytest.raises(ValueError):
        normalize_timestamp("não-é-data")
    with pytest.raises(ValueError):
        normalize_timestamp(None)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "raw, expected", [("BUY", "buy"), ("bid", "buy"), ("LONG", "buy"),
                      ("b", "buy"), ("sell", "sell"), ("ASK", "sell"),
                      ("short", "sell"), ("S", "sell")]
)
def test_normalize_side(raw, expected):
    assert normalize_side(raw) == expected


def test_normalize_side_invalid():
    with pytest.raises(ValueError):
        normalize_side("hold")


@pytest.mark.parametrize(
    "raw, expected",
    [("LIMIT", "limit"), ("market", "market"), ("STOP_LIMIT", "stop_limit"),
     ("stop-market", "stop_market")],
)
def test_normalize_order_type(raw, expected):
    assert normalize_order_type(raw) == expected


def test_validate_timeframe():
    assert validate_timeframe("1m") == "1m"
    assert validate_timeframe("1w") == "1w"
    with pytest.raises(ValueError):
        validate_timeframe("7m")  # granularidade inventada: rejeitada
    with pytest.raises(ValueError):
        validate_timeframe("1s5")


# ---------------------------------------------------------------------------
# Validação de modelos (CON-002)
# ---------------------------------------------------------------------------

def test_candle_validation_rejects_inconsistent_ohlc():
    with pytest.raises(ValueError):
        Candle(exchange="fake", symbol="BTC/USDT", timeframe="1m",
               open_time_ms=TS, close_time_ms=TS + 60_000,
               open=Decimal("100"), high=Decimal("90"),  # high < open
               low=Decimal("95"), close=Decimal("99"),
               volume=Decimal("1"))
    with pytest.raises(ValueError):
        Candle(exchange="fake", symbol="BTC/USDT", timeframe="1m",
               open_time_ms=TS, close_time_ms=TS,  # close <= open
               open=Decimal("100"), high=Decimal("101"),
               low=Decimal("99"), close=Decimal("100"),
               volume=Decimal("1"))
    with pytest.raises(ValueError):  # volume negativo
        Candle(exchange="fake", symbol="BTC/USDT", timeframe="1m",
               open_time_ms=TS, close_time_ms=TS + 60_000,
               open=Decimal("100"), high=Decimal("101"),
               low=Decimal("99"), close=Decimal("100"),
               volume=Decimal("-1"))


def test_candle_validation_rejects_bad_timestamp():
    with pytest.raises(ValueError):  # segundos, não ms
        Candle(exchange="fake", symbol="BTC/USDT", timeframe="1m",
               open_time_ms=1_791_000_000, close_time_ms=1_791_000_060,
               open=Decimal("100"), high=Decimal("101"),
               low=Decimal("99"), close=Decimal("100"),
               volume=Decimal("1"))


def test_trade_validation():
    with pytest.raises(ValueError):  # preço <= 0
        Trade(exchange="fake", symbol="BTC/USDT", trade_id="t",
              price=Decimal("0"), quantity=Decimal("1"), side="buy",
              timestamp_ms=TS)
    with pytest.raises(ValueError):  # lado inválido
        Trade(exchange="fake", symbol="BTC/USDT", trade_id="t",
              price=Decimal("1"), quantity=Decimal("1"), side="hold",  # type: ignore[arg-type]
              timestamp_ms=TS)


def test_orderbook_validation_and_properties():
    book = OrderBook(
        exchange="fake", symbol="BTC/USDT", timestamp_ms=TS,
        bids=((Decimal("100"), Decimal("1")), (Decimal("99"), Decimal("2"))),
        asks=((Decimal("101"), Decimal("1")), (Decimal("102"), Decimal("2"))),
    )
    assert book.best_bid == Decimal("100")
    assert book.best_ask == Decimal("101")
    assert book.spread == Decimal("1")
    assert book.mid_price == Decimal("100.5")
    with pytest.raises(ValueError):  # bids fora de ordem
        OrderBook(exchange="fake", symbol="BTC/USDT", timestamp_ms=TS,
                  bids=((Decimal("99"), Decimal("1")),
                        (Decimal("100"), Decimal("1"))),
                  asks=((Decimal("101"), Decimal("1")),))
    with pytest.raises(ValueError):  # asks fora de ordem
        OrderBook(exchange="fake", symbol="BTC/USDT", timestamp_ms=TS,
                  bids=((Decimal("100"), Decimal("1")),),
                  asks=((Decimal("102"), Decimal("1")),
                        (Decimal("101"), Decimal("1"))))
    empty = OrderBook(exchange="fake", symbol="BTC/USDT", timestamp_ms=TS,
                      bids=(), asks=())
    assert empty.best_bid is None and empty.spread is None


def test_market_instrument_order_fill_position_validation():
    market = Market(exchange="fake", symbol="BTC/USDT", base="BTC",
                    quote="USDT")
    with pytest.raises(ValueError):  # símbolo não normalizado
        Market(exchange="fake", symbol="BTCUSDT", base="BTC", quote="USDT")
    instrument = Instrument(market=market, instrument_id="BTCUSDT")
    assert instrument.symbol == "BTC/USDT"
    order = Order(order_id="o1", exchange="fake", symbol="BTC/USDT",
                  side="buy", order_type="limit", price=Decimal("100"),
                  quantity=Decimal("1"))
    assert order.status == "new"
    with pytest.raises(ValueError):  # limit sem preço
        Order(order_id="o2", exchange="fake", symbol="BTC/USDT",
              side="buy", order_type="limit", quantity=Decimal("1"))
    with pytest.raises(ValueError):  # filled > quantity
        Order(order_id="o3", exchange="fake", symbol="BTC/USDT",
              side="buy", order_type="market", quantity=Decimal("1"),
              filled_quantity=Decimal("2"))
    fill = Fill(fill_id="f1", order_id="o1", exchange="fake",
                symbol="BTC/USDT", price=Decimal("100"),
                quantity=Decimal("0.5"), timestamp_ms=TS)
    assert fill.fee == Decimal("0")
    position = Position(exchange="fake", symbol="BTC/USDT", side="long",
                        quantity=Decimal("0.5"), entry_price=Decimal("100"))
    assert position.side == "long"
    with pytest.raises(ValueError):  # flat com quantidade
        Position(exchange="fake", symbol="BTC/USDT", side="flat",
                 quantity=Decimal("1"), entry_price=Decimal("100"))


# ---------------------------------------------------------------------------
# Erros e envelope (CON-004)
# ---------------------------------------------------------------------------

def test_exchange_error_retryable_flags():
    assert ExchangeError(ErrorCode.RATE_LIMIT, "slow").retryable is True
    assert ExchangeError(ErrorCode.TIMEOUT, "t").retryable is True
    assert ExchangeError(ErrorCode.CONNECTION_LOST, "gone").retryable is True
    assert ExchangeError(ErrorCode.INVALID_SYMBOL, "bad").retryable is False
    assert ExchangeError(ErrorCode.BAD_RESPONSE, "bad").retryable is False
    # override explícito vence o padrão
    err = ExchangeError(ErrorCode.BAD_RESPONSE, "bad", retryable=True)
    assert err.retryable is True
    assert err.to_dict()["code"] == "BAD_RESPONSE"


def test_error_from_http_status():
    assert error_from_http_status(429, "slow").code == ErrorCode.RATE_LIMIT
    assert error_from_http_status(504, "gw").code == ErrorCode.TIMEOUT
    assert error_from_http_status(404, "nope").code == ErrorCode.INVALID_SYMBOL
    assert error_from_http_status(500, "boom").code == ErrorCode.BAD_RESPONSE
    assert error_from_http_status(418, "teapot").code == ErrorCode.UNKNOWN


def test_envelope_ok_and_error():
    env = ok_response({"price": "67000"}, exchange="fake", raw={"p": 1})
    assert env.ok is True and env.error is None
    assert env.data == {"price": "67000"}
    assert env.meta["exchange"] == "fake"
    assert env.meta["raw"] == {"p": 1}  # payload original preservado
    assert env.to_dict()["ok"] is True

    err = ExchangeError(ErrorCode.RATE_LIMIT, "slow down", exchange="fake")
    env2 = error_response(err)
    assert env2.ok is False and env2.data is None
    assert env2.error["code"] == "RATE_LIMIT"
    assert env2.error["retryable"] is True
    assert env2.meta["exchange"] == "fake"

    env3 = error_response("falha genérica", code="TIMEOUT")
    assert env3.error["code"] == "TIMEOUT"


def test_envelope_from_exception():
    env = envelope_from_exception(ValueError("boom"))
    assert env.ok is False
    assert env.error["code"] == "UNKNOWN"
    assert "ValueError" in env.error["message"]
    env2 = envelope_from_exception(
        ExchangeError(ErrorCode.TIMEOUT, "t", exchange="fake"))
    assert env2.error["code"] == "TIMEOUT"


# ---------------------------------------------------------------------------
# Binance implementada na Fase 4 (CEX-001) — sem rede, com fake CCXT
# ---------------------------------------------------------------------------

def test_binance_adapter_implemented_with_fake():
    """Binance (Fase 4) implementa o contrato sobre CCXT público."""
    from binance.adapter import BinanceAdapter
    from tests.connectors.fake_ccxt import FakeCCXTExchange

    adapter = BinanceAdapter(
        exchange=FakeCCXTExchange(), rate_per_sec=100.0, rate_burst=100
    )
    assert adapter.exchange_id == "binance"
    assert adapter.name == "Binance"
    assert adapter.supports_funding is True
    assert adapter.supports_open_interest is True
    # Sem credenciais na configuração pública do CCXT.
    assert not (
        set(adapter.public_config())
        & {"apiKey", "secret", "password", "uid", "privateKey"}
    )
    adapter.connect()
    assert adapter.health()["connected"] is True
    assert adapter.fetch_ticker("BTC/USDT").last == Decimal("67000")
    assert adapter.health()["latency_ms"]  # latência medida (CEX-006)
    assert adapter.health()["calls"] >= 1
    assert [m.symbol for m in adapter.fetch_markets()] == [
        "BTC/USDT", "ETH/USDT", "BTC/USDT:USDT",
    ]
    ticker = adapter.fetch_ticker("btcusdt")
    assert ticker.symbol == "BTC/USDT"
    assert ticker.last == Decimal("67000")
    assert ticker.raw["symbol"] == "BTC/USDT"  # payload original (CEX-005)
    assert adapter.fetch_trades("BTC/USDT")[0].trade_id == "t1"
    assert adapter.fetch_ohlcv("BTC/USDT", "1m")[0].close == Decimal("67050")
    book = adapter.fetch_order_book("BTC/USDT")
    assert book.best_bid == Decimal("67000")
    assert book.spread == Decimal("10")
    funding = adapter.fetch_funding_rate("BTC/USDT")
    assert funding.symbol == "BTC/USDT:USDT"  # spot -> perpétuo
    assert funding.rate == Decimal("0.0001")
    assert adapter.fetch_open_interest("BTC/USDT").value == Decimal("123456")
    # Wrappers legados delegam aos métodos canônicos.
    assert adapter.list_markets()[0]["symbol"] == "BTC/USDT"
    assert adapter.get_ticker("BTCUSDT")["last"] == "67000.0"
    assert adapter.get_trades("btc-usdt")[0]["trade_id"] == "t1"
    assert adapter.get_candles("BTC/USDT", "1m")[0]["close"] == "67050.0"
    assert adapter.get_orderbook("BTC/USDT")["bids"][0][0] == "67000.0"
    adapter.disconnect()
    assert adapter.health()["connected"] is False
