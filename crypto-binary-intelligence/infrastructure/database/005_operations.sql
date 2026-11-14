-- =============================================================================
-- Crypto & Binary Intelligence — 005_operations.sql (Fase 2 — DB-006)
-- =============================================================================
-- Tabelas de operação (§13 "Operação"): users, roles, permissions,
-- notifications, notification_deliveries.
-- NÃO duplicadas aqui (já existem no 001_init.sql): system_events,
-- audit_logs e connection_status.
-- Idempotente: CREATE TABLE/INDEX com IF NOT EXISTS; seeds com
-- ON CONFLICT DO NOTHING.
--
-- Trilha de auditoria (DB-006): audit_logs (001) registra ator/ação/alvo/
-- detalhes de toda ação administrativa e de execução; schema_migrations
-- (abaixo) registra cada migração aplicada; system_events registra eventos
-- operacionais. Nenhuma dessas tabelas tem política de retenção — a
-- auditoria é permanente (§11).
-- Segurança: `users.password_hash` guarda SOMENTE hash (bcrypt/argon2),
-- nunca senha em claro; segredos de exchange e tokens de notificação
-- NUNCA vão para o banco (ver 004_execution.sql e redis-schema.md).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- users — usuários do painel/API (§13, segurança: autenticação forte,
-- autorização por função, rate limiting, TLS).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- roles — papéis (admin, operator, viewer). Autorização por função (§13).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- permissions — permissões granulares (ex.: signals.read, execution.approve,
-- execution.kill_switch, admin.users). O endpoint de execução é protegido
-- (§13): só quem tem execution.* pode aprovar/cancelar/acionar kill switch.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Junções N:N (não são tabelas de domínio novas do §13; são a ligação
-- necessária entre users/roles/permissions).
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id       UUID NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions (id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles (id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- ---------------------------------------------------------------------------
-- notifications — notificações a distribuir (§9: Telegram, WhatsApp
-- Business oficial, painel web, API externa). Um registro por sinal/canal;
-- o envio em si fica em notification_deliveries.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel    TEXT NOT NULL CHECK (channel IN ('telegram', 'whatsapp', 'web', 'api')),
    signal_id  UUID, -- sem FK: strategy_signals é hypertable com PK (created_at, id); FK para só `id` é inválida no Postgres/TimescaleDB. Integridade garantida pela aplicação.
    title      TEXT,
    body       TEXT NOT NULL,
    payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
    status     TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'sent', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_notifications_signal ON notifications (signal_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications (status, created_at DESC);

-- ---------------------------------------------------------------------------
-- notification_deliveries — entregas e falhas por canal (§14 SIG-008:
-- registrar entregas e falhas). `provider_message_id` é o ID retornado
-- pelo Telegram/WhatsApp; `error` guarda a falha sem credenciais.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notification_deliveries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id     UUID NOT NULL REFERENCES notifications (id) ON DELETE CASCADE,
    channel             TEXT NOT NULL CHECK (channel IN ('telegram', 'whatsapp', 'web', 'api')),
    recipient           TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'sent', 'delivered', 'failed')),
    provider_message_id TEXT,
    error               TEXT,
    attempted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_deliveries_notification ON notification_deliveries (notification_id, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_deliveries_status       ON notification_deliveries (status, attempted_at DESC);

-- ---------------------------------------------------------------------------
-- schema_migrations — registro das migrações aplicadas (trilha DB-006).
-- Cada migração insere sua versão ao final da aplicação manual na VPS
-- (ver README.md). No docker-entrypoint-initdb.d o 001–005 rodam uma só
-- vez na criação do volume; esta tabela serve para as aplicações
-- manuais/sequenciais posteriores.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations (version) VALUES
    ('001_init'),
    ('002_market'),
    ('003_intelligence'),
    ('004_execution'),
    ('005_operations')
ON CONFLICT (version) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Seeds mínimos (RBAC). Sem usuário inicial: o primeiro admin é criado
-- pelo responsável na VPS (senha via variável de ambiente no setup, nunca
-- commitada). Papéis e permissões base:
-- ---------------------------------------------------------------------------
INSERT INTO roles (name, description) VALUES
    ('admin',    'Administração total, incluindo usuários e kill switch'),
    ('operator', 'Opera sinais e execução em modos de teste; sem gerir usuários'),
    ('viewer',   'Somente leitura: sinais, painel e relatórios')
ON CONFLICT (name) DO NOTHING;

INSERT INTO permissions (code, description) VALUES
    ('signals.read',        'Ler sinais'),
    ('signals.approve',     'Aprovar/rejeitar sinais'),
    ('strategies.read',     'Ler estratégias'),
    ('strategies.write',    'Criar/editar estratégias'),
    ('execution.read',      'Ler ordens, fills e posições'),
    ('execution.orders',    'Criar/cancelar ordens (modos de teste)'),
    ('execution.approve',   'Aprovar execução (humana, §10)'),
    ('execution.kill_switch','Acionar kill switch'),
    ('admin.users',         'Gerir usuários e papéis'),
    ('admin.system',        'Ver saúde do sistema e auditoria')
ON CONFLICT (code) DO NOTHING;

-- admin: todas as permissões. operator: tudo exceto admin.* e kill switch
-- (kill switch é ação crítica; só admin). viewer: somente leitura.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r CROSS JOIN permissions p WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code IN
    ('signals.read', 'signals.approve', 'strategies.read', 'strategies.write',
     'execution.read', 'execution.orders', 'execution.approve')
WHERE r.name = 'operator'
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.code IN
    ('signals.read', 'strategies.read', 'execution.read')
WHERE r.name = 'viewer'
ON CONFLICT DO NOTHING;
