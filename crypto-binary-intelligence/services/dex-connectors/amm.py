"""Matemática AMM (constant product) — simulação, nunca execução (Fase 6).

Usada pela simulação de venda do Crypto Shield (SEC-004/SEC-007) e
pelas cotações de leitura dos adapters PancakeSwap/Uniswap. Nenhuma
função aqui envia transação: tudo é aritmética sobre reservas lidas
via RPC/API pública.
"""

from __future__ import annotations

from decimal import Decimal

# Taxa padrão de pool V2 (PancakeSwap/Uniswap V2): 0,25% = 25 bps.
DEFAULT_FEE_BPS = 25


def constant_product_out(
    amount_in: Decimal,
    reserve_in: Decimal,
    reserve_out: Decimal,
    fee_bps: int = DEFAULT_FEE_BPS,
) -> Decimal:
    """Quanto sai de ``reserve_out`` ao vender ``amount_in`` de token.

    Fórmula x*y=k com taxa: ``out = R_out * a * (1-f) / (R_in + a * (1-f))``.
    Retorna 0 quando as reservas são inválidas ou o montante é <= 0.
    """
    if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return Decimal("0")
    fee = Decimal(fee_bps) / Decimal(10_000)
    amount_in_after_fee = amount_in * (Decimal("1") - fee)
    return (reserve_out * amount_in_after_fee) / (
        reserve_in + amount_in_after_fee
    )


def spot_price(reserve_in: Decimal, reserve_out: Decimal) -> Decimal:
    """Preço spot (unidades de ``reserve_out`` por 1 de token)."""
    if reserve_in <= 0 or reserve_out <= 0:
        return Decimal("0")
    return reserve_out / reserve_in


def price_impact_pct(
    amount_in: Decimal,
    reserve_in: Decimal,
    reserve_out: Decimal,
    fee_bps: int = DEFAULT_FEE_BPS,
) -> Decimal:
    """Impacto percentual da venda sobre o preço (0–100).

    ``1 - (preço executado / preço spot)``. 100% = venda sem saída
    (honeypot prático na simulação).
    """
    if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return Decimal("100")
    executed = constant_product_out(
        amount_in, reserve_in, reserve_out, fee_bps
    )
    if executed <= 0:
        return Decimal("100")
    executed_price = executed / amount_in
    spot = spot_price(reserve_in, reserve_out)
    if spot <= 0:
        return Decimal("100")
    impact = (Decimal("1") - executed_price / spot) * Decimal("100")
    return max(Decimal("0"), min(Decimal("100"), impact))
