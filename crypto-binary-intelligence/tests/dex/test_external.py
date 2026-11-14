"""Testes das integrações externas do Shield (Fase 6 — SEC-006).

GoPlus, RugCheck e Bubblemaps (legada) — somente mocks, sem rede.
Cobre: parsing dos resultados, falha graciosa e o bloqueio da API
nova da Bubblemaps (exige chave).
"""

from __future__ import annotations

from .helpers import adapter_path, load_module, shield_path
from .fakes import FakeSession

dex_http = load_module("dex_http", adapter_path("dex_http.py"))
external = load_module("shield_external_test", shield_path("shield_external.py"))
authorities_mod = load_module(
    "shield_authorities_external", shield_path("shield_authorities.py")
)

DexHttpClient = dex_http.DexHttpClient
GoPlusClient = external.GoPlusClient
RugCheckClient = external.RugCheckClient
BubblemapsClient = external.BubblemapsClient
from_goplus_result = authorities_mod.from_goplus_result
from_rugcheck_report = authorities_mod.from_rugcheck_report

GOPLUS_RESULT = {
    "is_honeypot": "0",
    "is_mintable": "1",
    "owner_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "buy_tax": "0.05",
    "sell_tax": "0.05",
    "cannot_buy": "0",
    "cannot_sell_all": "0",
    "is_proxy": "0",
}

RUGCHECK_REPORT = {
    "mint": "MINTTEST",
    "tokenProgram": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "creator": "CREATOR1",
    "mintAuthority": None,
    "freezeAuthority": "FREEZE1",
    "risks": [
        {"name": "Freeze Authority enabled", "level": "danger"},
        {"name": "Low Liquidity", "level": "warn"},
    ],
    "topHolders": [{"address": "AAA", "pct": 12.5}],
    "totalMarketLiquidity": 250000,
}


def _goplus_client():
    session = FakeSession()
    session.route("GET", "https://api.gopluslabs.io/api/v1/token_security/56",
                  {"code": 1, "message": "OK",
                   "result": {"0xtoken": GOPLUS_RESULT}})
    return GoPlusClient(
        client=DexHttpClient("https://api.gopluslabs.io", session=session, sleep=lambda s: None)
    )


def _rugcheck_client():
    session = FakeSession()
    session.route("GET", "https://api.rugcheck.xyz/v1/tokens/MINTTEST/report",
                  RUGCHECK_REPORT)
    session.route("GET", "https://api.rugcheck.xyz/v1/tokens/MINTTEST/report/summary",
                  {"mint": "MINTTEST", "score": 100})
    return RugCheckClient(
        client=DexHttpClient("https://api.rugcheck.xyz", session=session, sleep=lambda s: None)
    )


def test_goplus_token_security_ok():
    client = _goplus_client()
    result = client.token_security("bsc", ["0xTOKEN"])
    assert result["ok"] is True
    assert result["data"]["is_mintable"] == "1"


def test_goplus_chain_nao_suportada():
    client = _goplus_client()
    result = client.token_security("chain-que-nao-existe", ["0xTOKEN"])
    assert result["ok"] is False
    assert result["blocked"] is False


def test_goplus_result_normalizado_p_authorities():
    analysis = from_goplus_result(GOPLUS_RESULT)
    assert analysis.mint_authority == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert analysis.is_honeypot is False
    assert analysis.owner == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert str(analysis.buy_tax_pct) == "0.05"


def test_goplus_honeypot_flag():
    honeypot = dict(GOPLUS_RESULT, is_honeypot="1")
    analysis = from_goplus_result(honeypot)
    assert analysis.is_honeypot is True


def test_rugcheck_report_ok():
    client = _rugcheck_client()
    result = client.report("MINTTEST")
    assert result["ok"] is True
    assert result["data"]["creator"] == "CREATOR1"
    summary = client.summary("MINTTEST")
    assert summary["ok"] is True


def test_rugcheck_report_normalizado():
    analysis = from_rugcheck_report(RUGCHECK_REPORT)
    assert analysis.mint_authority is None  # revogada
    assert analysis.freeze_authority == "FREEZE1"
    assert analysis.owner == "CREATOR1"
    assert analysis.is_honeypot is None  # report nao traz o flag


def test_rugcheck_falha_graciosa():
    session = FakeSession()
    session.route("GET", "https://api.rugcheck.xyz/v1/tokens/NOPE/report",
                  {"error": "not found"}, status=404)
    client = RugCheckClient(
        client=DexHttpClient("https://api.rugcheck.xyz", session=session, sleep=lambda s: None)
    )
    result = client.report("NOPE")
    assert result["ok"] is False
    assert "rugcheck" in result["reason"]


def test_bubblemaps_legada_mapa_computado():
    session = FakeSession()
    session.route("GET", "https://api-legacy.bubblemaps.io/map-metadata",
                  {"status": "OK", "dt": "2026-11-13"})
    client = BubblemapsClient(
        client=DexHttpClient("https://api-legacy.bubblemaps.io", session=session, sleep=lambda s: None)
    )
    result = client.map_metadata("sol", "MINTTEST")
    assert result["ok"] is True


def test_bubblemaps_legada_mapa_nao_computado():
    session = FakeSession()
    session.route("GET", "https://api-legacy.bubblemaps.io/map-metadata",
                  {"status": "KO", "message": "map not computed"})
    client = BubblemapsClient(
        client=DexHttpClient("https://api-legacy.bubblemaps.io", session=session, sleep=lambda s: None)
    )
    result = client.map_metadata("eth", "0xTOKEN")
    assert result["ok"] is False
    assert "nao computado" in result["reason"]


def test_bubblemaps_api_nova_bloqueada():
    status = BubblemapsClient.new_api_status()
    assert status["blocked"] is True
    assert "API key" in status["reason"]
