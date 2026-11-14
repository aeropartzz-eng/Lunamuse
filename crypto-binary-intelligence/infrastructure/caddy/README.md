# infrastructure/caddy — Reverse proxy + HTTPS (Fase 1, INF-004)

O Caddy é o ponto de entrada público do sistema: recebe HTTPS na 443,
termina o TLS (Let's Encrypt, automático) e repassa para os serviços
internos, que continuam escutando só em `127.0.0.1` no docker-compose.

## Como funciona

```
Internet ── 443/HTTPS ──▶ Caddy ──▶ dashboard:3000  (https://<domínio>)
                              └────▶ api:8000       (https://api.<domínio>)
```

- **TLS automático:** o Caddy emite e renova os certificados sozinho
  (desafio HTTP-01 na porta 80 — por isso o `firewall.sh` libera a 80).
  Nenhum certificado é gerenciado à mão.
- **Domínios:** o painel fica em `https://<DOMAIN>` e a API em
  `https://api.<DOMAIN>`, definidos no `Caddyfile` via variáveis
  `{$DOMAIN}` e `{$ACME_EMAIL}` (lidas do `.env`).
- **Headers de segurança:** `nosniff`, `DENY` (frame), HSTS de 6 meses,
  `Referrer-Policy` e `Permissions-Policy` restritivos, header `Server`
  removido. A API ainda soma um `Content-Security-Policy` restritivo.
- **Rate limit básico:** 60 req/min por IP na API (rajada de 10). Atenção:
  a diretiva `rate_limit` **exige o plugin `caddy-rate-limit`**.

## DNS necessário (pendente — depende do Will)

Antes de subir o Caddy na VPS, criar no provedor de DNS do domínio:

| Host | Tipo | Valor |
|------|------|-------|
| `<DOMAIN>` (ex.: `cbi.exemplo.com`) | A (+ AAAA, se houver IPv6) | IP público da VPS |
| `api.<DOMAIN>` | A (+ AAAA) | IP público da VPS |

Sem esses registros o Let's Encrypt não emite o certificado e o Caddy
não sobe com HTTPS. O domínio em si também é uma pendência do Will
(contratar/definir).

## Rate limit: plugin necessário

A imagem oficial `caddy:latest` **não** inclui `rate_limit`. Opções:

1. **Construir a imagem com o plugin (recomendado):**
   ```dockerfile
   # infrastructure/caddy/Dockerfile
   FROM caddy:builder AS builder
   RUN xcaddy build --with github.com/mholt/caddy-ratelimit
   FROM caddy:latest
   COPY --from=builder /usr/bin/caddy /usr/bin/caddy
   ```
   E no `docker-compose.yml`, trocar `image: caddy:latest` por
   `build: ./infrastructure/caddy`.
2. **Sem plugin:** remover o bloco `rate_limit` do Caddyfile e deixar o
   rate limiting para a API (a implementar nas Fases 2+). O resto do
   Caddyfile funciona com a imagem oficial.

## Ligação com o docker-compose (pendente)

O serviço `caddy` **ainda não está** no `docker-compose.yml` — entra
quando houver domínio e DNS, junto com a subida na VPS. O bloco a
adicionar (referência):

```yaml
  caddy:
    image: caddy:latest   # ou build: ./infrastructure/caddy (com plugin)
    container_name: cbi-caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infrastructure/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddydata:/data
      - caddyconfig:/config
    env_file:
      - .env
    depends_on:
      - api
      - dashboard
    networks:
      - cbi-net
```

E os volumes `caddydata:` e `caddyconfig:` na seção `volumes:`.

## Variáveis (.env)

| Variável | Uso |
|----------|-----|
| `DOMAIN` | Domínio base do painel (ex.: `cbi.exemplo.com`) |
| `ACME_EMAIL` | E-mail para avisos do Let's Encrypt |

## Validação (sem VPS)

Nesta máquina não há Docker nem domínio, então o Caddyfile **não foi
executado nem validado contra o binário do Caddy**. O que foi feito:
revisão manual da sintaxe (blocos, chaves, diretivas) e conferência das
variáveis com o `.env.example`. Validação real na VPS, após o DNS:

```bash
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile
curl -sI https://<DOMAIN>            # esperar 200 + Strict-Transport-Security
curl -sI https://api.<DOMAIN>/health # esperar 200
```
