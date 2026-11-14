"""Testes do conector Coinbase Advanced (Fase 5 — CEX-007, CEX-012).

Somente mocks/fakes: nenhuma rede real, nenhuma chave de API, nenhuma
ordem enviada. O exchange CCXT é substituído por
``tests.connectors.fake_ccxt.FakeCCXTExchange``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from coinbase.adapter import CoinbaseAdapter
from errors import ErrorCode, ExchangeError
from tests.connectors.fake_ccxt import (
    TS,
    BadSymbol,
    NetworkError,
    RateLimitExceeded,
    RequestTimeout,
    FakeCCXTExchange,
    gapped_ohlcv,
)

# Timeframes reais do Coinbase Advanced via CCXT (sem 3m/4h/8h/12h/1w).
COINBASE_TIMEFRAMES = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "6h": 21600, "1d": 86400,
}

_CREDENTIAL_KEYS = {"apiKey", "secret", "password", "uid", "privateKey"}


def make_adapter(**kwargs) -> CoinbaseAdapter:
    """Adapter com fake e rate limit local folgado (só p/ testes)."""
    fake = kwargs.pop("fake", None) or FakeCCXTExchange(
        timeframes=COINBASE_TIMEFRAMES
    )
    return CoinbaseAdapter(
        exchange=fake, rate_per_sec=100.0, rate_burst=100, **kwargs
    )


def test_adapter_attributes_and_public_config():
    adapter = make_adapter()
    assert adapter.exchange_id == "coinbase"
    assert adapter.name == "Coinbase Advanced"
    assert adapter.ccxt_id == "coinbase"  # Advanced Trade, não o comum
    assert adapter.rate_per_sec == 10.0
    assert adapter.rate_burst == 15
    assert adapter.supports_funding is False
    assert adapter.supports_open_interest is False
    config = adapter.public_config()
    assert config["enableRateLimit"] is True
    assert not _CREDENTIAL_KEYS & set(config)
    assert not hasattr(adapter, "create_order")  # sem envio de ordens


def test_connect_disconnect_health_and_latency():
    fake = FakeCCXTExchange(timeframes=COINBASE_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    assert adapter.health()["connected"] is False
    adapter.connect()
    assert fake.loaded_markets is True
    assert adapter.health()["connected"] is True
    adapter.fetch_ticker("BTC/USDT")
    health = adapter.health()
    assert health["calls"] >= 1
    assert "fetch_ticker" in health["latency_ms"]
    assert health["latency_ms"]["fetch_ticker"] >= 0
    assert health["errors"] == 0
    adapter.disconnect()
    assert adapter.health()["connected"] is False
    assert fake.closed is True


def test_fetch_markets_normalized_with_raw():
    markets = make_adapter().fetch_markets()
    assert [m.symbol for m in markets] == [
        "BTC/USDT", "ETH/USDT", "BTC/USDT:USDT",
    ]
    assert [m.market_type for m in markets] == ["spot", "spot", "perp"]
    btc = markets[0]
    assert btc.exchange == "coinbase"
    assert btc.tick_size == Decimal("0.01")
    assert btc.min_qty == Decimal("0.0001")
    assert btc.raw["symbol"] == "BTC/USDT"  # payload original (CEX-005)


def test_fetch_ticker_normalizes_symbol():
    ticker = make_adapter().fetch_ticker("btcusdt")
    assert ticker.symbol == "BTC/USDT"
    assert ticker.last == Decimal("67000.0")
    assert ticker.bid == Decimal("66990")
    assert ticker.ask == Decimal("67010")
    assert ticker.timestamp_ms == TS
    assert ticker.volume_24h == Decimal("1234567.89")
    assert ticker.change_24h_pct == Decimal("1.5")
    assert ticker.raw["last"] == 67000.0


def test_fetch_trades_normalizes_sides():
    trades = make_adapter().fetch_trades("BTC/USDT")
    assert [(t.trade_id, t.side) for t in trades] == [
        ("t1", "buy"), ("t2", "sell"),
    ]
    assert trades[0].price == Decimal("67000.0")
    assert trades[0].quantity == Decimal("0.01")
    assert trades[0].timestamp_ms == TS
    assert trades[0].raw["id"] == "t1"


def test_fetch_ohlcv_and_gap_detection():
    adapter = make_adapter()
    candles = adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert len(candles) == 3
    assert candles[0].close == Decimal("67050.0")
    assert candles[0].close_time_ms == candles[0].open_time_ms + 60_000
    assert adapter.health()["gaps_detected"] == 0

    fake = FakeCCXTExchange(
        timeframes=COINBASE_TIMEFRAMES, ohlcv_rows=gapped_ohlcv()
    )
    adapter = make_adapter(fake=fake)
    adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert adapter.health()["gaps_detected"] == 1  # falta TS+120000


def test_fetch_ohlcv_rejects_invented_and_unsupported_timeframe():
    adapter = make_adapter()
    with pytest.raises(ValueError):  # granularidade inventada (§3)
        adapter.fetch_ohlcv("BTC/USDT", "7m")
    with pytest.raises(ExchangeError) as excinfo:
        # 3m é válido na especificação, mas o Coinbase não o serve.
        adapter.fetch_ohlcv("BTC/USDT", "3m")
    assert excinfo.value.code == ErrorCode.BAD_RESPONSE
    assert "3m" in excinfo.value.message


def test_fetch_order_book_sorted_with_spread():
    book = make_adapter().fetch_order_book("BTC/USDT")
    assert book.best_bid == Decimal("67000.0")
    assert book.best_ask == Decimal("67010")
    assert book.spread == Decimal("10")
    assert book.sequence == 12345
    assert book.timestamp_ms == TS


def test_funding_and_open_interest_not_supported():
    adapter = make_adapter()
    for method in (adapter.fetch_funding_rate, adapter.fetch_open_interest):
        with pytest.raises(ExchangeError) as excinfo:
            method("BTC/USDT")
        assert excinfo.value.code == ErrorCode.BAD_RESPONSE
        assert excinfo.value.retryable is False
        assert "não disponível" in excinfo.value.message


def test_error_translation_from_ccxt_names():
    fake = FakeCCXTExchange(timeframes=COINBASE_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    fake.fail_with["fetch_ticker"] = RateLimitExceeded("slow down")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.RATE_LIMIT
    assert excinfo.value.retryable is True

    fake.fail_with["fetch_ticker"] = RequestTimeout("timed out")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.TIMEOUT

    fake.fail_with["fetch_ticker"] = NetworkError("conn reset")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.CONNECTION_LOST

    fake.fail_with["fetch_ticker"] = BadSymbol("BTC/USDT")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.INVALID_SYMBOL
    assert excinfo.value.retryable is False
    assert adapter.health()["errors"] == 4


def test_error_translation_from_http_status():
    fake = FakeCCXTExchange(timeframes=COINBASE_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    err = Exception("too many requests")
    err.httpStatusCode = 429  # type: ignore[attr-defined]
    fake.fail_with["fetch_ticker"] = err
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.RATE_LIMIT


def test_legacy_wrappers_delegate():
    adapter = make_adapter()
    assert adapter.list_markets()[0]["symbol"] == "BTC/USDT"
    assert adapter.get_ticker("BTCUSDT")["last"] == "67000.0"
    assert adapter.get_trades("BTC/USDT")[0]["trade_id"] == "t1"
    assert adapter.get_candles("BTC/USDT", "1m")[0]["close"] == "67050.0"
    assert adapter.get_orderbook("BTC/USDT")["bids"][0][0] == "67000.0"
