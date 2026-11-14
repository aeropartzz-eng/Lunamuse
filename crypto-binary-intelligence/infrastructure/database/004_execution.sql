-- =============================================================================
-- Crypto & Binary Intelligence — 004_execution.sql (Fase 2 — DB-005)
-- =============================================================================
-- Tabelas de execução (§13 "Execução"; §10 Execution Engine).
-- Idempotente: CREATE TABLE/INDEX com IF NOT EXISTS.
--
-- TRAVAS DE SEGURANÇA (§10, §17):
-- - O sistema NUNCA muda sozinho para LIVE. `execution_orders.mode` registra
--   o modo de cada ordem; LIVE só existe após homologação formal (EXE-014).
-- - `exchange_accounts` guarda APENAS uma referência à credencial
--   (nome da variável no .env / referência do cofre). SEGREDOS NUNCA vão
--   para o banco, para logs ou para o Redis. Chaves de API sem saque e com
--   restrição de IP quando disponível.
-- - `client_order_id` é UNIQUE: idempotência de ordens (§10).
-- - Alavancagem desabilitada por padrão (leverage = 0); risco por operação
--   0,25% e limite diário de perda 1% são limites de homologação (§10).
-- - Retenção: ordens, fills, posições e eventos de risco/reconciliação
--   são retenção PERMANENTE (§11) — auditoria e resultado.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- exchange_accounts — contas de exchange vinculadas ao sistema.
-- `api_key_ref`: referência (ex.: nome da variável no .env, como
-- BINANCE_API_KEY), NUNCA o valor da chave/segredo.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exchange_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_id     TEXT NOT NULL REFERENCES exchanges (id) ON DELETE CASCADE,
    label           TEXT NOT NULL,
    account_type    TEXT NOT NULL CHECK (account_type IN ('spot', 'futures', 'testnet', 'paper')),
    api_key_ref     TEXT NOT NULL,
    permissions     JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_restriction  TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_exchange_accounts_exchange ON exchange_accounts (exchange_id);

