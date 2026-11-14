"""Testes de padrões de velas (Fase 10 — PAT-001…PAT-006).

Cada padrão tem ao menos um teste positivo (série sintética que forma
o padrão e deve ser detectada) e um negativo (série sem o padrão não
deve gerar falso positivo). Sem rede.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from models import Candle
from patterns import (
    assess_pattern,
    detect_all,
    detect_at,
    detect_doji,
    detect_engulfing,
    detect_hammer,
    detect_harami,
    detect_inside_bar,
    detect_marubozu,
    detect_morning_evening_star,
    detect_outside_bar,
    detect_piercing_dark_cloud,
    detect_shooting_star,
    detect_soldiers_crows,
    detect_spinning_top,
    detect_tweezers,
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


def downtrend(n: int = 5, start: float = 110.0, step: float = 2.0) -> list[Candle]:
    """Candles de baixa (fechamentos decrescentes) para dar contexto."""
    out = []
    for i in range(n):
        close = start - i * step
        out.append(candle(i, close + 0.5, close + 1.0, close - 0.5, close))
    return out


def uptrend(n: int = 5, start: float = 100.0, step: float = 2.0) -> list[Candle]:
    out = []
    for i in range(n):
        close = start + i * step
        out.append(candle(i, close - 0.5, close + 1.0, close - 0.5, close))
    return out


def names(dets) -> list[str]:
    return [d.name for d in dets]


# --- PAT-001: Doji -----------------------------------------------------------

def test_doji_detected():
    series = [candle(0, 100, 100.6, 99, 100.05)]
    det = detect_doji(series, 0)
    assert det is not None and det.name == "doji" and det.direction == "neutral"
    assert det.generates_entry is False and det.requires_confirmation is True


def test_doji_not_detected_when_body_is_large():
    series = [candle(0, 100, 101, 99, 101)]
    assert detect_doji(series, 0) is None


def test_gravestone_doji():
    series = [candle(0, 100, 102, 99.9, 100.1)]
    det = detect_doji(series, 0)
    assert det is not None and det.name == "gravestone_doji"
    assert det.direction == "bearish"


def test_dragonfly_doji():
    series = [candle(0, 100, 100.1, 98, 99.9)]
    det = detect_doji(series, 0)
    assert det is not None and det.name == "dragonfly_doji"
    assert det.direction == "bullish"


def test_long_legged_doji():
    series = [candle(0, 100, 102, 98, 100.05)]
    det = detect_doji(series, 0)
    assert det is not None and det.name == "long_legged_doji"


def test_four_price_doji():
    series = [candle(0, 100, 100, 100, 100)]
    det = detect_doji(series, 0)
    assert det is not None and det.name == "four_price_doji"


# --- PAT-002: Hammer / Shooting Star -----------------------------------------

def test_hammer_after_downtrend():
    series = downtrend() + [candle(5, 100, 101.5, 97, 101)]
    det = detect_hammer(series, 5)
    assert det is not None and det.name == "hammer"
    assert det.direction == "bullish"


def test_hanging_man_after_uptrend():
    series = uptrend() + [candle(5, 110, 111.5, 107, 111)]
    det = detect_hammer(series, 5)
    assert det is not None and det.name == "hanging_man"
    assert det.direction == "bearish"


def test_hammer_not_detected_without_long_lower_shadow():
    series = downtrend() + [candle(5, 100, 101, 99, 101)]
    assert detect_hammer(series, 5) is None


def test_shooting_star_after_uptrend():
    series = uptrend() + [candle(5, 100, 103, 98.8, 99)]
    det = detect_shooting_star(series, 5)
    assert det is not None and det.name == "shooting_star"
    assert det.direction == "bearish"


def test_inverted_hammer_after_downtrend():
    series = downtrend() + [candle(5, 100, 103, 98.8, 99)]
    det = detect_shooting_star(series, 5)
    assert det is not None and det.name == "inverted_hammer"
    assert det.direction == "bullish"


def test_shooting_star_not_detected_without_long_upper_shadow():
    series = uptrend() + [candle(5, 100, 100.6, 99, 99.5)]
    assert detect_shooting_star(series, 5) is None


# --- PAT-003: Engulfing / Harami / Piercing / Dark Cloud ---------------------

def test_bullish_engulfing():
    series = [candle(0, 102, 102.5, 99.5, 100),
              candle(1, 99.5, 103.5, 99, 103)]
    det = detect_engulfing(series, 1)
    assert det is not None and det.name == "bullish_engulfing"
    assert det.direction == "bullish" and det.confidence > 0.5


def test_bearish_engulfing():
    series = [candle(0, 100, 102.5, 99.5, 102),
              candle(1, 102.5, 103, 99, 99.5)]
    det = detect_engulfing(series, 1)
    assert det is not None and det.name == "bearish_engulfing"


def test_engulfing_not_detected_when_not_engulfed():
    series = [candle(0, 102, 102.5, 99.5, 100),
              candle(1, 100.5, 102, 100, 101.5)]
    assert detect_engulfing(series, 1) is None


def test_engulfing_not_detected_same_color():
    series = [candle(0, 100, 102, 99, 101),
              candle(1, 99, 103, 98, 102)]
    assert detect_engulfing(series, 1) is None


def test_bullish_harami():
    series = [candle(0, 105, 105.5, 99.5, 100),
              candle(1, 101, 103.5, 100.5, 103)]
    det = detect_harami(series, 1)
    assert det is not None and det.name == "bullish_harami"


def test_bearish_harami():
    series = [candle(0, 100, 105.5, 99.5, 105),
              candle(1, 104, 104.5, 101, 102)]
    det = detect_harami(series, 1)
    assert det is not None and det.name == "bearish_harami"


def test_harami_not_detected_when_body_outside():
    series = [candle(0, 105, 105.5, 99.5, 100),
              candle(1, 99, 106, 98.5, 104)]
    assert detect_harami(series, 1) is None


def test_piercing_line():
    series = [candle(0, 105, 105.5, 99.5, 100),
              candle(1, 99, 103.5, 98.5, 103)]
    det = detect_piercing_dark_cloud(series, 1)
    assert det is not None and det.name == "piercing_line"
    assert det.direction == "bullish"


def test_piercing_not_detected_below_midpoint():
    series = [candle(0, 105, 105.5, 99.5, 100),
              candle(1, 99, 103, 98.5, 101)]
    assert detect_piercing_dark_cloud(series, 1) is None


def test_dark_cloud_cover():
    series = [candle(0, 100, 105.5, 99.5, 105),
              candle(1, 106, 106.5, 101.5, 102)]
    det = detect_piercing_dark_cloud(series, 1)
    assert det is not None and det.name == "dark_cloud_cover"
    assert det.direction == "bearish"


def test_dark_cloud_not_detected_above_midpoint():
    series = [candle(0, 100, 105.5, 99.5, 105),
              candle(1, 106, 106.5, 103, 104)]
    assert detect_piercing_dark_cloud(series, 1) is None


# --- PAT-004: Morning / Evening Star ------------------------------------------

def test_morning_star():
    series = [candle(0, 110, 110.5, 99.5, 100),
              candle(1, 99, 100, 98.5, 99.5),
              candle(2, 100, 108.5, 99.5, 108)]
    det = detect_morning_evening_star(series, 2)
    assert det is not None and det.name == "morning_star"
    assert det.direction == "bullish"


def test_evening_star():
    series = [candle(0, 100, 110.5, 99.5, 110),
              candle(1, 111, 112, 110.5, 110.5),
              candle(2, 110, 110.5, 102, 103)]
    det = detect_morning_evening_star(series, 2)
    assert det is not None and det.name == "evening_star"
    assert det.direction == "bearish"


def test_morning_star_not_detected_when_third_candle_fails_midpoint():
    series = [candle(0, 110, 110.5, 99.5, 100),
              candle(1, 99, 100, 98.5, 99.5),
              candle(2, 100, 104, 99.5, 103)]
    assert detect_morning_evening_star(series, 2) is None


# --- PAT-005: Soldiers / Crows / Tweezers / Marubozu / Spinning / In-Out -----

def test_three_white_soldiers():
    series = [candle(0, 100, 102.5, 99.5, 102),
              candle(1, 101, 104, 100.5, 103.5),
              candle(2, 102.5, 105.5, 102, 105)]
    det = detect_soldiers_crows(series, 2)
    assert det is not None and det.name == "three_white_soldiers"
    assert det.direction == "bullish"


def test_three_black_crows():
    series = [candle(0, 105, 105.5, 102.5, 103),
              candle(1, 104, 104.5, 101, 101.5),
              candle(2, 102.5, 103, 99.5, 100)]
    det = detect_soldiers_crows(series, 2)
    assert det is not None and det.name == "three_black_crows"
    assert det.direction == "bearish"


def test_soldiers_not_detected_when_third_candle_reverses():
    series = [candle(0, 100, 102.5, 99.5, 102),
              candle(1, 101, 104, 100.5, 103.5),
              candle(2, 105, 105.5, 102, 103)]
    assert detect_soldiers_crows(series, 2) is None


def test_tweezer_bottom():
    series = [candle(0, 102, 102.5, 98, 100),
              candle(1, 100, 102.5, 98, 102)]
    det = detect_tweezers(series, 1)
    assert det is not None and det.name == "tweezer_bottom"
    assert det.direction == "bullish"


def test_tweezer_top():
    series = [candle(0, 100, 105, 99.5, 102),
              candle(1, 102, 105, 99.5, 100)]
    det = detect_tweezers(series, 1)
    assert det is not None and det.name == "tweezer_top"
    assert det.direction == "bearish"


def test_tweezers_not_detected_when_extremes_differ():
    series = [candle(0, 102, 102.5, 98, 100),
              candle(1, 100, 102.5, 99, 102)]  # mínima 99 vs 98: diff 1% > 0,1%
    assert detect_tweezers(series, 1) is None


def test_marubozu_bullish():
    series = [candle(0, 100, 104.1, 99.9, 104)]
    det = detect_marubozu(series, 0)
    assert det is not None and det.name == "marubozu_bullish"


def test_marubozu_not_detected_with_long_shadow():
    series = [candle(0, 100, 106, 98, 104)]
    assert detect_marubozu(series, 0) is None


def test_spinning_top():
    series = [candle(0, 100, 102, 98, 100.5)]
    det = detect_spinning_top(series, 0)
    assert det is not None and det.name == "spinning_top"
    assert det.direction == "neutral"


def test_spinning_top_not_detected_with_large_body():
    series = [candle(0, 100, 102, 98, 101.5)]
    assert detect_spinning_top(series, 0) is None


def test_inside_bar():
    series = [candle(0, 100, 105, 95, 102),
              candle(1, 101, 103, 97, 102)]
    det = detect_inside_bar(series, 1)
    assert det is not None and det.name == "inside_bar"


def test_inside_bar_not_detected_when_breaks_out():
    series = [candle(0, 100, 105, 95, 102),
              candle(1, 101, 106, 97, 102)]
    assert detect_inside_bar(series, 1) is None


def test_outside_bar_bullish():
    series = [candle(0, 100, 102, 98, 101),
              candle(1, 99, 104, 96, 103)]
    det = detect_outside_bar(series, 1)
    assert det is not None and det.name == "outside_bar_bullish"


def test_outside_bar_not_detected_when_contained():
    series = [candle(0, 100, 105, 95, 102),
              candle(1, 101, 103, 97, 102)]
    assert detect_outside_bar(series, 1) is None


# --- Orquestração + PAT-006 ---------------------------------------------------

def test_detect_all_finds_engulfing_in_series():
    series = [candle(0, 102, 102.5, 99.5, 100),
              candle(1, 99.5, 103.5, 99, 103)]
    found = detect_all(series)
    assert "bullish_engulfing" in names(found)
    assert all(d.index == 1 for d in found if d.name == "bullish_engulfing")


def test_detect_all_empty_on_neutral_series():
    # Candles de alta monótonos, corpos de 40% do range, aberturas fora
    # do corpo anterior: sem doji, sem sombra longa, sem engolfo/harami,
    # sem inside/outside bar, sem soldiers (abertura fora do corpo).
    series = [
        candle(0, 100, 101.5, 99.5, 100.8),
        candle(1, 101.0, 102.5, 100.5, 101.8),
        candle(2, 102.0, 103.5, 101.5, 102.8),
        candle(3, 103.0, 104.5, 102.5, 103.8),
        candle(4, 104.0, 105.5, 103.5, 104.8),
    ]
    assert detect_all(series) == []


def test_detect_at_out_of_range_returns_empty():
    series = [candle(0, 100, 101, 99, 100.05)]
    assert detect_at(series, 99) == []
    assert detect_at(series, -1) == []


def test_assess_pattern_adds_context_and_never_generates_entry():
    series = downtrend() + [candle(5, 100, 101.5, 97, 101, volume=300)]
    det = detect_hammer(series, 5)
    assert det is not None
    assessed = assess_pattern(det, series)
    assert assessed.generates_entry is False
    assert assessed.requires_confirmation is True
    assert assessed.confirmation  # texto de confirmação presente
    assert assessed.context["trend"] == "bearish"
    assert assessed.context["volume_above_average"] is True
    assert assessed.context["trend_aligned"] is True


def test_assess_pattern_misaligned_trend_flagged():
    # Hanging man (baixa) após tendência de alta: reversão no topo,
    # tendência prévia oposta à direção -> alinhado com a reversão.
    series = uptrend() + [candle(5, 110, 111.5, 107, 111)]
    det = detect_hammer(series, 5)
    assert det is not None and det.name == "hanging_man"
    assessed = assess_pattern(det, series)
    assert assessed.context["trend"] == "bullish"
    assert assessed.context["trend_aligned"] is True
    assert assessed.generates_entry is False
