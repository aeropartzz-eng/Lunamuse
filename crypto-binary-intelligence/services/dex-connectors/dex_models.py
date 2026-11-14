"""Modelos DEX / on-chain (Fase 6 — DEX-001…DEX-007).

Modelos de **dados** (somente leitura). O par DEX é normalizado a partir
de qualquer fonte (DEX Screener, Raydium, PancakeSwap, Uniswap, Jupiter)
para o mesmo vocabulário; o payload original fica em ``raw``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


def _dec(value: Any) -> Optional[Decimal]:
    """Converte número/str para Decimal; None/inválido vira None."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


@dataclass(frozen=True)
class DexPair:
    """Um par/pool de uma DEX, normalizado (descoberta e triagem)."""

    chain: str  # chainId da fonte, ex.: "solana", "bsc", "ethereum", "base"
    dex: str  # ex.: "raydium", "pancakeswap", "uniswap"
    pair_address: str
    base_symbol: str
    base_address: str
    quote_symbol: str
    quote_address: str
    price_usd: Optional[Decimal] = None
    price_native: Optional[Decimal] = None
    liquidity_usd: Optional[Decimal] = None
    volume_24h_usd: Optional[Decimal] = None
    txns_24h: Optional[int] = None
    fdv_usd: Optional[Decimal] = None
    market_cap_usd: Optional[Decimal] = None
    pair_created_at_ms: Optional[int] = None
    url: Optional[str] = None
    raw: Any = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Dict serializável (Decimal vira str) para o contrato DexAdapter."""
        out: dict[str, Any] = {
            "chain": self.chain,
            "dex": self.dex,
            "pair_address": self.pair_address,
            "base_token": {
                "symbol": self.base_symbol,
                "address": self.base_address,
            },
            "quote_token": {
                "symbol": self.quote_symbol,
                "address": self.quote_address,
            },
            "price_usd": str(self.price_usd) if self.price_usd is not None else None,
            "price_native": (
                str(self.price_native) if self.price_native is not None else None
            ),
            "liquidity_usd": (
                str(self.liquidity_usd) if self.liquidity_usd is not None else None
            ),
            "volume_24h_usd": (
                str(self.volume_24h_usd) if self.volume_24h_usd is not None else None
            ),
            "txns_24h": self.txns_24h,
            "fdv_usd": str(self.fdv_usd) if self.fdv_usd is not None else None,
            "market_cap_usd": (
                str(self.market_cap_usd) if self.market_cap_usd is not None else None
            ),
            "pair_created_at_ms": self.pair_created_at_ms,
            "url": self.url,
        }
        if self.raw is not None:
            out["raw"] = self.raw
        return out


def normalize_dexscreener_pair(raw: dict[str, Any]) -> DexPair:
    """Normaliza um par no formato da API pública do DEX Screener.

    A API agregadora serve para descoberta e triagem (§3): não presumir
    que seja feed de trades em tempo real.
    """
    base = raw.get("baseToken") or {}
    quote = raw.get("quoteToken") or {}
    liquidity = raw.get("liquidity") or {}
    volume = raw.get("volume") or {}
    txns = raw.get("txns") or {}
    h24 = txns.get("h24") or {}
    txns_24h = None
    if isinstance(h24, dict):
        buys = h24.get("buys") or 0
        sells = h24.get("sells") or 0
        if isinstance(buys, int) and isinstance(sells, int):
            txns_24h = buys + sells
    return DexPair(
        chain=str(raw.get("chainId") or ""),
        dex=str(raw.get("dexId") or ""),
        pair_address=str(raw.get("pairAddress") or ""),
        base_symbol=str(base.get("symbol") or ""),
        base_address=str(base.get("address") or ""),
        quote_symbol=str(quote.get("symbol") or ""),
        quote_address=str(quote.get("address") or ""),
        price_usd=_dec(raw.get("priceUsd")),
        price_native=_dec(raw.get("priceNative")),
        liquidity_usd=_dec(liquidity.get("usd")),
        volume_24h_usd=_dec(volume.get("h24")),
        txns_24h=txns_24h,
        fdv_usd=_dec(raw.get("fdv")),
        market_cap_usd=_dec(raw.get("marketCap")),
        pair_created_at_ms=raw.get("pairCreatedAt"),
        url=raw.get("url"),
        raw=raw,
    )
