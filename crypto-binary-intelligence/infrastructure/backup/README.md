# infrastructure/backup — Backup (Fase 1 — INF-008)

- Backup do PostgreSQL/TimescaleDB (pg_dump) + Object Storage.
- Teste de restauração obrigatório: backup sem restauração comprovada
  não conta como aceite (INF-008).
- Retenção (§11): trades brutos prioritários 7 dias; Order Book bruto
  2–7 dias; candles 1s 30 dias; candles 1m/5m 24 meses; timeframes
  maiores 3 anos ou mais; sinais, ordens e auditoria permanentes.
- `backup.sh` é um placeholder: implementar com as credenciais do
  Object Storage (S3_* no .env) na Fase 1.
