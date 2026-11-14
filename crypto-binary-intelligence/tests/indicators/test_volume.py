"""Volume — IND-005: VWAP, Anchored VWAP, OBV, Volume Profile, MFI, CVD.

Valores esperados calculados à mão (preço típico, fluxos e somas).
"""

from __future__ import annotations

import numpy as np
import pytest

import indicators as I

H = [12, 13, 14]
L = [10, 11, 12]
C = [11, 12, 13]
V = [100, 200, 100]


def test_vwap_known_values():
    # TP 11/12/13: cum 1100/100=11; 3500/300=11.6667; 4800/400=12.
    out = I.vwap(H, L, C, V)
    np.testing.assert_allclose(out, [11, 11.6667, 12], rtol=1e-4)


def test_vwap_session_reset():
    out = I.vwap(
        [12, 13, 14, 15], [10, 11, 12, 13], [11, 12, 13, 14],
        [100, 100, 100, 100], session_start=[True, False, True, False],
    )
    # Sessão 2 recomeça no idx2: TP 13 -> 13; depois (1300+1400)/200 = 13.5
    np.testing.assert_allclose(out, [11, 11.5, 13, 13.5])


def test_vwap_zero_volume_is_nan():
    out = I.vwap(H, L, C, [0, 0, 0])
    assert np.isnan(out).all()


def test_anchored_vwap_known_values():
    high = [12, 13, 14, 15, 16]
    low = [10, 11, 12, 13, 14]
    close = [11, 12, 13, 14, 15]
    out = I.anchored_vwap(high, low, close, [100, 200, 100, 50, 50], anchor_index=1)
    assert np.isnan(out[0])
    np.testing.assert_allclose(out[1:], [12, 12.3333, 12.5714, 12.875], rtol=1e-4)


def test_anchored_vwap_bad_anchor_raises():
    with pytest.raises(ValueError):
        I.anchored_vwap(H, L, C, V, anchor_index=99)


def test_obv_known_values():
    # closes 10,11,12,11 vols 100,200,100,50 -> 100, 300, 400, 350
    out = I.obv([10, 11, 12, 11], [100, 200, 100, 50])
    np.testing.assert_allclose(out, [100, 300, 400, 350])


def test_obv_flat_close_keeps_value():
    out = I.obv([10, 10, 10], [100, 200, 300])
    np.testing.assert_allclose(out, [100, 100, 100])


def test_volume_profile_known_values():
    out = I.volume_profile(H, L, C, V, bins=3, value_area_pct=0.70)
    # Faixas [10,11.33),[11.33,12.67),[12.67,14]: vols 100/200/100.
    assert out["poc"] == pytest.approx(12.0)
    assert out["total_volume"] == pytest.approx(400.0)
    np.testing.assert_allclose(out["bin_volumes"], [100, 200, 100])
    # Value area 70% (280): POC 200 + vizinho maior (empate -> p/ cima) = 300.
    assert out["value_area_low"] == pytest.approx(11.3333, rel=1e-4)
    assert out["value_area_high"] == pytest.approx(14.0)


def test_volume_profile_zero_volume():
    out = I.volume_profile(H, L, C, [0, 0, 0], bins=3)
    assert np.isnan(out["poc"])
    assert out["total_volume"] == pytest.approx(0.0)


def test_mfi_known_value():
    # TP 11,12,13,12.3333; fluxos 1100,1200,1300,1233.33 (período 3):
    # positivo 2500, negativo 1233.33 -> MFI = 100 - 100/3.0270 = 66.9643
    out = I.mfi(
        [12, 13, 14, 13], [10, 11, 12, 12], [11, 12, 13, 12],
        [100, 100, 100, 100], period=3,
    )
    assert np.isnan(out[:3]).all()
    assert out[3] == pytest.approx(66.9643, rel=1e-4)


def test_mfi_only_up_is_100():
    out = I.mfi([12, 13, 14, 15], [10, 11, 12, 13], [11, 12, 13, 14],
                [100, 100, 100, 100], period=3)
    assert out[3] == pytest.approx(100.0)


def test_cvd_from_open_known_values():
    # Sinal de close-open: +,+,+,- com vols 100,200,100,50 -> 100,300,400,350
    out = I.cvd([10, 11, 12, 11], [100, 200, 100, 50], open_=[9, 10, 11, 12])
    np.testing.assert_allclose(out, [100, 300, 400, 350])


def test_cvd_from_trade_side():
    # Lado do agressor: +1,-1,+1,+1 com vols 100 -> 100, 0, 100, 200
    out = I.cvd([10, 11, 12, 13], [100, 100, 100, 100], side=[1, -1, 1, 1])
    np.testing.assert_allclose(out, [100, 0, 100, 200])
