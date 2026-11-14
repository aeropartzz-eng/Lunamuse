# infrastructure/scripts — Scripts de provisionamento da VPS (Fase 1)

Scripts de **provisionamento da VPS futura** (INF-002, INF-003, INF-005).
Nada aqui é executado nesta máquina: não há Docker nem servidor aqui, e
os scripts **não devem** ser rodados contra nenhuma máquina real sem
revisão. Todos são idempotentes (podem rodar mais de uma vez) e têm
cabeçalho próprio com propósito, uso, pré-requisitos e reversão.

## Ordem de execução

| # | Script | Tarefa | O que faz |
|---|--------|--------|-----------|
| 1 | `install-ubuntu.sh` | INF-002 | Atualiza pacotes, cria usuário não-root com sudo, NTP (systemd-timesyncd), timezone |
| 2 | `install-docker.sh` | INF-005 | Docker Engine + Compose (plugin v2) do repositório oficial, usuário no grupo `docker`, teste `hello-world` |
| 3 | `harden-ssh.sh` | INF-003 | SSH só por chave, sem root e sem senha, porta opcional, fail2ban |
| 4 | `firewall.sh` | INF-003 | UFW: só SSH + 80/443; resto negado; portas internas do compose fechadas |

Ordem importa: o usuário precisa existir antes do Docker (grupo
`docker`); o firewall precisa conhecer a porta SSH **antes** de o SSH
ser endurecido/reiniciado com porta nova; e o `harden-ssh.sh` só deve
rodar **depois** de a chave SSH estar instalada e testada em outra sessão.

## Pré-requisitos

- VPS contratada (INF-001 — pendente, ver abaixo), Ubuntu Server LTS
  (22.04 ou 24.04), acesso root/sudo, internet.
- Uma chave SSH pública gerada na sua máquina (`ssh-keygen -t ed25519`).
- Uma sessão SSH aberta que você **não fecha** até testar o acesso
  endurecido em uma segunda sessão.

## Uso

```bash
# 1. Base do sistema (como root ou sudo)
sudo bash install-ubuntu.sh --user cbi --timezone America/Fortaleza \
  --ssh-key "$(cat ~/.ssh/id_ed25519.pub)"

# 2. Docker
sudo bash install-docker.sh --user cbi
#    -> faça logout/login do usuário cbi para o grupo docker valer

# 3. Firewall (ANTES de reiniciar o SSH com porta nova, se for o caso)
sudo bash firewall.sh --ssh-port 22

# 4. SSH (mantenha esta sessão aberta; teste em outra sessão depois)
sudo bash harden-ssh.sh --port 22
#    -> teste: ssh -p 22 cbi@<ip-da-vps>  (em uma NOVA sessão)
```

Variáveis de ambiente equivalentes: `APP_USER`, `TIMEZONE`,
`SSH_PUBLIC_KEY`, `SSH_PORT`. Cada script aceita `--help`.

## O que cada script faz (resumo)

- **install-ubuntu.sh** — `apt update && upgrade`, pacotes base
  (ca-certificates, curl, git, htop, jq, ufw, fail2ban,
  systemd-timesyncd), usuário `cbi` com sudo e chave SSH em
  `~/.ssh/authorized_keys`, `timedatectl set-ntp true` e timezone
  `America/Fortaleza` (default; ajuste com `--timezone`).
- **install-docker.sh** — chave GPG + repositório oficial do Docker,
  `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`,
  `docker-compose-plugin`; `systemctl enable --now docker`; usuário no
  grupo `docker`; versões impressas + `docker run hello-world`.
- **harden-ssh.sh** — backup de `/etc/ssh/sshd_config` com timestamp;
  `PermitRootLogin no`, `PasswordAuthentication no`,
  `ChallengeResponseAuthentication no`, `PubkeyAuthentication yes`,
  `MaxAuthTries 3`, `LoginGraceTime 30`; `sshd -t` antes de reiniciar;
  fail2ban instalado e ativado (a menos que `--no-fail2ban`).
- **firewall.sh** — `ufw default deny incoming` / `allow outgoing`;
  libera SSH + 80/tcp (ACME/Let's Encrypt) + 443/tcp (Caddy). As portas
  internas do compose (5432, 6379, 4222, 8000, 3000, 3001, 9090) **não**
  são abertas — ficam em `127.0.0.1` e o acesso externo passa pelo Caddy.

## Reversão

Cada script documenta a reversão no próprio cabeçalho:

| Script | Como reverter |
|--------|---------------|
| install-ubuntu.sh | `userdel -r cbi` (remove o usuário); `timedatectl set-timezone <tz>` para o timezone |
| install-docker.sh | `apt-get purge docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`; remover `/etc/apt/sources.list.d/docker.list` e `/etc/apt/keyrings/docker.gpg`; `deluser cbi docker` |
| harden-ssh.sh | `cp /etc/ssh/sshd_config.bak.<data-hora> /etc/ssh/sshd_config && systemctl restart ssh` |
| firewall.sh | `ufw disable` (desliga, mantém regras) ou `ufw reset` (apaga todas as regras) |

## Validação (sem VPS)

Nesta máquina (sem Docker, sem servidor) só é possível validar a
sintaxe — o que foi feito na Fase 1:

```bash
bash -n infrastructure/scripts/*.sh   # sintaxe OK (4/4)
shellcheck infrastructure/scripts/*.sh  # não disponível nesta máquina
```

O teste real é na VPS: `docker run --rm hello-world`, login SSH com
chave em nova sessão, `ufw status verbose` e `fail2ban-client status sshd`.
