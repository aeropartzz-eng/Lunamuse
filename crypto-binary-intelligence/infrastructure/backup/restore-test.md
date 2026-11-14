# Teste de restauração do backup (Fase 1, INF-008)

> ⚠️ **O teste descrito aqui NÃO rodou nesta máquina** — não há PostgreSQL
> nem Docker aqui. Ele só pode rodar na VPS, depois do primeiro backup
> (`backup.sh`) e com a stack no ar. Backup sem restauração comprovada
> **não conta como aceite** (INF-008). Quando o teste rodar, registrar a
> saída real e a data no final deste arquivo.

## Objetivo

Provar que um dump gerado pelo `backup.sh` restaura um banco utilizável:
tabelas presentes, hypertables do TimescaleDB íntegras e contagem de
linhas coerente com a origem.

## Pré-requisitos

- VPS com a stack no ar (`docker compose ps` com `cbi-postgres` saudável).
- Ao menos um backup no Object Storage (ver `aws s3 ls` no passo 1).
- Espaço em disco para um segundo banco (o de teste) — o dump completo
  tem o tamanho do banco de produção.

## Procedimento

### Passo 0 — Subir um PostgreSQL de teste (isolado da produção)

```bash
docker run -d --name cbi-restore-test \
  -e POSTGRES_DB=restore_test \
  -e POSTGRES_USER=cbi \
  -e POSTGRES_PASSWORD='<mesma senha de teste — NÃO reuse a de produção em log>' \
  -p 127.0.0.1:5433:5432 \
  timescale/timescaledb:latest-pg16
```

**Saída esperada:** o ID do container (hash hexadecimal). Depois:
`docker exec cbi-restore-test pg_isready -U cbi -d restore_test`
→ `restore_test accepting connections`.

### Passo 1 — Baixar o backup mais recente do Object Storage

```bash
cd /opt/crypto-binary-intelligence
source .env   # carrega S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY
export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
LATEST=$(aws --endpoint-url "$S3_ENDPOINT" s3 ls "s3://$S3_BUCKET/postgres/" \
  | sort | tail -n 1 | awk '{print $4}')
aws --endpoint-url "$S3_ENDPOINT" s3 cp "s3://$S3_BUCKET/postgres/$LATEST" "/tmp/$LATEST"
ls -lh "/tmp/$LATEST"
```

**Saída esperada:** `aws s3 ls` lista ao menos um objeto
`postgres/<banco>-<data>-<hora>.dump.gz`; o `cp` termina sem erro e o
arquivo existe em `/tmp/` com tamanho > 0.

### Passo 2 — Descomprimir e restaurar no banco de teste

```bash
gunzip -c "/tmp/$LATEST" > /tmp/restore.dump
docker exec -i cbi-restore-test pg_restore -U cbi -d restore_test \
  --no-owner --no-privileges /tmp/restore.dump
```

> `pg_restore` pode imprimir avisos sobre `COMMENT`/`ALTER ... OWNER`
> quando `--no-owner` é usado — avisos são aceitáveis. **Erros** de
> `ERROR: relation ... does not exist` ou falha de integridade não são.

**Saída esperada:** o comando termina com exit code 0 (confirmar com
`echo $?` → `0`). Nenhuma linha começando com `ERROR:`.

### Passo 3 — Verificar tabelas e hypertables

```bash
docker exec cbi-restore-test psql -U cbi -d restore_test -c \
  "SELECT count(*) AS tabelas FROM information_schema.tables WHERE table_schema='public';"
docker exec cbi-restore-test psql -U cbi -d restore_test -c \
  "SELECT hypertable_name FROM timescaledb_information.hypertables;"
```

**Saída esperada:** `tabelas` igual ao número de tabelas do banco de
produção (comparar com o mesmo comando rodado no `cbi-postgres`);
`hypertable_name` lista as hypertables esperadas (`market_trades`,
`market_candles`, conforme as migrações da Fase 2). Se a Fase 2 ainda
não criou hypertables, a segunda consulta retorna zero linhas — anotar
isso como esperado para aquele momento.

### Passo 4 — Verificar contagem de linhas (amostragem)

```bash
docker exec cbi-postgres psql -U cbi -d crypto_intelligence -t -c \
  "SELECT count(*) FROM market_candles;" > /tmp/count_prod.txt
docker exec cbi-restore-test psql -U cbi -d restore_test -t -c \
  "SELECT count(*) FROM market_candles;" > /tmp/count_restore.txt
diff /tmp/count_prod.txt /tmp/count_restore.txt && echo "CONTAGENS IGUAIS"
```

**Saída esperada:** `CONTAGENS IGUAIS`. Repetir para 2–3 tabelas
relevantes (`market_trades`, `strategy_signals`, `audit_logs` quando
existirem). Pequenas diferenças são aceitáveis **somente** se houver
escrita concorrente durante o dump — nesse caso, anotar o motivo.

### Passo 5 — Limpeza

```bash
docker stop cbi-restore-test && docker rm cbi-restore-test
rm -f /tmp/restore.dump "/tmp/$LATEST" /tmp/count_prod.txt /tmp/count_restore.txt
```

**Saída esperada:** container removido; nenhum arquivo de dump restante
em `/tmp`.

## Critério de aceite (INF-008)

- [ ] Passo 1: backup baixado do Object Storage.
- [ ] Passo 2: `pg_restore` com exit code 0, sem linhas `ERROR:`.
- [ ] Passo 3: nº de tabelas igual ao de produção; hypertables presentes.
- [ ] Passo 4: contagens iguais (ou divergência justificada e anotada).
- [ ] Passo 5: ambiente de teste removido.

## Registro de execução

| Data | Executor | Backup restaurado | Resultado |
|------|----------|-------------------|-----------|
| — | — | — | **NÃO EXECUTADO — aguardando VPS (não há Postgres nesta máquina).** |
