"""Verificação de LP e liquidez + simulação de venda (Fase 6 — SEC-004).

- Liquidez total e efetiva, liquidez/market cap, LP bloqueada ou
  queimada, prazo de bloqueio, concentração de provedores.
- Simulação de venda e slippage estimado (matemática AMM — nunca
  transação real).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

try:
    from amm import constant_product_out, price_impact_pct
    from shield_models import LiquidityAnalysis, SellSimulation
except ImportError:  # diretórios fora do sys.path
    import sys
    from pathlib import Path

    _here = Path(__file__).resolve().parent
    sys.path.append(str(_here.parent / "dex-connectors"))
    sys.path.append(str(_here))
    from amm import constant_product_out, price_impact_pct
    from shield_models import LiquidityAnalysis, SellSimulation


def analyze_liquidity(
    total_liquidity_usd: Optional[Decimal] = None,
    market_cap_usd: Optional[Decimal] = None,
    lp_locked_pct: Optional[Decimal] = None,
    lp_burned_pct: Optional[Decimal] = None,
    lock_expiry: Optional[str] = None,
    top_lp_holder_pct: Optional[Decimal] = None,
) -> LiquidityAnalysis:
    """Métricas de liquidez a partir de valores já coletados.

    Os valores vêm de DEX Screener / RugCheck / leitura on-chain de LP;
    aqui só há cálculo e sinalização — nenhuma coleta de rede.
    """
    ratio = None
    if (
        total_liquidity_usd is not None
        and market_cap_usd is not None
        and market_cap_usd > 0
    ):
        ratio = (total_liquidity_usd / market_cap_usd) * Decimal("100")

    evidence: list[str] = []
    if total_liquidity_usd is None:
        evidence.append("liquidez total desconhecida")
    elif total_liquidity_usd < Decimal("5000"):
        evidence.append(f"liquidez muito baixa: US$ {total_liquidity_usd}")
    if lp_locked_pct is None and lp_burned_pct is None:
        evidence.append("status do LP (bloqueado/queimado) desconhecido")
    if lp_locked_pct is not None and lp_locked_pct < Decimal("50"):
        evidence.append(f"LP pouco bloqueado: {lp_locked_pct}%")
    if top_lp_holder_pct is not None and top_lp_holder_pct > Decimal("50"):
        evidence.append(
            f"LP concentrado: maior provedor com {top_lp_holder_pct}%"
        )
    if lock_expiry:
        evidence.append(f"bloqueio de LP ate {lock_expiry}")

    return LiquidityAnalysis(
        total_liquidity_usd=total_liquidity_usd,
        market_cap_usd=market_cap_usd,
        liquidity_to_mcap_pct=ratio,
        lp_locked_pct=lp_locked_pct,
        lp_burned_pct=lp_burned_pct,
        lock_expiry=lock_expiry,
        top_lp_holder_pct=top_lp_holder_pct,
        evidence=tuple(evidence),
    )


def simulate_sell(
    reserve_token: Decimal,
    reserve_quote: Decimal,
    sell_fractions_of_pool: tuple[Decimal, ...] = (
        Decimal("0.01"),
        Decimal("0.05"),
        Decimal("0.10"),
        Decimal("0.25"),
    ),
    fee_bps: int = 25,
) -> SellSimulation:
    """Simula vendas de frações do pool e estima slippage.

    ``reserve_token``/``reserve_quote``: reservas do pool (unidades do
    token e do quote). Retorna, por cenário, quanto sairia (em unidades
    do quote) e o impacto no preço. Sem preço do quote em USD, não há
    conversão para dólar — nenhum preço é inventado.
    """
    scenarios: list[dict[str, Any]] = []
    evidence: list[str] = []
    if reserve_token <= 0 or reserve_quote <= 0:
        evidence.append("sem reservas validas p/ simular venda")
        return SellSimulation(scenarios=(), evidence=tuple(evidence))

    max_sellable: Optional[Decimal] = None
    for fraction in sell_fractions_of_pool:
        amount_in = reserve_token * fraction
        out = constant_product_out(
            amount_in, reserve_token, reserve_quote, fee_bps
        )
        impact = price_impact_pct(
            amount_in, reserve_token, reserve_quote, fee_bps
        )
        scenarios.append(
            {
                "sell_fraction_of_pool": str(fraction),
                "amount_in": str(amount_in),
                "amount_out_quote": str(out),
                "price_impact_pct": str(impact),
            }
        )
        # Maior venda com impacto <= 10% (limite interno conservador).
        if impact <= Decimal("10"):
            max_sellable = fraction
        if impact > Decimal("50"):
            evidence.append(
                f"venda de {fraction * 100}% do pool tem impacto de {impact}%"
            )
    return SellSimulation(
        scenarios=tuple(scenarios),
        max_sellable_pct_of_pool=max_sellable,
        evidence=tuple(evidence),
    )
