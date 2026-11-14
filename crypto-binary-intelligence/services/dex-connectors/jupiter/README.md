# Jupiter — implementado, tier Lite (DEX-007)

- Docs: https://dev.jup.ag/
- Tier Lite público, sem chave: https://lite-api.jup.ag (0,5 req/s).
- Somente leitura: Price API **v3** (`/price/v3?ids=...`) e Quote API v1
  (`/swap/v1/quote` — simulação de rota/slippage; o endpoint `/swap`
  que constrói transação NÃO é chamado).
- Sem pares próprios: descoberta via DEX Screener (DEX-001).
- Smoke ao vivo em 2026-11-13: preço SOL US$ 79,83 (OK).
