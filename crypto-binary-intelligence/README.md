# Crypto & Binary Intelligence

> **ESQUELETO / SCAFFOLD do MVP — não é um sistema funcional.**
> Este repositório contém a estrutura, os contratos e os stubs definidos na
> especificação **v4.1 (13/11/2026)**. Nenhum conector está implementado,
> nenhum dado de mercado é lido, nenhum sinal é gerado e **nenhuma ordem é
> executada**. O desenvolvimento segue o cronograma de 16 semanas da
> especificação, fase por fase, com evidência de aceite em cada tarefa.

Central própria de inteligência de mercado cripto (spot, perpetuals,
futuros, opções, arbitragem, DEX/DeFi e meme coins), funcionando 24/7:
conecta-se às principais exchanges, reconstrói candles, calcula
indicadores, reconhece padrões, analisa fluxo e liquidez, testa
estratégias, estima probabilidades, distribui sinais e — somente após
homologação — pode executar ordens autorizadas.

**Opções binárias ficam em módulo separado, de pesquisa e validação.**
Execução real nesse segmento só poderá ser considerada após validação
jurídica da plataforma, da API, da origem do preço e das regras de
liquidação (Fase 15 e semana 22 da expansão).

---

## Travas de segurança (não negociáveis)

| Trava | Regra |
|---|---|
| **LIVE desabilitado por padrão** | O sistema **nunca muda sozinho para LIVE**. Modos: RESEARCH → BACKTEST → PAPER → TESTNET → LIVE. LIVE exige aprovação técnica, estatística, operacional e regulatória + autorização expressa do responsável (EXE-014). O scaffold só aceita `EXECUTION_MODE=RESEARCH` e a API rejeita qualquer pedido de ordem com HTTP 403. |
| **Chaves de API sem saque** | Toda chave de exchange é criada **sem permissão de saque**, com restrição de IP quando disponível, e guardada fora do código e dos logs. |
| **Binárias só pesquisa** | O motor de binárias é isolado do motor cripto. Sem validação jurídica completa, só pesquisa e simulação — execução bloqueada. |
| **Meta de 85% é objetivo de pesquisa** | Não é promessa de acerto, lucro ou rentabilidade. Vale para sinais seletivos, sempre acompanhada de cobertura, intervalo de confiança de 95%, expectativa líquida, custos e desempenho fora da amostra (mín. 1.000 resultados fora da amostra em binárias; mín. 500 operações fora da amostra por estratégia em scalping cripto; Profit Factor de referência > 1,3; Sharpe de referência > 1,5; drawdown de referência < 10%). |
| **WAIT / NO TRADE** | Com dados ruins, probabilidade não calibrada ou expectativa insuficiente, a decisão correta é **não operar**. |
| **Risco** | Risco por operação 0,25% do patrimônio; limite diário de perda 1%; alavancagem desabilitada; até 3 posições simultâneas; feed inválido bloqueia novas entradas. Limites provisórios de engenharia, não recomendação financeira. |

---

## Arquitetura

Sete camadas (detalhes em [`docs/architecture.md`](docs/architecture.md)):

```
1. FONTES          CEX (Binance, Bybit, OKX, Coinbase, Kraken, Bitget,
                   Gate.io) · DEX (DEX Screener, PancakeSwap, Raydium,
                   Uniswap, Jupiter) · RPC (BNB, Solana, Ethereum, Base) ·
                   TradingView (webhook, complementar)
2. INGESTÃO       Conectores REST/WS/RPC · rate limiting · reconexão ·
                   validação de timestamps · normalização
3. MARKET DATA    Normalizador · Candle Builder · Order Book Manager ·
                   spread · detecção de gaps e latência
4. INTELIGÊNCIA   Indicadores · Padrões · Price Action · Estrutura ·
                   Order Flow · Regime · Cross-Exchange · Crypto Shield ·
                   Estratégias · Probabilidade
5. RISCO/EXECUÇÃO Risk Engine · Position Sizing · Pre-trade Validation ·
                   Execution Engine · Order Manager · Portfolio ·
                   Reconciliação · Circuit Breaker · Kill Switch
6. DISTRIBUIÇÃO   Telegram Bot · WhatsApp Business oficial · Painel web ·
                   WebSockets · API externa
7. ARMAZENAMENTO  PostgreSQL + TimescaleDB · Redis · NATS JetStream ·
  E OBSERVABILIDADE  Object Storage · Prometheus · Grafana · auditoria
```

