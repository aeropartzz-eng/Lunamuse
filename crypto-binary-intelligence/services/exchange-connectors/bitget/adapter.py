"""Conector Bitget — Fase 5 (CEX-009).

Implementa o contrato :class:`base.ExchangeAdapter` sobre o CCXT
(id ``bitget``). Somente endpoints públicos de mercado, sem nenhuma
chave de API e sem envio de ordens.

Bitget tem futuros/perpétuos com funding rate e open interest: ambos
são lidos no mercado swap com o símbolo canônico ``BASE/QUOTE:USDT``
(ex.: ``BTC/USDT:USDT``), via CCXT unificado.

Rate limits públicos (CEX-012, docs Bitget verificadas 2026-11-09
— ver README): teto geral 6.000 req/min por IP (REST + WS
compartilham a cota); market data 20 req/s por IP; tickers 20/s.
O token bucket local é 20 req/s, burst 20.

Limitações conhecidas (ver README):
- Conta Classic em modo de manutenção; a API atual é a UTA v3 — o
  CCXT 4.x já usa os endpoints v3 para market data.
- Bitget não atende EUA, Reino Unido e outras jurisdições
  restritas — presença no catálogo não garante disponibilidade (§3).
- Candles: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 3d, 1w, 1M.
"""

from __future__ import annotations

from ccxt_adapter import CCXTAdapter


class BitgetAdapter(CCXTAdapter):
    """Bitget Spot + USDT Perpétuos — leitura pública via CCXT."""

    exchange_id = "bitget"
    name = "Bitget"
    ccxt_id = "bitget"
    rate_per_sec = 20.0
    rate_burst = 20
    supports_funding = True
    supports_open_interest = True
    default_type = "spot"


__all__ = ["BitgetAdapter"]
