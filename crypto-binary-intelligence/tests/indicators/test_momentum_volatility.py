"""Momentum e volatilidade — IND-002/004: RSI, Stochastic, Stochastic RSI,
ROC, CCI, ATR, Bollinger, Keltner, Historical Volatility.

Valores esperados calculados à mão (Wilder, definições clássicas).
"""

from __future__ import annotations

import numpy as np
import pytest

import indicators as I


# --- RSI -----------------------------------------------------------------
def test_rsi_known_values():
    # Wilder, período 3, closes [10,11,12,11,10,9]:
    # idx3: avg_gain 2/3, avg_loss 1/3 -> 66.6667
    # idx4: RS 0.8 -> 44.4444 ; idx5: RS 8/19 -> 29.6296
    out = I.rsi([10, 11, 12, 11, 10, 9], period=3)
    assert np.isnan(out[:3]).all()
    np.testing.assert_allclose(out[3:], [66.6667, 44.4444, 29.6296], rtol=1e-4)


def test_rsi_extended_series():
    out = I.rsi([10, 11, 12, 11, 10, 9, 10, 11, 12, 13], period=3)
    np.testing.assert_allclose(
        out[3:], [66.6667, 44.4444, 29.6296, 53.0864, 68.7243, 79.1495, 86.0997],
        rtol=1e-4,
    )


def test_rsi_all_up_is_100_all_down_is_0():
    assert I.rsi([10, 11, 12, 13, 14, 15], period=3)[-1] == pytest.approx(100.0)
    assert I.rsi([15, 14, 13, 12, 11, 10], period=3)[-1] == pytest.approx(0.0)


def test_rsi_flat_series_is_50():
    out = I.rsi([10.0] * 10, period=3)
    np.testing.assert_allclose(out[3:], 50.0)


def test_rsi_bounds():
    out = I.rsi([10, 12, 9, 14, 8, 15, 7, 16, 6, 17, 5, 18], period=3)
    valid = out[~np.isnan(out)]
    assert ((valid >= 0) & (valid <= 100)).all()


# --- Stochastic ----------------------------------------------------------
def test_stochastic_known_values():
    out = I.stochastic([12, 13, 14], [10, 11, 12], [11, 12, 13], k_period=3, d_period=3)
    # Janela idx2: HH=14, LL=10, C=13 -> %K = 75.
    assert np.isnan(out["k"][:2]).all()
    assert out["k"][2] == pytest.approx(75.0)
    # %D precisa de 3 valores de %K: ainda NaN.
    assert np.isnan(out["d"]).all()


def test_stochastic_d_is_sma_of_k():
    out = I.stochastic(
        [12, 13, 14, 15, 16], [10, 11, 12, 13, 14], [11, 12, 13, 14, 15],
        k_period=3, d_period=3,
    )
    np.testing.assert_allclose(out["d"], I.sma(out["k"], 3), equal_nan=True)


def test_stochastic_flat_range_is_nan():
    # HH == LL -> divisão por zero vira NaN, não erro.
    out = I.stochastic([10, 10, 10], [10, 10, 10], [10, 10, 10], k_period=3)
    assert np.isnan(out["k"]).all()


def test_stochastic_rsi_known_values():
    out = I.stochastic_rsi(
        [10, 11, 12, 11, 10, 9, 10, 11, 12, 13],
        rsi_period=3, stoch_period=3, k_period=3, d_period=3,
    )
    # RSI bruto 0/100/100... -> %K idx7 = (0+100+100)/3 = 66.6667; idx8/9 = 100.
    assert out["k"][7] == pytest.approx(66.6667, rel=1e-4)
    assert out["k"][8] == pytest.approx(100.0)
    assert out["k"][9] == pytest.approx(100.0)
    assert out["d"][9] == pytest.approx(88.8889, rel=1e-4)


# --- ROC / CCI -----------------------------------------------------------
def test_roc_known_value():
    out = I.roc([10, 11, 12, 13], period=3)
    assert np.isnan(out[:3]).all()
    assert out[3] == pytest.approx(30.0)  # (13-10)/10 * 100


