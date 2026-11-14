"""Calibração de probabilidade — Fase 13 (ML-006), §8.

Probabilidade calibrada é o que alimenta o Signal Engine — nunca
operar com probabilidade não calibrada (premissa 7). A calibração
ajusta as probabilidades cruas do modelo para ficarem próximas das
taxas reais observadas, medida por Brier Score / Log Loss e pela
curva de calibração.

- ``CalibratedModel``: envolve um modelo já treinado e calibra com
  Platt scaling (``"sigmoid"``: regressão logística sobre a
  probabilidade crua) ou regressão isotônica (``"isotonic"``),
  ajustadas num conjunto de **calibração separado** (a validação
  cronológica — nunca o teste, que não participa de nenhum ajuste,
  conforme o protocolo do 85%). A implementação é direta sobre as
  probabilidades cruas (sem ``CalibratedClassifierCV``, cujo
  ``cv="prefit"`` foi removido no scikit-learn 1.9) — o que também
  deixa a fórmula auditável.
- ``calibration_curve`` / ``calibration_error`` (ECE): cálculo puro
  em NumPy, sem depender de versão do sklearn.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

try:
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression

    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False  # type: ignore[assignment]

try:
    from ml_metrics import brier_score, log_loss
except ImportError:  # importado fora do sys.path do serviço
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.append(str(_Path(__file__).resolve().parent))
    from ml_metrics import brier_score, log_loss

__all__ = [
    "CalibratedModel",
    "calibration_curve",
    "calibration_error",
    "compare_calibration",
]


def calibration_curve(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> List[Dict[str, float]]:
    """Curva de calibração: por faixa de probabilidade prevista, a
    probabilidade média prevista vs. a taxa real observada.

    Devolve uma linha por faixa: ``bin``, ``mean_predicted``,
    ``frac_positive`` e ``count``. Faixas vazias são omitidas.
    """
    y_true = np.asarray(y_true).astype(float)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) != len(y_prob):
        raise ValueError("y_true e y_prob com tamanhos diferentes")
    if len(y_true) == 0:
        raise ValueError("série vazia")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows: List[Dict[str, float]] = []
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        mask = (y_prob >= lo) & (y_prob < hi) if b < n_bins - 1 else (y_prob >= lo) & (y_prob <= hi)
        if not mask.any():
            continue
        rows.append({
            "bin": float((lo + hi) / 2.0),
            "bin_low": float(lo),
            "bin_high": float(hi),
            "mean_predicted": float(np.mean(y_prob[mask])),
            "frac_positive": float(np.mean(y_true[mask])),
            "count": int(mask.sum()),
        })
    return rows


def calibration_error(
    y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10
) -> float:
    """ECE — Expected Calibration Error (média ponderada de
    |previsto - observado| por faixa). Quanto menor, melhor."""
    curve = calibration_curve(y_true, y_prob, n_bins=n_bins)
    n = len(y_true)
    if n == 0:
        return float("nan")
    return float(sum(
        abs(r["mean_predicted"] - r["frac_positive"]) * r["count"] / n
        for r in curve
    ))


def compare_calibration(
    y_true: np.ndarray, proba_raw: np.ndarray, proba_cal: np.ndarray
) -> Dict[str, Any]:
    """Compara probabilidade crua vs. calibrada (Brier, Log Loss, ECE)."""
    return {
        "brier_raw": brier_score(y_true, proba_raw),
        "brier_calibrated": brier_score(y_true, proba_cal),
        "log_loss_raw": log_loss(y_true, proba_raw),
        "log_loss_calibrated": log_loss(y_true, proba_cal),
        "ece_raw": calibration_error(y_true, proba_raw),
        "ece_calibrated": calibration_error(y_true, proba_cal),
        "brier_improved": bool(
            brier_score(y_true, proba_cal) < brier_score(y_true, proba_raw)
        ),
    }


class CalibratedModel:
    """Envolve um modelo treinado e calibra suas probabilidades.

    Platt scaling (``method="sigmoid"``): regressão logística
    ajustada sobre a probabilidade crua do modelo base no conjunto
    de calibração. Isotônica (``method="isotonic"``): regressão
    isotônica sobre a mesma variável (exige mais dados; o ``fit``
    rejeita conjuntos com menos de 50 amostras).

    Uso: ``CalibratedModel(modelo_treinado, method="sigmoid")`` e
    depois ``fit(X_cal, y_cal)`` com o conjunto de calibração
    (validação cronológica). ``predict_proba`` devolve as
    probabilidades **calibradas**; ``predict`` usa o limiar 0,5
    sobre elas.
    """

    def __init__(self, base_model: Any, method: str = "sigmoid") -> None:
        if method not in ("sigmoid", "isotonic"):
            raise ValueError(f"method deve ser 'sigmoid' ou 'isotonic', recebido {method!r}")
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn não instalado — instale com: pip install scikit-learn")
        self.base_model = base_model
        self.method = method
        self._calibrator: Any = None
        self.is_fitted: bool = False

    @property
    def name(self) -> str:
        return f"{getattr(self.base_model, 'name', 'model')}_calibrated_{self.method}"

    def fit(self, X_cal: np.ndarray, y_cal: np.ndarray) -> "CalibratedModel":
        X_cal = np.asarray(X_cal, dtype=float)
        y_cal = np.asarray(y_cal).astype(int)
        if len(np.unique(y_cal)) < 2:
            raise ValueError("conjunto de calibração precisa das duas classes (0 e 1)")
        if len(y_cal) < 50:
            raise ValueError(
                f"conjunto de calibração pequeno demais para {self.method}: "
                f"{len(y_cal)} amostras (mínimo 50)"
            )
        raw = np.asarray(self.base_model.predict_proba(X_cal), dtype=float)[:, 1]
        if self.method == "sigmoid":
            self._calibrator = LogisticRegression(C=1.0, max_iter=1000)
            self._calibrator.fit(raw.reshape(-1, 1), y_cal)
        else:
            self._calibrator = IsotonicRegression(out_of_bounds="clip")
            self._calibrator.fit(raw, y_cal)
        self.is_fitted = True
        return self

    def _calibrate(self, raw_proba: np.ndarray) -> np.ndarray:
        if self.method == "sigmoid":
            return np.asarray(
                self._calibrator.predict_proba(raw_proba.reshape(-1, 1)),
                dtype=float,
            )[:, 1]
        return np.asarray(self._calibrator.predict(raw_proba), dtype=float)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self._calibrator is None:
            raise RuntimeError("modelo calibrado ainda não foi ajustado (fit)")
        raw = np.asarray(self.base_model.predict_proba(X), dtype=float)[:, 1]
        cal = np.clip(self._calibrate(raw), 0.0, 1.0)
        return np.column_stack([1.0 - cal, cal])

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)

    def predict_proba_raw(self, X: np.ndarray) -> np.ndarray:
        """Probabilidades cruas do modelo base (para comparação)."""
        return np.asarray(self.base_model.predict_proba(X), dtype=float)
