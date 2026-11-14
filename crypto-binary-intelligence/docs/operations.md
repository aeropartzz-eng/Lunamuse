# Operações — Crypto & Binary Intelligence

> Resumo da especificação **v4.1, §16 e §17**, e do cronograma
> (Fases 0–15 e expansão, semanas 17–28).

## Subir e parar o ambiente

```bash
cp .env.example .env        # preencher senhas obrigatórias
docker compose config       # validar (não sobe nada)
docker compose up -d        # subir serviços centrais
docker compose ps           # estado dos containers
docker compose logs -f api  # logs da API
docker compose down         # parar (volumes preservados)
docker compose down -v      # parar e apagar volumes (dados locais!)
```

Portas (em `127.0.0.1`): API `8000` · painel `3000` · Prometheus
`9090` · Grafana `3001` · PostgreSQL `5432` · Redis `6379` ·
NATS `4222`/`8222`.

## Métricas (§16)

### Infraestrutura

CPU, RAM, disco, I/O e rede; estado dos containers; reinicializações;
filas e mensagens pendentes.

### Mercado

Última mensagem por exchange; latência; gaps; mensagens por segundo;
eventos descartados; atraso de candles; qualidade do Order Book.

### Estratégia

Sinais por estratégia; aprovação e recusa; coverage; Win Rate;
Expectancy; Profit Factor; Drawdown; Brier Score; Log Loss; Concept
Drift.

### Execução

Ordens solicitadas/aceitas/rejeitadas; fills parciais; slippage;
taxas; posições divergentes; falhas de reconciliação.

## Alertas (§16)

- Exchange desconectada.
- Feed atrasado.
- Banco indisponível.
- Disco acima do limite.
- Fila acumulada.
- Modelo degradado.
- Estratégia desativada.
- Ordem rejeitada.
- Posição divergente.
- **Kill switch acionado.**

## Critérios de aceite (§17)

Uma fase só é concluída **com evidência**: logs, testes, relatórios,
prints ou resultados automatizados. **Código escrito não é, sozinho,
critério de aceite.**

| Área | Aceite |
|---|---|
| Infraestrutura | VPS segura, Docker funcional, backups restauráveis, HTTPS ativo, monitoramento operacional |
| Conectores | Exchanges prioritárias conectadas, limites respeitados, reconexão testada, gaps detectados, dados normalizados |
| Market Data | Trades recebidos, candles reproduzíveis, Order Book sincronizado, histórico consultável, dados inválidos rejeitados |
| Inteligência | Indicadores testados, padrões testados, estratégias versionadas, backtesting cronológico, métricas fora da amostra |
| Sinais | Registro completo, deduplicação, expiração e invalidação, Telegram funcionando, WhatsApp oficial funcionando, painel atualizado |
| Execução | Testnet homologada, idempotência, reconciliação, Risk Engine, Kill Switch, sem permissão de saque, **LIVE desabilitado por padrão** |

## Backup (Fase 1 — INF-008)

- Backup do PostgreSQL/TimescaleDB + Object Storage.
- **Teste de restauração obrigatório** — backup sem restauração
  comprovada não conta como aceite.
- Retenção (§11): trades 7 dias; Order Book 2–7 dias; candles 1s 30
  dias; candles 1m/5m 24 meses; timeframes maiores 3+ anos; sinais,
  ordens e auditoria permanentes.
- Ver `infrastructure/backup/README.md` e `backup.sh` (placeholder).

## Resiliência (semana 23 da expansão)

Simular e testar recuperação de: queda da VPS, falha de exchange,
falha de banco, perda de rede. Entrega: relatório de continuidade.

## Carga (semana 24 da expansão)

Medir CPU, RAM, disco e rede; otimizar assinaturas; ajustar retenção;
testar limites. Entrega: relatório de capacidade.

## Segurança operacional

- SSH por chave; root por senha desabilitado; firewall; portas
  limitadas (Fase 1 — INF-003).
- Ambientes development/staging/production com credenciais separadas
  (INF-007).
- `.env` nunca é commitado (ver `.gitignore`).
- Chaves de exchange sem saque e com restrição de IP.
- Segredos fora do código e dos logs.

## Regulatório (Fase 0 — GOV-007; §18)

- Identificar plataformas, verificar oferta e elegibilidade, bloquear
  integração irregular.
- Referências: CVM (https://www.gov.br/cvm/pt-br) e CFTC
  (https://www.cftc.gov/).
- Binárias: execução real só após validação jurídica completa
  (semana 22 da expansão).
