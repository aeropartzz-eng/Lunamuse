# Gate.io — Fase 5 (CEX-010) ✅

- Tarefa: CEX-010 (Fase 5).
- Docs: https://www.gate.com/docs/developers/apiv4/en/
- CCXT: id `gate`.
- Conexões estimadas: 2–3 WebSockets (§5).
- Implementação: `gateio/adapter.py` (`GateioAdapter`, herda de
  `ccxt_adapter.CCXTAdapter`). Somente endpoints públicos de mercado,
  sem nenhuma chave de API e sem envio de ordens.
- Testes: `tests/connectors/test_gateio.py` (fakes do CCXT, sem
  rede real; inclui funding rate e OI ausente).
- Smoke ao vivo: `docs/smoke-phase5.md` — ticker BTC/USDT OK em
  2026-11-13 (last 69025.7).

## Futuros / perpétuos

A Gate.io tem perpétuos USDT com funding rate, lido no mercado swap
com o símbolo canônico `BASE/QUOTE:USDT` (ex.: `BTC/USDT:USDT`),
via CCXT unificado.

## Rate limits públicos (CEX-012 / GOV-002)

Fonte: docs Gate API v4 — "Frequency limit rule" (tabela oficial).

| Recurso | Limite público |
|---|---|
| Endpoints públicos de spot | **900 req/s por IP** (order book, candles, pares etc.) |
| Endpoints privados (não usados) | 900 req/s por API key |
| Colocar ordens (não usado) | 10 req/s por UID + par |
| WebSocket | ≤ 300 conexões por IP; msgs enviadas sem limite declarado |

O CCXT impõe `rateLimit` de 50 ms entre chamadas. O token bucket
local é **20 req/s, burst 20** — ritmo do CCXT, bem abaixo do
teto oficial de 900 req/s.

## Restrições regionais

- A Gate.io não atende EUA, Canadá e jurisdições sancionadas,
  entre outras (lista oficial). Presença no catálogo não garante
  disponibilidade regional de todos os produtos (§3).

## Cobertura

| Dado | Status |
|---|---|
| Mercados spot | ✅ |
| Mercados swap (perpétuos USDT) | ✅ (`market_type = "perp"`) |
| Ticker, trades, OHLCV, order book | ✅ |
| Funding rate | ✅ (`fetch_funding_rate`) |
| Open interest | ❌ a API pública tem o campo nos contratos futuros, mas o CCXT 4.x não implementa `fetchOpenInterest` para Gate (`has.fetchOpenInterest = False`) |

O OI levanta `ExchangeError` (`BAD_RESPONSE`, não retryable) com
mensagem clara — o dado nunca é inventado. Suporte nativo ao OI
(chamada direta ao endpoint de contratos futuros) é trabalho
futuro, não desta fase.

## Timeframes (CCXT)

`10s, 1m, 5m, 15m, 30m, 1h, 2h, 4h, 8h, 1d, 7d, 1w`. O `10s`
não está na lista da especificação (§3) e é rejeitado por
`validate_timeframe`; `1w` e `7d` coexistem no CCXT.

## Limitações conhecidas

- Sem WebSocket em tempo real nesta fase (REST com polling);
  streaming de trades/book fica para a Fase 7.
- Latência por método e gaps de candles são expostos em `health()`.
