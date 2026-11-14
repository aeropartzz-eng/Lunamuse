"""Indicator Engine — Fase 9 (IND-001…IND-008), especificação v4.1 §6.

Cálculo de indicadores técnicos sobre séries OHLCV, **sem look-ahead**:
o valor do indicador no índice ``i`` só usa dados até ``i`` (IND-008).
Nenhuma função aqui acessa rede, credenciais ou envia ordens — é só
cálculo sobre séries.

Implementação com **NumPy puro** (sem TA-Lib): TA-Lib não está instalado
neste ambiente e exigiria compilação nativa; NumPy já faz parte do stack
do projeto (§8) e é suficiente para todos os indicadores abaixo, com
fórmulas explícitas e auditáveis neste arquivo.

Convenções
-----------
- Entradas: arrays 1-D (listas, ``np.ndarray`` ou séries pandas são
  aceites e convertidas para ``np.ndarray`` float64).
- Saídas: ``np.ndarray`` float64 do mesmo comprimento da entrada;
  posições sem dados suficientes para o período são ``NaN``
  (warm-up). Funções com várias saídas devolvem ``dict`` de arrays.
- Desvio-padrão: populacional (``ddof=0``), padrão de Bollinger/TA-Lib.
- EMA: semeada com a SMA dos ``period`` primeiros valores no índice
  ``period - 1``; a partir daí ``EMA[i] = k*x[i] + (1-k)*EMA[i-1]``,
  com ``k = 2 / (period + 1)``.
- Suavização de Wilder (RSI, ATR, ADX/DMI): primeira média = média
  simples dos ``period`` primeiros valores; depois
  ``avg[i] = (avg[i-1] * (period - 1) + x[i]) / period``.
- Valores ausentes (``NaN``): janelas móveis (SMA, Bollinger, ATR
  inicial etc.) devolvem ``NaN`` se a janela contiver ``NaN``;
  suavizadores recursivos (EMA, RSI, ATR, ADX) **pulam** o ``NaN``
  e carregam o último valor — o ``NaN`` nunca contamina o futuro,
  apenas a própria posição.
- Volume zero / divisão por zero: nunca levanta; o resultado é
  ``NaN`` (ex.: MFI sem fluxo, %K com máxima == mínima, ROC com
  preço anterior 0).

Funções por tarefa
------------------
- IND-001/003 (tendência): :func:`sma`, :func:`ema`, :func:`macd`,
  :func:`dmi`, :func:`adx`, :func:`supertrend`.
- IND-002 (momentum): :func:`rsi`, :func:`stochastic`,
  :func:`stochastic_rsi`, :func:`roc`, :func:`cci`.
- IND-004 (volatilidade): :func:`atr`, :func:`bollinger`,
  :func:`keltner`, :func:`historical_volatility` /
  :func:`realized_volatility`.
- IND-005 (volume): :func:`vwap`, :func:`anchored_vwap`, :func:`obv`,
  :func:`volume_profile`, :func:`mfi`, :func:`cvd`.
- IND-006 (divergências): :func:`find_swings`, :func:`detect_divergences`.
- IND-007 (features p/ Fase 13): :func:`log_returns`,
  :func:`realized_volatility`, :func:`distance_from_ma`,
  :func:`zscore`, :func:`zscore_volume`, :func:`compute_features`.
- Utilidades: :func:`candles_to_arrays`, :func:`compute_all`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np

__all__ = [
    "sma",
    "ema",
    "macd",
    "dmi",
    "adx",
    "supertrend",
    "rsi",
    "stochastic",
    "stochastic_rsi",
    "roc",
    "cci",
    "atr",
    "bollinger",
    "keltner",
    "historical_volatility",
    "realized_volatility",
    "vwap",
    "anchored_vwap",
    "obv",
    "volume_profile",
    "mfi",
    "cvd",
    "find_swings",
    "detect_divergences",
    "log_returns",
    "distance_from_ma",
    "zscore",
    "zscore_volume",
    "compute_features",
    "candles_to_arrays",
    "compute_all",
]

ArrayLike = Union[Sequence[float], np.ndarray]

# Parâmetros padrão (os mesmos usados por TA-Lib/TradingView quando há
# convenção; documentados também no README do serviço).
DEFAULTS = {
    "sma_period": 20,
    "ema_period": 20,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "adx_period": 14,
    "supertrend_period": 10,
    "supertrend_multiplier": 3.0,
    "rsi_period": 14,
    "stoch_k_period": 14,
    "stoch_d_period": 3,
    "stoch_rsi_period": 14,
    "roc_period": 12,
    "cci_period": 20,
    "atr_period": 14,
    "bollinger_period": 20,
    "bollinger_std": 2.0,
    "keltner_period": 20,
    "keltner_atr_period": 10,
    "keltner_multiplier": 2.0,
    "hv_window": 20,
    "hv_annualization": 365.0,  # cripto negocia 24/7
    "mfi_period": 14,
    "feature_window": 20,
}


# ----------------------------------------------------------------------
# Utilidades internas
# ----------------------------------------------------------------------
def _as_array(values: ArrayLike, name: str) -> np.ndarray:
    """Converte a entrada para ``np.ndarray`` float64 1-D."""
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} deve ser uma série 1-D, recebido ndim={arr.ndim}")
    if arr.size == 0:
        raise ValueError(f"{name} não pode ser vazia")
    return arr


def _check_period(period: int, name: str = "period") -> int:
    if isinstance(period, bool) or not isinstance(period, (int, np.integer)):
        raise ValueError(f"{name} deve ser inteiro, recebido {period!r}")
    if int(period) < 1:
        raise ValueError(f"{name} deve ser >= 1, recebido {period}")
    return int(period)


def _nan_out(n: int) -> np.ndarray:
    return np.full(n, np.nan, dtype=float)


def _rolling_mean(values: np.ndarray, period: int) -> np.ndarray:
    """Média móvel simples; janela com NaN devolve NaN (sem look-ahead)."""
    n = len(values)
    out = _nan_out(n)
    if n < period:
        return out
    # Soma cumulativa tratando NaN como "janela inválida": conta NaNs.
    valid = ~np.isnan(values)
    filled = np.where(valid, values, 0.0)
    csum = np.concatenate([[0.0], np.cumsum(filled)])
    cnan = np.concatenate([[0], np.cumsum((~valid).astype(int))])
    sums = csum[period:] - csum[:-period]
    nans = cnan[period:] - cnan[:-period]
    means = sums / period
    means = np.where(nans == 0, means, np.nan)
    out[period - 1:] = means
    return out


def _rolling_std(values: np.ndarray, period: int) -> np.ndarray:
    """Desvio-padrão populacional (ddof=0) em janela móvel."""
    n = len(values)
    out = _nan_out(n)
    if n < period:
        return out
    mean = _rolling_mean(values, period)
    sq = np.where(np.isnan(values), 0.0, values * values)
    valid = ~np.isnan(values)
    csum = np.concatenate([[0.0], np.cumsum(sq)])
    cnan = np.concatenate([[0], np.cumsum((~valid).astype(int))])
    sums = csum[period:] - csum[:-period]
    nans = cnan[period:] - cnan[:-period]
    var = sums / period - mean[period - 1:] ** 2
    var = np.where(nans == 0, np.maximum(var, 0.0), np.nan)
    out[period - 1:] = np.sqrt(var)
    return out


def _wilder_smooth(values: np.ndarray, period: int) -> np.ndarray:
    """Suavização de Wilder; NaN pula a atualização (carrega o último)."""
    n = len(values)
    out = _nan_out(n)
    if n < period:
        return out
    window = values[:period]
    if np.isnan(window).any():
        # Primeira média inválida: procura a primeira janela limpa.
        for start in range(1, n - period + 1):
            w = values[start:start + period]
            if not np.isnan(w).any():
                out[start + period - 1] = float(np.mean(w))
                last = float(np.mean(w))
                idx = start + period
                break
        else:
            return out
    else:
        last = float(np.mean(window))
        out[period - 1] = last
        idx = period
    for i in range(idx, n):
        if np.isnan(values[i]):
            out[i] = last
            continue
        last = (last * (period - 1) + values[i]) / period
        out[i] = last
    return out


def _ema_from_seed(values: np.ndarray, period: int) -> np.ndarray:
    """EMA semeada com a SMA; NaN pula a atualização (carrega o último)."""
    n = len(values)
    out = _nan_out(n)
    if n < period:
        return out
    k = 2.0 / (period + 1)
    seed_idx: Optional[int] = None
    for start in range(0, n - period + 1):
        w = values[start:start + period]
        if not np.isnan(w).any():
            seed_idx = start + period - 1
            last = float(np.mean(w))
            out[seed_idx] = last
            break
    if seed_idx is None:
        return out
    for i in range(seed_idx + 1, n):
        if np.isnan(values[i]):
            out[i] = last
            continue
        last = values[i] * k + last * (1.0 - k)
        out[i] = last
    return out


def _true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    # Primeiro candle: sem fechamento anterior, TR = high - low.
    prev_close = np.empty_like(close)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    return np.maximum.reduce(
        [
            high - low,
            np.abs(high - prev_close),
            np.abs(low - prev_close),
        ]
    )


def _typical_price(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    return (high + low + close) / 3.0


# ----------------------------------------------------------------------
# IND-001/003 — Tendência
# ----------------------------------------------------------------------
def sma(values: ArrayLike, period: int = 20) -> np.ndarray:
    """SMA — média móvel simples.

    ``SMA[i] = mean(values[i-period+1 .. i])``. NaN até ``period - 1``.
    """
    period = _check_period(period)
    return _rolling_mean(_as_array(values, "values"), period)


def ema(values: ArrayLike, period: int = 20) -> np.ndarray:
    """EMA — média móvel exponencial (``k = 2 / (period + 1)``).

    Semeada com a SMA dos ``period`` primeiros valores.
    """
    period = _check_period(period)
    return _ema_from_seed(_as_array(values, "values"), period)


def macd(
    close: ArrayLike,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Dict[str, np.ndarray]:
    """MACD — ``EMA(fast) - EMA(slow)``, sinal = EMA(signal) da linha.

    Devolve ``{"macd", "signal", "histogram"}``; histograma = macd - signal.
    Em série constante, macd = 0.
    """
    fast = _check_period(fast, "fast")
    slow = _check_period(slow, "slow")
    signal = _check_period(signal, "signal")
    c = _as_array(close, "close")
    macd_line = ema(c, fast) - ema(c, slow)
    # EMA do sinal só sobre os valores válidos da linha MACD.
    sig = _nan_out(len(c))
    valid = ~np.isnan(macd_line)
    if valid.sum() >= signal:
        first = int(np.argmax(valid))
        sig[first + signal - 1:] = _ema_from_seed(
            macd_line[first:], signal
        )[signal - 1:]
    return {
        "macd": macd_line,
        "signal": sig,
        "histogram": macd_line - sig,
    }


def dmi(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    period: int = 14,
) -> Dict[str, np.ndarray]:
    """DMI / ADX (Wilder).

    ``+DM`` = alta atual - alta anterior (se > movimento da mínima e > 0);
    ``-DM`` análogo; ``TR`` = true range. Suavização de Wilder sobre
    TR, +DM e -DM; ``+DI = 100 * +DM_suavizado / TR_suavizado``;
    ``DX = 100 * |+DI - -DI| / (+DI + -DI)``; ``ADX`` = média de Wilder
    de DX (primeiro valor = média dos ``period`` primeiros DX).

    Devolve ``{"plus_di", "minus_di", "dx", "adx"}``.
    """
    period = _check_period(period)
    h = _as_array(high, "high")
    l = _as_array(low, "low")
    c = _as_array(close, "close")
    n = len(c)
    if not (len(h) == len(l) == n):
        raise ValueError("high, low e close devem ter o mesmo comprimento")
    tr = _true_range(h, l, c)
    up_move = np.empty(n)
    up_move[0] = np.nan
    up_move[1:] = h[1:] - h[:-1]
    down_move = np.empty(n)
    down_move[0] = np.nan
    down_move[1:] = l[:-1] - l[1:]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    # Primeiro candle: sem barra anterior, DM = 0 (convenção padrão).
    plus_dm[0] = 0.0
    minus_dm[0] = 0.0
    tr_s = _wilder_smooth(tr, period)
    plus_s = _wilder_smooth(plus_dm, period)
    minus_s = _wilder_smooth(minus_dm, period)
    with np.errstate(invalid="ignore", divide="ignore"):
        plus_di = np.where(tr_s > 0, 100.0 * plus_s / tr_s, np.nan)
        minus_di = np.where(tr_s > 0, 100.0 * minus_s / tr_s, np.nan)
        di_sum = plus_di + minus_di
        dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, np.nan)
    adx = _wilder_smooth(dx, period)
    return {"plus_di": plus_di, "minus_di": minus_di, "dx": dx, "adx": adx}


def adx(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    period: int = 14,
) -> np.ndarray:
    """ADX — atalho para ``dmi(... )["adx"]``."""
    return dmi(high, low, close, period)["adx"]


def supertrend(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    period: int = 10,
    multiplier: float = 3.0,
) -> Dict[str, np.ndarray]:
    """Supertrend (Olivier Seban).

    Banda básica: ``mid = (H+L)/2``; ``upper = mid + mult*ATR``,
    ``lower = mid - mult*ATR``. A banda final só se move a favor da
    tendência (upper nunca sobe, lower nunca desce, salvo cruzamento).
    Tendência de alta enquanto o fechamento estiver acima da banda
    inferior final; de baixa enquanto estiver abaixo da banda superior.

    Devolve ``{"supertrend", "direction"}``; ``direction`` é +1 (alta)
    ou -1 (baixa), NaN no warm-up do ATR.
    """
    period = _check_period(period)
    if multiplier <= 0:
        raise ValueError(f"multiplier deve ser > 0, recebido {multiplier}")
    h = _as_array(high, "high")
    l = _as_array(low, "low")
    c = _as_array(close, "close")
    n = len(c)
    if not (len(h) == len(l) == n):
        raise ValueError("high, low e close devem ter o mesmo comprimento")
    atr_v = atr(h, l, c, period)
    mid = (h + l) / 2.0
    upper_basic = mid + multiplier * atr_v
    lower_basic = mid - multiplier * atr_v
    st = _nan_out(n)
    direction = _nan_out(n)
    first = period - 1
    if n <= first:
        return {"supertrend": st, "direction": direction}
    # Primeiro valor: tendência definida pelo fechamento vs. banda.
    if c[first] > upper_basic[first]:
        direction[first] = 1.0
        st[first] = lower_basic[first]
    else:
        direction[first] = -1.0
        st[first] = upper_basic[first]
    final_upper = upper_basic[first]
    final_lower = lower_basic[first]
    for i in range(first + 1, n):
        if np.isnan(atr_v[i]):
            st[i] = st[i - 1]
            direction[i] = direction[i - 1]
            continue
        # Banda final: upper só desce, lower só sobe (sem cruzamento).
        if upper_basic[i] < final_upper or c[i - 1] > final_upper:
            final_upper = upper_basic[i]
        if lower_basic[i] > final_lower or c[i - 1] < final_lower:
            final_lower = lower_basic[i]
        if direction[i - 1] == 1.0:
            if c[i] < final_lower:
                direction[i] = -1.0
                st[i] = final_upper
            else:
                direction[i] = 1.0
                st[i] = final_lower
        else:
            if c[i] > final_upper:
                direction[i] = 1.0
                st[i] = final_lower
            else:
                direction[i] = -1.0
                st[i] = final_upper
    return {"supertrend": st, "direction": direction}


# ----------------------------------------------------------------------
# IND-002 — Momentum
# ----------------------------------------------------------------------
def rsi(close: ArrayLike, period: int = 14) -> np.ndarray:
    """RSI de Wilder: ``100 - 100 / (1 + avg_gain / avg_loss)``.

    Médias de ganhos/perdas suavizadas por Wilder. Se a perda média é
    0 (só altas) → 100; se o ganho médio é 0 (só quedas) → 0.
    """
    period = _check_period(period)
    c = _as_array(close, "close")
    n = len(c)
    out = _nan_out(n)
    if n < period + 1:
        return out
    delta = np.diff(c)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    # delta NaN (close NaN): ganho/perda NaN → Wilder pula a atualização.
    gain = np.where(np.isnan(delta), np.nan, gain)
    loss = np.where(np.isnan(delta), np.nan, loss)
    avg_gain = _wilder_smooth(gain, period)
    avg_loss = _wilder_smooth(loss, period)
    # avg_* tem índice alinhado a delta; RSI[i] usa avg até i-1.
    with np.errstate(invalid="ignore", divide="ignore"):
        rs = avg_gain / avg_loss
        rsi_v = 100.0 - 100.0 / (1.0 + rs)
    rsi_v = np.where((avg_loss == 0) & (avg_gain > 0), 100.0, rsi_v)
    rsi_v = np.where((avg_gain == 0) & (avg_loss > 0), 0.0, rsi_v)
    rsi_v = np.where((avg_gain == 0) & (avg_loss == 0), 50.0, rsi_v)
    out[1:] = rsi_v
    return out


def stochastic(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    k_period: int = 14,
    d_period: int = 3,
) -> Dict[str, np.ndarray]:
    """Stochastic: ``%K = 100 * (C - LL) / (HH - LL)``; ``%D = SMA(%K, d)``.

    HH/LL são máxima/mínima da janela ``k_period``. Se HH == LL → NaN.
    """
    k_period = _check_period(k_period, "k_period")
    d_period = _check_period(d_period, "d_period")
    h = _as_array(high, "high")
    l = _as_array(low, "low")
    c = _as_array(close, "close")
    n = len(c)
    if not (len(h) == len(l) == n):
        raise ValueError("high, low e close devem ter o mesmo comprimento")
    k = _nan_out(n)
    for i in range(k_period - 1, n):
        window_h = h[i - k_period + 1:i + 1]
        window_l = l[i - k_period + 1:i + 1]
        if np.isnan(window_h).any() or np.isnan(window_l).any() or np.isnan(c[i]):
            continue
        hh, ll = float(np.max(window_h)), float(np.min(window_l))
        k[i] = 100.0 * (c[i] - ll) / (hh - ll) if hh > ll else np.nan
    return {"k": k, "d": sma(k, d_period)}


def stochastic_rsi(
    close: ArrayLike,
    rsi_period: int = 14,
    stoch_period: int = 14,
    k_period: int = 3,
    d_period: int = 3,
) -> Dict[str, np.ndarray]:
    """Stochastic RSI: Stochastic aplicado sobre o RSI.

    ``%K = SMA(100 * (RSI - min RSI) / (max RSI - min RSI), k)``;
    ``%D = SMA(%K, d)``.
    """
    rsi_period = _check_period(rsi_period, "rsi_period")
    stoch_period = _check_period(stoch_period, "stoch_period")
    k_period = _check_period(k_period, "k_period")
    d_period = _check_period(d_period, "d_period")
    rsi_v = rsi(close, rsi_period)
    n = len(rsi_v)
    raw = _nan_out(n)
    for i in range(stoch_period - 1, n):
        window = rsi_v[i - stoch_period + 1:i + 1]
        if np.isnan(window).any():
            continue
        hi, lo = float(np.max(window)), float(np.min(window))
        raw[i] = 100.0 * (rsi_v[i] - lo) / (hi - lo) if hi > lo else np.nan
    k = sma(raw, k_period)
    return {"k": k, "d": sma(k, d_period)}


def roc(close: ArrayLike, period: int = 12) -> np.ndarray:
    """ROC (%): ``100 * (C[i] - C[i-period]) / C[i-period]``.

    Preço anterior 0 ou NaN → NaN.
    """
    period = _check_period(period)
    c = _as_array(close, "close")
    out = _nan_out(len(c))
    if len(c) <= period:
        return out
    prev = c[:-period]
    with np.errstate(invalid="ignore", divide="ignore"):
        out[period:] = np.where(
            (prev != 0) & ~np.isnan(prev),
            100.0 * (c[period:] - prev) / prev,
            np.nan,
        )
    return out


def cci(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    period: int = 20,
) -> np.ndarray:
    """CCI (Lambert): ``(TP - SMA(TP)) / (0.015 * desvio médio de TP)``.

    TP = preço típico ``(H+L+C)/3``. Desvio médio 0 → NaN.
    """
    period = _check_period(period)
    h = _as_array(high, "high")
    l = _as_array(low, "low")
    c = _as_array(close, "close")
    if not (len(h) == len(l) == len(c)):
        raise ValueError("high, low e close devem ter o mesmo comprimento")
    tp = _typical_price(h, l, c)
    mean = _rolling_mean(tp, period)
    out = _nan_out(len(c))
    for i in range(period - 1, len(c)):
        window = tp[i - period + 1:i + 1]
        if np.isnan(window).any() or np.isnan(mean[i]):
            continue
        mean_dev = float(np.mean(np.abs(window - mean[i])))
        out[i] = (tp[i] - mean[i]) / (0.015 * mean_dev) if mean_dev > 0 else np.nan
    return out


# ----------------------------------------------------------------------
# IND-004 — Volatilidade
# ----------------------------------------------------------------------
def atr(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    period: int = 14,
) -> np.ndarray:
    """ATR de Wilder: média de Wilder do True Range."""
    period = _check_period(period)
    h = _as_array(high, "high")
    l = _as_array(low, "low")
    c = _as_array(close, "close")
    if not (len(h) == len(l) == len(c)):
        raise ValueError("high, low e close devem ter o mesmo comprimento")
    return _wilder_smooth(_true_range(h, l, c), period)


def bollinger(
    close: ArrayLike,
    period: int = 20,
    std_dev: float = 2.0,
) -> Dict[str, np.ndarray]:
    """Bollinger Bands: média ± ``std_dev`` * desvio-padrão populacional.

    Devolve ``{"upper", "middle", "lower", "bandwidth", "percent_b"}``;
    ``bandwidth = (upper - lower) / middle`` e
    ``%B = (C - lower) / (upper - lower)``.
    """
    period = _check_period(period)
    if std_dev < 0:
        raise ValueError(f"std_dev deve ser >= 0, recebido {std_dev}")
    c = _as_array(close, "close")
    middle = _rolling_mean(c, period)
    std = _rolling_std(c, period)
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    with np.errstate(invalid="ignore", divide="ignore"):
        bandwidth = np.where(middle != 0, (upper - lower) / middle, np.nan)
        percent_b = np.where(
            (upper - lower) > 0, (c - lower) / (upper - lower), np.nan
        )
    return {
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "bandwidth": bandwidth,
        "percent_b": percent_b,
    }


def keltner(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    period: int = 20,
    atr_period: int = 10,
    multiplier: float = 2.0,
) -> Dict[str, np.ndarray]:
    """Keltner Channels: EMA(TP, period) ± ``multiplier`` * ATR.

    Devolve ``{"upper", "middle", "lower"}``.
    """
    period = _check_period(period)
    atr_period = _check_period(atr_period, "atr_period")
    if multiplier < 0:
        raise ValueError(f"multiplier deve ser >= 0, recebido {multiplier}")
    h = _as_array(high, "high")
    l = _as_array(low, "low")
    c = _as_array(close, "close")
    if not (len(h) == len(l) == len(c)):
        raise ValueError("high, low e close devem ter o mesmo comprimento")
    middle = ema(_typical_price(h, l, c), period)
    atr_v = atr(h, l, c, atr_period)
    return {
        "upper": middle + multiplier * atr_v,
        "middle": middle,
        "lower": middle - multiplier * atr_v,
    }


def realized_volatility(
    close: ArrayLike,
    window: int = 20,
    annualization: float = 365.0,
) -> np.ndarray:
    """Volatilidade realizada anualizada: desvio-padrão populacional dos
    retornos log vezes ``sqrt(annualization)``.

    ``annualization`` padrão 365 (cripto negocia 24/7); use 252 para
    comparar com ativos de bolsa.
    """
    window = _check_period(window, "window")
    if annualization <= 0:
        raise ValueError(f"annualization deve ser > 0, recebido {annualization}")
    c = _as_array(close, "close")
    rets = log_returns(c)
    std = _rolling_std(rets, window)
    return std * float(np.sqrt(annualization))


def historical_volatility(
    close: ArrayLike,
    window: int = 20,
    annualization: float = 365.0,
) -> np.ndarray:
    """Historical Volatility — mesmo cálculo de :func:`realized_volatility`."""
    return realized_volatility(close, window, annualization)


# ----------------------------------------------------------------------
# IND-005 — Volume
# ----------------------------------------------------------------------
def vwap(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    volume: ArrayLike,
    session_start: Optional[Sequence[bool]] = None,
) -> np.ndarray:
    """VWAP: ``sum(TP * V) / sum(V)`` acumulado na sessão.

    TP = preço típico. ``session_start`` (opcional, array booleano do
    mesmo comprimento) reinicia o acumulado em ``True`` (ex.: abertura
    do dia). Volume acumulado 0 → NaN.
    """
    h = _as_array(high, "high")
    l = _as_array(low, "low")
    c = _as_array(close, "close")
    v = _as_array(volume, "volume")
    n = len(c)
    if not (len(h) == len(l) == len(v) == n):
        raise ValueError("high, low, close e volume devem ter o mesmo comprimento")
    if session_start is not None:
        starts = np.asarray(session_start, dtype=bool)
        if len(starts) != n:
            raise ValueError("session_start deve ter o mesmo comprimento")
    else:
        starts = np.zeros(n, dtype=bool)
        starts[0] = True
    tp = _typical_price(h, l, c)
    out = _nan_out(n)
    cum_pv = 0.0
    cum_v = 0.0
    for i in range(n):
        if starts[i]:
            cum_pv, cum_v = 0.0, 0.0
        if not (np.isnan(tp[i]) or np.isnan(v[i])):
            cum_pv += tp[i] * v[i]
            cum_v += v[i]
        out[i] = cum_pv / cum_v if cum_v > 0 else np.nan
    return out


def anchored_vwap(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    volume: ArrayLike,
    anchor_index: int = 0,
) -> np.ndarray:
    """Anchored VWAP: VWAP acumulado a partir de ``anchor_index``.

    Antes da âncora → NaN. Volume acumulado 0 → NaN.
    """
    h = _as_array(high, "high")
    l = _as_array(low, "low")
    c = _as_array(close, "close")
    v = _as_array(volume, "volume")
    n = len(c)
    if not (len(h) == len(l) == len(v) == n):
        raise ValueError("high, low, close e volume devem ter o mesmo comprimento")
    if not 0 <= anchor_index < n:
        raise ValueError(f"anchor_index fora da série: {anchor_index}")
    tp = _typical_price(h, l, c)
    out = _nan_out(n)
    cum_pv = 0.0
    cum_v = 0.0
    for i in range(anchor_index, n):
        if not (np.isnan(tp[i]) or np.isnan(v[i])):
            cum_pv += tp[i] * v[i]
            cum_v += v[i]
        out[i] = cum_pv / cum_v if cum_v > 0 else np.nan
    return out


def obv(close: ArrayLike, volume: ArrayLike) -> np.ndarray:
    """OBV: soma volume quando o fechamento sobe, subtrai quando cai.

    Fechamento igual ao anterior não muda o OBV. Primeiro valor = volume
    do primeiro candle.
    """
    c = _as_array(close, "close")
    v = _as_array(volume, "volume")
    if len(c) != len(v):
        raise ValueError("close e volume devem ter o mesmo comprimento")
    out = _nan_out(len(c))
    out[0] = v[0]
    for i in range(1, len(c)):
        if np.isnan(c[i]) or np.isnan(c[i - 1]) or np.isnan(v[i]):
            out[i] = out[i - 1]
            continue
        if c[i] > c[i - 1]:
            out[i] = out[i - 1] + v[i]
        elif c[i] < c[i - 1]:
            out[i] = out[i - 1] - v[i]
        else:
            out[i] = out[i - 1]
    return out


def volume_profile(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    volume: ArrayLike,
    bins: int = 24,
    value_area_pct: float = 0.70,
) -> Dict[str, Any]:
    """Volume Profile: distribui o volume por faixas de preço.

    Cada candle contribui com seu volume na faixa do seu preço típico.
    ``POC`` = centro da faixa com maior volume. Value area = faixas
    expandidas a partir do POC até acumular ``value_area_pct`` do volume.

    Devolve ``{"poc", "value_area_high", "value_area_low",
    "bin_edges", "bin_volumes", "total_volume"}``. Sem volume (total 0)
    → POC e value area NaN.
    """
    bins = _check_period(bins, "bins")
    if not 0 < value_area_pct <= 1:
        raise ValueError(f"value_area_pct deve estar em (0, 1], recebido {value_area_pct}")
    h = _as_array(high, "high")
    l = _as_array(low, "low")
    c = _as_array(close, "close")
    v = _as_array(volume, "volume")
    if not (len(h) == len(l) == len(c) == len(v)):
        raise ValueError("high, low, close e volume devem ter o mesmo comprimento")
    tp = _typical_price(h, l, c)
    valid = ~np.isnan(tp) & ~np.isnan(v)
    total = float(np.sum(v[valid])) if valid.any() else 0.0
    if not valid.any() or total <= 0:
        edges = np.full(bins + 1, np.nan)
        return {
            "poc": np.nan,
            "value_area_high": np.nan,
            "value_area_low": np.nan,
            "bin_edges": edges,
            "bin_volumes": np.zeros(bins),
            "total_volume": total,
        }
    lo, hi = float(np.min(l[valid])), float(np.max(h[valid]))
    if hi <= lo:
        edges = np.linspace(lo, hi, bins + 1) if valid.any() else np.full(bins + 1, np.nan)
        return {
            "poc": np.nan,
            "value_area_high": np.nan,
            "value_area_low": np.nan,
            "bin_edges": edges,
            "bin_volumes": np.zeros(bins),
            "total_volume": total,
        }
    edges = np.linspace(lo, hi, bins + 1)
    bin_volumes, _ = np.histogram(tp[valid], bins=edges, weights=v[valid])
    poc_idx = int(np.argmax(bin_volumes))
    poc = float((edges[poc_idx] + edges[poc_idx + 1]) / 2.0)
    # Value area: expande do POC somando a faixa vizinha de maior volume.
    va_lo = va_hi = poc_idx
    va_vol = float(bin_volumes[poc_idx])
    target = value_area_pct * total
    while va_vol < target and (va_lo > 0 or va_hi < bins - 1):
        up = float(bin_volumes[va_hi + 1]) if va_hi < bins - 1 else -1.0
        down = float(bin_volumes[va_lo - 1]) if va_lo > 0 else -1.0
        if up >= down:
            va_hi += 1
            va_vol += up
        else:
            va_lo -= 1
            va_vol += down
    return {
        "poc": poc,
        "value_area_high": float(edges[va_hi + 1]),
        "value_area_low": float(edges[va_lo]),
        "bin_edges": edges,
        "bin_volumes": bin_volumes.astype(float),
        "total_volume": total,
    }


def mfi(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    volume: ArrayLike,
    period: int = 14,
) -> np.ndarray:
    """MFI: ``100 - 100 / (1 + fluxo positivo / fluxo negativo)``.

    Fluxo = TP * volume; positivo quando TP sobe, negativo quando cai.
    Fluxo negativo 0 (só altas) → 100; ambos 0 → NaN.
    """
    period = _check_period(period)
    h = _as_array(high, "high")
    l = _as_array(low, "low")
    c = _as_array(close, "close")
    v = _as_array(volume, "volume")
    if not (len(h) == len(l) == len(c) == len(v)):
        raise ValueError("high, low, close e volume devem ter o mesmo comprimento")
    tp = _typical_price(h, l, c)
    flow = tp * v
    pos = np.zeros(len(c))
    neg = np.zeros(len(c))
    up = tp[1:] > tp[:-1]
    down = tp[1:] < tp[:-1]
    pos[1:][up] = flow[1:][up]
    neg[1:][down] = flow[1:][down]
    pos[0] = np.nan
    neg[0] = np.nan
    # Somas móveis dos fluxos (janela period, incluindo o candle atual).
    n = len(c)
    out = _nan_out(n)
    if n < period + 1:
        return out
    pos_c = np.concatenate([[0.0], np.nancumsum(np.where(np.isnan(pos), 0.0, pos))])
    neg_c = np.concatenate([[0.0], np.nancumsum(np.where(np.isnan(neg), 0.0, neg))])
    for i in range(period, n):
        # Janela de `period` fluxos: índices i-period+1 .. i (fluxo do
        # candle i compara TP[i] com TP[i-1]; por isso o warm-up é period).
        p = pos_c[i + 1] - pos_c[i + 1 - period]
        q = neg_c[i + 1] - neg_c[i + 1 - period]
        if np.isnan(tp[i - period + 1:i + 1]).any():
            continue
        if q == 0:
            out[i] = 100.0 if p > 0 else np.nan
        else:
            out[i] = 100.0 - 100.0 / (1.0 + p / q)
    return out


def cvd(
    close: ArrayLike,
    volume: ArrayLike,
    open_: Optional[ArrayLike] = None,
    side: Optional[Sequence[int]] = None,
) -> np.ndarray:
    """CVD — Cumulative Volume Delta (soma acumulada do volume com sinal).

    O sinal de cada candle vem, em ordem de preferência, de ``side``
    (+1 compra agressora / -1 venda agressora, dado de trade da Fase 7/10)
    ou do sinal de ``close - open`` (``open_``). Sem nenhum dos dois,
    usa o sinal da variação do fechamento. É uma aproximação quando não
    há dado de agressor — documentar a origem na hora de usar.
    """
    c = _as_array(close, "close")
    v = _as_array(volume, "volume")
    if len(c) != len(v):
        raise ValueError("close e volume devem ter o mesmo comprimento")
    if side is not None:
        s = np.asarray(side, dtype=float)
        if len(s) != len(c):
            raise ValueError("side deve ter o mesmo comprimento")
        signs = np.where(s > 0, 1.0, np.where(s < 0, -1.0, 0.0))
    elif open_ is not None:
        o = _as_array(open_, "open")
        if len(o) != len(c):
            raise ValueError("open deve ter o mesmo comprimento")
        signs = np.sign(c - o)
    else:
        signs = np.zeros(len(c))
        signs[1:] = np.sign(c[1:] - c[:-1])
        signs[0] = 1.0 if not np.isnan(c[0]) else 0.0
    signs = np.where(np.isnan(c) | np.isnan(v), 0.0, signs)
    return np.cumsum(signs * np.where(np.isnan(v), 0.0, v))


# ----------------------------------------------------------------------
# IND-006 — Divergências
# ----------------------------------------------------------------------
def find_swings(
    values: ArrayLike, window: int = 2
) -> Dict[str, List[int]]:
    """Topos e fundos (pivôs): índice ``i`` é topo se for o máximo
    estrito de ``values[i-window .. i+window]`` (fundo análogo).

    Devolve ``{"highs": [...], "lows": [...]}`` com índices ordenados.
    """
    window = _check_period(window, "window")
    v = _as_array(values, "values")
    highs: List[int] = []
    lows: List[int] = []
    for i in range(window, len(v) - window):
        w = v[i - window:i + window + 1]
        if np.isnan(w).any():
            continue
        if v[i] == np.max(w) and v[i] > v[i - 1] and v[i] >= v[i + 1]:
            highs.append(i)
        if v[i] == np.min(w) and v[i] < v[i - 1] and v[i] <= v[i + 1]:
            lows.append(i)
    return {"highs": highs, "lows": lows}


def detect_divergences(
    close: ArrayLike,
    indicator: ArrayLike,
    window: int = 2,
) -> List[Dict[str, Any]]:
    """Divergências preço vs. indicador (regular e oculta).

    Compara pivôs **consecutivos** do mesmo tipo em preço e indicador:

    - regular de alta: preço faz fundo mais baixo, indicador fundo mais alto;
    - regular de baixa: preço faz topo mais alto, indicador topo mais baixo;
    - oculta de alta: preço faz fundo mais alto, indicador fundo mais baixo;
    - oculta de baixa: preço faz topo mais baixo, indicador topo mais alto.

    Devolve lista de ``{"type", "price_index", "indicator_index",
    "price_value", "indicator_value", "previous_price_index",
    "previous_indicator_index"}`` ordenada por ``price_index``.
    """
    window = _check_period(window, "window")
    price = _as_array(close, "close")
    ind = _as_array(indicator, "indicator")
    if len(price) != len(ind):
        raise ValueError("close e indicator devem ter o mesmo comprimento")
    p_sw = find_swings(price, window)
    i_sw = find_swings(ind, window)
    out: List[Dict[str, Any]] = []

    def _pair(pivots_p, pivots_i, kind: str) -> None:
        # Emparelha pivôs consecutivos do mesmo tipo: para cada par
        # consecutivo de pivôs de preço, usa os dois pivôs de indicador
        # mais próximos (anteriores ou iguais) a cada um deles.
        for a, b in zip(pivots_p, pivots_p[1:]):
            ia = [x for x in pivots_i if x <= a]
            ib = [x for x in pivots_i if x <= b]
            if not ia or not ib or ia[-1] == ib[-1]:
                continue
            ia, ib = ia[-1], ib[-1]
            pv_a, pv_b = price[a], price[b]
            iv_a, iv_b = ind[ia], ind[ib]
            div_type = None
            if kind == "low":
                if pv_b < pv_a and iv_b > iv_a:
                    div_type = "regular_bullish"
                elif pv_b > pv_a and iv_b < iv_a:
                    div_type = "hidden_bullish"
            else:
                if pv_b > pv_a and iv_b < iv_a:
                    div_type = "regular_bearish"
                elif pv_b < pv_a and iv_b > iv_a:
                    div_type = "hidden_bearish"
            if div_type:
                out.append(
                    {
                        "type": div_type,
                        "price_index": int(b),
                        "indicator_index": int(ib),
                        "price_value": float(pv_b),
                        "indicator_value": float(iv_b),
                        "previous_price_index": int(a),
                        "previous_indicator_index": int(ia),
                    }
                )

    _pair(p_sw["lows"], i_sw["lows"], "low")
    _pair(p_sw["highs"], i_sw["highs"], "high")
    out.sort(key=lambda d: d["price_index"])
    return out


# ----------------------------------------------------------------------
# IND-007 — Features derivadas (para a Fase 13 / ML)
# ----------------------------------------------------------------------
def log_returns(close: ArrayLike) -> np.ndarray:
    """Retornos log: ``ln(C[i] / C[i-1])``; primeiro valor NaN."""
    c = _as_array(close, "close")
    out = _nan_out(len(c))
    with np.errstate(invalid="ignore", divide="ignore"):
        out[1:] = np.where(
            (c[1:] > 0) & (c[:-1] > 0), np.log(c[1:] / c[:-1]), np.nan
        )
    return out


def distance_from_ma(close: ArrayLike, period: int = 20) -> np.ndarray:
    """Distância do preço à SMA, em %: ``100 * (C - SMA) / SMA``."""
    period = _check_period(period)
    c = _as_array(close, "close")
    ma = sma(c, period)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(ma != 0, 100.0 * (c - ma) / ma, np.nan)


def zscore(values: ArrayLike, window: int = 20) -> np.ndarray:
    """Z-score em janela móvel: ``(x - média) / desvio-padrão``.

    Desvio-padrão 0 → 0.0 se o valor é igual à média, senão NaN.
    """
    window = _check_period(window, "window")
    v = _as_array(values, "values")
    mean = _rolling_mean(v, window)
    std = _rolling_std(v, window)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(
            std > 0,
            (v - mean) / std,
            np.where(v == mean, 0.0, np.nan),
        )
    return out


def zscore_volume(volume: ArrayLike, window: int = 20) -> np.ndarray:
    """Z-score do volume em janela móvel (atalho de :func:`zscore`)."""
    return zscore(volume, window)


# ----------------------------------------------------------------------
# Utilidades — candles e cálculo em lote
# ----------------------------------------------------------------------
def candles_to_arrays(candles: Sequence[Any]) -> Dict[str, np.ndarray]:
    """Converte uma sequência de :class:`Candle` (ou dicts com as mesmas
    chaves) em dict de arrays: open/high/low/close/volume e timestamps.
    """
    if len(candles) == 0:
        raise ValueError("candles não pode ser vazio")
    rows: List[Dict[str, float]] = []
    for candle in candles:
        if isinstance(candle, dict):
            get = candle.__getitem__
            rows.append(
                {
                    "open": float(get("open")),
                    "high": float(get("high")),
                    "low": float(get("low")),
                    "close": float(get("close")),
                    "volume": float(get("volume")),
                    "open_time_ms": float(get("open_time_ms")),
                    "close_time_ms": float(get("close_time_ms")),
                }
            )
        else:
            rows.append(
                {
                    "open": float(candle.open),
                    "high": float(candle.high),
                    "low": float(candle.low),
                    "close": float(candle.close),
                    "volume": float(candle.volume),
                    "open_time_ms": float(candle.open_time_ms),
                    "close_time_ms": float(candle.close_time_ms),
                }
            )
    return {k: np.array([r[k] for r in rows], dtype=float) for k in rows[0]}


def compute_features(
    close: ArrayLike,
    volume: Optional[ArrayLike] = None,
    window: int = 20,
) -> Dict[str, np.ndarray]:
    """Features derivadas prontas para a Fase 13 (ML).

    ``log_return``, ``realized_vol_{window}``, ``dist_sma_{window}``,
    ``dist_ema_{window}``, ``zscore_close_{window}`` e, se houver volume,
    ``zscore_volume_{window}`` e ``volume_ratio`` (volume / SMA(volume)).
    """
    window = _check_period(window, "window")
    c = _as_array(close, "close")
    feats: Dict[str, np.ndarray] = {
        "log_return": log_returns(c),
        f"realized_vol_{window}": realized_volatility(c, window),
        f"dist_sma_{window}": distance_from_ma(c, window),
        f"dist_ema_{window}": np.where(
            ema(c, window) != 0,
            100.0 * (c - ema(c, window)) / ema(c, window),
            np.nan,
        ),
        f"zscore_close_{window}": zscore(c, window),
    }
    if volume is not None:
        v = _as_array(volume, "volume")
        feats[f"zscore_volume_{window}"] = zscore_volume(v, window)
        vol_ma = sma(v, window)
        with np.errstate(invalid="ignore", divide="ignore"):
            feats["volume_ratio"] = np.where(vol_ma > 0, v / vol_ma, np.nan)
    return feats


def compute_all(
    candles: Sequence[Any],
    session_start: Optional[Sequence[bool]] = None,
) -> Dict[str, Any]:
    """Calcula todos os indicadores com parâmetros padrão sobre candles.

    Devolve dict com as séries (arrays) e o volume profile (dict).
    Útil para a Fase 11 (estratégias) e a Fase 13 (features).
    """
    data = candles_to_arrays(candles)
    h, l, c, v = data["high"], data["low"], data["close"], data["volume"]
    o = data["open"]
    result: Dict[str, Any] = {
        "sma_20": sma(c, 20),
        "ema_20": ema(c, 20),
        "macd": macd(c),
        "dmi": dmi(h, l, c),
        "supertrend": supertrend(h, l, c),
        "rsi_14": rsi(c, 14),
        "stochastic": stochastic(h, l, c),
        "stochastic_rsi": stochastic_rsi(c),
        "roc_12": roc(c, 12),
        "cci_20": cci(h, l, c, 20),
        "atr_14": atr(h, l, c, 14),
        "bollinger": bollinger(c),
        "keltner": keltner(h, l, c),
        "historical_volatility_20": historical_volatility(c, 20),
        "vwap": vwap(h, l, c, v, session_start),
        "obv": obv(c, v),
        "volume_profile": volume_profile(h, l, c, v),
        "mfi_14": mfi(h, l, c, v, 14),
        "cvd": cvd(c, v, open_=o),
        "features": compute_features(c, v),
    }
    result["divergences_rsi"] = detect_divergences(c, result["rsi_14"])
    return result
