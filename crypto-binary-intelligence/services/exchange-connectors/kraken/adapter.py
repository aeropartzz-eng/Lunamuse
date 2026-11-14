"""Conector Kraken — Fase 5 (CEX-008).

Implementa o contrato :class:`base.ExchangeAdapter` sobre o CCXT
(id ``kraken``). Somente endpoints públicos de mercado, sem nenhuma
chave de API e sem envio de ordens.

Particularidade: Kraken usa alias de símbolos — ``XBT`` para BTC e
``XDG`` para DOGE (códigos nativos como ``XXBTZUSD``). A tabela de
alias vive em :mod:`normalization` (``ASSET_ALIASES``) e é aplicada
em todos os métodos; o canônico é sempre ``BTC/USD`` etc.

Rate limits públicos (CEX-012, docs Kraken 2026-11-12 — ver README):
endpoints públicos não têm custo no contador da API; a orientação
oficial é não passar de 1 chamada/s por IP (Trades/OHLC contam por
IP + par). O token bucket local é 1 req/s, burst 3.

Limitações conhecidas (ver README):
- Sem funding rate nem open interest no Spot via API pública/CCXT
  (``has.fetchFundingRate = False``) — os métodos levantam
  ``ExchangeError`` (BAD_RESPONSE) em vez de inventar dado. O
  open interest de futuros vive na API Kraken Futures (fora deste
  conector spot).
- Candles: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 2w.
- Kraken não opera em alguns estados dos EUA (ex.: NY, WA) — a
  presença no catálogo não garante disponibilidade regional (§3).
"""

from __future__ import annotations

from ccxt_adapter import CCXTAdapter


class KrakenAdapter(CCXTAdapter):
    """Kraken Spot — leitura pública via CCXT (alias XBT→BTC)."""

    exchange_id = "kraken"
    name = "Kraken"
    ccxt_id = "kraken"
    rate_per_sec = 1.0
    rate_burst = 3
    supports_funding = False
    supports_open_interest = False
    default_type = "spot"


__all__ = ["KrakenAdapter"]
