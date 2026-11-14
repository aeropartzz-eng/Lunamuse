# Dexscreener — implementado (DEX-001)

- Docs: https://docs.dexscreener.com/api/reference
- API pública, sem chave: 300 req/min (pares/busca), 60 req/min (perfis/boosts).
- Endpoints: `/latest/dex/search`, `/token-pairs/v1/{chain}/{token}`,
  `/latest/dex/pairs/{chain}/{pair}`, `/tokens/v1/{chain}/{token}`,
  `/token-profiles/latest/v1`, `/token-boosts/latest/v1`.
- Descoberta e triagem apenas — não é feed de trades em tempo real (§3).
- Smoke ao vivo em 2026-11-13: busca `BONK` retornou 30 pares (OK).
