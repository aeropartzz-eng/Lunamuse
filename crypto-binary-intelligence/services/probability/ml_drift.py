"""Concept Drift — Fase 13 (ML-009), §8.

Detecta quando a distribuição das features muda entre o treino
(referência) e uma janela recente — sinal de que o modelo pode
estar degradado e precisa de re-treino.

Métrica: **PSI (Population Stability Index)** por feature, com os
limites consagrados na literatura de risco de modelos:

- PSI < 0,10 → distribuição estável;
- 0,10 ≤ PSI < 0,25 → mudança moderada (observar);
- PSI ≥ 0,25 → mudança significativa → **alerta de drift**.

O limite de alerta padrão é **0,25** (``DRIFT_PSI_THRESHOLD``).
``detect_drift`` também reporta a mudança de média/desvio por
feature (``distribution_shift``) para diagnóstico.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

__all__ = [
    "DRIFT_PSI_THRESHOLD",
    "PSI_STABLE_MAX",
    "PSI_MODERATE_MAX",
    "psi",
    "psi_report",
    "distribution_shift",
    "detect_drift",
]

# Limites PSI (padrão da literatura de risco de modelos).
PSI_STABLE_MAX = 0.10
PSI_MODERATE_MAX = 0.25
DRIFT_PSI_THRESHOLD = 0.25  # alerta quando max PSI >= 0,25


def psi(
    expected: np.ndarray,
    actual: np.ndarray,
    bins: int = 10,
    epsilon: float = 1e-4,
) -> float:
    """PSI entre duas amostras de uma feature.

    Faixas por quantis da referência; ``PSI = sum((a - e) * ln(a/e))``
    sobre as proporções por faixa (cortadas em ``epsilon``).
    """
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]
    if len(expected) == 0 or len(actual) == 0:
        return float("nan")
    if np.std(expected) == 0 and np.std(actual) == 0:
        return 0.0 if float(np.mean(expected)) == float(np.mean(actual)) else 1.0
    edges = np.unique(np.quantile(expected, np.linspace(0.0, 1.0, bins + 1)))
    if len(edges) < 3:
        # Referência quase constante: compara por faixas de largura igual.
        lo = min(float(np.min(expected)), float(np.min(actual)))
        hi = max(float(np.max(expected)), float(np.max(actual)))
        if hi <= lo:
            return 0.0
        edges = np.linspace(lo, hi, bins + 1)
    e_counts, _ = np.histogram(expected, bins=edges)
    a_counts, _ = np.histogram(actual, bins=edges)
    # Valores fora das faixas (cauda da janela recente) vão para as
    # faixas das pontas, para não sumirem do cálculo.
    a_counts[0] += int((actual < edges[0]).sum())
    a_counts[-1] += int((actual > edges[-1]).sum())
    e_prop = np.clip(e_counts / max(len(expected), 1), epsilon, None)
    a_prop = np.clip(a_counts / max(len(actual), 1), epsilon, None)
    return float(np.sum((a_prop - e_prop) * np.log(a_prop / e_prop)))


def psi_report(
    X_ref: np.ndarray,
    X_recent: np.ndarray,
    feature_names: Optional[Sequence[str]] = None,
    bins: int = 10,
) -> List[Dict[str, Any]]:
    """PSI por feature entre referência e janela recente."""
    X_ref = np.asarray(X_ref, dtype=float)
    X_recent = np.asarray(X_recent, dtype=float)
    if X_ref.ndim != 2 or X_recent.ndim != 2:
        raise ValueError("X_ref e X_recent devem ser matrizes 2-D")
    if X_ref.shape[1] != X_recent.shape[1]:
        raise ValueError("X_ref e X_recent com números de features diferentes")
    names = list(feature_names) if feature_names is not None else [
        f"feature_{i}" for i in range(X_ref.shape[1])
    ]
    rows: List[Dict[str, Any]] = []
    for j, name in enumerate(names):
        value = psi(X_ref[:, j], X_recent[:, j], bins=bins)
        if value < PSI_STABLE_MAX:
            level = "estável"
        elif value < PSI_MODERATE_MAX:
            level = "moderado"
        else:
            level = "significativo"
        rows.append({"feature": name, "psi": value, "level": level})
    rows.sort(key=lambda r: r["psi"], reverse=True)
    return rows


def distribution_shift(
    X_ref: np.ndarray,
    X_recent: np.ndarray,
    feature_names: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Mudança de média/desvio por feature (referência vs. recente).

    ``mean_shift_std`` = (média_recente - média_ref) / desvio_ref.
    """
    X_ref = np.asarray(X_ref, dtype=float)
    X_recent = np.asarray(X_recent, dtype=float)
    names = list(feature_names) if feature_names is not None else [
        f"feature_{i}" for i in range(X_ref.shape[1])
    ]
    rows: List[Dict[str, Any]] = []
    for j, name in enumerate(names):
        ref, rec = X_ref[:, j], X_recent[:, j]
        ref = ref[np.isfinite(ref)]
        rec = rec[np.isfinite(rec)]
        std_ref = float(np.std(ref)) if len(ref) else float("nan")
        rows.append({
            "feature": name,
            "mean_ref": float(np.mean(ref)) if len(ref) else float("nan"),
            "mean_recent": float(np.mean(rec)) if len(rec) else float("nan"),
            "std_ref": std_ref,
            "std_recent": float(np.std(rec)) if len(rec) else float("nan"),
            "mean_shift_std": (
                float((np.mean(rec) - np.mean(ref)) / std_ref)
                if std_ref and std_ref > 0 else 0.0
            ),
        })
    return rows


def detect_drift(
    X_ref: np.ndarray,
    X_recent: np.ndarray,
    feature_names: Optional[Sequence[str]] = None,
    threshold: float = DRIFT_PSI_THRESHOLD,
    bins: int = 10,
) -> Dict[str, Any]:
    """Detecção de drift (ML-009).

    ``drift_detected`` é True quando o maior PSI entre as features
    passa de ``threshold`` (padrão 0,25). O alerta nomeia as
    features acima do limite.
    """
    report = psi_report(X_ref, X_recent, feature_names, bins=bins)
    max_psi = max((r["psi"] for r in report), default=0.0)
    drifted = [r["feature"] for r in report if r["psi"] >= threshold]
    return {
        "drift_detected": bool(max_psi >= threshold),
        "threshold": float(threshold),
        "max_psi": float(max_psi),
        "mean_psi": float(np.mean([r["psi"] for r in report])) if report else 0.0,
        "n_features": len(report),
        "n_drifted_features": len(drifted),
        "drifted_features": drifted,
        "per_feature": report,
        "alert": (
            f"DRIFT: {len(drifted)} feature(s) com PSI >= {threshold} "
            f"(máx. {max_psi:.3f}): {', '.join(drifted)} — re-treino recomendado."
            if drifted else None
        ),
    }
