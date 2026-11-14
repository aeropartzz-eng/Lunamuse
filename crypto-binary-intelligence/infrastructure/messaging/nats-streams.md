# NATS JetStream — streams e subjects (Fase 2 — DB-004)

Fonte: especificação v4.1, §§2, 5, 9, 10, 16. Configuração canônica em
[`nats-streams.yaml`](nats-streams.yaml) (validar com `python -c "import yaml;
yaml.safe_load(open('nats-streams.yaml'))"`). Este documento explica o
desenho; o YAML é o que se aplica na VPS.

## Fluxo

Fonte → Conector → Normalizador → NATS → Market Data → Indicadores →
Padrões/Order Flow → Estratégia → Probabilidade → Risk Engine →
Signal Engine → Notificações → (se autorizado) Execução → Reconciliação.

## Streams

| Stream | Subjects | Retenção | max_age | Uso |
|---|---|---|---|---|
| `MARKET` | `market.trades.>`, `market.candles.>`, `market.orderbook.>`, `market.tickers.>`, `market.funding.>`, `market.open_interest.>`, `market.liquidations.>`, `market.onchain.>` | limits, discard old | 7 dias (168h) | Barramento de dados de mercado; histórico canônico é o TimescaleDB |
| `SIGNALS` | `signals.new.>`, `signals.approved.>`, `signals.published.>`, `signals.closed.>`, `signals.invalidated.>`, `signals.expired.>`, `predictions.>` | limits, discard old | 90 dias (2160h) | Ciclo de vida do sinal (§9); registro canônico em `strategy_signals` |
| `EXECUTION` | `execution.orders.>`, `execution.fills.>`, `execution.positions.>`, `execution.reconciliation.>`, `risk.events.>`, `risk.kill_switch.>` | limits, discard old | 90 dias (2160h) | Ordens/fills/risco (§10); registro canônico no Postgres |
| `SYSTEM` | `system.heartbeat.>`, `system.health.>`, `system.connection.>`, `system.alerts.>`, `system.events.>` | limits, discard old | 30 dias (720h) | Heartbeats e alertas (§§5, 16); auditoria canônica em `audit_logs` |

- **Réplicas: 1** — VPS única (§11). Subir para 3 quando houver cluster NATS.
- **Storage: file** em todos os streams (volume `natsdata` no compose).
- **Duplicate window: 2 min** em todos os streams — deduplicação de
  republicação pelo produtor (NATS descarta `Nats-Msg-Id` repetido).
- **Ack: explícito** no consumidor (padrão em `consumer_defaults` no YAML):
  confirma só depois de persistir/processar; sem ack, reentrega.
  `ack_wait: 30s`, `max_deliver: 5` — depois disso, dead-letter
  (subject `*.dlq` do mesmo stream, a criar por serviço).
- **Deliver policy:** `all` para replay no boot (recuperar o que perdeu
  durante a queda); `new` para consumo contínuo.

## Convenção de subjects

`market.<tipo>.<exchange>.<symbol>` — ex.: `market.trades.binance.BTCUSDT`,
`market.candles.bybit.ETHUSDT.1m`, `market.orderbook.okx.BTC-USDT-SWAP`.
`signals.<estágio>.<strategy_code>.<symbol>` — ex.:
`signals.approved.STR-001.BTCUSDT`. `execution.orders.<mode>.<exchange>` —
ex.: `execution.orders.PAPER.binance`. `risk.kill_switch` não leva
parâmetro: qualquer publicação nele bloqueia novas entradas (§10).

## O que NUNCA passa pelo NATS

Chaves de API, segredos, tokens de Telegram/WhatsApp, senhas. Payloads
levam apenas dados de mercado, sinais e eventos. Credenciais vivem no
`.env`/cofre e são lidas direto pelo serviço que precisa delas.

## Aplicar na VPS

```bash
# depois de: docker compose up -d nats
docker exec cbi-nats nats stream add --config infrastructure/messaging/nats-streams.yaml
# conferir:
docker exec cbi-nats nats stream ls
docker exec cbi-nats nats stream info MARKET
```

Sem o CLI `nats` no container, criar cada stream com
`nats stream add MARKET --subjects "market.>" --retention limits
--max-age 168h --storage file --replicas 1` (idem para os demais,
com os subjects e `max-age` da tabela acima).
