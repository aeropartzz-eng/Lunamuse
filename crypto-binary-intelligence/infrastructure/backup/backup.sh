#!/usr/bin/env bash
# =============================================================================
# backup.sh — Backup do PostgreSQL/TimescaleDB (Fase 1, INF-008)
# =============================================================================
# PROPÓSITO
#   Dump do PostgreSQL/TimescaleDB (pg_dump em formato custom), compressão
#   com gzip, upload para Object Storage compatível com S3 e rotação de
#   backups locais e remotos. Loga cada execução e impede duas execuções
#   simultâneas (lockfile).
#
# USO (na VPS, dentro do diretório do projeto, como o usuário da aplicação)
#   bash infrastructure/backup/backup.sh [--dry-run]
#   Agendamento recomendado (crontab do usuário cbi):
#     0 3 * * * cd /opt/crypto-binary-intelligence && bash infrastructure/backup/backup.sh >> /var/log/cbi-backup.log 2>&1
#
# VARIÁVEIS (todas via .env na raiz do projeto — NENHUMA credencial aqui)
#   POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD (já exigidas pelo compose)
#   S3_ENDPOINT, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY (ver .env.example)
#   S3_REGION (default: us-east-1), BACKUP_PREFIX (default: postgres)
#   BACKUP_DIR (default: ./data/backups), BACKUP_RETENTION_DAYS (default: 7 local)
#   BACKUP_REMOTE_RETENTION_DAYS (default: 30 remoto)
#
# PRÉ-REQUISITOS
#   - Stack no ar: container cbi-postgres saudável (docker compose up).
#   - AWS CLI v2 instalado (upload S3): https://aws.amazon.com/cli/
#     (ou `apt install awscli`). Sem ele, o backup local é feito, mas o
#     upload falha e o script sai com erro — de propósito, para não haver
#     falsa sensação de backup.
#   - .env preenchido com as credenciais do Object Storage.
#
# RETENÇÃO (§11): dumps completos diários; local 7 dias, remoto 30 dias.
#   A retenção longa (candles 24 meses, sinais/auditoria permanente) é
#   política de dados do banco, não deste script: o dump é sempre completo.
#
# REVERSÃO: o script só cria arquivos em BACKUP_DIR e objetos no bucket.
#   Para desfazer um backup: apagar o arquivo/objeto. Não altera o banco.
#
# TESTE DE RESTAURAÇÃO: ver infrastructure/backup/restore-test.md.
#   Backup sem restauração comprovada NÃO conta como aceite (INF-008).
#   ⚠️  O teste de restauração NÃO rodou nesta máquina (não há PostgreSQL
#   aqui) — ele só pode rodar na VPS, contra um banco de teste.
# =============================================================================
set -euo pipefail

# --- Configuração ------------------------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_DIR}"

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

# Carrega o .env (se existir) sem exportar segredos para o log.
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  echo "ERRO: .env não encontrado em ${PROJECT_DIR}." >&2
  exit 1
fi

: "${POSTGRES_DB:?POSTGRES_DB não definida no .env}"
: "${POSTGRES_USER:?POSTGRES_USER não definida no .env}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD não definida no .env}"
: "${S3_ENDPOINT:?S3_ENDPOINT não definido no .env}"
: "${S3_BUCKET:?S3_BUCKET não definido no .env}"
: "${S3_ACCESS_KEY:?S3_ACCESS_KEY não definido no .env}"
: "${S3_SECRET_KEY:?S3_SECRET_KEY não definido no .env}"

S3_REGION="${S3_REGION:-us-east-1}"
BACKUP_PREFIX="${BACKUP_PREFIX:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/data/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
BACKUP_REMOTE_RETENTION_DAYS="${BACKUP_REMOTE_RETENTION_DAYS:-30}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-cbi-postgres}"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/${POSTGRES_DB}-${TIMESTAMP}.dump.gz"
LOCKFILE="${BACKUP_DIR}/.backup.lock"
LOG_PREFIX="[backup ${TIMESTAMP}]"

log() { echo "${LOG_PREFIX} $*"; }
run() {
  if [[ "${DRY_RUN}" == true ]]; then
    echo "${LOG_PREFIX} [dry-run] $*"
  else
    "$@"
  fi
}

