"""Conector PancakeSwap (Fase 6 — DEX-005).

Leitura de pools V2 e swaps da BNB Chain **via RPC público** (eth_call
em pares/factory), sem chave de API.

Por que RPC e não a API REST da PancakeSwap:
- A API legada de info (``api.pancakeswap.info/api/v2``) não é
  documentada/oficial e não é confiável como fonte.
- A Aggregator API atual (``hub-gateway.pancakeswap.com``) exige
  ``x-secure-token`` — token de API que o Will ainda não forneceu
  (BLOQUEADO aguardando chave; cotação de rota agregada fica fora).
- O par V2 on-chain (``getReserves``/``token0``/``token1``) é a fonte
  de verdade para preço, liquidez e simulação de slippage.

Docs: https://developer.pancakeswap.finance/
Factory V2 (BSC): 0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

try:
    from amm import constant_product_out, price_impact_pct, spot_price
    from dex_http import DexHttpError
    from evm_rpc import (
        DEAD_ADDRESS,
        ZERO_ADDRESS,
        EvmRpcClient,
        EvmRpcError,
    )
except ImportError:  # diretórios fora do sys.path (ver tests/dex/conftest.py)
    import sys
    from pathlib import Path

    _base = Path(__file__).resolve().parents[1]
    sys.path.append(str(_base))
    sys.path.append(str(_base / "rpc"))
    from amm import constant_product_out, price_impact_pct, spot_price
    from dex_http import DexHttpError
    from evm_rpc import (
        DEAD_ADDRESS,
        ZERO_ADDRESS,
        EvmRpcClient,
        EvmRpcError,
    )

V2_FACTORY_BSC = "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73"
V2_FEE_BPS = 25  # 0,25% por swap no V2

# WBNB (BSC) — par de referência mais comum para preço em USD via
# DEX Screener; o adapter em si não precifica em USD sem fonte externa.
WBNB_BSC = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"


class PancakeswapAdapter:
    """Implementa o contrato DexAdapter (ver ../base.py)."""

    source_id = "pancakeswap"
    name = "Pancakeswap"

    def __init__(self, rpc: Optional[EvmRpcClient] = None) -> None:
        self._rpc = rpc or EvmRpcClient(chain_id=56)

    # -- contrato DexAdapter ------------------------------------------
    def search_pairs(self, query: str) -> list[dict[str, Any]]:
        """Sem busca pública sem chave: usar o DEX Screener (DEX-001).

        A API de info legada não é confiável e a Aggregator API exige
        token (``x-secure-token``) — bloqueado aguardando o Will.
        """
        raise NotImplementedError(
            "Pancakeswap: sem endpoint publico de busca sem chave; "
            "usar DexscreenerAdapter.search_pairs p/ descoberta e "
            "PancakeswapAdapter.get_pool p/ leitura do par on-chain."
        )

    def get_pool(self, pool_address: str) -> dict[str, Any]:
        """Reservas, preço e liquidez de um par V2 (leitura on-chain)."""
        try:
            token0, token1 = self._rpc.pair_tokens(pool_address)
            reserve0, reserve1, _ts = self._rpc.pair_reserves(pool_address)
            lp_supply = self._rpc.token_total_supply(pool_address)
        except EvmRpcError as exc:
            raise DexHttpError(f"pancakeswap get_pool falhou: {exc}") from exc
        price0_in_1 = spot_price(Decimal(reserve0), Decimal(reserve1))
        price1_in_0 = spot_price(Decimal(reserve1), Decimal(reserve0))
        return {
            "chain": "bsc",
            "dex": "pancakeswap",
            "pair_address": pool_address,
            "base_token": {"symbol": "", "address": token0},
            "quote_token": {"symbol": "", "address": token1},
            "reserve0": str(reserve0),
            "reserve1": str(reserve1),
            "lp_total_supply": str(lp_supply),
            "price_token0_in_token1": str(price0_in_1),
            "price_token1_in_token0": str(price1_in_0),
            "pool_type": "v2",
        }

    def health(self) -> dict[str, Any]:
        """Estado do RPC BSC subjacente (uma chamada real)."""
        status = self._rpc.health()
        return {"source": self.source_id, **status}

    # -- próprios -------------------------------------------------------
    def find_pair(self, token_a: str, token_b: str) -> Optional[str]:
        """Endereço do par V2 na factory, ou None se não existir."""
        try:
            pair = self._rpc.factory_get_pair(V2_FACTORY_BSC, token_a, token_b)
        except EvmRpcError:
            return None
        if pair.lower() in (ZERO_ADDRESS,):
            return None
        return pair

    def quote_sell(
        self,
        pair_address: str,
        amount_in: Decimal,
        sell_token_is_token0: bool,
        fee_bps: int = V2_FEE_BPS,
    ) -> dict[str, Any]:
        """Simulação de venda (só matemática; nenhuma transação).

        Retorna quanto sairia do outro lado e o impacto no preço.
        """
        pool = self.get_pool(pair_address)
        reserve0 = Decimal(pool["reserve0"])
        reserve1 = Decimal(pool["reserve1"])
        reserve_in, reserve_out = (
            (reserve0, reserve1) if sell_token_is_token0 else (reserve1, reserve0)
        )
        out = constant_product_out(amount_in, reserve_in, reserve_out, fee_bps)
        impact = price_impact_pct(amount_in, reserve_in, reserve_out, fee_bps)
        return {
            "pair_address": pair_address,
            "amount_in": str(amount_in),
            "amount_out": str(out),
            "price_impact_pct": str(impact),
            "fee_bps": fee_bps,
        }

    def lp_burned_or_locked_info(
        self, pair_address: str
    ) -> dict[str, Any]:
        """Quanto do LP está no endereço morto (queimado).

        LP bloqueado em locker (ex.: Team Finance) exige leitura do
        contrato do locker — fora do escopo desta fase; o Crypto Shield
        usa DEX Screener/RugCheck para o restante.
        """
        try:
            burned = self._rpc.token_balance_of(pair_address, DEAD_ADDRESS)
            total = self._rpc.token_total_supply(pair_address)
        except EvmRpcError as exc:
            raise DexHttpError(
                f"pancakeswap lp info falhou: {exc}"
            ) from exc
        pct = (
            (Decimal(burned) / Decimal(total) * Decimal("100"))
            if total > 0
            else Decimal("0")
        )
        return {
            "pair_address": pair_address,
            "lp_burned": str(burned),
            "lp_total_supply": str(total),
            "lp_burned_pct": str(pct),
        }
