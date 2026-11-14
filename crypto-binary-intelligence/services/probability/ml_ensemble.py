"""Ensemble — Fase 13 (ML-010), §8.

Combinação dos modelos da Fase 13 com comparação honesta contra o
melhor modelo individual:

- ``EnsembleModel``: média ponderada das probabilidades dos modelos
  base (pesos iguais por padrão; ``fit_ensemble_weights`` otimiza os
  pesos na **validação** minimizando o Brier Score — nunca no teste).
- ``StackingModel``: meta-aprendiz (Regressão Logística) sobre as
  probabilidades dos modelos base na validação.
- ``compare``: tabela de métricas (Brier, Log Loss, acurácia) por
  modelo + ensemble, com o melhor individual marcado — o ensemble
  só é "melhor" se vencer nessa tabela, fora da amostra.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

try:
    from sklearn.linear_model import LogisticRegression

    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False  # type: ignore[assignment]

try:
    from ml_metrics import brier_score, evaluate_classifier, log_loss
except ImportError:
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.append(str(_Path(__file__).resolve().parent))
    from ml_metrics import brier_score, evaluate_classifier, log_loss

__all__ = [
    "EnsembleModel",
    "StackingModel",
    "fit_ensemble_weights",
    "compare",
]


class EnsembleModel:
    """Média ponderada das probabilidades dos modelos base."""

    def __init__(
        self,
        models: Sequence[Any],
        weights: Optional[Sequence[float]] = None,
    ) -> None:
        if not models:
            raise ValueError("ensemble precisa de ao menos um modelo")
        self.models = list(models)
        if weights is None:
            self.weights = np.full(len(models), 1.0 / len(models))
        else:
            w = np.asarray(weights, dtype=float)
            if len(w) != len(models):
                raise ValueError("weights com tamanho diferente do nº de modelos")
            if np.any(w < 0) or w.sum() <= 0:
                raise ValueError("weights devem ser >= 0 e somar > 0")
            self.weights = w / w.sum()
        self.is_fitted = all(
            getattr(m, "is_fitted", False) for m in self.models
        )

    @property
    def name(self) -> str:
        return "ensemble_weighted"

    def fit(self, X: np.ndarray, y: np.ndarray) -> "EnsembleModel":
        for m in self.models:
            m.fit(X, y)
        self.is_fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("ensemble ainda não foi treinado (fit)")
        X = np.asarray(X, dtype=float)
        proba = np.zeros((len(X), 2))
        for w, m in zip(self.weights, self.models):
            proba += w * np.asarray(m.predict_proba(X), dtype=float)
        return proba

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def fit_ensemble_weights(
    models: Sequence[Any],
    X_val: np.ndarray,
    y_val: np.ndarray,
    n_iter: int = 2000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Otimiza os pesos do ensemble na validação (busca aleatória
    determinística sobre o simplex, minimizando o Brier Score).

    Devolve ``weights`` (na ordem dos modelos), ``brier_val`` do
    melhor peso e o ``brier_val`` dos pesos iguais, para comparação.
    """
    X_val = np.asarray(X_val, dtype=float)
    y_val = np.asarray(y_val).astype(int)
    probas = [np.asarray(m.predict_proba(X_val), dtype=float)[:, 1] for m in models]
    rng = np.random.default_rng(seed)
    equal_w = np.full(len(models), 1.0 / len(models))
    best_w = equal_w.copy()
    best_brier = brier_score(y_val, sum(w * p for w, p in zip(equal_w, probas)))
    for _ in range(n_iter):
        w = rng.dirichlet(np.ones(len(models)))
        mixed = sum(wi * p for wi, p in zip(w, probas))
        b = brier_score(y_val, mixed)
        if b < best_brier:
            best_brier = b
            best_w = w
    return {
        "weights": [float(x) for x in best_w],
        "brier_val": float(best_brier),
        "brier_val_equal_weights": float(
            brier_score(y_val, sum(w * p for w, p in zip(equal_w, probas)))
        ),
    }


class StackingModel:
    """Stacking simples: meta-aprendiz logístico sobre as
    probabilidades dos modelos base.

    ``fit`` treina os modelos base no treino e o meta-aprendiz nas
    probabilidades dos modelos base sobre o conjunto meta
    (validação cronológica — nunca o teste).
    """

    def __init__(self, models: Sequence[Any]) -> None:
        if not models:
            raise ValueError("stacking precisa de ao menos um modelo base")
        self.models = list(models)
        self._meta: Any = None
        self.is_fitted = False

    @property
    def name(self) -> str:
        return "ensemble_stacking"

    def fit(
        self, X_train: np.ndarray, y_train: np.ndarray,
        X_meta: np.ndarray, y_meta: np.ndarray,
    ) -> "StackingModel":
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn não instalado — instale com: pip install scikit-learn")
        for m in self.models:
            m.fit(X_train, y_train)
        meta_X = np.column_stack([
            np.asarray(m.predict_proba(X_meta), dtype=float)[:, 1]
            for m in self.models
        ])
        self._meta = LogisticRegression(max_iter=1000, random_state=42)
        self._meta.fit(meta_X, np.asarray(y_meta).astype(int))
        self.is_fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self._meta is None:
            raise RuntimeError("stacking ainda não foi treinado (fit)")
        meta_X = np.column_stack([
            np.asarray(m.predict_proba(X), dtype=float)[:, 1]
            for m in self.models
        ])
        return np.asarray(self._meta.predict_proba(meta_X), dtype=float)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)


def compare(
    y_true: np.ndarray,
    probas: Dict[str, np.ndarray],
    y_pred: Optional[Dict[str, np.ndarray]] = None,
) -> List[Dict[str, Any]]:
    """Tabela de comparação honesta (fora da amostra).

    Cada linha: modelo, acurácia, Brier, Log Loss. A última coluna
    marca o melhor por Brier (menor). O ensemble só é declarado
    melhor se vencer aqui.
    """
    y_true = np.asarray(y_true).astype(int)
    rows: List[Dict[str, Any]] = []
    for name, p in probas.items():
        p1 = np.asarray(p, dtype=float)[:, 1]
        pred = (
            np.asarray(y_pred[name]).astype(int) if y_pred and name in y_pred
            else (p1 >= 0.5).astype(int)
        )
        ev = evaluate_classifier(y_true, pred, p1)
        rows.append({
            "model": name,
            "accuracy": ev["accuracy"],
            "precision": ev["precision"],
            "recall": ev["recall"],
            "brier_score": ev["brier_score"],
            "log_loss": ev["log_loss"],
            "n": ev["n"],
        })
    rows.sort(key=lambda r: r["brier_score"])
    for i, row in enumerate(rows):
        row["rank_brier"] = i + 1
        row["best_brier"] = i == 0
    return rows
