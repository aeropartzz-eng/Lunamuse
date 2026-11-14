# Order Flow Engine

- **Camada:** Camada 4
- **Fase:** Fase 10 — FLOW-001…FLOW-005 (implementado)

Volume Delta, CVD, Order Book Imbalance, absorção, exaustão,
Liquidity Sweep, profundidade, spread e slippage estimado — sobre
`Trade`, `OrderBook` e `Candle` (contrato universal, Fase 3). Só
análise: nenhuma rede, nenhuma chave, nenhum envio de ordem.

## Funções

| Item | Função | Regra |
|---|---|---|
| Volume Delta (FLOW-001) | `volume_delta(trades)` | soma do volume agressivo buy/sell; `delta = buy − sell` |
| CVD (FLOW-002) | `cumulative_cvd(trades)`, `final_cvd(trades)` | soma corrente de +qty (buy) / −qty (sell), em ordem cronológica (a ordenação é da ingestão, Fase 7) |
| Order Book Imbalance (FLOW-003) | `book_imbalance(book, levels=5)` | `(bid − ask) / (bid + ask)` nos N primeiros níveis; `strong` quando `|imbalance| ≥ 0,30` |
| Mudança de profundidade | `depth_change(prev, curr, levels=5)` | variação de qty por lado entre dois snapshots |
| Spread | `spread_bps(book)` | `(ask − bid) / mid × 10.000`; `None` se o book estiver vazio |
| Slippage estimado | `estimated_slippage(book, side, quantity)` | percorre o book e calcula o preço médio de execução vs mid; informa `filled_quantity` e `fully_filled` — simulação sobre o snapshot, não envia ordem |
| Absorção (FLOW-004) | `detect_absorption(trades, start_price, end_price, atr)` | ≥ 60% do volume agressivo num só lado **e** deslocamento de preço ≤ 0,2 ATR |
| Exaustão (FLOW-004) | `detect_exhaustion(candle, avg_volume, index)` | volume ≥ 2× a média **e** pavio ≥ 50% do range **e** fechamento revertido (na metade oposta ao pavio) |
| Liquidity Sweep (FLOW-005) | `detect_liquidity_sweep(candles, level, direction)` | pavio além do nível com fechamento de volta para dentro, no mesmo candle ou no seguinte |

## Thresholds

- Imbalance forte: `|imbalance| ≥ 0,30`.
- Absorção: lado único ≥ 60% do volume; preço move ≤ 0,2 ATR
  (se `atr ≤ 0`, usa ≤ 0,05% do preço inicial).
- Exaustão: volume ≥ 2× a média; pavio ≥ 50% do range.

## Footprint: indisponível nesta fase

`footprint_status()` explica o motivo e `build_footprint()` levanta
`NotImplementedError`. O footprint exige volume agressivo de
compra/venda **por nível de preço** dentro de cada candle — dado que
os conectores atuais não fornecem (só trades por lado e snapshots de
book). Nada é inventado no lugar do dado que não existe. Quando o
market-data passar a agregar trades por preço por candle, o footprint
poderá ser construído.

## Testes

`tests/order-flow/` — CVD com lados conhecidos (valor exato),
imbalance com valores conhecidos, absorção/exaustão/sweep com casos
positivo e negativo, spread e slippage. Sem rede.
