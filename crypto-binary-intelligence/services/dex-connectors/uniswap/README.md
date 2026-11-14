# Uniswap — avaliado + leitura via RPC (DEX-007)

- Docs: https://docs.uniswap.org/
- **Sem API REST pública sem chave**: subgrafo via gateway The Graph
  exige API key; API Uniswap Labs (`api.uniswap.org`) exige chave.
  Ambas BLOQUEADAS aguardando decisão/chave do Will.
- Viável sem chave (implementado): leitura de pools V2/V3 on-chain via
  RPC público (`getReserves`, `slot0`, `liquidity`); descoberta via
  DEX Screener (DEX-001).
