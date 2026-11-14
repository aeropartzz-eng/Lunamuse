"""Integrações antifraude externas (Fase 6 — SEC-006).

Somente APIs públicas **sem chave**:
- GoPlus Token Security (free, 100 chamadas/min, sem chave).
- RugCheck (report gratuito em cache, sem chave; report fresco e
  bulk exigem plano pago — bloqueados).
- Bubblemaps API legada (map-metadata, sem chave, só mapas já
  computados; a API nova exige chave — bloqueada). **Em 2026-11-13
  a legada retornou HTTP 500** — instável; o cliente trata a falha
  como dado ausente (REVISÃO, nunca aprovação no escuro).

Cada cliente retorna ``{"ok", "data", "blocked", "reason"}``: falha de
fonte nunca derruba a avaliação — vira evidência de dado ausente e o
Shield decide REVISÃO em vez de aprovar no escuro.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    from dex_http import DexHttpClient, DexHttpError
except ImportError:  # diretório services/dex-connectors fora do sys.path
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parents[1] / "dex-connectors"))
    from dex_http import DexHttpClient, DexHttpError

# Chain IDs do GoPlus (https://docs.gopluslabs.io/).
GOPLUS_CHAIN_IDS = {
    "ethereum": "1",
    "bsc": "56",
    "base": "8453",
    "solana": "101",
    "polygon": "137",
    "arbitrum": "42161",
    "optimism": "10",
    "avalanche": "43114",
}

# Chains da API legada da Bubblemaps.
BUBBLEMAPS_LEGACY_CHAINS = (
    "eth",
    "bsc",
    "ftm",
    "avax",
    "cro",
    "arbi",
    "poly",
    "base",
    "sol",
    "sonic",
)


def _blocked(reason: str) -> dict[str, Any]:
    return {"ok": False, "data": None, "blocked": True, "reason": reason}


def _failed(reason: str) -> dict[str, Any]:
    return {"ok": False, "data": None, "blocked": False, "reason": reason}


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data, "blocked": False, "reason": None}


class GoPlusClient:
    """GoPlus Token Security API — pública, sem chave (plano free)."""

    source_id = "goplus"
    base_url = "https://api.gopluslabs.io"

    def __init__(self, client: Optional[DexHttpClient] = None) -> None:
        self._client = client or DexHttpClient(
            self.base_url, timeout=10.0, min_interval_s=0.6
        )

    def token_security(
        self, chain: str, contract_addresses: list[str]
    ) -> dict[str, Any]:
        """Segurança de token(s) EVM/Solana. Até 1 endereço no free.

        Retorna o ``result`` bruto do endereço (ou dict vazio).
        """
        chain_id = GOPLUS_CHAIN_IDS.get(chain.lower())
        if chain_id is None:
            return _failed(f"goplus: chain '{chain}' nao suportada")
        if not contract_addresses:
            return _failed("goplus: nenhum contract_address informado")
        address = contract_addresses[0]
        try:
            data = self._client.get(
                f"/api/v1/token_security/{chain_id}",
                params={"contract_addresses": address},
            )
        except DexHttpError as exc:
            return _failed(f"goplus: {exc}")
        if not isinstance(data, dict):
            return _failed("goplus: resposta inesperada")
        result = (data.get("result") or {}).get(address.lower())
        if not isinstance(result, dict):
            return _failed("goplus: token sem resultado")
        return _ok(result)


class RugCheckClient:
    """RugCheck — report gratuito (em cache), sem chave (Solana)."""

    source_id = "rugcheck"
    base_url = "https://api.rugcheck.xyz"

    def __init__(self, client: Optional[DexHttpClient] = None) -> None:
        self._client = client or DexHttpClient(
            self.base_url, timeout=10.0, min_interval_s=0.5
        )

    def report(self, mint: str) -> dict[str, Any]:
        """Report completo do mint (cache gratuito; sem chave)."""
        try:
            data = self._client.get(f"/v1/tokens/{mint}/report")
        except DexHttpError as exc:
            return _failed(f"rugcheck: {exc}")
        if not isinstance(data, dict):
            return _failed("rugcheck: resposta inesperada")
        return _ok(data)

    def summary(self, mint: str) -> dict[str, Any]:
        """Resumo do report (mais curto que o completo)."""
        try:
            data = self._client.get(f"/v1/tokens/{mint}/report/summary")
        except DexHttpError as exc:
            return _failed(f"rugcheck: {exc}")
        if not isinstance(data, dict):
            return _failed("rugcheck: resposta inesperada")
        return _ok(data)


class BubblemapsClient:
    """Bubblemaps — API legada sem chave + status da API nova.

    A API nova (api.bubblemaps.io) exige cadastro e chave — BLOQUEADA
    aguardando chave do Will. A legada (api-legacy.bubblemaps.io)
    responde sem chave **somente para mapas já computados**; mapa
    inexistente retorna 200 com status explícito de não computado.
    """

    source_id = "bubblemaps"
    legacy_base_url = "https://api-legacy.bubblemaps.io"

    def __init__(self, client: Optional[DexHttpClient] = None) -> None:
        self._client = client or DexHttpClient(
            self.legacy_base_url, timeout=10.0, min_interval_s=0.5
        )

    def map_metadata(self, chain: str, token: str) -> dict[str, Any]:
        """Metadados do mapa (legada, sem chave)."""
        if chain.lower() not in BUBBLEMAPS_LEGACY_CHAINS:
            return _failed(f"bubblemaps: chain '{chain}' nao suportada na API legada")
        try:
            data = self._client.get(
                "/map-metadata",
                params={"chain": chain.lower(), "token": token},
            )
        except DexHttpError as exc:
            return _failed(f"bubblemaps: {exc}")
        if not isinstance(data, dict):
            return _failed("bubblemaps: resposta inesperada")
        status = str(data.get("status") or "")
        if status and status != "OK":
            return {
                "ok": False,
                "data": data,
                "blocked": False,
                "reason": f"bubblemaps: mapa nao computado (status={status})",
            }
        return _ok(data)

    @staticmethod
    def new_api_status() -> dict[str, Any]:
        """Status da API nova (requer chave) — sempre bloqueado aqui."""
        return _blocked(
            "bubblemaps API nova exige cadastro + API key; "
            "aguardando chave do Will (usar API legada p/ mapas computados)"
        )
