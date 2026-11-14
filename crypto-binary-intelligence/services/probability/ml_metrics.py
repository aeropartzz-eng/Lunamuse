"""Métricas de modelos probabilísticos — Fase 13 (ML-007), §8.

Funções puras em NumPy (sem depender de versão do sklearn):

- ``brier_score`` / ``log_loss``: qualidade da probabilidade;
- ``precision_recall_f1``: qualidade da classificação;
- ``wilson_ci``: intervalo de Wilson 95% (mesma fórmula de
  ``backtesting/metrics.py`` — duplicada aqui para o módulo ser
  autocontido);
- ``evaluate_classifier``: resumo completo de um classificador;
- ``trade_expectancy``: Win Rate e expectativa quando o modelo vira
  sinal (só prevê "sobe" → opera comprado; custo por trade em bps,
  mesmas premissas de custo da Fase 12).
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

import numpy as np

__all__ = [
    "brier_score",
    "log_loss",
    "precision_recall_f1",
    "wilson_ci",
    "evaluate_classifier",
    "trade_expectancy",
]


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Brier Score: média de ``(p - y)^2``. 0 é perfeito; 0,25 é o
    escore de um modelo que sempre prevê 0,5."""
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) != len(y_prob):
        raise ValueError("y_true e y_prob com tamanhos diferentes")
    if len(y_true) == 0:
        raise ValueError("série vazia")
    return float(np.mean((y_prob - y_true) ** 2))


def log_loss(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Log Loss (entropia cruzada binária); probabilidades cortadas
    em [1e-15, 1-1e-15] para não divergir."""
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(y_true) != len(y_prob):
        raise ValueError("y_true e y_prob com tamanhos diferentes")
    if len(y_true) == 0:
        raise ValueError("série vazia")
    eps = 1e-15
    p = np.clip(y_prob, eps, 1.0 - eps)
    return float(-np.mean(
        y_true * np.log(p) + (1.0 - y_true) * np.log(1.0 - p)
    ))


def precision_recall_f1(
    y_true: np.ndarray, y_pred: np.ndarray
) -> Dict[str, float]:
    """Precision / Recall / F1 da classe positiva (1 = "sobe")."""
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    if len(y_true) != len(y_pred):
        raise ValueError("y_true e y_pred com tamanhos diferentes")
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "tp": tp, "fp": fp, "fn": fn,
    }


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


def evaluate_classifier(
    y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray
) -> Dict[str, Any]:
    """Resumo completo: acurácia, precision/recall/F1, Brier, Log Loss."""
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    y_prob = np.asarray(y_prob, dtype=float)
    prf = precision_recall_f1(y_true, y_pred)
    return {
        "n": int(len(y_true)),
        "n_positive": int((y_true == 1).sum()),
        "accuracy": float(np.mean(y_pred == y_true)) if len(y_true) else 0.0,
        "precision": prf["precision"],
        "recall": prf["recall"],
        "f1": prf["f1"],
        "tp": prf["tp"], "fp": prf["fp"], "fn": prf["fn"],
        "brier_score": brier_score(y_true, y_prob),
        "log_loss": log_loss(y_true, y_prob),
    }


def trade_expectancy(
    future_returns: np.ndarray,
    y_pred: np.ndarray,
    cost_bps: float = 30.0,
) -> Dict[str, Any]:
    """Win Rate e expectativa quando o modelo vira sinal (ML-007).

    Regra do sinal: prevê 1 ("sobe") → opera comprado no horizonte;
    prevê 0 → sem trade (WAIT / NO TRADE). O retorno líquido do
    trade é ``future_log_return - custo``; o custo padrão de 30 bps
    por trade é a soma das premissas da Fase 12 (taxa 10 bps/lado
    + spread 5 bps + slippage 5 bps, ida e volta).
    """
    future_returns = np.asarray(future_returns, dtype=float)
    y_pred = np.asarray(y_pred).astype(int)
    if len(future_returns) != len(y_pred):
        raise ValueError("future_returns e y_pred com tamanhos diferentes")
    cost = float(cost_bps) / 10_000.0
    traded = y_pred == 1
    n_trades = int(traded.sum())
    if n_trades == 0:
        return {
            "n_trades": 0, "win_rate": 0.0, "n_wins": 0,
            "expectancy_per_trade": 0.0, "expectancy_bps": 0.0,
            "total_return": 0.0, "cost_bps_per_trade": float(cost_bps),
        }
    net = future_returns[traded] - cost
    n_wins = int((net > 0).sum())
    return {
        "n_trades": n_trades,
        "win_rate": float(n_wins / n_trades),
        "n_wins": n_wins,
        "expectancy_per_trade": float(np.mean(net)),
        "expectancy_bps": float(np.mean(net) * 10_000.0),
        "total_return": float(np.sum(net)),
        "cost_bps_per_trade": float(cost_bps),
    }
