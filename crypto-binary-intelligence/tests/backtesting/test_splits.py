"""Testes de divisão cronológica, walk-forward e purged CV — Fase 12
(BKT-004/BKT-005/BKT-006). Sem rede.
"""

from __future__ import annotations

import pytest

from splits import chronological_split, purged_kfold_splits, walk_forward_windows


def test_chronological_split_blocks():
    split = chronological_split(1000, 0.6, 0.2)
    assert split == {"train": (0, 600), "validation": (600, 800), "test": (800, 1000)}
    # Blocos contíguos, sem sobreposição, cobrindo a série inteira.
    assert split["train"][1] == split["validation"][0]
    assert split["validation"][1] == split["test"][0]


def test_chronological_split_rejects_bad_fractions():
    with pytest.raises(ValueError):
        chronological_split(100, 0.7, 0.3)
    with pytest.raises(ValueError):
        chronological_split(1, 0.6, 0.2)  # sem candles para o warm-up


def test_walk_forward_no_overlap_and_chronological():
    windows = walk_forward_windows(1000, train_size=400, test_size=100, step=100)
    assert len(windows) == 6  # starts 0..500
    for w in windows:
        train, test = w["train"], w["test"]
        assert train[1] <= test[0]  # teste sempre após o treino
        assert train[0] < train[1] <= test[0] < test[1]
        assert len(set(range(*train)) & set(range(*test))) == 0
    # Janelas avançam no tempo.
    starts = [w["test"][0] for w in windows]
    assert starts == sorted(starts)
    assert windows[0] == {"train": (0, 400), "test": (400, 500)}
    assert windows[-1] == {"train": (500, 900), "test": (900, 1000)}


def test_walk_forward_embargo_separates_train_test():
    windows = walk_forward_windows(
        1000, train_size=400, test_size=100, step=100, embargo_bars=10)
    assert windows[0]["test"][0] == 410  # 400 + embargo 10
    assert windows[0]["train"][1] == 400


def test_walk_forward_rejects_short_series():
    with pytest.raises(ValueError):
        walk_forward_windows(100, train_size=400, test_size=100, step=100)


def test_purged_kfold_embargo_excludes_neighbors():
    splits = purged_kfold_splits(100, n_splits=5, embargo_bars=2)
    assert len(splits) == 5
    for split in splits:
        train = set(split["train_idx"])
        test = split["test_idx"]
        assert not (train & set(test))
        # Embargo: vizinhos do fold de teste não estão no treino.
        lo, hi = min(test), max(test)
        for i in range(max(0, lo - 2), min(100, hi + 3)):
            if lo <= i <= hi:
                continue
            assert i not in train
    # Cada índice é teste exatamente uma vez.
    all_test = sorted(i for s in splits for i in s["test_idx"])
    assert all_test == list(range(100))


def test_purged_kfold_no_embargo_covers_all():
    splits = purged_kfold_splits(100, n_splits=4, embargo_bars=0)
    for split in splits:
        assert sorted(split["train_idx"] + split["test_idx"]) == list(range(100))
