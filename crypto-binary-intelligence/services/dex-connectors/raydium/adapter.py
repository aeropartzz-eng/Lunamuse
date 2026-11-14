"""Conector Raydium (Fase 6 — DEX-006).

API v3 pública, sem autenticação: https://docs.raydium.io/
Base: https://api-v3.raydium.io — todos os endpoints de leitura
aceitam chamadas anônimas (só o fórum exige ``ray-token`` com
assinatura de carteira — fora do escopo, nunca usado).

Endpoints usados: ``/pools/info/mint``, ``/pools/info/ids``,
``/pools/info/list``, ``/mint/price``, ``/mint/list``.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from dex_http import DexHttpClient, DexHttpError
except ImportError:  # diretório services/dex-connectors fora do sys.path
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from dex_http import DexHttpClient, DexHttpError

BASE_URL = "https://api-v3.raydium.io"


class RaydiumAdapter:
    """Implementa o contrato DexAdapter (ver ../base.py)."""

    source_id = "raydium"
    name = "Raydium"

    def __init__(
        self,
        client: Optional[DexHttpClient] = None,
        timeout: float = 10.0,
    ) -> None:
        self._client = client or DexHttpClient(
            BASE_URL, timeout=timeout, min_interval_s=0.2
        )
        self._last_ok: Optional[float] = None

    # -- contrato DexAdapter ------------------------------------------
    def search_pairs(self, query: str) -> list[dict[str, Any]]:
        """Sem busca por símbolo na API v3: usar DEX Screener (DEX-001)."""
        raise NotImplementedError(
            "Raydium: API v3 nao tem busca por simbolo; usar "
            "DexscreenerAdapter.search_pairs p/ descoberta e "
            "RaydiumAdapter.get_pools_by_mint p/ leitura dos pools."
        )

    def get_pool(self, pool_address: str) -> dict[str, Any]:
        """Pool por id (endereço do pool) via /pools/info/ids."""
        pools = self.get_pools_by_ids([pool_address])
        if not pools:
            raise DexHttpError(
                f"pool Raydium {pool_address} nao encontrado", status=404
            )
        return pools[0]

    def health(self) -> dict[str, Any]:
        """Estado do adapter (sem chamada de rede; ver ``ping``)."""
        return {
            "source": self.source_id,
            "connected": self._last_ok is not None,
            "status": "ok" if self._last_ok is not None else "unknown",
            "last_ok": self._last_ok,
        }

    # -- endpoints próprios ------------------------------------------
    def get_pools_by_mint(
        self,
        mint: str,
        mint2: Optional[str] = None,
        pool_type: str = "all",
        page_size: int = 10,
    ) -> list[dict[str, Any]]:
        """Pools que contêm um mint (omitir mint2 p/ buscar um só mint)."""
        params: dict[str, Any] = {
            "mint1": mint,
            "poolType": pool_type,
            "poolSortField": "default",
            "sortType": "desc",
            "pageSize": page_size,
            "page": 1,
        }
        if mint2:
            params["mint2"] = mint2
        data = self._client.get("/pools/info/mint", params=params)
        pools = self._pools_from_envelope(data)
        self._mark_ok()
        return [self._normalize_pool(p) for p in pools]

    def get_pools_by_ids(self, pool_ids: list[str]) -> list[dict[str, Any]]:
        """Pools por id (endereço), até 30 por chamada."""
        if not pool_ids:
            return []
        data = self._client.get(
            "/pools/info/ids", params={"ids": ",".join(pool_ids[:30])}
        )
        pools = self._pools_from_envelope(data)
        self._mark_ok()
        return [self._normalize_pool(p) for p in pools]

    def get_pools_list(
        self, pool_type: str = "all", page_size: int = 20
    ) -> list[dict[str, Any]]:
        """Lista geral de pools (ordenada por TVL)."""
        data = self._client.get(
            "/pools/info/list",
            params={
                "poolType": pool_type,
                "poolSortField": "tvl",
                "sortType": "desc",
                "pageSize": page_size,
                "page": 1,
            },
        )
        pools = self._pools_from_envelope(data)
        self._mark_ok()
        return [self._normalize_pool(p) for p in pools]

    def get_mint_price(self, mints: list[str]) -> dict[str, Any]:
        """Preço em USD por mint (``/mint/price``)."""
        if not mints:
            return {}
        data = self._client.get(
            "/mint/price", params={"mints": ",".join(mints)}
        )
        self._mark_ok()
        if isinstance(data, dict):
            inner = data.get("data") or {}
            return inner if isinstance(inner, dict) else {}
        return {}

    def ping(self) -> dict[str, Any]:
        """Uma leitura real mínima para provar conectividade."""
        pools = self.get_pools_list(page_size=1)
        return {
            "source": self.source_id,
            "connected": True,
            "status": "ok",
            "pools_returned": len(pools),
        }

    # -- internos ------------------------------------------------------
    @staticmethod
    def _pools_from_envelope(data: Any) -> list[dict[str, Any]]:
        if not isinstance(data, dict):
            return []
        if not data.get("success", True):
            raise DexHttpError(f"Raydium API retornou success=false: {data}")
        inner = data.get("data")
        if isinstance(inner, dict):
            pools = inner.get("data") or []
        elif isinstance(inner, list):
            pools = inner
        else:
            pools = []
        return [p for p in pools if isinstance(p, dict)]

    @staticmethod
    def _normalize_pool(raw: dict[str, Any]) -> dict[str, Any]:
        mint_a = raw.get("mintA") or {}
        mint_b = raw.get("mintB") or {}
        return {
            "chain": "solana",
            "dex": "raydium",
            "pair_address": raw.get("id") or "",
            "pool_type": raw.get("poolType") or raw.get("type") or "",
            "base_token": {
                "symbol": mint_a.get("symbol") or "",
                "address": mint_a.get("address") or "",
                "decimals": mint_a.get("decimals"),
            },
            "quote_token": {
                "symbol": mint_b.get("symbol") or "",
                "address": mint_b.get("address") or "",
                "decimals": mint_b.get("decimals"),
            },
            "price": raw.get("price"),
            "tvl_usd": raw.get("tvl"),
            "volume_24h_usd": (raw.get("day") or {}).get("volume"),
            "apr_24h": (raw.get("day") or {}).get("apr"),
            "fee_rate": raw.get("feeRate"),
            "lp_mint": (raw.get("lpMint") or {}).get("address"),
            "raw": raw,
        }

    def _mark_ok(self) -> None:
        import time

        self._last_ok = time.time()
