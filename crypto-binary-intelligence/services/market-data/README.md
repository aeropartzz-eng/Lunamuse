# Market Data — Fase 7 ✅

- **Camada:** Camada 3
- **Fase:** Fase 7 — DAT-001…DAT-010 (especificação v4.1, §2, §5, §11)

Pipeline de trades, deduplicação, validação cronológica, detecção de
gaps, Order Book Manager, persistência e retenção.

## O que foi implementado (`market_data.py`)

| Componente | Tarefas | Conteúdo |
|---|---|---|
| `parse_trade_message` | DAT-001 | Traduz mensagens nativas de trades (Binance, Bybit, OKX) para `models.Trade`. Acks/pongs retornam `[]`. |
| `TradePipeline` | DAT-001/002/005/006 | Ingestão + dedup por `(exchange, symbol, trade_id)` (ou `(ts, preço, qty)` quando a fonte não dá id) via `ConnectionManager`; rejeita trades fora de ordem; assinantes recebem os trades aceitos (é assim que o Candle Builder se pluga). |
| `OrderBookManager` | DAT-007/008 | Snapshot + deltas sequenciados; gap de sequência marca divergência e exige resync (delta fora de ordem **não** é aplicado); livro cruzado também diverge; spread, mid-price, profundidade e imbalance. |
| `MarketDataSource` | — | **Protocolo consumido pela Fase 8**: `get_ticker(symbol)`, `get_candles(symbol, timeframe, limit)`, `get_trades(symbol, limit)`, `get_order_book(symbol, depth)`. Implementações: `RestMarketDataSource` (REST via `ExchangeAdapter`) e `InMemoryMarketDataSource` (memória, testes/dev). |
| `PostgresMarketDataRepository` | DAT-009 | Persistência contra `infrastructure/database/002_market.sql` (`market_trades`, `market_candles`, `orderbook_snapshots`, `orderbook_events`, `market_tickers`), com `INSERT ... ON CONFLICT DO NOTHING` (replays idempotentes). A conexão é injetada — nunca há DSN/credencial no código. `InMemoryMarketDataRepository` é o fake dos testes. |
| `RetentionPolicy` | DAT-010 | Retenção §11 como código: trades/book 7 dias, tickers 30 dias, candles 1s 30 dias, 1m/5m 24 meses, demais TF 3 anos. Gera o SQL (TimescaleDB `add_retention_policy`, `DELETE` de expurgo, `SELECT` de arquivamento) — **não executa nada aqui**. |
| `LiveTradeFeed` | DAT-001 | Cliente WebSocket público (`websockets`) para Binance/Bybit/OKX, com reconexão (backoff via `ConnectionManager`) e re-subscribe. Sem chave de API. |

## Como plugar o repositório real na VPS

1. Aplicar as migrações `infrastructure/database/001_init.sql` e
   `002_market.sql` no PostgreSQL/TimescaleDB.
2. Criar a conexão com as credenciais do `.env` (`DATABASE_URL`) e
   instanciar `PostgresMarketDataRepository(conn)`.
3. Ligar o pipeline ao repositório: `pipeline.subscribe(repo.save_trades)`
   (via adaptador que agrupa trades em lotes) e o builder a
   `repo.save_candles(candles, source="builder")`.
4. Retenção: só ativar `add_retention_policy` / expurgo **depois** de
   confirmar o arquivamento externo (object storage) — ver
   `RetentionPolicy` e os comentários de `002_market.sql`.

## Como plugar o Candle Builder

```python
from candle_builder import CandleBuilder
builder = CandleBuilder("binance", "BTC/USDT", ["1m", "5m"])
pipeline.subscribe(lambda t: builder.add_trade(t))
```

## Smoke ao vivo

`scripts/smoke_phase7.py` — uma conexão WebSocket pública curta
(trades BTC/USDT da Binance) + fallback REST. Relatório em
`data/reports/fase7-smoke-YYYY-MM-DD.md`.

## Regras preservadas

- Somente dados públicos; nenhuma chave de API; nenhum envio de ordem.
- Timeframes só os 17 reais da fonte (§3) — ver `candle_builder.py`.
- Gaps nunca são preenchidos com dado inventado; candles só existem
  com trades reais.
- Execução continua bloqueada (403); o scaffold força RESEARCH quando
  `EXECUTION_MODE=LIVE`.

## Testes

`tests/market-data/` — parsers, dedup, cronologia, book (snapshot +
sequência + divergência), repositório com fake, protocolo e feed ao
vivo com websocket fake. Sem rede nos testes.
