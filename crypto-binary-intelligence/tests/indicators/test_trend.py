"""Tendência — IND-001/003: SMA, EMA, MACD, DMI/ADX, Supertrend.

Valores esperados calculados à mão (verificação aritmética independente
em /tmp/refcalc.py e /tmp/ref2.py) — não apenas "não quebrou".
"""

from __future__ import annotations

import numpy as np
import pytest

import indicators as I


def test_sma_known_values(closes):
    out = I.sma(closes, 3)
    assert np.isnan(out[:2]).all()
    np.testing.assert_allclose(
        out[2:], [11, 12, 13, 14, 14.3333, 14, 13, 12], rtol=1e-4
    )


def test_sma_period_1_is_identity(closes):
    np.testing.assert_allclose(I.sma(closes, 1), closes)


def test_ema_known_values(closes):
    # EMA3 semeada com a SMA dos 3 primeiros (11.0); k = 0.5.
    out = I.ema(closes, 3)
    assert np.isnan(out[:2]).all()
    np.testing.assert_allclose(
        out[2:], [11, 12, 13, 14, 14, 13.5, 12.75, 11.875], rtol=1e-9
    )


def test_ema_reacts_faster_than_sma(closes):
    # Após a reversão (15 -> 11), a EMA cai mais rápido que a SMA.
    assert I.ema(closes, 3)[-1] < I.sma(closes, 3)[-1]


def test_macd_known_values_linear_series():
    closes = [10 + i for i in range(10)]
    out = I.macd(closes, fast=3, slow=5, signal=2)
    # Em série linear, EMA3 - EMA5 estabiliza em 1.0 a partir do idx 4.
    assert np.isnan(out["macd"][:4]).all()
    np.testing.assert_allclose(out["macd"][4:], 1.0, rtol=1e-9)
    # Sinal = EMA2 da linha, semeado em idx 5; histograma zera.
    assert np.isnan(out["signal"][:5]).all()
    np.testing.assert_allclose(out["signal"][5:], 1.0, rtol=1e-9)
    np.testing.assert_allclose(out["histogram"][5:], 0.0, atol=1e-12)


def test_macd_flat_series_is_zero():
    out = I.macd([10.0] * 40)
    assert np.isnan(out["macd"][:25]).all()
    np.testing.assert_allclose(out["macd"][25:], 0.0, atol=1e-12)
    # Sinal = EMA9 da linha: válido a partir do idx 33.
    assert np.isnan(out["signal"][:33]).all()
    np.testing.assert_allclose(out["signal"][33:], 0.0, atol=1e-12)
    np.testing.assert_allclose(out["histogram"][33:], 0.0, atol=1e-12)


def test_macd_equals_ema_difference(closes):
    out = I.macd(closes, fast=3, slow=5, signal=2)
    expected = I.ema(closes, 3) - I.ema(closes, 5)
    np.testing.assert_allclose(out["macd"], expected, rtol=1e-12, equal_nan=True)


def test_dmi_adx_strong_uptrend():
    # +DM = 1 por candle, -DM = 0, TR = 2  =>  +DI = 50, -DI = 0, DX = ADX = 100.
    n = 30
    high = [12 + i for i in range(n)]
    low = [10 + i for i in range(n)]
    close = [11 + i for i in range(n)]
    out = I.dmi(high, low, close, period=3)
    # +DI converge a 50 (a semente de Wilder inclui o DM=0 do 1º candle).
    assert out["plus_di"][-1] == pytest.approx(50.0, rel=1e-3)
    assert out["minus_di"][-1] == pytest.approx(0.0, abs=1e-9)
    assert out["dx"][-1] == pytest.approx(100.0)
    assert out["adx"][-1] == pytest.approx(100.0)


def test_adx_flat_series_is_nan_or_zero():
    # Sem movimento direcional, DX = 0/0 -> NaN; ADX não inventa tendência.
    out = I.adx([11.0] * 30, [11.0] * 30, [11.0] * 30, period=3)
    assert np.isnan(out).all()


def test_supertrend_known_values():
    high = [12, 13, 14, 15, 16]
    low = [10, 11, 12, 13, 14]
    close = [11, 12, 13, 14, 15]
    out = I.supertrend(high, low, close, period=2, multiplier=1.0)
    # ATR = 2 constante; bandas 14/10 -> 15/11 -> ...; cruzamento p/ cima no idx 4.
    assert np.isnan(out["supertrend"][0])
    np.testing.assert_allclose(out["supertrend"][1:], [14, 14, 14, 13])
    np.testing.assert_allclose(out["direction"][1:], [-1, -1, -1, 1])


def test_supertrend_downtrend_stays_bearish():
    high = [16, 15, 14, 13, 12]
    low = [14, 13, 12, 11, 10]
    close = [15, 14, 13, 12, 11]
    out = I.supertrend(high, low, close, period=2, multiplier=1.0)
    assert (out["direction"][1:] == -1).all()
