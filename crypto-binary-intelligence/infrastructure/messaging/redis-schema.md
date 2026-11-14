# Redis — schema de chaves (Fase 2 — DB-003)

Fonte: especificação v4.1, §§2, 7, 11. Redis no compose: `redis:7-alpine`,
senha obrigatória (`REDIS_PASSWORD` do `.env`), `--maxmemory 256mb`
(`REDIS_MAXMEMORY`), política `allkeys-lru`, AOF ligado. Orçamento de
RAM do documento: 250 MB. O Redis é **estado quente e cache** — tudo aqui
pode ser reconstruído a partir do Postgres/NATS; nada aqui é fonte única
de verdade.

Convenção: chaves em minúsculas, separadas por `:`. TTL em segundos.
Prefixo `cbi:` em todas as chaves do projeto.

## 1. Último ticker por símbolo

| Chave | Tipo | Conteúdo | TTL |
|---|---|---|---|
| `cbi:ticker:{exchange}:{symbol}` | HASH | `price`, `bid`, `ask`, `volume_24h`, `ts` (epoch ms da origem), `received_at` | 60 s (renovado a cada tick; se expirar, o feed está parado) |
| `cbi:ticker:{exchange}:{symbol}:stale` | — | (ausência da chave acima = feed sem dados; o detector de gaps lê isso) | — |

Leitura: `HGETALL`. O painel e o scanner leem daqui, não do Postgres.
Escrita: só o normalizador/market-data.

## 2. Snapshot de order book

| Chave | Tipo | Conteúdo | TTL |
|---|---|---|---|
| `cbi:book:{exchange}:{symbol}` | HASH | `bids` (JSON, top N), `asks` (JSON, top N), `best_bid`, `best_ask`, `spread`, `mid`, `seq`, `ts` | 30 s (renovado a cada update; Nível 3: até 20 livros aprofundados) |
| `cbi:book:{exchange}:{symbol}:seq` | STRING | última sequência aplicada (detecção de gap, §5) | 30 s |

Snapshots completos vão para `orderbook_snapshots` no Postgres; aqui fica
só o estado corrente para cálculo de spread/imbalance.

## 3. Contadores de rate limit

| Chave | Tipo | Conteúdo | TTL |
|---|---|---|---|
| `cbi:rl:{exchange}:{endpoint}:{janela}` | STRING (INCR) | nº de chamadas na janela | igual à janela (ex.: 60 s, 600 s) |
| `cbi:rl:notify:{channel}:{destino}` | STRING (INCR) | envios de notificação (anti-spam Telegram/WhatsApp) | 3600 s |

Padrão: `INCR` + `EXPIRE` na primeira escrita (janela fixa). Quando o
contador atinge o limite documentado da exchange, o conector pausa e
registra `connection_status`/`system_events` — nunca estoura o limite.

## 4. Deduplicação de sinais

| Chave | Tipo | Conteúdo | TTL |
|---|---|---|---|
| `cbi:signal:dedup:{strategy_code}:{symbol}:{timeframe}:{direcao}:{bucket_minuto}` | STRING | `signal_id` (SET NX) | 3600 s |
| `cbi:signal:seen:{signal_id}` | STRING | `1` (SET NX, marca sinal já publicado) | até `valid_until` do sinal (máx. 86400 s) |

Padrão: `SET key value NX EX ttl` — se já existir, o sinal é duplicata e
não é republicado (§14 SIG-003). O registro canônico continua em
`strategy_signals` (Postgres).

## 5. Cache (geral)

| Chave | Tipo | Conteúdo | TTL |
|---|---|---|---|
| `cbi:cache:candles:{exchange}:{symbol}:{timeframe}` | STRING (JSON) | últimas N velas fechadas | 300 s |
| `cbi:cache:indicators:{exchange}:{symbol}:{timeframe}:{indicador}` | STRING (JSON) | último valor calculado | 300 s |
| `cbi:cache:shield:{network}:{contrato}` | STRING (JSON) | score/estado APROVADO/REVISÃO/BLOQUEADO do Crypto Shield (§7) | 3600 s |
| `cbi:cache:funding:{exchange}:{symbol}` | HASH | `rate`, `mark`, `index`, `next_funding` | 600 s |
| `cbi:cache:oi:{exchange}:{symbol}` | STRING | open interest corrente | 600 s |

Cache é só leitura: em `MISS`, recalcular a partir do Postgres e
repopular. Nunca servir dado de cache como se fosse dado fresco sem
checar o `ts` gravado junto.

## 6. Locks e flags operacionais

| Chave | Tipo | Conteúdo | TTL |
|---|---|---|---|
| `cbi:lock:{servico}:{recurso}` | STRING | dono do lock (SET NX PX) | 30000 ms (lock distribuído; renovar enquanto segura) |
| `cbi:flag:kill_switch` | STRING | `1` quando o kill switch está armado (§10) | sem TTL (só sai por ação humana) |
| `cbi:flag:feed_invalid:{exchange}` | STRING | `1` enquanto o feed estiver inválido (bloqueia novas entradas, §10) | 300 s (renovado pelo detector de gaps) |

## O que NUNCA vai para o Redis

- **Segredos e chaves de API** (exchange, Telegram, WhatsApp, RPCs).
- **Senhas** (Postgres, Redis, Grafana) e **tokens** de qualquer tipo.
- **Chaves privadas / seeds de carteira** (execução DEX, §10).
- **Dados pessoais** além do mínimo necessário (sem e-mail/senha de usuário).
- **Payloads completos de ordens com credencial** — a ordem em si vai
  para o NATS/Postgres sem nenhum segredo.

Motivo: o Redis tem AOF em disco e, por desenho, é estado quente
descartável; segredo nele é segredo persistido sem necessidade. As
credenciais vivem no `.env` (fora do repo) e, no futuro, em cofre.

## Comandos de verificação (na VPS)

```bash
docker exec cbi-redis redis-cli -a "$REDIS_PASSWORD" --no-auth-warning INFO memory
docker exec cbi-redis redis-cli -a "$REDIS_PASSWORD" --no-auth-warning --scan --pattern 'cbi:ticker:*' | head
docker exec cbi-redis redis-cli -a "$REDIS_PASSWORD" --no-auth-warning GET 'cbi:flag:kill_switch'
```
