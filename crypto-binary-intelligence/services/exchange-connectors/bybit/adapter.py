"""Conector Bybit — Fase 4 (CEX-002).

Implementa o contrato :class:`base.ExchangeAdapter` sobre o CCXT
(id ``bybit``, API v5). Somente endpoints públicos de mercado, sem
nenhuma chave de API e sem envio de ordens.

Mercados: spot (``BTC/USDT``) e contratos lineares/inversos
(``BTC/USDT:USDT``), via símbolo unificado do CCXT.

Rate limits públicos (CEX-012, docs Bybit — ver README): camada IP
de 600 req/5 s (exceder = HTTP 403 "access too frequent" e bloqueio
de ~10 min); limites por endpoint/UID só valem para trading. O token
bucket local é 10 req/s, burst 20 — bem abaixo do teto.

Limitações conhecidas (ver README):
- Sem WebSocket em tempo real nesta fase (REST; WS na Fase 7).
- IPs dos EUA e da China continental são rejeitados (403) pela
  Bybit; contas regionais (Turquia, Cazaquistão, Emirados Árabes,
  EEE, Japão etc.) usam domínios de API próprios — presença no
  catálogo não garante disponibilidade regional (§3).
- O CCXT obtém o funding rate de forma "emulada" (a partir do
  ticker do contrato); o valor é o publicado pela Bybit, não um
  cálculo local.
- Funding rate e open interest só existem para contratos: pedir
  para ``BTC/USDT`` lê o perpétuo ``BTC/USDT:USDT``.
- Candles: sem 1s/5s/15s/30s nem 8h (intervalos v5: 1, 3, 5, 15, 30,
  60, 120, 240, 360, 720 min, D, W, M).
"""

from __future__ import annotations

from ccxt_adapter import CCXTAdapter


class BybitAdapter(CCXTAdapter):
    """Bybit Spot + Contratos — leitura pública via CCXT (API v5)."""

    exchange_id = "bybit"
    name = "Bybit"
    ccxt_id = "bybit"
    rate_per_sec = 10.0
    rate_burst = 20
    supports_funding = True
    supports_open_interest = True
    default_type = "spot"


__all__ = ["BybitAdapter"]
