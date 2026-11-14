"""Divergências (IND-006), features derivadas (IND-007) e integração com
candles (:func:`candles_to_arrays`, :func:`compute_all`).
"""

from __future__ import annotations

import numpy as np
import pytest

import indicators as I


# --- Swings ---------------------------------------------------------------
def test_find_swings():
    out = I.find_swings([10, 9, 8, 9, 10, 7, 8, 9], window=1)
    assert out["lows"] == [2, 5]
    assert out["highs"] == [4]


def test_find_swings_ignores_nan_window():
    out = I.find_swings([10, np.nan, 8, 9, 10], window=1)
    assert out["lows"] == [] and out["highs"] == []


# --- Divergências ---------------------------------------------------------
def test_divergence_regular_bullish():
    # Preço: fundo 8 -> 7 (mais baixo); indicador: fundo 40 -> 45 (mais alto).
    out = I.detect_divergences(
        [10, 9, 8, 9, 10, 7, 8, 9], [50, 45, 40, 45, 50, 45, 50, 55], window=1
    )
    assert len(out) == 1
    assert out[0]["type"] == "regular_bullish"
    assert out[0]["price_index"] == 5
    assert out[0]["price_value"] == pytest.approx(7.0)
    assert out[0]["indicator_value"] == pytest.approx(45.0)


def test_divergence_regular_bearish():
    # Preço: topo 12 -> 13 (mais alto); indicador: topo 60 -> 58 (mais baixo).
    out = I.detect_divergences(
        [10, 11, 12, 11, 10, 11, 13, 12], [50, 55, 60, 55, 50, 55, 58, 50], window=1
    )
    assert [d["type"] for d in out] == ["regular_bearish"]
    assert out[0]["price_index"] == 6


def test_divergence_hidden_bullish():
    # Preço: fundo 8 -> 9 (mais alto); indicador: fundo 40 -> 38 (mais baixo).
    out = I.detect_divergences(
        [10, 9, 8, 9, 10, 9, 10, 11], [50, 45, 40, 45, 50, 38, 45, 55], window=1
    )
    assert [d["type"] for d in out] == ["hidden_bullish"]
    assert out[0]["price_index"] == 5


def test_divergence_hidden_bearish():
    # Preço: topo 12 -> 11.5 (mais baixo); indicador: topo 60 -> 62 (mais alto).
    out = I.detect_divergences(
        [10, 11, 12, 11, 10, 11, 11.5, 10], [50, 55, 60, 55, 50, 55, 62, 55], window=1
    )
    assert [d["type"] for d in out] == ["hidden_bearish"]
    assert out[0]["price_index"] == 6


def test_divergence_none_when_aligned():
    out = I.detect_divergences(
        [10, 9, 8, 9, 10, 7, 8, 9], [50, 45, 40, 45, 50, 35, 40, 45], window=1
    )
    assert out == []  # indicador acompanha o preço: sem divergência


# --- Features (IND-007) ----------------------------------------------------
def test_log_returns_known_value():
    out = I.log_returns([10, 11])
    assert np.isnan(out[0])
    assert out[1] == pytest.approx(0.0953102, rel=1e-6)  # ln(1.1)


def test_distance_from_ma_known_value():
    # SMA3 de [10,11,12] = 11; distância do close 12 = 100*1/11 = 9.0909%.
    out = I.distance_from_ma([10, 11, 12], period=3)
    assert np.isnan(out[:2]).all()
    assert out[2] == pytest.approx(9.0909, rel=1e-4)


def test_zscore_known_value():
    # Janela [10,11,12]: média 11, desvio pop 0.8165 -> z(12) = 1.2247.
    out = I.zscore([10, 11, 12, 13, 14], window=3)
    assert np.isnan(out[:2]).all()
    assert out[2] == pytest.approx(1.2247, rel=1e-4)
    assert out[4] == pytest.approx(1.2247, rel=1e-4)


def test_zscore_volume_and_ratio():
    feats = I.compute_features([10, 11, 12, 13], volume=[100, 200, 300, 400], window=3)
    assert feats["zscore_volume_3"][2] == pytest.approx(1.2247, rel=1e-4)
    # volume_ratio idx2 = 300 / SMA3(100,200,300)=200 -> 1.5
    assert feats["volume_ratio"][2] == pytest.approx(1.5)
    assert "log_return" in feats and "realized_vol_3" in feats
    assert "dist_sma_3" in feats and "dist_ema_3" in feats


def test_compute_features_keys():
    feats = I.compute_features([10, 11, 12, 13, 14], window=3)
    assert set(feats) == {
        "log_return", "realized_vol_3", "dist_sma_3", "dist_ema_3", "zscore_close_3",
    }


# --- Integração com candles ------------------------------------------------
def test_candles_to_arrays(candle_factory):
    candles = candle_factory([10, 11, 12], volumes=[100, 200, 300])
    data = I.candles_to_arrays(candles)
    np.testing.assert_allclose(data["close"], [10, 11, 12])
    np.testing.assert_allclose(data["volume"], [100, 200, 300])
    assert data["open"][0] == pytest.approx(10.0)
    assert data["high"][1] == pytest.approx(11.5)
    assert len(data["open_time_ms"]) == 3


def test_candles_to_arrays_empty_raises():
    with pytest.raises(ValueError):
        I.candles_to_arrays([])


def test_compute_all_runs_on_candles(candle_factory):
    closes = list(range(10, 50))  # 40 candles: warm-up suficiente p/ período 20
    result = I.compute_all(candle_factory(closes))
    assert len(result["sma_20"]) == 40
    assert len(result["rsi_14"]) == 40
    assert len(result["vwap"]) == 40
    assert len(result["obv"]) == 40
    assert result["macd"]["macd"][-1] > 0  # tendência de alta
    assert result["volume_profile"]["total_volume"] == pytest.approx(40 * 100)
    assert isinstance(result["divergences_rsi"], list)
    assert set(result["features"]) >= {"log_return", "zscore_close_20"}
