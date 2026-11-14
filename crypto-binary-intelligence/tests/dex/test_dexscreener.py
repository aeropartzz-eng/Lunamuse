"""Testes do DEX Screener (Fase 6 — DEX-001). Somente mocks, sem rede."""

from __future__ import annotations

import pytest

from .helpers import adapter_path, load_module
from .fakes import FakeSession

dex_http = load_module("dex_http", adapter_path("dex_http.py"))
dexscreener_mod = load_module(
    "dexscreener_adapter_test", adapter_path("dexscreener", "adapter.py")
)

DexHttpClient = dex_http.DexHttpClient
DexHttpError = dex_http.DexHttpError
DexscreenerAdapter = dexscreener_mod.DexscreenerAdapter

PAIR_RAW = {
    "chainId": "solana",
    "dexId": "raydium",
    "pairAddress": "PAIR123",
    "baseToken": {"address": "MINT_A", "name": "Bonk", "symbol": "BONK"},
    "quoteToken": {"address": "So11111111111111111111111111111111111111112", "symbol": "SOL"},
    "priceNative": "0.00001",
    "priceUsd": "0.00002",
    "liquidity": {"usd": 1500000},
    "volume": {"h24": 500000},
    "txns": {"h24": {"buys": 1200, "sells": 800}},
    "fdv": 90000000,
    "marketCap": 85000000,
    "pairCreatedAt": 1760000000000,
    "url": "https://dexscreener.com/solana/PAIR123",
}


def _adapter_with(payload, status=200):
    session = FakeSession()
    session.route("GET", "https://api.dexscreener.com/latest/dex/search",
                  {"pairs": [PAIR_RAW]}, status=status)
    session.route("GET", "https://api.dexscreener.com/token-pairs/v1/solana/MINT_A",
                  {"pairs": [PAIR_RAW]}, status=status)
    session.route("GET", "https://api.dexscreener.com/latest/dex/pairs/solana/PAIR123",
                  {"pairs": [PAIR_RAW]}, status=status)
    client = DexHttpClient("https://api.dexscreener.com", session=session, sleep=lambda s: None)
    return DexscreenerAdapter(client=client), session


def test_search_normaliza_par():
    adapter, _ = _adapter_with(None)
    pairs = adapter.search_pairs("BONK")
    assert len(pairs) == 1
    pair = pairs[0]
    assert pair["chain"] == "solana"
    assert pair["dex"] == "raydium"
    assert pair["pair_address"] == "PAIR123"
    assert pair["base_token"]["symbol"] == "BONK"
    assert pair["quote_token"]["symbol"] == "SOL"
    assert pair["price_usd"] == "0.00002"
    assert pair["liquidity_usd"] == "1500000"
    assert pair["volume_24h_usd"] == "500000"
    assert pair["txns_24h"] == 2000
    assert pair["market_cap_usd"] == "85000000"
    assert pair["pair_created_at_ms"] == 1760000000000


def test_search_query_vazia_rejeitada():
    adapter, _ = _adapter_with(None)
    with pytest.raises(ValueError):
        adapter.search_pairs("   ")


def test_get_token_pairs():
    adapter, _ = _adapter_with(None)
    pairs = adapter.get_token_pairs("solana", "MINT_A")
    assert len(pairs) == 1
    assert pairs[0]["pair_address"] == "PAIR123"


def test_get_pool_por_chain_e_endereco():
    adapter, _ = _adapter_with(None)
    pair = adapter.get_pool("PAIR123", chain_id="solana")
    assert pair["dex"] == "raydium"


def test_get_pool_formato_chain_address():
    adapter, _ = _adapter_with(None)
    pair = adapter.get_pool("solana:PAIR123")
    assert pair["pair_address"] == "PAIR123"


def test_get_pool_sem_chain_rejeita():
    adapter, _ = _adapter_with(None)
    with pytest.raises(ValueError):
        adapter.get_pool("PAIR123")


def test_get_pool_inexistente_levanta_404():
    session = FakeSession()
    session.route("GET", "https://api.dexscreener.com/latest/dex/pairs/solana/NOPE",
                  {"pairs": []})
    client = DexHttpClient("https://api.dexscreener.com", session=session, sleep=lambda s: None)
    adapter = DexscreenerAdapter(client=client)
    with pytest.raises(DexHttpError) as excinfo:
        adapter.get_pool("NOPE", chain_id="solana")
    assert excinfo.value.status == 404


def test_erro_http_vira_dex_http_error():
    adapter, _ = _adapter_with(None, status=500)
    with pytest.raises(DexHttpError):
        adapter.search_pairs("BONK")


def test_health_sem_chamada_e_unknown_e_depois_ok():
    adapter, _ = _adapter_with(None)
    assert adapter.health()["status"] == "unknown"
    adapter.search_pairs("BONK")
    assert adapter.health()["status"] == "ok"
    assert adapter.health()["connected"] is True


def test_search_sem_pares_retorna_lista_vazia():
    session = FakeSession()
    session.route("GET", "https://api.dexscreener.com/latest/dex/search", {"pairs": []})
    client = DexHttpClient("https://api.dexscreener.com", session=session, sleep=lambda s: None)
    adapter = DexscreenerAdapter(client=client)
    assert adapter.search_pairs("ZZZNOPE") == []
