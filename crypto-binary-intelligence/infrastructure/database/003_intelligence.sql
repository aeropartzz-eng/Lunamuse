-- =============================================================================
-- Crypto & Binary Intelligence — 003_intelligence.sql (Fase 2 — DB-005)
-- =============================================================================
-- Tabelas de inteligência (§13 "Inteligência"; §§6, 8, 9).
-- Idempotente: CREATE TABLE/INDEX com IF NOT EXISTS; create_hypertable com
-- if_not_exists. Estratégias e modelos são versionados (§6: cada estratégia
-- tem ID, regras, parâmetros, versão, mercados, timeframes, filtros,
-- custos, histórico de testes e status experimental/em teste/aprovada/
-- desativada). Sinais seguem o ciclo DETECTED -> VALIDATING -> APPROVED ->
-- PUBLISHED -> ACTIVE -> CLOSED, podendo ser INVALIDATED ou EXPIRED (§9),
-- com todos os campos mínimos do §9.
-- Retenção: indicadores/padrões/regimes/features 24 meses (agregados, não
-- brutos); sinais e resultados de estratégia: retenção permanente (§11).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- market_indicators — valores de indicadores por símbolo/timeframe (§6:
-- EMA, SMA, ADX, MACD, RSI, ATR, Bollinger, VWAP, OBV, CVD etc.).
-- `indicator`: nome do indicador; `params`: parâmetros usados;
-- `value`: valor principal; `values`: demais saídas (ex.: MACD line/signal).
-- Hypertable, chunk de 7 dias.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_indicators (
    time       TIMESTAMPTZ NOT NULL,
    exchange   TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    timeframe  TEXT NOT NULL,
    indicator  TEXT NOT NULL,
    params     JSONB NOT NULL DEFAULT '{}'::jsonb,
    value      NUMERIC(38, 18),
    values     JSONB,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol, timeframe, indicator)
);
SELECT create_hypertable('market_indicators', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_indicators_symbol_tf ON market_indicators (symbol, timeframe, indicator, time DESC);
CREATE INDEX IF NOT EXISTS idx_indicators_exch_sym  ON market_indicators (exchange, symbol, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('market_indicators', INTERVAL '24 months');

-- ---------------------------------------------------------------------------
-- market_patterns — padrões de velas e Price Action detectados (§6:
-- Doji, Hammer, Engulfing, Morning/Evening Star, BOS/CHoCH, FVG etc.).
-- Um padrão isolado não gera entrada automática: `context` registra
-- tendência, volume, volatilidade e confirmação avaliados.
-- Hypertable, chunk de 7 dias.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_patterns (
    time       TIMESTAMPTZ NOT NULL,
    exchange   TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    timeframe  TEXT NOT NULL,
    pattern    TEXT NOT NULL,
    direction  TEXT CHECK (direction IN ('bullish', 'bearish', 'neutral')),
    confidence NUMERIC(5, 4) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    context    JSONB NOT NULL DEFAULT '{}'::jsonb,
    confirmed  BOOLEAN NOT NULL DEFAULT FALSE,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol, timeframe, pattern)
);
SELECT create_hypertable('market_patterns', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_patterns_symbol_tf ON market_patterns (symbol, timeframe, pattern, time DESC);
CREATE INDEX IF NOT EXISTS idx_patterns_exch_sym  ON market_patterns (exchange, symbol, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('market_patterns', INTERVAL '24 months');

-- ---------------------------------------------------------------------------
-- market_regimes — classificação de regime (§11 REG-001..005: tendência,
-- lateralização, compressão, expansão, mudança de regime).
-- Hypertable, chunk de 7 dias.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_regimes (
    time       TIMESTAMPTZ NOT NULL,
    exchange   TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    timeframe  TEXT NOT NULL,
    regime     TEXT NOT NULL CHECK (regime IN ('trend_up', 'trend_down', 'range', 'compression', 'expansion', 'volatile', 'transition')),
    confidence NUMERIC(5, 4) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    features   JSONB NOT NULL DEFAULT '{}'::jsonb,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol, timeframe)
);
SELECT create_hypertable('market_regimes', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_regimes_symbol_tf ON market_regimes (symbol, timeframe, time DESC);
CREATE INDEX IF NOT EXISTS idx_regimes_exch_sym  ON market_regimes (exchange, symbol, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('market_regimes', INTERVAL '24 months');

-- ---------------------------------------------------------------------------
-- market_features — feature store para ML (§8, ML-001): vetores de
-- features derivados de indicadores/padrões/order flow, por versão de
-- conjunto de features (`feature_set`) e versão de modelo.
-- Hypertable, chunk de 7 dias.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_features (
    time         TIMESTAMPTZ NOT NULL,
    exchange     TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    timeframe    TEXT NOT NULL,
    feature_set  TEXT NOT NULL,
    features     JSONB NOT NULL,
    model_version TEXT,
    received_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, exchange, symbol, timeframe, feature_set)
);
SELECT create_hypertable('market_features', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_features_symbol_tf ON market_features (symbol, timeframe, feature_set, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('market_features', INTERVAL '24 months');

-- ---------------------------------------------------------------------------
-- strategies — catálogo de estratégias (§6: STR-001..016 crypto e
-- BIN-001..016 binárias — pesquisa/simulação). `code` é o ID estável
-- (ex.: 'STR-001'); versionamento detalhado em strategy_versions.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT,
    category    TEXT NOT NULL CHECK (category IN ('crypto', 'binary')),
    status      TEXT NOT NULL DEFAULT 'experimental' CHECK (status IN ('experimental', 'testing', 'approved', 'disabled')),
    markets     JSONB NOT NULL DEFAULT '[]'::jsonb,
    timeframes  JSONB NOT NULL DEFAULT '[]'::jsonb,
    params      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_strategies_category ON strategies (category);
CREATE INDEX IF NOT EXISTS idx_strategies_status   ON strategies (status);

-- ---------------------------------------------------------------------------
-- strategy_versions — versões imutáveis de uma estratégia: regras e
-- parâmetros exatos usados em cada backtest/sinal (reprodutibilidade, §8).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_versions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id  UUID NOT NULL REFERENCES strategies (id) ON DELETE CASCADE,
    version      INTEGER NOT NULL CHECK (version >= 1),
    rules        JSONB NOT NULL DEFAULT '{}'::jsonb,
    params       JSONB NOT NULL DEFAULT '{}'::jsonb,
    status       TEXT NOT NULL DEFAULT 'experimental' CHECK (status IN ('experimental', 'testing', 'approved', 'disabled')),
    created_by   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (strategy_id, version)
);
CREATE INDEX IF NOT EXISTS idx_strategy_versions_strategy ON strategy_versions (strategy_id);

-- ---------------------------------------------------------------------------
-- strategy_signals — sinais (§9: campos mínimos completos).
-- Ciclo: DETECTED -> VALIDATING -> APPROVED -> PUBLISHED -> ACTIVE ->
-- CLOSED; também INVALIDATED ou EXPIRED. `probability` é a probabilidade
-- CALIBRADA (0–1); `rationale` guarda as justificativas; `result` o
-- desfecho após o fechamento. Retenção PERMANENTE (§11).
-- Hypertable em created_at, chunk de 7 dias.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_signals (
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    id                UUID NOT NULL DEFAULT gen_random_uuid(),
    exchange          TEXT NOT NULL,
    market            TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    timeframe         TEXT NOT NULL,
    direction         TEXT NOT NULL CHECK (direction IN ('long', 'short', 'call', 'put', 'neutral')),
    strategy_id       UUID REFERENCES strategies (id) ON DELETE SET NULL,
    strategy_version  INTEGER,
    model_version     TEXT,
    originated_at     TIMESTAMPTZ,
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    reference_price   NUMERIC(38, 18),
    entry_price       NUMERIC(38, 18),
    stop_loss         NUMERIC(38, 18),
    take_profit       NUMERIC(38, 18),
    probability       NUMERIC(5, 4) CHECK (probability IS NULL OR (probability >= 0 AND probability <= 1)),
    valid_until       TIMESTAMPTZ,
    spread            NUMERIC(38, 18),
    liquidity_usd     NUMERIC(38, 2),
    rationale         JSONB NOT NULL DEFAULT '{}'::jsonb,
    status            TEXT NOT NULL DEFAULT 'DETECTED' CHECK (status IN ('DETECTED', 'VALIDATING', 'APPROVED', 'PUBLISHED', 'ACTIVE', 'CLOSED', 'INVALIDATED', 'EXPIRED')),
    result            TEXT CHECK (result IS NULL OR result IN ('win', 'loss', 'breakeven', 'expired', 'invalidated')),
    result_pnl        NUMERIC(38, 18),
    closed_at         TIMESTAMPTZ,
    PRIMARY KEY (created_at, id)
);
SELECT create_hypertable('strategy_signals', by_range('created_at'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_signals_symbol_time  ON strategy_signals (symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_exchange_sym ON strategy_signals (exchange, symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_strategy      ON strategy_signals (strategy_id, strategy_version, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_status        ON strategy_signals (status, created_at DESC);
-- SEM política de retenção: sinais têm retenção permanente (§11).

-- ---------------------------------------------------------------------------
-- strategy_results — resultados de backtest/paper por estratégia/versão
-- (§8: win rate, expectativa, profit factor, Sharpe, drawdown, cobertura,
-- Brier score; fora da amostra sinalizado em out_of_sample).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_results (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id      UUID NOT NULL REFERENCES strategies (id) ON DELETE CASCADE,
    strategy_version INTEGER,
    period_start     TIMESTAMPTZ,
    period_end       TIMESTAMPTZ,
    trades_count     INTEGER NOT NULL DEFAULT 0,
    win_rate         NUMERIC(5, 4),
    expectancy       NUMERIC(38, 18),
    profit_factor    NUMERIC(10, 4),
    sharpe           NUMERIC(10, 4),
    max_drawdown     NUMERIC(5, 4),
    coverage         NUMERIC(5, 4),
    brier_score      NUMERIC(5, 4),
    sample_size      INTEGER,
    out_of_sample    BOOLEAN NOT NULL DEFAULT FALSE,
    metrics          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_strategy_results_strategy ON strategy_results (strategy_id, strategy_version, created_at DESC);

-- ---------------------------------------------------------------------------
-- model_versions — versões de modelos quantitativos (§8: Logistic
-- Regression, Random Forest, XGBoost, LightGBM, HMM, GARCH etc.).
-- `calibration` guarda o método de calibração de probabilidade.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_code  TEXT NOT NULL,
    version     TEXT NOT NULL,
    algorithm   TEXT,
    features    JSONB NOT NULL DEFAULT '{}'::jsonb,
    calibration JSONB NOT NULL DEFAULT '{}'::jsonb,
    status      TEXT NOT NULL DEFAULT 'experimental' CHECK (status IN ('experimental', 'testing', 'approved', 'disabled')),
    trained_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (model_code, version)
);
CREATE INDEX IF NOT EXISTS idx_model_versions_code ON model_versions (model_code);

-- ---------------------------------------------------------------------------
-- model_predictions — predições dos modelos (§8: probabilidade calibrada,
-- selective prediction). Hypertable, chunk de 7 dias.
-- Retenção: 24 meses.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_predictions (
    time           TIMESTAMPTZ NOT NULL,
    model_version  TEXT NOT NULL,
    exchange       TEXT NOT NULL,
    symbol         TEXT NOT NULL,
    timeframe      TEXT NOT NULL,
    direction      TEXT CHECK (direction IN ('long', 'short', 'call', 'put', 'neutral')),
    probability    NUMERIC(5, 4) CHECK (probability IS NULL OR (probability >= 0 AND probability <= 1)),
    features_ref   UUID,
    received_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (time, model_version, exchange, symbol, timeframe)
);
SELECT create_hypertable('model_predictions', by_range('time'), if_not_exists => TRUE, chunk_time_interval => INTERVAL '7 days');
CREATE INDEX IF NOT EXISTS idx_predictions_symbol ON model_predictions (symbol, timeframe, time DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_model  ON model_predictions (model_version, time DESC);
-- Retenção (ativar após arquivamento externo):
-- SELECT add_retention_policy('model_predictions', INTERVAL '24 months');
