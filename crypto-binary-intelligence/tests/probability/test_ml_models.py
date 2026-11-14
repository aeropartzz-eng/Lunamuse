"""Testes dos modelos — Fase 13 (ML-002…ML-005).

Sem rede. Séries sintéticas determinísticas. Se xgboost/lightgbm
não estiverem instalados, os testes aceitam o modelo como "fora"
com motivo — mas nunca aceitam um resultado inventado.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml_features import build_feature_matrix
from ml_models import (
    AVAILABLE_MODELS,
    MODEL_REGISTRY,
    get_model,
    train_models,
)
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
    split = chronological_split(fs.n_rows, 0.6, 0.2)
    tr = split["train"]
    te = split["test"]
    return (
        fs.X[tr[0]:tr[1]], fs.y[tr[0]:tr[1]],
        fs.X[te[0]:te[1]], fs.y[te[0]:te[1]],
    )


def test_train_models_interface(split_data):
    X_train, y_train, X_test, y_test = split_data
    result = train_models(X_train, y_train)
    trained, skipped = result["trained"], result["skipped"]
    # Baseline linear e floresta sempre disponíveis (scikit-learn).
    assert "logistic_regression" in trained
    assert "random_forest" in trained
    for name in ("xgboost", "lightgbm"):
        assert name in trained or name in skipped
        if name in skipped:
            assert "não instalado" in skipped[name]
    assert set(trained) | set(skipped) == set(MODEL_REGISTRY)
    for name, model in trained.items():
        assert model.is_fitted
        proba = model.predict_proba(X_test)
        assert proba.shape == (len(y_test), 2)
        assert np.allclose(proba.sum(axis=1), 1.0)
        assert ((proba >= 0.0) & (proba <= 1.0)).all()
        pred = model.predict(X_test)
        assert set(np.unique(pred)) <= {0, 1}
        assert len(pred) == len(y_test)


def test_available_models_flags_match_registry():
    for name in MODEL_REGISTRY:
        assert name in AVAILABLE_MODELS
    assert AVAILABLE_MODELS["logistic_regression"] is True
    assert AVAILABLE_MODELS["random_forest"] is True


def test_get_model_unknown_raises():
    with pytest.raises(ValueError, match="desconhecido"):
        get_model("lstm")


def test_predict_before_fit_raises():
    model = get_model("logistic_regression")
    with pytest.raises(RuntimeError, match="não foi treinado"):
        model.predict(np.zeros((2, 29)))


def test_fit_requires_two_classes():
    model = get_model("logistic_regression")
    with pytest.raises(ValueError, match="duas classes"):
        model.fit(np.zeros((10, 29)), np.zeros(10, dtype=int))
