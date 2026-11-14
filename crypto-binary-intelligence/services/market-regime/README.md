# Market Regime Engine

- **Camada:** Camada 4
- **Fase:** Fase 11 — REG-001…REG-005
- **Módulo:** `market_regime.py`

Classifica tendência, consolidação, volatilidade, compressão, expansão e mudanças de regime — com regras objetivas e testáveis, sem look-ahead (o regime no índice `i` só usa dados até `i`).

## Regimes

| Rótulo | Tarefa | Regra (todas medidas no último candle) |
|---|---|---|
| `TREND_UP` / `TREND_DOWN` | REG-001 | ADX ≥ 25 **e** EMA(20) acima/abaixo da EMA(50) **e** fechamento do mesmo lado da EMA(20) **e** inclinação da EMA(20) em 5 candles no sentido do movimento |
| `RANGE` | REG-002 | ADX efetivo < 25 **e** eficiência de 20 candles ≤ 0,35 **e** variação líquida de 20 candles ≤ 3% |
| `COMPRESSION` | REG-003 | Largura de Bollinger ≤ 0,65x a mediana das últimas 50 larguras **e** ATR ≤ 1,15x a SMA(ATR, 20) **e** ADX < 25 |
| `EXPANSION` | REG-004 | ATR ≥ 1,40x a SMA(ATR, 20) **ou** largura de Bollinger ≥ 1,50x a mediana |
| `TRANSITION` | REG-005 | Nenhuma das regras acima se confirma |

Os rótulos em minúsculo (`trend_up`, `trend_down`, `range`, `compression`, `expansion`, `transition`) são os valores da tabela `market_regimes` da Fase 2.

**Precedência:** compressão e expansão são estados de volatilidade e são testados **antes** da tendência — uma expansão forte durante uma alta é `EXPANSION`, não `TREND_UP`.

## Thresholds (decisões)

- **ADX 25** para tendência (convenção de Wilder); abaixo de 25, sem tendência direcional.
- **Compressão usa a largura de Bollinger como discriminante principal**, não o ATR: numa série sintética de amplitude decrescente o ATR quase não cai (o ruído de high/low impõe um piso), enquanto a largura cai para ~0,42x a mediana. Numa tendência estável as razões de ATR e de largura ficam ~1,0, então tendência não vira expansão por engano.
- **ADX `NaN`:** após um longo período plano seguido de movimento, a suavização de Wilder da Fase 9 não encontra janela limpa e o ADX vem `NaN`. Nesse caso usa-se como proxy `| +DI − −DI |`.
- **Confiança 0,50–0,95**, proporcional à margem acima dos thresholds (ex.: quanto maior o ADX acima de 25, maior a confiança de tendência).
- **Mínimo de 50 candles** (warm-up da EMA(50) + ADX + Bollinger(20)); menos que isso levanta `ValueError`.

## Mudança de regime (REG-005)

`detect_regime()` classifica o último candle (rótulo **bruto**). A confirmação vive em `RegimeTracker`: um novo rótulo só vira o regime confirmado depois de `min_persistence` classificações consecutivas com esse rótulo (**padrão: 3 candles**). Enquanto isso, o regime confirmado não muda — nada de flip a cada candle. `detect_regime_changes(candles)` aplica o tracker sobre a série inteira e devolve as mudanças confirmadas (`index`, `from`, `to`, `confidence`, `reason`).

## API

```python
from market_regime import detect_regime, classify_series, RegimeTracker, detect_regime_changes

regime = detect_regime(candles)          # Regime(label, confidence, reason, index, features)
regime.label        # "TREND_UP" | "TREND_DOWN" | "RANGE" | "COMPRESSION" | "EXPANSION" | "TRANSITION"
regime.features     # adx, adx_effective, plus_di, minus_di, ema_20, ema_50,
                    # ema_slope_pct, atr, atr_ratio, bb_bandwidth,
                    # bb_bandwidth_ratio, efficiency_20, change_20_pct

tracker = RegimeTracker(min_persistence=3)
confirmed = tracker.update(candles)     # regime confirmado (com persistência)
tracker.history                         # mudanças confirmadas

changes = detect_regime_changes(candles)  # [{"index", "from", "to", "confidence", "reason"}]
```

## Testes

`tests/market-regime/test_market_regime.py` — séries sintéticas com regime conhecido: tendência de alta → `TREND_UP`, lateral → `RANGE`, compressão → `COMPRESSION`, compressão seguida de expansão → mudança confirmada para `EXPANSION`, persistência do tracker (1 candle não vira o regime, 3 viram).
