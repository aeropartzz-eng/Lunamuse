# Exchanges e fontes — Crypto & Binary Intelligence

> Resumo da especificação **v4.1, §3 e §5**.

## CEX — primeiro grupo (Fases 4–5)

| Exchange | Tarefa | Fase | Docs |
|---|---|---|---|
| Binance | CEX-001 — mercados, trades, ticker, candles e book | 4 | https://developers.binance.com/docs/binance-spot-api-docs |
| Bybit | CEX-002 — Spot e contratos suportados | 4 | https://bybit-exchange.github.io/docs/v5/intro |
| OKX | CEX-003 — instrumentos, trades e books | 4 | https://www.okx.com/docs-v5/en/ |
| Coinbase Advanced | CEX-007 | 5 | ✅ implementado — ver `services/exchange-connectors/coinbase/README.md` | https://docs.cdp.coinbase.com/advanced-trade/docs/welcome |
| Kraken | CEX-008 | 5 | ✅ implementado — ver `services/exchange-connectors/kraken/README.md` | https://docs.kraken.com/api/ |
| Bitget | CEX-009 | 5 | ✅ implementado — ver `services/exchange-connectors/bitget/README.md` | https://www.bitget.com/api-doc/common/intro |
| Gate.io | CEX-010 | 5 | ✅ implementado — ver `services/exchange-connectors/gateio/README.md` | https://www.gate.com/docs/developers/apiv4/en/ |

**Expansão (CEX-011):** KuCoin, MEXC, BingX, Bitfinex, HTX,
Crypto.com Exchange — avaliados em `docs/exchanges-expansion.md`
(todas viáveis via CCXT; conectores não implementados nesta fase).

**A presença no catálogo não garante disponibilidade regional de todos
os produtos.** Cada conector precisa verificar documentação,
permissões, elegibilidade, rate limits e condições de uso.

## DEX / on-chain (Fase 6)

| Fonte | Tarefa | Papel |
|---|---|---|
| DEX Screener | DEX-001 | Descoberta de pares, volume e liquidez agregados |
| PancakeSwap | DEX-005 | Pools e swaps da BNB Chain |
| Raydium | DEX-006 | Pools e swaps da Solana |
| Uniswap | DEX-007 | Ethereum, Base e redes suportadas |
| Jupiter | DEX-007 | Agregação e execução no ecossistema Solana |
| RPC/WebSocket BNB Chain | DEX-002 | Eventos on-chain |
| RPC/WebSocket Solana | DEX-003 | Eventos on-chain |
| RPC/WebSocket Ethereum/Base | DEX-004 | Eventos on-chain |
| Birdeye, Helius e outros | — | Conforme necessidade |

**API agregadora serve para descoberta e triagem; não deve ser
presumida como feed de trades em tempo real.** Para eventos on-chain,
usar RPC, WebSocket ou indexador adequado.

Ferramentas do Crypto Shield (§7): Bubblemaps, GoPlus, RugCheck,
Helius/Solana RPC, DEX Screener, Birdeye e exploradores oficiais.

## Dados a capturar (§3)

- Último preço, trades individuais, OHLCV, Bid/Ask e spread, Order
  Book, volume, Volume Delta e CVD.
- Funding Rate, Open Interest, Mark Price e Index Price, liquidações
  (quando disponíveis).
- Eventos de pools e swaps, liquidez de pools, movimentações de
  carteiras, dados de contratos e holders.

## Timeframes (§3)

Tick/trade · 1s · 5s · 15s · 30s · 1m · 3m · 5m · 15m · 30m · 1h · 2h ·
4h · 6h · 8h · 12h · diário · semanal.

**Não inventar granularidade.** Se a fonte não fornecer trades
individuais, não simular ticks ou candles de um segundo.

## Conexões (§5)

Planejamento aproximado: **25–35 conexões WebSocket persistentes**.

| Fonte | Conexões estimadas |
|---|---|
| Binance | 3–5 |
| Bybit | 4–6 |
| OKX | 2–4 |
| Coinbase | 1–2 |
| Kraken | 1–2 |
| Bitget | 2–3 |
| Gate.io | 2–3 |
| DEX/RPC | 3–5 |

Implementar: heartbeat, reconexão exponencial com jitter, renovação
programada, recuperação de assinaturas, rate limiting, deduplicação,
sequenciamento, snapshot e sincronização de Order Book, detecção de
gaps, métrica de latência, circuit breaker por fonte e bloqueio de
sinais com feed inválido.

## Referências técnicas (§18)

- CCXT: https://docs.ccxt.com/
- DEX Screener: https://docs.dexscreener.com/api/reference
- PancakeSwap: https://developer.pancakeswap.finance/
- Raydium: https://docs.raydium.io/
- Uniswap: https://docs.uniswap.org/
- Jupiter: https://dev.jup.ag/
- GoPlus: https://docs.gopluslabs.io/
- RugCheck: https://rugcheck.xyz/
- Bubblemaps: https://bubblemaps.io/
