"""Relatório de backtest — Fase 12 (BKT-007/BKT-008), §8.

Relatório Markdown por série + consolidado + walk-forward, sempre
com: custos considerados, cobertura junto com a precisão, intervalo
de confiança, expectativa líquida e desempenho fora da amostra
(protocolo do 85% — ver ``docs/protocol-85.md``). Precisão isolada
não aparece sozinha em nenhum trecho do relatório.

O relatório de exemplo (dados sintéticos) carrega o aviso
``DADOS SINTÉTICOS`` no título e no corpo: não é resultado real.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from metrics import protocol_85_check

__all__ = [
    "render_report",
    "format_metric_value",
]

SYNTHETIC_WARNING = (
    "> ⚠️ **DADOS SINTÉTICOS — EXEMPLO, NÃO É RESULTADO REAL.** "
    "As séries usadas aqui foram geradas por simulação (seed fixa, "
    "regimes mistos) para demonstrar o motor. Nenhum número deste "
    "relatório valida a estratégia em mercado real. A validação com "
    "dados reais é trabalho da VPS (Fase 12, pendência registrada)."
)


def _fmt(value: Any, suffix: str = "", digits: int = 2) -> str:
    if value is None:
        return "n/d"
    if isinstance(value, float) and value in (float("inf"), float("-inf")):
        return "∞"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


def format_metric_value(value: Any) -> str:
    """Formatação pública (reutilizada por testes)."""
    return _fmt(value)


def _metrics_table(metrics: Dict[str, Any]) -> str:
    ci = metrics.get("win_rate_ci95") or {}
    ci_txt = (
        f"{100 * ci.get('low', 0):.1f}% – {100 * ci.get('high', 0):.1f}%"
        if ci else "n/d"
    )
    rows = [
        ("Trades fechados", f"{metrics['n_trades']}"),
        ("Vitórias / derrotas / breakeven",
         f"{metrics['n_wins']} / {metrics['n_losses']} / {metrics['n_breakeven']}"),
        ("Win Rate (= precisão sobre trades)",
         f"{100 * metrics['win_rate']:.2f}%"),
        ("IC 95% do Win Rate (Wilson)",
         ci_txt),
        ("Cobertura — sinais por 100 candles avaliados",
         f"{metrics['coverage_signals_per_100_bars']:.2f}"),
        ("Cobertura — taxa de execução (trades / sinais)",
         f"{100 * metrics['coverage_execution_rate']:.1f}% "
         f"({metrics['n_signals_executed']}/{metrics['n_signals']} sinais)"),
        ("Expectativa matemática (líquida, por trade)",
         f"US$ {metrics['expectancy_usd']:.2f} "
         f"({metrics['expectancy_pct_capital']:.3f}% do capital; "
         f"{metrics['expectancy_r']:.2f} R)"),
        ("Retorno líquido total",
         f"{metrics['total_return_pct']:.2f}% "
         f"(anualizado: {_fmt(metrics['annualized_return_pct'])}"
         f"{'%' if metrics['annualized_return_pct'] is not None else ' — série curta demais para anualizar'})"),
        ("Profit Factor",
         _fmt(metrics["profit_factor"])),
        ("Sharpe (anualizado)", _fmt(metrics["sharpe"])),
        ("Sortino (anualizado)", _fmt(metrics["sortino"])),
        ("Maximum Drawdown", f"{metrics['max_drawdown_pct']:.2f}%"),
        ("Calmar", _fmt(metrics["calmar"])),
        ("Payoff (ganho médio / perda média)",
         _fmt(metrics["payoff_ratio"])),
        ("Ganho médio / perda média (US$)",
         f"{metrics['avg_win_usd']:.2f} / {metrics['avg_loss_usd']:.2f}"),
        ("Maior sequência de vitórias / derrotas",
         f"{metrics['max_win_streak']} / {metrics['max_loss_streak']}"),
        ("Tempo médio em trade",
         f"{metrics['avg_holding_bars']:.1f} candles"),
        ("Brier Score (probabilidade do sinal)",
         _fmt(metrics["brier_score"], digits=4)),
        ("Log Loss (probabilidade do sinal)",
         _fmt(metrics["log_loss"], digits=4)),
        ("Custos totais (taxas + slippage + gas)",
         f"US$ {metrics['total_cost_usd']:.2f} "
         f"(taxas US$ {metrics['total_fees_usd']:.2f}; "
         f"slippage US$ {metrics['total_slippage_usd']:.2f}; "
         f"gas US$ {metrics['total_gas_usd']:.2f}; "
         f"{metrics['n_fills']} fills)"),
    ]
    lines = ["| Métrica | Valor |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in rows]
    return "\n".join(lines)


def _protocol_table(check: Dict[str, Any]) -> str:
    lines = ["| Critério de referência (§8) | Observado | Resultado |",
             "|---|---|---|"]
    for c in check["checks"]:
        obs = c["observed"]
        obs_txt = _fmt(obs) if not isinstance(obs, int) else str(obs)
        lines.append(
            f"| {c['criterion']} | {obs_txt} | "
            f"{'✅ PASS' if c['passed'] else '❌ FAIL'} |"
        )
    lines.append("")
    global_txt = (
        "✅ todos os critérios de triagem atendidos"
        if check["all_passed"]
        else "❌ nem todos os critérios foram atendidos"
    )
    lines.append(
        f"**Resultado global:** {global_txt} "
        f"(fora da amostra: {'sim' if check['oos'] else 'não'}). "
        "Estes critérios são de **triagem** (§8) — nenhum deles, sozinho "
        "ou em conjunto, aprova a estratégia (§0, premissa 3)."
    )
    return "\n".join(lines)


def render_report(
    *,
    title: str,
    strategy_id: str,
    strategy_version: int,
    strategy_status: str,
    costs: Any,
    per_series: Dict[str, Dict[str, Any]],
    consolidated: Optional[Dict[str, Any]] = None,
    walk_forward: Optional[Dict[str, Any]] = None,
    tested_combinations: Optional[List[Dict[str, Any]]] = None,
    synthetic: bool = False,
    vectorbt_check: Optional[Dict[str, Any]] = None,
    notes: Optional[List[str]] = None,
) -> str:
    """Monta o relatório Markdown completo."""
    lines: List[str] = [f"# {title}", ""]
    if synthetic:
        lines += [SYNTHETIC_WARNING, ""]
    lines += [
        f"- Estratégia: **{strategy_id} v{strategy_version}** "
        f"(status: `{strategy_status}` — nenhuma estratégia é aprovada "
        f"só por backtest otimizado; §0, premissa 3).",
        f"- Custos: taxa {costs.fee_bps} bps/lado; spread "
        f"{costs.spread_bps} bps; slippage {costs.slippage_bps} bps; "
        f"gas US$ {costs.gas_usd}; latência {costs.latency_bars} candle(s); "
        f"fills parciais em {costs.partial_fill_chunks} chunk(s).",
        "",
        "## Por série",
        "",
    ]
    for label, out in per_series.items():
        m = out["metrics"]
        res = out["result"]
        lines += [
            f"### {label}",
            "",
            f"- Símbolo: `{res.symbol}` · timeframe: `{out['timeframe']}` · "
            f"candles avaliados: {m['evaluated_bars']} · sinais gerados: "
            f"{m['n_signals']}.",
            "",
            _metrics_table(m),
            "",
            _protocol_table(protocol_85_check(m, oos=True)),
            "",
        ]
    if consolidated is not None:
        lines += [
            "## Consolidado (todas as séries)",
            "",
            "| Métrica | Valor |",
            "|---|---|",
            f"| Séries | {consolidated['n_series']} |",
            f"| Trades (agregados) | {consolidated['n_trades']} |",
            f"| Win Rate (agregado) | {100 * consolidated['win_rate']:.2f}% |",
            f"| Profit Factor (agregado) | {_fmt(consolidated['profit_factor'])} |",
            f"| Expectativa (líquida, por trade) | US$ {consolidated['expectancy_usd']:.2f} |",
            f"| Retorno líquido (capital total alocado) | {consolidated['total_return_pct']:.2f}% |",
            "",
        ]
    if walk_forward is not None:
        lines += ["## Walk-forward", ""]
        lines += [
            f"- Janelas: {walk_forward['n_windows']} · trades agregados "
            f"nos testes: {walk_forward['pooled_n_trades']}.",
            "",
            "| Janela | Treino | Teste | Trades | Win Rate | Retorno líq. | PF | Max DD |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for out in walk_forward["per_window"]:
            w = out["window"]
            m = out["metrics"]
            lines.append(
                f"| {out['window_index'] + 1} | {w['train']} | {w['test']} | "
                f"{m['n_trades']} | {100 * m['win_rate']:.1f}% | "
                f"{m['total_return_pct']:.2f}% | {_fmt(m['profit_factor'])} | "
                f"{m['max_drawdown_pct']:.2f}% |"
            )
        lines += [""]
    if vectorbt_check is not None:
        lines += ["## Verificação cruzada (vectorbt)", ""]
        if vectorbt_check.get("available"):
            delta = vectorbt_check.get("reconciled_delta_usd")
            delta_txt = f"US$ {delta:.2f}" if delta is not None else "n/d"
            lines += [
                f"- Backend: `{vectorbt_check['engine']}` (replay dos fills exatos do motor).",
                f"- Retorno bruto de taxas (vectorbt): {vectorbt_check['total_return_pct']:.2f}% · "
                f"trades: {vectorbt_check['n_trades']} · "
                f"max DD: {vectorbt_check['max_drawdown_pct']:.2f}% · "
                f"Sharpe: {_fmt(vectorbt_check['sharpe_ratio'])} · "
                f"Profit Factor: {_fmt(vectorbt_check['profit_factor'])}.",
                f"- Reconciliação: final_vectorbt − (final_motor + taxas + gas) = {delta_txt} "
                f"(taxas US$ {vectorbt_check.get('total_fees_usd', 0):.2f}; "
                f"gas US$ {vectorbt_check.get('total_gas_usd', 0):.2f}). "
                f"Delta ~0 indica que a contabilidade dos dois lados concorda.",
                f"- {vectorbt_check['notes']}",
                "",
            ]
        else:
            lines += [f"- Indisponível: {vectorbt_check.get('reason', 'n/d')}.", ""]
    if tested_combinations:
        lines += [
            "## Combinações testadas (§8 — registro completo)",
            "",
            f"Total: **{len(tested_combinations)}** combinações "
            "(estratégia × versão × parâmetros × custos × série × janela).",
            "",
        ]
        for i, combo in enumerate(tested_combinations, 1):
            lines.append(
                f"{i}. `{combo['strategy_id']}` v{combo['strategy_version']} · "
                f"série `{combo['series']}` · janela {combo['window']} · "
                f"capital US$ {combo['initial_capital']:.0f} · "
                f"posição {100 * combo['position_size_pct']:.0f}% · "
                f"custos {combo['costs']}."
            )
        lines += [""]
    lines += [
        "## Notas e pendências",
        "",
        "- Métricas anualizadas (Sharpe, Sortino, retorno anualizado, "
        "Calmar) só são calculadas com >= 30 dias de candles; com "
        "séries mais curtas a anualização explode e o número vira "
        "lixo — nestes casos o relatório mostra n/d.",
        "- A probabilidade das STR-001…STR-010 é escore de confluência, "
        "NÃO calibrada (Fase 13): Brier/Log Loss medem o afastamento, "
        "sem fingir calibração.",
        "- Recall não é computável sem um conjunto rotulado de "
        "oportunidades perdidas; a cobertura (sinais/100 candles e taxa "
        "de execução) é o substituto informado junto com a precisão.",
        "- Purged CV com embargo **não** foi aplicada ao backtest "
        "orientado a eventos: o walk-forward cronológico com embargo "
        "cumpre o mesmo papel; a purged CV fica reservada à Fase 13 "
        "(features com janelas sobrepostas).",
    ]
    for note in (notes or []):
        lines.append(f"- {note}")
    lines += [
        "- Validação com dados reais na VPS e calibração de probabilidade "
        "são pendências (Fase 13).",
        "",
        "_Gerado pelo motor de backtest da Fase 12 (só simulação — "
        "nenhuma ordem real foi enviada)._",
        "",
    ]
    return "\n".join(lines)
