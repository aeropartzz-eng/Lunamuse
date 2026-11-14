# Coinbase Advanced — Fase 5 (CEX-007) ✅

- Tarefa: CEX-007 (Fase 5).
- Docs: https://docs.cdp.coinbase.com/advanced-trade/docs/welcome
- CCXT: id `coinbase` = **Coinbase Advanced Trade** (API em
  `api.coinbase.com`), não o Coinbase comum. O CCXT 4.x unificou o
  Advanced Trade no id `coinbase` (o antigo `coinbasepro` foi
  removido).
- Conexões estimadas: 1–2 WebSockets (§5).
- Implementação: `coinbase/adapter.py` (`CoinbaseAdapter`, herda de
  `ccxt_adapter.CCXTAdapter`). Somente endpoints públicos de mercado,
  sem nenhuma chave de API e sem envio de ordens.
- Testes: `tests/connectors/test_coinbase.py` (fakes do CCXT, sem
  rede real).
- Smoke ao vivo: `docs/smoke-phase5.md` — ticker BTC/USDT OK em
  2026-11-13 (last 69050.89).

## Rate limits públicos (CEX-012 / GOV-002)

Fontes: docs CDP — "Advanced Trade WebSocket Rate Limits"
(atualizado 2026-11-10) e "Exchange Rate Limits Overview"; valores
confirmados por várias fontes secundárias em 2026-11-13.

| Recurso | Limite público |
|---|---|
| REST pública | **10 req/s por IP** (rajadas até 15/s) |
| REST privada (não usada) | 30 req/s por usuário |
| WebSocket — conexões | 8 por segundo por IP (750/s segundo outra página oficial — divergência documentada; usar 8/s) |
| WebSocket — msgs não autenticadas | 8 por segundo por IP |

Excesso retorna HTTP 429. O token bucket local é **10 req/s,
burst 15** (`rate_per_sec`/`rate_burst` no adapter).

## Restrições regionais

- Perpétuos do Advanced Trade (ex.: BTC-PERP) só existem fora dos
  EUA; o conector não assume que existam.
- A Coinbase não atende todas as jurisdições (ex.: residentes de
  Nova York dependem de BitLicense; países sancionados fora).
  Presença no catálogo não garante disponibilidade regional de
  todos os produtos (§3) — verificar elegibilidade antes de
  operar em produção.

## Cobertura

| Dado | Status |
|---|---|
| Mercados spot | ✅ (`fetch_markets`) |
| Ticker, trades, OHLCV, order book | ✅ |
| Funding rate | ❌ sem endpoint público/CCXT (`has.fetchFundingRate = False`) |
| Open interest | ❌ sem endpoint público/CCXT (`has.fetchOpenInterest = False`) |

Funding/OI levantam `ExchangeError` (`BAD_RESPONSE`, não retryable)
com mensagem clara — o dado nunca é inventado.

## Timeframes (CCXT)

`1m, 5m, 15m, 30m, 1h, 2h, 6h, 1d` — sem `3m/4h/8h/12h/1w`
(`fetch_ohlcv` com um deles levanta `ExchangeError`).
Máx. **350 candles** por chamada de OHLCV (limite da API).

## Limitações conhecidas

- Sem WebSocket em tempo real nesta fase (REST com polling);
  streaming de trades/book fica para a Fase 7.
- Latência por método e gaps de candles são expostos em `health()`.
