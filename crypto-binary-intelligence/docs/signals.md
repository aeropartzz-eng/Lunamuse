# Sinais e distribuição — Crypto & Binary Intelligence

> Resumo da especificação **v4.1, §9 e §14 (Fase 14)**.

## Ciclo de vida do sinal

```
DETECTED -> VALIDATING -> APPROVED -> PUBLISHED -> ACTIVE -> CLOSED
```

Também pode terminar como **INVALIDATED** ou **EXPIRED**.

- **DETECTED** — estratégia/modelo detectou a oportunidade.
- **VALIDATING** — validação de dados, probabilidade calibrada,
  spread/liquidez e risco.
- **APPROVED** — passou nos filtros; pronto para publicar.
- **PUBLISHED** — distribuído aos canais.
- **ACTIVE** — dentro da validade, acompanhado.
- **CLOSED** — resultado registrado (atingiu alvo/stop ou expirou).
- **INVALIDATED** — dados ou premissas invalidados.
- **EXPIRED** — validade vencida sem execução.

## Campos mínimos do sinal

- `signal_id`, `exchange`, `market`, `symbol`, `timeframe`
- `direction`
- `strategy_id` e versão, `model_version`
- timestamps de origem e recebimento
- preço de referência
- entrada, stop e alvo (quando aplicáveis)
- **probabilidade calibrada**
- validade
- spread e liquidez
- justificativas
- status
- resultado

## Canais de distribuição

1. **Telegram Bot** (Fase 14 — SIG-004)
2. **WhatsApp Business Platform oficial** (Fase 14 — SIG-005)
3. **Painel web** (Fase 14 — SIG-006)
4. **API externa** (Fase 14 — SIG-007 WebSockets)

O **TradingView** pode enviar alertas por webhook HTTPS
(`POST /v1/webhooks/tradingview`). O endpoint deve validar e
enfileirar rapidamente; a análise pesada ocorre de forma assíncrona.
**Webhook é fonte complementar, não dependência única.**

> **Decisão do Will (2026-11-13): Telegram e WhatsApp ficam em
> stand-by.** Os dois canais continuam listados e aparecem no painel
> web como opcionais, com o campo para adicionar a API (token do bot /
> credenciais do WhatsApp Business) — mas nada é conectado agora e
> nada é automático: quando ele decidir usar, a API é colocada
> manualmente. Sem token, sem cadastro, sem envio.

## Regras

- **Deduplicação** de sinais (SIG-003): o mesmo sinal não é publicado
  duas vezes.
- **Registro de entregas e falhas** (SIG-008): toda distribuição é
  auditável.
- **WAIT / NO TRADE**: com dados ruins, probabilidade não calibrada ou
  expectativa insuficiente, o sistema não publica sinal.
- **Meta de 85%** (objetivo de pesquisa, não promessa): vale para
  sinais seletivos, sempre com cobertura, intervalo de confiança de
  95%, expectativa líquida, custos e desempenho fora da amostra.
  - Binárias: mín. 1.000 resultados fora da amostra.
  - Scalping cripto: mín. 500 operações fora da amostra por
    estratégia; Profit Factor de referência > 1,3; Sharpe de
    referência > 1,5; drawdown de referência < 10%.
- Sinais **não executam ordens sozinhos**: a execução passa pelo Risk
  Engine e pelo Execution Engine, e o LIVE está bloqueado até a
  homologação (Fase 15, EXE-014). Ver `docs/risk-policy.md`.
