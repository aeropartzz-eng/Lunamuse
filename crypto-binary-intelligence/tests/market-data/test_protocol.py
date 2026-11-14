"""Testes do protocolo MarketDataSource (consumido pela Fase 8).

``get_ticker`` / ``get_candles`` / ``get_trades`` / ``get_order_book``
— exatamente estes 4 métodos. Sem rede.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from market_data import (
    InMemoryMarketDataSource,
    MarketDataSource,
    RestMarketDataSource,
)
from models import Candle, OrderBook, Ticker, Trade

T0 = 1_793_000_000_000  # ms UTC (2026-11-13)


def test_inmemory_source_satisfies_protocol():
    source = InMemoryMarketDataSource("binance")
    assert isinstance(source, MarketDataSource)
    assert hasattr(source, "get_ticker")
    assert hasattr(source, "get_candles")
    assert hasattr(source, "get_trades")
    assert hasattr(source, "get_order_book")


def test_inmemory_source_roundtrip():
    source = InMemoryMarketDataSource("binance")
    source.add_ticker(
        Ticker(
            exchange="binance",
            symbol="BTC/USDT",
            last=Decimal("90000"),
            timestamp_ms=T0,
        )
    )
    candle = Candle(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1m",
        open_time_ms=T0,
        close_time_ms=T0 + 59_999,
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("1"),
        close=Decimal("2"),
        volume=Decimal("3"),
    )
    source.add_candles([candle])
    source.add_trades(
        [
            Trade(
                exchange="binance",
                symbol="BTC/USDT",
                trade_id="1",
                price=Decimal("90000"),
                quantity=Decimal("0.01"),
                side="buy",
                timestamp_ms=T0,
            )
        ]
    )
    book = OrderBook(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp_ms=T0,
        bids=((Decimal("89999"), Decimal("1")),),
        asks=((Decimal("90001"), Decimal("1")),),
    )
    source.set_order_book(book)

    assert source.get_ticker("BTC/USDT").last == Decimal("90000")
    assert source.get_candles("BTC/USDT", "1m", limit=10) == [candle]
    assert len(source.get_trades("BTC/USDT", limit=10)) == 1
    assert source.get_order_book("BTC/USDT", depth=20).spread == Decimal("2")
    # limit respeitado
    with pytest.raises(ValueError, match="limit deve ser > 0"):
        source.get_candles("BTC/USDT", "1m", limit=0)
    # timeframe inválido rejeitado (nunca inventar granularidade)
    with pytest.raises(ValueError, match="timeframe inválido"):
        source.get_candles("BTC/USDT", "2m")
    # sem dados: erro explícito, não dado inventado
    with pytest.raises(Exception, match="sem ticker"):
        source.get_ticker("ETH/USDT")
    with pytest.raises(Exception, match="sem book"):
        source.get_order_book("ETH/USDT")


class FakeAdapter:
    """ExchangeAdapter fake (sem rede) para o RestMarketDataSource."""

    exchange_id = "binance"

    def __init__(self) -> None:
        self.calls: list = []

    def fetch_ticker(self, symbol):
        self.calls.append(("ticker", symbol))
        return Ticker(
            exchange="binance", symbol=symbol,
            last=Decimal("90000"), timestamp_ms=T0,
        )

    def fetch_ohlcv(self, symbol, timeframe, limit=100):
        self.calls.append(("ohlcv", symbol, timeframe, limit))
        return [
            Candle(
                exchange="binance", symbol=symbol, timeframe=timeframe,
                open_time_ms=T0, close_time_ms=T0 + 59_999,
                open=Decimal("1"), high=Decimal("1"), low=Decimal("1"),
                close=Decimal("1"), volume=Decimal("1"),
            )
        ]

    def fetch_trades(self, symbol, limit=100):
        self.calls.append(("trades", symbol, limit))
        return [
            Trade(
                exchange="binance", symbol=symbol, trade_id="1",
                price=Decimal("90000"), quantity=Decimal("0.01"),
                side="buy", timestamp_ms=T0,
            )
        ]

    def fetch_order_book(self, symbol, depth=20):
        self.calls.append(("book", symbol, depth))
        return OrderBook(
            exchange="binance", symbol=symbol, timestamp_ms=T0,
            bids=((Decimal("89999"), Decimal("1")),),
            asks=((Decimal("90001"), Decimal("1")),),
        )


def test_rest_source_delegates_to_adapter():
    adapter = FakeAdapter()
    source = RestMarketDataSource(adapter)
    assert isinstance(source, MarketDataSource)
    assert source.get_ticker("BTC/USDT").last == Decimal("90000")
    assert len(source.get_candles("BTC/USDT", "1m", limit=5)) == 1
    assert len(source.get_trades("BTC/USDT", limit=5)) == 1
    assert source.get_order_book("BTC/USDT", depth=5).best_bid == Decimal("89999")
    assert ("ohlcv", "BTC/USDT", "1m", 5) in adapter.calls
    with pytest.raises(ValueError, match="limit deve ser > 0"):
        source.get_trades("BTC/USDT", limit=0)
    with pytest.raises(ValueError, match="timeframe inválido"):
        source.get_candles("BTC/USDT", "7m")
