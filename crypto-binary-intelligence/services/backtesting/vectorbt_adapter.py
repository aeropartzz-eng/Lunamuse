"""Verificação cruzada com vectorbt — Fase 12 (BKT-001).

O vectorbt (1.2.1) é usado como backend **independente de
verificação**: os fills do motor próprio (preço e quantidade
efetivos de cada fill) são replayados por
``vbt.Portfolio.from_orders`` e o valor final é comparado com o do
motor. Taxas e gas não entram no replay (o vectorbt não modela gas
por ordem): a reconciliação é
``final_vectorbt == final_motor + taxas + gas`` — delta ~0 indica
que a contabilidade dos dois lados concorda.

Por que o vectorbt não é o motor canônico: ele não modela latência
em candles, fills parciais, gas por ordem nem registro de fill por
ordem (preço/custo/slippage) — todos exigidos pelo §8 (BKT-002 e
BKT-003). O motor próprio (``engine.py``) modela tudo isso; o
vectorbt confere a contabilidade por outro caminho, com os preços
exatos de fill.

Se o vectorbt não estiver instalado, ``run_vectorbt_crosscheck``
devolve ``{"available": False, ...}`` em vez de levantar — o motor
próprio não depende dele.
"""

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np

from costs import CostModel

__all__ = [
    "vectorbt_available",
    "run_vectorbt_crosscheck",
]


def vectorbt_available() -> bool:
    """True se o vectorbt estiver importável neste ambiente."""
    try:
        import vectorbt  # noqa: F401
        return True
    except Exception:
        return False


def run_vectorbt_crosscheck(
    candles: Sequence[Any],
    trades: Sequence[Any],
    fills: Sequence[Any],
    costs: CostModel | None = None,
    initial_capital: float = 10_000.0,
    engine_final_equity: float | None = None,
) -> Dict[str, Any]:
    """Replay dos fills do motor próprio no vectorbt.

    ``fills`` são os fills do motor (preço e quantidade efetivos);
    ``trades`` só contam os trades para conferência. Taxas e gas
    são reconciliados fora do replay (ver módulo). Devolve as
    métricas do vectorbt + o delta da reconciliação.
    """
    costs = costs or CostModel()
    try:
        import pandas as pd
        import vectorbt as vbt
    except Exception as exc:  # vectorbt ausente: sem verificação
        return {"available": False, "reason": f"vectorbt indisponível: {exc}"}

    n = len(candles)
    if n == 0:
        return {"available": False, "reason": "série vazia"}

    def _f(c, name):
        v = getattr(c, name, None)
        if v is None and isinstance(c, dict):
            v = c.get(name)
        return float(v)

    close = pd.Series([_f(c, "close") for c in candles], dtype=float)
    # Ordens por candle: quantidade assinada e preço médio ponderado
    # (em geral há no máximo 1 fill por candle; o agregado cobre o
    # caso geral sem perder valor).
    size = pd.Series(np.zeros(n, dtype=float))
    value = pd.Series(np.zeros(n, dtype=float))
    for fill in fills:
        signed = float(fill.quantity) if fill.side == "buy" else -float(fill.quantity)
        size.iloc[int(fill.index)] += signed
        value.iloc[int(fill.index)] += signed * float(fill.price)
    price = pd.Series(np.full(n, np.nan, dtype=float))
    nonzero = size != 0
    price[nonzero] = value[nonzero] / size[nonzero]

    pf = vbt.Portfolio.from_orders(
        close,
        size,
        price=price,
        init_cash=float(initial_capital),
        fees=0.0,  # taxas reconciliadas fora do replay (ver docstring)
        freq="5min",
    )
    total_fees = float(sum(float(f.fee_usd) for f in fills))
    total_gas = float(sum(float(f.gas_usd) for f in fills))
    final_value = float(pf.final_value())
    delta = None
    if engine_final_equity is not None:
        delta = final_value - (float(engine_final_equity) + total_fees + total_gas)
    trade_records = pf.trades.records_readable
    return {
        "available": True,
        "engine": f"vectorbt {vbt.__version__}",
        "total_return_pct": float(pf.total_return() * 100.0),
        "n_trades": int(len(trade_records)),
        "final_value": final_value,
        "reconciled_delta_usd": delta,
        "total_fees_usd": total_fees,
        "total_gas_usd": total_gas,
        "max_drawdown_pct": abs(float(pf.max_drawdown() * 100.0)),
        "sharpe_ratio": float(pf.sharpe_ratio()),
        "profit_factor": float(pf.trades.profit_factor()),
        "win_rate": float(pf.trades.win_rate()),
        "notes": (
            "Replay dos fills exatos do motor (preço e quantidade); "
            "taxas e gas reconciliados fora do replay: "
            "final_vectorbt == final_motor + taxas + gas."
        ),
    }
