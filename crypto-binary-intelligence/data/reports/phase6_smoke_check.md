# Smoke check ao vivo — Fase 6 (DEX e Crypto Shield)

Data: **2026-11-13** (manhã, -03). Script: `scripts/smoke_phase6.py`
(somente leitura pública, sem chave, sem transação).

## 1ª tentativa

| Fonte | Resultado |
|---|---|
| DEX Screener search BONK | **FALHA** — `ProxyError: Unable to connect to proxy, RemoteDisconnected` (falha transitória de proxy do sandbox; o mesmo endpoint respondeu 200 via curl minutos antes) |
| Raydium pools BONK | OK — 2 pools |
| Jupiter price SOL (v3) | OK — US$ 79,8356883580706 |
| BSC RPC blockNumber | OK — bloco 133.328.293 |
| Solana RPC getSlot | OK — slot 468.877.394 |

## 2ª tentativa (re-rodada sem mudar nada)

| Fonte | Resultado |
|---|---|
| DEX Screener search BONK | **OK** — 30 pares; 1º: Orca, BONK, liq US$ 258.805,21 |
| Raydium pools BONK | OK — 2 pools |
| Jupiter price SOL (v3) | OK — US$ 79,83463153981022 |
| BSC RPC blockNumber | OK — bloco 133.328.307 |
| Solana RPC getSlot | OK — slot 468.877.424 |

**Smoke Fase 6: 5/5 OK** (a falha da 1ª tentativa foi transitória de
rede/proxy, não da integração — registrada aqui honestamente).

## Outras sondas ao vivo (13/11/2026, curl)

- DEX Screener search `SOL`: HTTP 200, 30 pares; 1º SOL/USDC (Base,
  Aerodrome), preço US$ 79,71, liquidez US$ 88.546,38.
- GoPlus `token_security/1` (USDT): HTTP 200, `is_honeypot: 0`.
- RugCheck summary (BONK): HTTP 200, `score: 101`, `lpLockedPct` presente.
- Raydium `/pools/info/list`: HTTP 500 uma vez (transitório);
  `/pools/info/mint`: HTTP 200.
- Jupiter quote SOL→USDC: HTTP 200, `outAmount` + `priceImpactPct`.
- Jupiter Price API: **v2 retornou 404** — a versão atual é a **v3**
  (`/price/v3`, dict plano `{mint: {usdPrice}}`); adapter corrigido.
- Bubblemaps legada: HTTP 500 (instável no dia).
- Ankr public RPC: passou a exigir API key (401 "Unauthorized") —
  removido das listas de endpoints.
- eth.llamarpc.com: HTTP 525 (instável) — último fallback.
- OnFinality público (Base): HTTP 429 — fallback apenas.
- BSC dataseeds (3), Solana mainnet-beta/publicnode, Cloudflare ETH,
  PublicNode ETH, Base mainnet: todos HTTP 200.
