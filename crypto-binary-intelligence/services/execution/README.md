# Execution Engine — stub

- **Camada:** Camada 5
- **Fase:** Fase 15 — EXE-001…EXE-014

Interface universal de execução, Order Manager, Position Manager, idempotência, reconciliação. Modos: RESEARCH, BACKTEST, PAPER, TESTNET, LIVE.

TRAVA: este scaffold NÃO contém código de execução real de ordens. LIVE desabilitado por padrão; o sistema nunca muda sozinho para LIVE (EXE-014). API key sem saque, restrição de IP, kill switch, reconciliação obrigatória (§10).

## Estado atual

Esqueleto: nenhuma lógica implementada. Este diretório marca o lugar do serviço na arquitetura (especificação v4.1, §2 e §12).
