"""Testes de Order Flow (Fase 10 — FLOW-001…FLOW-005).

CVD de sequência com lados conhecidos bate o valor esperado; imbalance
do book com valores conhecidos; absorção, exaustão, sweep, spread e
slippage estimado. Sem rede.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from models import Candle, OrderBook, Trade
from order_flow import (
    build_footprint,
    book_imbalance,
    cumulative_cvd,
    depth_change,
    detect_absorption,
    detect_exhaustion,
    detect_liquidity_sweep,
    estimated_slippage,
    final_cvd,
    footprint_status,
    spread_bps,
    volume_delta,
)

BASE_MS = 1_700_000_000_000


def trade(i: int, side: str, qty: float, price: float = 100.0) -> Trade:
    return Trade(
        exchange="binance", symbol="BTC/USDT", trade_id=f"t{i}",
        price=Decimal(str(price)), quantity=Decimal(str(qty)),
        side=side, timestamp_ms=BASE_MS + i * 1_000)


def book(bids: list[tuple[float, float]],
         asks: list[tuple[float, float]]) -> OrderBook:
    return OrderBook(
        exchange="binance", symbol="BTC/USDT", timestamp_ms=BASE_MS,
        bids=tuple((Decimal(str(p)), Decimal(str(q))) for p, q in bids),
        asks=tuple((Decimal(str(p)), Decimal(str(q))) for p, q in asks))


def candle(i: int, o: float, h: float, l: float, c: float,
           volume: float = 100.0) -> Candle:
    return Candle(
        exchange="binance", symbol="BTC/USDT", timeframe="1m",
        open_time_ms=BASE_MS + i * 60_000,
        close_time_ms=BASE_MS + (i + 1) * 60_000,
        open=Decimal(str(o)), high=Decimal(str(h)), low=Decimal(str(l)),
        close=Decimal(str(c)), volume=Decimal(str(volume)))


# --- FLOW-001: Volume Delta ---------------------------------------------------

def test_volume_delta_known_sides():
    trades = [trade(0, "buy", 2), trade(1, "buy", 3), trade(2, "sell", 1)]
    vd = volume_delta(trades)
    assert vd.buy_volume == Decimal("5")
    assert vd.sell_volume == Decimal("1")
    assert vd.delta == Decimal("4")
    assert vd.total_volume == Decimal("6")
    assert vd.buy_ratio == pytest.approx(5 / 6, abs=1e-3)
    assert vd.dominant_side == "buy"


def test_volume_delta_empty():
    vd = volume_delta([])
    assert vd.delta == Decimal("0") and vd.total_volume == Decimal("0")
    assert vd.dominant_side is None


def test_volume_delta_sell_dominant():
    trades = [trade(0, "sell", 4), trade(1, "buy", 1)]
    assert volume_delta(trades).dominant_side == "sell"


# --- FLOW-002: CVD -------------------------------------------------------------

def test_cvd_known_sequence():
    trades = [trade(0, "buy", 1.5), trade(1, "sell", 0.5), trade(2, "buy", 2)]
    points = cumulative_cvd(trades)
    assert [p.cvd for p in points] == [
        Decimal("1.5"), Decimal("1.0"), Decimal("3.0")]
    assert [p.delta for p in points] == [
        Decimal("1.5"), Decimal("-0.5"), Decimal("2")]
    assert final_cvd(trades) == Decimal("3.0")


def test_cvd_empty_is_zero():
    assert cumulative_cvd([]) == []
    assert final_cvd([]) == Decimal("0")


def test_cvd_all_sell_is_negative():
    trades = [trade(0, "sell", 1), trade(1, "sell", 2)]
    assert final_cvd(trades) == Decimal("-3")


# --- FLOW-003: Imbalance e profundidade ------------------------------------------

def test_book_imbalance_known_values():
    ob = book([(100, 10), (99, 5)], [(101, 4), (102, 2)])
    imb = book_imbalance(ob, levels=2)
    assert imb.bid_qty == Decimal("15")
    assert imb.ask_qty == Decimal("6")
    assert imb.imbalance == pytest.approx((15 - 6) / 21, abs=1e-3)
    assert imb.dominant_side == "bid"
    assert imb.strong is True


def test_book_imbalance_balanced_is_near_zero():
    ob = book([(100, 10), (99, 10)], [(101, 10), (102, 10)])
    imb = book_imbalance(ob, levels=2)
    assert imb.imbalance == pytest.approx(0.0, abs=1e-9)
    assert imb.dominant_side is None
    assert imb.strong is False


def test_book_imbalance_empty_book():
    ob = book([], [])
    imb = book_imbalance(ob)
    assert imb.imbalance == 0.0 and imb.dominant_side is None


def test_book_imbalance_respects_levels():
    ob = book([(100, 10), (99, 5), (98, 100)], [(101, 4)])
    imb = book_imbalance(ob, levels=2)
    assert imb.bid_qty == Decimal("15")  # o 3º nível (100) fica fora


def test_depth_change_known_values():
    prev = book([(100, 10)], [(101, 6)])
    curr = book([(100, 14)], [(101, 6)])
    change = depth_change(prev, curr, levels=1)
    assert change.bid_qty_delta == Decimal("4")
    assert change.ask_qty_delta == Decimal("0")
    assert change.bid_change_pct == pytest.approx(0.4, abs=1e-3)
    assert change.ask_change_pct == pytest.approx(0.0, abs=1e-9)


def test_depth_change_ask_removed():
    prev = book([(100, 10)], [(101, 6)])
    curr = book([(100, 10)], [(101, 2)])
    change = depth_change(prev, curr, levels=1)
    assert change.ask_qty_delta == Decimal("-4")
    assert change.total_qty_delta == Decimal("-4")


# --- Spread e slippage --------------------------------------------------------------

def test_spread_bps_known_values():
    ob = book([(100, 10)], [(100.5, 10)])
    assert spread_bps(ob) == pytest.approx(0.5 / 100.25 * 10_000, abs=1e-2)


def test_spread_bps_empty_book_is_none():
    assert spread_bps(book([], [])) is None


def test_estimated_slippage_buy_walks_book():
    ob = book([(100, 10)], [(101, 10), (102, 10)])
    est = estimated_slippage(ob, "buy", Decimal("12"))
    assert est.filled_quantity == Decimal("12")
    assert est.fully_filled is True
    assert est.avg_fill_price == Decimal("1214") / Decimal("12")
    # mid = (100 + 101) / 2 = 100.5
    assert est.slippage_bps == pytest.approx(
        (float(Decimal("1214") / Decimal("12")) - 100.5) / 100.5 * 10_000,
        abs=1e-2)


def test_estimated_slippage_sell_partial_fill():
    ob = book([(100, 5), (99, 5)], [(101, 10)])
    est = estimated_slippage(ob, "sell", Decimal("12"))
    assert est.filled_quantity == Decimal("10")
    assert est.fully_filled is False
    assert est.slippage_bps is not None


def test_estimated_slippage_rejects_bad_side():
    ob = book([(100, 10)], [(101, 10)])
    with pytest.raises(ValueError):
        estimated_slippage(ob, "hold", Decimal("1"))


# --- FLOW-004: absorção e exaustão ------------------------------------------------------

def test_absorption_buy_side_no_price_move():
    trades = [trade(i, "buy", 10) for i in range(8)] + \
             [trade(8 + i, "sell", 5) for i in range(4)]
    # buy 80, sell 20 -> 80% num lado só; preço quase não se move.
    ev = detect_absorption(trades, start_price=100.0, end_price=100.05, atr=1.0)
    assert ev is not None
    assert ev.absorbed_side == "buy"
    assert ev.one_sided_ratio == pytest.approx(0.8, abs=1e-3)


def test_absorption_not_detected_when_price_moves():
    trades = [trade(i, "buy", 10) for i in range(8)] + \
             [trade(8 + i, "sell", 5) for i in range(4)]
    ev = detect_absorption(trades, start_price=100.0, end_price=101.0, atr=1.0)
    assert ev is None  # moveu 1,0 ATR: não é absorção


def test_absorption_not_detected_when_balanced():
    trades = [trade(i, "buy", 10) for i in range(5)] + \
             [trade(5 + i, "sell", 10) for i in range(5)]
    ev = detect_absorption(trades, start_price=100.0, end_price=100.0, atr=1.0)
    assert ev is None


def test_exhaustion_bearish_upper_wick():
    c = candle(0, 100, 106, 99, 101, volume=300)
    ev = detect_exhaustion(c, avg_volume=Decimal("100"), index=0)
    assert ev is not None
    assert ev.direction == "bearish"
    assert ev.volume_ratio == pytest.approx(3.0, abs=1e-3)
    assert ev.wick_ratio == pytest.approx(5 / 7, abs=1e-3)


def test_exhaustion_bullish_lower_wick():
    c = candle(0, 101, 102, 95, 100, volume=250)
    ev = detect_exhaustion(c, avg_volume=Decimal("100"), index=0)
    assert ev is not None and ev.direction == "bullish"


def test_exhaustion_not_detected_without_volume_climax():
    c = candle(0, 100, 106, 99, 101, volume=100)
    assert detect_exhaustion(c, avg_volume=Decimal("100"), index=0) is None


def test_exhaustion_not_detected_without_long_wick():
    c = candle(0, 100, 102, 99, 101, volume=300)
    assert detect_exhaustion(c, avg_volume=Decimal("100"), index=0) is None


# --- FLOW-005: Liquidity Sweep ---------------------------------------------------------------

def test_liquidity_sweep_bullish_below_level():
    series = [
        candle(0, 101, 102, 100.5, 101),
        candle(1, 101, 102, 99, 101.5),  # varre abaixo de 100, fecha acima
    ]
    sweeps = detect_liquidity_sweep(series, level=100.0, direction="bullish")
    assert len(sweeps) == 1
    assert sweeps[0].index == 1 and sweeps[0].wick_beyond == 1.0


def test_liquidity_sweep_bearish_above_level():
    series = [
        candle(0, 99, 99.5, 98, 99),
        candle(1, 99, 101, 98.5, 99.5),  # varre acima de 100, fecha abaixo
    ]
    sweeps = detect_liquidity_sweep(series, level=100.0, direction="bearish")
    assert len(sweeps) == 1
    assert sweeps[0].index == 1 and sweeps[0].wick_beyond == 1.0


def test_liquidity_sweep_not_detected_when_close_stays_out():
    series = [candle(0, 101, 102, 99, 99.5)]  # varre e fecha abaixo: rompimento
    assert detect_liquidity_sweep(series, level=100.0, direction="bullish") == []


def test_liquidity_sweep_rejects_bad_direction():
    with pytest.raises(ValueError):
        detect_liquidity_sweep([], level=100.0, direction="sideways")


# --- Footprint: indisponível ----------------------------------------------------------------------

def test_footprint_unavailable_and_documented():
    status = footprint_status()
    assert status["available"] is False
    assert "required_data" in status
    with pytest.raises(NotImplementedError):
        build_footprint()
