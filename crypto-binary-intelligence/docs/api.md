# API — Crypto & Binary Intelligence

> Resumo da especificação **v4.1, §13**. Estado atual: **esqueleto** —
> `GET /health`, `GET /v1/exchanges` e `GET /v1/system/health` existem
> como stubs; as demais rotas retornam HTTP 501; as rotas de execução
> retornam HTTP 403 (LIVE desabilitado).

## Base

- Base URL: `http://localhost:8000` (desenvolvimento).
- Versão: `/v1`.
- Docs interativas: `/docs` (Swagger) e `/redoc`.
- Formato: JSON. Autenticação forte e autorização por função entram
  com a implementação das rotas (Fases 7–15).

## Endpoints

### Sistema

| Método | Rota | Estado | Descrição |
|---|---|---|---|
| GET | `/health` | implementado (scaffold) | Health check do serviço |
| GET | `/` | implementado (scaffold) | Identificação do serviço |
| GET | `/v1/system/health` | stub | Saúde agregada (banco, Redis, NATS, conectores) |

### Exchanges

| Método | Rota | Estado | Descrição |
|---|---|---|---|
| GET | `/v1/exchanges` | stub | Catálogo do primeiro grupo de CEX |
| GET | `/v1/exchanges/status` | stub | Status de conexão por exchange |

### Mercado

| Método | Rota | Estado |
|---|---|---|
| GET | `/v1/instruments` | stub (501) |
| GET | `/v1/markets` | stub (501) |
| GET | `/v1/market/{symbol}/trades` | stub (501) |
| GET | `/v1/market/{symbol}/candles` | stub (501) |
| GET | `/v1/market/{symbol}/orderbook` | stub (501) |

### Inteligência

| Método | Rota | Estado |
|---|---|---|
| GET | `/v1/indicators/{symbol}` | stub (501) |
| GET | `/v1/patterns/{symbol}` | stub (501) |
| GET | `/v1/opportunities` | stub (501) |

### Estratégias e sinais

| Método | Rota | Estado |
|---|---|---|
| GET | `/v1/strategies` | stub (501) |
| POST | `/v1/strategies` | stub (501) |
| PATCH | `/v1/strategies/{id}` | stub (501) |
| GET | `/v1/signals` | stub (501) |
| GET | `/v1/signals/{id}` | stub (501) |

### Execução — BLOQUEADA (§10)

| Método | Rota | Estado |
|---|---|---|
| POST | `/v1/execution/preview` | **403 — bloqueada** |
| POST | `/v1/execution/orders` | **403 — bloqueada** |
| POST | `/v1/execution/cancel` | **403 — bloqueada** |
| GET | `/v1/execution/positions` | stub (501) |
| POST | `/v1/execution/kill-switch` | stub (estado armado, sem posições reais) |
| GET | `/v1/portfolio` | stub (501) |

### Webhook

| Método | Rota | Estado |
|---|---|---|
| POST | `/v1/webhooks/tradingview` | stub (501) — fonte complementar; validação e enfileiramento na Fase 14 |

## WebSockets (Fase 14)

- `/ws/market` — trades, candles, order book
- `/ws/signals` — sinais publicados
- `/ws/opportunities` — oportunidades de arbitragem/divergência
- `/ws/execution` — ordens e fills
- `/ws/portfolio` — posições e exposição
- `/ws/system` — saúde do sistema

## Segurança (§13)

- Autenticação forte, autorização por função, rate limiting, TLS.
- Segredos fora do código e dos logs.
- Validação de payload, idempotência e proteção contra replay.
- Auditoria administrativa; endpoint de execução protegido.
- API keys de exchange **sem saque** e com restrição de IP quando
  disponível.

## Banco de dados (§13)

Tabelas principais (ver `infrastructure/database/001_init.sql` e
migrações futuras):

- **Cadastro:** exchanges, exchange_products, markets, instruments,
  networks, tokens, pools.
- **Mercado:** market_trades, market_candles, orderbook_snapshots,
  orderbook_events, market_tickers, funding_rates, open_interest,
  liquidations, onchain_events.
- **Inteligência:** market_indicators, market_patterns, market_regimes,
  market_features, strategies, strategy_versions, strategy_signals,
  strategy_results, model_versions, model_predictions.
- **Execução:** exchange_accounts, execution_orders, execution_fills,
  positions, portfolio_snapshots, risk_events, reconciliation_events.
- **Operação:** users, roles, permissions, notifications,
  notification_deliveries, system_events, audit_logs,
  connection_status.
