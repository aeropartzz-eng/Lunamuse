# Kraken — Fase 5 (CEX-008) ✅

- Tarefa: CEX-008 (Fase 5).
- Docs: https://docs.kraken.com/api/
- CCXT: id `kraken`.
- Conexões estimadas: 1–2 WebSockets (§5).
- Implementação: `kraken/adapter.py` (`KrakenAdapter`, herda de
  `ccxt_adapter.CCXTAdapter`). Somente endpoints públicos de mercado,
  sem nenhuma chave de API e sem envio de ordens.
- Testes: `tests/connectors/test_kraken.py` (fakes do CCXT, sem
  rede real; inclui os alias de símbolos).
- Smoke ao vivo: `docs/smoke-phase5.md` — ticker BTC/USDT OK em
  2026-11-13 (last 69037.1).

## Alias de símbolos

O Kraken usa códigos próprios: **`XBT` para BTC e `XDG` para
DOGE** (pares nativos como `XXBTZUSD`). A tabela vive em
`normalization.py` (`ASSET_ALIASES["kraken"]`) e é aplicada em
todos os métodos: `XBT/USD`, `XBTUSD` e `xbt-usd` viram o canônico
`BTC/USD`. Na volta, `denormalize_symbol("BTC/USD", "kraken")`
devolve `XBTUSD`.

## Rate limits públicos (CEX-012 / GOV-002)

Fontes: docs Kraken — "Spot REST Rate Limits" e "What are the API
rate limits?" (atualizados 2026-11-12 e 2026-10-01).

| Recurso | Limite público |
|---|---|
| Endpoints públicos | **sem custo** no contador da API (não consomem o budget privado) |
| Orientação oficial | **≤ 1 chamada/s por IP** fica dentro do limite; acima disso pode haver bloqueio por alguns segundos |
| Trades / OHLC | limitados por IP **+ par** |
| Contador privado (não usado) | Starter 15 / Intermediate e Pro 20, com decaimento 0,33–1/s |

Excesso retorna `EAPI:Rate limit exceeded`. O token bucket local é
**1 req/s, burst 3** (`rate_per_sec`/`rate_burst` no adapter) —
conservador, seguindo a orientação oficial.

## Restrições regionais

- O Kraken não atende residentes de Nova York e Washington (EUA)
  nem jurisdições sancionadas; saiu do Japão em 2023. Presença no
  catálogo não garante disponibilidade regional de todos os
  produtos (§3).

## Cobertura

| Dado | Status |
|---|---|
| Mercados spot | ✅ (`fetch_markets`, com alias XBT/XDG) |
| Ticker, trades, OHLCV, order book | ✅ |
| Funding rate | ❌ sem funding no Spot (`has.fetchFundingRate = False`) |
| Open interest | ❌ sem OI no Spot via CCXT (o OI de futuros vive na API Kraken Futures, fora deste conector) |

Funding/OI levantam `ExchangeError` (`BAD_RESPONSE`, não retryable)
com mensagem clara — o dado nunca é inventado.

## Timeframes (CCXT)

`1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 2w` — sem `3m/8h/12h`.

## Limitações conhecidas

- Sem WebSocket em tempo real nesta fase (REST com polling);
  streaming de trades/book fica para a Fase 7.
- Latência por método e gaps de candles são expostos em `health()`.
