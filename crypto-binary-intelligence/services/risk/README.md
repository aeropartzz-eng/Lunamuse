# Risk Engine — stub

- **Camada:** Camada 5
- **Fase:** Fase 15 — EXE-008

Position Sizing, Pre-trade Validation, limites por operação e por dia, exposição, posições simultâneas, slippage, circuit breaker e kill switch. Regras determinísticas — funcionam sem APIs externas (§2).

Limites iniciais de homologação: risco por operação 0,25% · perda diária máx. 1% · alavancagem desabilitada · até 3 posições simultâneas · feed inválido bloqueia novas entradas (§10).

## Estado atual

Esqueleto: nenhuma lógica implementada. Este diretório marca o lugar do serviço na arquitetura (especificação v4.1, §2 e §12).
