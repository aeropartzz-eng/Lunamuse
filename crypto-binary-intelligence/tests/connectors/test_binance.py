"""Testes do conector Binance (Fase 4 — CEX-001, CEX-004…CEX-006, CEX-012).

Somente mocks/fakes: nenhuma rede real, nenhuma chave de API, nenhuma
ordem enviada. Cobre normalização, paginação de trades/candles,
tratamento de erros (RATE_LIMIT, TIMEOUT, INVALID_SYMBOL,
CONNECTION_LOST), funding/OI (inclusive o caso "não oferecido") e
latência/gaps expostos em health().
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from binance.adapter import BinanceAdapter
from errors import ErrorCode, ExchangeError
from tests.connectors.fake_ccxt import (
    TS,
    BadSymbol,
    FakeCCXTExchange,
    NetworkError,
    NotSupported,
    RateLimitExceeded,
    RequestTimeout,
    gapped_ohlcv,
)
from tests.connectors.paged_fake import PagedFakeCCXTExchange

# Timeframes reais da Binance via CCXT (spot + futuros).
BINANCE_TIMEFRAMES = {
    "1s": 1, "5s": 5, "15s": 15, "30s": 30,
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800,
    "12h": 43200, "1d": 86400, "1w": 604800, "1M": 2592000,
}

_CREDENTIAL_KEYS = {"apiKey", "secret", "password", "uid", "privateKey"}


def make_adapter(**kwargs) -> BinanceAdapter:
    fake = kwargs.pop("fake", None) or FakeCCXTExchange(
        timeframes=BINANCE_TIMEFRAMES
    )
    return BinanceAdapter(
        exchange=fake, rate_per_sec=100.0, rate_burst=100, **kwargs
    )


def test_adapter_attributes_and_public_config():
    adapter = make_adapter()
    assert adapter.exchange_id == "binance"
    assert adapter.name == "Binance"
    assert adapter.ccxt_id == "binance"
    assert adapter.rate_per_sec == 10.0  # conservador vs 6.000 peso/min
    assert adapter.rate_burst == 20
    assert adapter.supports_funding is True
    assert adapter.supports_open_interest is True
    assert adapter.default_type == "spot"
    assert not _CREDENTIAL_KEYS & set(adapter.public_config())
    assert not hasattr(adapter, "create_order")


def test_connect_disconnect_health_latency():
    fake = FakeCCXTExchange(timeframes=BINANCE_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    assert adapter.health()["connected"] is False
    adapter.connect()
    assert fake.loaded_markets is True
    assert adapter.health()["connected"] is True
    adapter.fetch_ticker("BTC/USDT")
    health = adapter.health()
    assert health["latency_ms"]["fetch_ticker"] >= 0
    assert health["latency_avg_ms"]["fetch_ticker"] >= 0
    assert health["calls"] >= 1
    adapter.disconnect()
    assert adapter.health()["connected"] is False
    assert fake.closed is True


def test_fetch_markets_spot_and_perp():
    markets = make_adapter().fetch_markets()
    assert [m.symbol for m in markets] == [
        "BTC/USDT", "ETH/USDT", "BTC/USDT:USDT",
    ]
    assert [m.market_type for m in markets] == ["spot", "spot", "perp"]
    assert markets[0].tick_size == Decimal("0.01")
    assert markets[0].min_qty == Decimal("0.0001")
    assert markets[0].raw["symbol"] == "BTC/USDT"  # payload original
    assert markets[2].raw["type"] == "swap"


def test_fetch_ticker_symbol_variants_and_raw():
    adapter = make_adapter()
    for raw_symbol in ("BTC/USDT", "BTCUSDT", "btc-usdt", "BTC_USDT"):
        ticker = adapter.fetch_ticker(raw_symbol)
        assert ticker.symbol == "BTC/USDT"
        assert ticker.last == Decimal("67000")
        assert ticker.timestamp_ms == TS
        assert ticker.bid == Decimal("66990")
        assert ticker.ask == Decimal("67010")
        assert ticker.raw["symbol"] == "BTC/USDT"
    assert adapter.fetch_ticker("BTC/USDT:USDT").symbol == "BTC/USDT:USDT"


def test_fetch_trades_and_ohlcv_canonical():
    adapter = make_adapter()
    trades = adapter.fetch_trades("btcusdt")
    assert [t.trade_id for t in trades] == ["t1", "t2"]
    assert [t.side for t in trades] == ["buy", "sell"]
    assert all(t.symbol == "BTC/USDT" for t in trades)
    assert trades[0].raw["id"] == "t1"
    candles = adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert len(candles) == 3
    assert candles[0].close == Decimal("67050")
    assert candles[0].close_time_ms - candles[0].open_time_ms == 60_000


def test_fetch_trades_pagination_and_since():
    fake = PagedFakeCCXTExchange(
        n_trades=2500, timeframes=BINANCE_TIMEFRAMES
    )
    adapter = make_adapter(fake=fake)
    trades = adapter.fetch_trades("BTC/USDT", limit=2500)
    assert len(trades) == 2500
    assert len({t.trade_id for t in trades}) == 2500  # sem duplicata
    assert trades[0].trade_id == "t0"
    assert trades[-1].trade_id == "t2499"
    assert trades[-1].timestamp_ms == TS + 2499 * 1000
    # Chamadas paginadas de 1000: 3 chamadas ao fake.
    assert fake.calls.count("fetch_trades") == 3
    # since_ms filtra a partir de um instante.
    recent = adapter.fetch_trades("BTC/USDT", since_ms=TS + 2000 * 1000)
    assert len(recent) == 100  # default limit=100
    assert recent[0].trade_id == "t2000"


def test_fetch_ohlcv_pagination():
    fake = PagedFakeCCXTExchange(
        n_candles=1500, timeframes=BINANCE_TIMEFRAMES
    )
    adapter = make_adapter(fake=fake)
    candles = adapter.fetch_ohlcv("BTC/USDT", "1m", limit=1500)
    assert len(candles) == 1500
    assert candles[0].open_time_ms == TS
    assert candles[-1].open_time_ms == TS + 1499 * 60_000
    assert fake.calls.count("fetch_ohlcv") == 2  # 1000 + 500
    assert adapter.health()["gaps_detected"] == 0


def test_fetch_ohlcv_gap_detection():
    fake = FakeCCXTExchange(
        timeframes=BINANCE_TIMEFRAMES, ohlcv_rows=gapped_ohlcv()
    )
    adapter = make_adapter(fake=fake)
    adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert adapter.health()["gaps_detected"] == 1


def test_fetch_ohlcv_rejects_invented_timeframe():
    adapter = make_adapter()
    with pytest.raises(ValueError):
        adapter.fetch_ohlcv("BTC/USDT", "7m")


def test_fetch_order_book_sorted_with_sequence():
    book = make_adapter().fetch_order_book("BTC/USDT")
    assert book.symbol == "BTC/USDT"
    assert book.best_bid == Decimal("67000")
    assert book.best_ask == Decimal("67010")
    assert book.spread == Decimal("10")
    assert book.sequence == 12345  # nonce da exchange (CEX-006)
    assert book.raw["nonce"] == 12345


def test_funding_and_open_interest_perp():
    adapter = make_adapter()
    funding = adapter.fetch_funding_rate("BTC/USDT")
    assert funding.symbol == "BTC/USDT:USDT"  # spot -> perpétuo
    assert funding.rate == Decimal("0.0001")
    assert funding.timestamp_ms == TS
    assert funding.next_funding_ms == TS + 8 * 3_600_000
    funding2 = adapter.fetch_funding_rate("BTC/USDT:USDT")
    assert funding2.symbol == "BTC/USDT:USDT"
    oi = adapter.fetch_open_interest("BTC/USDT")
    assert oi.symbol == "BTC/USDT:USDT"
    assert oi.value == Decimal("123456")
    assert oi.timestamp_ms == TS


def test_funding_not_offered_returns_clear_error():
    """Exchange sem funding: erro claro, dado nunca inventado."""
    fake = FakeCCXTExchange(timeframes=BINANCE_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    fake.fail_with["fetch_funding_rate"] = NotSupported("no funding")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_funding_rate("BTC/USDT:USDT")
    assert excinfo.value.code == ErrorCode.BAD_RESPONSE
    assert excinfo.value.retryable is False
    fake.fail_with["fetch_open_interest"] = NotSupported("no OI")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_open_interest("BTC/USDT:USDT")
    assert excinfo.value.code == ErrorCode.BAD_RESPONSE


def test_error_translation():
    fake = FakeCCXTExchange(timeframes=BINANCE_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    fake.fail_with["fetch_ticker"] = RateLimitExceeded("slow")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.RATE_LIMIT
    assert excinfo.value.retryable is True
    fake.fail_with["fetch_ticker"] = RequestTimeout("slow")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.TIMEOUT
    assert excinfo.value.retryable is True
    fake.fail_with["fetch_ticker"] = BadSymbol("XXX/YYY")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("XXX/YYY")
    assert excinfo.value.code == ErrorCode.INVALID_SYMBOL
    assert excinfo.value.retryable is False
    fake.fail_with["fetch_ticker"] = NetworkError("down")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.CONNECTION_LOST
    assert excinfo.value.retryable is True
    # Erro conta em health().
    assert adapter.health()["errors"] == 4


def test_local_rate_limiter_blocks():
    """Token bucket local (CEX-012): rajada 1 -> 2ª chamada dá RATE_LIMIT."""
    fake = FakeCCXTExchange(timeframes=BINANCE_TIMEFRAMES)
    adapter = BinanceAdapter(
        exchange=fake, rate_per_sec=0.001, rate_burst=1
    )
    adapter.fetch_ticker("BTC/USDT")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.RATE_LIMIT


def test_legacy_wrappers_delegate():
    adapter = make_adapter()
    assert adapter.list_markets()[0]["symbol"] == "BTC/USDT"
    assert adapter.get_ticker("BTCUSDT")["last"] == "67000.0"
    assert adapter.get_trades("btc-usdt")[0]["trade_id"] == "t1"
    assert adapter.get_candles("BTC/USDT", "1m")[0]["close"] == "67050.0"
    assert adapter.get_orderbook("BTC/USDT")["bids"][0][0] == "67000.0"
