"""Testes de Ensemble e do relatório do 85% — Fase 13 (ML-010/ML-011).

Sem rede. Séries sintéticas determinísticas.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml_ensemble import (
    EnsembleModel,
    StackingModel,
    compare,
    fit_ensemble_weights,
)
from ml_features import build_feature_matrix
from ml_models import train_models
from ml_report import generate_85_report
from splits import chronological_split
from synthetic import make_mixed_regime_series

REGIMES = [
    ("TREND_UP", 200, 0.004, 0.006),
    ("RANGE", 200, 0.0, 0.008),
]


@pytest.fixture(scope="module")
def split_data():
    candles = make_mixed_regime_series(seed=42, regimes=REGIMES)
    fs = build_feature_matrix(candles, horizon=1)
    s = chronological_split(fs.n_rows, 0.6, 0.2)
    tr, va, te = s["train"], s["validation"], s["test"]
    return {
        "X_train": fs.X[tr[0]:tr[1]], "y_train": fs.y[tr[0]:tr[1]],
        "X_val": fs.X[va[0]:va[1]], "y_val": fs.y[va[0]:va[1]],
        "X_test": fs.X[te[0]:te[1]], "y_test": fs.y[te[0]:te[1]],
    }


def _model_table_best():
    return [
        {"model": "logistic_regression", "accuracy": 0.68, "precision": 0.68,
         "recall": 1.0, "brier_score": 0.22, "log_loss": 0.63,
         "brier_calibrated": 0.22, "log_loss_calibrated": 0.63,
         "win_rate": 0.49, "expectancy_bps": -2.0, "n": 642},
    ]


def _scan():
    return [
        {"threshold": 0.60, "n_total": 100, "n_covered": 80,
         "coverage": 0.8, "accuracy_covered": 0.70, "precision_covered": 0.70},
        {"threshold": 0.85, "n_total": 100, "n_covered": 10,
         "coverage": 0.10, "accuracy_covered": 0.90, "precision_covered": 0.90},
    ]


def test_ensemble_runs_and_weights_sum_to_one(split_data):
    d = split_data
    trained = train_models(
        d["X_train"], d["y_train"], names=["logistic_regression", "random_forest"]
    )["trained"]
    models = [trained["logistic_regression"], trained["random_forest"]]
    weights = fit_ensemble_weights(models, d["X_val"], d["y_val"])
    assert abs(sum(weights["weights"]) - 1.0) < 1e-9
    assert weights["brier_val"] <= weights["brier_val_equal_weights"] + 1e-9
    ens = EnsembleModel(models, weights=weights["weights"])
    proba = ens.predict_proba(d["X_test"])
    assert proba.shape == (len(d["y_test"]), 2)
    assert np.allclose(proba.sum(axis=1), 1.0)


def test_ensemble_equal_weights_default(split_data):
    d = split_data
    trained = train_models(
        d["X_train"], d["y_train"], names=["logistic_regression", "random_forest"]
    )["trained"]
    models = list(trained.values())
    ens = EnsembleModel(models)
    assert np.allclose(ens.weights, [0.5, 0.5])
    with pytest.raises(ValueError, match="ao menos um modelo"):
        EnsembleModel([])


def test_stacking_runs(split_data):
    d = split_data
    trained = train_models(
        d["X_train"], d["y_train"], names=["logistic_regression", "random_forest"]
    )["trained"]
    stacking = StackingModel(list(trained.values()))
    stacking.fit(d["X_train"], d["y_train"], d["X_val"], d["y_val"])
    proba = stacking.predict_proba(d["X_test"])
    assert proba.shape == (len(d["y_test"]), 2)
    assert np.allclose(proba.sum(axis=1), 1.0)


def test_compare_ranks_by_brier(split_data):
    d = split_data
    y = d["y_test"]
    probas = {
        "a": np.column_stack([1 - np.full(len(y), 0.4), np.full(len(y), 0.4)]),
        "b": np.column_stack([1 - np.full(len(y), 0.6), np.full(len(y), 0.6)]),
    }
    table = compare(y, probas)
    assert table[0]["rank_brier"] == 1
    assert table[0]["best_brier"] is True
    assert table[0]["brier_score"] <= table[1]["brier_score"]


def test_report_marks_synthetic_and_verdict_not_met(tmp_path):
    out = tmp_path / "relatorio-85.md"
    verdict = generate_85_report(
        out,
        model_table=_model_table_best(),
        best_model_name="logistic_regression",
        selective_scan=_scan(),
        selective_best={"threshold": 0.85, "precision_covered": 0.70,
                        "accuracy_covered": 0.70, "coverage": 0.10,
                        "n_covered": 10, "target_met": False},
        ensemble_table=[{"model": "logistic_regression", "accuracy": 0.68,
                         "brier_score": 0.22, "log_loss": 0.63,
                         "rank_brier": 1, "best_brier": True}],
        drift={"max_psi": 0.05, "mean_psi": 0.02, "drift_detected": False,
               "threshold": 0.25, "alert": None, "per_feature": []},
        dataset_info={"feature_version": "v1", "n_features": 29, "horizon": 1,
                      "symbols": "BTC/USDT", "timeframe": "5m", "seeds": "42",
                      "n_train": 100, "n_val": 50, "n_test": 100},
        costs_bps=30.0,
    )
    text = out.read_text(encoding="utf-8")
    assert "DADOS SINTÉTICOS" in text
    assert "NÃO ATINGIDA" in text
    assert verdict["target_met"] is False
    assert verdict["best_selective_precision"] == pytest.approx(0.70)
    assert "IC 95%" in text or "95%" in text


def test_report_verdict_met_only_with_all_criteria(tmp_path):
    out = tmp_path / "relatorio-85.md"
    good_table = [
        {**_model_table_best()[0], "expectancy_bps": 5.0, "win_rate": 0.60}
    ]
    verdict = generate_85_report(
        out,
        model_table=good_table,
        best_model_name="logistic_regression",
        selective_scan=_scan(),
        selective_best={"threshold": 0.85, "precision_covered": 0.90,
                        "accuracy_covered": 0.90, "coverage": 0.60,
                        "n_covered": 600, "target_met": True},
        ensemble_table=[{"model": "logistic_regression", "accuracy": 0.68,
                         "brier_score": 0.22, "log_loss": 0.63,
                         "rank_brier": 1, "best_brier": True}],
        drift={"max_psi": 0.05, "mean_psi": 0.02, "drift_detected": False,
               "threshold": 0.25, "alert": None, "per_feature": []},
        dataset_info={"feature_version": "v1", "n_features": 29, "horizon": 1,
                      "symbols": "BTC/USDT", "timeframe": "5m", "seeds": "42",
                      "n_train": 100, "n_val": 50, "n_test": 1000},
        costs_bps=30.0,
    )
    text = out.read_text(encoding="utf-8")
    assert verdict["target_met"] is True
    assert "ATINGIDA" in text
    assert "DADOS SINTÉTICOS" in text
