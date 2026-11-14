"""Testes da Feature Store — Fase 13 (ML-001).

Sem rede. Séries sintéticas determinísticas.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from ml_features import (
    FEATURE_NAMES,
    FEATURE_SET_VERSION,
    FeatureStore,
    build_feature_matrix,
    make_labels,
)
from splits import chronological_split
from synthetic import make_mixed_regime_series

SHORT_REGIMES = [
    ("TREND_UP", 200, 0.004, 0.006),
    ("RANGE", 200, 0.0, 0.008),
]


def _series(seed=42):
    return make_mixed_regime_series(seed=seed, regimes=SHORT_REGIMES)


def test_feature_matrix_shape_and_version():
    fs = build_feature_matrix(_series(), horizon=1)
    assert fs.version == FEATURE_SET_VERSION
    assert fs.n_features == 29
    assert fs.feature_names == FEATURE_NAMES
    assert fs.X.shape[1] == 29
    assert fs.X.shape[0] == fs.y.shape[0] == fs.future_returns.shape[0]
    assert not np.isnan(fs.X).any()
    assert set(np.unique(fs.y)) <= {0, 1}
    assert fs.regime_available is True
    assert fs.n_rows > 300  # 400 candles menos warm-up e rótulo final


def test_make_labels_direction():
    labels = make_labels(np.array([100.0, 101.0, 99.0, 99.5]), horizon=1)
    assert labels["y"][0] == 1.0  # 101 > 100
    assert labels["y"][1] == 0.0  # 99 < 101
    assert labels["y"][2] == 1.0  # 99.5 > 99
    assert np.isnan(labels["y"][3])  # sem fechamento futuro
    assert labels["future_log_return"][0] == pytest.approx(np.log(101.0 / 100.0))


def test_no_lookahead_perturb_future():
    """Perturbar candles após o índice 200 não muda as features até 199."""
    candles = _series()
    fs_before = build_feature_matrix(candles, horizon=1)

    perturbed = copy.deepcopy(candles)
    for c in perturbed[200:]:
        c["close"] *= 1.5
        c["high"] *= 1.5
        c["low"] *= 1.5
        c["open"] *= 1.5
        c["volume"] *= 3.0
    fs_after = build_feature_matrix(perturbed, horizon=1)

    # Linhas com índice original <= 199: features idênticas.
    mask_before = fs_before.row_index <= 199
    mask_after = fs_after.row_index <= 199
    assert mask_before.sum() == mask_after.sum()
    assert np.allclose(
        fs_before.X[mask_before], fs_after.X[mask_after], equal_nan=True
    )
    # E alguma linha depois de 200 de fato mudou (o teste não é vazio).
    mask_late = fs_after.row_index >= 250
    assert not np.allclose(
        fs_before.X[fs_before.row_index >= 250],
        fs_after.X[mask_late],
        equal_nan=True,
    )


def test_feature_store_save_load_roundtrip(tmp_path):
    fs = build_feature_matrix(_series(), horizon=1)
    store = FeatureStore()
    store.add("TEST-5m-v1", fs)
    assert "TEST-5m-v1" in store
    assert store.list() == ["TEST-5m-v1"]
    paths = store.save("TEST-5m-v1", tmp_path)
    assert paths["npz"].exists() and paths["json"].exists()

    loaded = FeatureStore.load("TEST-5m-v1", tmp_path)
    assert loaded.version == fs.version
    assert loaded.feature_names == fs.feature_names
    assert np.array_equal(loaded.X, fs.X)
    assert np.array_equal(loaded.y, fs.y)
    assert np.array_equal(loaded.row_index, fs.row_index)
    with pytest.raises(KeyError):
        store.get("inexistente")


def test_chronological_split_keeps_order():
    fs = build_feature_matrix(_series(), horizon=1)
    split = chronological_split(fs.n_rows, 0.6, 0.2)
    (t0, t1), (v0, v1), (s0, s1) = (
        split["train"], split["validation"], split["test"])
    assert t0 == 0 and t1 == v0 and v1 == s0 and s1 == fs.n_rows
    assert t1 > v1 - v0 > 0
