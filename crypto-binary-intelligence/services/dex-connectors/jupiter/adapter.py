"""Conector Jupiter (Fase 6 — DEX-007).

Agregador de swaps em Solana. Tier **Lite** público, sem chave:
https://lite-api.jup.ag — 0,5 req/s sem chave (chave gratuita dobra
para 1 req/s; planos pagos a partir de US$ 25/mês para mais).

Somente leitura aqui: preço (Price API v3) e cotação de rota
(Quote API v1 — simulação de rota/slippage, sem montar nem enviar
transação; o endpoint ``/swap`` que constrói transação **não** é
chamado). Execução DEX é semana 19 da expansão, com Crypto Shield
obrigatório — fora desta fase.

Docs: https://dev.jup.ag/ (portal: https://developers.jup.ag)
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

BASE_URL = "https://lite-api.jup.ag"


class JupiterAdapter:
    """Implementa o contrato DexAdapter (ver ../base.py)."""

    source_id = "jupiter"
    name = "Jupiter"

    def __init__(
        self,
        client: Optional[DexHttpClient] = None,
        timeout: float = 10.0,
    ) -> None:
        # Lite keyless: 0,5 req/s -> throttle de 2s entre chamadas.
        self._client = client or DexHttpClient(
            BASE_URL, timeout=timeout, min_interval_s=2.0
        )
        self._last_ok: Optional[float] = None

    # -- contrato DexAdapter ------------------------------------------
    def search_pairs(self, query: str) -> list[dict[str, Any]]:
        """Agregador não tem pares próprios: usar DEX Screener (DEX-001)."""
        raise NotImplementedError(
            "Jupiter: agregador sem pares proprios; usar "
            "DexscreenerAdapter.search_pairs p/ descoberta e "
            "JupiterAdapter.get_quote p/ cotacao de rota."
        )

    def get_pool(self, pool_address: str) -> dict[str, Any]:
        """Agregador não tem pools próprios: usar get_quote."""
        raise NotImplementedError(
            "Jupiter: agregador sem pools proprios; usar "
            "JupiterAdapter.get_quote p/ simular rota e slippage."
        )

    def health(self) -> dict[str, Any]:
        """Estado do adapter (sem chamada de rede; ver ``ping``)."""
        return {
            "source": self.source_id,
            "connected": self._last_ok is not None,
            "status": "ok" if self._last_ok is not None else "unknown",
            "last_ok": self._last_ok,
        }

    # -- endpoints próprios ------------------------------------------
    def get_price(self, mints: list[str]) -> dict[str, Any]:
        """Preço em USD por mint (Price API v3).

        Resposta é um dict plano ``{mint: {usdPrice, ...}}`` (v3 não
        envolve em ``data``). Retorna o dict com ``price`` (= usdPrice)
        adicionado por conveniência.
        """
        if not mints:
            return {}
        data = self._client.get("/price/v3", params={"ids": ",".join(mints)})
        self._mark_ok()
        if not isinstance(data, dict):
            return {}
        out: dict[str, Any] = {}
        for mint, info in data.items():
            if isinstance(info, dict):
                entry = dict(info)
                entry["price"] = info.get("usdPrice")
                out[mint] = entry
        return out

    def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> dict[str, Any]:
        """Cotação de rota (só simulação): outAmount, priceImpactPct.

        ``amount`` é a quantidade em unidades mínimas do token de
        entrada (lamports/unidades com decimals). Nenhuma transação é
        montada ou enviada.
        """
        if amount <= 0:
            raise ValueError("amount deve ser > 0")
        data = self._client.get(
            "/swap/v1/quote",
            params={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": str(slippage_bps),
            },
        )
        self._mark_ok()
        if not isinstance(data, dict) or "outAmount" not in data:
            raise DexHttpError(f"Jupiter quote sem outAmount: {data}")
        return {
            "input_mint": input_mint,
            "output_mint": output_mint,
            "amount_in": str(amount),
            "amount_out": str(data.get("outAmount")),
            "price_impact_pct": str(data.get("priceImpactPct")),
            "slippage_bps": slippage_bps,
            "route_plan": data.get("routePlan"),
            "raw": data,
        }

    def ping(self) -> dict[str, Any]:
        """Uma leitura real mínima para provar conectividade."""
        # SOL (wrapped) — mint canônico da Solana.
        price = self.get_price(
            ["So11111111111111111111111111111111111111112"]
        )
        return {
            "source": self.source_id,
            "connected": True,
            "status": "ok",
            "price_returned": len(price),
        }

    # -- internos ------------------------------------------------------
    def _mark_ok(self) -> None:
        import time

        self._last_ok = time.time()
