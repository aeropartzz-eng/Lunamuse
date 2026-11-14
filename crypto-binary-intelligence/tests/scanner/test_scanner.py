"""Testes do scanner multinível (Fase 8 — SCN-001…SCN-003).

Fakes do MarketDataSource; sem rede, sem chave de API.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from models import Candle, OrderBook, Ticker, Trade
from scanner import (
    ActiveScanner,
    DiscoveryScanner,
    PriorityScanner,
    atr_pct,
    book_imbalance,
    cvd,
    detect_candle_pattern,
    detect_sweep,
    rel_volume,
    spread_bps,
)

TS = 1_790_985_600_000  # 2026-10-03 00:00:00 UTC, em ms
D = Decimal


def candle(open_, high, low, close, volume, i=0):
    return Candle(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        open_time_ms=TS + i * 3_600_000,
        close_time_ms=TS + (i + 1) * 3_600_000,
        open=D(str(open_)),
        high=D(str(high)),
        low=D(str(low)),
        close=D(str(close)),
        volume=D(str(volume)),
    )


def ticker(price="100", change="5", volume="1000"):
    return Ticker(
        exchange="binance",
        symbol="BTC/USDT",
        last=D(price),
        timestamp_ms=TS,
        volume_24h=D(volume),
        change_24h_pct=D(change),
    )


def trade(price, qty, side, i=0):
    return Trade(
        exchange="binance",
        symbol="BTC/USDT",
        trade_id=f"t{i}",
        price=D(str(price)),
        quantity=D(str(qty)),
        side=side,
        timestamp_ms=TS + i * 1000,
    )


def book():
    return OrderBook(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp_ms=TS,
        bids=((D("99"), D("10")), (D("98"), D("20"))),
        asks=((D("101"), D("5")), (D("102"), D("15"))),
    )


class FakeSource:
    """MarketDataSource fake: dados fixos por símbolo."""

    def __init__(self, tickers=None, candles=None, trades=None, books=None):
        self.tickers = tickers or {}
        self.candles = candles or {}
        self.trades = trades or {}
        self.books = books or {}

    def get_ticker(self, symbol):
        return self.tickers[symbol]

    def get_candles(self, symbol, timeframe, limit=100):
        return self.candles.get(symbol, [])[:limit]

    def get_trades(self, symbol, limit=100):
        return self.trades.get(symbol, [])[:limit]

    def get_order_book(self, symbol, depth=20):
        return self.books[symbol]


# -- métricas puras ----------------------------------------------------------


def test_rel_volume_last_over_average_of_previous():
    candles = [candle(100, 101, 99, 100, 10, i) for i in range(4)]
    candles.append(candle(100, 101, 99, 100, 40, 4))
    assert rel_volume(candles) == D("4")


def test_rel_volume_needs_history():
    assert rel_volume([candle(100, 101, 99, 100, 10)]) is None
    assert rel_volume([]) is None


def test_atr_pct_average_range():
    candles = [candle(100, 110, 90, 100, 10, 0), candle(100, 105, 95, 100, 10, 1)]
    # (20/100 + 10/100) / 2 = 15%
    assert atr_pct(candles) == D("15")


def test_spread_bps_and_imbalance():
    b = book()
    assert spread_bps(b) == D("200")  # (101-99)/100 * 10000
    # bids 30, asks 20 -> (30-20)/50 = 0.2
    assert book_imbalance(b) == D("0.2")


def test_cvd_buy_minus_sell():
    trades = [trade(100, 3, "buy", 0), trade(100, 1, "sell", 1)]
    assert cvd(trades) == D("2")


def test_detect_candle_pattern_doji_and_engulfing():
    doji = candle(100, 101, 99, 100, 10, 0)
    assert "doji" in detect_candle_pattern([doji])
    prev = candle(105, 106, 99, 100, 10, 0)  # bear
    engulf = candle(99, 107, 98, 106, 10, 1)  # bull engulfing
    assert "engulfing_bull" in detect_candle_pattern([prev, engulf])


def test_detect_sweep_trade_outside_top_of_book():
    assert detect_sweep([trade(98, 1, "sell", 0)], book()) is True
    assert detect_sweep([trade(100, 1, "buy", 0)], book()) is False


# -- Discovery (SCN-001) -----------------------------------------------------


def test_discovery_scan_rows_sorted_and_new_pairs_flagged():
    candles = [candle(100, 101, 99, 100, 10, i) for i in range(5)]
    source = FakeSource(
        tickers={"BTC/USDT": ticker(), "ETH/USDT": ticker("50", "1", "10")},
        candles={"BTC/USDT": candles, "ETH/USDT": candles},
    )
    rows, new = DiscoveryScanner().scan(
        source, "binance", ["BTC/USDT", "ETH/USDT"],
        previous_catalog={"BTC/USDT"},
    )
    assert new == ["ETH/USDT"]
    assert rows[0].symbol == "BTC/USDT"  # maior score (change 5% vs 1%)
    assert rows[0].liquidity_est_usd == D("100") * D("1000")
    assert rows[0].is_new is False
    assert rows[1].is_new is True


def test_discovery_scan_skips_failing_symbol():
    source = FakeSource(tickers={"BTC/USDT": ticker()}, candles={"BTC/USDT": []})

    class Failing(FakeSource):
        def get_ticker(self, symbol):
            if symbol == "BAD/USDT":
                raise RuntimeError("boom")
            return super().get_ticker(symbol)

    rows, _ = DiscoveryScanner().scan(
        Failing(tickers=source.tickers, candles=source.candles),
        "binance", ["BTC/USDT", "BAD/USDT"],
    )
    assert [r.symbol for r in rows] == ["BTC/USDT"]


# -- Active (SCN-002) --------------------------------------------------------


def test_active_scanner_metrics():
    candles = [candle(100, 102, 98, 100, 10, i) for i in range(4)]
    candles.append(candle(100, 110, 90, 108, 50, 4))
    source = FakeSource(candles={"BTC/USDT": candles})
    m = ActiveScanner().analyze(source, "binance", "BTC/USDT")
    assert m.rel_volume == D("5")
    assert m.price == D("108")
    assert m.score > 0


def test_active_scanner_no_candles_raises():
    with pytest.raises(ValueError):
        ActiveScanner().analyze(FakeSource(), "binance", "BTC/USDT")


# -- Priority (SCN-003) ------------------------------------------------------


def test_priority_scanner_book_and_cvd():
    trades = [trade(100, 5, "buy", i) for i in range(3)]
    trades += [trade(100, 1, "sell", 3)]
    source = FakeSource(trades={"BTC/USDT": trades}, books={"BTC/USDT": book()})
    m = PriorityScanner().analyze(source, "binance", "BTC/USDT")
    assert m.spread_bps == D("200")
    assert m.imbalance == D("0.2")
    assert m.cvd == D("14")
    assert m.sweep is False
    # depth: bids 99*10+98*20=2950, asks 101*5+102*15=2035
    assert m.depth_value_usd == D("4985")


def test_priority_scanner_absorption_heuristic():
    # CVD todo comprador e range de preço ~0 -> absorção.
    trades = [trade(100, 10, "buy", i) for i in range(5)]
    source = FakeSource(trades={"BTC/USDT": trades}, books={"BTC/USDT": book()})
    m = PriorityScanner().analyze(source, "binance", "BTC/USDT")
    assert m.absorption is True
