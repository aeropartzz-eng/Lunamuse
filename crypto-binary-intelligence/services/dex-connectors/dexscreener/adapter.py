"""Conector DEX Screener (Fase 6 — DEX-001).

API pública, sem chave: https://docs.dexscreener.com/api/reference
Base: https://api.dexscreener.com — 300 req/min (pares/busca),
60 req/min (perfis/boosts). Somente leitura.

A API agregadora serve para **descoberta e triagem** (§3): não presumir
que seja feed de trades em tempo real. Para eventos on-chain, usar
RPC/WebSocket ou indexador adequado.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from dex_http import DexHttpClient, DexHttpError
    from dex_models import normalize_dexscreener_pair
except ImportError:  # diretório services/dex-connectors fora do sys.path
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from dex_http import DexHttpClient, DexHttpError
    from dex_models import normalize_dexscreener_pair

BASE_URL = "https://api.dexscreener.com"

# chainIds suportados pela API (os 4 do escopo da Fase 6 + comuns).
CHAINS = ("solana", "bsc", "ethereum", "base")


class DexscreenerAdapter:
    """Implementa o contrato DexAdapter (ver ../base.py)."""

    source_id = "dexscreener"
    name = "Dexscreener"

    def __init__(
        self,
        client: Optional[DexHttpClient] = None,
        timeout: float = 10.0,
    ) -> None:
        self._client = client or DexHttpClient(
            BASE_URL, timeout=timeout, min_interval_s=0.25
        )
        self._last_ok: Optional[float] = None

    # -- contrato DexAdapter ------------------------------------------
    def search_pairs(self, query: str) -> list[dict[str, Any]]:
        """Descoberta de pares por símbolo, nome ou endereço (máx. 30)."""
        if not query or not query.strip():
            raise ValueError("search_pairs precisa de query não vazia")
        data = self._client.get("/latest/dex/search", params={"q": query.strip()})
        pairs = self._pairs_from_payload(data)
        self._mark_ok()
        return [p.to_dict() for p in pairs]

    def get_pool(
        self, pool_address: str, chain_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Dados de um pool por endereço.

        Aceita ``"chainId:pairAddress"`` ou ``pairAddress`` + ``chain_id``.
        Sem chainId não há como resolver o par (a API exige chainId).
        """
        chain, address = self._split_pool_address(pool_address, chain_id)
        data = self._client.get(f"/latest/dex/pairs/{chain}/{address}")
        pairs = self._pairs_from_payload(data)
        self._mark_ok()
        if not pairs:
            raise DexHttpError(
                f"par {chain}:{address} nao encontrado no DEX Screener",
                status=404,
            )
        return pairs[0].to_dict()

    def health(self) -> dict[str, Any]:
        """Estado do adapter (sem chamada de rede; ver ``ping``)."""
        return {
            "source": self.source_id,
            "connected": self._last_ok is not None,
            "status": "ok" if self._last_ok is not None else "unknown",
            "last_ok": self._last_ok,
        }

    # -- endpoints próprios ------------------------------------------
    def get_token_pairs(
        self, chain_id: str, token_address: str
    ) -> list[dict[str, Any]]:
        """Todos os pools de um token em uma chain (máx. 30)."""
        data = self._client.get(f"/token-pairs/v1/{chain_id}/{token_address}")
        pairs = self._pairs_from_payload(data)
        self._mark_ok()
        return [p.to_dict() for p in pairs]

    def get_pairs(
        self, chain_id: str, pair_addresses: list[str]
    ) -> list[dict[str, Any]]:
        """Pares conhecidos por endereço (até 30 por chamada)."""
        if not pair_addresses:
            return []
        joined = ",".join(pair_addresses[:30])
        data = self._client.get(f"/latest/dex/pairs/{chain_id}/{joined}")
        pairs = self._pairs_from_payload(data)
        self._mark_ok()
        return [p.to_dict() for p in pairs]

    def get_token_profiles_latest(self) -> list[dict[str, Any]]:
        """Últimos token profiles (60 req/min)."""
        data = self._client.get("/token-profiles/latest/v1")
        self._mark_ok()
        return data if isinstance(data, list) else []

    def get_token_boosts_latest(self) -> list[dict[str, Any]]:
        """Últimos tokens com boost (60 req/min; boost = placement pago)."""
        data = self._client.get("/token-boosts/latest/v1")
        self._mark_ok()
        return data if isinstance(data, list) else []

    def ping(self) -> dict[str, Any]:
        """Uma busca real mínima para provar conectividade."""
        result = self.search_pairs("SOL")
        return {
            "source": self.source_id,
            "connected": True,
            "status": "ok",
            "pairs_returned": len(result),
        }

    # -- internos ------------------------------------------------------
    @staticmethod
    def _pairs_from_payload(data: Any) -> list:
        if isinstance(data, dict):
            raw_pairs = data.get("pairs") or []
        elif isinstance(data, list):
            raw_pairs = data
        else:
            raw_pairs = []
        pairs = []
        for raw in raw_pairs:
            if isinstance(raw, dict) and raw.get("pairAddress"):
                pairs.append(normalize_dexscreener_pair(raw))
        return pairs

    @staticmethod
    def _split_pool_address(
        pool_address: str, chain_id: Optional[str]
    ) -> tuple[str, str]:
        if ":" in pool_address and chain_id is None:
            chain, address = pool_address.split(":", 1)
            return chain.strip(), address.strip()
        if chain_id is None:
            raise ValueError(
                "get_pool precisa de chain_id (ex.: 'solana') ou de "
                "pool_address no formato 'chainId:pairAddress'"
            )
        return chain_id, pool_address

    def _mark_ok(self) -> None:
        import time

        self._last_ok = time.time()
