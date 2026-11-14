"""Orquestração dos backtests — Fase 12 (BKT-004/BKT-005/BKT-008).

- :func:`run_backtest`: uma estratégia sobre uma série (gera sinais
  sem look-ahead, simula, calcula métricas).
- :func:`run_walk_forward`: janelas deslizantes de
  ``splits.walk_forward_windows``; em cada janela, os sinais são
  gerados **só dentro do trecho de teste** (o treino é registrado
  como contexto, mas nenhum parâmetro é ajustado nele nesta fase —
  as STR-001…STR-010 são v1 fixas; a reotimização por janela é
  trabalho da Fase 13). O relatório por janela mede a estabilidade
  fora da amostra.
- :func:`run_multi_series`: mesma estratégia/custos sobre várias
  séries (ativos diferentes) — relatório por série e consolidado
  (trades agregados; cada série recebe o mesmo capital inicial).

Registro de combinações (§8): cada chamada devolve, em
``tested_combinations``, a combinação executada (estratégia,
versão, parâmetros, custos, série, janela) — o relatório as lista
todas, para que o risco de overfitting por múltiplos testes fique
visível.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from costs import CostModel
from engine import BacktestEngine, BacktestResult
from metrics import compute_metrics
from signals import generate_signals_series
from splits import walk_forward_windows

__all__ = [
    "run_backtest",
    "run_walk_forward",
    "run_multi_series",
]


def _timeframe_of(candles: Sequence[Any]) -> str:
    first = candles[0]
    tf = getattr(first, "timeframe", None)
    if tf is None and isinstance(first, dict):
        tf = first.get("timeframe")
    return str(tf or "5m")


def _symbol_of(candles: Sequence[Any]) -> str:
    first = candles[0]
    sym = getattr(first, "symbol", None)
    if sym is None and isinstance(first, dict):
        sym = first.get("symbol")
    return str(sym or "BTC/USDT")


def run_backtest(
    strategy: Any,
    candles: Sequence[Any],
    costs: Optional[CostModel] = None,
    initial_capital: float = 10_000.0,
    position_size_pct: float = 1.0,
    *,
    symbol: Optional[str] = None,
    series_label: str = "",
    start_index: int = 0,
    end_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Roda uma estratégia sobre uma série (ou um trecho dela).

    ``start_index``: os sinais só são gerados a partir deste índice
    (o motor roda sobre a série inteira recebida — o prefixo antes
    de ``start_index`` serve só de warm-up causal dos indicadores,
    nunca de sinais). ``end_index`` corta a série.
    """
    candles = list(candles)
    if end_index is not None:
        candles = candles[:end_index]
    if not candles:
        raise ValueError("série vazia para o backtest")
    timeframe = _timeframe_of(candles)
    symbol = symbol or _symbol_of(candles)
    gen = generate_signals_series(
        strategy, candles, symbol=symbol, start_index=start_index,
    )
    engine = BacktestEngine(
        costs=costs or CostModel(),
        initial_capital=initial_capital,
        position_size_pct=position_size_pct,
    )
    result: BacktestResult = engine.run(
        candles,
        gen.signals,
        symbol=symbol,
        strategy_id=strategy.code,
        strategy_version=int(strategy.version),
        series_label=series_label or symbol,
        evaluated_bars=gen.evaluated_bars,
        params=dict(getattr(strategy, "params", {})),
    )
    metrics = compute_metrics(result, timeframe=timeframe)
    return {
        "result": result,
        "metrics": metrics,
        "generation": gen,
        "timeframe": timeframe,
        "tested_combinations": [{
            "strategy_id": strategy.code,
            "strategy_version": int(strategy.version),
            "params": dict(getattr(strategy, "params", {})),
            "costs": (costs or CostModel()).to_dict(),
            "series": series_label or symbol,
            "window": f"[{start_index}:{end_index or len(candles)}]",
            "initial_capital": initial_capital,
            "position_size_pct": position_size_pct,
        }],
    }


