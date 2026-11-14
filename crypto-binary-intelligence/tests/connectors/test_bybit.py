"""Testes do conector Bybit (Fase 4 — CEX-002, CEX-004…CEX-006, CEX-012).

Somente mocks/fakes: nenhuma rede real, nenhuma chave de API, nenhuma
ordem enviada. Cobre normalização, paginação de trades/candles,
tratamento de erros (RATE_LIMIT, TIMEOUT, INVALID_SYMBOL,
CONNECTION_LOST), funding/OI de contratos e as particularidades da
Bybit: sem candles de 1s/8h e funding rate "emulado" pelo CCXT.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bybit.adapter import BybitAdapter
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

# Timeframes reais da Bybit v5 via CCXT (sem 1s/5s/15s/30s nem 8h).
BYBIT_TIMEFRAMES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720,
    "1d": "D", "1w": "W", "1M": "M",
}

_CREDENTIAL_KEYS = {"apiKey", "secret", "password", "uid", "privateKey"}


def make_adapter(**kwargs) -> BybitAdapter:
    fake = kwargs.pop("fake", None) or FakeCCXTExchange(
        timeframes=BYBIT_TIMEFRAMES
    )
    return BybitAdapter(
        exchange=fake, rate_per_sec=100.0, rate_burst=100, **kwargs
    )


def test_adapter_attributes_and_public_config():
    adapter = make_adapter()
    assert adapter.exchange_id == "bybit"
    assert adapter.name == "Bybit"
    assert adapter.ccxt_id == "bybit"
    assert adapter.rate_per_sec == 10.0  # conservador vs 600 req/5 s (IP)
    assert adapter.rate_burst == 20
    assert adapter.supports_funding is True
    assert adapter.supports_open_interest is True
    assert adapter.default_type == "spot"
    assert not _CREDENTIAL_KEYS & set(adapter.public_config())
    assert not hasattr(adapter, "create_order")


def test_connect_disconnect_health_latency():
    fake = FakeCCXTExchange(timeframes=BYBIT_TIMEFRAMES)
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


def test_fetch_markets_spot_and_perp():
    markets = make_adapter().fetch_markets()
    assert [m.symbol for m in markets] == [
        "BTC/USDT", "ETH/USDT", "BTC/USDT:USDT",
    ]
    assert [m.market_type for m in markets] == ["spot", "spot", "perp"]
    assert markets[2].raw["type"] == "swap"


def test_fetch_ticker_symbol_variants_and_raw():
    adapter = make_adapter()
    for raw_symbol in ("BTC/USDT", "BTCUSDT", "btc-usdt"):
        ticker = adapter.fetch_ticker(raw_symbol)
        assert ticker.symbol == "BTC/USDT"
        assert ticker.last == Decimal("67000")
        assert ticker.timestamp_ms == TS
        assert ticker.raw["symbol"] == "BTC/USDT"


def test_fetch_trades_and_ohlcv_canonical():
    adapter = make_adapter()
    trades = adapter.fetch_trades("BTCUSDT")
    assert [t.trade_id for t in trades] == ["t1", "t2"]
    assert all(t.symbol == "BTC/USDT" for t in trades)
    candles = adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert len(candles) == 3
    assert candles[0].close == Decimal("67050")


def test_fetch_trades_pagination():
    fake = PagedFakeCCXTExchange(
        n_trades=2100, timeframes=BYBIT_TIMEFRAMES
    )
    adapter = make_adapter(fake=fake)
    trades = adapter.fetch_trades("BTC/USDT", limit=2100)
    assert len(trades) == 2100
    assert len({t.trade_id for t in trades}) == 2100
    assert trades[-1].trade_id == "t2099"
    assert fake.calls.count("fetch_trades") == 3  # 1000 + 1000 + 100


def test_fetch_ohlcv_pagination():
    fake = PagedFakeCCXTExchange(
        n_candles=1200, timeframes=BYBIT_TIMEFRAMES
    )
    adapter = make_adapter(fake=fake)
    candles = adapter.fetch_ohlcv("BTC/USDT", "1m", limit=1200)
    assert len(candles) == 1200
    assert candles[-1].open_time_ms == TS + 1199 * 60_000
    assert fake.calls.count("fetch_ohlcv") == 2
    assert adapter.health()["gaps_detected"] == 0


def test_fetch_ohlcv_gap_detection():
    fake = FakeCCXTExchange(
        timeframes=BYBIT_TIMEFRAMES, ohlcv_rows=gapped_ohlcv()
    )
    adapter = make_adapter(fake=fake)
    adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert adapter.health()["gaps_detected"] == 1


def test_fetch_ohlcv_rejects_invented_and_unsupported_timeframes():
    adapter = make_adapter()
    with pytest.raises(ValueError):
        adapter.fetch_ohlcv("BTC/USDT", "7m")
    # 1s e 8h são válidos na especificação, mas a Bybit v5 não os serve.
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


def test_funding_and_open_interest_perp():
    adapter = make_adapter()
    funding = adapter.fetch_funding_rate("BTC/USDT")
    assert funding.symbol == "BTC/USDT:USDT"
    assert funding.rate == Decimal("0.0001")
    assert funding.next_funding_ms == TS + 8 * 3_600_000
    oi = adapter.fetch_open_interest("BTC/USDT:USDT")
    assert oi.symbol == "BTC/USDT:USDT"
    assert oi.value == Decimal("123456")


def test_funding_not_offered_returns_clear_error():
    fake = FakeCCXTExchange(timeframes=BYBIT_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    fake.fail_with["fetch_funding_rate"] = NotSupported("no funding")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_funding_rate("BTC/USDT:USDT")
    assert excinfo.value.code == ErrorCode.BAD_RESPONSE
    assert excinfo.value.retryable is False


def test_error_translation():
    fake = FakeCCXTExchange(timeframes=BYBIT_TIMEFRAMES)
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
