-- =============================================================================
-- Crypto & Binary Intelligence — 001_init.sql (Fase 2 — DB-001/DB-002/DB-005)
-- =============================================================================
-- Roda uma vez, na primeira subida do postgres-timescale.
-- Cria as extensões e as tabelas-base do catálogo e da operação.
-- As hypertables de trades/candles (TimescaleDB) e as demais tabelas da
-- especificação (§13) entram em migrações posteriores.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Cadastro (§13)
CREATE TABLE IF NOT EXISTS exchanges (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    group_name  TEXT NOT NULL DEFAULT 'priority',
    status      TEXT NOT NULL DEFAULT 'scaffold',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO exchanges (id, name) VALUES
    ('binance',  'Binance'),
    ('bybit',    'Bybit'),
    ('okx',      'OKX'),
    ('coinbase', 'Coinbase Advanced'),
    ('kraken',   'Kraken'),
    ('bitget',   'Bitget'),
    ('gateio',   'Gate.io')
ON CONFLICT (id) DO NOTHING;

-- Operação / auditoria (§13)
CREATE TABLE IF NOT EXISTS system_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    level       TEXT NOT NULL DEFAULT 'info',
    component   TEXT NOT NULL,
    message     TEXT NOT NULL,
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT,
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Estado de conexões (§5, §13 — connection_status)
CREATE TABLE IF NOT EXISTS connection_status (
    source_id        TEXT PRIMARY KEY,
    connected        BOOLEAN NOT NULL DEFAULT FALSE,
    last_message_at  TIMESTAMPTZ,
    latency_ms       DOUBLE PRECISION,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- Cadastro — restante do §13 (adicionado na Fase 2, DB-005).
-- `exchanges` já existe acima; as tabelas abaixo dependem dela e por isso
-- ficam neste mesmo arquivo, em vez de um 000_catalog.sql (que rodaria
-- antes do 001 no docker-entrypoint-initdb.d e quebraria as FKs).
-- =============================================================================

-- Produtos oferecidos por cada exchange (spot, perpetual, futures, options).
CREATE TABLE IF NOT EXISTS exchange_products (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_id  TEXT NOT NULL REFERENCES exchanges (id) ON DELETE CASCADE,
    product_type TEXT NOT NULL CHECK (product_type IN ('spot', 'perpetual', 'futures', 'options')),
    symbol       TEXT NOT NULL,
    base_asset   TEXT,
    quote_asset  TEXT,
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'delisted')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (exchange_id, symbol, product_type)
);
CREATE INDEX IF NOT EXISTS idx_exchange_products_exchange ON exchange_products (exchange_id);
CREATE INDEX IF NOT EXISTS idx_exchange_products_symbol  ON exchange_products (symbol);

-- Mercados negociáveis (par/contrato em uma exchange).
CREATE TABLE IF NOT EXISTS markets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_id  TEXT NOT NULL REFERENCES exchanges (id) ON DELETE CASCADE,
    symbol       TEXT NOT NULL,
    market_type  TEXT NOT NULL CHECK (market_type IN ('spot', 'perpetual', 'futures', 'options', 'dex')),
    base_asset   TEXT,
    quote_asset  TEXT,
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'delisted')),
    min_qty      NUMERIC(38, 18),
    tick_size    NUMERIC(38, 18),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (exchange_id, symbol, market_type)
);
CREATE INDEX IF NOT EXISTS idx_markets_exchange ON markets (exchange_id);
CREATE INDEX IF NOT EXISTS idx_markets_symbol   ON markets (symbol);

-- Instrumentos (contratos de futuros/opções dentro de um mercado).
CREATE TABLE IF NOT EXISTS instruments (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id      UUID NOT NULL REFERENCES markets (id) ON DELETE CASCADE,
    symbol         TEXT NOT NULL,
    instrument_type TEXT NOT NULL CHECK (instrument_type IN ('spot', 'perpetual', 'futures', 'options', 'binary')),
    underlying     TEXT,
    expiry         TIMESTAMPTZ,
    strike         NUMERIC(38, 18),
    contract_size  NUMERIC(38, 18),
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'expired', 'delisted')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (market_id, symbol)
);
CREATE INDEX IF NOT EXISTS idx_instruments_market ON instruments (market_id);

-- Redes blockchain (BNB Chain, Solana, Ethereum, Base — §3).
CREATE TABLE IF NOT EXISTS networks (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    chain_id         BIGINT,
    native_currency  TEXT,
    explorer_url     TEXT,
    status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO networks (id, name, chain_id, native_currency) VALUES
    ('bsc',      'BNB Chain', 56,    'BNB'),
    ('solana',   'Solana',    NULL,  'SOL'),
    ('ethereum', 'Ethereum',  1,     'ETH'),
    ('base',     'Base',      8453,  'ETH')
ON CONFLICT (id) DO NOTHING;

-- Tokens on-chain (contratos verificados; risco avaliado pelo Crypto Shield, §7).
CREATE TABLE IF NOT EXISTS tokens (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    network_id       TEXT NOT NULL REFERENCES networks (id) ON DELETE CASCADE,
    contract_address TEXT NOT NULL,
    symbol           TEXT,
    name             TEXT,
    decimals         SMALLINT,
    total_supply     NUMERIC(38, 18),
    shield_status    TEXT NOT NULL DEFAULT 'pending' CHECK (shield_status IN ('pending', 'approved', 'review', 'blocked')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (network_id, contract_address)
);
CREATE INDEX IF NOT EXISTS idx_tokens_network ON tokens (network_id);
CREATE INDEX IF NOT EXISTS idx_tokens_symbol  ON tokens (symbol);

-- Pools de liquidez DEX (PancakeSwap, Raydium, Uniswap — §3).
CREATE TABLE IF NOT EXISTS pools (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    network_id    TEXT NOT NULL REFERENCES networks (id) ON DELETE CASCADE,
    dex           TEXT NOT NULL,
    token_a_id    UUID REFERENCES tokens (id) ON DELETE SET NULL,
    token_b_id    UUID REFERENCES tokens (id) ON DELETE SET NULL,
    pool_address  TEXT NOT NULL,
    fee_tier      NUMERIC(10, 6),
    liquidity_usd NUMERIC(38, 2),
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (network_id, pool_address)
);
CREATE INDEX IF NOT EXISTS idx_pools_network ON pools (network_id);
CREATE INDEX IF NOT EXISTS idx_pools_dex     ON pools (dex);
