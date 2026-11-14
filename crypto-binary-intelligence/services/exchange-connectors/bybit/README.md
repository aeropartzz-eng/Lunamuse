# Bybit — Fase 4 (CEX-002) ✅

- Tarefa: CEX-002 — Spot e contratos suportados.
- Adapter: `bybit/adapter.py` (`BybitAdapter`, sobre
  `ccxt_adapter.CCXTAdapter`, id CCXT `bybit`, API v5).
- Docs: https://bybit-exchange.github.io/docs/v5/intro
- Conexões estimadas: 4–6 WebSockets (§5) — WS chega na Fase 7;
  esta fase é REST.
- Somente endpoints públicos de mercado, sem nenhuma chave de API
  e sem envio de ordens. Execução continua bloqueada (403).

## Mercados

- Spot (`BTC/USDT`) e contratos lineares/inversos
  (`BTC/USDT:USDT`), via símbolo unificado do CCXT.
- Funding rate e open interest só existem para contratos: pedir
  para `BTC/USDT` lê o perpétuo `BTC/USDT:USDT`.
- O CCXT obtém o funding rate de forma "emulada" (a partir do
  ticker do contrato); o valor é o publicado pela Bybit, não um
  cálculo local.
- Candles (intervalos v5): 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h,
  12h, 1d, 1w — **sem 1s/5s/15s/30s nem 8h** (a API não os serve;
  `validate_timeframe` aceita, o conector rejeita com
  `BAD_RESPONSE`).

## Rate limits (CEX-012)

Publicados pela Bybit (Rate Limit Rules, API v5):

| Limite | Valor |
|---|---|
| Camada IP | 600 req/5 s por IP (todos os endpoints) |
| Ao exceder (IP) | HTTP 403 "access too frequent" + bloqueio de ~10 min (fechar as sessões e aguardar) |
| Camada UID | por endpoint/segundo, só para trading (ex.: criar ordem 20/s spot, 10/s perpétuo USDT) — não se aplica a market data público |
| WebSocket | até 500 conexões/5 min; até 1.000 conexões de market data por IP |

O token bucket local do conector é **10 req/s, rajada 20** — bem
abaixo do teto da camada IP. O CCXT ainda aplica `enableRateLimit`
(`rateLimit` nativo de 20 ms).

## Restrições regionais (GOV-002)

- **IPs dos EUA e da China continental são rejeitados** (403) pela
  Bybit, conforme o guia de integração oficial.
- Contas registradas em sites regionais (Turquia, Cazaquistão,
  Geórgia, Emirados Árabes, EEE, Indonésia, Japão, Hong Kong) usam
  domínios de API próprios (`api.bytick.com` etc.); este conector
  usa `api.bybit.com` (conta internacional).
- Derivativos são restritos em várias jurisdições (ex.: Reino
  Unido). A presença no catálogo não garante disponibilidade
  regional de todos os produtos (§3).

## Limitações conhecidas

- Sem WebSocket em tempo real nesta fase (REST com polling);
  streaming de trades/book fica para a Fase 7 (Market Data Engine).
- `fetch_trades`/`fetch_ohlcv` paginam acima de 1000 itens
  (`since_ms` opcional, dedup por id/`open_time_ms`).
- Latência por método e gaps de candles são expostos em `health()`.