Fluxo: Fonte → Conector → Normalizador → NATS → Market Data →
Indicadores → Padrões/Order Flow → Estratégia → Probabilidade →
Risk Engine → Signal Engine → Notificações → (se autorizado) Execution
Engine → Reconciliação → Resultado e auditoria.

A IA generativa **não está no caminho crítico de execução**: as regras
determinísticas de risco funcionam sem APIs externas.

### Monitoramento hierárquico (§4)

Não assinar tudo de todo mundo. Três níveis dinâmicos:

- **Discovery** — até ~2.000 pares candidatos (ticker, volume, liquidez).
- **Active** — até ~200 instrumentos (trades, candles, indicadores).
- **Priority** — até ~50 ativos intensivos, até 20 com Order Book
  aprofundado (CVD, imbalance, absorção, liquidity sweep).

### Infraestrutura de referência (§11)

VPS Linux econômica: **4 vCPU · 8 GB RAM · SSD ~320 GB · Ubuntu LTS**,
Docker + Docker Compose. Estimativa de planejamento: **~US$ 84/mês** de
VPS + **~US$ 3/mês** de Object Storage (100 GB) — valores a confirmar
antes de contratar; não são cotação garantida. Sem GPU; sem LLM grande
local. Orçamento de RAM inicial: ~8 GB (detalhado em
`docs/architecture.md`).

---

## Plano de 16 semanas (resumo)

| Fase | Semana(s) | Entrega |
|---|---|---|
| **0 — Governança** | 1 | Requisitos, cobertura, políticas de dados/risco/execução, protocolo de 85%, revisão regulatória |
| **1 — VPS e infra** | 1–2 | VPS segura, HTTPS, Docker, repositório, ambientes, backup com restauração testada |
| **2 — Banco e mensageria** | 2 | PostgreSQL/TimescaleDB, Redis, NATS JetStream, migrações, auditoria |
| **3 — Contrato universal** | 3 | `ExchangeAdapter`, modelos, normalização, gerenciador de conexões, testes de desconexão |
| **4 — CEX prioritárias** | 4 | Binance, Bybit, OKX conectadas e monitoradas |
| **5 — Expansão CEX** | 5 | Coinbase, Kraken, Bitget, Gate.io + avaliação de KuCoin, MEXC, BingX, Bitfinex, HTX, Crypto.com |
| **6 — DEX e Crypto Shield** | 6 | DEX Screener, RPCs, PancakeSwap, Raydium, Uniswap/Jupiter; holder intelligence; estados APROVADO/REVISÃO/BLOQUEADO |
| **7 — Market Data Engine** | 7 | Pipeline de trades, Candle Builder, Order Book, gaps, persistência |
| **8 — Scanner e cross-exchange** | 8 | Scanners Discovery/Active/Priority, comparação de preços, arbitragem simulada |
| **9 — Indicator Engine** | 9 | SMA/EMA, RSI/MACD, ADX, ATR/Bollinger, VWAP/OBV/MFI, divergências — sem look-ahead |
| **10 — Pattern e Order Flow** | 10 | Padrões de velas, estrutura (BOS/CHoCH), CVD, imbalance, absorção, liquidity sweep |
| **11 — Regime e Strategy Lab** | 11 | Detecção de regime, framework de estratégias (STR-001…STR-016) |
| **12 — Backtesting** | 12 | vectorbt/Backtrader, custos, Walk-Forward, Purged CV, relatório fora da amostra |
| **13 — Machine Learning** | 13 | Feature Store, XGBoost/LightGBM, calibração, Brier/Log Loss, relatório de 85% |
| **14 — Signal Engine e notificações** | 14 | Ciclo de vida do sinal, Telegram, WhatsApp oficial, painel, WebSockets |
| **15 — Execution e Testnet** | 15–16 | Interface universal, testnets, Order/Position Manager, Risk Engine, Kill Switch, Paper Trading, Shadow Mode. **LIVE continua bloqueado.** |

