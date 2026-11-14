# Raydium — implementado (DEX-006)

- Docs: https://docs.raydium.io/
- API v3 pública, sem autenticação: https://api-v3.raydium.io
  (`/pools/info/mint`, `/pools/info/ids`, `/pools/info/list`,
  `/mint/price`). Só o fórum exige `ray-token` — fora do escopo.
- Sem busca por símbolo na API v3: descoberta via DEX Screener (DEX-001).
- Smoke ao vivo em 2026-11-13: pools de BONK retornaram 2 pools (OK).
  (`/pools/info/list` retornou HTTP 500 uma vez — transitório.)
