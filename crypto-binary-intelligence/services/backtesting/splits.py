"""Divisão cronológica e validação — Fase 12 (BKT-004/BKT-005/BKT-006).

Tudo aqui trabalha com índices, nunca embaralha o tempo e nunca
deixa o treino ver o teste.

- :func:`chronological_split`: treino/validação/teste em blocos
  contíguos (padrão 60/20/20).
- :func:`walk_forward_windows`: janelas deslizantes — cada janela
  tem um treino contíguo e um teste contíguo **após** o treino, com
  embargo opcional entre eles. As janelas avançam ``step`` candles;
  treino e teste nunca se sobrepõem (testado).
- :func:`purged_kfold_splits`: K folds cronológicos com purga +
  embargo (Lopez de Prado). Uso: **só** quando há vazamento por
  sobreposição de janelas de features ou autocorrelação de rótulos
  — ou seja, no treino de modelos da Fase 13, não no backtest
  orientado a eventos, onde o walk-forward já impede o vazamento
  (o sinal do candle ``i`` só usa dados até ``i``). O embargo
  remove ``embargo_bars`` ao redor de cada fold de teste do treino.

Documentação da decisão (BKT-006): purged CV **não** é aplicado
ao backtest de estratégias desta fase — o walk-forward cronológico
com embargo cumpre o mesmo papel sem misturar passado e futuro;
a purged CV fica reservada à Fase 13 (features com janelas
sobrepostas e rótulos autocorrelacionados).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

__all__ = [
    "chronological_split",
    "walk_forward_windows",
    "purged_kfold_splits",
]


def chronological_split(
    n: int,
    train_frac: float = 0.6,
    val_frac: float = 0.2,
) -> Dict[str, Tuple[int, int]]:
    """Treino/validação/teste cronológicos (blocos contíguos).

    Devolve ``{"train": (0, a), "validation": (a, b), "test": (b, n)}``
    como intervalos semiabertos ``[início, fim)``. ``train_frac +
    val_frac`` deve ser < 1.
    """
    if n <= 0:
        raise ValueError("n deve ser > 0")
    if not 0.0 < train_frac < 1.0:
        raise ValueError("train_frac deve estar em (0, 1)")
    if not 0.0 <= val_frac < 1.0:
        raise ValueError("val_frac deve estar em [0, 1)")
    if train_frac + val_frac >= 1.0:
        raise ValueError("train_frac + val_frac deve ser < 1")
    a = int(n * train_frac)
    b = int(n * (train_frac + val_frac))
    if a <= 0 or b <= a or b >= n:
        raise ValueError(
            f"n={n} pequeno demais para a divisão {train_frac}/{val_frac}"
        )
    return {"train": (0, a), "validation": (a, b), "test": (b, n)}


def walk_forward_windows(
    n: int,
    train_size: int,
    test_size: int,
    step: int,
    embargo_bars: int = 0,
) -> List[Dict[str, Tuple[int, int]]]:
    """Janelas walk-forward deslizantes (BKT-005).

    Cada janela ``k``: treino ``[start, start + train_size)`` e teste
    ``[start + train_size + embargo_bars, ... + test_size)``. A
    próxima janela começa ``step`` candles depois. A última janela
    parcial (teste menor que ``test_size``) é descartada — janelas
    incompletas não entram no relatório.
    """
    if train_size <= 0 or test_size <= 0 or step <= 0:
        raise ValueError("train_size, test_size e step devem ser > 0")
    if embargo_bars < 0:
        raise ValueError("embargo_bars não pode ser negativo")
    windows: List[Dict[str, Tuple[int, int]]] = []
    start = 0
    while True:
        train_end = start + train_size
        test_start = train_end + embargo_bars
        test_end = test_start + test_size
        if test_end > n:
            break
        windows.append({
            "train": (start, train_end),
            "test": (test_start, test_end),
        })
        start += step
    if not windows:
        raise ValueError(
            f"série de {n} candles curta demais para train={train_size}, "
            f"test={test_size}, step={step}, embargo={embargo_bars}"
        )
    return windows


def purged_kfold_splits(
    n: int,
    n_splits: int = 5,
    embargo_bars: int = 0,
) -> List[Dict[str, List[int]]]:
    """Purged K-Fold cronológico com embargo (BKT-006, Fase 13).

    A série é dividida em ``n_splits`` folds contíguos; cada fold é
    o teste uma vez, e o treino é todo o resto **menos** os
    ``embargo_bars`` ao redor do fold de teste (antes e depois).
    Devolve índices explícitos (``train_idx``/``test_idx``).
    """
    if n_splits < 2:
        raise ValueError("n_splits deve ser >= 2")
    if n < n_splits:
        raise ValueError("n menor que n_splits")
    if embargo_bars < 0:
        raise ValueError("embargo_bars não pode ser negativo")
    bounds = [round(i * n / n_splits) for i in range(n_splits + 1)]
    splits: List[Dict[str, List[int]]] = []
    for k in range(n_splits):
        test_start, test_end = bounds[k], bounds[k + 1]
        test_idx = list(range(test_start, test_end))
        purge_lo = max(0, test_start - embargo_bars)
        purge_hi = min(n, test_end + embargo_bars)
        train_idx = [i for i in range(n) if i < purge_lo or i >= purge_hi]
        splits.append({"train_idx": train_idx, "test_idx": test_idx})
    return splits
