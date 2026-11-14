"""Conector OKX — Fase 4 (CEX-003).

Implementa o contrato :class:`base.ExchangeAdapter` sobre o CCXT
(id ``okx``, API v5). Somente endpoints públicos de mercado, sem
nenhuma chave de API e sem envio de ordens.

Mercados: spot (``BTC/USDT``) e swaps/futuros (``BTC/USDT:USDT``),
via símbolo unificado do CCXT. O formato nativo da OKX é
``BTC-USDT`` (com hífen); a conversão é feita pelo CCXT, e o
canônico do projeto continua ``BASE/QUOTE``.

Rate limits públicos (CEX-012, docs OKX v5 — ver README): por
endpoint, por IP, em janelas de 2 s — tickers 20/2 s, order book e
candles 40/2 s, trades 100/2 s, funding rate e open interest 10/2 s
por IP + instrumento (erro 50011 ao exceder). O token bucket local
é 5 req/s, burst 10 — igual ao endpoint público mais restrito.

Limitações conhecidas (ver README):
- Sem WebSocket em tempo real nesta fase (REST; WS na Fase 7).
- OKX não atende EUA (a OKX US é operação separada) nem outras
  jurisdições restritas — presença no catálogo não garante
  disponibilidade regional (§3).
- Funding rate e open interest só existem para contratos: pedir
  para ``BTC/USDT`` lê o perpétuo ``BTC/USDT:USDT``.
- Candles: sem 1s/5s/15s/30s nem 8h (intervalos v5: 1m–12h, 1d, 1w).
"""

from __future__ import annotations

from ccxt_adapter import CCXTAdapter


class OkxAdapter(CCXTAdapter):
    """OKX Spot + Swaps — leitura pública via CCXT (API v5)."""

    exchange_id = "okx"
    name = "OKX"
    ccxt_id = "okx"
    rate_per_sec = 5.0
    rate_burst = 10
    supports_funding = True
    supports_open_interest = True
    default_type = "spot"


__all__ = ["OkxAdapter"]
