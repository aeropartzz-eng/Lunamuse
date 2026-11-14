"""Testes de estrutura de mercado (Fase 10 — PAT-007).

Séries sintéticas com topos/fundos conhecidos: HH/HL classifica alta,
BOS/CHoCH em série construída, FVG, Fibonacci, S/R, sweep, breakout e
reteste, pullback e order block. Sem rede.
"""

from __future__ import annotations

from decimal import Decimal

from models import Candle
from structure import (
    Level,
    classify_trend,
    detect_bos_choch,
    detect_breakout_retest,
    detect_fvg,
    detect_liquidity_sweeps,
    detect_order_blocks,
    detect_pullbacks,
    fib_extension,
    fib_retracement,
    find_levels,
    find_swings,
)

BASE_MS = 1_700_000_000_000


def candle(i: int, o: float, h: float, l: float, c: float,
           volume: float = 100.0) -> Candle:
    return Candle(
        exchange="binance", symbol="BTC/USDT", timeframe="1m",
        open_time_ms=BASE_MS + i * 60_000,
        close_time_ms=BASE_MS + (i + 1) * 60_000,
        open=Decimal(str(o)), high=Decimal(str(h)), low=Decimal(str(l)),
        close=Decimal(str(c)), volume=Decimal(str(volume)))


def series_from_highs(highs: list[float], spread: float = 1.0,
                      body: float = 0.1) -> list[Candle]:
    """Candles de alta com high/low dados; close = high - body."""
    out = []
    for i, h in enumerate(highs):
        out.append(candle(i, h - body - 0.1, h, h - spread, h - body))
    return out


def uptrend_series() -> list[Candle]:
    """HH/HL claros: topos 104, 105, 106, 107; fundos 100, 101, 102, 103."""
    highs = [100, 102, 104, 101, 103, 105, 102, 104, 106, 103, 105, 107,
             104, 106, 108]
    return series_from_highs(highs)


# --- Swings e tendência --------------------------------------------------------

def test_find_swings_uptrend():
    swings = find_swings(uptrend_series())
    highs = [s.price for s in swings if s.kind == "high"]
    lows = [s.price for s in swings if s.kind == "low"]
    assert highs == [104, 105, 106, 107]
    assert lows == [100, 101, 102, 103]


def test_classify_trend_uptrend_hh_hl():
    result = classify_trend(uptrend_series())
    assert result["trend"] == "uptrend"
    assert result["higher_highs"] is True
    assert result["higher_lows"] is True


def test_classify_trend_downtrend_lh_ll():
    highs = [108, 106, 104, 107, 105, 103, 106, 104, 102, 105, 103, 101,
             104, 102, 100]
    result = classify_trend(series_from_highs(highs))
    assert result["trend"] == "downtrend"
    assert result["lower_highs"] is True
    assert result["lower_lows"] is True


def test_classify_trend_sideways_on_flat_series():
    series = [candle(i, 100, 100.5, 99.5, 100) for i in range(10)]
    assert classify_trend(series)["trend"] == "sideways"


# --- BOS / CHoCH ---------------------------------------------------------------

def test_bos_bullish_in_uptrend():
    events = detect_bos_choch(uptrend_series())
    assert events, "esperava ao menos um BOS na série de alta"
    first = events[0]
    assert first.kind == "bos" and first.direction == "bullish"
    assert first.index == 5 and first.level == 104


def test_choch_bearish_after_uptrend():
    # Alta com BOS e depois fechamento abaixo do último swing low.
    highs = [100, 102, 104, 101, 103, 105, 102, 104, 100, 98, 97, 96]
    events = detect_bos_choch(series_from_highs(highs))
    kinds = [(e.kind, e.direction) for e in events]
    assert ("bos", "bullish") in kinds
    assert ("choch", "bearish") in kinds
    choch = next(e for e in events if e.kind == "choch")
    assert choch.index == 8 and choch.level == 100


def test_no_bos_choch_on_flat_series():
    series = [candle(i, 100, 100.5, 99.5, 100) for i in range(10)]
    assert detect_bos_choch(series) == []


# --- Suporte / resistência ------------------------------------------------------

def test_find_levels_repeated_high_is_resistance():
    highs = [100, 102, 105, 101, 103, 105, 102, 104, 100, 99, 98, 97]
    levels = find_levels(series_from_highs(highs))
    assert any(lv.price == 105 and lv.touches == 2
               and lv.kind == "resistance" for lv in levels)


def test_find_levels_empty_without_repeated_swings():
    assert find_levels(uptrend_series()) == []


# --- Breakout e reteste ----------------------------------------------------------

def test_breakout_and_retest():
    level = Level(price=100.0, touches=2, kind="resistance")
    series = [
        candle(0, 97, 98.5, 96.5, 98),
        candle(1, 98, 99.5, 97.5, 99),
        candle(2, 99, 101.5, 98.5, 101),
        candle(3, 101, 101, 99.5, 100.5),
    ]
    events = detect_breakout_retest(series, [level])
    kinds = [(e.kind, e.direction, e.index) for e in events]
    assert ("breakout", "bullish", 2) in kinds
    assert ("retest", "bullish", 3) in kinds


def test_no_breakout_without_crossing():
    level = Level(price=100.0, touches=2, kind="resistance")
    series = [candle(i, 97 + i * 0.5, 98 + i * 0.5, 96 + i * 0.5, 97.5 + i * 0.5)
              for i in range(4)]
    assert detect_breakout_retest(series, [level]) == []


