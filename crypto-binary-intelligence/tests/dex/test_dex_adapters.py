"""Testes dos adapters Raydium, Jupiter, PancakeSwap e Uniswap (Fase 6).

Somente mocks/fakes, sem rede. Cobre normalização, cotação de rota,
leitura de par V2/V3 e os caminhos de "sem endpoint público sem chave".
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .helpers import adapter_path, load_module
from .fakes import FakeSession

dex_http = load_module("dex_http", adapter_path("dex_http.py"))
raydium_mod = load_module("raydium_adapter_test", adapter_path("raydium", "adapter.py"))
jupiter_mod = load_module("jupiter_adapter_test", adapter_path("jupiter", "adapter.py"))
pancake_mod = load_module("pancakeswap_adapter_test", adapter_path("pancakeswap", "adapter.py"))
uniswap_mod = load_module("uniswap_adapter_test", adapter_path("uniswap", "adapter.py"))
evm = load_module("evm_rpc", adapter_path("rpc", "evm_rpc.py"))

DexHttpClient = dex_http.DexHttpClient
RaydiumAdapter = raydium_mod.RaydiumAdapter
JupiterAdapter = jupiter_mod.JupiterAdapter
PancakeswapAdapter = pancake_mod.PancakeswapAdapter
UniswapAdapter = uniswap_mod.UniswapAdapter

MINT_A = "MINTAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
MINT_B = "So11111111111111111111111111111111111111112"

RAYDIUM_POOL = {
    "id": "POOL123",
    "poolType": "Standard",
    "mintA": {"address": MINT_A, "symbol": "BONK", "decimals": 5},
    "mintB": {"address": MINT_B, "symbol": "WSOL", "decimals": 9},
    "price": 0.00002,
    "tvl": 1500000,
    "day": {"volume": 500000, "apr": 120.5},
    "feeRate": 2500,
    "lpMint": {"address": "LP123"},
}


def _session_with_routes():
    session = FakeSession()
    session.route("GET", "https://api-v3.raydium.io/pools/info/mint",
                  {"id": "x", "success": True, "data": {"data": [RAYDIUM_POOL]}})
    session.route("GET", "https://api-v3.raydium.io/pools/info/ids",
                  {"id": "x", "success": True, "data": [RAYDIUM_POOL]})
    session.route("GET", "https://api-v3.raydium.io/mint/price",
                  {"id": "x", "success": True, "data": {MINT_A: {"price": 0.00002}}})
    session.route("GET", "https://lite-api.jup.ag/price/v3",
                  {MINT_B: {"usdPrice": 180.5, "decimals": 9}})
    session.route("GET", "https://lite-api.jup.ag/swap/v1/quote",
                  {"inputMint": MINT_A, "outputMint": MINT_B,
                   "inAmount": "1000000", "outAmount": "18000",
                   "priceImpactPct": "0.12", "routePlan": []})
    return session


def _client_for(base_url):
    return DexHttpClient(base_url, session=_session_with_routes(), sleep=lambda s: None)


def test_raydium_pools_by_mint_normalizado():
    client = _client_for("https://api-v3.raydium.io")
    adapter = RaydiumAdapter(client=client)
    pools = adapter.get_pools_by_mint(MINT_A)
    assert len(pools) == 1
    pool = pools[0]
    assert pool["chain"] == "solana"
    assert pool["dex"] == "raydium"
    assert pool["pair_address"] == "POOL123"
    assert pool["base_token"]["symbol"] == "BONK"
    assert pool["quote_token"]["symbol"] == "WSOL"
    assert pool["tvl_usd"] == 1500000
    assert pool["volume_24h_usd"] == 500000


def test_raydium_get_pool_e_preco():
    client = _client_for("https://api-v3.raydium.io")
    adapter = RaydiumAdapter(client=client)
    pool = adapter.get_pool("POOL123")
    assert pool["pair_address"] == "POOL123"
    prices = adapter.get_mint_price([MINT_A])
    assert prices[MINT_A]["price"] == 0.00002


def test_raydium_search_sem_endpoint():
    adapter = RaydiumAdapter(client=_client_for("https://api-v3.raydium.io"))
    with pytest.raises(NotImplementedError, match="Dexscreener"):
        adapter.search_pairs("BONK")


def test_jupiter_price_e_quote():
    client = _client_for("https://lite-api.jup.ag")
    adapter = JupiterAdapter(client=client)
    prices = adapter.get_price([MINT_B])
    assert prices[MINT_B]["price"] == 180.5
    assert prices[MINT_B]["usdPrice"] == 180.5
    quote = adapter.get_quote(MINT_A, MINT_B, 1_000_000)
    assert quote["amount_out"] == "18000"
    assert quote["price_impact_pct"] == "0.12"
    assert quote["input_mint"] == MINT_A


def test_jupiter_quote_amount_invalido():
    adapter = JupiterAdapter(client=_client_for("https://lite-api.jup.ag"))
    with pytest.raises(ValueError):
        adapter.get_quote(MINT_A, MINT_B, 0)


def test_jupiter_sem_pares_proprios():
    adapter = JupiterAdapter(client=_client_for("https://lite-api.jup.ag"))
    with pytest.raises(NotImplementedError):
        adapter.get_pool("QUALQUER")


class FakeEvmRpc:
    """RPC EVM fake p/ PancakeSwap e Uniswap (reservas fixas)."""

    def __init__(self, reserve0=1_000_000, reserve1=2_000_000):
        self.reserve0 = reserve0
        self.reserve1 = reserve1
        self.token0 = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        self.token1 = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        self.lp_supply = 1_414_213
        self.sqrt_price = 2**96  # preço 1:1
        self.tick = 0
        self.liquidity = 5_000_000

    def pair_tokens(self, pair):
        return self.token0, self.token1

    def pair_reserves(self, pair):
        return self.reserve0, self.reserve1, 1_700_000_000

    def token_total_supply(self, token):
        return self.lp_supply

    def token_balance_of(self, token, holder):
        return 700_000  # 700k de ~1.41M = ~49,5% queimado

    def factory_get_pair(self, factory, a, b):
        return "0x1111111111111111111111111111111111111111"

    def v3_slot0(self, pool):
        return self.sqrt_price, self.tick

    def v3_liquidity(self, pool):
        return self.liquidity

    def health(self):
        return {"chain_id": 56, "connected": True, "status": "ok", "block_number": 100}


def test_pancakeswap_get_pool_reservas():
    adapter = PancakeswapAdapter(rpc=FakeEvmRpc())
    pool = adapter.get_pool("0x1111111111111111111111111111111111111111")
    assert pool["dex"] == "pancakeswap"
    assert pool["chain"] == "bsc"
    assert pool["reserve0"] == "1000000"
    assert pool["reserve1"] == "2000000"
    assert pool["price_token0_in_token1"] == "2"


def test_pancakeswap_quote_sell_slippage():
    adapter = PancakeswapAdapter(rpc=FakeEvmRpc())
    quote = adapter.quote_sell(
        "0x1111111111111111111111111111111111111111",
        Decimal("10000"),
        sell_token_is_token0=True,
    )
    # out = 2M * 9975 / (1M + 9975) ≈ 19753; impacto ≈ 1,2%
    assert Decimal(quote["amount_out"]) > 0
    assert Decimal(quote["price_impact_pct"]) > 0
    assert Decimal(quote["price_impact_pct"]) < Decimal("5")


def test_pancakeswap_lp_burned_pct():
    adapter = PancakeswapAdapter(rpc=FakeEvmRpc())
    info = adapter.lp_burned_or_locked_info("0x1111111111111111111111111111111111111111")
    assert Decimal(info["lp_burned_pct"]) > Decimal("49")
    assert Decimal(info["lp_burned_pct"]) < Decimal("50")


def test_pancakeswap_search_sem_endpoint():
    adapter = PancakeswapAdapter(rpc=FakeEvmRpc())
    with pytest.raises(NotImplementedError, match="Dexscreener"):
        adapter.search_pairs("CAKE")


def test_uniswap_v2_pool_e_find_pair():
    adapter = UniswapAdapter(chain_id=1, rpc=FakeEvmRpc())
    pool = adapter.get_pool("0x1111111111111111111111111111111111111111", version=2)
    assert pool["dex"] == "uniswap"
    assert pool["pool_type"] == "v2"
    assert pool["price_token0_in_token1"] == "2"
    pair = adapter.find_v2_pair("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                                "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    assert pair == "0x1111111111111111111111111111111111111111"


def test_uniswap_v3_slot0_preco_1_para_1():
    adapter = UniswapAdapter(chain_id=1, rpc=FakeEvmRpc())
    pool = adapter.get_pool("0x2222222222222222222222222222222222222222", version=3)
    assert pool["pool_type"] == "v3"
    assert Decimal(pool["price_token1_per_token0_raw"]) == Decimal("1")
    assert pool["liquidity"] == "5000000"


def test_uniswap_search_sem_endpoint_e_chain_invalida():
    adapter = UniswapAdapter(chain_id=1, rpc=FakeEvmRpc())
    with pytest.raises(NotImplementedError, match="Dexscreener"):
        adapter.search_pairs("UNI")
    with pytest.raises(ValueError):
        UniswapAdapter(chain_id=999, rpc=FakeEvmRpc())
