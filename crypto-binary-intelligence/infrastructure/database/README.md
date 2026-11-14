# Banco de dados — migrações (Fase 2 — DB-001/DB-002/DB-005/DB-006)

Especificação v4.1, §§11 e 13. Stack: PostgreSQL 16 + TimescaleDB
(imagem `timescale/timescaledb:latest-pg16`, serviço `postgres-timescale`
no `docker-compose.yml`). Banco e usuário vêm do `.env`
(`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` — sem senha literal
em nenhum arquivo deste repositório).

## Ordem de aplicação

Aplicar **nesta ordem** (cada arquivo depende do anterior):

| # | Arquivo | Conteúdo | Tarefas |
|---|---|---|---|
| 1 | `001_init.sql` | Extensões (`timescaledb`, `pgcrypto`); catálogo (`exchanges` + seed das 7 CEX do primeiro grupo, `exchange_products`, `markets`, `instruments`, `networks` + seed das 4 redes, `tokens`, `pools`); operação (`system_events`, `audit_logs`, `connection_status`) | DB-001, DB-002, DB-005 |
| 2 | `002_market.sql` | Mercado: `market_trades`, `market_candles`, `orderbook_snapshots`, `orderbook_events`, `market_tickers`, `funding_rates`, `open_interest`, `liquidations`, `onchain_events` — todas hypertables | DB-002, DB-005 |
| 3 | `003_intelligence.sql` | Inteligência: `market_indicators`, `market_patterns`, `market_regimes`, `market_features`, `strategies`, `strategy_versions`, `strategy_signals`, `strategy_results`, `model_versions`, `model_predictions` | DB-005 |
| 4 | `004_execution.sql` | Execução: `exchange_accounts`, `execution_orders`, `execution_fills`, `positions`, `portfolio_snapshots`, `risk_events`, `reconciliation_events` | DB-005 |
| 5 | `005_operations.sql` | Operação: `users`, `roles`, `permissions`, `role_permissions`, `user_roles`, `notifications`, `notification_deliveries`, `schema_migrations` + seeds de papéis/permissões | DB-005, DB-006 |

Não há `000_catalog.sql`: o catálogo que faltava no 001
(`exchange_products`, `markets`, `instruments`, `networks`, `tokens`,
`pools`) foi completado **dentro do próprio 001**, porque um arquivo
`000_` rodaria antes do 001 no `docker-entrypoint-initdb.d` e quebraria
as chaves estrangeiras para `exchanges`. `system_events`, `audit_logs` e
`connection_status` já existiam no 001 e **não** foram duplicados no 005.

## Como aplicar

### Primeira subida (volume novo — automático)

```bash
cp .env.example .env   # preencher POSTGRES_PASSWORD, REDIS_PASSWORD, GRAFANA_ADMIN_PASSWORD
docker compose up -d postgres-timescale
```

O compose monta `./infrastructure/database` em
`/docker-entrypoint-initdb.d` (somente leitura): na **primeira** criação
do volume `pgdata`, o Postgres executa `001`–`005` em ordem alfabética.
Em subidas posteriores os arquivos **não** rodam de novo — é o
comportamento do entrypoint, não um bug.

### Aplicação manual / migração posterior (na VPS)

```bash
# dentro da VPS, na raiz do projeto, com o .env preenchido:
export PGPASSWORD="$POSTGRES_PASSWORD"
for f in infrastructure/database/00*.sql; do
  echo "== $f"; psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f "$f"
done
psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT * FROM schema_migrations ORDER BY version;"
```

Ou dentro do container:

```bash
docker exec -i cbi-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 < infrastructure/database/002_market.sql
```

Todas as migrações são idempotentes (`CREATE TABLE/INDEX IF NOT EXISTS`,
`create_hypertable(..., if_not_exists => TRUE)`, seeds com
`ON CONFLICT DO NOTHING`): reaplicar não duplica tabelas nem seeds.
**Exceção:** `create_hypertable` numa tabela que já tem dados fora do
chunk esperado falha — nesse caso, aplicar com a tabela vazia ou migrar
os dados antes.

