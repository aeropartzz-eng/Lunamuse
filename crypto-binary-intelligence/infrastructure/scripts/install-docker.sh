#!/usr/bin/env bash
# =============================================================================
# install-docker.sh — Docker Engine + Docker Compose (Fase 1, INF-005)
# =============================================================================
# PROPÓSITO
#   Instalar o Docker Engine e o plugin Docker Compose (v2) a partir do
#   repositório oficial do Docker, colocar o usuário da aplicação no grupo
#   `docker` e testar se o daemon responde e roda um container.
#
# USO (na VPS, como root ou com sudo)
#   sudo bash install-docker.sh [--user NOME] [--skip-test]
#   Variável de ambiente equivalente: APP_USER (default: cbi).
#   --skip-test pula o `docker run hello-world` (útil se a VPS estiver sem
#   internet no momento, ou para rodar o teste depois à mão).
#
# PRÉ-REQUISITOS
#   - Rodar install-ubuntu.sh antes (ou, no mínimo, Ubuntu LTS atualizado).
#   - Internet (repositório apt.docker.com + Docker Hub para o teste).
#   - O usuário precisa fazer LOGOUT e LOGIN novamente após entrar no grupo
#     docker, para o grupo valer na sessão.
#
# IDEMPOTENTE: pode rodar mais de uma vez; não reinstala o que já existe.
#
# REVERSÃO: apt-get purge docker-ce docker-ce-cli containerd.io \
#   docker-buildx-plugin docker-compose-plugin; remover /etc/apt/sources.list.d/docker.list
#   e /etc/apt/keyrings/docker.gpg; remover o usuário do grupo docker
#   (deluser <nome> docker). Volumes e imagens em /var/lib/docker permanecem
#   até remoção manual.
# =============================================================================
set -euo pipefail

APP_USER="${APP_USER:-cbi}"
SKIP_TEST=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)      APP_USER="$2"; shift 2 ;;
    --skip-test) SKIP_TEST=true; shift ;;
    -h|--help)
      sed -n '2,/^# ===/p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "Opção desconhecida: $1 (use --help)" >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERRO: rode como root ou com sudo." >&2; exit 1
fi

echo "==> [1/4] Instalando pré-requisitos do repositório Docker..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg

echo "==> [2/4] Adicionando chave GPG e repositório oficial do Docker..."
install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.gpg ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "==> [3/4] Instalando Docker Engine + Compose (plugin v2)..."
apt-get update -qq
apt-get install -y -qq \
  docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "==> [4/4] Adicionando '${APP_USER}' ao grupo docker..."
if id "${APP_USER}" &>/dev/null; then
  usermod -aG docker "${APP_USER}"
else
  echo "    AVISO: usuário '${APP_USER}' não existe — rode install-ubuntu.sh primeiro"
  echo "    ou crie o usuário e rode: sudo usermod -aG docker <nome>"
fi

echo
echo "--- Versões instaladas ---"
docker --version
docker compose version

if [[ "${SKIP_TEST}" == false ]]; then
  echo
  echo "--- Teste de funcionamento (docker run hello-world) ---"
  docker run --rm hello-world
  echo "OK — Docker operacional."
else
  echo "Teste pulado (--skip-test). Para testar depois:"
  echo "  docker run --rm hello-world && docker compose version"
fi

echo
echo "IMPORTANTE: faça logout/login do usuário '${APP_USER}' para o grupo"
echo "docker valer na sessão (ou rode: newgrp docker)."
