#!/usr/bin/env bash
# =============================================================================
# harden-ssh.sh — Endurecimento do SSH (Fase 1, INF-003)
# =============================================================================
# PROPÓSITO
#   Trocar o SSH da VPS de "padrão de fábrica" para acesso só por chave:
#   desabilita login root e autenticação por senha, permite só chave pública,
#   opcionalmente muda a porta e instala/configura o fail2ban.
#
# USO (na VPS, como root ou com sudo)
#   sudo bash harden-ssh.sh [--port PORTA] [--allow-root-key] [--no-fail2ban]
#   Variáveis de ambiente equivalentes: SSH_PORT (default: 22),
#   ALLOW_ROOT_KEY=false, INSTALL_FAIL2BAN=true.
#   --port muda a porta do sshd (ex.: 2222). Se mudar, lembre de liberar a
#   porta no firewall.sh ANTES de reiniciar o SSH (o script avisa).
#   --allow-root-key mantém PermitRootLogin prohibit-password (root só com
#   chave). Default é `no` (root nem com chave — use sudo pelo usuário).
#
# PRÉ-REQUISITOS
#   - Chave SSH já instalada no usuário não-root (install-ubuntu.sh
#     --ssh-key) E TESTADA em outra sessão antes de rodar este script.
#   - ⚠️  MANTENHA UMA SESSÃO SSH ABERTA enquanto roda este script. Se algo
#     der errado, você ainda tem a sessão aberta para reverter.
#   - O script faz backup de /etc/ssh/sshd_config em
#     /etc/ssh/sshd_config.bak.<data-hora> antes de alterar.
#
# IDEMPOTENTE: pode rodar mais de uma vez; as diretivas são reescritas no
# mesmo valor.
#
# REVERSÃO: cp /etc/ssh/sshd_config.bak.<data-hora> /etc/ssh/sshd_config
#   && systemctl restart ssh
# =============================================================================
set -euo pipefail

SSH_PORT="${SSH_PORT:-22}"
ALLOW_ROOT_KEY="${ALLOW_ROOT_KEY:-false}"
INSTALL_FAIL2BAN="${INSTALL_FAIL2BAN:-true}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)           SSH_PORT="$2"; shift 2 ;;
    --allow-root-key) ALLOW_ROOT_KEY=true; shift ;;
    --no-fail2ban)    INSTALL_FAIL2BAN=false; shift ;;
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

SSHD_CONFIG="/etc/ssh/sshd_config"
BACKUP="${SSHD_CONFIG}.bak.$(date +%Y%m%d-%H%M%S)"

echo "==> [1/4] Backup de ${SSHD_CONFIG} -> ${BACKUP}"
cp "${SSHD_CONFIG}" "${BACKUP}"

# Escreve (ou substitui) uma diretiva no sshd_config, sem duplicar.
set_directive() {
  local key="$1" value="$2"
  if grep -qE "^[#[:space:]]*${key}[[:space:]]" "${SSHD_CONFIG}"; then
    sed -i -E "s|^[#[:space:]]*${key}[[:space:]].*|${key} ${value}|" "${SSHD_CONFIG}"
  else
    echo "${key} ${value}" >> "${SSHD_CONFIG}"
  fi
}

echo "==> [2/4] Aplicando diretivas de endurecimento..."
set_directive "Port" "${SSH_PORT}"
set_directive "PermitRootLogin" "$([[ "${ALLOW_ROOT_KEY}" == true ]] && echo "prohibit-password" || echo "no")"
set_directive "PasswordAuthentication" "no"
set_directive "ChallengeResponseAuthentication" "no"
set_directive "PubkeyAuthentication" "yes"
set_directive "PermitEmptyPasswords" "no"
set_directive "MaxAuthTries" "3"
set_directive "LoginGraceTime" "30"
set_directive "X11Forwarding" "no"

echo "==> [3/4] Validando configuração e reiniciando o SSH..."
sshd -t
systemctl restart ssh
systemctl is-active --quiet ssh && echo "    sshd ativo na porta ${SSH_PORT}."

if [[ "${INSTALL_FAIL2BAN}" == true ]]; then
  echo "==> [4/4] Instalando e ativando o fail2ban (proteção contra força bruta)..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq fail2ban
  # Jail sshd com os defaults do pacote (5 tentativas / 10 min de banimento).
  # Ajustes finos vão em /etc/fail2ban/jail.local, se necessário.
  systemctl enable --now fail2ban
  fail2ban-client status sshd || true
else
  echo "==> [4/4] fail2ban pulado (--no-fail2ban)."
fi

echo
echo "OK — SSH endurecido."
echo "  Porta: ${SSH_PORT} | root: $([[ "${ALLOW_ROOT_KEY}" == true ]] && echo 'só com chave' || echo 'bloqueado')"
echo "  Senha: desabilitada | fail2ban: ${INSTALL_FAIL2BAN}"
echo "  Backup da config anterior: ${BACKUP}"
echo
echo "⚠️  TESTE AGORA, em uma NOVA sessão SSH, antes de fechar esta:"
echo "     ssh -p ${SSH_PORT} <usuario>@<ip-da-vps>"
if [[ "${SSH_PORT}" != "22" ]]; then
  echo "  E libere a porta no firewall: sudo bash firewall.sh --ssh-port ${SSH_PORT}"
fi