# --- Pullback ----------------------------------------------------------------------

def test_pullback_bullish():
    lows = [105, 103, 100, 102, 104, 106, 108, 104, 105]
    series = []
    for i, lo in enumerate(lows):
        series.append(candle(i, lo + 0.5, lo + 2, lo, lo + 1))
    events = detect_pullbacks(series)
    assert events, "esperava um pullback de alta"
    ev = events[0]
    assert ev.kind == "pullback" and ev.direction == "bullish"
    assert ev.index == 7
    assert abs(ev.details["retracement"] - 0.6) < 1e-9


def test_pullback_not_detected_when_origin_breaks():
    # Perna 100 -> 110 e depois mínima abaixo de 100: não é pullback.
    lows = [105, 103, 100, 102, 104, 106, 108, 99, 98]
    series = []
    for i, lo in enumerate(lows):
        series.append(candle(i, lo + 0.5, lo + 2, lo, lo + 1))
    assert detect_pullbacks(series) == []


# --- Liquidity Sweep ------------------------------------------------------------------

def test_liquidity_sweep_bearish_wick_above_swing_high():
    series = [
        candle(0, 99.5, 100, 99, 99.9),
        candle(1, 101.5, 102, 101, 101.9),
        candle(2, 103.5, 104, 103, 103.9),
        candle(3, 100.5, 101, 100, 100.9),
        candle(4, 102.5, 103, 102, 102.9),
        candle(5, 104.5, 105, 103, 103.0),  # pavio acima de 104, fecha abaixo
    ]
    events = detect_liquidity_sweeps(series)
    assert events, "esperava um sweep do topo 104"
    ev = events[0]
    assert ev.kind == "sweep" and ev.direction == "bearish"
    assert ev.index == 5 and ev.level == 104
    assert ev.details["wick_beyond"] == 1.0


def test_liquidity_sweep_not_detected_on_real_breakout():
    series = [
        candle(0, 99.5, 100, 99, 99.9),
        candle(1, 101.5, 102, 101, 101.9),
        candle(2, 103.5, 104, 103, 103.9),
        candle(3, 100.5, 101, 100, 100.9),
        candle(4, 102.5, 103, 102, 102.9),
        candle(5, 104.5, 105, 103, 104.5),  # rompe 104 e fecha acima: BOS, não sweep
    ]
    assert detect_liquidity_sweeps(series) == []


# --- FVG -------------------------------------------------------------------------------

def test_fvg_bullish():
    series = [
        candle(0, 99, 100, 98, 99.5),
        candle(1, 99.5, 100.5, 99, 100),
        candle(2, 101, 102.5, 101, 102),
    ]
    gaps = detect_fvg(series)
    assert len(gaps) == 1
    assert gaps[0].direction == "bullish"
    assert gaps[0].bottom == 100 and gaps[0].top == 101
    assert gaps[0].filled is False


def test_fvg_bearish():
    series = [
        candle(0, 101, 102, 100, 100.5),
        candle(1, 100.5, 101, 100, 100),
        candle(2, 99, 99.5, 98, 98.5),
    ]
    gaps = detect_fvg(series)
    assert len(gaps) == 1
    assert gaps[0].direction == "bearish"
    assert gaps[0].bottom == 99.5 and gaps[0].top == 100


def test_fvg_filled_when_price_closes_through():
    series = [
        candle(0, 99, 100, 98, 99.5),
        candle(1, 99.5, 100.5, 99, 100),
        candle(2, 101, 102.5, 101, 102),
        candle(3, 102, 102.5, 99, 99.5),  # fecha abaixo do fundo do FVG
    ]
    gaps = detect_fvg(series)
    assert gaps[0].filled is True and gaps[0].filled_index == 3


def test_fvg_not_detected_without_gap():
    series = [
        candle(0, 99, 100, 98, 99.5),
        candle(1, 99.5, 100.5, 99, 100),
        candle(2, 100, 100.5, 99.5, 100.2),
    ]
    assert detect_fvg(series) == []


# --- Order Blocks -------------------------------------------------------------------------

def test_order_block_before_bos():
    highs = [100, 102, 104, 101, 103, 105, 102, 104, 106, 103, 105, 107,
             104, 106, 108]
    series = series_from_highs(highs)
    # Candle 4 vira de baixa (último candle de baixa antes do BOS no 5).
    series[4] = candle(4, 102.9, 103, 101.5, 102.0)
    blocks = detect_order_blocks(series)
    assert blocks, "esperava um order block antes do BOS"
    block = blocks[0]
    assert block.direction == "bullish" and block.bos_index == 5
    assert block.index == 4
    assert block.top == 103 and block.bottom == 101.5


def test_no_order_block_without_bos():
    series = [candle(i, 100, 100.5, 99.5, 100) for i in range(10)]
    assert detect_order_blocks(series) == []


# --- Fibonacci -------------------------------------------------------------------------------

def test_fib_retracement_levels():
    levels = fib_retracement(100, 110)
    assert levels[0.0] == 110
    assert levels[1.0] == 100
    assert levels[0.5] == 105
    assert levels[0.618] == 103.82
    assert levels[0.382] == 106.18


def test_fib_extension_levels():
    levels = fib_extension(100, 110)
    assert levels[1.272] == 112.72
    assert levels[1.618] == 116.18
    assert levels[2.618] == 126.18


def test_fib_retracement_rejects_inverted_range():
    import pytest
    with pytest.raises(ValueError):
        fib_retracement(110, 100)
