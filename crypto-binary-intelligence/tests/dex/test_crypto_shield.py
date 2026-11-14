"""Testes do Crypto Shield (Fase 6 — SEC-001…SEC-007).

Somente mocks/fakes, sem rede. Cobre: Top 10/20, regras de bloqueio
(dev >5%, Top 10 >30%), simulação de slippage, estados
APROVADO/REVISÃO/BLOQUEADO e o caso sem dados (REVISÃO, nunca aprovar
no escuro).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .helpers import adapter_path, load_module, shield_path

amm = load_module("amm", adapter_path("amm.py"))
holders_mod = load_module("shield_holders_test", shield_path("shield_holders.py"))
liquidity_mod = load_module("shield_liquidity_test", shield_path("shield_liquidity.py"))
authorities_mod = load_module("shield_authorities_test", shield_path("shield_authorities.py"))
shield_mod = load_module("crypto_shield_test", shield_path("crypto_shield.py"))

analyze_holders = holders_mod.analyze_holders
cluster_by_funder = holders_mod.cluster_by_funder
analyze_liquidity = liquidity_mod.analyze_liquidity
simulate_sell = liquidity_mod.simulate_sell
analyze_authorities = authorities_mod.analyze_authorities
assess_token = shield_mod.assess_token
ShieldAssessor = shield_mod.ShieldAssessor

TOTAL = 1_000_000_000
DEV = "DEV1111111111111111111111111111111111111111"
POOL = "POOL111111111111111111111111111111111111111"
BURN = "0x000000000000000000000000000000000000dEaD"


def _balances(top10_each=80_000_000, rest_each=10_000_000, n_rest=10):
    """Top 10 com 8% cada (80%) + 10 holders com 1% cada (10%)."""
    balances = [(f"HOLDER{i:02d}", top10_each) for i in range(10)]
    balances += [(f"REST{i:02d}", rest_each) for i in range(n_rest)]
    return balances


def _saudavel():
    holders = analyze_holders(
        [(f"H{i:02d}", 10_000_000) for i in range(10)]  # 1% cada
        + [(f"R{i:02d}", 1_000_000) for i in range(10)],
        TOTAL,
    )
    liquidity = analyze_liquidity(
        total_liquidity_usd=Decimal("500000"),
        market_cap_usd=Decimal("5000000"),
        lp_locked_pct=Decimal("90"),
        lp_burned_pct=Decimal("0"),
    )
    authorities = analyze_authorities(source="test")
    sell_sim = simulate_sell(Decimal("1000000"), Decimal("2000000"))
    return holders, liquidity, authorities, sell_sim


# -- holders ------------------------------------------------------------

def test_top10_top20_calculo():
    analysis = analyze_holders(_balances(), TOTAL)
    assert analysis.top10_pct == Decimal("80")
    assert analysis.top20_pct == Decimal("90")
    assert len(analysis.holders) == 20
    assert analysis.holders[0].balance_raw == 80_000_000


def test_top10_ajustado_exclui_burn_classificado():
    balances = [(BURN, 100_000_000)] + _balances()  # burn com 10%
    analysis = analyze_holders(
        balances, TOTAL, excluded_addresses={BURN: "burn"}
    )
    assert analysis.top10_pct == Decimal("82")  # burn 10% + 9x8%
    assert analysis.top10_pct_excl_classified == Decimal("80")
    assert any("classificado" in e for e in analysis.evidence)


def test_dev_share_identificado():
    balances = [(DEV, 40_000_000)] + _balances()
    analysis = analyze_holders(balances, TOTAL, dev_addresses=[DEV])
    assert analysis.dev_pct == Decimal("4")
    assert analysis.dev_address == DEV


def test_cluster_por_funder_soma_participacao():
    analysis = analyze_holders(_balances(), TOTAL)
    clusters = cluster_by_funder(
        analysis.holders,
        {"FUNDER1": ["HOLDER00", "HOLDER01", "HOLDER02"]},
    )
    assert len(clusters) == 1
    assert clusters[0]["combined_share_pct"] == "24.00"
    assert clusters[0]["member_count"] == 3


def test_cluster_sem_dados_nao_presume_vinculo():
    analysis = analyze_holders(_balances(), TOTAL)
    assert cluster_by_funder(analysis.holders, {}) == ()


def test_saldo_negativo_rejeitado():
    with pytest.raises(ValueError):
        analyze_holders([("X", -1)], TOTAL)


# -- simulação de venda ---------------------------------------------------

def test_amm_out_valor_conhecido():
    # x=1M, y=2M, vende 10k com taxa 0,25%: out = 2M*9975/(1M+9975)
    out = amm.constant_product_out(
        Decimal("10000"), Decimal("1000000"), Decimal("2000000"), 25
    )
    esperado = (Decimal("2000000") * Decimal("9975")) / (
        Decimal("1000000") + Decimal("9975")
    )
    assert out == esperado


def test_price_impact_cresce_com_tamanho():
    small = amm.price_impact_pct(
        Decimal("1000"), Decimal("1000000"), Decimal("2000000")
    )
    big = amm.price_impact_pct(
        Decimal("250000"), Decimal("1000000"), Decimal("2000000")
    )
    assert small < Decimal("1")
    assert big > Decimal("15")


def test_simulate_sell_cenarios_e_maximo():
    sim = simulate_sell(Decimal("1000000"), Decimal("2000000"))
    assert len(sim.scenarios) == 4
    assert sim.scenarios[0]["sell_fraction_of_pool"] == "0.01"
    impact_1pct = Decimal(sim.scenarios[0]["price_impact_pct"])
    assert impact_1pct < Decimal("5")
    assert sim.max_sellable_pct_of_pool == Decimal("0.10")


def test_simulate_sell_sem_reservas():
    sim = simulate_sell(Decimal("0"), Decimal("0"))
    assert sim.scenarios == ()
    assert sim.evidence


# -- vereditos ------------------------------------------------------------

def test_token_saudavel_aprovado():
    holders, liquidity, authorities, sell_sim = _saudavel()
    result = assess_token(
        "TOKEN", "solana",
        holders=holders, liquidity=liquidity,
        authorities=authorities, sell_simulation=sell_sim,
        sources=["test"],
    )
    assert result.status == "APROVADO"
    assert result.risk_score < 40
    assert result.auto_approval_blocked is False


def test_dev_acima_de_5_bloqueia():
    holders = analyze_holders(
        [(DEV, 60_000_000)] + _balances(), TOTAL, dev_addresses=[DEV]
    )
    liquidity = analyze_liquidity(
        total_liquidity_usd=Decimal("500000"),
        market_cap_usd=Decimal("5000000"),
        lp_locked_pct=Decimal("90"),
    )
    result = assess_token(
        "TOKEN", "solana", holders=holders, liquidity=liquidity,
        authorities=analyze_authorities(source="test"),
    )
    assert result.status == "BLOQUEADO"
    assert result.auto_approval_blocked is True
    assert any(">5%" in r for r in result.reasons)


def test_top10_acima_de_30_revisao():
    # Top 10 = 35% -> REVISÃO (piso da regra: >30% é risco elevado).
    holders = analyze_holders(
        [(f"H{i:02d}", 35_000_000) for i in range(10)]
        + [(f"R{i:02d}", 1_000_000) for i in range(10)],
        TOTAL,
    )
    assert holders.top10_pct == Decimal("35")
    result = assess_token(
        "TOKEN", "solana", holders=holders,
        liquidity=analyze_liquidity(
            total_liquidity_usd=Decimal("500000"),
            market_cap_usd=Decimal("5000000"),
            lp_locked_pct=Decimal("90"),
        ),
        authorities=analyze_authorities(source="test"),
    )
    assert result.status == "REVISÃO"
    assert result.auto_approval_blocked is True


def test_top10_acima_de_50_bloqueia():
    holders = analyze_holders(_balances(), TOTAL)  # Top 10 = 80%
    result = assess_token("TOKEN", "solana", holders=holders)
    assert result.status == "BLOQUEADO"


def test_dev_entre_2_e_3_atencao_elevada():
    holders = analyze_holders(
        [(DEV, 25_000_000)]
        + [(f"H{i:02d}", 10_000_000) for i in range(10)]
        + [(f"R{i:02d}", 1_000_000) for i in range(10)],
        TOTAL,
        dev_addresses=[DEV],
    )
    assert holders.dev_pct == Decimal("2.5")
    result = assess_token(
        "TOKEN", "solana", holders=holders,
        liquidity=analyze_liquidity(
            total_liquidity_usd=Decimal("500000"),
            market_cap_usd=Decimal("5000000"),
            lp_locked_pct=Decimal("90"),
        ),
        authorities=analyze_authorities(source="test"),
    )
    assert result.status == "REVISÃO" or result.status == "APROVADO"
    assert any("atencao elevada" in r for r in result.reasons)


def test_honeypot_bloqueia_e_prevalece():
    holders, liquidity, _, sell_sim = _saudavel()
    authorities = analyze_authorities(source="goplus", is_honeypot=True)
    result = assess_token(
        "TOKEN", "bsc",
        holders=holders, liquidity=liquidity,
        authorities=authorities, sell_simulation=sell_sim,
    )
    assert result.status == "BLOQUEADO"
    assert any("honeypot" in r.lower() for r in result.reasons)


def test_sem_dados_revisao_nunca_aprova_no_escuro():
    result = assess_token("TOKEN", "solana")
    assert result.status == "REVISÃO"
    assert result.auto_approval_blocked is True
    assert any("sem dados" in r.lower() for r in result.reasons)


def test_liquidez_muito_baixa_sobe_score():
    holders, _, authorities, sell_sim = _saudavel()
    liquidity = analyze_liquidity(
        total_liquidity_usd=Decimal("1000"),
        market_cap_usd=Decimal("5000000"),
        lp_locked_pct=Decimal("0"),
        lp_burned_pct=Decimal("0"),
    )
    result = assess_token(
        "TOKEN", "solana",
        holders=holders, liquidity=liquidity,
        authorities=authorities, sell_simulation=sell_sim,
    )
    assert result.risk_score >= 40
    assert result.status in ("REVISÃO", "BLOQUEADO")


def test_rugcheck_rugged_bloqueia():
    holders, liquidity, authorities, sell_sim = _saudavel()
    result = assess_token(
        "TOKEN", "solana",
        holders=holders, liquidity=liquidity,
        authorities=authorities, sell_simulation=sell_sim,
        rugcheck_report={"rugged": True, "risks": []},
    )
    assert result.status == "BLOQUEADO"


def test_to_dict_serializavel():
    holders, liquidity, authorities, sell_sim = _saudavel()
    result = assess_token(
        "TOKEN", "solana",
        holders=holders, liquidity=liquidity,
        authorities=authorities, sell_simulation=sell_sim,
    )
    data = result.to_dict()
    assert data["status"] == "APROVADO"
    assert data["holders"]["top10_pct"] == "10.00"
    assert data["liquidity"]["total_liquidity_usd"] == "500000"


# -- assessor (coleta com mocks) ------------------------------------------

class FakeDexscreener:
    def get_token_pairs(self, chain, token):
        return [{
            "chain": chain, "dex": "raydium", "pair_address": "P1",
            "liquidity_usd": "400000", "market_cap_usd": "4000000",
        }]


class FakeSolanaRpc:
    def get_token_supply(self, mint):
        return {"amount": "1000000000", "decimals": 6}

    def get_token_largest_accounts(self, mint):
        return [
            {"address": "AAA", "amount": "10000000"},
            {"address": "BBB", "amount": "10000000"},
        ]

    def find_mint_creator(self, mint):
        return {"creator": "CREATOR1"}

    def get_mint_info(self, mint):
        return {"mint_authority": None, "freeze_authority": None,
                "supply": 1_000_000_000, "decimals": 6}


class FakeRugcheck:
    def report(self, mint):
        return {"ok": True, "data": {
            "mint": mint, "mintAuthority": None, "freezeAuthority": None,
            "creator": "CREATOR1", "risks": [],
            "topHolders": [{"address": "AAA", "pct": 1.0}],
            "totalMarketLiquidity": 400000,
        }}


def test_assessor_solana_mint_com_mocks():
    assessor = ShieldAssessor(
        dexscreener=FakeDexscreener(),
        solana_rpc=FakeSolanaRpc(),
        rugcheck=FakeRugcheck(),
    )
    result = assessor.assess_solana_mint("MINTTEST")
    assert result.chain == "solana"
    assert result.status in ("APROVADO", "REVISÃO", "BLOQUEADO")
    assert "solana-rpc" in result.sources
    assert "rugcheck" in result.sources
    assert result.holders is not None
    assert result.holders.top10_pct == Decimal("2")


def test_assessor_solana_sem_fontes_revisao():
    assessor = ShieldAssessor()
    result = assessor.assess_solana_mint("MINTTEST")
    assert result.status == "REVISÃO"
    assert result.holders is None