def test_cci_known_value():
    # TP [11,12,13], média 12, desvio médio 2/3 -> CCI = 100 no idx2.
    out = I.cci([12, 13, 14], [10, 11, 12], [11, 12, 13], period=3)
    assert np.isnan(out[:2]).all()
    assert out[2] == pytest.approx(100.0)


def test_cci_flat_series_is_nan():
    out = I.cci([11, 11, 11], [11, 11, 11], [11, 11, 11], period=3)
    assert np.isnan(out).all()  # desvio médio 0 -> NaN, não erro


# --- ATR -----------------------------------------------------------------
def test_atr_known_values():
    high = [12, 13, 15, 14]
    low = [10, 11, 12, 13]
    close = [11, 12, 14, 13]
    out = I.atr(high, low, close, period=3)
    # TR: 2, 2, 3 -> semente 7/3 = 2.3333; TR4 = 1 -> (2.3333*2+1)/3 = 1.8889
    assert np.isnan(out[:2]).all()
    assert out[2] == pytest.approx(2.3333, rel=1e-4)
    assert out[3] == pytest.approx(1.8889, rel=1e-4)


def test_atr_constant_range():
    out = I.atr([12] * 6, [10] * 6, [11] * 6, period=3)
    np.testing.assert_allclose(out[2:], 2.0)


# --- Bollinger -----------------------------------------------------------
def test_bollinger_known_values():
    out = I.bollinger([10, 11, 12, 13, 14], period=3, std_dev=2.0)
    # Janela [10,11,12]: média 11, desvio pop sqrt(2/3)=0.8165
    assert np.isnan(out["middle"][:2]).all()
    assert out["middle"][2] == pytest.approx(11.0)
    assert out["upper"][2] == pytest.approx(12.6330, rel=1e-4)
    assert out["lower"][2] == pytest.approx(9.3670, rel=1e-4)
    assert out["middle"][4] == pytest.approx(13.0)
    assert out["upper"][4] == pytest.approx(14.6330, rel=1e-4)
    # %B do close 12 na janela [10,11,12]: (12-9.367)/(12.633-9.367)
    assert out["percent_b"][2] == pytest.approx(0.8062, rel=1e-4)
    assert out["bandwidth"][2] == pytest.approx(0.2969, rel=1e-4)


def test_bollinger_bands_symmetric_around_middle():
    out = I.bollinger([10, 11, 12, 13, 14, 15, 16], period=3, std_dev=2.0)
    mid = out["middle"][2:]
    np.testing.assert_allclose(out["upper"][2:] - mid, mid - out["lower"][2:])


# --- Keltner -------------------------------------------------------------
def test_keltner_known_values():
    high = [12, 13, 14, 15, 16]
    low = [10, 11, 12, 13, 14]
    close = [11, 12, 13, 14, 15]
    out = I.keltner(high, low, close, period=3, atr_period=2, multiplier=2.0)
    # TP = close; EMA3(TP) idx2 = 12; ATR2 = 2 -> bandas 16/12/8.
    assert np.isnan(out["middle"][:2]).all()
    np.testing.assert_allclose(out["middle"][2:], [12, 13, 14])
    np.testing.assert_allclose(out["upper"][2:], [16, 17, 18])
    np.testing.assert_allclose(out["lower"][2:], [8, 9, 10])


# --- Historical volatility -----------------------------------------------
def test_historical_volatility_known_value():
    # Retornos log de [10,11,12,13]; desvio pop * sqrt(365) = 0.11923.
    out = I.historical_volatility([10, 11, 12, 13], window=3, annualization=365.0)
    assert np.isnan(out[:3]).all()
    assert out[3] == pytest.approx(0.11923, rel=1e-4)


def test_historical_volatility_flat_is_zero():
    out = I.historical_volatility([10.0] * 10, window=3)
    np.testing.assert_allclose(out[3:], 0.0)
