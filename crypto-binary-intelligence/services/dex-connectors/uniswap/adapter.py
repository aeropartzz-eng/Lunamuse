"""Conector Uniswap (Fase 6 — DEX-007, avaliação).

**Avaliação (2026-11-13): não há API REST pública do Uniswap sem
chave.** O subgrafo oficial migrou para o gateway da The Graph (exige
API key) e a API da Uniswap Labs (``api.uniswap.org``) também exige
chave — ambas BLOQUEADAS aguardando decisão/chave do Will.

O que é viável sem chave (implementado aqui):
- Leitura de pools V2/V3 **on-chain via RPC público** (``eth_call``):
  V2 ``getReserves``/``token0``/``token1``; V3 ``slot0``/``liquidity``.
- Descoberta de pares via DEX Screener (DEX-001), que indexa Uniswap.

Docs: https://docs.uniswap.org/
Factories (Ethereum): V2 0x5C69bEe701ef814a2B6a3EDD4B1652CB7cc5aA6f,
V3 0x1F98431c8aD98523631AE4a59f267346ea31F984.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

try:
    from amm import spot_price
    from dex_http import DexHttpError
    from evm_rpc import ZERO_ADDRESS, EvmRpcClient, EvmRpcError
except ImportError:  # diretórios fora do sys.path (ver tests/dex/conftest.py)
    import sys
    from pathlib import Path

    _base = Path(__file__).resolve().parents[1]
    sys.path.append(str(_base))
    sys.path.append(str(_base / "rpc"))
    from amm import spot_price
    from dex_http import DexHttpError
    from evm_rpc import ZERO_ADDRESS, EvmRpcClient, EvmRpcError

# chain_id -> (factory V2, factory V3)
FACTORIES: dict[int, tuple[str, str]] = {
    1: (  # Ethereum
        "0x5C69bEe701ef814a2B6a3EDD4B1652CB7cc5aA6f",
        "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    ),
    8453: (  # Base (mesmas factories, deployment canônico)
        "0x5C69bEe701ef814a2B6a3EDD4B1652CB7cc5aA6f",
        "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    ),
}

CHAIN_NAMES = {1: "ethereum", 8453: "base"}

# Status das fontes REST avaliadas (SEC-006/DEX-007).
BLOCKED_SOURCES = {
    "thegraph_gateway": (
        "Subgrafo Uniswap via gateway The Graph exige API key — "
        "bloqueado aguardando chave do Will."
    ),
    "uniswap_labs_api": (
        "API Uniswap Labs (api.uniswap.org) exige chave — "
        "bloqueado aguardando chave do Will."
    ),
}


class UniswapAdapter:
    """Implementa o contrato DexAdapter (ver ../base.py)."""

    source_id = "uniswap"
    name = "Uniswap"

    def __init__(
        self,
        chain_id: int = 1,
        rpc: Optional[EvmRpcClient] = None,
    ) -> None:
        if chain_id not in FACTORIES:
            raise ValueError(f"Uniswap: chain {chain_id} sem factory mapeada")
        self.chain_id = chain_id
        self.chain = CHAIN_NAMES[chain_id]
        self._rpc = rpc or EvmRpcClient(chain_id=chain_id)

    # -- contrato DexAdapter ------------------------------------------
    def search_pairs(self, query: str) -> list[dict[str, Any]]:
        """Sem busca REST sem chave: usar DEX Screener (DEX-001)."""
        raise NotImplementedError(
            "Uniswap: sem endpoint publico de busca sem chave "
            "(The Graph/Uniswap Labs exigem API key); usar "
            "DexscreenerAdapter.search_pairs p/ descoberta."
        )

    def get_pool(
        self, pool_address: str, version: int = 2
    ) -> dict[str, Any]:
        """Pool V2 (reservas) ou V3 (slot0 + liquidez), via RPC público."""
        if version not in (2, 3):
            raise ValueError("version deve ser 2 ou 3")
        try:
            if version == 2:
                return self._get_v2_pool(pool_address)
            return self._get_v3_pool(pool_address)
        except EvmRpcError as exc:
            raise DexHttpError(f"uniswap get_pool falhou: {exc}") from exc

    def health(self) -> dict[str, Any]:
        """Estado do RPC subjacente (uma chamada real)."""
        status = self._rpc.health()
        return {"source": self.source_id, "chain": self.chain, **status}

    # -- próprios -------------------------------------------------------
    def find_v2_pair(self, token_a: str, token_b: str) -> Optional[str]:
        """Endereço do par V2 na factory, ou None se não existir."""
        factory = FACTORIES[self.chain_id][0]
        try:
            pair = self._rpc.factory_get_pair(factory, token_a, token_b)
        except EvmRpcError:
            return None
        if pair.lower() == ZERO_ADDRESS:
            return None
        return pair

    # -- internos ------------------------------------------------------
    def _get_v2_pool(self, pool_address: str) -> dict[str, Any]:
        token0, token1 = self._rpc.pair_tokens(pool_address)
        reserve0, reserve1, _ts = self._rpc.pair_reserves(pool_address)
        lp_supply = self._rpc.token_total_supply(pool_address)
        return {
            "chain": self.chain,
            "dex": "uniswap",
            "pair_address": pool_address,
            "pool_type": "v2",
            "base_token": {"symbol": "", "address": token0},
            "quote_token": {"symbol": "", "address": token1},
            "reserve0": str(reserve0),
            "reserve1": str(reserve1),
            "lp_total_supply": str(lp_supply),
            "price_token0_in_token1": str(
                spot_price(Decimal(reserve0), Decimal(reserve1))
            ),
            "price_token1_in_token0": str(
                spot_price(Decimal(reserve1), Decimal(reserve0))
            ),
        }

    def _get_v3_pool(self, pool_address: str) -> dict[str, Any]:
        sqrt_price_x96, tick = self._rpc.v3_slot0(pool_address)
        liquidity = self._rpc.v3_liquidity(pool_address)
        # Preço token1/token0 = (sqrtPriceX96 / 2^96)^2 (sem ajuste de
        # decimals; a normalização por decimals é feita pelo chamador
        # quando os decimals dos tokens são conhecidos).
        price = (
            (Decimal(sqrt_price_x96) / Decimal(2**96)) ** 2
            if sqrt_price_x96 > 0
            else Decimal("0")
        )
        return {
            "chain": self.chain,
            "dex": "uniswap",
            "pair_address": pool_address,
            "pool_type": "v3",
            "sqrt_price_x96": str(sqrt_price_x96),
            "tick": str(tick),
            "liquidity": str(liquidity),
            "price_token1_per_token0_raw": str(price),
        }
