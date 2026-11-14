# Ambientes — dev / staging / prod (Fase 1, INF-007)

## Princípio

Um ambiente é definido por **três coisas separadas**: o `.env` (credenciais),
o `docker-compose.yml` (ou override) e os dados. Nada de produção vaza
para dev/staging e nada de dev é promovido a produção sem revisão.
Credenciais **nunca** são compartilhadas entre ambientes e **nunca** vão
para o Git (o `.env` está no `.gitignore`).

## Os três ambientes

| Aspecto | development (dev) | staging | production (prod) |
|---|---|---|---|
| Onde roda | Máquina do desenvolvedor (ou VPS de testes) | VPS de staging (pode ser a mesma VPS, stack separada, ou VPS menor) | VPS de produção (4 vCPU / 8 GB / ~320 GB, §11) |
| `ENVIRONMENT` | `development` | `staging` | `production` |
| `EXECUTION_MODE` | `RESEARCH` | `RESEARCH` ou `PAPER` | `RESEARCH` até homologação; `PAPER`/`TESTNET` só após EXE-014; **LIVE bloqueado** (§10) |
| Banco | Local, descartável (`docker compose down -v` apaga) | Cópia sanitizada ou dados sintéticos — **nunca** dump de produção sem anonimizar | PostgreSQL/TimescaleDB de produção + backup diário (INF-008) |
| Credenciais | Próprias, fracas e locais (ex.: senhas de dev) | Próprias, geradas para staging | Próprias, fortes, geradas por ambiente; rotação ao trocar de responsável |
| Chaves de exchange | Só testnet / só leitura; sem chaves reais | Testnet / leitura | Leitura no início; trade só após homologação, sem saque, com IP restrito |
| Domínio / HTTPS | `localhost` (sem Caddy) | Subdomínio próprio (ex.: `staging.<DOMAIN>`) com TLS | `<DOMAIN>` + `api.<DOMAIN>` com TLS (Caddy, INF-004) |
| Monitoramento | Opcional | Prometheus/Grafana ligados | Obrigatório (alertas §16) |
| Dados de mercado | Amostra / replay de histórico | Replay ou feed real limitado | Feed real 24/7 |

## Separação de credenciais

- **Um `.env` por ambiente, nunca copiado de um para o outro.** O
  `.env.example` é o contrato de variáveis; cada ambiente preenche o seu.
- Senhas: `POSTGRES_PASSWORD`, `REDIS_PASSWORD`,
  `GRAFANA_ADMIN_PASSWORD` — valores **diferentes** em cada ambiente,
  gerados com `openssl rand -base64 32` (ou gerenciador de senhas).
- Chaves de exchange: uma chave por ambiente, quando a exchange permitir
  (Binance/Bybit testnet para dev/staging). Chave de produção **nunca**
  entra em dev/staging.
- Object Storage: um bucket (ou prefixo) por ambiente —
  `cbi-backups-dev`, `cbi-backups-staging`, `cbi-backups-prod` — para um
  `backup.sh` de staging nunca apagar/ler o backup de produção.
- Telegram/WhatsApp: bot/canal de staging separado do de produção, para
  um sinal de teste nunca chegar ao canal real.

## O que muda em cada um (na prática)

1. **Compose:** o `docker-compose.yml` base é o mesmo; diferenças vão em
   overrides (`docker-compose.staging.yml`, `docker-compose.prod.yml`)
   — ex.: em prod o Caddy expõe 80/443 e os serviços ficam só em
   `127.0.0.1`; em dev as portas ficam em `localhost` sem Caddy.
2. **Variáveis:** só o `.env` muda (`ENVIRONMENT`, senhas, `DOMAIN`,
   `S3_BUCKET`, `EXECUTION_MODE`, tokens de notificação).
3. **Dados:** dev usa dados sintéticos ou amostras; staging usa replay
   ou cópia sanitizada; prod usa o feed real e é o único com backup
   diário obrigatório e retenção longa (§11).
4. **Acesso:** dev é local; staging e prod são VPS com SSH por chave,
   firewall e fail2ban (scripts em `infrastructure/scripts/`). O acesso
   a prod é restrito ao responsável.

## Promoção dev → staging → prod

1. Código: merge para a branch do ambiente, com revisão (INF-006).
2. Staging: subir, rodar testes de fumaça (`/health`, conectores,
   sinais de teste) e só então promover.
3. Prod: deploy com o mesmo artefato testado em staging; **nunca**
   editar código direto em produção.
4. Rollback: `git checkout <tag anterior>` + `docker compose up -d`
   (e restaurar o banco a partir do backup, se uma migração tiver
   corrido — ver `infrastructure/backup/restore-test.md`).

## Checklist de criação de um ambiente

- [ ] `.env` próprio criado a partir do `.env.example`, senhas geradas.
- [ ] `ENVIRONMENT` e `EXECUTION_MODE` conferidos (LIVE nunca por padrão).
- [ ] Bucket/prefixo de backup próprio.
- [ ] Domínio/DNS (staging/prod) ou `localhost` (dev).
- [ ] `docker compose config` valida sem erro (não sobe nada).
- [ ] `/health` responde 200 após `docker compose up -d`.
