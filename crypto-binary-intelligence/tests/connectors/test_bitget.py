"""Testes do conector Bitget (Fase 5 — CEX-009, CEX-012).

Somente mocks/fakes: nenhuma rede real, nenhuma chave de API, nenhuma
ordem enviada. Foco extra em funding rate e open interest de
perpétuos USDT (símbolo swap ``BTC/USDT:USDT``).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from bitget.adapter import BitgetAdapter
from errors import ErrorCode, ExchangeError
from tests.connectors.fake_ccxt import (
    TS,
    NotSupported,
    RateLimitExceeded,
    FakeCCXTExchange,
    gapped_ohlcv,
)

BITGET_TIMEFRAMES = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "3d": 259200, "1w": 604800, "1M": 2592000,
}

_CREDENTIAL_KEYS = {"apiKey", "secret", "password", "uid", "privateKey"}


def make_adapter(**kwargs) -> BitgetAdapter:
    fake = kwargs.pop("fake", None) or FakeCCXTExchange(
        timeframes=BITGET_TIMEFRAMES
    )
    return BitgetAdapter(
        exchange=fake, rate_per_sec=100.0, rate_burst=100, **kwargs
    )


def test_adapter_attributes_and_public_config():
    adapter = make_adapter()
    assert adapter.exchange_id == "bitget"
    assert adapter.name == "Bitget"
    assert adapter.ccxt_id == "bitget"
    assert adapter.rate_per_sec == 20.0  # market data 20 req/s por IP
    assert adapter.rate_burst == 20
    assert adapter.supports_funding is True
    assert adapter.supports_open_interest is True
    assert not _CREDENTIAL_KEYS & set(adapter.public_config())
    assert not hasattr(adapter, "create_order")


def test_connect_disconnect_health_and_latency():
    fake = FakeCCXTExchange(timeframes=BITGET_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    adapter.connect()
    assert fake.loaded_markets is True
    adapter.fetch_funding_rate("BTC/USDT")
    health = adapter.health()
    assert health["connected"] is True
    assert health["calls"] >= 1
    assert "fetch_funding_rate" in health["latency_ms"]
    adapter.disconnect()
    assert adapter.health()["connected"] is False


def test_fetch_markets_includes_swap_as_perp():
    markets = make_adapter().fetch_markets()
    assert [m.symbol for m in markets] == [
        "BTC/USDT", "ETH/USDT", "BTC/USDT:USDT",
    ]
    assert [m.market_type for m in markets] == ["spot", "spot", "perp"]


def test_fetch_ticker_trades_orderbook():
    adapter = make_adapter()
    ticker = adapter.fetch_ticker("BTC/USDT")
    assert ticker.symbol == "BTC/USDT"
    assert ticker.last == Decimal("67000.0")
    assert ticker.timestamp_ms == TS
    trades = adapter.fetch_trades("BTC/USDT")
    assert [t.side for t in trades] == ["buy", "sell"]
    book = adapter.fetch_order_book("BTC/USDT")
    assert book.best_bid == Decimal("67000.0")
    assert book.spread == Decimal("10")


def test_fetch_ohlcv_and_gap_detection():
    adapter = make_adapter()
    candles = adapter.fetch_ohlcv("BTC/USDT", "3m")  # Bitget serve 3m
    assert len(candles) == 3
    assert candles[0].close_time_ms == candles[0].open_time_ms + 180_000
    fake = FakeCCXTExchange(
        timeframes=BITGET_TIMEFRAMES, ohlcv_rows=gapped_ohlcv()
    )
    adapter = make_adapter(fake=fake)
    adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert adapter.health()["gaps_detected"] == 1


def test_fetch_funding_rate_uses_swap_symbol():
    funding = make_adapter().fetch_funding_rate("BTC/USDT")
    assert funding.symbol == "BTC/USDT:USDT"
    assert funding.rate == Decimal("0.0001")
    assert funding.timestamp_ms == TS
    assert funding.next_funding_ms == TS + 8 * 3_600_000
    assert funding.raw["fundingRate"] == 0.0001


def test_fetch_funding_rate_accepts_swap_symbol_directly():
    funding = make_adapter().fetch_funding_rate("BTC/USDT:USDT")
    assert funding.symbol == "BTC/USDT:USDT"
    assert funding.rate == Decimal("0.0001")


def test_fetch_open_interest():
    oi = make_adapter().fetch_open_interest("BTC/USDT")
    assert oi.symbol == "BTC/USDT:USDT"
    assert oi.value == Decimal("123456")
    assert oi.timestamp_ms == TS
    assert oi.raw["openInterestAmount"] == 123456.0


def test_funding_unsupported_from_exchange_becomes_clear_error():
    fake = FakeCCXTExchange(timeframes=BITGET_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    fake.fail_with["fetch_funding_rate"] = NotSupported("no funding")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_funding_rate("BTC/USDT")
    assert excinfo.value.code == ErrorCode.BAD_RESPONSE
    fake.fail_with["fetch_open_interest"] = NotSupported("no OI")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_open_interest("BTC/USDT")
    assert excinfo.value.code == ErrorCode.BAD_RESPONSE


def test_error_translation_rate_limit():
    fake = FakeCCXTExchange(timeframes=BITGET_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    fake.fail_with["fetch_ticker"] = RateLimitExceeded("slow")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.RATE_LIMIT
    assert excinfo.value.retryable is True


def test_legacy_wrappers_delegate():
    adapter = make_adapter()
    assert adapter.get_ticker("BTCUSDT")["last"] == "67000.0"
    assert adapter.get_candles("BTC/USDT", "1m")[0]["close"] == "67050.0"
