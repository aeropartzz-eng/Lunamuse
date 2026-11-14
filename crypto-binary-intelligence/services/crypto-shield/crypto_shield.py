"""Crypto Shield — Antifraude (Fase 6 — SEC-001…SEC-007).

Orquestra Holder Intelligence, LP/liquidez, authorities e simulação
de venda em um veredito: APROVADO / REVISÃO / BLOQUEADO, com score
de risco (0–100), evidências e fontes.

REGRAS DO PROJETO (§7) — filtros internos conservadores, não garantias:
- Criador/carteira de controle com mais de 5% do suprimento: bloqueia
  aprovação automática (BLOQUEADO) e exige revisão manual.
- Dev acima de 2–3%: atenção elevada. Dev 3–5%: no mínimo REVISÃO.
- Top 10 acima de 30%: risco elevado (no mínimo REVISÃO);
  acima de 50%: BLOQUEADO.
- Sem dados suficientes: REVISÃO — nunca aprovar no escuro.
- **Risco crítico prevalece sobre qualquer score agregado.**

``assess_token`` é puro (recebe análises prontas — testável sem rede).
:class:`ShieldAssessor` coleta os dados dos clientes públicos com
degradação graciosa: fonte fora vira evidência, nunca exceção.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

try:
    from shield_authorities import from_goplus_result, from_rugcheck_report
    from shield_holders import analyze_holders
    from shield_liquidity import analyze_liquidity, simulate_sell
    from shield_models import (
        AuthorityAnalysis,
        HolderAnalysis,
        LiquidityAnalysis,
        SellSimulation,
        ShieldResult,
    )
except ImportError:  # diretório fora do sys.path
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent))
    from shield_authorities import from_goplus_result, from_rugcheck_report
    from shield_holders import analyze_holders
    from shield_liquidity import analyze_liquidity, simulate_sell
    from shield_models import (
        AuthorityAnalysis,
        HolderAnalysis,
        LiquidityAnalysis,
        SellSimulation,
        ShieldResult,
    )

# Limites da especificação (§7).
DEV_BLOCK_PCT = Decimal("5")
DEV_HIGH_ATTENTION_PCT = Decimal("2")
TOP10_HIGH_RISK_PCT = Decimal("30")
TOP10_BLOCK_PCT = Decimal("50")

SCORE_BLOCK = 70
SCORE_REVIEW = 40


def assess_token(
    token: str,
    chain: str,
    *,
    holders: Optional[HolderAnalysis] = None,
    liquidity: Optional[LiquidityAnalysis] = None,
    authorities: Optional[AuthorityAnalysis] = None,
    sell_simulation: Optional[SellSimulation] = None,
    rugcheck_report: Optional[dict[str, Any]] = None,
    goplus_result: Optional[dict[str, Any]] = None,
    sources: Optional[list[str]] = None,
) -> ShieldResult:
    """Veredito a partir das análises já coletadas (sem rede)."""
    reasons: list[str] = []
    evidence: list[str] = []
    score = 0
    critical: list[str] = []

    # -- holders -------------------------------------------------------
    if holders is not None:
        evidence.extend(holders.evidence)
        if holders.top10_pct > TOP10_BLOCK_PCT:
            critical.append(
                f"Top 10 com {holders.top10_pct}% do suprimento (>50%)"
            )
        elif holders.top10_pct > TOP10_HIGH_RISK_PCT:
            score += 25
            reasons.append(
                f"Top 10 com {holders.top10_pct}% (>30%: risco elevado)"
            )
        elif holders.top10_pct > Decimal("20"):
            score += 10
            reasons.append(f"Top 10 com {holders.top10_pct}% (>20%)")
        if holders.dev_pct > DEV_BLOCK_PCT:
            critical.append(
                f"criador/dev com {holders.dev_pct}% do suprimento (>5%)"
            )
        elif holders.dev_pct > Decimal("3"):
            score += 20
            reasons.append(
                f"criador/dev com {holders.dev_pct}% (3–5%: revisao)"
            )
        elif holders.dev_pct > DEV_HIGH_ATTENTION_PCT:
            score += 10
            reasons.append(
                f"criador/dev com {holders.dev_pct}% (2–3%: atencao elevada)"
            )
        for cluster in holders.clusters:
            share = Decimal(cluster["combined_share_pct"])
            if share > Decimal("10"):
                score += 15
                reasons.append(
                    f"cluster de carteiras relacionadas com {share}% "
                    f"(funder {cluster['funder']})"
                )
            elif share > Decimal("5"):
                score += 8
                reasons.append(
                    f"cluster de carteiras relacionadas com {share}%"
                )
    else:
        evidence.append("holders nao analisados (sem dados)")

    # -- liquidez ------------------------------------------------------
    if liquidity is not None:
        evidence.extend(liquidity.evidence)
        if liquidity.total_liquidity_usd is None:
            score += 10
            reasons.append("liquidez total desconhecida")
        elif liquidity.total_liquidity_usd < Decimal("5000"):
            score += 25
            reasons.append(
                f"liquidez muito baixa: US$ {liquidity.total_liquidity_usd}"
            )
        elif liquidity.total_liquidity_usd < Decimal("25000"):
            score += 15
            reasons.append(
                f"liquidez baixa: US$ {liquidity.total_liquidity_usd}"
            )
        if (
            liquidity.liquidity_to_mcap_pct is not None
            and liquidity.liquidity_to_mcap_pct < Decimal("1")
        ):
            score += 10
            reasons.append(
                "liquidez/market cap abaixo de 1% "
                f"({liquidity.liquidity_to_mcap_pct}%)"
            )
        locked = liquidity.lp_locked_pct
        burned = liquidity.lp_burned_pct
        if locked is None and burned is None:
            score += 10
            reasons.append("LP bloqueado/queimado desconhecido")
        else:
            secured = (locked or Decimal("0")) + (burned or Decimal("0"))
            if secured < Decimal("50"):
                score += 15
                reasons.append(f"LP pouco assegurado: {secured}%")
        if (
            liquidity.top_lp_holder_pct is not None
            and liquidity.top_lp_holder_pct > Decimal("50")
        ):
            score += 10
            reasons.append(
                "LP concentrado num unico provedor "
                f"({liquidity.top_lp_holder_pct}%)"
            )
    else:
        evidence.append("liquidez nao analisada (sem dados)")

    # -- authorities ---------------------------------------------------
    if authorities is not None:
        evidence.extend(authorities.evidence)
        if authorities.is_honeypot is True:
            critical.append("honeypot detectado (simulacao de compra/venda)")
        if authorities.mint_authority:
            score += 20
            reasons.append("mint authority ativa (novos tokens possiveis)")
        if authorities.freeze_authority:
            score += 15
            reasons.append("freeze authority ativa (contas podem ser travadas)")
        for tax, name in (
            (authorities.buy_tax_pct, "compra"),
            (authorities.sell_tax_pct, "venda"),
        ):
            if tax is not None and tax > Decimal("10"):
                score += 15
                reasons.append(f"taxa de {name} alta: {tax}%")
        if authorities.trading_restricted:
            score += 15
            reasons.append("restricao de compra/venda detectada")
        if authorities.is_proxy:
            score += 5
            reasons.append("contrato proxy")
    else:
        evidence.append("authorities nao analisadas (sem dados)")

    # -- simulação de venda --------------------------------------------
    if sell_simulation is not None:
        evidence.extend(sell_simulation.evidence)
        for scenario in sell_simulation.scenarios:
            fraction = Decimal(scenario["sell_fraction_of_pool"])
            impact = Decimal(scenario["price_impact_pct"])
            if fraction == Decimal("0.01"):
                if impact > Decimal("50"):
                    score += 20
                    reasons.append(
                        f"venda de 1% do pool com impacto de {impact}%"
                    )
                elif impact > Decimal("20"):
                    score += 10
                    reasons.append(
                        f"venda de 1% do pool com impacto de {impact}%"
                    )
    else:
        evidence.append("simulacao de venda nao executada")

    # -- sinais externos (GoPlus / RugCheck) ---------------------------
    if goplus_result:
        if str(goplus_result.get("is_honeypot")) == "1":
            critical.append("honeypot segundo GoPlus")
        if str(goplus_result.get("is_mintable")) == "1":
            reasons.append("GoPlus: token com mint habilitado")
    if rugcheck_report:
        if rugcheck_report.get("rugged") is True:
            critical.append("rugged segundo RugCheck")
        risks = rugcheck_report.get("risks") or []
        danger = sum(
            1
            for r in risks
            if isinstance(r, dict) and str(r.get("level")) == "danger"
        )
        warn = sum(
            1
            for r in risks
            if isinstance(r, dict) and str(r.get("level")) == "warn"
        )
        if danger:
            score += min(30, 15 * danger)
            reasons.append(f"RugCheck: {danger} risco(s) nivel danger")
        if warn:
            score += min(10, 5 * warn)
            reasons.append(f"RugCheck: {warn} risco(s) nivel warn")

    # -- veredito --------------------------------------------------------
    score = max(0, min(100, score))
    has_any_data = any(
        x is not None
        for x in (holders, liquidity, authorities, sell_simulation)
    ) or bool(rugcheck_report or goplus_result)
    # Pisos da especificação (§7): Top 10 > 30% ou dev 3–5% nunca
    # passam como APROVADO, mesmo com score baixo.
    floor_review = bool(
        holders
        and (
            holders.top10_pct > TOP10_HIGH_RISK_PCT
            or holders.dev_pct > Decimal("3")
        )
    )

    if critical:
        status = "BLOQUEADO"
        reasons = critical + reasons
    elif not has_any_data:
        status = "REVISÃO"
        reasons.append("sem dados suficientes — nao aprovar no escuro")
    elif score >= SCORE_BLOCK:
        status = "BLOQUEADO"
        reasons.append(f"score de risco {score} >= {SCORE_BLOCK}")
    elif score >= SCORE_REVIEW or floor_review:
        status = "REVISÃO"
        if score >= SCORE_REVIEW:
            reasons.append(f"score de risco {score} >= {SCORE_REVIEW}")
    else:
        status = "APROVADO"

    return ShieldResult(
        token=token,
        chain=chain,
        status=status,
        risk_score=score,
        reasons=tuple(reasons),
        evidence=tuple(evidence),
        holders=holders,
        liquidity=liquidity,
        authorities=authorities,
        sell_simulation=sell_simulation,
        auto_approval_blocked=status != "APROVADO",
        sources=tuple(sources or []),
    )


def not_implemented(*args, **kwargs):
    """Placeholder legado do scaffold — removido na Fase 6.

    Mantido para compatibilidade de import; a API atual é
    :func:`assess_token` e :class:`ShieldAssessor`.
    """
    raise NotImplementedError(
        "Crypto Shield: usar assess_token / ShieldAssessor (Fase 6)."
    )


class ShieldAssessor:
    """Coleta dados das fontes públicas e avalia (degradação graciosa).

    Cada fonte é opcional: falha vira evidência e o veredito tende a
    REVISÃO. Nenhuma fonte aqui usa chave de API.
    """

    def __init__(
        self,
        dexscreener=None,
        solana_rpc=None,
        evm_rpc=None,
        goplus=None,
        rugcheck=None,
        bubblemaps=None,
    ) -> None:
        self.dexscreener = dexscreener
        self.solana_rpc = solana_rpc
        self.evm_rpc = evm_rpc
        self.goplus = goplus
        self.rugcheck = rugcheck
        self.bubblemaps = bubblemaps

    # -- Solana ---------------------------------------------------------
    def assess_solana_mint(self, mint: str) -> ShieldResult:
        """Avalia um mint Solana (holders via RPC, RugCheck, DEX Screener)."""
        sources: list[str] = []
        holders = liquidity = authorities = sell_sim = None
        rugcheck_report = goplus_result = None

        dev_addresses: list[str] = []
        if self.solana_rpc is not None:
            sources.append("solana-rpc")
            try:
                supply = self.solana_rpc.get_token_supply(mint)
                total = int(supply.get("amount") or 0)
                largest = self.solana_rpc.get_token_largest_accounts(mint)
                balances = [
                    (a.get("address", ""), int(a.get("amount") or 0))
                    for a in largest
                    if a.get("address")
                ]
                creator = self.solana_rpc.find_mint_creator(mint)
                if creator.get("creator"):
                    dev_addresses.append(creator["creator"])
                if total > 0 and balances:
                    holders = analyze_holders(
                        balances, total, dev_addresses=dev_addresses
                    )
            except Exception as exc:  # noqa: BLE001 - degradacao graciosa
                holders = None
                sources.append(f"solana-rpc falhou: {exc}")
            try:
                mint_info = self.solana_rpc.get_mint_info(mint)
                authorities = AuthorityAnalysis(
                    mint_authority=mint_info.get("mint_authority"),
                    freeze_authority=mint_info.get("freeze_authority"),
                    owner=dev_addresses[0] if dev_addresses else None,
                    source="solana-rpc",
                    evidence=(
                        ("mint authority ativa",)
                        if mint_info.get("mint_authority")
                        else ()
                    )
                    + (
                        ("freeze authority ativa",)
                        if mint_info.get("freeze_authority")
                        else ()
                    ),
                )
            except Exception:  # noqa: BLE001
                pass

        if self.rugcheck is not None:
            sources.append("rugcheck")
            report = self.rugcheck.report(mint)
            if report.get("ok"):
                rugcheck_report = report["data"]
                if authorities is None:
                    authorities = from_rugcheck_report(rugcheck_report)
                if holders is None:
                    holders = self._holders_from_rugcheck(
                        rugcheck_report, dev_addresses
                    )
                locked = self._lp_locked_from_rugcheck(rugcheck_report)
                liq_usd = rugcheck_report.get("totalMarketLiquidity")
                liquidity = analyze_liquidity(
                    total_liquidity_usd=(
                        Decimal(str(liq_usd)) if liq_usd is not None else None
                    ),
                    lp_locked_pct=locked,
                )

        if self.dexscreener is not None and liquidity is None:
            sources.append("dexscreener")
            try:
                pairs = self.dexscreener.get_token_pairs("solana", mint)
                if pairs:
                    best = max(
                        pairs,
                        key=lambda p: float(p.get("liquidity_usd") or 0),
                    )
                    liq = best.get("liquidity_usd")
                    mcap = best.get("market_cap_usd")
                    liquidity = analyze_liquidity(
                        total_liquidity_usd=(
                            Decimal(str(liq)) if liq else None
                        ),
                        market_cap_usd=(
                            Decimal(str(mcap)) if mcap else None
                        ),
                    )
            except Exception:  # noqa: BLE001
                pass

        return assess_token(
            mint,
            "solana",
            holders=holders,
            liquidity=liquidity,
            authorities=authorities,
            sell_simulation=sell_sim,
            rugcheck_report=rugcheck_report,
            goplus_result=goplus_result,
            sources=sources,
        )

    # -- EVM -------------------------------------------------------------
    def assess_evm_token(
        self,
        chain: str,
        address: str,
        pair_address: Optional[str] = None,
    ) -> ShieldResult:
        """Avalia um token EVM (GoPlus + DEX Screener + RPC do par).

        Top holders EVM **não** estão disponíveis via RPC público
        (exigem indexador com chave — BscScan/Etherscan — bloqueado);
        holders fica ausente e o veredito tende a REVISÃO.
        """
        sources: list[str] = []
        holders = liquidity = authorities = sell_sim = None
        goplus_result = None

        if self.goplus is not None:
            sources.append("goplus")
            result = self.goplus.token_security(chain, [address])
            if result.get("ok"):
                goplus_result = result["data"]
                authorities = from_goplus_result(goplus_result)

        if self.dexscreener is not None:
            sources.append("dexscreener")
            try:
                pairs = self.dexscreener.get_token_pairs(chain, address)
                if pairs:
                    best = max(
                        pairs,
                        key=lambda p: float(p.get("liquidity_usd") or 0),
                    )
                    liq = best.get("liquidity_usd")
                    mcap = best.get("market_cap_usd")
                    liquidity = analyze_liquidity(
                        total_liquidity_usd=(
                            Decimal(str(liq)) if liq else None
                        ),
                        market_cap_usd=(
                            Decimal(str(mcap)) if mcap else None
                        ),
                    )
            except Exception:  # noqa: BLE001
                pass

        if self.evm_rpc is not None and pair_address:
            sources.append("evm-rpc")
            try:
                reserve0, reserve1, _ = self.evm_rpc.pair_reserves(pair_address)
                token0, _token1 = self.evm_rpc.pair_tokens(pair_address)
                is_token0 = token0.lower() == address.lower()
                reserve_token, reserve_quote = (
                    (Decimal(reserve0), Decimal(reserve1))
                    if is_token0
                    else (Decimal(reserve1), Decimal(reserve0))
                )
                sell_sim = simulate_sell(reserve_token, reserve_quote)
            except Exception:  # noqa: BLE001
                pass

        return assess_token(
            address,
            chain,
            holders=holders,
            liquidity=liquidity,
            authorities=authorities,
            sell_simulation=sell_sim,
            goplus_result=goplus_result,
            sources=sources,
        )

    # -- internos --------------------------------------------------------
    @staticmethod
    def _holders_from_rugcheck(
        report: dict[str, Any], dev_addresses: list[str]
    ) -> Optional[HolderAnalysis]:
        top = report.get("topHolders") or []
        if not top:
            return None
        total = 0
        balances: list[tuple[str, int]] = []
        for entry in top:
            if not isinstance(entry, dict):
                continue
            address = entry.get("address") or ""
            pct = entry.get("pct")
            if pct is None:
                continue
            # RugCheck dá pct (0-100); converter p/ base 1e9 p/ cálculo.
            raw = int(Decimal(str(pct)) * Decimal(10_000_000))
            balances.append((address, raw))
            total += raw
        if not balances or total <= 0:
            return None
        devs = list(dev_addresses)
        creator = report.get("creator")
        if creator and creator not in devs:
            devs.append(creator)
        return analyze_holders(balances, total, dev_addresses=devs)

    @staticmethod
    def _lp_locked_from_rugcheck(
        report: dict[str, Any],
    ) -> Optional[Decimal]:
        """% de LP bloqueado — tenta as grafias conhecidas do report."""
        for key in (
            "lpLockedPct",
            "lp_locked",
            "lockedLpPct",
            "liquidityLockedPct",
        ):
            value = report.get(key)
            if value is not None:
                try:
                    return Decimal(str(value))
                except Exception:  # noqa: BLE001
                    continue
        lockers = report.get("lockers") or {}
        if isinstance(lockers, dict):
            total_pct = Decimal("0")
            found = False
            for entry in lockers.values():
                if isinstance(entry, dict) and entry.get("pct") is not None:
                    total_pct += Decimal(str(entry["pct"]))
                    found = True
            if found:
                return total_pct
        return None