-- ---------------------------------------------------------------------------
-- execution_orders — ordens (§10: fluxo receber sinal -> validar -> enviar
-- -> confirmar -> acompanhar fills -> reconciliar -> auditar).
-- `mode`: RESEARCH | BACKTEST | PAPER | TESTNET | LIVE (LIVE bloqueado até
-- homologação). `status`: requested/accepted/rejected/filled/partially_
-- filled/cancelled/expired/failed.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS execution_orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_order_id     TEXT NOT NULL UNIQUE,
    exchange_account_id UUID REFERENCES exchange_accounts (id) ON DELETE SET NULL,
    exchange            TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    market              TEXT NOT NULL,
    side                TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type          TEXT NOT NULL CHECK (order_type IN ('market', 'limit', 'stop_limit', 'stop_market')),
    quantity            NUMERIC(38, 18) NOT NULL CHECK (quantity > 0),
    price               NUMERIC(38, 18),
    status              TEXT NOT NULL DEFAULT 'requested' CHECK (status IN ('requested', 'accepted', 'rejected', 'filled', 'partially_filled', 'cancelled', 'expired', 'failed')),
    mode                TEXT NOT NULL DEFAULT 'RESEARCH' CHECK (mode IN ('RESEARCH', 'BACKTEST', 'PAPER', 'TESTNET', 'LIVE')),
    strategy_signal_id  UUID, -- sem FK: strategy_signals é hypertable com PK (created_at, id); FK para só `id` é inválida no Postgres/TimescaleDB. Integridade garantida pela aplicação.
    filled_quantity     NUMERIC(38, 18) NOT NULL DEFAULT 0,
    avg_fill_price      NUMERIC(38, 18),
    reject_reason       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_orders_account   ON execution_orders (exchange_account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_symbol    ON execution_orders (symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_signal    ON execution_orders (strategy_signal_id);
CREATE INDEX IF NOT EXISTS idx_orders_mode_stat ON execution_orders (mode, status, created_at DESC);
-- SEM política de retenção: ordens têm retenção permanente (§11).

-- ---------------------------------------------------------------------------
-- execution_fills — fills (execuções parciais/totais) de uma ordem.
-- Hypertable em time, chunk de 30 dias. Retenção PERMANENTE (§11).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS execution_fills (
    time         TIMESTAMPTZ NOT NULL,
    order_id     UUID NOT NULL REFERENCES execution_orders (id) ON DELETE CASCADE,
    fill_id      TEXT NOT NULL,
    price        NUMERIC(38, 18) NOT NULL,
    quantity     NUMERIC(38, 18) NOT NULL,
    fee          NUMERIC(38, 18),
    fee_currency TEXT,
    liquidity    TEXT CHECK (liquidity IN ('maker', 'taker')),
    received_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, order_id, fill_id)
);
SELECT create_hypertable('execution_fills', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '30 days');
CREATE INDEX IF NOT EXISTS idx_fills_order ON execution_fills (order_id, time DESC);
-- SEM política de retenção: fills têm retenção permanente (§11).

-- ---------------------------------------------------------------------------
-- positions — posições abertas/fechadas (§10: position manager).
-- Só uma posição aberta por conta/exchange/símbolo/mercado (índice único
-- parcial). Alavancagem desabilitada por padrão (leverage = 0).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS positions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_account_id UUID REFERENCES exchange_accounts (id) ON DELETE SET NULL,
    exchange            TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    market              TEXT NOT NULL,
    side                TEXT NOT NULL CHECK (side IN ('long', 'short')),
    quantity            NUMERIC(38, 18) NOT NULL,
    entry_price         NUMERIC(38, 18),
    mark_price          NUMERIC(38, 18),
    unrealized_pnl      NUMERIC(38, 18),
    realized_pnl        NUMERIC(38, 18),
    leverage            NUMERIC(10, 4) NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    opened_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at           TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_one_open
    ON positions (exchange_account_id, exchange, symbol, market) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_positions_account ON positions (exchange_account_id, status, opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_symbol  ON positions (symbol, status, opened_at DESC);

-- ---------------------------------------------------------------------------
-- portfolio_snapshots — snapshot do portfólio por conta (§10: portfolio
-- manager). Hypertable em time, chunk de 30 dias. Retenção PERMANENTE (§11).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    time                TIMESTAMPTZ NOT NULL,
    exchange_account_id UUID NOT NULL REFERENCES exchange_accounts (id) ON DELETE CASCADE,
    total_equity_usd    NUMERIC(38, 2),
    cash_usd            NUMERIC(38, 2),
    exposure_usd        NUMERIC(38, 2),
    positions_count     INTEGER NOT NULL DEFAULT 0,
    daily_pnl_usd       NUMERIC(38, 2),
    drawdown_pct        NUMERIC(5, 4),
    PRIMARY KEY (time, exchange_account_id)
);
SELECT create_hypertable('portfolio_snapshots', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '30 days');
CREATE INDEX IF NOT EXISTS idx_portfolio_account ON portfolio_snapshots (exchange_account_id, time DESC);
-- SEM política de retenção: snapshots de portfólio têm retenção permanente (§11).

-- ---------------------------------------------------------------------------
-- risk_events — eventos do Risk Engine (§10: limite por operação/dia,
-- exposição, slippage, feed inválido, circuit breaker, kill switch).
-- `action_taken`: o que o sistema fez (ex.: 'blocked_new_entries',
-- 'kill_switch_armed', 'order_rejected').
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type          TEXT NOT NULL CHECK (event_type IN ('per_trade_risk', 'daily_loss_limit', 'exposure_limit', 'positions_limit', 'slippage_limit', 'feed_invalid', 'circuit_breaker', 'kill_switch', 'min_order_size')),
    severity            TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'critical')),
    exchange_account_id UUID REFERENCES exchange_accounts (id) ON DELETE SET NULL,
    symbol              TEXT,
    details             JSONB NOT NULL DEFAULT '{}'::jsonb,
    action_taken        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_risk_events_type    ON risk_events (event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_account ON risk_events (exchange_account_id, created_at DESC);
-- SEM política de retenção: eventos de risco têm retenção permanente (§11).

-- ---------------------------------------------------------------------------
-- reconciliation_events — reconciliação obrigatória (§10: comparar estado
-- interno com a exchange; divergência mantém o bloqueio até resolver).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reconciliation_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_account_id UUID REFERENCES exchange_accounts (id) ON DELETE SET NULL,
    event_type          TEXT NOT NULL CHECK (event_type IN ('orders', 'positions', 'balance', 'fills')),
    expected_state      JSONB NOT NULL DEFAULT '{}'::jsonb,
    actual_state        JSONB NOT NULL DEFAULT '{}'::jsonb,
    divergences         JSONB NOT NULL DEFAULT '[]'::jsonb,
    resolved            BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_recon_account  ON reconciliation_events (exchange_account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recon_unresolved ON reconciliation_events (resolved, created_at DESC) WHERE resolved = FALSE;
-- SEM política de retenção: reconciliação têm retenção permanente (§11).
