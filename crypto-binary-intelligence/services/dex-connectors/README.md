# services/dex-connectors — Conectores DEX / On-chain (Fase 6 — implementado)

Camada 2 — Ingestão (especificação v4.1, Fase 6 — DEX-001…DEX-007).

| Fonte | Tarefa | Papel | Status (2026-11-13) |
|---|---|---|---|
| DEX Screener | DEX-001 | Descoberta de pares, volume e liquidez agregados | ✅ Público, sem chave (300 req/min); smoke OK |
| PancakeSwap | DEX-005 | Pools e swaps da BNB Chain | ✅ Via RPC público BSC (V2 on-chain); Aggregator API exige token — bloqueado |
| Raydium | DEX-006 | Pools e swaps da Solana | ✅ API v3 pública, sem auth; smoke OK |
| Uniswap | DEX-007 | Ethereum, Base e redes suportadas | ⚠️ Sem REST público sem chave (The Graph/Uniswap Labs exigem chave); leitura V2/V3 via RPC público |
| Jupiter | DEX-007 | Agregação no ecossistema Solana | ✅ Lite keyless (0,5 req/s); preço v3 + quote v1; smoke OK |

RPC/WebSocket: BNB Chain (DEX-002), Solana (DEX-003), Ethereum/Base
(DEX-004) — ver `rpc/` (somente leitura; nenhum envio de transação).

## Regras

- **API agregadora serve para descoberta e triagem** — não presumir que
  seja feed de trades em tempo real. Para eventos on-chain, usar RPC,
  WebSocket ou indexador adequado (§3).
- Somente leitura pública, sem nenhuma chave de API. Nenhum método
  envia transação, assina nada ou conecta carteira.
- Execução DEX (semana 19 da expansão) é simulação: rota, gas, slippage
  e liquidez — com Crypto Shield obrigatório e sem transferências
  irrestritas (§10).

## Arquivos

- `dex_http.py` — cliente HTTP compartilhado (timeout, retry, throttle).
- `dex_models.py` — `DexPair` normalizado + normalização DEX Screener.
- `amm.py` — matemática AMM (constant product) p/ simulação de venda.
- `dexscreener/`, `pancakeswap/`, `raydium/`, `uniswap/`, `jupiter/` — adapters.
- `rpc/` — `evm_rpc.py` (BSC/Ethereum/Base) e `solana_rpc.py`.

Detalhes e matriz de fontes: `docs/dex-crypto-shield.md`.
