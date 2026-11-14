"""Backtesting — Fase 12 (BKT-001…BKT-008), especificação v4.1 §8.

Fachada do serviço: reexporta a API pública dos submódulos.

- :mod:`costs`: taxas, spread, slippage, gas, latência, fills parciais.
- :mod:`signals`: geração de sinais sem look-ahead + cobertura.
- :mod:`engine`: motor de simulação (canônico) com registro de fills.
- :mod:`metrics`: Win Rate, expectativa, PF, Sharpe/Sortino, Max DD,
  Calmar, Brier/Log Loss, cobertura, IC 95% e checagem do protocolo 85%.
- :mod:`splits`: treino/validação/teste cronológicos, walk-forward e
  purged CV com embargo.
- :mod:`runner`: backtest único, walk-forward e multi-série.
- :mod:`vectorbt_adapter`: verificação cruzada com vectorbt.
- :mod:`synthetic`: séries sintéticas (exemplo e testes).
- :mod:`report`: relatório Markdown fora da amostra.

Só simulação: nenhuma chave de API, nenhum envio de ordem, nenhuma
conexão a conta. A execução continua bloqueada (403).
"""

from __future__ import annotations

from costs import CostModel
from engine import BacktestEngine, BacktestResult, Fill, Trade
from metrics import compute_metrics, protocol_85_check, wilson_ci
from report import render_report
from runner import run_backtest, run_multi_series, run_walk_forward
from signals import SignalGeneration, generate_signals_series
from splits import chronological_split, purged_kfold_splits, walk_forward_windows
from synthetic import make_mixed_regime_series, make_synthetic_series
from vectorbt_adapter import run_vectorbt_crosscheck, vectorbt_available

__all__ = [
    "CostModel",
    "BacktestEngine",
    "BacktestResult",
    "Fill",
    "Trade",
    "compute_metrics",
    "protocol_85_check",
    "wilson_ci",
    "render_report",
    "run_backtest",
    "run_multi_series",
    "run_walk_forward",
    "SignalGeneration",
    "generate_signals_series",
    "chronological_split",
    "purged_kfold_splits",
    "walk_forward_windows",
    "make_mixed_regime_series",
    "make_synthetic_series",
    "run_vectorbt_crosscheck",
    "vectorbt_available",
]
