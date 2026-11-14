# Bitget — Fase 5 (CEX-009) ✅

- Tarefa: CEX-009 (Fase 5).
- Docs: https://www.bitget.com/api-doc/common/intro
- CCXT: id `bitget`.
- Conexões estimadas: 2–3 WebSockets (§5).
- Implementação: `bitget/adapter.py` (`BitgetAdapter`, herda de
  `ccxt_adapter.CCXTAdapter`). Somente endpoints públicos de mercado,
  sem nenhuma chave de API e sem envio de ordens.
- Testes: `tests/connectors/test_bitget.py` (fakes do CCXT, sem
  rede real; inclui funding rate e open interest).
- Smoke ao vivo: `docs/smoke-phase5.md` — ticker BTC/USDT OK em
  2026-11-13 (last 69023.51).

## Futuros / perpétuos

A Bitget tem perpétuos USDT com funding rate e open interest. Ambos
são lidos no mercado swap com o símbolo canônico `BASE/QUOTE:USDT`
(ex.: `BTC/USDT:USDT`), via CCXT unificado. `fetch_funding_rate`
e `fetch_open_interest` aceitam `BTC/USDT` ou `BTC/USDT:USDT` e
sempre devolvem o símbolo swap.

## Rate limits públicos (CEX-012 / GOV-002)

Fontes: docs Bitget — Quick Start e Order Management (verificadas
2026-11-09); compilação verificada em 2026-10-29.

| Recurso | Limite público |
|---|---|
| Geral (domínio comum) | **6.000 req/min por IP** — REST e WebSocket compartilham a cota |
| Market data | **20 req/s por IP** (tickers 20/s) |
| Ordens (não usadas) | 10/s por UID; batch 5/s (máx. 20 ordens) |
| WebSocket | 300 conexões / 5 min por IP; máx. 100 conexões por IP; 240 subscrições/hora por conexão; 10 msgs/s por conexão |

Excesso retorna HTTP 429 (erro 50011); o header
`x-mbx-used-remain-limit` mostra a cota restante do endpoint.
O token bucket local é **20 req/s, burst 20**.

## Restrições regionais

- A Bitget não atende EUA, Reino Unido, Canadá, Singapura e
  jurisdições sancionadas, entre outras (lista oficial). Presença
  no catálogo não garante disponibilidade regional de todos os
  produtos (§3).
- A conta Classic está em modo de manutenção; a API atual é a
  UTA v3 — o CCXT 4.x já usa os endpoints v3 para market data.

## Cobertura

| Dado | Status |
|---|---|
| Mercados spot | ✅ |
| Mercados swap (perpétuos USDT) | ✅ (`market_type = "perp"`) |
| Ticker, trades, OHLCV, order book | ✅ |
| Funding rate | ✅ (`fetch_funding_rate`) |
| Open interest | ✅ (`fetch_open_interest`) |

## Timeframes (CCXT)

`1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 3d, 1w, 1M`.

## Limitações conhecidas

- Sem WebSocket em tempo real nesta fase (REST com polling);
  streaming de trades/book fica para a Fase 7.
- Latência por método e gaps de candles são expostos em `health()`.
