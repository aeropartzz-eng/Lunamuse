"""Testes de calibração e métricas — Fase 13 (ML-006/ML-007).

Sem rede. Valores de Brier/Log Loss conferidos à mão.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from ml_calibration import (
    CalibratedModel,
    calibration_curve,
    calibration_error,
    compare_calibration,
)
from ml_metrics import (
    brier_score,
    evaluate_classifier,
    log_loss,
    precision_recall_f1,
    trade_expectancy,
    wilson_ci,
)


class ExtremeClassifier:
    """Classificador propositalmente superconfiante: prevê 0,99 ou
    0,01 conforme o sinal de X[:, 0]. A taxa real de acerto dessas
    chamadas é ~70% — a calibração deve aproximar as probabilidades
    de 0,7/0,3 e melhorar o Brier."""

    name = "extreme"

    def __init__(self):
        self.classes_ = np.array([0, 1])

    def fit(self, X, y):
        return self

    def predict_proba(self, X):
        p = np.where(np.asarray(X)[:, 0] > 0, 0.99, 0.01)
        return np.column_stack([1.0 - p, p])


def _extreme_data(seed, n):
    rng = np.random.default_rng(seed)
    X = rng.normal(0.0, 1.0, size=(n, 1))
    signal = X[:, 0] > 0
    p_true = np.where(signal, 0.7, 0.3)
    y = (rng.random(n) < p_true).astype(int)
    return X, y


def test_brier_and_logloss_hand_computed():
    y = np.array([0, 1])
    p = np.array([0.25, 0.75])
    assert brier_score(y, p) == pytest.approx(0.0625)
    assert log_loss(y, p) == pytest.approx(
        -math.log(0.75), abs=1e-9
    )
    assert brier_score(y, np.array([0.5, 0.5])) == pytest.approx(0.25)


def test_precision_recall_f1_hand_computed():
    y_true = np.array([1, 1, 0, 0, 1])
    y_pred = np.array([1, 0, 1, 0, 1])
    out = precision_recall_f1(y_true, y_pred)
    assert out["precision"] == pytest.approx(2 / 3)
    assert out["recall"] == pytest.approx(2 / 3)
    assert out["tp"] == 2 and out["fp"] == 1 and out["fn"] == 1


def test_wilson_ci_contains_estimate():
    ci = wilson_ci(85, 100)
    assert ci is not None
    assert ci["low"] < 0.85 < ci["high"]
    assert 0.0 <= ci["low"] and ci["high"] <= 1.0
    assert wilson_ci(0, 0) is None


def test_trade_expectancy_hand_computed():
    fut = np.array([0.01, -0.02, 0.005])
    pred = np.array([1, 1, 0])
    out = trade_expectancy(fut, pred, cost_bps=0.0)
    assert out["n_trades"] == 2
    assert out["win_rate"] == pytest.approx(0.5)
    assert out["expectancy_per_trade"] == pytest.approx(-0.005)
    # Com custo de 30 bps, os dois trades perdem 0,003 cada.
    out_cost = trade_expectancy(fut, pred, cost_bps=30.0)
    assert out_cost["expectancy_per_trade"] == pytest.approx(-0.008)
    # Sem trades previstos: zeros, sem erro.
    assert trade_expectancy(fut, np.zeros(3, dtype=int))["n_trades"] == 0


def test_calibration_improves_brier_on_overconfident_model():
    X_cal, y_cal = _extreme_data(seed=1, n=1000)
    X_test, y_test = _extreme_data(seed=2, n=1000)
    base = ExtremeClassifier().fit(X_cal, y_cal)
    raw = base.predict_proba(X_test)[:, 1]

    cal = CalibratedModel(base, method="sigmoid").fit(X_cal, y_cal)
    calibrated = cal.predict_proba(X_test)[:, 1]

    comp = compare_calibration(y_test, raw, calibrated)
    assert comp["brier_improved"] is True
    assert comp["brier_calibrated"] < comp["brier_raw"] - 0.03
    assert comp["ece_calibrated"] < comp["ece_raw"]
    assert ((calibrated >= 0.0) & (calibrated <= 1.0)).all()


def test_calibration_isotonic_runs():
    X_cal, y_cal = _extreme_data(seed=3, n=500)
    X_test, y_test = _extreme_data(seed=4, n=500)
    base = ExtremeClassifier().fit(X_cal, y_cal)
    cal = CalibratedModel(base, method="isotonic").fit(X_cal, y_cal)
    proba = cal.predict_proba(X_test)
    assert proba.shape == (500, 2)
    assert np.allclose(proba.sum(axis=1), 1.0)
    assert brier_score(y_test, proba[:, 1]) < brier_score(
        y_test, base.predict_proba(X_test)[:, 1]
    )


def test_calibration_rejects_bad_calibration_sets():
    X, y = _extreme_data(seed=5, n=100)
    base = ExtremeClassifier()
    with pytest.raises(ValueError, match="duas classes"):
        CalibratedModel(base).fit(X, np.zeros(100, dtype=int))
    with pytest.raises(ValueError, match="pequeno demais"):
        CalibratedModel(base).fit(X[:10], y[:10])
    with pytest.raises(ValueError, match="sigmoid.*isotonic"):
        CalibratedModel(base, method="platt")


def test_calibration_curve_counts():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.8, 0.9])
    curve = calibration_curve(y, p, n_bins=2)
    assert sum(r["count"] for r in curve) == 4
    assert curve[0]["frac_positive"] == pytest.approx(0.0)
    assert curve[-1]["frac_positive"] == pytest.approx(1.0)
    assert calibration_error(y, p, n_bins=2) == pytest.approx(0.15)


def test_evaluate_classifier_summary():
    y_true = np.array([1, 1, 0, 0])
    y_pred = np.array([1, 0, 0, 0])
    y_prob = np.array([0.9, 0.4, 0.2, 0.1])
    ev = evaluate_classifier(y_true, y_pred, y_prob)
    assert ev["n"] == 4
    assert ev["accuracy"] == pytest.approx(0.75)
    assert ev["precision"] == pytest.approx(1.0)
    assert ev["recall"] == pytest.approx(0.5)
    assert ev["brier_score"] == pytest.approx(
        float(np.mean((y_prob - y_true) ** 2))
    )
