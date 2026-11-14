#!/usr/bin/env bash
# =============================================================================
# install-ubuntu.sh — Preparação base do Ubuntu Server LTS (Fase 1, INF-002)
# =============================================================================
# PROPÓSITO
#   Deixar um Ubuntu Server LTS recém-instalado pronto para receber o
#   Crypto & Binary Intelligence: pacotes atualizados, usuário não-root com
#   sudo, NTP sincronizado e timezone configurado.
#
# USO (na VPS, como root ou com sudo)
#   sudo bash install-ubuntu.sh [--user NOME] [--timezone TZ] [--ssh-key "CHAVE"]
#   Variáveis de ambiente equivalentes: APP_USER, TIMEZONE, SSH_PUBLIC_KEY.
#   Defaults: APP_USER=cbi | TIMEZONE=America/Fortaleza
#   --ssh-key instala a chave pública no ~/.ssh/authorized_keys do usuário.
#   Sem ela, o usuário é criado sem chave (o login por senha continua ativo
#   até o harden-ssh.sh rodar — veja scripts/README.md).
#
# PRÉ-REQUISITOS
#   - Ubuntu Server LTS (22.04 ou 24.04), acesso root/sudo, internet.
#   - Rodar ANTES de install-docker.sh, harden-ssh.sh e firewall.sh.
#
# IDEMPOTENTE: pode rodar mais de uma vez; não recria o usuário nem
# reinstala pacotes já presentes.
#
# REVERSÃO: não há "desinstalar" automático — pacotes e usuário criados
# aqui são base do servidor. Para desfazer, remover o usuário
# (userdel -r <nome>) e restaurar o timezone (timedatectl set-timezone).
# =============================================================================
set -euo pipefail

APP_USER="${APP_USER:-cbi}"
TIMEZONE="${TIMEZONE:-America/Fortaleza}"
SSH_PUBLIC_KEY="${SSH_PUBLIC_KEY:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)     APP_USER="$2"; shift 2 ;;
    --timezone) TIMEZONE="$2"; shift 2 ;;
    --ssh-key)  SSH_PUBLIC_KEY="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,/^# ===/p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "Opção desconhecida: $1 (use --help)" >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERRO: rode como root ou com sudo." >&2; exit 1
fi

echo "==> [1/5] Atualizando lista de pacotes e sistema..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq

echo "==> [2/5] Instalando pacotes base..."
apt-get install -y -qq \
  ca-certificates curl gnupg lsb-release \
  git vim htop ncdu unzip jq \
  ufw fail2ban \
  systemd-timesyncd

echo "==> [3/5] Criando usuário não-root '${APP_USER}' (se ainda não existir)..."
if id "${APP_USER}" &>/dev/null; then
  echo "    Usuário já existe; mantendo."
else
  adduser --disabled-password --gecos "" "${APP_USER}"
  echo "    Usuário criado sem senha (login só por chave SSH)."
fi
usermod -aG sudo "${APP_USER}"

if [[ -n "${SSH_PUBLIC_KEY}" ]]; then
  echo "==> Instalando chave SSH pública para '${APP_USER}'..."
  HOME_DIR="$(getent passwd "${APP_USER}" | cut -d: -f6)"
  mkdir -p "${HOME_DIR}/.ssh"
  chmod 700 "${HOME_DIR}/.ssh"
  touch "${HOME_DIR}/.ssh/authorized_keys"
  if ! grep -qxF "${SSH_PUBLIC_KEY}" "${HOME_DIR}/.ssh/authorized_keys"; then
    echo "${SSH_PUBLIC_KEY}" >> "${HOME_DIR}/.ssh/authorized_keys"
  fi
  chmod 600 "${HOME_DIR}/.ssh/authorized_keys"
  chown -R "${APP_USER}:${APP_USER}" "${HOME_DIR}/.ssh"
else
  echo "    AVISO: nenhuma chave SSH informada (--ssh-key). O login por senha"
  echo "    continua ativo até o harden-ssh.sh desabilitá-lo."
fi

echo "==> [4/5] Configurando NTP (systemd-timesyncd)..."
systemctl enable --now systemd-timesyncd
timedatectl set-ntp true

echo "==> [5/5] Configurando timezone para '${TIMEZONE}'..."
timedatectl set-timezone "${TIMEZONE}"

echo
echo "OK — base instalada."
timedatectl status | head -n 5
echo "Próximo passo: sudo bash install-docker.sh"
