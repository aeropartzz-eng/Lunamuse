"""Conector Coinbase Advanced — Fase 5 (CEX-007).

Implementa o contrato :class:`base.ExchangeAdapter` sobre o CCXT
(id ``coinbase`` = Coinbase Advanced Trade, API em
``api.coinbase.com``). Somente endpoints públicos de mercado, sem
nenhuma chave de API e sem envio de ordens.

Rate limits públicos (CEX-012, docs CDP 2026-11-10 — ver README):
REST pública 10 req/s por IP; WebSocket 8 conexões/s e 8 msgs/s
não autenticadas por IP. O token bucket local é 10 req/s, burst 15.

Limitações conhecidas (ver README):
- Sem funding rate nem open interest via API pública/CCXT
  (``has.fetchFundingRate/fetchOpenInterest = False``) — os métodos
  levantam ``ExchangeError`` (BAD_RESPONSE) em vez de inventar dado.
- Perpétuos Advanced (ex.: BTC-PERP) existem só em jurisdições
  fora dos EUA; o conector não assume que existam.
- Candles: 1m, 5m, 15m, 30m, 1h, 2h, 6h, 1d (sem 3m/4h/8h/12h/1w).
- Máx. 350 candles por chamada de OHLCV.
"""

from __future__ import annotations

from ccxt_adapter import CCXTAdapter


class CoinbaseAdapter(CCXTAdapter):
    """Coinbase Advanced Trade — leitura pública via CCXT."""

    exchange_id = "coinbase"
    name = "Coinbase Advanced"
    ccxt_id = "coinbase"
    rate_per_sec = 10.0
    rate_burst = 15
    supports_funding = False
    supports_open_interest = False
    default_type = "spot"


__all__ = ["CoinbaseAdapter"]
