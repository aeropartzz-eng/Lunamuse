"""Modelos do Crypto Shield (Fase 6 — SEC-001…SEC-007).

Modelos de **dados** da avaliação antifraude. Nenhum método aqui faz
rede, envia transação ou aprova nada: o veredito vive em
:mod:`crypto_shield` e segue as regras da especificação (§7).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Optional

ShieldStatus = Literal["APROVADO", "REVISÃO", "BLOQUEADO"]

# Endereços técnicos canônicos excluíveis **somente após
# classificação documentada** (§7): burn e pares/pools.
BURN_ADDRESSES = frozenset(
    {
        "0x0000000000000000000000000000000000000000",
        "0x000000000000000000000000000000000000dead",
        "11111111111111111111111111111111",  # Solana: System Program (burn)
    }
)


@dataclass(frozen=True)
class Holder:
    """Um detentor de token, com participação e classificação."""

    address: str
    balance_raw: int
    share_pct: Decimal
    label: str = "unknown"  # dev|creator|pool|burn|exchange|insider|unknown


@dataclass(frozen=True)
class HolderAnalysis:
    """Top 10/20, participação do criador e clusters (SEC-001…SEC-003)."""

    total_supply: int
    holders: tuple[Holder, ...]  # ordenados por participação desc
    top10_pct: Decimal
    top20_pct: Decimal
    top10_pct_excl_classified: Optional[Decimal] = None
    dev_pct: Decimal = Decimal("0")
    dev_address: Optional[str] = None
    clusters: tuple[dict[str, Any], ...] = ()
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class LiquidityAnalysis:
    """Liquidez total/efetiva, LP e concentração (SEC-004)."""

    total_liquidity_usd: Optional[Decimal] = None
    market_cap_usd: Optional[Decimal] = None
    liquidity_to_mcap_pct: Optional[Decimal] = None
    lp_locked_pct: Optional[Decimal] = None  # None = desconhecido
    lp_burned_pct: Optional[Decimal] = None
    lock_expiry: Optional[str] = None
    top_lp_holder_pct: Optional[Decimal] = None
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class AuthorityAnalysis:
    """Authorities e funções do contrato (SEC-005)."""

    mint_authority: Optional[str] = None  # None = revogada/ausente
    freeze_authority: Optional[str] = None
    owner: Optional[str] = None
    is_honeypot: Optional[bool] = None  # None = não verificado
    buy_tax_pct: Optional[Decimal] = None
    sell_tax_pct: Optional[Decimal] = None
    can_change_tax: Optional[bool] = None
    trading_restricted: Optional[bool] = None
    is_proxy: Optional[bool] = None
    source: str = "unknown"
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class SellSimulation:
    """Simulação de venda (só matemática; nunca transação real)."""

    scenarios: tuple[dict[str, Any], ...] = ()
    max_sellable_pct_of_pool: Optional[Decimal] = None
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class ShieldResult:
    """Veredito do Crypto Shield (SEC-007)."""

    token: str
    chain: str
    status: ShieldStatus
    risk_score: int  # 0–100 (maior = mais arriscado)
    reasons: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    holders: Optional[HolderAnalysis] = None
    liquidity: Optional[LiquidityAnalysis] = None
    authorities: Optional[AuthorityAnalysis] = None
    sell_simulation: Optional[SellSimulation] = None
    auto_approval_blocked: bool = False
    sources: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Dict serializável para API/painel/auditoria."""
        return {
            "token": self.token,
            "chain": self.chain,
            "status": self.status,
            "risk_score": self.risk_score,
            "reasons": list(self.reasons),
            "evidence": list(self.evidence),
            "auto_approval_blocked": self.auto_approval_blocked,
            "sources": list(self.sources),
            "holders": (
                {
                    "top10_pct": str(self.holders.top10_pct),
                    "top20_pct": str(self.holders.top20_pct),
                    "dev_pct": str(self.holders.dev_pct),
                    "dev_address": self.holders.dev_address,
                    "clusters": list(self.holders.clusters),
                }
                if self.holders
                else None
            ),
            "liquidity": (
                {
                    "total_liquidity_usd": (
                        str(self.liquidity.total_liquidity_usd)
                        if self.liquidity.total_liquidity_usd is not None
                        else None
                    ),
                    "liquidity_to_mcap_pct": (
                        str(self.liquidity.liquidity_to_mcap_pct)
                        if self.liquidity.liquidity_to_mcap_pct is not None
                        else None
                    ),
                    "lp_locked_pct": (
                        str(self.liquidity.lp_locked_pct)
                        if self.liquidity.lp_locked_pct is not None
                        else None
                    ),
                    "lp_burned_pct": (
                        str(self.liquidity.lp_burned_pct)
                        if self.liquidity.lp_burned_pct is not None
                        else None
                    ),
                }
                if self.liquidity
                else None
            ),
            "authorities": (
                {
                    "mint_authority": self.authorities.mint_authority,
                    "freeze_authority": self.authorities.freeze_authority,
                    "is_honeypot": self.authorities.is_honeypot,
                    "buy_tax_pct": (
                        str(self.authorities.buy_tax_pct)
                        if self.authorities.buy_tax_pct is not None
                        else None
                    ),
                    "sell_tax_pct": (
                        str(self.authorities.sell_tax_pct)
                        if self.authorities.sell_tax_pct is not None
                        else None
                    ),
                }
                if self.authorities
                else None
            ),
        }
