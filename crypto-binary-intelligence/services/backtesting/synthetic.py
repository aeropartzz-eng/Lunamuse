"""Séries sintéticas para backtest — Fase 12 (BKT-008 e relatório).

Dados **sintéticos e determinísticos** (seed fixa), usados nos
testes e no relatório de exemplo. Não são dados reais: o relatório
de exemplo deixa isso explícito no título e no corpo.

Cada série mistura regimes: tendência de alta, lateralização,
tendência de baixa e expansão volátil — para que o motor seja
exercitado em mais de um regime, como exige o BKT-008. Os candles
são dicts (o motor aceita dicts e objetos ``Candle``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

__all__ = [
    "make_synthetic_series",
    "make_mixed_regime_series",
    "REGIMES",
]

BASE_MS = 1_767_000_000_000  # 2026-01-01T00:00:00Z
TF_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000}

# (rótulo, nº de candles, drift por candle, vol por candle)
REGIMES: List[Tuple[str, int, float, float]] = [
    ("TREND_UP", 300, 0.004, 0.006),
    ("RANGE", 200, 0.0, 0.008),
    ("TREND_DOWN", 200, -0.004, 0.006),
    ("EXPANSION", 150, 0.001, 0.020),
    ("TREND_UP", 250, 0.003, 0.006),
]


def _regime_closes(
    rng: np.random.Generator, start: float, drift: float, vol: float, n: int,
    range_amp: float = 0.03,
) -> List[float]:
    """Fechamentos de um regime: random walk com drift (+ oscilação
    senoidal no RANGE, para o preço ir e voltar sem tendência)."""
    closes: List[float] = []
    price = start
    for i in range(n):
        shock = rng.normal(0.0, vol)
        if drift == 0.0:  # RANGE: reversão à média em torno do preço inicial
            pull = -0.02 * (price - start) / start
            price *= 1.0 + pull + shock
        else:
            price *= 1.0 + drift + shock
        closes.append(price)
    return closes


def make_mixed_regime_series(
    seed: int = 42,
    start_price: float = 100.0,
    timeframe: str = "5m",
    symbol: str = "BTC/USDT",
    regimes: Sequence[Tuple[str, int, float, float]] = REGIMES,
) -> List[Dict[str, Any]]:
    """Série sintética com regimes mistos (determinística por seed)."""
    rng = np.random.default_rng(seed)
    closes: List[float] = []
    price = start_price
    for _label, n, drift, vol in regimes:
        leg = _regime_closes(rng, price, drift, vol, n)
        closes.extend(leg)
        price = leg[-1]
    return make_synthetic_series(
        closes, seed=seed, timeframe=timeframe, symbol=symbol,
        volume_base=100.0,
    )


def make_synthetic_series(
    closes: Sequence[float],
    seed: int = 42,
    timeframe: str = "5m",
    symbol: str = "BTC/USDT",
    volume_base: float = 100.0,
) -> List[Dict[str, Any]]:
    """Candles OHLCV dict a partir de fechamentos.

    open = fechamento anterior; high/low com pavio aleatório
    (determinístico por seed); volume com ruído e picos ocasionais.
    """
    rng = np.random.default_rng(seed)
    step_ms = TF_MS.get(timeframe, 300_000)
    candles: List[Dict[str, Any]] = []
    prev = float(closes[0])
    for i, close in enumerate(closes):
        close = float(close)
        open_ = prev
        wick = abs(rng.normal(0.0, 0.004)) * close
        high = max(open_, close) + wick
        low = min(open_, close) - wick
        volume = volume_base * float(rng.lognormal(0.0, 0.3))
        if rng.random() < 0.05:
            volume *= 2.5  # pico ocasional de volume
        candles.append({
            "exchange": "synthetic",
            "symbol": symbol,
            "timeframe": timeframe,
            "open_time_ms": BASE_MS + i * step_ms,
            "close_time_ms": BASE_MS + (i + 1) * step_ms,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })
        prev = close
    return candles