def run_walk_forward(
    strategy: Any,
    candles: Sequence[Any],
    costs: Optional[CostModel] = None,
    initial_capital: float = 10_000.0,
    position_size_pct: float = 1.0,
    *,
    train_size: int = 400,
    test_size: int = 100,
    step: int = 100,
    embargo_bars: int = 0,
    symbol: Optional[str] = None,
    series_label: str = "",
) -> Dict[str, Any]:
    """Walk-forward: janelas deslizantes com teste fora da amostra.

    Cada janela roda :func:`run_backtest` sobre o prefixo até o fim
    do teste, com sinais gerados só a partir do início do teste
    (o prefixo anterior serve de warm-up causal dos indicadores —
    nada após o fim do teste é visto). As métricas da janela são
    restritas ao trecho de teste: trades com entrada no teste e
    curva de equity do teste, com capital inicial igual ao equity
    no candle anterior ao teste.
    """
    import dataclasses

    candles = list(candles)
    symbol = symbol or _symbol_of(candles)
    windows = walk_forward_windows(
        len(candles), train_size, test_size, step, embargo_bars,
    )
    per_window: List[Dict[str, Any]] = []
    combos: List[Dict[str, Any]] = []
    pooled_trades: List[Any] = []
    for k, window in enumerate(windows):
        test_start, test_end = window["test"]
        prefix = candles[:test_end]
        out = run_backtest(
            strategy, prefix, costs, initial_capital, position_size_pct,
            symbol=symbol,
            series_label=f"{series_label or symbol} [janela {k + 1}]",
            start_index=test_start,
        )
        res = out["result"]
        # Restringe o resultado ao trecho de teste.
        window_trades = [t for t in res.trades if t.entry_index >= test_start]
        window_equity = res.equity_curve[test_start:]
        window_capital = float(res.equity_curve[test_start - 1]) if test_start > 0 else res.initial_capital
        window_result = dataclasses.replace(
            res,
            trades=window_trades,
            equity_curve=window_equity,
            initial_capital=window_capital,
            final_equity=float(window_equity[-1]) if len(window_equity) else window_capital,
            n_signals_executed=len(window_trades),
        )
        out["result"] = window_result
        out["metrics"] = compute_metrics(window_result, timeframe=out["timeframe"])
        out["window"] = window
        out["window_index"] = k
        per_window.append(out)
        combos.extend(out["tested_combinations"])
        pooled_trades.extend(window_trades)
    return {
        "windows": windows,
        "per_window": per_window,
        "tested_combinations": combos,
        "n_windows": len(windows),
        "pooled_n_trades": len(pooled_trades),
    }


def run_multi_series(
    strategy: Any,
    series: Dict[str, Sequence[Any]],
    costs: Optional[CostModel] = None,
    initial_capital: float = 10_000.0,
    position_size_pct: float = 1.0,
) -> Dict[str, Any]:
    """Mesma estratégia/custos sobre várias séries (BKT-008)."""
    per_series: Dict[str, Dict[str, Any]] = {}
    combos: List[Dict[str, Any]] = []
    pooled_trades: List[Any] = []
    total_final = 0.0
    total_initial = 0.0
    for label, candles in series.items():
        out = run_backtest(
            strategy, list(candles), costs, initial_capital,
            position_size_pct, series_label=label,
        )
        per_series[label] = out
        combos.extend(out["tested_combinations"])
        pooled_trades.extend(out["result"].trades)
        total_final += out["result"].final_equity
        total_initial += out["result"].initial_capital
    # Consolidado sobre os trades agregados (métricas de trades) e
    # sobre o capital total alocado (retorno consolidado).
    wins = [t for t in pooled_trades if t.net_pnl_usd > 0]
    gross_profit = sum(t.net_pnl_usd for t in wins)
    gross_loss = sum(-t.net_pnl_usd for t in pooled_trades if t.net_pnl_usd < 0)
    consolidated = {
        "n_series": len(series),
        "n_trades": len(pooled_trades),
        "win_rate": (len(wins) / len(pooled_trades)) if pooled_trades else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else (
            float("inf") if gross_profit > 0 else 0.0
        ),
        "expectancy_usd": (
            sum(t.net_pnl_usd for t in pooled_trades) / len(pooled_trades)
            if pooled_trades else 0.0
        ),
        "total_return_pct": (
            100.0 * (total_final - total_initial) / total_initial
            if total_initial > 0 else 0.0
        ),
        "total_final_equity": total_final,
        "total_initial_capital": total_initial,
    }
    return {
        "per_series": per_series,
        "consolidated": consolidated,
        "tested_combinations": combos,
    }
