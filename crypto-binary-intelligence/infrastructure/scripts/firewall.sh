#!/usr/bin/env bash
# =============================================================================
# firewall.sh — Firewall UFW (Fase 1, INF-003)
# =============================================================================
# PROPÓSITO
#   Configurar o UFW (Uncomplicated Firewall) com política de negação por
#   padrão: só entra o que está explicitamente liberado.
#
# REGRAS (documentadas — nada além disto é aberto)
#   Entrada (incoming): NEGADA por padrão.
#     - SSH ............ porta ${SSH_PORT} (default 22) — única porta de
#                        administração. Se o harden-ssh.sh mudou a porta,
#                        passe a mesma aqui (--ssh-port).
#     - HTTP ........... porta 80/tcp — necessário para o desafio HTTP-01
#                        do Let's Encrypt (Caddy renova o TLS por aqui).
#     - HTTPS .......... porta 443/tcp — API e painel via Caddy.
#   Saída (outgoing): PERMITIDA (o servidor precisa buscar pacotes, imagens
#   Docker e dados das exchanges).
#   NÃO são expostas: 5432 (PostgreSQL), 6379 (Redis), 4222/8222 (NATS),
#   8000 (API), 3000/3001 (painel/Grafana), 9090 (Prometheus). No
#   docker-compose.yml esses serviços escutam só em 127.0.0.1 e o acesso
#   externo passa pelo Caddy (443) — ver infrastructure/caddy/README.md.
#
# USO (na VPS, como root ou com sudo)
#   sudo bash firewall.sh [--ssh-port PORTA] [--dry-run]
#   Variável de ambiente equivalente: SSH_PORT (default: 22).
#   --dry-run mostra as regras que seriam aplicadas sem alterar nada.
#
# PRÉ-REQUISITOS
#   - UFW instalado (install-ubuntu.sh já instala). Se a porta SSH foi
#     alterada, rode este script com a porta nova ANTES de reiniciar o SSH.
#
# IDEMPOTENTE: `ufw allow` repetido não duplica a regra.
#
# REVERSÃO: sudo ufw disable  (desliga o firewall, mantendo as regras) ou
#   sudo ufw reset  (apaga TODAS as regras — exige confirmar e recriar).
# =============================================================================
set -euo pipefail

SSH_PORT="${SSH_PORT:-22}"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ssh-port) SSH_PORT="$2"; shift 2 ;;
    --dry-run)  DRY_RUN=true; shift ;;
    -h|--help)
      sed -n '2,/^# ===/p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "Opção desconhecida: $1 (use --help)" >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERRO: rode como root ou com sudo." >&2; exit 1
fi

if ! [[ "${SSH_PORT}" =~ ^[0-9]+$ ]] || [[ "${SSH_PORT}" -lt 1 ]] || [[ "${SSH_PORT}" -gt 65535 ]]; then
  echo "ERRO: porta SSH inválida: ${SSH_PORT}" >&2; exit 1
fi

run() {
  if [[ "${DRY_RUN}" == true ]]; then
    echo "  [dry-run] $*"
  else
    "$@"
  fi
}

echo "Regras a aplicar:"
echo "  incoming: deny (padrão) | allow ${SSH_PORT}/tcp (SSH)"
echo "  allow 80/tcp (HTTP/ACME) | allow 443/tcp (HTTPS/Caddy)"
echo "  outgoing: allow (padrão)"
echo

run ufw --force reset
run ufw default deny incoming
run ufw default allow outgoing
run ufw allow "${SSH_PORT}/tcp" comment 'SSH'
run ufw allow 80/tcp comment 'HTTP - Caddy/ACME'
run ufw allow 443/tcp comment 'HTTPS - Caddy (API + painel)'
run ufw --force enable

if [[ "${DRY_RUN}" == false ]]; then
  echo
  ufw status verbose
  echo
  echo "OK — firewall ativo. Portas internas do compose (5432, 6379, 4222,"
  echo "8000, 3000, 3001, 9090) NÃO foram abertas: ficam em 127.0.0.1."
fi
