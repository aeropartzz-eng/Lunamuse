# apps/notifier — Distribuição de sinais (stub)

Serviço de notificações (Camada 6, especificação v4.1, Fase 14):

- **SIG-004** — Telegram Bot (Bot API).
- **SIG-005** — WhatsApp Business Platform **oficial** (Meta).
- **SIG-008** — Registro de entregas e falhas.

## Estado atual: stub

Nenhum canal está implementado. As credenciais (`TELEGRAM_BOT_TOKEN`,
`WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`) ficam no `.env`
e só são preenchidas na Fase 14.

## Regras do documento

- Sinais seguem o ciclo DETECTED → VALIDATING → APPROVED → PUBLISHED →
  ACTIVE → CLOSED (ou INVALIDATED / EXPIRED) — ver `docs/signals.md`.
- O TradingView é fonte complementar por webhook; nunca dependência única.
- **Não usar automação de WhatsApp por navegador** — só a API oficial.
- Toda entrega (ou falha) é registrada para auditoria.
