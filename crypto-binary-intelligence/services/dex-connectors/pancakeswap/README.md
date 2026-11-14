# Pancakeswap — implementado via RPC (DEX-005)

- Docs: https://developer.pancakeswap.finance/
- Leitura de pares V2 on-chain via RPC público BSC (`getReserves`,
  `token0`/`token1`, `totalSupply`, `balanceOf` p/ LP queimado).
- Sem busca pública sem chave: a API de info legada não é confiável e
  a Aggregator API exige `x-secure-token` — BLOQUEADO aguardando o Will.
  Descoberta via DEX Screener (DEX-001).
- Factory V2 (BSC): 0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73.
