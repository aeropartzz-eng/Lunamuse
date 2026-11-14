# Indicator Engine

- **Camada:** Camada 4 (Inteligência)
- **Fase:** Fase 9 — IND-001…IND-008
- **Módulo:** `services/indicators/indicators.py` (NumPy puro, sem TA-Lib)
- **Testes:** `tests/indicators/` — 70 testes, todos com valores esperados
  calculados à mão ou por referência independente

Tendência (EMA, SMA, ADX, DMI, MACD, Supertrend) · Momentum (RSI,
Stochastic, Stochastic RSI, ROC, CCI) · Volatilidade (ATR, Bollinger,
Keltner, Historical Volatility) · Volume (VWAP, Anchored VWAP, OBV,
Volume Profile, MFI, CVD) · Divergências (regular e oculta, preço vs.
RSI/MACD) · Features derivadas para a Fase 13 (ML).

## Regra de ouro — sem look-ahead (IND-008)

O valor do indicador no índice `i` só usa dados até `i`. Testado
explicitamente em `tests/indicators/test_no_lookahead.py`: alterar (ou
anular) dados futuros não muda nenhum valor passado, para SMA, EMA, RSI,
ROC, ATR, Bollinger, MACD, DMI, Supertrend, VWAP, OBV, MFI e divergências.

## Por que NumPy puro (e não TA-Lib)

TA-Lib não está instalado neste ambiente e exige compilação nativa
(C); NumPy já faz parte do stack do projeto (§8) e é suficiente para
todos os indicadores, com fórmulas explícitas e auditáveis no código.
Nada aqui acessa rede, credenciais ou envia ordens — é só cálculo
sobre séries OHLCV.

## Convenções

- Entradas: arrays 1-D (listas, `np.ndarray` ou séries pandas).
- Saídas: `np.ndarray` float64 do mesmo comprimento; posições sem dados
  suficientes são `NaN` (warm-up). Funções com várias saídas devolvem
  `dict` de arrays.
- Desvio-padrão populacional (`ddof=0`), padrão de Bollinger/TA-Lib.
- EMA semeada com a SMA dos `period` primeiros valores no índice
  `period - 1`; `k = 2 / (period + 1)`.
- Suavização de Wilder (RSI, ATR, ADX/DMI): primeira média = média
  simples dos `period` primeiros valores; depois
  `avg[i] = (avg[i-1] * (period - 1) + x[i]) / period`.
- `NaN` na entrada: janelas móveis devolvem `NaN` se a janela contiver
  `NaN`; suavizadores recursivos (EMA, RSI, ATR, ADX) **pulam** o `NaN`
  e carregam o último valor — o `NaN` nunca contamina o futuro.
- Volume zero / divisão por zero: resultado `NaN`, nunca exceção.

## Indicadores e parâmetros padrão

| Grupo | Função | Padrão | Fórmula de referência |
|---|---|---|---|
| Tendência | `sma(values, period=20)` | 20 | média dos últimos `period` valores |
| Tendência | `ema(values, period=20)` | 20 | `k*x + (1-k)*EMA anterior`, `k=2/(period+1)` |
| Tendência | `macd(close, fast=12, slow=26, signal=9)` | 12/26/9 | `EMA12-EMA26`; sinal = EMA9 da linha; histograma = linha − sinal |
| Tendência | `dmi(high, low, close, period=14)` | 14 | Wilder: `+DI/-DI` de TR e ±DM suavizados; `DX`, `ADX` |
| Tendência | `adx(high, low, close, period=14)` | 14 | atalho para `dmi(...)["adx"]` |
| Tendência | `supertrend(high, low, close, period=10, multiplier=3.0)` | 10 / 3.0 | bandas `(H+L)/2 ± mult*ATR`, final só move a favor da tendência |
| Momentum | `rsi(close, period=14)` | 14 | Wilder: `100 - 100/(1 + ganho médio/perda média)` |
| Momentum | `stochastic(high, low, close, k_period=14, d_period=3)` | 14 / 3 | `%K = 100*(C-LL)/(HH-LL)`; `%D = SMA(%K, 3)` |
| Momentum | `stochastic_rsi(close, rsi_period=14, stoch_period=14, k_period=3, d_period=3)` | 14/14/3/3 | Stochastic aplicado sobre o RSI |
| Momentum | `roc(close, period=12)` | 12 | `100*(C[i]-C[i-period])/C[i-period]` |
| Momentum | `cci(high, low, close, period=20)` | 20 | `(TP-SMA(TP)) / (0.015 * desvio médio de TP)`, `TP=(H+L+C)/3` |
| Volatilidade | `atr(high, low, close, period=14)` | 14 | média de Wilder do True Range |
| Volatilidade | `bollinger(close, period=20, std_dev=2.0)` | 20 / 2.0 | média ± `2*σ`; devolve `upper/middle/lower/bandwidth/percent_b` |
| Volatilidade | `keltner(high, low, close, period=20, atr_period=10, multiplier=2.0)` | 20/10/2.0 | `EMA(TP) ± mult*ATR` |
| Volatilidade | `historical_volatility(close, window=20, annualization=365.0)` | 20 / 365 | `σ` pop. dos retornos log × `sqrt(365)` (cripto 24/7; use 252 p/ bolsa) |
| Volume | `vwap(high, low, close, volume, session_start=None)` | — | `Σ(TP*V)/Σ(V)` acumulado; `session_start` reinicia por sessão |
| Volume | `anchored_vwap(high, low, close, volume, anchor_index=0)` | âncora 0 | VWAP acumulado a partir de `anchor_index` |
| Volume | `obv(close, volume)` | — | soma volume se fecha sobe, subtrai se cai |
| Volume | `volume_profile(high, low, close, volume, bins=24, value_area_pct=0.70)` | 24 / 70% | POC = faixa de maior volume; value area expande do POC até 70% |
| Volume | `mfi(high, low, close, volume, period=14)` | 14 | `100 - 100/(1 + fluxo+/fluxo-)`, fluxo = `TP*V` |
| Volume | `cvd(close, volume, open_=None, side=None)` | — | volume acumulado com sinal; prefere `side` (+1/-1, dado de trade), senão sinal de `close-open`, senão da variação do fechamento |
| Divergência | `find_swings(values, window=2)` | 2 | pivôs (topos/fundos) por máximo/mínimo local |
| Divergência | `detect_divergences(close, indicator, window=2)` | 2 | regular/oculta de alta/baixa comparando pivôs consecutivos |
| Features | `log_returns(close)` | — | `ln(C[i]/C[i-1])` |
| Features | `realized_volatility(close, window=20, annualization=365.0)` | 20 / 365 | igual a `historical_volatility` |
| Features | `distance_from_ma(close, period=20)` | 20 | `100*(C-SMA)/SMA` |
| Features | `zscore(values, window=20)` / `zscore_volume(volume, window=20)` | 20 | `(x-média)/σ` em janela móvel |
| Features | `compute_features(close, volume=None, window=20)` | 20 | pacote p/ Fase 13: log_return, realized_vol, dist_sma/ema, zscores, volume_ratio |

