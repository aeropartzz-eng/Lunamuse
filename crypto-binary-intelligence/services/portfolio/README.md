# Portfolio Manager — stub

- **Camada:** Camada 5
- **Fase:** Fase 15 — EXE-007/EXE-011

Acompanhamento de posições, saldos, exposição e snapshots de portfólio; reconciliação com a exchange após qualquer falha de backend.

Em falha do backend: bloquear novas entradas, não presumir cancelamento de ordens, consultar ordens/saldo/posições ao retornar e reconciliar o estado (§10).

## Estado atual

Esqueleto: nenhuma lógica implementada. Este diretório marca o lugar do serviço na arquitetura (especificação v4.1, §2 e §12).
