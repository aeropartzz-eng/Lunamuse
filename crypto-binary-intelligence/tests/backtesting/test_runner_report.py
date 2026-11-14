"""Testes do runner (backtest único, walk-forward, multi-série) e do
relatório — Fase 12 (BKT-004/BKT-005/BKT-007/BKT-008). Sem rede.
"""

from __future__ import annotations

import pytest

from costs import CostModel
from report import render_report
from runner import run_backtest, run_multi_series, run_walk_forward
from strategies import get_strategy
from synthetic import make_mixed_regime_series


@pytest.fixture(scope="module")
def series():
    return make_mixed_regime_series(seed=7)


def test_run_backtest_str001_on_synthetic(series):
    out = run_backtest(get_strategy("STR-001"), series, CostModel())
    assert out["result"].n_signals >= 0
    assert out["result"].evaluated_bars == len(series) - 50
    assert "win_rate" in out["metrics"]
    assert "profit_factor" in out["metrics"]
    assert "max_drawdown_pct" in out["metrics"]
    assert len(out["tested_combinations"]) == 1
    assert out["tested_combinations"][0]["strategy_id"] == "STR-001"


def test_run_walk_forward_windows_are_oos(series):
    wf = run_walk_forward(
        get_strategy("STR-001"), series, CostModel(),
        train_size=400, test_size=100, step=200,
    )
    assert wf["n_windows"] >= 2
    for out in wf["per_window"]:
        m = out["metrics"]
        assert m["evaluated_bars"] == 100  # só o trecho de teste
        assert out["result"].initial_capital > 0


def test_run_multi_series_and_consolidated():
    series = {
        "BTC/USDT (sintético)": make_mixed_regime_series(seed=7),
        "ETH/USDT (sintético)": make_mixed_regime_series(seed=8, start_price=50.0),
    }
    out = run_multi_series(get_strategy("STR-001"), series, CostModel())
    assert set(out["per_series"]) == set(series)
    assert out["consolidated"]["n_series"] == 2
    assert out["consolidated"]["n_trades"] == sum(
        o["result"].n_trades for o in out["per_series"].values())
    assert len(out["tested_combinations"]) == 2


def test_render_report_marks_synthetic_and_lists_combinations():
    series = make_mixed_regime_series(seed=7)
    out = run_backtest(get_strategy("STR-001"), series, CostModel())
    multi = run_multi_series(
        get_strategy("STR-001"),
        {"BTC/USDT (sintético)": series},
        CostModel(),
    )
    report = render_report(
        title="Backtest exemplo — STR-001 (sintético)",
        strategy_id="STR-001",
        strategy_version=1,
        strategy_status="experimental",
        costs=CostModel(),
        per_series=multi["per_series"],
        consolidated=multi["consolidated"],
        tested_combinations=multi["tested_combinations"],
        synthetic=True,
    )
    assert "DADOS SINTÉTICOS" in report
    assert "NÃO É RESULTADO REAL" in report
    assert "STR-001" in report
    assert "Win Rate" in report
    assert "Cobertura" in report
    assert "Combinações testadas" in report
    assert "experimental" in report
    assert "Purged CV" in report