`DEFAULTS` (no módulo) reúne todos os parâmetros padrão.

## Como usar

```python
import sys
sys.path.insert(0, "services/indicators")  # testes já fazem isso via conftest
import indicators as I

# Séries OHLCV (listas ou arrays)
rsi = I.rsi(closes, period=14)
bb = I.bollinger(closes, period=20, std_dev=2.0)   # dict: upper/middle/lower/...
macd = I.macd(closes)                              # dict: macd/signal/histogram
dmi = I.dmi(highs, lows, closes)                   # dict: plus_di/minus_di/dx/adx
st = I.supertrend(highs, lows, closes)             # dict: supertrend/direction (+1/-1)
vp = I.volume_profile(highs, lows, closes, vols)   # dict: poc/value_area_*/...
divs = I.detect_divergences(closes, rsi)           # lista de dicts

# A partir de candles (modelo Candle do contrato universal, ou dicts)
from models import Candle
data = I.candles_to_arrays(candles)   # dict de arrays open/high/low/close/volume/...
all_ind = I.compute_all(candles)     # todos os indicadores com parâmetros padrão
feats = I.compute_features(data["close"], data["volume"])  # features p/ Fase 13
```

## Testes (IND-008)

`tests/indicators/` — `test_trend.py`, `test_momentum_volatility.py`,
`test_volume.py`, `test_divergences_features.py`,
`test_no_lookahead.py` (+ `conftest.py` com fábrica de candles):

- Cada indicador tem ao menos um teste com valor esperado conhecido
  (SMA/EMA/RSI/Bollinger/VWAP/ATR/MFI/CCI/ROC/Stochastic/MACD/ADX/
  Supertrend/Keltner/HV/OBV/CVD/Volume Profile/StochRSI e divergências
  dos 4 tipos), calculado à mão ou por referência independente.
- Bordas: série curta demais (tudo `NaN`), série vazia, período
  inválido, comprimentos diferentes, `NaN` no meio da série, volume
  zero, preço anterior zero, `HH == LL`, série constante (RSI 50,
  MACD 0, ATR constante).
- Look-ahead: mutar dados futuros (inclusive inserir `NaN`) não muda
  nenhum valor passado.

```bash
python3 -m pytest tests/indicators/ -q   # 70 testes
python3 -m pytest tests/ -q              # suíte completa
```

## Pendências / limites conhecidos

- **CVD com lado do agressor**: `cvd(..., side=...)` precisa do dado de
  trade (Fase 7/10 — Order Flow); sem ele, usa `close - open` ou a
  variação do fechamento, que é uma aproximação — documentar a origem
  ao usar em estratégia.
- **VWAP por sessão**: `session_start` precisa ser fornecido pelo
  chamador (ex.: abertura do dia); sem ele, o VWAP acumula toda a
  série passada.
- **Volume Profile**: distribui o volume do candle na faixa do seu
  preço típico (não há footprint intra-candle nesta fase).
- **Divergências**: detecção por pivôs com `window` fixo; não há ainda
  confirmação por volume/estrutura (Fase 10/11).
- **Warm-up**: ADX precisa de ~`2 * period` barras para o primeiro
  valor (DX precisa de `period` valores antes da suavização).
