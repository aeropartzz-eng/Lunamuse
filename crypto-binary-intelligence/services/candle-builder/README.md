# Candle Builder — Fase 7 ✅

- **Camada:** Camada 3
- **Fase:** Fase 7 — DAT-003/DAT-004 (especificação v4.1, §3, §7)

Constrói candles OHLCV próprios a partir de trades e agrega
timeframes. Só granularidades fornecidas pela fonte — nunca simular
ticks ou candles de 1s sem trades (§3).

## O que foi implementado (`candle_builder.py`)

| Componente | Tarefas | Conteúdo |
|---|---|---|
| `TIMEFRAME_MS` | DAT-003 | Os 17 timeframes reais (§3): 1s, 5s, 15s, 30s, 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 1w. Buckets alinhados à época Unix (a semana alinha à quinta 00:00 UTC). |
| `CandleBuilder` | DAT-003/005/006 | Um par (exchange, symbol) × N timeframes. `add_trade()` retorna os candles fechados; `flush(now_ms)` fecha buckets completos; `open_candles()` mostra os parciais. |
| `aggregate_candles` | DAT-004 | Agrega candles **fechados** de um timeframe menor num maior, só quando o alvo é múltiplo exato da origem (1m→5m, 1h→4h, 1d→1w). |
| `detect_gaps` | DAT-006 | Lista os `open_time_ms` ausentes numa sequência de candles. |

## Regras

- **Sem look-ahead:** um candle só é emitido quando o bucket
  seguinte começa (ou pelo `flush` após o fim do bucket). O candle
  aberto nunca é entregue como fechado, e só candles fechados entram
  na agregação.
- **Sem dado inventado:** bucket sem trades não vira candle — é
  contado como gap (`gap_buckets_skipped`) e detectável por
  `detect_gaps`. Buckets pulados nunca são preenchidos.
- **Validação cronológica (DAT-005):** trade com timestamp anterior
  ao último aceito é rejeitado e contado (`out_of_order_rejected`);
  o passado nunca é reordenado.
- **Granularidade real:** `validate_timeframe` rejeita qualquer
  timeframe fora dos 17; `aggregate_candles` rejeita alvo que não
  seja múltiplo exato da origem.

## Uso

```python
from candle_builder import CandleBuilder, aggregate_candles

builder = CandleBuilder("binance", "BTC/USDT", ["1m", "5m"])
closed_1m = builder.add_trade(trade)   # [] até fechar um bucket
closed_5m = aggregate_candles(closed_1m, "5m")
```

## Testes

`tests/market-data/test_candle_builder.py` — OHLCV a partir de
trades sintéticos, agregação, sem look-ahead, fora de ordem e gaps.
