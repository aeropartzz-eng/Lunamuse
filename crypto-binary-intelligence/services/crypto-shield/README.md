# Crypto Shield — Antifraude (Fase 6 — SEC-001…SEC-007 — implementado)

- **Camada:** Camada 4
- **Fase:** Fase 6 — SEC-001…SEC-007

Verificação de contrato (mint/freeze authority, funções administrativas, honeypot), liquidez (LP bloqueada/queimada, concentração, slippage) e holders (Top 10/20, participação do criador, clusters, bundlers). Resultado: APROVADO / REVISÃO / BLOQUEADO.

## Regras (§7)

- Criador ou carteira de controle com **mais de 5%** do suprimento bloqueia aprovação automática (BLOQUEADO) e exige revisão manual.
- Top 10 acima de **30%** = risco elevado (no mínimo REVISÃO); acima de 50% = BLOQUEADO.
- Dev acima de **2–3%** = atenção elevada; dev 3–5% = no mínimo REVISÃO.
- Sem dados suficientes: REVISÃO — nunca aprovar no escuro.
- **Risco crítico prevalece sobre qualquer score agregado.**
- Pools, burn addresses e carteiras técnicas só são excluídos do Top 10 após classificação documentada; vínculo entre carteiras só existe com evidência (origem comum de financiamento).

## Módulos

| Módulo | Papel |
|---|---|
| `crypto_shield.py` | `assess_token()` (puro, testável) + `ShieldAssessor` (coleta com degradação graciosa) |
| `shield_models.py` | `Holder`, `HolderAnalysis`, `LiquidityAnalysis`, `AuthorityAnalysis`, `SellSimulation`, `ShieldResult` |
| `shield_holders.py` | Top 10/20, dev share, clusters por funder (SEC-001…SEC-003) |
| `shield_liquidity.py` | LP/liquidez + simulação de venda AMM (SEC-004) |
| `shield_authorities.py` | Normalização GoPlus/RugCheck/RPC (SEC-005) |
| `shield_external.py` | GoPlus, RugCheck, Bubblemaps legada (SEC-006) |

## Fontes externas (SEC-006)

| Fonte | Status (2026-11-13) |
|---|---|
| GoPlus Token Security | ✅ Pública, sem chave (free, 100/min); testada ao vivo (USDT: honeypot 0) |
| RugCheck (Solana) | ✅ Report em cache gratuito, sem chave; testado ao vivo (summary OK, `lpLockedPct` presente) |
| Bubblemaps legada | ⚠️ API legada retornou HTTP 500 no teste; API nova exige chave — bloqueada aguardando o Will |
| Top holders EVM | ❌ Sem RPC público (exige indexador com chave — BscScan/Etherscan) — bloqueado; holders EVM ficam ausentes e o veredito tende a REVISÃO |

Detalhes e matriz completa: `docs/dex-crypto-shield.md`.
Evidência do smoke ao vivo: `data/reports/phase6_smoke_check.md`.
