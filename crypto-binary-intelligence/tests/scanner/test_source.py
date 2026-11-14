"""Testes do protocolo MarketDataSource e do adaptador (Fase 8).

Verifica que o adaptador fino delega ao ExchangeAdapter e que um
fake estrutural (sem herança) satisfaz o protocolo.
"""

from __future__ import annotations

from decimal import Decimal

from models import Market, Ticker
from source import AdapterMarketDataSource, MarketDataSource

TS = 1_790_985_600_000
D = Decimal


class FakeAdapter:
    """ExchangeAdapter fake mínimo (só os métodos usados)."""

    exchange_id = "binance"
    name = "Binance"
    calls: list

    def __init__(self):
        self.calls = []

    def fetch_ticker(self, symbol):
        self.calls.append(("ticker", symbol))
        return Ticker(
            exchange="binance", symbol=symbol, last=D("100"),
            timestamp_ms=TS,
        )

    def fetch_ohlcv(self, symbol, timeframe, limit=100):
        self.calls.append(("ohlcv", symbol, timeframe, limit))
        return []

    def fetch_trades(self, symbol, limit=100):
        self.calls.append(("trades", symbol, limit))
        return []

    def fetch_order_book(self, symbol, depth=20):
        self.calls.append(("book", symbol, depth))
        return None

    def fetch_markets(self):
        return [
            Market(exchange="binance", symbol="BTC/USDT", base="BTC", quote="USDT"),
            Market(exchange="binance", symbol="ETH/USDT", base="ETH", quote="USDT"),
        ]


def test_adapter_delegates_to_fetch_methods():
    adapter = FakeAdapter()
    source = AdapterMarketDataSource(adapter)
    assert source.exchange == "binance"
    assert source.get_ticker("BTC/USDT").last == D("100")
    source.get_candles("BTC/USDT", "1h", limit=10)
    source.get_trades("BTC/USDT", limit=5)
    source.get_order_book("BTC/USDT", depth=5)
    assert source.list_symbols() == ["BTC/USDT", "ETH/USDT"]
    assert ("ticker", "BTC/USDT") in adapter.calls
    assert ("ohlcv", "BTC/USDT", "1h", 10) in adapter.calls


def test_structural_fake_satisfies_protocol():
    class FakeSource:
        def get_ticker(self, symbol):
            return None

        def get_candles(self, symbol, timeframe, limit=100):
            return []

        def get_trades(self, symbol, limit=100):
            return []

        def get_order_book(self, symbol, depth=20):
            return None

    # Protocol runtime_checkable: isinstance verifica a presença
    # dos métodos, sem exigir herança.
    assert isinstance(FakeSource(), MarketDataSource)
    assert isinstance(AdapterMarketDataSource(FakeAdapter()), MarketDataSource)
