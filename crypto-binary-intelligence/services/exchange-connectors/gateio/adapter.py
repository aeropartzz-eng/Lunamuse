"""Conector Gate.io — Fase 5 (CEX-010).

Implementa o contrato :class:`base.ExchangeAdapter` sobre o CCXT
(id ``gate``). Somente endpoints públicos de mercado, sem nenhuma
chave de API e sem envio de ordens.

Gate.io tem futuros/perpétuos com funding rate: lido no mercado swap
com o símbolo canônico ``BASE/QUOTE:USDT`` (ex.: ``BTC/USDT:USDT``),
via CCXT unificado.

Rate limits públicos (CEX-012, docs Gate API v4 — ver README):
endpoints públicos de spot 900 req/s por IP; o CCXT impõe
``rateLimit`` de 50 ms entre chamadas. O token bucket local é
20 req/s, burst 20 (ritmo do CCXT, bem abaixo do teto oficial).

Limitações conhecidas (ver README):
- Open interest: a API pública tem o campo (contratos futuros),
  mas o CCXT 4.x não implementa ``fetchOpenInterest`` para Gate
  (``has.fetchOpenInterest = False``) — o método levanta
  ``ExchangeError`` (BAD_RESPONSE) em vez de inventar dado; o
  suporte nativo é trabalho futuro, não desta fase.
- Gate.io não atende EUA, Canadá e outras jurisdições restritas —
  presença no catálogo não garante disponibilidade regional (§3).
- Candles: 10s, 1m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 1d, 7d, 1w
  (o ``10s`` não está na lista da especificação e é rejeitado por
  ``validate_timeframe``; ``1w``/``7d`` coexistem no CCXT).
"""

from __future__ import annotations

from ccxt_adapter import CCXTAdapter


class GateioAdapter(CCXTAdapter):
    """Gate.io Spot + USDT Perpétuos — leitura pública via CCXT."""

    exchange_id = "gateio"
    name = "Gate.io"
    ccxt_id = "gate"
    rate_per_sec = 20.0
    rate_burst = 20
    supports_funding = True
    supports_open_interest = False
    default_type = "spot"


__all__ = ["GateioAdapter"]
