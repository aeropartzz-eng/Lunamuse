"""Modelos probabilísticos — Fase 13 (ML-002…ML-005), §8.

Quatro modelos com a **mesma interface** (``fit`` / ``predict`` /
``predict_proba``) e o mesmo split cronológico da Fase 12
(``splits.chronological_split`` — o split é feito fora, no
pipeline, e passado já dividido para :func:`train_models`):

- ML-002 Logistic Regression (scikit-learn, com StandardScaler);
- ML-003 Random Forest (scikit-learn);
- ML-004 XGBoost;
- ML-005 LightGBM.

Disponibilidade: scikit-learn já faz parte do stack (§8). XGBoost
e LightGBM são opcionais — se o import falhar neste ambiente, o
modelo fica marcado como indisponível em ``AVAILABLE_MODELS`` e
:func:`get_model` levanta ``RuntimeError`` explicando como
instalar, em vez de fingir que treinou. Nenhum modelo é
instanciado "de mentira".

Só pesquisa com dados sintéticos; nenhum modelo envia ordens.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

import numpy as np

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False  # type: ignore[assignment]

try:
    from xgboost import XGBClassifier

    _XGBOOST_AVAILABLE = True
except ImportError:
    _XGBOOST_AVAILABLE = False  # type: ignore[assignment]

try:
    from lightgbm import LGBMClassifier

    _LIGHTGBM_AVAILABLE = True
except ImportError:
    _LIGHTGBM_AVAILABLE = False  # type: ignore[assignment]

__all__ = [
    "BaseMLModel",
    "LogisticRegressionModel",
    "RandomForestModel",
    "XGBoostModel",
    "LightGBMModel",
    "MODEL_REGISTRY",
    "AVAILABLE_MODELS",
    "SKLEARN_AVAILABLE",
    "XGBOOST_AVAILABLE",
    "LIGHTGBM_AVAILABLE",
    "get_model",
    "train_models",
]

SKLEARN_AVAILABLE = _SKLEARN_AVAILABLE
XGBOOST_AVAILABLE = _XGBOOST_AVAILABLE
LIGHTGBM_AVAILABLE = _LIGHTGBM_AVAILABLE

_RANDOM_STATE = 42


class BaseMLModel:
    """Interface comum de todos os modelos (ML-002…ML-005).

    ``fit(X, y)`` treina; ``predict(X)`` devolve a classe (0/1);
    ``predict_proba(X)`` devolve ``(n, 2)`` com a probabilidade da
    classe 1 em ``[:, 1]``. ``name`` identifica o modelo nos
    relatórios.
    """

    name: str = "base"

    def __init__(self) -> None:
        self._estimator: Any = None
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BaseMLModel":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y).astype(int)
        if X.shape[0] != len(y):
            raise ValueError("X e y com números de linhas diferentes")
        if len(np.unique(y)) < 2:
            raise ValueError("y precisa das duas classes (0 e 1) para treinar")
        self._estimator = self._build()
        self._estimator.fit(X, y)
        self.is_fitted = True
        return self

    def _build(self) -> Any:
        raise NotImplementedError

    def _check_fitted(self) -> None:
        if not self.is_fitted or self._estimator is None:
            raise RuntimeError(f"modelo {self.name} ainda não foi treinado (fit)")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        self._check_fitted()
        proba = np.asarray(self._estimator.predict_proba(np.asarray(X, dtype=float)), dtype=float)
        # Garante colunas [P(0), P(1)] mesmo se o estimador devolver
        # só uma classe (não deve acontecer após o treino com 2 classes).
        if proba.shape[1] == 1:
            proba = np.column_stack([1.0 - proba[:, 0], proba[:, 0]])
        return proba

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    @property
    def feature_importances_(self) -> Optional[Dict[str, float]]:
        """Importância por feature (quando o estimador oferece)."""
        return None


class LogisticRegressionModel(BaseMLModel):
    """ML-002 — Regressão Logística (baseline linear)."""

    name = "logistic_regression"

    def _build(self) -> Any:
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn não instalado — instale com: pip install scikit-learn")
        return Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, C=1.0, random_state=_RANDOM_STATE)),
        ])


class RandomForestModel(BaseMLModel):
    """ML-003 — Random Forest."""

    name = "random_forest"

    def __init__(self, n_estimators: int = 200) -> None:
        super().__init__()
        self.n_estimators = n_estimators

    def _build(self) -> Any:
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn não instalado — instale com: pip install scikit-learn")
        return RandomForestClassifier(
            n_estimators=self.n_estimators,
            min_samples_leaf=5,
            random_state=_RANDOM_STATE,
            n_jobs=-1,
        )

    @property
    def feature_importances_(self) -> Optional[Dict[str, float]]:
        if not self.is_fitted:
            return None
        importances = getattr(self._estimator, "feature_importances_", None)
        return None if importances is None else {"importances": importances}


class XGBoostModel(BaseMLModel):
    """ML-004 — XGBoost (indisponível se o pacote não instalar)."""

    name = "xgboost"

    def __init__(self, n_estimators: int = 200) -> None:
        super().__init__()
        self.n_estimators = n_estimators

    def _build(self) -> Any:
        if not _XGBOOST_AVAILABLE:
            raise RuntimeError(
                "xgboost não instalado neste ambiente — instale com: "
                "pip install xgboost (e re-treine; nenhum resultado de "
                "XGBoost foi gerado sem o pacote)"
            )
        return XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=_RANDOM_STATE,
            n_jobs=-1,
        )


class LightGBMModel(BaseMLModel):
    """ML-005 — LightGBM (indisponível se o pacote não instalar)."""

    name = "lightgbm"

    def __init__(self, n_estimators: int = 200) -> None:
        super().__init__()
        self.n_estimators = n_estimators

    def _build(self) -> Any:
        if not _LIGHTGBM_AVAILABLE:
            raise RuntimeError(
                "lightgbm não instalado neste ambiente — instale com: "
                "pip install lightgbm (e re-treine; nenhum resultado de "
                "LightGBM foi gerado sem o pacote)"
            )
        return LGBMClassifier(
            n_estimators=self.n_estimators,
            num_leaves=31,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=_RANDOM_STATE,
            verbose=-1,
            n_jobs=-1,
        )


MODEL_REGISTRY: Dict[str, Type[BaseMLModel]] = {
    "logistic_regression": LogisticRegressionModel,
    "random_forest": RandomForestModel,
    "xgboost": XGBoostModel,
    "lightgbm": LightGBMModel,
}

AVAILABLE_MODELS: Dict[str, bool] = {
    "logistic_regression": _SKLEARN_AVAILABLE,
    "random_forest": _SKLEARN_AVAILABLE,
    "xgboost": _XGBOOST_AVAILABLE,
    "lightgbm": _LIGHTGBM_AVAILABLE,
}


def get_model(name: str, **params: Any) -> BaseMLModel:
    """Instancia um modelo pelo nome; erro claro se indisponível."""
    if name not in MODEL_REGISTRY:
        raise ValueError(f"modelo desconhecido: {name!r} (conhecidos: {sorted(MODEL_REGISTRY)})")
    if not AVAILABLE_MODELS[name]:
        # Instancia só para obter a mensagem de erro honesta do _build.
        MODEL_REGISTRY[name](**params)._build()
    return MODEL_REGISTRY[name](**params)


def train_models(
    X_train: np.ndarray,
    y_train: np.ndarray,
    names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Treina os modelos pedidos (padrão: todos os disponíveis).

    Devolve ``{"trained": {nome: modelo}, "skipped": {nome: motivo}}``.
    Modelos indisponíveis entram em ``skipped`` — nunca em ``trained``.
    """
    wanted = list(names) if names is not None else sorted(MODEL_REGISTRY)
    trained: Dict[str, BaseMLModel] = {}
    skipped: Dict[str, str] = {}
    for name in wanted:
        if name not in MODEL_REGISTRY:
            skipped[name] = f"modelo desconhecido: {name!r}"
            continue
        if not AVAILABLE_MODELS[name]:
            skipped[name] = "pacote não instalado neste ambiente"
            continue
        model = MODEL_REGISTRY[name]()
        model.fit(X_train, y_train)
        trained[name] = model
    return {"trained": trained, "skipped": skipped}