# --- Lock (evita duas execuções simultâneas) ---------------------------------
mkdir -p "${BACKUP_DIR}"
exec 9>"${LOCKFILE}"
if ! flock -n 9; then
  log "ERRO: outro backup já está em execução (lock em ${LOCKFILE})."
  exit 1
fi

log "Iniciando backup do banco '${POSTGRES_DB}' (container ${POSTGRES_CONTAINER})."

# --- 1. Dump via pg_dump dentro do container ---------------------------------
# Formato custom (-Fc): restaura com pg_restore e permite restaurar tabelas
# específicas. O dump sai do container por stdout e é comprimido no host,
# sem arquivo intermediário sem compressão em disco.
if [[ "${DRY_RUN}" == true ]]; then
  run docker exec "${POSTGRES_CONTAINER}" pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc
else
  if ! docker exec "${POSTGRES_CONTAINER}" pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc \
      | gzip > "${BACKUP_FILE}"; then
    log "ERRO: pg_dump falhou. Backup local NÃO foi criado."
    rm -f "${BACKUP_FILE}"
    exit 1
  fi
fi
log "Dump local criado: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" 2>/dev/null | cut -f1 || echo '?'))."

# --- 2. Upload para o Object Storage ------------------------------------------
S3_KEY="${BACKUP_PREFIX}/$(basename "${BACKUP_FILE}")"
export AWS_ACCESS_KEY_ID="${S3_ACCESS_KEY}"
export AWS_SECRET_ACCESS_KEY="${S3_SECRET_KEY}"
export AWS_DEFAULT_REGION="${S3_REGION}"

if ! command -v aws &>/dev/null; then
  log "ERRO: AWS CLI não encontrada. Instale a AWS CLI v2 para o upload S3."
  log "O dump local existe, mas NÃO foi enviado ao Object Storage."
  exit 1
fi

log "Enviando para s3://${S3_BUCKET}/${S3_KEY} (endpoint ${S3_ENDPOINT})..."
run aws --endpoint-url "${S3_ENDPOINT}" s3 cp "${BACKUP_FILE}" "s3://${S3_BUCKET}/${S3_KEY}"
log "Upload concluído."

# --- 3. Rotação local (BACKUP_RETENTION_DAYS) ---------------------------------
log "Rotação local: removendo dumps com mais de ${BACKUP_RETENTION_DAYS} dias..."
if [[ "${DRY_RUN}" == true ]]; then
  find "${BACKUP_DIR}" -name "${POSTGRES_DB}-*.dump.gz" -type f -mtime "+${BACKUP_RETENTION_DAYS}" -print
else
  find "${BACKUP_DIR}" -name "${POSTGRES_DB}-*.dump.gz" -type f -mtime "+${BACKUP_RETENTION_DAYS}" -delete
fi

# --- 4. Rotação remota (BACKUP_REMOTE_RETENTION_DAYS) --------------------------
# Lista objetos do prefixo e apaga os mais antigos que a retenção. Feito via
# `s3api list-objects-v2` para não depender de `s3 ls --recursive` com datas.
log "Rotação remota: removendo objetos com mais de ${BACKUP_REMOTE_RETENTION_DAYS} dias..."
CUTOFF="$(date -d "-${BACKUP_REMOTE_RETENTION_DAYS} days" +%Y-%m-%dT%H:%M:%S)"
if [[ "${DRY_RUN}" == true ]]; then
  run aws --endpoint-url "${S3_ENDPOINT}" s3api list-objects-v2 \
    --bucket "${S3_BUCKET}" --prefix "${BACKUP_PREFIX}/" \
    --query "Contents[?LastModified<='${CUTOFF}'].Key"
else
  OLD_KEYS="$(aws --endpoint-url "${S3_ENDPOINT}" s3api list-objects-v2 \
    --bucket "${S3_BUCKET}" --prefix "${BACKUP_PREFIX}/" \
    --query "Contents[?LastModified<='${CUTOFF}'].Key" --output text)"
  if [[ -n "${OLD_KEYS}" && "${OLD_KEYS}" != "None" ]]; then
    for key in ${OLD_KEYS}; do
      log "Removendo remoto: ${key}"
      aws --endpoint-url "${S3_ENDPOINT}" s3 rm "s3://${S3_BUCKET}/${key}"
    done
  else
    log "Nenhum objeto remoto fora da retenção."
  fi
fi

log "Backup concluído com sucesso: s3://${S3_BUCKET}/${S3_KEY}"
