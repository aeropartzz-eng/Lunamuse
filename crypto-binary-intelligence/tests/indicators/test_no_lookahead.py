"""REGRA DE OURO — sem look-ahead (IND-008) — e casos de borda.

Para cada indicador: calcular sobre a série base, depois alterar apenas
os dados **futuros** (índices >= k) e provar que todos os valores até
``k - 1`` permanecem idênticos. Também cobre séries curtas, NaN, volume
zero, divisão por zero e parâmetros inválidos. Sem rede.
"""

from __future__ import annotations

import numpy as np
import pytest

import indicators as I


def _assert_prefix_unchanged(fn, base, mutated, k):
    before = fn(base)
    after = fn(mutated)
    if isinstance(before, dict):
        for key in before:
            np.testing.assert_allclose(
                before[key][:k], after[key][:k], rtol=0, atol=0, equal_nan=True
            )
    else:
        np.testing.assert_allclose(
            before[:k], after[:k], rtol=0, atol=0, equal_nan=True
        )


def test_no_lookahead_sma_ema_rsi(closes):
    k = 6
    mutated = closes[:k] + [999.0] * (len(closes) - k)
    _assert_prefix_unchanged(lambda c: I.sma(c, 3), closes, mutated, k)
    _assert_prefix_unchanged(lambda c: I.ema(c, 3), closes, mutated, k)
    _assert_prefix_unchanged(lambda c: I.rsi(c, 3), closes, mutated, k)
    _assert_prefix_unchanged(lambda c: I.roc(c, 3), closes, mutated, k)


def test_no_lookahead_ohlc_indicators(ohlc):
    high, low, close = ohlc
    k = 6

    def mutate(series):
        return series[:k] + [999.0] * (len(series) - k)

    m_high, m_low, m_close = mutate(high), mutate(low), mutate(close)
    _assert_prefix_unchanged(
        lambda args: I.atr(*args, 3), (high, low, close), (m_high, m_low, m_close), k
    )
    _assert_prefix_unchanged(
        lambda args: I.bollinger(args[2], 3), (high, low, close), (m_high, m_low, m_close), k
    )
    _assert_prefix_unchanged(
        lambda args: I.macd(args[2], 3, 5, 2), (high, low, close), (m_high, m_low, m_close), k
    )
    _assert_prefix_unchanged(
        lambda args: I.dmi(*args, 3), (high, low, close), (m_high, m_low, m_close), k
    )
    _assert_prefix_unchanged(
        lambda args: I.supertrend(*args, 3, 2.0),
        (high, low, close), (m_high, m_low, m_close), k,
    )


def test_no_lookahead_volume_indicators(ohlc):
    high, low, close = ohlc
    volume = [100, 200, 150, 120, 180, 90, 110, 130, 140, 160]
    k = 6
    m_close = close[:k] + [999.0] * (len(close) - k)
    m_vol = volume[:k] + [99999.0] * (len(volume) - k)
    _assert_prefix_unchanged(
        lambda args: I.vwap(args[0], args[1], args[2], args[3]),
        (high, low, close, volume), (high, low, m_close, m_vol), k,
    )
    _assert_prefix_unchanged(
        lambda args: I.obv(args[0], args[1]),
        (close, volume), (m_close, m_vol), k,
    )
    _assert_prefix_unchanged(
        lambda args: I.mfi(args[0], args[1], args[2], args[3], 3),
        (high, low, close, volume), (high, low, m_close, m_vol), k,
    )


def test_no_lookahead_future_nan_does_not_corrupt_past(closes):
    # Um NaN no futuro não pode alterar o passado nem "vazar" para trás.
    mutated = closes[:6] + [np.nan] + closes[7:]
    before = I.sma(closes, 3)
    after = I.sma(mutated, 3)
    np.testing.assert_allclose(before[:6], after[:6], equal_nan=True)
    # E o NaN só afeta a janela que o contém (idx 6, 7, 8).
    assert np.isnan(after[6])
    assert not np.isnan(after[9])


def test_no_lookahead_divergences():
    close = [10, 9, 8, 9, 10, 7, 8, 9, 10, 11]
    ind = [50, 45, 40, 45, 50, 45, 50, 55, 60, 65]
    base = I.detect_divergences(close, ind, window=1)
    mutated = close[:6] + [100.0] * 4
    after = I.detect_divergences(mutated, ind, window=1)
    # A divergência detectada no idx 5 usa só dados até 5.
    assert base == after


# --- Casos de borda --------------------------------------------------------
def test_short_series_returns_all_nan():
    assert np.isnan(I.sma([10, 11], period=5)).all()
    assert np.isnan(I.rsi([10, 11, 12], period=5)).all()
    assert np.isnan(I.atr([12], [10], [11], period=5)).all()


def test_empty_series_raises():
    with pytest.raises(ValueError):
        I.sma([], period=3)


def test_invalid_period_raises():
    with pytest.raises(ValueError):
        I.sma([10, 11, 12], period=0)
    with pytest.raises(ValueError):
        I.ema([10, 11, 12], period=-1)


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        I.atr([12, 13], [10], [11, 12])
    with pytest.raises(ValueError):
        I.obv([10, 11], [100])


def test_nan_input_does_not_break_series():
    # NaN no meio: SMA invalida só a janela; EMA carrega o último valor.
    out = I.sma([10, 11, np.nan, 13, 14, 15], period=3)
    assert np.isnan(out[2]) and np.isnan(out[3]) and np.isnan(out[4])
    assert out[5] == pytest.approx(14.0)
    ema_out = I.ema([10, 11, 12, np.nan, 14, 15], period=3)
    assert ema_out[3] == pytest.approx(ema_out[2])  # carrega
    assert ema_out[5] > ema_out[3]  # recupera depois


def test_zero_volume_and_zero_price_guards():
    assert np.isnan(I.vwap([12], [10], [11], [0])).all()
    assert np.isnan(I.roc([0, 10, 11], period=1)[1])  # preço anterior 0
    assert np.isnan(I.log_returns([10, 0])[1])


def test_nan_close_keeps_rsi_bounded():
    out = I.rsi([10, 11, np.nan, 13, 14, 15, 16], period=3)
    valid = out[~np.isnan(out)]
    assert ((valid >= 0) & (valid <= 100)).all()
