# Política de execução — Crypto & Binary Intelligence

> Fonte: especificação **v4.1 (13/11/2026), §0, §1, §10, §14 (Fase 15)
> e §17**.
> Fase 0 — GOV-005. Versão 1.0 — 13/11/2026.
> Status: **rascunho aguardando aprovação formal do responsável**
> (ver `governance-checklist.md`).
>
> **O sistema nunca muda sozinho para LIVE.** Execução real exige
> aprovação técnica, estatística, operacional e regulatória, além de
> autorização expressa do responsável (§0, premissa 4).

## 1. Modos de execução (§10)

| Modo | Significado | Dinheiro real | Como se entra |
|---|---|---|---|
| RESEARCH | Pesquisa e desenvolvimento | Não | Modo padrão do scaffold |
| BACKTEST | Testes com dados históricos | Não | Seleção explícita de modo |
| PAPER | Simulação em tempo real | Não | Seleção explícita de modo |
| TESTNET | Execução em ambientes de teste das exchanges | Não (fundos de teste) | Seleção explícita de modo |
| LIVE | Dinheiro real | **Sim** | **Somente** após homologação (EXE-014) + autorização expressa do responsável |

Regras:

1. O scaffold só aceita `EXECUTION_MODE=RESEARCH` e a API rejeita
   qualquer pedido de ordem com HTTP 403 (ver `README.md`).
2. **Transição de modo nunca é automática.** Nenhum resultado de
   backtest, de paper trading ou de testnet promove o sistema a LIVE.
3. LIVE exige, cumulativamente: aprovação técnica, aprovação
   estatística (protocolo do 85% — ver `protocol-85.md`),
   aprovação operacional, aprovação regulatória (ver
   `regulatory-review.md`) e **autorização expressa do
   responsável** (Fase 15, EXE-014).
4. A mudança para LIVE é uma ação administrativa auditada (quem
   autorizou, quando, com base em qual evidência) e reversível a
   qualquer momento pelo kill switch (§5).
5. Cada modo tem credenciais e ambientes separados (§14, INF-007:
   Development, Staging, Production, credenciais separadas).
   Credencial de produção nunca é usada em RESEARCH/BACKTEST/PAPER/
   TESTNET.

## 2. Permissões por papel (§13)

1. Autorização por função (role-based): autenticação forte, rate
   limiting, TLS, validação de payload, idempotência e proteção
   contra replay, auditoria administrativa (§13, Segurança).
2. Papéis a serem definidos formalmente pelo responsável (pendente —
   ver `governance-checklist.md`): no mínimo separar quem **opera/
   visualiza**, quem **aprova mudanças de modo e de limites** e quem
   **administra credenciais**. Nenhum papel acumula sozinho a
   autorização de LIVE e a guarda das credenciais de produção.
3. O endpoint de execução é protegido (§13); ordens só partem de
   sinais aprovados, após revalidação (§3).
4. Nenhuma permissão é concedida por padrão: acessos novos começam
   sem permissão de execução.

## 3. Aprovação humana obrigatória

1. **Aprovação humana é obrigatória** para:
   - mudar o modo de execução (em especial qualquer passo em
     direção a LIVE);
   - alterar limites de risco (`risk-policy.md`);
   - ativar/desativar estratégias em produção;
   - liberar execução em um novo mercado, exchange ou segmento
     (incluindo binárias — ver §6);
   - rearmar o sistema após kill switch ou circuit breaker.
2. A IA generativa **não está no caminho crítico de execução** (§2):
   regras determinísticas de risco funcionam sem APIs externas, e
   nenhuma decisão de execução depende de aprovação gerada por
   modelo.
3. Sinais seguem o ciclo DETECTED → VALIDATING → APPROVED →
   PUBLISHED → ACTIVE → CLOSED (podendo ser INVALIDATED ou EXPIRED)
   (§9); só sinais APPROVED chegam ao motor de execução.

## 4. Fluxo de execução (§10)

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

Qualquer falha em 2–8 **rejeita a operação antes do envio**. A
rejeição é registrada com o motivo (auditoria).

## 5. Controles obrigatórios (§10)

| Controle | Regra |
|---|---|
| Chave sem saque | Toda API key é criada **sem permissão de saque** |
| Restrição de IP | Aplicada quando a exchange oferecer |
| Segredos | Fora do código e dos logs; nunca em repositório |
| Limites | Por operação e por dia; exposição; posições simultâneas; slippage (valores em `risk-policy.md`) |
| Idempotência | A mesma ordem nunca é enviada duas vezes; proteção contra replay |
| Circuit breaker | Interrompe novas entradas por fonte/estratégia em falha |
| Kill switch | Para novas entradas imediatamente; acionamento auditado; rearme só com aprovação humana |
| Reconciliação | Obrigatória: ordens, fills, saldo e posições conferidos com a exchange |

Falha do backend (§10):

- Bloquear novas entradas.
- **Não presumir cancelamento de ordens.**
- Consultar ordens, saldo e posições ao retornar.
- Reconciliar o estado.
- Manter o bloqueio se houver divergência.
- Utilizar proteções nativas da exchange quando disponíveis.

## 6. Execução DEX e binárias (§10)

**DEX:**

- Serviço e carteira separados; chave protegida.
- Simulação de transação; verificação de rota, contrato, gas e
  slippage.
- **Crypto Shield obrigatório.**
- Sem transferências irrestritas.

**Binárias — motor isolado:**

- Motor de binárias **isolado** do motor cripto.
- Antes de qualquer execução, validar: legalidade, plataforma, API
  oficial, origem do preço, feed de liquidação, timestamp,
  arredondamento, vencimento, payout, empate e cancelamento.
- **Se não for possível validar, permitir pesquisa e simulação, mas
  bloquear execução.**
- Nunca usar automação de binárias por navegador como substituto de
  API oficial (fora do escopo inicial, §1).
- Ver `regulatory-review.md` e a semana 22 da expansão (relatório de
  viabilidade do feed binário; execução bloqueada se houver lacunas).

## 7. Cobertura GOV

Esta política atende **GOV-005** (política de execução: modos,
permissões, aprovação humana — aceite: matriz de autorização).
Mapeamento completo GOV-001 a GOV-007 em
[`governance-checklist.md`](governance-checklist.md).