**Expansão (semanas 17–28):** derivativos, opções, simulação DEX,
arbitragem, Order Flow avançado, verificação do feed binário, resiliência,
carga e 4 semanas de paper trading global.

Critério de aceite (§17): uma fase só é concluída **com evidência**
(logs, testes, relatórios, prints ou resultados automatizados). Código
escrito não é, sozinho, critério de aceite.

---

## Como rodar o esqueleto

Pré-requisitos: Docker Engine + Docker Compose v2.

```bash
# 1. Copiar e preencher as variáveis (senhas obrigatórias: POSTGRES_PASSWORD,
#    REDIS_PASSWORD, GRAFANA_ADMIN_PASSWORD). Sem elas os serviços não sobem.
cp .env.example .env

# 2. Validar a composição (não sobe nada)
docker compose config

# 3. Subir os serviços centrais (banco, cache, mensageria, API, painel,
#    Prometheus, Grafana)
docker compose up -d

# 4. Verificar o health da API
curl http://localhost:8000/health
# {"status":"ok","service":"crypto-binary-intelligence","version":"0.1.0-scaffold","execution_mode":"RESEARCH","live_enabled":false}

# 5. Ver o painel placeholder
open http://localhost:3000

# 6. Ver logs e parar
docker compose logs -f api
docker compose down
```

Portas (todas ligadas a `127.0.0.1` por padrão): API `8000` · painel
`3000` · Prometheus `9090` · Grafana `3001` · PostgreSQL `5432` ·
Redis `6379` · NATS `4222`/`8222`.

---

## Estrutura

```
crypto-binary-intelligence/
├── apps/
│   ├── api/            # FastAPI — health + stubs /v1/* (sem execução real)
│   ├── dashboard/      # Painel web — página placeholder (Fase 14)
│   └── notifier/       # Telegram/WhatsApp — stub (Fase 14)
├── services/
│   ├── exchange-connectors/   # binance, bybit, okx, coinbase, kraken, bitget, gateio
│   ├── dex-connectors/        # dexscreener, pancakeswap, raydium, uniswap, jupiter
│   ├── market-data/ candle-builder/ indicators/ patterns/ order-flow/
│   ├── market-regime/ cross-exchange/ crypto-shield/ strategies/
│   ├── probability/ backtesting/ risk/ execution/ portfolio/ notifications/
├── skills/             # price-action, candlestick, ict-smc, wyckoff,
│                       # scalping, binary-options, order-flow, risk-management
├── data/               # historical, features, models, reports
├── infrastructure/
│   ├── docker/         # prometheus.yml
│   ├── monitoring/     # datasources do Grafana
│   ├── database/       # 001_init.sql (extensões + tabelas-base)
│   ├── deployment/     # notas de deploy na VPS
│   └── backup/         # script de backup (placeholder)
├── tests/              # connectors, market-data, indicators, strategies,
│                       # backtesting, execution, security
├── docs/               # architecture, api, exchanges, signals, risk-policy, operations
├── .env.example
├── docker-compose.yml
└── README.md
```

## Documentação

- [`docs/architecture.md`](docs/architecture.md) — camadas, fluxo, RAM, retenção
- [`docs/api.md`](docs/api.md) — endpoints, websockets, segurança
- [`docs/exchanges.md`](docs/exchanges.md) — CEX, DEX, dados e timeframes
- [`docs/signals.md`](docs/signals.md) — ciclo de vida e campos do sinal
- [`docs/risk-policy.md`](docs/risk-policy.md) — limites, controles, kill switch
- [`docs/operations.md`](docs/operations.md) — operação, métricas, alertas, backup

Documento-base: `~/workspace/user/files/crypto_binary_intelligence_contexto_cronograma_v4_1_4_3ruc.txt`
(especificação v4.1, consolidada em 13/11/2026).
