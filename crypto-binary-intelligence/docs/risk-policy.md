# Política de risco — Crypto & Binary Intelligence

> Resumo da especificação **v4.1, §0 (premissas), §10 e §17**.
> **Estes limites são parâmetros de engenharia provisórios, não
> recomendação financeira.**
> Fase 0 — GOV-004. Versão 1.0 — 13/11/2026.
> Status: **rascunho aguardando aprovação formal do responsável**
> (ver `governance-checklist.md`).

## Princípios

1. **Nenhuma oportunidade vale comprometer a integridade dos dados, a
   segurança das credenciais ou os limites de risco.**
2. **Na ausência de dados confiáveis ou de vantagem estatística
   demonstrada, a decisão correta do sistema é NÃO OPERAR.**
3. O sistema prefere **WAIT / NO TRADE** quando os dados forem ruins,
   a probabilidade não estiver calibrada ou a expectativa for
   insuficiente.
4. Nenhuma estratégia é aprovada somente por backtest otimizado
   (validação fora da amostra é obrigatória).
5. A IA generativa não está no caminho crítico: as regras
   determinísticas de risco funcionam sem APIs externas.

## Modos de execução (§10)

| Modo | Significado |
|---|---|
| RESEARCH | Pesquisa e desenvolvimento — único modo do scaffold |
| BACKTEST | Testes com dados históricos |
| PAPER | Simulação em tempo real, sem dinheiro real |
| TESTNET | Execução em ambientes de teste das exchanges |
| LIVE | Dinheiro real — **bloqueado até homologação** |

**O sistema nunca muda sozinho para LIVE.** LIVE exige aprovação
técnica, estatística, operacional e regulatória + autorização expressa
do responsável (Fase 15, EXE-014).

## Limites iniciais para homologação (§10)

| Limite | Valor |
|---|---|
| Risco por operação | 0,25% do patrimônio |
| Limite diário de perda | 1% |
| Alavancagem | desabilitada |
| Posições simultâneas | até 3 |
| Feed inválido | bloquear novas entradas |

Se a ordem mínima exceder o risco permitido, **rejeitar a operação**.

## Controles obrigatórios (§10)

- API key **sem saque**; restrição de IP quando disponível.
- Segredos fora do código e dos logs.
- Limites por operação e por dia; limite de exposição; limite de
  posições simultâneas; limite de slippage.
- Idempotência (a mesma ordem nunca é enviada duas vezes).
- Circuit breaker e kill switch.
- Reconciliação obrigatória (ordens, fills, saldo e posições).

## Fluxo de execução (§10)

1. Receber sinal aprovado.
2. Revalidar dados e validade.
3. Verificar saúde do feed.
4. Consultar saldo e exposição.
5. Validar limites de risco.
6. Validar quantidade mínima e precisão.
7. Simular slippage.
8. Calcular tamanho da ordem.
9. Enviar pela API oficial.
10. Confirmar ordem.
11. Acompanhar fills.
12. Atualizar posição.
13. Verificar proteções de saída.
14. Reconciliar com a exchange.
15. Auditar resultado.

## Falha do backend (§10)

- Bloquear novas entradas.
- **Não presumir cancelamento de ordens.**
- Consultar ordens, saldo e posições ao retornar.
- Reconciliar o estado.
- Manter o bloqueio se houver divergência.
- Utilizar proteções nativas da exchange quando disponíveis.

## Execução DEX (§10)

- Serviço e carteira separados; chave protegida.
- Simulação de transação; verificação de rota, contrato, gas e
  slippage.
- **Crypto Shield obrigatório.**
- Sem transferências irrestritas.

## Opções binárias (§10)

Motor **isolado** do motor cripto. Antes de qualquer execução, validar:
legalidade, plataforma, API oficial, origem do preço, feed de
liquidação, timestamp, arredondamento, vencimento, payout, empate e
cancelamento. **Se não for possível validar, permitir pesquisa e
simulação, mas bloquear execução.**

Nunca usar automação de binárias por navegador como substituto de API
oficial (fora do escopo inicial, §1).

## Meta de 85% (§0, §8)

Objetivo de **pesquisa** para sinais seletivos — **não é promessa de
acerto, lucro ou rentabilidade**. Precisão deve ser avaliada junto com
cobertura, expectativa matemática, custos, intervalo de confiança e
desempenho fora da amostra. Um sistema pode ter alta precisão e
cobertura muito baixa; ambos devem ser informados. Detalhamento em
`protocol-85.md`.

## Alteração de limites

Os limites desta política são provisórios e só mudam por decisão
documentada e aprovada pelo responsável, registrada em auditoria
(quem alterou, quando, qual valor anterior e posterior, e com base
em qual evidência). Nenhum resultado de backtest ou de operação
altera limites automaticamente. A alteração de limites é uma das
ações que exigem aprovação humana obrigatória
(`execution-policy.md`, §3).

## Eventos de risco e auditoria

Toda rejeição por limite, bloqueio por feed inválido, acionamento de
circuit breaker ou de kill switch e toda divergência de
reconciliação é registrada como evento de risco
(tabelas `risk_events` e `reconciliation_events`, §13) e entra na
trilha de auditoria (`audit_logs`). Limite diário de perda atingido
encerra novas entradas no dia; o rearme é manual, com aprovação
humana.

## Cobertura GOV

Esta política atende **GOV-004** (política de risco — aceite: Risk
Policy versionada). Mapeamento completo GOV-001 a GOV-007 em
[`governance-checklist.md`](governance-checklist.md).
