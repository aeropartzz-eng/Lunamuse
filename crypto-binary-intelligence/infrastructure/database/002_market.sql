-- =============================================================================
-- Crypto & Binary Intelligence — 002_market.sql (Fase 2 — DB-002/DB-005)
-- =============================================================================
-- Tabelas de mercado (§13 "Mercado"). Todas as tabelas de série temporal
-- são hypertables TimescaleDB. Idempotente: pode ser reaplicada; CREATE
-- TABLE/INDEX usam IF NOT EXISTS e create_hypertable usa if_not_exists.
--
-- Retenção (§11): trades brutos 7 dias; order book bruto 2–7 dias;
-- candles 1s 30 dias; candles 1m/5m 24 meses; TF maiores 3+ anos.
-- As políticas de retenção estão COMENTADAS abaixo: só ativar depois de
-- confirmar o arquivamento externo (object storage), para não apagar
-- dados sem destino. Sinais, ordens e auditoria têm retenção permanente.
--
-- Convenção: `time` é o timestamp do evento na origem (normalizado, §5);
-- `received_at` é quando o sistema recebeu. Nunca inventar granularidade
-- (§3): sem trades individuais, não há candles de 1s.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- market_trades — trades individuais normalizados (§3, §7 DAT-001).
-- Hypertable, chunk de 1 dia. Retenção: 7 dias (bruto prioritário).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_trades (
    time            TIMESTAMPTZ NOT NULL,
    exchange        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    trade_id        TEXT NOT NULL,
    side            TEXT CHECK (side IN ('buy', 'sell')),
    price           NUMERIC(38, 18) NOT NULL,
    quantity        NUMERIC(38, 18) NOT NULL,
    quote_quantity  NUMERIC(38, 18),
    is_buyer_maker  BOOLEAN,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw             JSONB,
    PRIMARY KEY (time, exchange, symbol, trade_id)
);
SELECT create_hypertable('market_trades', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time   ON market_trades (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_exchange_sym  ON market_trades (exchange, symbol, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('market_trades', INTERVAL '7 days');

-- ---------------------------------------------------------------------------
-- market_candles — OHLCV por timeframe (§3: 1s, 5s, 15s, 30s, 1m, 3m, 5m,
-- 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, diário, semanal).
-- `source`: 'exchange' (candle da própria exchange) ou 'builder' (candle
-- próprio construído a partir de trades, §7 DAT-003).
-- Hypertable, chunk de 7 dias. Retenção: 1s 30 dias; 1m/5m 24 meses;
-- TF maiores 3+ anos (políticas por timeframe exigem tabelas ou
-- particionamento por timeframe — ver nota no README.md).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_candles (
    time          TIMESTAMPTZ NOT NULL,
    exchange      TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    timeframe     TEXT NOT NULL,
    open          NUMERIC(38, 18) NOT NULL,
    high          NUMERIC(38, 18) NOT NULL,
    low           NUMERIC(38, 18) NOT NULL,
    close         NUMERIC(38, 18) NOT NULL,
    volume        NUMERIC(38, 18) NOT NULL DEFAULT 0,
    quote_volume  NUMERIC(38, 18),
    trades_count  INTEGER,
    source        TEXT NOT NULL DEFAULT 'exchange' CHECK (source IN ('exchange', 'builder')),
    is_closed     BOOLEAN NOT NULL DEFAULT FALSE,
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol, timeframe)
);
SELECT create_hypertable('market_candles', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_time ON market_candles (symbol, timeframe, time DESC);
CREATE INDEX IF NOT EXISTS idx_candles_exchange_sym   ON market_candles (exchange, symbol, timeframe, time DESC);
-- Retenção (ativar após arquivamento externo; por timeframe, ver README.md):
-- SELECT add_retention_policy('market_candles', INTERVAL '3 years');

-- ---------------------------------------------------------------------------
-- orderbook_snapshots — snapshot completo do livro (§5, §7 DAT-007/008).
-- `bids`/`asks`: arrays JSON [[preço, quantidade], ...], profundidade
-- limitada ao nível contratado (Nível 3: até 20 livros aprofundados).
-- Hypertable, chunk de 1 dia. Retenção: 2–7 dias.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    time       TIMESTAMPTZ NOT NULL,
    exchange   TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    bids       JSONB NOT NULL,
    asks       JSONB NOT NULL,
    best_bid   NUMERIC(38, 18),
    best_ask   NUMERIC(38, 18),
    spread     NUMERIC(38, 18),
    mid_price  NUMERIC(38, 18),
    sequence   BIGINT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol)
);
SELECT create_hypertable('orderbook_snapshots', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');
CREATE INDEX IF NOT EXISTS idx_ob_snap_symbol_time ON orderbook_snapshots (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_ob_snap_exch_sym    ON orderbook_snapshots (exchange, symbol, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('orderbook_snapshots', INTERVAL '7 days');

-- ---------------------------------------------------------------------------
-- orderbook_events — eventos incrementais do livro (updates/deltas).
-- Hypertable, chunk de 1 dia. Retenção: 2–7 dias.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orderbook_events (
    time       TIMESTAMPTZ NOT NULL,
    exchange   TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('snapshot', 'update', 'delete')),
    side       TEXT CHECK (side IN ('bid', 'ask')),
    price      NUMERIC(38, 18),
    quantity   NUMERIC(38, 18),
    sequence   BIGINT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol, sequence)
);
SELECT create_hypertable('orderbook_events', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');
CREATE INDEX IF NOT EXISTS idx_ob_events_symbol_time ON orderbook_events (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_ob_events_exch_sym    ON orderbook_events (exchange, symbol, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('orderbook_events', INTERVAL '7 days');

-- ---------------------------------------------------------------------------
-- market_tickers — último preço / ticker 24h (§3).
-- Hypertable, chunk de 1 dia. Retenção: 30 dias (o ticker corrente vive
-- no Redis; aqui fica o histórico curto para o painel e o scanner).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_tickers (
    time                TIMESTAMPTZ NOT NULL,
    exchange            TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    last_price          NUMERIC(38, 18),
    bid                 NUMERIC(38, 18),
    ask                 NUMERIC(38, 18),
    volume_24h          NUMERIC(38, 18),
    quote_volume_24h    NUMERIC(38, 18),
    price_change_pct_24h NUMERIC(10, 4),
    high_24h            NUMERIC(38, 18),
    low_24h             NUMERIC(38, 18),
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol)
);
SELECT create_hypertable('market_tickers', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '1 day');
CREATE INDEX IF NOT EXISTS idx_tickers_symbol_time ON market_tickers (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_tickers_exch_sym    ON market_tickers (exchange, symbol, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('market_tickers', INTERVAL '30 days');

-- ---------------------------------------------------------------------------
-- funding_rates — funding de perpetuals + mark/index price (§3, semana 17).
-- Hypertable, chunk de 7 dias. Retenção: 24 meses.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS funding_rates (
    time              TIMESTAMPTZ NOT NULL,
    exchange          TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    funding_rate      NUMERIC(18, 10),
    mark_price        NUMERIC(38, 18),
    index_price       NUMERIC(38, 18),
    next_funding_time TIMESTAMPTZ,
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol)
);
SELECT create_hypertable('funding_rates', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_funding_symbol_time ON funding_rates (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_funding_exch_sym    ON funding_rates (exchange, symbol, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('funding_rates', INTERVAL '24 months');

-- ---------------------------------------------------------------------------
-- open_interest — open interest de derivativos (§3, semana 17).
-- Hypertable, chunk de 7 dias. Retenção: 24 meses.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS open_interest (
    time              TIMESTAMPTZ NOT NULL,
    exchange          TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    open_interest     NUMERIC(38, 18),
    open_interest_usd NUMERIC(38, 2),
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol)
);
SELECT create_hypertable('open_interest', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_oi_symbol_time ON open_interest (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_oi_exch_sym    ON open_interest (exchange, symbol, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('open_interest', INTERVAL '24 months');

-- ---------------------------------------------------------------------------
-- liquidations — liquidações de derivativos, quando disponíveis (§3).
-- Hypertable, chunk de 7 dias. Retenção: 24 meses.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS liquidations (
    time            TIMESTAMPTZ NOT NULL,
    exchange        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    order_id        TEXT NOT NULL,
    side            TEXT CHECK (side IN ('buy', 'sell')),
    price           NUMERIC(38, 18),
    quantity        NUMERIC(38, 18),
    quote_quantity  NUMERIC(38, 18),
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol, order_id)
);
SELECT create_hypertable('liquidations', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_liq_symbol_time ON liquidations (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_liq_exch_sym    ON liquidations (exchange, symbol, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('liquidations', INTERVAL '24 months');

-- ---------------------------------------------------------------------------
-- onchain_events — eventos de pools/swaps/transferências (§3, Fase 6).
-- Fonte: RPC/WebSocket ou indexador (DEX Screener é triagem, não feed
-- de eventos em tempo real). Hypertable, chunk de 7 dias.
-- Retenção: 24 meses (eventos de fraude/Shield precisam de histórico).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS onchain_events (
    time            TIMESTAMPTZ NOT NULL,
    network_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL CHECK (event_type IN ('swap', 'pool_created', 'transfer', 'liquidity_add', 'liquidity_remove', 'mint', 'burn', 'holder_move')),
    tx_hash         TEXT NOT NULL,
    token_address   TEXT,
    pool_address    TEXT,
    wallet_address  TEXT,
    amount          NUMERIC(38, 18),
    amount_usd      NUMERIC(38, 2),
    raw             JSONB,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, network_id, event_type, tx_hash)
);
SELECT create_hypertable('onchain_events', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_onchain_token_time  ON onchain_events (token_address, time DESC);
CREATE INDEX IF NOT EXISTS idx_onchain_wallet_time ON onchain_events (wallet_address, time DESC);
CREATE INDEX IF NOT EXISTS idx_onchain_network     ON onchain_events (network_id, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('onchain_events', INTERVAL '24 months');
