"""Testes do conector Gate.io (Fase 5 — CEX-010, CEX-012).

Somente mocks/fakes: nenhuma rede real, nenhuma chave de API, nenhuma
ordem enviada. Foco extra: funding rate suportado, open interest
ausente no CCXT (erro claro, dado nunca inventado).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from errors import ErrorCode, ExchangeError
from gateio.adapter import GateioAdapter
from tests.connectors.fake_ccxt import (
    TS,
    RateLimitExceeded,
    FakeCCXTExchange,
    gapped_ohlcv,
)

GATE_TIMEFRAMES = {
    "10s": 10, "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "8h": 28800,
    "1d": 86400, "7d": 604800, "1w": 604800,
}

_CREDENTIAL_KEYS = {"apiKey", "secret", "password", "uid", "privateKey"}


def make_adapter(**kwargs) -> GateioAdapter:
    fake = kwargs.pop("fake", None) or FakeCCXTExchange(
        timeframes=GATE_TIMEFRAMES
    )
    return GateioAdapter(
        exchange=fake, rate_per_sec=100.0, rate_burst=100, **kwargs
    )


def test_adapter_attributes_and_public_config():
    adapter = make_adapter()
    assert adapter.exchange_id == "gateio"
    assert adapter.name == "Gate.io"
    assert adapter.ccxt_id == "gate"
    assert adapter.rate_per_sec == 20.0  # ritmo do CCXT (50 ms)
    assert adapter.rate_burst == 20
    assert adapter.supports_funding is True
    assert adapter.supports_open_interest is False  # CCXT não implementa
    assert not _CREDENTIAL_KEYS & set(adapter.public_config())
    assert not hasattr(adapter, "create_order")


def test_connect_disconnect_health():
    fake = FakeCCXTExchange(timeframes=GATE_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    adapter.connect()
    assert fake.loaded_markets is True
    assert adapter.health()["connected"] is True
    adapter.disconnect()
    assert adapter.health()["connected"] is False


def test_fetch_markets_ticker_trades_orderbook():
    adapter = make_adapter()
    markets = adapter.fetch_markets()
    assert [m.symbol for m in markets] == [
        "BTC/USDT", "ETH/USDT", "BTC/USDT:USDT",
    ]
    ticker = adapter.fetch_ticker("BTC/USDT")
    assert ticker.last == Decimal("67000.0")
    assert ticker.timestamp_ms == TS
    trades = adapter.fetch_trades("BTC/USDT")
    assert [t.side for t in trades] == ["buy", "sell"]
    book = adapter.fetch_order_book("BTC/USDT")
    assert book.best_bid == Decimal("67000.0")
    assert book.spread == Decimal("10")


def test_fetch_ohlcv_and_gap_detection():
    adapter = make_adapter()
    candles = adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert len(candles) == 3
    assert candles[0].close == Decimal("67050.0")
    fake = FakeCCXTExchange(
        timeframes=GATE_TIMEFRAMES, ohlcv_rows=gapped_ohlcv()
    )
    adapter = make_adapter(fake=fake)
    adapter.fetch_ohlcv("BTC/USDT", "1m")
    assert adapter.health()["gaps_detected"] == 1


def test_fetch_ohlcv_rejects_10s_not_in_spec():
    # O CCXT do Gate serve 10s, mas a especificação (§3) não lista 10s.
    with pytest.raises(ValueError):
        make_adapter().fetch_ohlcv("BTC/USDT", "10s")


def test_fetch_funding_rate_supported():
    funding = make_adapter().fetch_funding_rate("BTC/USDT")
    assert funding.symbol == "BTC/USDT:USDT"
    assert funding.rate == Decimal("0.0001")
    assert funding.timestamp_ms == TS
    assert funding.next_funding_ms == TS + 8 * 3_600_000


def test_fetch_open_interest_not_supported_via_ccxt():
    with pytest.raises(ExchangeError) as excinfo:
        make_adapter().fetch_open_interest("BTC/USDT")
    assert excinfo.value.code == ErrorCode.BAD_RESPONSE
    assert excinfo.value.retryable is False
    assert "não disponível" in excinfo.value.message


def test_error_translation_rate_limit():
    fake = FakeCCXTExchange(timeframes=GATE_TIMEFRAMES)
    adapter = make_adapter(fake=fake)
    fake.fail_with["fetch_ticker"] = RateLimitExceeded("slow")
    with pytest.raises(ExchangeError) as excinfo:
        adapter.fetch_ticker("BTC/USDT")
    assert excinfo.value.code == ErrorCode.RATE_LIMIT
    assert excinfo.value.retryable is True
    assert adapter.health()["errors"] == 1


def test_legacy_wrappers_delegate():
    adapter = make_adapter()
    assert adapter.get_ticker("BTCUSDT")["last"] == "67000.0"
    assert adapter.get_candles("BTC/USDT", "1m")[0]["close"] == "67050.0"
    assert adapter.list_markets()[2]["symbol"] == "BTC/USDT:USDT"
