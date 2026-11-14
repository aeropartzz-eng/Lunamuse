"""Testes do conector OKX (Fase 4 — CEX-003, CEX-004…CEX-006, CEX-012).

Somente mocks/fakes: nenhuma rede real, nenhuma chave de API, nenhuma
ordem enviada. Cobre normalização, paginação de trades/candles,
tratamento de erros (RATE_LIMIT, TIMEOUT, INVALID_SYMBOL,
CONNECTION_LOST), funding/OI de swaps e as particularidades da OKX:
símbolo nativo ``BTC-USDT`` (convertido pelo CCXT), sem candles de
1s/8h e token bucket local mais restrito (5 req/s).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from errors import ErrorCode, ExchangeError
from okx.adapter import OkxAdapter
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

# Timeframes reais da OKX v5 via CCXT (sem 1s/5s/15s/30s nem 8h).
OKX_TIMEFRAMES = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "1w": 604800, "1M": 2592000,
}

_CREDENTIAL_KEYS = {"apiKey", "secret", "password", "uid", "privateKey"}


def make_adapter(**kwargs) -> OkxAdapter:
    fake = kwargs.pop("fake", None) or FakeCCXTExchange(
        timeframes=OKX_TIMEFRAMES
    )
    return OkxAdapter(
        exchange=fake, rate_per_sec=100.0, rate_burst=100, **kwargs
    )


def test_adapter_attributes_and_public_config():
    adapter = make_adapter()
    assert adapter.exchange_id == "okx"
    assert adapter.name == "OKX"
    assert adapter.ccxt_id == "okx"
    assert adapter.rate_per_sec == 5.0  # endpoint mais restrito: 10/2 s
    assert adapter.rate_burst == 10
    assert adapter.supports_funding is True
    assert adapter.supports_open_interest is True
    assert adapter.default_type == "spot"
    assert not _CREDENTIAL_KEYS & set(adapter.public_config())
    assert not hasattr(adapter, "create_order")


def test_connect_disconnect_health_latency():
    fake = FakeCCXTExchange(timeframes=OKX_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    adapter.connect()
    assert fake.loaded_markets is True
    assert adapter.health()["connected"] is True
    adapter.fetch_ticker("BTC/USDT")
    health = adapter.health()
    assert health["latency_ms"]["fetch_ticker"] >= 0
    assert health["calls"] >= 1
    adapter.disconnect()
    assert adapter.health()["connected"] is False


def test_fetch_markets_spot_and_swap():
    markets = make_adapter().fetch_markets()
    assert [m.symbol for m in markets] == [
        "BTC/USDT", "ETH/USDT", "BTC/USDT:USDT",
    ]
    assert [m.market_type for m in markets] == ["spot", "spot", "perp"]
    assert markets[0].tick_size == Decimal("0.01")
    assert markets[0].raw["symbol"] == "BTC/USDT"


def test_fetch_ticker_accepts_okx_native_form():
    """OKX nativo é BTC-USDT; o canônico continua BTC/USDT."""
    adapter = make_adapter()
    for raw_symbol in ("BTC/USDT", "BTCUSDT", "btc-usdt", "BTC-USDT"):
        ticker = adapter.fetch_ticker(raw_symbol)
        assert ticker.symbol == "BTC/USDT"
        assert ticker.last == Decimal("67000")
        assert ticker.timestamp_ms == TS
        assert ticker.raw["symbol"] == "BTC/USDT"


def test_fetch_trades_and_ohlcv_canonical():
    adapter = make_adapter()
    trades = adapter.fetch_trades("BTC-USDT")
    assert [t.trade_id for t in trades] == ["t1", "t2"]
    assert all(t.symbol == "BTC/USDT" for t in trades)
    candles = adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert len(candles) == 3
    assert candles[0].close == Decimal("67050")


def test_fetch_trades_pagination():
    fake = PagedFakeCCXTExchange(
        n_trades=2050, timeframes=OKX_TIMEFRAMES
    )
    adapter = make_adapter(fake=fake)
    trades = adapter.fetch_trades("BTC/USDT", limit=2050)
    assert len(trades) == 2050
    assert len({t.trade_id for t in trades}) == 2050
    assert trades[-1].trade_id == "t2049"
    assert fake.calls.count("fetch_trades") == 3  # 1000 + 1000 + 50


def test_fetch_ohlcv_pagination():
    fake = PagedFakeCCXTExchange(
        n_candles=1100, timeframes=OKX_TIMEFRAMES
    )
    adapter = make_adapter(fake=fake)
    candles = adapter.fetch_ohlcv("BTC/USDT", "1m", limit=1100)
    assert len(candles) == 1100
    assert candles[-1].open_time_ms == TS + 1099 * 60_000
    assert fake.calls.count("fetch_ohlcv") == 2
    assert adapter.health()["gaps_detected"] == 0


def test_fetch_ohlcv_gap_detection():
    fake = FakeCCXTExchange(
        timeframes=OKX_TIMEFRAMES, ohlcv_rows=gapped_ohlcv()
    )
    adapter = make_adapter(fake=fake)
    adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert adapter.health()["gaps_detected"] == 1


def test_fetch_ohlcv_rejects_invented_and_unsupported_timeframes():
    adapter = make_adapter()
    with pytest.raises(ValueError):
        adapter.fetch_ohlcv("BTC/USDT", "7m")
    # 1s e 8h são válidos na especificação, mas a OKX v5 não os serve.
    for tf in ("1s", "8h"):
        with pytest.raises(ExchangeError) as excinfo:
            adapter.fetch_ohlcv("BTC/USDT", tf)
        assert excinfo.value.code == ErrorCode.BAD_RESPONSE


def test_fetch_order_book_sorted_with_sequence():
    book = make_adapter().fetch_order_book("BTC/USDT")
    assert book.best_bid == Decimal("67000")
    assert book.best_ask == Decimal("67010")
    assert book.spread == Decimal("10")
    assert book.sequence == 12345


def test_funding_and_open_interest_swap():
    adapter = make_adapter()
    funding = adapter.fetch_funding_rate("BTC/USDT")
    assert funding.symbol == "BTC/USDT:USDT"
    assert funding.rate == Decimal("0.0001")
    assert funding.next_funding_ms == TS + 8 * 3_600_000
    oi = adapter.fetch_open_interest("BTC/USDT")
    assert oi.symbol == "BTC/USDT:USDT"
    assert oi.value == Decimal("123456")


def test_funding_not_offered_returns_clear_error():
    fake = FakeCCXTExchange(timeframes=OKX_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    fake.fail_with["fetch_funding_rate"] = NotSupported("no funding")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_funding_rate("BTC/USDT:USDT")
    assert excinfo.value.code == ErrorCode.BAD_RESPONSE
    assert excinfo.value.retryable is False


def test_error_translation():
    fake = FakeCCXTExchange(timeframes=OKX_TIMEFRAMES)
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
    fake.fail_with["fetch_ticker"] = BadSymbol("XXX/YYY")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("XXX/YYY")
    assert excinfo.value.code == ErrorCode.INVALID_SYMBOL
    assert excinfo.value.retryable is False
    fake.fail_with["fetch_ticker"] = NetworkError("down")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.CONNECTION_LOST
    assert adapter.health()["errors"] == 4


def test_legacy_wrappers_delegate():
    adapter = make_adapter()
    assert adapter.list_markets()[0]["symbol"] == "BTC/USDT"
    assert adapter.get_ticker("BTCUSDT")["last"] == "67000.0"
    assert adapter.get_trades("btc-usdt")[0]["trade_id"] == "t1"
    assert adapter.get_candles("BTC/USDT", "1m")[0]["close"] == "67050.0"
    assert adapter.get_orderbook("BTC/USDT")["bids"][0][0] == "67000.0"
