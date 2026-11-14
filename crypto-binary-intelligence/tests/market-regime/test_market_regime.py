"""Testes do Market Regime Engine — Fase 11 (REG-001…REG-005).

Séries sintéticas com regime conhecido; sem rede.
"""

from __future__ import annotations

import math

import pytest

from market_regime import (
    COMPRESSION,
    EXPANSION,
    RANGE,
    TRANSITION,
    TREND_DOWN,
    TREND_UP,
    RegimeTracker,
    detect_regime,
    detect_regime_changes,
    classify_series,
)


def trend_up_closes(n=80, start=100.0, step=0.004):
    return [start * (1 + step) ** i for i in range(n)]


def trend_down_closes(n=80, start=100.0, step=0.004):
    return [start * (1 - step) ** i for i in range(n)]


def range_closes(n=80):
    return [100 + 2 * math.sin(i * 2 * math.pi / 20) for i in range(n)]


def compression_closes(n=80):
    # Amplitude decrescente: 3,3 -> 0,3 ao longo da série.
    return [100 + (3 * (1 - i / n) + 0.3) * math.sin(i * 2 * math.pi / 20)
            for i in range(n)]


def expansion_closes():
    closes = [100 + 0.5 * math.sin(i * 2 * math.pi / 20) for i in range(60)]
    price = closes[-1]
    for _ in range(10):
        price *= 1.03
        closes.append(price)
    return closes


# --- REG-001: tendência -------------------------------------------------------

def test_trend_up(candle_factory):
    regime = detect_regime(candle_factory(trend_up_closes()))
    assert regime.label == TREND_UP
    assert 0.5 <= regime.confidence <= 1.0
    assert "ADX" in regime.reason
    assert regime.features["adx_effective"] >= 25


def test_trend_down(candle_factory):
    regime = detect_regime(candle_factory(trend_down_closes()))
    assert regime.label == TREND_DOWN
    assert regime.features["ema_20"] < regime.features["ema_50"]


def test_trend_reason_has_numbers(candle_factory):
    regime = detect_regime(candle_factory(trend_up_closes()))
    assert regime.features["close"] is not None
    assert regime.features["ema_slope_pct"] > 0


# --- REG-002: lateralização ---------------------------------------------------

def test_range(candle_factory):
    regime = detect_regime(candle_factory(range_closes()))
    assert regime.label == RANGE
    assert regime.features["efficiency_20"] <= 0.35


def test_flat_series_is_not_trend(candle_factory):
    regime = detect_regime(candle_factory([100.0] * 60))
    assert regime.label in (RANGE, TRANSITION, COMPRESSION)
    assert regime.label != TREND_UP


# --- REG-003/REG-004: compressão e expansão ------------------------------------

def test_compression(candle_factory):
    regime = detect_regime(candle_factory(compression_closes()))
    assert regime.label == COMPRESSION
    assert regime.features["bb_bandwidth_ratio"] <= 0.65


def test_expansion_after_compression(candle_factory):
    closes = expansion_closes()
    regime = detect_regime(candle_factory(closes))
    assert regime.label == EXPANSION
    assert regime.features["atr_ratio"] >= 1.40


def test_compression_then_expansion_change_is_detected(candle_factory):
    closes = expansion_closes()
    # A série começa comprimida (amplitude 0,5) e termina em expansão.
    series = classify_series(candle_factory(closes))
    assert series[0].label in (COMPRESSION, RANGE, TRANSITION)
    assert series[-1].label == EXPANSION
    changes = detect_regime_changes(candle_factory(closes))
    assert changes, "esperava ao menos uma mudança de regime confirmada"
    assert changes[-1]["to"] == EXPANSION
    assert changes[-1]["from"] != EXPANSION


# --- REG-005: mudança de regime com persistência -------------------------------

def test_tracker_does_not_flip_on_one_candle(candle_factory):
    tracker = RegimeTracker(min_persistence=3)
    trend = candle_factory(trend_up_closes())
    assert tracker.update(trend).label == TREND_UP
    # Troca brusca para uma série lateral: o rótulo bruto muda, mas o
    # confirmado só vira depois de 3 classificações consecutivas.
    sideways = candle_factory(range_closes())
    assert tracker.update(sideways).label == TREND_UP  # 1ª: pendente
    assert tracker.update(sideways).label == TREND_UP  # 2ª: pendente
    assert tracker.update(sideways).label == RANGE     # 3ª: confirmado
    assert len(tracker.history) == 1
    assert tracker.history[0]["from"] == TREND_UP
    assert tracker.history[0]["to"] == RANGE


def test_tracker_observe_persistence_directly():
    tracker = RegimeTracker(min_persistence=2)
    from market_regime import Regime
    r_up = Regime(label=TREND_UP, confidence=0.8, reason="t", index=0)
    r_range = Regime(label=RANGE, confidence=0.7, reason="r", index=1)
    assert tracker.observe(r_up).label == TREND_UP
    assert tracker.observe(r_range).label == TREND_UP  # pendente
    assert tracker.observe(r_range).label == RANGE     # confirmado
    assert tracker.history[0]["from"] == TREND_UP
    assert tracker.history[0]["to"] == RANGE


def test_tracker_single_candle_noise_does_not_confirm(candle_factory):
    tracker = RegimeTracker(min_persistence=3)
    from market_regime import Regime
    base = Regime(label=TREND_UP, confidence=0.8, reason="t", index=0)
    noise = Regime(label=RANGE, confidence=0.6, reason="r", index=1)
    tracker.observe(base)
    assert tracker.observe(noise).label == TREND_UP
    # Volta ao regime original antes de persistir: o pendente é descartado.
    assert tracker.observe(base).label == TREND_UP
    assert tracker.history == []


def test_classify_series_has_no_lookahead(candle_factory):
    closes = trend_up_closes()
    series = classify_series(candle_factory(closes))
    assert len(series) == len(closes) - 49  # warm-up de 50 candles
    assert series[-1].label == TREND_UP
    assert all(r.index >= 49 for r in series)


def test_insufficient_candles_raises(candle_factory):
    with pytest.raises(ValueError, match="ao menos 50"):
        detect_regime(candle_factory([100.0] * 20))


def test_invalid_persistence_raises():
    with pytest.raises(ValueError):
        RegimeTracker(min_persistence=0)


def test_regime_labels_are_known(candle_factory):
    from market_regime import REGIMES
    regime = detect_regime(candle_factory(range_closes()))
    assert regime.label in REGIMES
