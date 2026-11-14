# Arquitetura — Crypto & Binary Intelligence

> Resumo das decisões da especificação **v4.1 (13/11/2026), §2, §4, §5, §11**.
> Documento-base: `~/workspace/user/files/crypto_binary_intelligence_contexto_cronograma_v4_1_4_3ruc.txt`.

## Visão

Central própria de inteligência de mercado cripto, 24/7, conectada às
principais exchanges e fontes descentralizadas: recebe dados, reconstrói
gráficos, calcula indicadores, reconhece padrões, analisa fluxo e
liquidez, testa estratégias, estima probabilidades, distribui sinais e,
após homologação, pode executar ordens autorizadas.

## As sete camadas

| Camada | Responsabilidade | Serviços |
|---|---|---|
| 1. Fontes | CEX, DEX, RPC/WS de blockchains, dados on-chain, TradingView (webhook, complementar) | `services/exchange-connectors/*`, `services/dex-connectors/*` |
| 2. Ingestão | Conectores REST/WS/RPC, gerenciador de conexões, rate limiting, reconexão, validação de timestamps, normalização | `services/exchange-connectors/base.py` (contrato `ExchangeAdapter`) |
| 3. Market Data | Normalizador de trades, Candle Builder, agregador de volume, Order Book Manager, spread, sincronização, gaps | `services/market-data/`, `services/candle-builder/` |
| 4. Inteligência | Indicadores, padrões, Price Action, estrutura, Order Flow, regime, cross-exchange, Crypto Shield, estratégias, probabilidade | `services/indicators/`, `patterns/`, `order-flow/`, `market-regime/`, `cross-exchange/`, `crypto-shield/`, `strategies/`, `probability/` |
| 5. Risco e Execução | Risk Engine, position sizing, pre-trade validation, Execution Engine, Order/Portfolio Manager, reconciliação, circuit breaker, kill switch | `services/risk/`, `execution/`, `portfolio/` |
| 6. Distribuição | Telegram Bot, WhatsApp Business oficial, painel web, WebSockets, API externa | `apps/notifier/`, `apps/dashboard/` |
| 7. Armazenamento e observabilidade | PostgreSQL + TimescaleDB, Redis, NATS JetStream, Object Storage, Prometheus, Grafana, auditoria | `docker-compose.yml`, `infrastructure/` |

## Fluxo

```
Fonte -> Conector -> Normalizador -> NATS -> Market Data -> Indicadores
-> Padrões/Order Flow -> Estratégia -> Probabilidade -> Risk Engine
-> Signal Engine -> Notificações -> (se autorizado) Execution Engine
-> Reconciliação -> Resultado e auditoria
```

**A IA generativa não está no caminho crítico de execução.** As regras
determinísticas de risco continuam funcionando sem APIs externas.

## Monitoramento hierárquico (§4)

Não assinar todos os canais de todos os ativos. Três níveis dinâmicos,
com promoção e despromoção automáticas:

| Nível | O que assina | Meta inicial |
|---|---|---|
| 1 — Discovery | Catálogo, ticker, preço/variação, volume, candles de referência, liquidez estimada, novos pares | até ~2.000 pares candidatos |
| 2 — Active | Trades, candles de alta resolução, indicadores, padrões, volatilidade, volume relativo | até ~200 instrumentos |
| 3 — Priority | Trades detalhados, Order Book, Bid/Ask, CVD, imbalance, absorção, liquidity sweep | até ~50 ativos intensivos; até 20 com Order Book aprofundado |

Os números são metas de dimensionamento, não limites das corretoras.

## Conexões e resiliência (§5)

- Planejamento: **25–35 conexões WebSocket persistentes** (Binance 3–5,
  Bybit 4–6, OKX 2–4, Coinbase 1–2, Kraken 1–2, Bitget 2–3, Gate.io 2–3,
  DEX/RPC 3–5).
- Heartbeat, reconexão exponencial com jitter, renovação programada,
  recuperação de assinaturas, rate limiting, deduplicação,
  sequenciamento, snapshot e sincronização de Order Book, detecção de
  gaps, métrica de latência, circuit breaker por fonte, bloqueio de
  sinais com feed inválido.
- **Uma conexão aberta não significa conexão saudável.** Medir idade da
  última mensagem, sequência, atraso e integridade.

## Infraestrutura de referência (§11)

- VPS Linux: **4 vCPU · 8 GB RAM · SSD ~320 GB · Ubuntu Server LTS**,
  Docker Engine + Docker Compose.
- Custo de planejamento: **~US$ 84/mês** (VPS) + **~US$ 3/mês** (Object
  Storage 100 GB). Confirmar antes de contratar — não é cotação.
- Sem GPU; sem LLM grande local. Modelos quantitativos leves e APIs
  externas apenas para tarefas não críticas.
- MVP começa com PostgreSQL/TimescaleDB, Redis, NATS, API e conectores.
  ClickHouse e servidores adicionais entram quando a carga justificar.

### Orçamento de RAM inicial (~8 GB)

| Componente | MB |
|---|---|
| Sistema/Docker | 800 |
| PostgreSQL/TimescaleDB | 1.500 |
| Redis | 250 |
| NATS | 250 |
| Conectores | 1.300 |
| Market Data/candles | 900 |
| Indicadores/estratégias | 800 |
| API/painel/notificações | 600 |
| Monitoramento | 350 |
| Reserva | 1.250 |

### Retenção (§11)

| Dado | Retenção |
|---|---|
| Trades brutos prioritários | 7 dias |
| Order Book bruto | 2–7 dias |
| Candles 1s | 30 dias |
| Candles 1m / 5m | 24 meses |
| Timeframes maiores | 3 anos ou mais |
| Sinais, ordens e auditoria | permanente (conforme política) |

Não guardar todos os ticks e books indefinidamente na VPS de 320 GB —
agregação e arquivamento externo são necessários.

## Serviços Docker (§11)

O `docker-compose.yml` deste scaffold sobe os serviços centrais:
`postgres-timescale`, `redis`, `nats`, `api`, `dashboard`,
`prometheus`, `grafana`. Os demais serviços do documento (`caddy`,
`api-gateway`, `websocket-gateway`, `cex-connectors`, `dex-connectors`,
`market-normalizer`, `candle-builder`, `market-scanner`,
`indicator-engine`, `pattern-engine`, `orderflow-engine`,
`regime-engine`, `strategy-engine`, `probability-engine`,
`risk-engine`, `execution-engine`, `order-manager`,
`portfolio-manager`, `notification-worker`, `backup-worker`) entram
quando forem implementados. Não é obrigatório iniciar todos
simultaneamente.
