"""Conector Binance — Fase 4 (CEX-001).

Implementa o contrato :class:`base.ExchangeAdapter` sobre o CCXT
(id ``binance``). Somente endpoints públicos de mercado, sem nenhuma
chave de API e sem envio de ordens.

Mercados: spot (``BTC/USDT``) e USDⓈ-M futuros/perpétuos
(``BTC/USDT:USDT``), via símbolo unificado do CCXT.

Rate limits públicos (CEX-012, docs Binance — ver README): spot
6.000 de peso/min por IP (klines peso 2, order book 5–250 conforme
a profundidade); 429 vira 418 (banimento de IP) se insistir. O token
bucket local é 10 req/s, burst 20 — bem abaixo do teto.

Limitações conhecidas (ver README):
- Sem WebSocket em tempo real nesta fase (REST; WS na Fase 7).
- Binance.com não atende residentes dos EUA (usam Binance.US,
  API separada) nem jurisdições restritas — presença no catálogo
  não garante disponibilidade regional (§3).
- Funding rate e open interest só existem para contratos: pedir
  para ``BTC/USDT`` lê o perpétuo ``BTC/USDT:USDT``.
"""

from __future__ import annotations

from ccxt_adapter import CCXTAdapter


class BinanceAdapter(CCXTAdapter):
    """Binance Spot + USDⓈ-M Perpétuos — leitura pública via CCXT."""

    exchange_id = "binance"
    name = "Binance"
    ccxt_id = "binance"
    rate_per_sec = 10.0
    rate_burst = 20
    supports_funding = True
    supports_open_interest = True
    default_type = "spot"


__all__ = ["BinanceAdapter"]
