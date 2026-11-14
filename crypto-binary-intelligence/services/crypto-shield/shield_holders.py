"""Holder Intelligence (Fase 6 — SEC-001…SEC-003).

Top 10/20, participação do criador/dev e clusters de carteiras
relacionadas. Regras da especificação (§7):

- Pools, burn addresses e carteiras técnicas só são excluídos do
  Top 10 **após classificação documentada** — a exclusão é entrada
  explícita, nunca presunção.
- Vínculo entre carteiras (cluster) só existe com evidência
  (origem comum de financiamento); sem dados, nada é presumido.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, Optional

try:
    from shield_models import BURN_ADDRESSES, Holder, HolderAnalysis
except ImportError:  # diretório fora do sys.path
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent))
    from shield_models import BURN_ADDRESSES, Holder, HolderAnalysis


def _pct(part: int, total: int) -> Decimal:
    if total <= 0:
        return Decimal("0")
    return (Decimal(part) / Decimal(total)) * Decimal("100")


def analyze_holders(
    balances: Iterable[tuple[str, int]],
    total_supply: int,
    dev_addresses: Optional[Iterable[str]] = None,
    excluded_addresses: Optional[dict[str, str]] = None,
) -> HolderAnalysis:
    """Calcula Top 10/20 e participação do criador.

    ``balances``: pares (endereço, saldo em unidades mínimas).
    ``dev_addresses``: endereços identificados como criador/controle
    (evidência externa: RugCheck/Solana RPC/GoPlus).
    ``excluded_addresses``: {endereço: motivo} — só entram aqui
    endereços classificados (pool, burn, carteira técnica); a
    exclusão fica documentada em ``evidence`` e no Top 10 ajustado.
    """
    dev_set = {a.lower() for a in (dev_addresses or [])}
    excluded = {a.lower(): reason for a, reason in (excluded_addresses or {}).items()}

    holders: list[Holder] = []
    for address, balance in balances:
        if balance < 0:
            raise ValueError(f"saldo negativo para {address!r}")
        lowered = address.lower()
        if lowered in dev_set:
            label = "dev"
        elif lowered in excluded:
            label = excluded[lowered]
        elif lowered in BURN_ADDRESSES:
            label = "burn"
        else:
            label = "unknown"
        holders.append(
            Holder(
                address=address,
                balance_raw=balance,
                share_pct=_pct(balance, total_supply),
                label=label,
            )
        )
    holders.sort(key=lambda h: h.balance_raw, reverse=True)

    def _top(n: int, items: list[Holder]) -> Decimal:
        return sum((h.share_pct for h in items[:n]), Decimal("0"))

    top10 = _top(10, holders)
    top20 = _top(20, holders)

    # Top 10 ajustado: exclui apenas endereços classificados.
    classified = {"pool", "burn", "technical"}
    adjusted = [h for h in holders if h.label not in classified]
    top10_adj = _top(10, adjusted)

    dev_holders = [h for h in holders if h.label == "dev"]
    dev_pct = sum((h.share_pct for h in dev_holders), Decimal("0"))
    dev_address = dev_holders[0].address if dev_holders else None

    evidence: list[str] = []
    if excluded:
        evidence.append(
            f"{len(excluded)} endereco(s) classificado(s) e excluido(s) "
            f"do Top 10 ajustado: {sorted(excluded)}"
        )
    if dev_address:
        evidence.append(f"criador/dev identificado: {dev_address} ({dev_pct}%)")
    else:
        evidence.append("criador/dev nao identificado nos holders informados")

    return HolderAnalysis(
        total_supply=total_supply,
        holders=tuple(holders),
        top10_pct=top10,
        top20_pct=top20,
        top10_pct_excl_classified=top10_adj,
        dev_pct=dev_pct,
        dev_address=dev_address,
        evidence=tuple(evidence),
    )


def cluster_by_funder(
    holders: Iterable[Holder],
    funding_edges: dict[str, list[str]],
) -> tuple[dict[str, Any], ...]:
    """Agrupa holders por origem comum de financiamento.

    ``funding_edges``: {funder: [endereços financiados]} — evidência
    on-chain (ex.: primeira transferência de SOL/BNB vinda do mesmo
    endereço). Sem arestas, retorna () — vínculo nunca é presumido.
    """
    by_address = {h.address.lower(): h for h in holders}
    clusters: list[dict[str, Any]] = []
    for funder, funded in funding_edges.items():
        members = [a for a in funded if a.lower() in by_address]
        if len(members) < 2:
            continue
        share = sum(
            (by_address[a.lower()].share_pct for a in members), Decimal("0")
        )
        clusters.append(
            {
                "funder": funder,
                "members": members,
                "member_count": len(members),
                "combined_share_pct": str(share),
                "evidence": "origem comum de financiamento",
            }
        )
    clusters.sort(
        key=lambda c: Decimal(c["combined_share_pct"]), reverse=True
    )
    return tuple(clusters)
