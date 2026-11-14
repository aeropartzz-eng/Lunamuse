"""Testes de Selective Prediction e Concept Drift — Fase 13 (ML-008/ML-009).

Sem rede. Séries sintéticas determinísticas.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml_drift import detect_drift, distribution_shift, psi, psi_report
from ml_features import build_feature_matrix
from ml_selective import find_threshold, selective_metrics, threshold_scan
from synthetic import make_mixed_regime_series

# Alta confiança = acerto; baixa confiança = erro (construído).
Y_TRUE = np.array([1, 0, 1, 0, 0, 1, 0, 1])
Y_PROB = np.array([0.95, 0.05, 0.95, 0.05, 0.60, 0.40, 0.60, 0.40])


def test_selective_reduces_coverage_and_raises_precision():
    low = selective_metrics(Y_TRUE, Y_PROB, threshold=0.55)
    high = selective_metrics(Y_TRUE, Y_PROB, threshold=0.90)
    assert low["coverage"] == pytest.approx(1.0)
    assert low["accuracy_covered"] == pytest.approx(0.5)
    assert high["coverage"] == pytest.approx(0.5)
    assert high["n_covered"] == 4
    assert high["accuracy_covered"] == pytest.approx(1.0)
    assert high["coverage"] < low["coverage"]
    assert high["accuracy_covered"] > low["accuracy_covered"]


def test_selective_empty_coverage_returns_none_precision():
    out = selective_metrics(Y_TRUE, Y_PROB, threshold=0.99)
    assert out["n_covered"] == 0
    assert out["coverage"] == pytest.approx(0.0)
    assert out["accuracy_covered"] is None
    assert out["precision_covered"] is None


def test_threshold_scan_is_monotone_in_coverage():
    scan = threshold_scan(Y_TRUE, Y_PROB)
    coverages = [row["coverage"] for row in scan]
    assert coverages == sorted(coverages, reverse=True)
    assert all("precision_covered" in row for row in scan)


def test_find_threshold_hits_target():
    out = find_threshold(Y_TRUE, Y_PROB, target_precision=0.85, min_coverage=0.25)
    assert out["target_met"] is True
    assert out["precision_covered"] == pytest.approx(1.0)
    assert out["coverage"] >= 0.25
    # Sem limiar viável: não inventa um resultado.
    out2 = find_threshold(Y_TRUE, Y_PROB, target_precision=0.99, min_coverage=0.9)
    assert out2["target_met"] is False


def test_psi_identical_is_zero():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, 500)
    assert psi(x, x.copy()) == pytest.approx(0.0)
    assert psi(x, rng.normal(0, 1, 500)) < 0.10  # mesma distribuição


def test_drift_detected_on_regime_change():
    up = make_mixed_regime_series(
        seed=11, regimes=[("TREND_UP", 400, 0.004, 0.006)])
    flat = make_mixed_regime_series(
        seed=12, regimes=[("RANGE", 400, 0.0, 0.008)])
    X_up = build_feature_matrix(up, horizon=1).X
    X_flat = build_feature_matrix(flat, horizon=1).X
    names = build_feature_matrix(up, horizon=1).feature_names
    result = detect_drift(X_up, X_flat, names)
    assert result["drift_detected"] is True
    assert result["max_psi"] >= 0.25
    assert result["alert"] is not None
    assert "PSI" in result["alert"]
    assert result["n_drifted_features"] >= 1


def test_no_drift_on_same_distribution():
    rng = np.random.default_rng(0)
    X_ref = rng.normal(0, 1, size=(400, 5))
    X_rec = rng.normal(0, 1, size=(400, 5))
    result = detect_drift(X_ref, X_rec, [f"f{i}" for i in range(5)])
    assert result["drift_detected"] is False
    assert result["max_psi"] < 0.25
    assert result["alert"] is None


def test_psi_report_sorted_and_levels():
    rng = np.random.default_rng(0)
    X_ref = rng.normal(0, 1, size=(300, 2))
    X_rec = rng.normal(0, 1, size=(300, 2))
    X_rec[:, 0] += 5.0  # deslocamento grande na feature 0
    report = psi_report(X_ref, X_rec, ["a", "b"])
    assert report[0]["feature"] == "a"
    assert report[0]["psi"] > report[1]["psi"]
    assert report[0]["level"] == "significativo"
    shifts = distribution_shift(X_ref, X_rec, ["a", "b"])
    assert abs(shifts[0]["mean_shift_std"]) > 4.0
