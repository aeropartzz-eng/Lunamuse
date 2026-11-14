"""Testes de métricas — Fase 12 (BKT-007).

Valores calculados à mão a partir de uma sequência conhecida de
trades; sem rede.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine import BacktestResult, Trade
from metrics import compute_metrics, max_drawdown, protocol_85_check, wilson_ci


def _result(trades, equity, initial=10_000.0, n_signals=5, evaluated=100):
    return BacktestResult(
        symbol="BTC/USDT",
        strategy_id="STR-TEST",
        strategy_version=1,
        initial_capital=initial,
        final_equity=float(equity[-1]),
        equity_curve=np.array(equity, dtype=float),
        trades=trades,
        fills=[],
        n_signals=n_signals,
        n_signals_executed=len(trades),
        evaluated_bars=evaluated,
    )


def _trade(pnl, prob=None, stop=None, entry=100.0):
    return Trade(
        trade_id=1, direction="long", entry_index=0, exit_index=1,
        entry_price=entry, exit_price=entry + pnl / 100.0, quantity=100.0,
        stop_loss=stop, probability=prob, exit_reason="target",
    )


def test_metrics_known_trade_sequence():
    """PnLs líquidos [100, -50, 200, -50, 100] (qty 100, entry 100):
    win rate 3/5 = 60%; expectativa 60; PF 400/100 = 4; payoff 2."""
    pnls = [100.0, -50.0, 200.0, -50.0, 100.0]
    trades = [_trade(p) for p in pnls]
    equity = [10_000.0, 10_100.0, 10_050.0, 10_250.0, 10_200.0, 10_300.0]
    m = compute_metrics(_result(trades, equity))
    assert m["n_trades"] == 5
    assert m["n_wins"] == 3 and m["n_losses"] == 2
    assert m["win_rate"] == pytest.approx(0.6)
    assert m["precision"] == pytest.approx(0.6)
    assert m["expectancy_usd"] == pytest.approx(60.0)
    assert m["expectancy_pct_capital"] == pytest.approx(0.6)
    assert m["gross_profit_usd"] == pytest.approx(400.0)
    assert m["gross_loss_usd"] == pytest.approx(100.0)
    assert m["profit_factor"] == pytest.approx(4.0)
    assert m["avg_win_usd"] == pytest.approx(400.0 / 3.0)
    assert m["avg_loss_usd"] == pytest.approx(-50.0)
    assert m["payoff_ratio"] == pytest.approx((400.0 / 3.0) / 50.0)
    assert m["total_return_pct"] == pytest.approx(3.0)
    # Max DD: pico 10.100 -> vale 10.050 = 0,495%.
    assert m["max_drawdown_pct"] == pytest.approx(100.0 * 50.0 / 10_100.0)
    # Cobertura: 5 sinais / 100 candles avaliados.
    assert m["coverage_signals_per_100_bars"] == pytest.approx(5.0)
    assert m["coverage_execution_rate"] == pytest.approx(1.0)
    # Expectativa em R: risco = (100 - stop) * 100; sem stop, R = 0.
    assert m["expectancy_r"] == pytest.approx(0.0)


def test_metrics_no_trades():
    m = compute_metrics(_result([], [10_000.0, 10_000.0], n_signals=0, evaluated=50))
    assert m["n_trades"] == 0
    assert m["win_rate"] == 0.0
    assert m["profit_factor"] == 0.0
    assert m["max_drawdown_pct"] == pytest.approx(0.0)
    assert m["sharpe"] is None
    assert m["win_rate_ci95"] is None


def test_metrics_all_wins_profit_factor_infinite():
    trades = [_trade(100.0), _trade(50.0)]
    m = compute_metrics(_result(trades, [10_000.0, 10_100.0, 10_150.0], n_signals=2))
    assert m["profit_factor"] == float("inf")
    assert m["win_rate"] == pytest.approx(1.0)


def test_wilson_ci_known_values():
    ci = wilson_ci(3, 5)
    assert ci is not None
    # Wilson 95% para 3/5: centro 0,6; intervalo aprox. [0,23; 0,88].
    assert ci["low"] == pytest.approx(0.2307, abs=0.01)
    assert ci["high"] == pytest.approx(0.8824, abs=0.01)
    assert wilson_ci(0, 0) is None
    assert wilson_ci(0, 10)["low"] == pytest.approx(0.0)


def test_max_drawdown_known_curve():
    dd = max_drawdown(np.array([100.0, 110.0, 105.0, 120.0, 90.0, 95.0]))
    # Pico 120 -> vale 90 = 25%.
    assert dd["max_drawdown_pct"] == pytest.approx(25.0)
    assert dd["peak_index"] == 3
    assert dd["trough_index"] == 4


def test_brier_and_logloss_with_probabilities():
    # Probabilidades [0,8; 0,6; 0,7] com resultados [win, loss, win]:
    # Brier = ((0,8-1)^2 + (0,6-0)^2 + (0,7-1)^2)/3 = 0,1633.
    trades = [_trade(100.0, prob=0.8), _trade(-50.0, prob=0.6), _trade(50.0, prob=0.7)]
    m = compute_metrics(_result(trades, [10_000.0, 10_100.0, 10_050.0, 10_100.0], n_signals=3))
    assert m["brier_score"] == pytest.approx((0.04 + 0.36 + 0.09) / 3.0)
    expected_ll = -(
        math.log(0.8) + math.log(0.4) + math.log(0.7)
    ) / 3.0
    assert m["log_loss"] == pytest.approx(expected_ll)
    assert m["n_scored"] == 3


def test_protocol_85_check():
    m = {
        "profit_factor": 2.0, "sharpe": 2.0, "max_drawdown_pct": 5.0,
        "n_trades": 600, "expectancy_usd": 10.0,
    }
    check = protocol_85_check(m, oos=True)
    assert check["all_passed"] is True
    m["n_trades"] = 10
    check = protocol_85_check(m, oos=True)
    assert check["all_passed"] is False
    assert any(c["criterion"].startswith(">= 500") and not c["passed"]
               for c in check["checks"])
