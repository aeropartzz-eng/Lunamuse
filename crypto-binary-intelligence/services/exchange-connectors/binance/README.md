# Binance — Fase 4 (CEX-001) ✅

- Tarefa: CEX-001 — mercados, trades, ticker, candles e book.
- Adapter: `binance/adapter.py` (`BinanceAdapter`, sobre
  `ccxt_adapter.CCXTAdapter`, id CCXT `binance`).
- Docs: https://developers.binance.com/docs/binance-spot-api-docs
- Docs WS: https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams
- Conexões estimadas: 3–5 WebSockets (§5) — WS chega na Fase 7;
  esta fase é REST.
- Somente endpoints públicos de mercado, sem nenhuma chave de API
  e sem envio de ordens. Execução continua bloqueada (403).

## Mercados

- Spot (`BTC/USDT`) e USDⓈ-M futuros/perpétuos
  (`BTC/USDT:USDT`), via símbolo unificado do CCXT.
- Funding rate e open interest só existem para contratos: pedir
  para `BTC/USDT` lê o perpétuo `BTC/USDT:USDT`.
- Candles: 1s, 5s, 15s, 30s, 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h,
  8h, 12h, 1d, 1w (todos os timeframes da especificação §3).

## Rate limits (CEX-012)

Publicados pela Binance (spot `exchangeInfo`, verificados nas docs):

| Limite | Valor |
|---|---|
| Peso por IP | 6.000/min (spot); 2.400/min (futuros USDⓈ-M) |
| Requisições brutas por IP | 300.000/5 min |
| Peso por endpoint | klines 2 (≤500) / 5 (≤1000); order book 5–250 conforme a profundidade; ticker 2 |
| Ao exceder | HTTP 429 com `Retry-After`; insistir após 429 vira HTTP 418 (banimento de IP de 2 min a 3 dias) |

O token bucket local do conector é **10 req/s, rajada 20** — bem
abaixo do teto publicado. O CCXT ainda aplica `enableRateLimit`
(`rateLimit` nativo de 50 ms).

## Restrições regionais (GOV-002)

- **Binance.com não atende residentes dos EUA** — usam a
  Binance.US, que é outra exchange com API própria
  (`api.binance.us`); este conector usa `api.binance.com`.
- Jurisdições proibidas/restritas publicadas pela Binance incluem
  EUA, Canadá, Países Baixos, Cuba, Coreia do Norte, Irã, Síria e
  Crimeia/áreas não controladas da Ucrânia (lista de 27/02/2024;
  verificar a lista atual antes de operar em produção).
- Derivativos (futuros/perpétuos) são restritos em várias
  jurisdições (ex.: varejo no Reino Unido). A presença no catálogo
  não garante disponibilidade regional de todos os produtos (§3).
- Dados públicos de mercado também podem ser lidos em
  `data-api.binance.vision` (host só de market data, sem chave).

## Limitações conhecidas

- Sem WebSocket em tempo real nesta fase (REST com polling);
  streaming de trades/book fica para a Fase 7 (Market Data Engine).
- `fetch_trades`/`fetch_ohlcv` paginam acima de 1000 itens
  (`since_ms` opcional, dedup por id/`open_time_ms`).
- Latência por método e gaps de candles são expostos em `health()`.
