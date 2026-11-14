"""Verificação de authorities e funções do contrato (Fase 6 — SEC-005).

Normaliza os sinais vindos de GoPlus, RugCheck e leitura on-chain
(Solana: mint/freeze authority via RPC; EVM: owner/mint via eth_call)
em uma estrutura única. Honeypot aqui é **simulação de compra e
venda** (GoPlus/RugCheck) — nunca transação real.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

try:
    from shield_models import AuthorityAnalysis
except ImportError:  # diretório fora do sys.path
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent))
    from shield_models import AuthorityAnalysis


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _to_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes"):
            return True
        if lowered in ("0", "false", "no"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def analyze_authorities(
    *,
    source: str,
    mint_authority: Optional[str] = None,
    freeze_authority: Optional[str] = None,
    owner: Optional[str] = None,
    is_honeypot: Optional[bool] = None,
    buy_tax_pct: Optional[Any] = None,
    sell_tax_pct: Optional[Any] = None,
    can_change_tax: Optional[Any] = None,
    trading_restricted: Optional[Any] = None,
    is_proxy: Optional[Any] = None,
) -> AuthorityAnalysis:
    """Monta a análise a partir de sinais já coletados (sem rede)."""
    evidence: list[str] = []
    if is_honeypot is True:
        evidence.append("honeypot detectado pela fonte (simulacao)")
    if mint_authority:
        evidence.append(f"mint authority ativa: {mint_authority}")
    if freeze_authority:
        evidence.append(f"freeze authority ativa: {freeze_authority}")
    if owner:
        evidence.append(f"owner do contrato: {owner}")
    buy_tax = _to_decimal(buy_tax_pct)
    sell_tax = _to_decimal(sell_tax_pct)
    if buy_tax is not None and buy_tax > Decimal("10"):
        evidence.append(f"taxa de compra alta: {buy_tax}%")
    if sell_tax is not None and sell_tax > Decimal("10"):
        evidence.append(f"taxa de venda alta: {sell_tax}%")
    if _to_bool(trading_restricted):
        evidence.append("restricao de compra/venda detectada")
    if _to_bool(is_proxy):
        evidence.append("contrato proxy (logica pode mudar)")

    return AuthorityAnalysis(
        mint_authority=mint_authority,
        freeze_authority=freeze_authority,
        owner=owner,
        is_honeypot=_to_bool(is_honeypot),
        buy_tax_pct=buy_tax,
        sell_tax_pct=sell_tax,
        can_change_tax=_to_bool(can_change_tax),
        trading_restricted=_to_bool(trading_restricted),
        is_proxy=_to_bool(is_proxy),
        source=source,
        evidence=tuple(evidence),
    )


def from_goplus_result(result: dict[str, Any]) -> AuthorityAnalysis:
    """Normaliza o ``result`` do endpoint token_security do GoPlus.

    Campos GoPlus (strings "0"/"1" ou valores): ``is_honeypot``,
    ``is_mintable``, ``owner_address``, ``buy_tax``, ``sell_tax``,
    ``cannot_buy``, ``cannot_sell_all``, ``is_proxy``, ``hidden_owner``.
    """
    mint_authority = result.get("owner_address") if result.get("is_mintable") == "1" else None
    honeypot = result.get("is_honeypot") == "1"
    restricted = (
        result.get("cannot_buy") == "1"
        or result.get("cannot_sell_all") == "1"
    )
    return analyze_authorities(
        source="goplus",
        mint_authority=mint_authority,
        owner=result.get("owner_address"),
        is_honeypot=honeypot,
        buy_tax_pct=result.get("buy_tax"),
        sell_tax_pct=result.get("sell_tax"),
        can_change_tax=None,
        trading_restricted=restricted,
        is_proxy=result.get("is_proxy") == "1",
    )


def from_rugcheck_report(report: dict[str, Any]) -> AuthorityAnalysis:
    """Normaliza o report do RugCheck (Solana).

    Campos: ``mintAuthority`` (None = revogada), ``freezeAuthority``,
    ``creator``, ``risks`` (lista com ``name``/``level``). O report não
    traz um booleano de honeypot — não inventar: ``is_honeypot`` fica
    None e o risco vem da lista de ``risks`` no ShieldResult.
    """
    return analyze_authorities(
        source="rugcheck",
        mint_authority=report.get("mintAuthority"),
        freeze_authority=report.get("freezeAuthority"),
        owner=report.get("creator"),
        is_honeypot=None,
        buy_tax_pct=None,
        sell_tax_pct=None,
        can_change_tax=None,
        trading_restricted=None,
        is_proxy=None,
    )
