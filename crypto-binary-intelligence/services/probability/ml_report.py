"""Relatório do 85% — Fase 13 (ML-011), §8 e protocolo do 85%.

Gera ``data/reports/relatorio-85.md`` com cobertura, intervalo de
confiança de 95% (Wilson), expectativa líquida de custos e
desempenho fora da amostra — sobre **dados sintéticos**, marcado
claramente como tal.

Veredicto (critérios documentados, não forçados):

- a meta de 85% só é "ATINGIDA" se, **fora da amostra**,
  (a) a precisão seletiva for >= 85%,
  (b) o subconjunto seletivo tiver >= 500 amostras (referência
  §8 para crypto scalping; 1.000 para binárias),
  (c) a expectativa líquida de custos for positiva;
- caso contrário o relatório diz **NÃO ATINGIDA**, com os motivos.

Precisão isolada, sem cobertura, expectativa, custos, IC 95% e
amostra fora da amostra, não pode aprovar nem divulgar nada
(protocolo do 85%, §5).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from ml_metrics import wilson_ci
except ImportError:
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.append(str(_Path(__file__).resolve().parent))
    from ml_metrics import wilson_ci

__all__ = [
    "generate_85_report",
    "TARGET_PRECISION",
    "REF_MIN_OOS_CRYPTO",
    "REF_MIN_OOS_BINARY",
]

TARGET_PRECISION = 0.85
REF_MIN_OOS_CRYPTO = 500   # §8: >= 500 operações fora da amostra por estratégia
REF_MIN_OOS_BINARY = 1000  # §8: >= 1.000 resultados fora da amostra (binárias)


def _fmt_pct(value: Optional[float]) -> str:
    return "n/d" if value is None else f"{100.0 * value:.2f}%"


def _fmt(value: Optional[float], digits: int = 4) -> str:
    return "n/d" if value is None else f"{value:.{digits}f}"


def generate_85_report(
    output_path: str | Path,
    *,
    model_table: List[Dict[str, Any]],
    best_model_name: str,
    selective_scan: List[Dict[str, Any]],
    selective_best: Dict[str, Any],
    ensemble_table: List[Dict[str, Any]],
    drift: Dict[str, Any],
    dataset_info: Dict[str, Any],
    costs_bps: float = 30.0,
    target_precision: float = TARGET_PRECISION,
    report_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Gera o relatório do 85% em Markdown e devolve o veredicto.

    ``model_table``: uma linha por modelo com ``model``,
    ``accuracy``, ``precision``, ``recall``, ``brier_score``,
    ``log_loss``, ``brier_calibrated``, ``log_loss_calibrated``,
    ``win_rate``, ``expectancy_bps``, ``n`` (fora da amostra).
    ``selective_best``: saída de ``ml_selective.find_threshold``.
    """
    report_date = report_date or date.today().isoformat()
    n_oos = int(dataset_info.get("n_test", 0))
    n_covered = int(selective_best.get("n_covered") or 0)
    prec = selective_best.get("precision_covered")
    acc = selective_best.get("accuracy_covered")
    coverage = selective_best.get("coverage") or 0.0
    threshold = selective_best.get("threshold")

    # IC 95% (Wilson) da precisão seletiva: acertos entre os cobertos.
    wins = None
    ci = None
    if prec is not None and n_covered > 0:
        wins = int(round(prec * n_covered))
        ci = wilson_ci(wins, n_covered)

    # Expectativa do melhor modelo (da tabela) — líquida de custos.
    best_row = next(
        (r for r in model_table if r.get("model") == best_model_name),
        model_table[0] if model_table else {},
    )
    expectancy_bps = best_row.get("expectancy_bps")
    win_rate = best_row.get("win_rate")

    # Veredicto — critérios explícitos, sem forçar o número.
    reasons: List[str] = []
    if prec is None or prec < target_precision:
        reasons.append(
            f"precisão seletiva {_fmt_pct(prec)} < {100.0 * target_precision:.0f}%"
        )
    if n_covered < REF_MIN_OOS_CRYPTO:
        reasons.append(
            f"subconjunto seletivo com {n_covered} amostras < {REF_MIN_OOS_CRYPTO} "
            "(referência §8 para crypto scalping)"
        )
    if expectancy_bps is None or expectancy_bps <= 0:
        reasons.append(
            f"expectativa líquida {expectancy_bps if expectancy_bps is not None else 'n/d'} bps "
            "<= 0 (não positiva após custos)"
        )
    target_met = not reasons

    lines: List[str] = []
    lines.append("# Relatório do 85% — Machine Learning (Fase 13)")
    lines.append("")
    lines.append("> ⚠️ **DADOS SINTÉTICOS — NÃO É RESULTADO REAL.** Todas as séries usadas aqui foram geradas por simulação (seeds fixas, regimes mistos) para demonstrar e validar o pipeline de ML. Nenhum número deste relatório valida qualquer modelo em mercado real, nem promete acerto, lucro ou rentabilidade. A meta de 85% é um objetivo de pesquisa para sinais seletivos (§0, premissa 1). A validação com dados reais é trabalho da VPS (pendência registrada).")
    lines.append("")
    lines.append(f"- Data: **{report_date}** · Fase 13 (ML-001…ML-011) · especificação v4.1 §8.")
    lines.append(f"- Feature set: **{dataset_info.get('feature_version', 'v1')}** ({dataset_info.get('n_features', '?')} features) · horizonte do rótulo: {dataset_info.get('horizon', 1)} candle(s).")
    lines.append(f"- Séries sintéticas: {dataset_info.get('symbols', '?')} · timeframe {dataset_info.get('timeframe', '?')} · seeds {dataset_info.get('seeds', '?')}.")
    lines.append(f"- Split cronológico (Fase 12): treino {dataset_info.get('n_train', '?')} · validação {dataset_info.get('n_val', '?')} · **teste (fora da amostra) {n_oos}**.")
    lines.append(f"- Custos por trade: **{costs_bps:.0f} bps** (taxa 10 bps/lado + spread 5 bps + slippage 5 bps — mesmas premissas da Fase 12).")
    lines.append("- Calibração: Platt (sigmoid) ajustada na validação. A calibração isotônica existe em `CalibratedModel(method='isotonic')` como alternativa, mas não é usada neste relatório.")
    lines.append("")
    lines.append("## Veredicto")
    lines.append("")
    if target_met:
        lines.append(f"**✅ META DE 85% ATINGIDA (nesta amostra sintética):** precisão seletiva {_fmt_pct(prec)} com cobertura {_fmt_pct(coverage)} ({n_covered} de {n_oos} amostras fora da amostra), IC 95% {_fmt_pct(ci['low']) if ci else 'n/d'} – {_fmt_pct(ci['high']) if ci else 'n/d'}, expectativa líquida {expectancy_bps:.1f} bps/trade. Mesmo assim, isto **não aprova** o modelo: é sintético, e a aprovação exige dados reais, walk-forward, regimes diferentes e homologação (§0, premissa 3).")
    else:
        lines.append(f"**❌ META DE 85% NÃO ATINGIDA (nesta amostra sintética):** {'; '.join(reasons)}. O número não foi forçado — a precisão é reportada como medida, junto com cobertura, IC 95%, expectativa e custos, como exige o protocolo do 85%.")
    lines.append("")
    lines.append("## 1. Modelos fora da amostra (teste, calibrados na validação)")
    lines.append("")
    lines.append("| Modelo | Acurácia | Precision | Recall | Brier (cru → calibrado) | Log Loss (cru → calibrado) | Win Rate (sinal) | Expectativa líq. (bps/trade) | n |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in model_table:
        lines.append(
            f"| {row.get('model', '?')} | {_fmt_pct(row.get('accuracy'))} | "
            f"{_fmt_pct(row.get('precision'))} | {_fmt_pct(row.get('recall'))} | "
            f"{_fmt(row.get('brier_score'))} → {_fmt(row.get('brier_calibrated'))} | "
            f"{_fmt(row.get('log_loss'))} → {_fmt(row.get('log_loss_calibrated'))} | "
            f"{_fmt_pct(row.get('win_rate'))} | "
            f"{row.get('expectancy_bps') if row.get('expectancy_bps') is not None else 'n/d'} | "
            f"{row.get('n', '?')} |"
        )
    lines.append("")
    lines.append(f"Melhor modelo individual (menor Brier fora da amostra): **{best_model_name}**.")
    lines.append("")
    lines.append("## 2. Selective Prediction — precisão SEMPRE com cobertura")
    lines.append("")
    lines.append("| Limiar de confiança | Cobertura | n coberto | Precisão (cobertos) | Acurácia (cobertos) |")
    lines.append("|---|---|---|---|---|")
    for row in selective_scan:
        lines.append(
            f"| {row.get('threshold', '?'):.2f} | {_fmt_pct(row.get('coverage'))} | "
            f"{row.get('n_covered', '?')} | {_fmt_pct(row.get('precision_covered'))} | "
            f"{_fmt_pct(row.get('accuracy_covered'))} |"
        )
    lines.append("")
    if threshold is not None:
        if selective_best.get("target_met"):
            lines.append(
                f"Limiar escolhido: **{threshold:.2f}** (menor limiar com precisão >= "
                f"{100.0 * target_precision:.0f}% e cobertura >= 5%, varredura 0,50–0,99)."
            )
        else:
            lines.append(
                f"Limiar escolhido: **{threshold:.2f}** (maior precisão encontrada na "
                f"varredura 0,50–0,99 com cobertura >= 5% — a meta de "
                f"{100.0 * target_precision:.0f}% não foi atingida em nenhum limiar)."
            )
        lines.append(
            f"Precisão seletiva: **{_fmt_pct(prec)}** · cobertura **{_fmt_pct(coverage)}** "
            f"({n_covered}/{n_oos}) · IC 95% (Wilson): "
            f"**{_fmt_pct(ci['low']) if ci else 'n/d'} – {_fmt_pct(ci['high']) if ci else 'n/d'}** "
            f"({wins}/{n_covered} acertos)."
        )
    else:
        lines.append("Nenhum limiar atingiu cobertura mínima com precisão mensurável — sem subconjunto seletivo a reportar.")
    lines.append("")
    lines.append("## 3. Ensemble vs. melhor modelo individual")
    lines.append("")
    lines.append("| Modelo | Acurácia | Brier | Log Loss | Rank (Brier) |")
    lines.append("|---|---|---|---|---|")
    for row in ensemble_table:
        lines.append(
            f"| {row.get('model', '?')} | {_fmt_pct(row.get('accuracy'))} | "
            f"{_fmt(row.get('brier_score'))} | {_fmt(row.get('log_loss'))} | "
            f"{row.get('rank_brier', '?')} |"
        )
    lines.append("")
    best_ens = ensemble_table[0] if ensemble_table else {}
    if best_ens.get("model", "").startswith("ensemble"):
        lines.append(f"O ensemble (**{best_ens.get('model')}**) venceu o melhor modelo individual em Brier fora da amostra ({_fmt(best_ens.get('brier_score'))}).")
    else:
        lines.append(f"O ensemble **não** venceu o melhor modelo individual fora da amostra — o melhor continua sendo **{best_ens.get('model', '?')}** (Brier {_fmt(best_ens.get('brier_score'))}). Comparação honesta: nenhum ensemble é declarado melhor sem vencer esta tabela.")
    lines.append("")
    lines.append("## 4. Concept Drift (treino vs. teste)")
    lines.append("")
    lines.append(f"- PSI máximo: **{drift.get('max_psi', 0.0):.3f}** (limite de alerta: {drift.get('threshold', 0.25)}) · PSI médio: {drift.get('mean_psi', 0.0):.3f}.")
    lines.append(f"- Drift detectado: **{'SIM' if drift.get('drift_detected') else 'não'}**.")
    if drift.get("alert"):
        lines.append(f"- Alerta: {drift['alert']}")
    top = (drift.get("per_feature") or [])[:5]
    if top:
        lines.append("- Maiores PSIs por feature:")
        for r in top:
            lines.append(f"  - {r['feature']}: {r['psi']:.3f} ({r['level']})")
    lines.append("")
    lines.append("## 5. Critérios do §8 / protocolo do 85%")
    lines.append("")
    lines.append("| Critério | Observado | Resultado |")
    lines.append("|---|---|---|")
    lines.append(f"| Precisão seletiva >= 85% | {_fmt_pct(prec)} | {'✅ PASS' if (prec is not None and prec >= target_precision) else '❌ FAIL'} |")
    lines.append(f"| Cobertura divulgada junto com a precisão | {_fmt_pct(coverage)} ({n_covered}/{n_oos}) | ✅ PASS |")
    lines.append(f"| IC 95% da precisão seletiva | {_fmt_pct(ci['low']) if ci else 'n/d'} – {_fmt_pct(ci['high']) if ci else 'n/d'} | {'✅ PASS' if ci else '❌ FAIL'} |")
    lines.append(f"| Expectativa líquida positiva (custos incluídos) | {expectancy_bps if expectancy_bps is not None else 'n/d'} bps/trade | {'✅ PASS' if (expectancy_bps is not None and expectancy_bps > 0) else '❌ FAIL'} |")
    lines.append(f"| Amostra fora da amostra (crypto: >= 500; binárias: >= 1.000) | {n_oos} (teste) / {n_covered} (seletivo) | {'✅ PASS' if n_covered >= REF_MIN_OOS_CRYPTO else '❌ FAIL'} |")
    lines.append(f"| Win Rate do melhor modelo como sinal | {_fmt_pct(win_rate)} | — |")
    lines.append("")
    lines.append("Estes critérios são de **triagem** (§8) — nenhum deles, sozinho ou em conjunto, aprova o modelo (§0, premissa 3). Correlação temporal entre operações exige métodos de validação adicionais.")
    lines.append("")
    lines.append("## 6. Limitações e pendências")
    lines.append("")
    lines.append("- **Dados sintéticos**: séries geradas por simulação (random walk com regimes); o sinal aprendido aqui pode não existir em mercado real.")
    lines.append("- Amostra fora da amostra pequena para o §8 (ver §5): o subconjunto seletivo raramente chega a 500 amostras com séries de ~1.100 candles.")
    lines.append("- Rótulo de 1 candle à frente: horizonte curto, ruidoso; horizontes maiores e custos de latência real não foram testados.")
    lines.append("- Sem walk-forward de ML nesta fase: o split é um único bloco cronológico 60/20/20 por série (walk-forward de modelos fica para a validação na VPS).")
    lines.append("- **Pendente: treino com dados reais na VPS** (Fase 13, ML-011) — re-treinar, re-calibrar e reemitir este relatório com dados de exchange, antes de qualquer homologação.")
    lines.append("- Execução continua bloqueada (403); nenhum modelo deste relatório gera ordem real.")
    lines.append("")
    lines.append("_Gerado pelo pipeline de ML da Fase 13 — só pesquisa, nenhuma ordem real foi enviada._")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "path": str(output_path),
        "target_met": target_met,
        "target_precision": float(target_precision),
        "best_selective_precision": prec,
        "best_selective_coverage": coverage,
        "best_selective_n_covered": n_covered,
        "best_selective_threshold": threshold,
        "ci95": ci,
        "n_oos": n_oos,
        "expectancy_bps": expectancy_bps,
        "reasons": reasons,
    }
