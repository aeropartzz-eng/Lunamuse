"""Relatório de exemplo fora da amostra — Fase 12 (BKT-007/BKT-008).

Roda a STR-001 (Trend Following v1, status ``experimental``) com os
custos padrão sobre 3 séries **sintéticas** de regimes mistos
(BTC/ETH/SOL-like, seeds diferentes) + walk-forward na série BTC e
verificação cruzada com vectorbt. O relatório sai em
``data/reports/backtest-exemplo-STR-001.md``.

DADOS SINTÉTICOS — o relatório deixa isso explícito: não é
resultado real e não valida a estratégia. Validação com dados reais
é pendência da VPS (Fase 12).

Uso::

    python3 scripts/run_backtest_str001_example.py

Só simulação: nenhuma chave de API, nenhuma ordem real.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _name in ("exchange-connectors", "indicators", "patterns",
              "order-flow", "market-regime", "strategies", "backtesting"):
    sys.path.insert(0, str(_PROJECT_ROOT / "services" / _name))

from costs import CostModel  # noqa: E402
from report import render_report  # noqa: E402
from runner import run_multi_series, run_walk_forward  # noqa: E402
from strategies import get_strategy  # noqa: E402
from synthetic import make_mixed_regime_series  # noqa: E402
from vectorbt_adapter import run_vectorbt_crosscheck  # noqa: E402

REPORT_PATH = _PROJECT_ROOT / "data" / "reports" / "backtest-exemplo-STR-001.md"


def main() -> int:
    strategy = get_strategy("STR-001")
    costs = CostModel()  # padrões da Fase 12 (ver README do serviço)
    print(f"Estratégia: {strategy.code} v{strategy.version} ({strategy.status})")
    print(f"Custos: {costs.to_dict()}")

    series = {
        "BTC/USDT (sintético)": make_mixed_regime_series(
            seed=7, start_price=100.0, symbol="BTC/USDT"),
        "ETH/USDT (sintético)": make_mixed_regime_series(
            seed=8, start_price=50.0, symbol="ETH/USDT"),
        "SOL/USDT (sintético)": make_mixed_regime_series(
            seed=9, start_price=20.0, symbol="SOL/USDT"),
    }
    for label, candles in series.items():
        print(f"Série {label}: {len(candles)} candles")

    multi = run_multi_series(strategy, series, costs, initial_capital=10_000.0)
    for label, out in multi["per_series"].items():
        m = out["metrics"]
        print(f"[{label}] trades={m['n_trades']} win_rate={100 * m['win_rate']:.1f}% "
              f"PF={m['profit_factor']:.2f} retorno={m['total_return_pct']:.2f}% "
              f"maxDD={m['max_drawdown_pct']:.2f}%")

    btc = series["BTC/USDT (sintético)"]
    wf = run_walk_forward(
        strategy, btc, costs, initial_capital=10_000.0,
        train_size=400, test_size=100, step=200, embargo_bars=5,
    )
    print(f"Walk-forward: {wf['n_windows']} janelas, "
          f"{wf['pooled_n_trades']} trades nos testes")

    btc_out = multi["per_series"]["BTC/USDT (sintético)"]
    btc_result = btc_out["result"]
    vbt = run_vectorbt_crosscheck(
        btc, btc_result.trades, btc_result.fills, costs, 10_000.0,
        engine_final_equity=btc_result.final_equity)
    if vbt.get("available"):
        print(f"vectorbt: retorno bruto {vbt['total_return_pct']:.2f}% vs. "
              f"motor (líquido) {btc_result.total_return_pct:.2f}% · "
              f"trades: {vbt['n_trades']} vs. {btc_result.n_trades} · "
              f"delta da reconciliação: US$ {vbt['reconciled_delta_usd']:.2f}")
    else:
        print(f"vectorbt indisponível: {vbt.get('reason')}")

    combos = list(multi["tested_combinations"])
    combos.extend(wf["tested_combinations"])
    report = render_report(
        title="Backtest exemplo — STR-001 (Trend Following) — DADOS SINTÉTICOS",
        strategy_id=strategy.code,
        strategy_version=int(strategy.version),
        strategy_status=strategy.status,
        costs=costs,
        per_series=multi["per_series"],
        consolidated=multi["consolidated"],
        walk_forward=wf,
        tested_combinations=combos,
        synthetic=True,
        vectorbt_check=vbt,
        notes=[
            "Walk-forward com embargo de 5 candles entre treino e teste.",
            "Séries sintéticas geradas por `synthetic.make_mixed_regime_series` "
            "(seeds 7/8/9; regimes TREND_UP, RANGE, TREND_DOWN, EXPANSION).",
        ],
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Relatório: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
