# Checklist de governança — Fase 0 (GOV-001 a GOV-007)

> Fonte: especificação **v4.1 (13/11/2026), §14 (Fase 0)**.
> Versão 1.0 — 13/11/2026.
> Status: **rascunho aguardando aprovação formal do responsável.**
>
> Uma fase só é concluída **com evidência** (§17): logs, testes,
> relatórios, prints ou resultados automatizados. Código escrito não
> é, sozinho, critério de aceite.

## Mapeamento GOV-001 a GOV-007

| ID | Tarefa (§14) | Critério de aceite (§14) | Onde está atendido | Status |
|---|---|---|---|---|
| GOV-001 | Consolidar requisitos — revisar o documento-base, separar obrigatório e desejável, registrar dependências | Requisitos aprovados | Especificação v4.1 (documento-base); este checklist registra a consolidação da Fase 0 | Pendente de aprovação formal do responsável |
| GOV-002 | Definir cobertura — listar exchanges, listar mercados, registrar restrições regionais | Matriz de cobertura | `docs/exchanges.md` (CEX primeiro grupo + expansão, DEX, dados e timeframes) e §2 de `regulatory-review.md` (verificação por plataforma) | Pendente de aprovação formal; restrições regionais a confirmar por conector (Fases 4–5) |
| GOV-003 | Política de dados — definir timestamps, granularidade, retenção, gaps | Contrato de dados | `docs/data-policy.md` | Documento escrito; pendente de aprovação formal |
| GOV-004 | Política de risco — risco por operação, limite diário, exposição, alavancagem, bloqueios | Risk Policy versionada | `docs/risk-policy.md` (revisado e completado nesta fase — ver § "Alteração de limites" e § "Cobertura GOV") | Documento escrito; pendente de aprovação formal |
| GOV-005 | Política de execução — definir RESEARCH, BACKTEST, PAPER, TESTNET, LIVE; definir permissões; definir aprovação humana | Matriz de autorização | `docs/execution-policy.md` (§1 modos, §2 permissões por papel, §3 aprovação humana) | Documento escrito; pendente de aprovação formal e de definição formal dos papéis |
| GOV-006 | Protocolo de 85% — definir amostras, cobertura, intervalo de confiança, teste fora da amostra | Protocolo estatístico | `docs/protocol-85.md` | Documento escrito; pendente de aprovação formal |
| GOV-007 | Revisão regulatória — identificar plataformas, verificar oferta e elegibilidade, bloquear integração irregular | Matriz jurídica | `docs/regulatory-review.md` (§2 matriz de verificação por plataforma, §3 bloqueio de binárias, §4 referências CVM/CFTC) | Documento escrito; pendente de aprovação formal e de validação jurídica externa |

## Consistência com as travas do README

- **LIVE bloqueado:** `execution-policy.md` §1 — o sistema nunca
  muda sozinho para LIVE; o scaffold só aceita
  `EXECUTION_MODE=RESEARCH` e a API rejeita ordens com HTTP 403.
- **Binárias só pesquisa:** `execution-policy.md` §6 e
  `regulatory-review.md` §3 — motor isolado; execução bloqueada sem
  validação jurídica completa.
- **Meta de 85% é objetivo de pesquisa:** `protocol-85.md` §1 e §5
  e `risk-policy.md` — nunca apresentada como promessa.
- **Risco:** limites de `risk-policy.md` (0,25% por operação; 1%
  diário; alavancagem desabilitada; até 3 posições; feed inválido
  bloqueia novas entradas; ordem mínima acima do risco → rejeitar).
- **WAIT / NO TRADE:** `data-policy.md` §4 e `risk-policy.md` —
  dados ruins, probabilidade não calibrada ou expectativa
  insuficiente → não operar.

## Pendências que dependem de decisão do Will

1. **Aprovação formal** das cinco políticas (dados, risco, execução,
   protocolo do 85%, revisão regulatória) e deste checklist.
2. **Definição de responsáveis:** quem aprova mudanças de modo,
   limites e estratégias; papéis de autorização (§2 de
   `execution-policy.md`).
3. **Validação jurídica externa** da revisão regulatória
   (`regulatory-review.md` não é parecer jurídico).
4. Confirmação das **restrições regionais por plataforma** (GOV-002),
   a ser preenchida por conector nas Fases 4–5.
5. Tolerância documentada de **timestamp futuro por conector**
   (`data-policy.md` §1, item 2), a definir nas Fases 3–4.
