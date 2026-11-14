"""Métricas do backtest — Fase 12 (BKT-007), §8 e protocolo do 85%.

Todas as métricas são funções puras sobre trades + curva de equity,
com fórmulas explícitas para conferência manual (os testes usam
sequências de trades com valores calculados à mão).

Métricas
--------
- Win Rate (= precisão sobre trades fechados) e intervalo de
  confiança de Wilson (95%).
- Expectativa matemática: PnL líquido médio por trade (USD, % do
  capital e em R — múltiplos do risco inicial).
- Retorno líquido total, Profit Factor, Sharpe e Sortino
  (anualizados pela granularidade do timeframe; cripto opera 24/7:
  ``bars_per_year = 525600 / timeframe_min``). Anualização só com
  >= 30 dias de candles — com séries mais curtas, Sharpe, Sortino,
  retorno anualizado e Calmar são None ("n/d").
- Maximum Drawdown, Calmar (retorno anualizado / max DD).
- Cobertura: sinais gerados por 100 candles avaliados e taxa de
  execução (trades / sinais) — sempre junto com a precisão, como
  exige o protocolo do 85%.
- Brier Score e Log Loss da probabilidade do sinal vs. o resultado
  do trade (a probabilidade das STR-001…STR-010 é escore de
  confluência, NÃO calibrada — Fase 13; os valores aqui medem o
  quanto ela se afasta de uma probabilidade, sem fingir calibração).
- Precision = win rate (trades). Recall não é computável num
  backtest direcional sem um conjunto rotulado de oportunidades
  perdidas — o relatório informa isso explicitamente em vez de
  inventar um número.

Referências do §8 (triagem, não aprovação): Profit Factor > 1,3;
Sharpe > 1,5; drawdown < 10%; >= 500 operações fora da amostra por
estratégia (crypto scalping). ``protocol_85_check`` compara e
devolve PASS/FAIL por critério.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

__all__ = [
    "compute_metrics",
    "wilson_ci",
    "max_drawdown",
    "bars_per_year",
    "protocol_85_check",
    "TIMEFRAME_MINUTES",
]

TIMEFRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
    "1d": 1440, "1w": 10080,
}

# Referências de triagem do §8 (não são aprovação automática).
REF_PROFIT_FACTOR = 1.3
REF_SHARPE = 1.5
REF_MAX_DRAWDOWN_PCT = 10.0
REF_MIN_OOS_TRADES = 500


def bars_per_year(timeframe: str) -> float:
    """Candles por ano (cripto 24/7)."""
    minutes = TIMEFRAME_MINUTES.get(timeframe, 5)
    return 525_600.0 / minutes


def wilson_ci(wins: int, n: int, z: float = 1.96) -> Optional[Dict[str, float]]:
    """Intervalo de Wilson (95%) para uma proporção."""
    if n <= 0:
        return None
    p = wins / n
    denom = 1.0 + z * z / n
    center = p + z * z / (2.0 * n)
    margin = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return {
        "low": max(0.0, (center - margin) / denom),
        "high": min(1.0, (center + margin) / denom),
        "center": p,
    }


def max_drawdown(equity: np.ndarray) -> Dict[str, float]:
    """Max drawdown (relativo ao pico) e onde ocorreu."""
    equity = np.asarray(equity, dtype=float)
    if len(equity) == 0:
        return {"max_drawdown_pct": 0.0, "peak_index": 0, "trough_index": 0}
    peaks = np.maximum.accumulate(equity)
    dd = np.where(peaks > 0, (peaks - equity) / peaks, 0.0)
    trough = int(np.argmax(dd))
    peak = int(np.argmax(equity[: trough + 1])) if trough > 0 else 0
    return {
        "max_drawdown_pct": float(dd[trough] * 100.0),
        "peak_index": peak,
        "trough_index": trough,
    }


def _brier_logloss(trades: List[Any]) -> Dict[str, Optional[float]]:
    """Brier e Log Loss da probabilidade do sinal vs. resultado."""
    pairs = [
        (float(t.probability), 1.0 if t.net_pnl_usd > 0 else 0.0)
        for t in trades
        if t.probability is not None and t.exit_index is not None
    ]
    if not pairs:
        return {"brier_score": None, "log_loss": None, "n_scored": 0}
    eps = 1e-15
    brier = float(np.mean([(p - y) ** 2 for p, y in pairs]))
    logloss = float(np.mean([
        -(y * math.log(min(max(p, eps), 1 - eps))
          + (1 - y) * math.log(min(max(1 - p, eps), 1 - eps)))
        for p, y in pairs
    ]))
    return {"brier_score": brier, "log_loss": logloss, "n_scored": len(pairs)}


def compute_metrics(result: Any, timeframe: str = "5m") -> Dict[str, Any]:
    """Calcula todas as métricas §8 de um ``BacktestResult``."""
    trades = [t for t in result.trades if t.exit_index is not None]
    equity = np.asarray(result.equity_curve, dtype=float)
    n = len(trades)
    wins = [t for t in trades if t.net_pnl_usd > 0]
    losses = [t for t in trades if t.net_pnl_usd < 0]
    n_wins, n_losses = len(wins), len(losses)

    net_pnls = np.array([t.net_pnl_usd for t in trades], dtype=float) if n else np.zeros(0)
    gross_profit = float(sum(t.net_pnl_usd for t in wins)) if n_wins else 0.0
    gross_loss = float(sum(-t.net_pnl_usd for t in losses)) if n_losses else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
        float("inf") if gross_profit > 0 else 0.0
    )
    win_rate = (n_wins / n) if n else 0.0
    expectancy_usd = float(np.mean(net_pnls)) if n else 0.0
    expectancy_pct = (
        100.0 * expectancy_usd / result.initial_capital if result.initial_capital > 0 else 0.0
    )
    expectancy_r = float(np.mean([t.pnl_r for t in trades])) if n else 0.0
    avg_win = float(np.mean([t.net_pnl_usd for t in wins])) if n_wins else 0.0
    avg_loss = float(np.mean([t.net_pnl_usd for t in losses])) if n_losses else 0.0
    payoff = (avg_win / abs(avg_loss)) if avg_loss < 0 else 0.0

    # Sharpe/Sortino/anualização: só fazem sentido com amostra de
    # duração mínima (>= 30 dias de candles); com séries curtas o
    # expoente de anualização explode e o número vira lixo — nestes
    # casos devolve None ("n/d") em vez de um valor absurdo.
    bpay = bars_per_year(timeframe)
    n_bars_total = max(len(equity) - 1, 1)
    annualize = n_bars_total >= bpay / 12.0
    sharpe = sortino = None
    if len(equity) > 1 and annualize:
        rets = np.diff(equity) / np.where(equity[:-1] != 0, equity[:-1], np.nan)
        rets = rets[np.isfinite(rets)]
        if len(rets) > 1:
            std = float(np.std(rets, ddof=1))
            mean = float(np.mean(rets))
            if std > 0:
                sharpe = mean / std * math.sqrt(bpay)
            neg = rets[rets < 0]
            if len(neg) > 1:
                downside = float(np.std(neg, ddof=1))
                if downside > 0:
                    sortino = mean / downside * math.sqrt(bpay)

    dd = max_drawdown(equity)
    total_return = result.total_return_pct
    n_bars = max(len(equity) - 1, 1)
    # Anualização: com pouquíssimos candles o expoente explode
    # (ex.: 3 candles de 5m -> (1+r)**52560); séries curtas não
    # suportam anualização — devolve None (ver `annualize` acima).
    base = 1.0 + total_return / 100.0
    if not annualize or result.initial_capital <= 0 or base <= 0:
        annualized_return_pct = None
    else:
        try:
            annualized_return_pct = (
                100.0 * (base ** (bpay / n_bars) - 1.0)
            )
        except OverflowError:
            annualized_return_pct = (
                float("inf") if total_return > 0 else float("-inf")
            )
    calmar = None
    if annualized_return_pct is not None and dd["max_drawdown_pct"] > 0:
        calmar = annualized_return_pct / dd["max_drawdown_pct"]

    # Streaks.
    max_win_streak = max_loss_streak = cur_w = cur_l = 0
    for t in trades:
        if t.net_pnl_usd > 0:
            cur_w += 1
            cur_l = 0
            max_win_streak = max(max_win_streak, cur_w)
        elif t.net_pnl_usd < 0:
            cur_l += 1
            cur_w = 0
            max_loss_streak = max(max_loss_streak, cur_l)
        else:
            cur_w = cur_l = 0

    scoring = _brier_logloss(trades)
    ci = wilson_ci(n_wins, n)

    return {
        "n_trades": n,
        "n_wins": n_wins,
        "n_losses": n_losses,
        "n_breakeven": n - n_wins - n_losses,
        "win_rate": win_rate,
        "win_rate_ci95": ci,
        "precision": win_rate,  # precisão sobre trades fechados
        "recall": None,  # sem conjunto rotulado de oportunidades perdidas
        "expectancy_usd": expectancy_usd,
        "expectancy_pct_capital": expectancy_pct,
        "expectancy_r": expectancy_r,
        "total_return_pct": total_return,
        "annualized_return_pct": annualized_return_pct,
        "gross_profit_usd": gross_profit,
        "gross_loss_usd": gross_loss,
        "profit_factor": profit_factor,
        "avg_win_usd": avg_win,
        "avg_loss_usd": avg_loss,
        "payoff_ratio": payoff,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown_pct": dd["max_drawdown_pct"],
        "max_drawdown_peak_index": dd["peak_index"],
        "max_drawdown_trough_index": dd["trough_index"],
        "calmar": calmar,
        "max_win_streak": max_win_streak,
        "max_loss_streak": max_loss_streak,
        "avg_holding_bars": (
            float(np.mean([t.holding_bars for t in trades if t.holding_bars is not None]))
            if any(t.holding_bars is not None for t in trades) else 0.0
        ),
        "brier_score": scoring["brier_score"],
        "log_loss": scoring["log_loss"],
        "n_scored": scoring["n_scored"],
        # Cobertura (§8 / protocolo do 85%): sempre junto com a precisão.
        "coverage_signals_per_100_bars": (
            100.0 * result.n_signals / result.evaluated_bars if result.evaluated_bars else 0.0
        ),
        "coverage_execution_rate": result.execution_rate,
        "n_signals": result.n_signals,
        "n_signals_executed": result.n_signals_executed,
        "evaluated_bars": result.evaluated_bars,
        "total_fees_usd": float(sum(f.fee_usd for f in result.fills)),
        "total_slippage_usd": float(sum(f.slippage_usd for f in result.fills)),
        "total_gas_usd": float(sum(f.gas_usd for f in result.fills)),
        "total_cost_usd": float(sum(f.total_cost_usd for f in result.fills)),
        "n_fills": len(result.fills),
    }


def protocol_85_check(metrics: Dict[str, Any], oos: bool = True) -> Dict[str, Any]:
    """Compara as métricas com as referências de triagem do §8.

    ``oos`` indica se as métricas são fora da amostra (o §8 exige
    amostras fora da amostra para qualquer leitura de aprovação).
    Devolve um item por critério, com PASS/FAIL e o valor observado.
    """
    pf = metrics.get("profit_factor")
    sharpe = metrics.get("sharpe")
    dd = metrics.get("max_drawdown_pct")
    n = metrics.get("n_trades", 0)
    checks = [
        {
            "criterion": "Profit Factor > 1,3",
            "observed": pf,
            "passed": (pf is not None and pf > REF_PROFIT_FACTOR),
        },
        {
            "criterion": "Sharpe > 1,5",
            "observed": sharpe,
            "passed": (sharpe is not None and sharpe > REF_SHARPE),
        },
        {
            "criterion": "Maximum Drawdown < 10%",
            "observed": dd,
            "passed": (dd is not None and dd < REF_MAX_DRAWDOWN_PCT),
        },
        {
            "criterion": ">= 500 operações fora da amostra",
            "observed": n,
            "passed": (oos and n >= REF_MIN_OOS_TRADES),
        },
        {
            "criterion": "Expectativa líquida positiva",
            "observed": metrics.get("expectancy_usd"),
            "passed": (metrics.get("expectancy_usd") or 0.0) > 0,
        },
    ]
    return {
        "oos": oos,
        "checks": checks,
        "all_passed": all(c["passed"] for c in checks),
    }