### Verificação após aplicar

```bash
docker exec cbi-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT hypertable_name FROM timescaledb_information.hypertables ORDER BY 1;"
# esperado: market_trades, market_candles, orderbook_snapshots,
# orderbook_events, market_tickers, funding_rates, open_interest,
# liquidations, onchain_events, market_indicators, market_patterns,
# market_regimes, market_features, strategy_signals, model_predictions,
# execution_fills, portfolio_snapshots (17 hypertables)
docker exec cbi-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"
```

## Hypertables e chunks

| Tabela | Chunk | Motivo |
|---|---|---|
| `market_trades`, `orderbook_snapshots`, `orderbook_events`, `market_tickers` | 1 dia | Alto volume; chunks curtos para drop rápido por retenção |
| `market_candles`, `funding_rates`, `open_interest`, `liquidations`, `onchain_events`, `market_indicators`, `market_patterns`, `market_regimes`, `market_features`, `model_predictions`, `strategy_signals` | 7 dias | Volume médio; equilíbrio entre nº de chunks e manutenção |
| `execution_fills`, `portfolio_snapshots` | 30 dias | Baixo volume; retenção permanente |

Chave primária das hypertables **inclui sempre a coluna de partição**
(`time` ou `created_at`) — exigência do TimescaleDB. Índices úteis em
todas as tabelas de série: `(symbol, time DESC)` e
`(exchange, symbol, time DESC)`.

## Retenção (§11)

As políticas de retenção estão **comentadas** nas migrações
(`add_retention_policy`) e só devem ser ativadas depois de confirmar o
arquivamento externo (object storage, INF-008), para não apagar dados
sem destino:

| Dados | Retenção |
|---|---|
| Trades brutos prioritários | 7 dias |
| Order book bruto | 2–7 dias |
| Candles 1s | 30 dias |
| Candles 1m / 5m | 24 meses |
| Timeframes maiores | 3+ anos |
| Indicadores, padrões, regimes, features, predições | 24 meses |
| Funding, OI, liquidações, on-chain | 24 meses |
| **Sinais, ordens, fills, posições, snapshots, risco, reconciliação, auditoria** | **permanente (sem política)** |

Nota: `add_retention_policy` aplica-se à tabela inteira — retenção
diferente por timeframe de candle (1s 30 dias vs. 1m 24 meses vs. 1h
3+ anos) exige ou tabelas separadas por timeframe, ou um job de
arquivamento/expurgo por `timeframe` (Fase 7, DAT-010). Não inventar
granularidade: sem trades individuais, não há candle de 1s (§3).

## Trilha de auditoria (DB-006)

- **`audit_logs`** (001): ator, ação, alvo, detalhes (JSONB) e timestamp
  de toda ação administrativa e de execução. Escrita pelos serviços
  (API/execution); nunca editada ou apagada por rotina de retenção.
- **`system_events`** (001): eventos operacionais por componente/nível.
- **`schema_migrations`** (005): versão e data de cada migração aplicada.
- **`risk_events`** e **`reconciliation_events`** (004): eventos de risco
  e divergências de reconciliação, com `resolved` e ação tomada.
- **`notification_deliveries`** (005): entregas e falhas por canal.
- Regra: auditoria não tem `DELETE` em rotina nenhuma; expurgo, se um
  dia existir, exige aprovação expressa do responsável e registro no
  próprio `audit_logs`.

## O que NÃO está aqui (pendente de outras fases)

- Seeds de estratégias (STR-001..016, BIN-001..016) — Fase 11 (STR-001..010).
- Usuário admin inicial — criado pelo responsável na VPS (ver 005).
- Políticas de retenção ativas — após arquivamento externo (Fase 7, DAT-010).
- Backup/restore — Fase 1, INF-008 (`infrastructure/backup/`).
