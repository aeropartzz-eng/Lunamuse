"""RPC/WebSocket públicos — somente leitura (Fase 6 — DEX-002…DEX-004).

Clientes JSON-RPC sem chave de API, com failover entre endpoints
públicos. Nenhum envio de transação, assinatura ou conexão de
carteira existe neste pacote.

Módulos:
- :mod:`evm_rpc`: BNB Chain (56), Ethereum (1), Base (8453).
- :mod:`solana_rpc`: Solana mainnet.

WebSocket (assinatura de logs/swaps em tempo real) fica para a Fase 7
(Market Data Engine); aqui o foco é leitura pontual e triagem.
"""
