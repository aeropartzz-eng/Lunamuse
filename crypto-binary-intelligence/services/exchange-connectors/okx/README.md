# OKX — Fase 4 (CEX-003) ✅

- Tarefa: CEX-003 — instrumentos, trades e books.
- Adapter: `okx/adapter.py` (`OkxAdapter`, sobre
  `ccxt_adapter.CCXTAdapter`, id CCXT `okx`, API v5).
- Docs: https://www.okx.com/docs-v5/en/
- Conexões estimadas: 2–4 WebSockets (§5) — WS chega na Fase 7;
  esta fase é REST.
- Somente endpoints públicos de mercado, sem nenhuma chave de API
  e sem envio de ordens. Execução continua bloqueada (403).

## Mercados

- Spot (`BTC/USDT`) e swaps/futuros (`BTC/USDT:USDT`), via símbolo
  unificado do CCXT. O formato nativo da OKX é `BTC-USDT` (com
  hífen); a conversão é feita pelo CCXT e o canônico do projeto
  continua `BASE/QUOTE`.
- Funding rate e open interest só existem para contratos: pedir
  para `BTC/USDT` lê o swap `BTC/USDT:USDT`.
- Candles (intervalos v5): 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h,
  12h, 1d, 1w — **sem 1s/5s/15s/30s nem 8h** (a API não os serve;
  `validate_timeframe` aceita, o conector rejeita com
  `BAD_RESPONSE`).

## Rate limits (CEX-012)

Publicados pela OKX (API v5, por endpoint, por IP, em janelas de 2 s;
erro 50011 ao exceder):

| Endpoint público | Limite |
|---|---|
| Tickers | 20 req/2 s |
| Order book e candles | 40 req/2 s |
| Trades | 100 req/2 s |
| History candles / history trades | 20 req/2 s |
| Funding rate e funding history | 10 req/2 s (por IP + instrumento) |
| Open interest | 20 req/2 s (por IP + instrumento) |

Os limites não escalam com chave (são por IP) e o acordo da API
proíbe contorná-los. O token bucket local do conector é **5 req/s,
rajada 10** — igual ao endpoint público mais restrito (10/2 s). O
CCXT ainda aplica `enableRateLimit` (`rateLimit` nativo de 110 ms).

## Restrições regionais (GOV-002)

- **OKX não atende EUA** (a OKX US é operação separada, ex-OKCoin)
  nem outras jurisdições restritas; verificar a elegibilidade
  antes de operar em produção.
- A OKX não tem host REST separado de testnet: demo trading usa o
  mesmo host de produção com chave demo e o header
  `x-simulated-trading: 1` — fora do escopo desta fase (só market
  data público, sem chave).
- A presença no catálogo não garante disponibilidade regional de
  todos os produtos (§3).

## Limitações conhecidas

- Sem WebSocket em tempo real nesta fase (REST com polling);
  streaming de trades/book fica para a Fase 7 (Market Data Engine).
  O canal público é `wss://ws.okx.com:8443/ws/v5/public`.
- `fetch_trades`/`fetch_ohlcv` paginam acima de 1000 itens
  (`since_ms` opcional, dedup por id/`open_time_ms`).
- Latência por método e gaps de candles são expostos em `health()`.
