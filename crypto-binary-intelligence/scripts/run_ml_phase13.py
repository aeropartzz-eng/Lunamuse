"""Pipeline da Fase 13 (ML-001…ML-011) — só pesquisa, dados sintéticos.

Gera, a partir de 3 séries sintéticas (seeds 7/8/9, mesmos regimes
do relatório de exemplo da Fase 12):

- snapshot de features em ``data/features/`` (ML-001);
- modelos treinados em ``data/models/`` (ML-002…ML-005);
- ``data/reports/relatorio-85.md`` (ML-011).

Split cronológico 60/20/20 por série (Fase 12), concatenado entre
as séries — nenhuma feature cruza a fronteira entre séries.
Calibração (Platt/sigmoid) ajustada na validação; o teste nunca
participa de treino, calibração ou escolha de pesos/threshold.

Uso: ``python3 scripts/run_ml_phase13.py`` (a partir da raiz do
projeto, com o Python do sistema — ver README do serviço).
Nenhuma chave de API, nenhuma ordem, nenhuma rede.
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for sub in ("services/probability", "services/backtesting",
            "services/indicators", "services/market-regime"):
    sys.path.insert(0, str(PROJECT_ROOT / sub))

from synthetic import make_mixed_regime_series  # noqa: E402
from splits import chronological_split  # noqa: E402
from ml_features import FeatureStore, build_feature_matrix  # noqa: E402
from ml_models import AVAILABLE_MODELS, train_models  # noqa: E402
from ml_calibration import CalibratedModel, compare_calibration  # noqa: E402
from ml_metrics import evaluate_classifier, trade_expectancy  # noqa: E402
from ml_selective import find_threshold, threshold_scan  # noqa: E402
from ml_drift import detect_drift  # noqa: E402
from ml_ensemble import (  # noqa: E402
    EnsembleModel,
    StackingModel,
    compare,
    fit_ensemble_weights,
)
from ml_report import generate_85_report  # noqa: E402

SERIES = [
    ("BTC/USDT", 7),
    ("ETH/USDT", 8),
    ("SOL/USDT", 9),
]
COST_BPS = 30.0
TARGET_PRECISION = 0.85


def _split_concat(feature_sets):
    """Split cronológico 60/20/20 por série, concatenado."""
    parts = {"train": [], "val": [], "test": []}
    y_parts = {"train": [], "val": [], "test": []}
    fut_parts = {"train": [], "val": [], "test": []}
    for fs in feature_sets:
        split = chronological_split(fs.n_rows, 0.6, 0.2)
        for key, (a, b) in split.items():
            k = {"train": "train", "validation": "val", "test": "test"}[key]
            parts[k].append(fs.X[a:b])
            y_parts[k].append(fs.y[a:b])
            fut_parts[k].append(fs.future_returns[a:b])
    out = {}
    for k in ("train", "val", "test"):
        out[f"X_{k}"] = np.vstack(parts[k])
        out[f"y_{k}"] = np.concatenate(y_parts[k])
        out[f"fut_{k}"] = np.concatenate(fut_parts[k])
    return out


def main() -> int:
    store = FeatureStore()
    feature_sets = []
    for symbol, seed in SERIES:
        candles = make_mixed_regime_series(seed=seed, symbol=symbol)
        fs = build_feature_matrix(candles, horizon=1)
        name = symbol.replace("/", "-") + "-5m-v1"
        store.add(name, fs)
        store.save(name, PROJECT_ROOT / "data" / "features")
        feature_sets.append(fs)
        print(f"features {name}: {fs.n_rows} linhas, "
              f"taxa positiva {float(np.mean(fs.y)):.3f}, "
              f"regime={'sim' if fs.regime_available else 'não'}")

    data = _split_concat(feature_sets)
    X_train, y_train = data["X_train"], data["y_train"]
    X_val, y_val = data["X_val"], data["y_val"]
    X_test, y_test, fut_test = data["X_test"], data["y_test"], data["fut_test"]
    print(f"split: treino={len(y_train)} validação={len(y_val)} teste={len(y_test)}")

    result = train_models(X_train, y_train)
    trained, skipped = result["trained"], result["skipped"]
    print(f"modelos treinados: {sorted(trained)}; fora: {skipped or 'nenhum'}")

    models_dir = PROJECT_ROOT / "data" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    model_table = []
    probas_test = {}
    for name, model in trained.items():
        proba_raw = model.predict_proba(X_test)[:, 1]
        cal = CalibratedModel(model, method="sigmoid")
        cal.fit(X_val, y_val)
        proba_cal = cal.predict_proba(X_test)[:, 1]
        pred_cal = (proba_cal >= 0.5).astype(int)
        ev_raw = evaluate_classifier(y_test, (proba_raw >= 0.5).astype(int), proba_raw)
        ev_cal = evaluate_classifier(y_test, pred_cal, proba_cal)
        comp = compare_calibration(y_test, proba_raw, proba_cal)
        texp = trade_expectancy(fut_test, pred_cal, cost_bps=COST_BPS)
        model_table.append({
            "model": name,
            "accuracy": ev_cal["accuracy"],
            "precision": ev_cal["precision"],
            "recall": ev_cal["recall"],
            "brier_score": ev_raw["brier_score"],
            "log_loss": ev_raw["log_loss"],
            "brier_calibrated": ev_cal["brier_score"],
            "log_loss_calibrated": ev_cal["log_loss"],
            "win_rate": texp["win_rate"],
            "expectancy_bps": texp["expectancy_bps"],
            "n": ev_cal["n"],
            "n_trades": texp["n_trades"],
        })
        probas_test[name] = cal.predict_proba(X_test)
        print(f"{name}: Brier {ev_raw['brier_score']:.4f} -> {ev_cal['brier_score']:.4f} "
              f"(calibrado, melhorou={comp['brier_improved']}) | "
              f"LogLoss {ev_raw['log_loss']:.4f} -> {ev_cal['log_loss']:.4f} | "
              f"acc {ev_cal['accuracy']:.3f} | win rate {texp['win_rate']:.3f} | "
              f"expectativa {texp['expectancy_bps']:.1f} bps/trade ({texp['n_trades']} trades)")
        with open(models_dir / f"{name}.pkl", "wb") as f:
            pickle.dump({"model": model, "calibrated_sigmoid": cal}, f)

    best_name = min(model_table, key=lambda r: r["brier_calibrated"])["model"]
    best_cal_proba = probas_test[best_name][:, 1]
    print(f"melhor modelo individual (Brier calibrado): {best_name}")

    scan = threshold_scan(y_test, best_cal_proba)
    sel_best = find_threshold(
        y_test, best_cal_proba,
        target_precision=TARGET_PRECISION, min_coverage=0.05,
    )
    print(f"selective: limiar={sel_best['threshold']} precisão={sel_best['precision_covered']} "
          f"cobertura={sel_best['coverage']:.3f} n={sel_best['n_covered']} "
          f"atingiu={sel_best['target_met']}")

    drift = detect_drift(X_train, X_test, list(feature_sets[0].feature_names))
    print(f"drift: PSI máx={drift['max_psi']:.3f} detectado={drift['drift_detected']}")
    if drift["alert"]:
        print(f"  ALERTA: {drift['alert']}")

    # Ensemble: pesos otimizados na validação (Brier), avaliados no teste.
    base_models = [trained[n] for n in sorted(trained)]
    weights = fit_ensemble_weights(base_models, X_val, y_val)
    ensemble = EnsembleModel(base_models, weights=weights["weights"])
    ensemble.is_fitted = True  # modelos base já treinados
    stacking = StackingModel([trained[n] for n in sorted(trained)])
    stacking.fit(X_train, y_train, X_val, y_val)
    ens_probas = dict(probas_test)
    ens_probas["ensemble_weighted"] = ensemble.predict_proba(X_test)
    ens_probas["ensemble_stacking"] = stacking.predict_proba(X_test)
    ens_table = compare(y_test, ens_probas)
    print("ensemble (Brier no teste): " + "; ".join(
        f"{r['model']}={r['brier_score']:.4f}" for r in ens_table
    ))
    (models_dir / "ensemble-weights.json").write_text(
        json.dumps(
            {"models": sorted(trained), "weights": weights["weights"],
             "brier_val": weights["brier_val"],
             "brier_val_equal_weights": weights["brier_val_equal_weights"]},
            indent=2,
        ),
        encoding="utf-8",
    )
    with open(models_dir / "ensemble_stacking.pkl", "wb") as f:
        pickle.dump({"stacking": stacking, "weights": weights["weights"]}, f)

    verdict = generate_85_report(
        PROJECT_ROOT / "data" / "reports" / "relatorio-85.md",
        model_table=model_table,
        best_model_name=best_name,
        selective_scan=scan,
        selective_best=sel_best,
        ensemble_table=ens_table,
        drift=drift,
        dataset_info={
            "feature_version": feature_sets[0].version,
            "n_features": feature_sets[0].n_features,
            "horizon": 1,
            "symbols": ", ".join(s for s, _ in SERIES),
            "timeframe": "5m",
            "seeds": ", ".join(str(s) for _, s in SERIES),
            "n_train": len(y_train),
            "n_val": len(y_val),
            "n_test": len(y_test),
        },
        costs_bps=COST_BPS,
        target_precision=TARGET_PRECISION,
    )
    print(f"relatório: {verdict['path']}")
    print(f"veredicto 85%: {'ATINGIDA' if verdict['target_met'] else 'NÃO ATINGIDA'} — "
          f"precisão seletiva {verdict['best_selective_precision']}, "
          f"cobertura {verdict['best_selective_coverage']:.3f}, "
          f"motivos: {verdict['reasons'] or 'nenhum'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
