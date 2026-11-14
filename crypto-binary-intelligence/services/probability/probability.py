"""Probability Engine — Fase 13 (ML-001…ML-011), especificação v4.1 §8.

Fachada: re-exporta a API pública dos módulos ``ml_*`` deste
serviço (módulos planos — o diretório tem hífen? Não: este é
``services/probability/``; os módulos usam o prefixo ``ml_`` para
não colidir com ``metrics.py``/``report.py`` de backtesting e
``models.py`` dos conectores no ``sys.path`` dos testes).

- ML-001 Feature Store: :mod:`ml_features`
- ML-002…ML-005 Modelos: :mod:`ml_models`
- ML-006 Calibração: :mod:`ml_calibration`
- ML-007 Métricas: :mod:`ml_metrics`
- ML-008 Selective Prediction: :mod:`ml_selective`
- ML-009 Concept Drift: :mod:`ml_drift`
- ML-010 Ensemble: :mod:`ml_ensemble`
- ML-011 Relatório do 85%: :mod:`ml_report`

Só pesquisa com dados sintéticos. Nenhuma chave de API, nenhum
envio de ordem, nenhuma conexão a conta. A execução continua
bloqueada (403) e o scaffold força RESEARCH quando
EXECUTION_MODE=LIVE.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from ml_features import (  # noqa: E402,F401
    FEATURE_NAMES,
    FEATURE_SET_VERSION,
    FeatureSet,
    FeatureStore,
    build_feature_matrix,
    make_labels,
)
from ml_models import (  # noqa: E402,F401
    AVAILABLE_MODELS,
    MODEL_REGISTRY,
    BaseMLModel,
    LightGBMModel,
    LogisticRegressionModel,
    RandomForestModel,
    XGBoostModel,
    get_model,
    train_models,
)
from ml_calibration import (  # noqa: E402,F401
    CalibratedModel,
    calibration_curve,
    calibration_error,
    compare_calibration,
)
from ml_metrics import (  # noqa: E402,F401
    brier_score,
    evaluate_classifier,
    log_loss,
    precision_recall_f1,
    trade_expectancy,
    wilson_ci,
)
from ml_selective import (  # noqa: E402,F401
    find_threshold,
    selective_metrics,
    selective_predict,
    threshold_scan,
)
from ml_drift import (  # noqa: E402,F401
    DRIFT_PSI_THRESHOLD,
    detect_drift,
    distribution_shift,
    psi,
    psi_report,
)
from ml_ensemble import (  # noqa: E402,F401
    EnsembleModel,
    StackingModel,
    compare,
    fit_ensemble_weights,
)
from ml_report import (  # noqa: E402,F401
    TARGET_PRECISION,
    generate_85_report,
)

__all__ = [
    "FEATURE_NAMES",
    "FEATURE_SET_VERSION",
    "FeatureSet",
    "FeatureStore",
    "build_feature_matrix",
    "make_labels",
    "AVAILABLE_MODELS",
    "MODEL_REGISTRY",
    "BaseMLModel",
    "LightGBMModel",
    "LogisticRegressionModel",
    "RandomForestModel",
    "XGBoostModel",
    "get_model",
    "train_models",
    "CalibratedModel",
    "calibration_curve",
    "calibration_error",
    "compare_calibration",
    "brier_score",
    "evaluate_classifier",
    "log_loss",
    "precision_recall_f1",
    "trade_expectancy",
    "wilson_ci",
    "find_threshold",
    "selective_metrics",
    "selective_predict",
    "threshold_scan",
    "DRIFT_PSI_THRESHOLD",
    "detect_drift",
    "distribution_shift",
    "psi",
    "psi_report",
    "EnsembleModel",
    "StackingModel",
    "compare",
    "fit_ensemble_weights",
    "TARGET_PRECISION",
    "generate_85_report",
]
