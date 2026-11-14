# Fase 6 — DEX e Crypto Shield — Matriz de fontes públicas

Data da verificação: **2026-11-13**. Somente leitura pública, sem
nenhuma chave de API. Execução continua bloqueada (403) e o scaffold
força RESEARCH quando `EXECUTION_MODE=LIVE` — trava preservada.

## DEX — o que funciona sem chave

| Fonte | Endpoint | Verificação ao vivo (13/11/2026) |
|---|---|---|
| DEX Screener | `api.dexscreener.com` — search, token-pairs, pairs, profiles, boosts | ✅ 200 — busca `SOL`: 30 pares; busca `BONK`: 30 pares (1º: Orca, liq US$ 258.805) |
| Raydium API v3 | `api-v3.raydium.io` — pools/info/mint, ids, list; mint/price | ✅ 200 — pools de BONK: 2 pools. `/pools/info/list` retornou HTTP 500 uma vez (transitório) |
| Jupiter Lite | `lite-api.jup.ag` — Price v3, Quote v1 | ✅ 200 — preço SOL US$ 79,83; quote SOL→USDC com `priceImpactPct` |
| PancakeSwap | RPC BSC (par V2 on-chain) | ✅ Leitura via `eth_call` (reservas, LP queimado) |
| Uniswap | RPC Ethereum/Base (pool V2/V3 on-chain) | ✅ Leitura via `eth_call` (`getReserves`, `slot0`, `liquidity`) |
| RPC BSC | dataseeds oficiais (binance.org, defibit, ninicoin) | ✅ 200 — `eth_blockNumber` 133.328.307 |
| RPC Solana | `api.mainnet-beta.solana.com`, `solana-rpc.publicnode.com` | ✅ 200 — `getSlot` 468.877.424 |
| RPC Ethereum | `cloudflare-eth.com`, `ethereum-rpc.publicnode.com` | ✅ 200 — `eth_chainId` 0x1 |
| RPC Base | `mainnet.base.org` | ✅ 200 — `eth_chainId` 0x2105 |

## DEX — bloqueado / limitado (aguardando o Will)

| Fonte | Motivo |
|---|---|
| PancakeSwap Aggregator API (`hub-gateway.pancakeswap.com`) | Exige `x-secure-token` (token de API) |
| Uniswap — The Graph gateway / Uniswap Labs API | Exigem API key |
| Ankr public RPC (`rpc.ankr.com/*`) | **Passou a exigir API key** (testado: "Unauthorized: You must authenticate...") — removido das listas |
| eth.llamarpc.com | Instável (HTTP 525 Cloudflare no teste) — mantido como último fallback |
| OnFinality público (Base) | HTTP 429 frequente (limite do plano gratuito) — mantido como fallback |
| Top holders EVM | Sem RPC público; exige indexador com chave (BscScan/Etherscan) |

## Crypto Shield — fontes externas (SEC-006)

| Fonte | Verificação ao vivo (13/11/2026) |
|---|---|
| GoPlus Token Security | ✅ 200 — USDT (Ethereum): `is_honeypot: 0`, free sem chave, 100/min |
| RugCheck (Solana) | ✅ 200 — summary de BONK: `score: 101`, `lpLockedPct` presente; report em cache gratuito sem chave |
| Bubblemaps legada (`api-legacy.bubblemaps.io/map-metadata`) | ⚠️ HTTP 500 no teste (instável); API nova exige chave — bloqueada |
| Solana RPC (holders + authorities) | ✅ `getTokenLargestAccounts` (Top 20), parse SPL Mint (mint/freeze authority), criador via 1ª assinatura |

## Regras do Shield (§7)

- Dev/criador > 5% do suprimento → BLOQUEADO (aprovação automática
  bloqueada, revisão manual obrigatória).
- Dev 2–3% → atenção elevada; 3–5% → no mínimo REVISÃO.
- Top 10 > 30% → risco elevado (no mínimo REVISÃO); > 50% → BLOQUEADO.
- Sem dados → REVISÃO (nunca aprovar no escuro).
- Risco crítico (honeypot, rugged, dev > 5%, Top 10 > 50%) prevalece
  sobre qualquer score agregado.

## Evidência

- Testes: `python3 -m pytest tests/ -q` — 226 passed (70 antigos + 156 novos... ver saída no relatório).
- Smoke ao vivo: `scripts/smoke_phase6.py` — 5/5 OK na 2ª tentativa
  (1ª tentativa teve 1 falha transitória de proxy no DEX Screener;
  registrada honestamente em `data/reports/phase6_smoke_check.md`).
