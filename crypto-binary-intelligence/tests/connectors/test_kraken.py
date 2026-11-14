"""Testes do conector Kraken (Fase 5 — CEX-008, CEX-012).

Somente mocks/fakes: nenhuma rede real, nenhuma chave de API, nenhuma
ordem enviada. Foco extra nos alias de símbolos (XBT→BTC, XDG→DOGE).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from errors import ErrorCode, ExchangeError
from kraken.adapter import KrakenAdapter
from tests.connectors.fake_ccxt import (
    TS,
    BadSymbol,
    FakeCCXTExchange,
    RateLimitExceeded,
    default_markets,
    gapped_ohlcv,
)

# Timeframes reais do Kraken via CCXT.
KRAKEN_TIMEFRAMES = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "4h": 240, "1d": 1440, "1w": 10080, "2w": 21600,
}

_CREDENTIAL_KEYS = {"apiKey", "secret", "password", "uid", "privateKey"}


def kraken_markets() -> list[dict]:
    """Mercados com os códigos nativos do Kraken (XBT, XDG)."""
    return [
        {
            "symbol": "XBT/USD", "base": "XBT", "quote": "USD",
            "type": "spot", "active": True,
            "precision": {"price": 1, "amount": 8},
            "limits": {"amount": {"min": 0.0001}},
        },
        {
            "symbol": "XDG/USD", "base": "XDG", "quote": "USD",
            "type": "spot", "active": True,
            "precision": {"price": 5, "amount": 8},
            "limits": {"amount": {"min": 1.0}},
        },
    ]


def make_adapter(**kwargs) -> KrakenAdapter:
    fake = kwargs.pop("fake", None) or FakeCCXTExchange(
        timeframes=KRAKEN_TIMEFRAMES, markets=kraken_markets()
    )
    return KrakenAdapter(
        exchange=fake, rate_per_sec=100.0, rate_burst=100, **kwargs
    )


def test_adapter_attributes_and_public_config():
    adapter = make_adapter()
    assert adapter.exchange_id == "kraken"
    assert adapter.name == "Kraken"
    assert adapter.ccxt_id == "kraken"
    assert adapter.rate_per_sec == 1.0  # orientação oficial: ~1 req/s
    assert adapter.rate_burst == 3
    assert adapter.supports_funding is False
    assert adapter.supports_open_interest is False
    assert not _CREDENTIAL_KEYS & set(adapter.public_config())
    assert not hasattr(adapter, "create_order")


def test_connect_disconnect_health():
    fake = FakeCCXTExchange(
        timeframes=KRAKEN_TIMEFRAMES, markets=kraken_markets()
    )
    adapter = make_adapter(fake=fake)
    adapter.connect()
    assert fake.loaded_markets is True
    assert adapter.health()["connected"] is True
    adapter.disconnect()
    assert adapter.health()["connected"] is False


def test_fetch_markets_applies_xbt_xdg_alias():
    markets = make_adapter().fetch_markets()
    assert [m.symbol for m in markets] == ["BTC/USD", "DOGE/USD"]
    assert [m.base for m in markets] == ["BTC", "DOGE"]
    assert markets[0].raw["base"] == "XBT"  # payload original (CEX-005)
    assert markets[0].tick_size == Decimal("0.1")


def test_fetch_ticker_accepts_kraken_alias_forms():
    adapter = make_adapter()
    for raw_symbol in ("XBT/USD", "XBTUSD", "xbt-usd"):
        ticker = adapter.fetch_ticker(raw_symbol)
        assert ticker.symbol == "BTC/USD"
        assert ticker.last == Decimal("67000.0")
        assert ticker.timestamp_ms == TS
    assert adapter.fetch_ticker("BTC/USD").symbol == "BTC/USD"


def test_fetch_trades_and_ohlcv_use_canonical_symbol():
    adapter = make_adapter()
    trades = adapter.fetch_trades("XBT/USD")
    assert all(t.symbol == "BTC/USD" for t in trades)
    assert trades[0].side == "buy"
    candles = adapter.fetch_ohlcv("XBT/USD", "1m")
    assert candles[0].symbol == "BTC/USD"
    assert candles[0].close == Decimal("67050.0")


def test_fetch_ohlcv_gap_detection():
    fake = FakeCCXTExchange(
        timeframes=KRAKEN_TIMEFRAMES, markets=kraken_markets(),
        ohlcv_rows=gapped_ohlcv(),
    )
    adapter = make_adapter(fake=fake)
    adapter.fetch_ohlcv("BTC/USD", "1m")
    assert adapter.health()["gaps_detected"] == 1


def test_fetch_ohlcv_rejects_unsupported_timeframe():
    adapter = make_adapter()
    with pytest.raises(ValueError):
        adapter.fetch_ohlcv("BTC/USD", "7m")
    with pytest.raises(ExchangeError) as excinfo:
        # 3m é válido na especificação, mas o Kraken não o serve.
        adapter.fetch_ohlcv("BTC/USD", "3m")
    assert excinfo.value.code == ErrorCode.BAD_RESPONSE


def test_fetch_order_book_sorted():
    book = make_adapter().fetch_order_book("XBT/USD")
    assert book.symbol == "BTC/USD"
    assert book.best_bid == Decimal("67000.0")
    assert book.best_ask == Decimal("67010")
    assert book.spread == Decimal("10")


def test_funding_and_open_interest_not_supported():
    adapter = make_adapter()
    for method in (adapter.fetch_funding_rate, adapter.fetch_open_interest):
        with pytest.raises(ExchangeError) as excinfo:
            method("BTC/USD")
        assert excinfo.value.code == ErrorCode.BAD_RESPONSE
        assert excinfo.value.retryable is False
        assert "não disponível" in excinfo.value.message


def test_error_translation():
    fake = FakeCCXTExchange(
        timeframes=KRAKEN_TIMEFRAMES, markets=kraken_markets()
    )
    adapter = make_adapter(fake=fake)
    fake.fail_with["fetch_ticker"] = RateLimitExceeded("slow")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USD")
    assert excinfo.value.code == ErrorCode.RATE_LIMIT
    assert excinfo.value.retryable is True
    fake.fail_with["fetch_ticker"] = BadSymbol("XXX/YYY")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("XXX/YYY")
    assert excinfo.value.code == ErrorCode.INVALID_SYMBOL


def test_legacy_wrappers_delegate_with_alias():
    adapter = make_adapter()
    assert adapter.list_markets()[0]["symbol"] == "BTC/USD"
    assert adapter.get_ticker("XBTUSD")["last"] == "67000.0"
    assert adapter.get_orderbook("XBT/USD")["bids"][0][0] == "67000.0"


def test_default_markets_helper_still_importable():
    assert default_markets()[0]["symbol"] == "BTC/USDT"
