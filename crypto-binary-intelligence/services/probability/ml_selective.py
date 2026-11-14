"""Selective Prediction — Fase 13 (ML-008), §8 e protocolo do 85%.

Só emitir previsão quando a confiança passa do limiar; reportar
**cobertura junto com precisão — sempre as duas**, como exige o
protocolo do 85%. Um sistema pode ter alta precisão e cobertura
muito baixa; ambos devem ser informados.

Confiança de uma previsão = ``max(p, 1 - p)`` (distância da
probabilidade ao 0,5). Previsões abaixo do limiar viram WAIT /
NO TRADE (premissa 7: preferir não operar quando a probabilidade
não está calibrada ou a expectativa é insuficiente).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

__all__ = [
    "selective_predict",
    "selective_metrics",
    "threshold_scan",
    "find_threshold",
]


def selective_predict(
    y_prob: np.ndarray, threshold: float = 0.85
) -> Dict[str, np.ndarray]:
    """Máscara de previsões emitidas e confiança por amostra.

    ``emitted[i]`` é True quando ``max(p, 1-p) >= threshold``.
    ``y_pred_covered`` traz a classe prevista só onde emitido
    (-1 onde não emitido).
    """
    if not 0.5 <= threshold <= 1.0:
        raise ValueError(f"threshold deve estar em [0.5, 1.0], recebido {threshold}")
    y_prob = np.asarray(y_prob, dtype=float)
    confidence = np.maximum(y_prob, 1.0 - y_prob)
    emitted = confidence >= threshold
    y_pred = np.where(
        y_prob >= 0.5, 1, 0
    ).astype(int)
    y_pred_covered = np.where(emitted, y_pred, -1)
    return {
        "emitted": emitted,
        "confidence": confidence,
        "y_pred_covered": y_pred_covered,
        "coverage": float(np.mean(emitted)) if len(y_prob) else 0.0,
    }


def selective_metrics(
    y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.85
) -> Dict[str, Any]:
    """Precisão **e** cobertura no limiar dado (ML-008).

    ``accuracy_covered`` / ``precision_covered`` são calculadas só
    sobre as previsões emitidas; ``coverage`` é a fração emitida.
    Sem previsões emitidas, a precisão é ``None`` (não 0 — não há
    amostra para medir).
    """
    y_true = np.asarray(y_true).astype(int)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) != len(y_prob):
        raise ValueError("y_true e y_prob com tamanhos diferentes")
    sel = selective_predict(y_prob, threshold)
    emitted = sel["emitted"]
    n_covered = int(emitted.sum())
    result: Dict[str, Any] = {
        "threshold": float(threshold),
        "n_total": int(len(y_true)),
        "n_covered": n_covered,
        "coverage": float(sel["coverage"]),
        "accuracy_covered": None,
        "precision_covered": None,
    }
    if n_covered == 0:
        return result
    y_pred = np.where(y_prob >= 0.5, 1, 0).astype(int)
    yt, yp = y_true[emitted], y_pred[emitted]
    result["accuracy_covered"] = float(np.mean(yp == yt))
    predicted_pos = yp == 1
    if predicted_pos.any():
        result["precision_covered"] = float(
            np.mean(yt[predicted_pos] == 1)
        )
    return result


def threshold_scan(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    thresholds: Optional[List[float]] = None,
) -> List[Dict[str, Any]]:
    """Varre limiares e devolve precisão + cobertura em cada um."""
    if thresholds is None:
        thresholds = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    return [selective_metrics(y_true, y_prob, t) for t in thresholds]


def find_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    target_precision: float = 0.85,
    min_coverage: float = 0.05,
) -> Dict[str, Any]:
    """Menor limiar que atinge ``target_precision`` com cobertura
    mínima ``min_coverage`` (varredura de 0,50 a 0,99 em passos de
    0,01). Se nenhum limiar cumpre os dois critérios, devolve o
    limiar de maior precisão com a cobertura mínima e
    ``target_met=False`` — nunca inventa um limiar que funcione.
    """
    if not 0.0 < target_precision <= 1.0:
        raise ValueError("target_precision deve estar em (0, 1]")
    if not 0.0 <= min_coverage <= 1.0:
        raise ValueError("min_coverage deve estar em [0, 1]")
    best: Optional[Dict[str, Any]] = None
    for t in np.arange(0.50, 0.991, 0.01):
        m = selective_metrics(y_true, y_prob, float(round(float(t), 2)))
        if m["precision_covered"] is None:
            continue
        if m["coverage"] < min_coverage:
            continue
        if best is None or m["precision_covered"] > best["precision_covered"]:
            best = m
        if m["precision_covered"] >= target_precision:
            return {
                "threshold": m["threshold"],
                "precision_covered": m["precision_covered"],
                "accuracy_covered": m["accuracy_covered"],
                "coverage": m["coverage"],
                "n_covered": m["n_covered"],
                "target_met": True,
                "target_precision": float(target_precision),
                "min_coverage": float(min_coverage),
            }
    if best is None:
        return {
            "threshold": None, "precision_covered": None,
            "accuracy_covered": None, "coverage": 0.0, "n_covered": 0,
            "target_met": False, "target_precision": float(target_precision),
            "min_coverage": float(min_coverage),
        }
    return {
        "threshold": best["threshold"],
        "precision_covered": best["precision_covered"],
        "accuracy_covered": best["accuracy_covered"],
        "coverage": best["coverage"],
        "n_covered": best["n_covered"],
        "target_met": False,
        "target_precision": float(target_precision),
        "min_coverage": float(min_coverage),
    }
