# Pattern Engine

- **Camada:** Camada 4
- **Fase:** Fase 10 — PAT-001…PAT-007 (implementado)

Padrões de velas, Price Action e estrutura de mercado sobre `Candle`
(contrato universal, Fase 3). Só análise: nenhuma rede, nenhuma chave,
nenhum envio de ordem.

## Regra central (PAT-006, §6)

**Um padrão isolado NÃO gera entrada automática.** Toda detecção
(`PatternDetection`) carrega `requires_confirmation=True` e
`generates_entry=False`. `assess_pattern` / `assess_all` anexam o
contexto mínimo — tendência, volume relativo, volatilidade (range/ATR)
e localização (distância ao nível mais próximo, quando informado) — e
o texto do que seria a confirmação. A decisão de operar pertence às
fases 11/14/15, nunca a este módulo.

## Módulos

- `patterns.py` — padrões de velas (PAT-001…PAT-006) e contexto.
- `structure.py` — estrutura de mercado (PAT-007).

## Padrões de velas (`patterns.py`)

| Padrão | Função | Direção |
|---|---|---|
| Doji, Gravestone, Dragonfly, Long-Legged, Four-Price | `detect_doji` | neutra / baixa / alta |
| Hammer / Hanging Man | `detect_hammer` | alta / baixa |
| Shooting Star / Inverted Hammer | `detect_shooting_star` | baixa / alta |
| Bullish / Bearish Engulfing | `detect_engulfing` | alta / baixa |
| Bullish / Bearish Harami | `detect_harami` | alta / baixa |
| Piercing Line / Dark Cloud Cover | `detect_piercing_dark_cloud` | alta / baixa |
| Morning Star / Evening Star | `detect_morning_evening_star` | alta / baixa |
| Three White Soldiers / Three Black Crows | `detect_soldiers_crows` | alta / baixa |
| Tweezer Top / Tweezer Bottom | `detect_tweezers` | baixa / alta |
| Marubozu (bullish / bearish) | `detect_marubozu` | alta / baixa |
| Spinning Top | `detect_spinning_top` | neutra |
| Inside Bar | `detect_inside_bar` | neutra |
| Outside Bar (bullish / bearish) | `detect_outside_bar` | alta / baixa |

`detect_at(candles, i)` devolve todos os padrões que terminam no
candle `i`; `detect_all(candles)` varre a série. `assess_all(candles,
levels=[...])` devolve as detecções já com contexto.

### Thresholds

- Doji: corpo ≤ 10% do range. Gravestone: sombra inferior ≤ 10% e
  superior ≥ 60% do range; Dragonfly: espelho; Long-Legged: ambas as
  sombras ≥ 35% do range.
- Hammer / Shooting Star: corpo ≤ 35% do range, sombra longa ≥ 2× o
  corpo, sombra oposta ≤ 1× o corpo. O nome depende da tendência
  prévia (5 closes): baixa → Hammer / Inverted Hammer; alta →
  Hanging Man / Shooting Star.
- Marubozu: corpo ≥ 90% do range, sombras ≤ 5% do range cada.
- Spinning Top: corpo ≤ 30% do range, ambas as sombras ≥ 1× o corpo.
- Engulfing: corpo do candle 2 engole o corpo do candle 1, cores
  opostas (engolfo exato não conta).
- Harami: corpo do candle 2 dentro do corpo do candle 1, cores opostas.
- Piercing / Dark Cloud: candle 2 abre além do extremo do candle 1 e
  fecha além do ponto médio do corpo do candle 1.
- Morning / Evening Star: candle 1 longo (corpo ≥ 50% do range),
  candle 2 de corpo pequeno (≤ 35%) com gap, candle 3 fecha além do
  ponto médio do corpo do candle 1.
- Soldiers / Crows: 3 candles da mesma cor, corpos ≥ 50% do range,
  cada abertura dentro do corpo anterior, fechamentos progressivos,
  sombra na direção do movimento ≤ 25% do range.
- Tweezers: máximas (topo) ou mínimas (fundo) iguais dentro de 0,1%
  do preço, cores opostas.
- Inside Bar: high/low contidos no candle anterior (ao menos um
  extremo estrito). Outside Bar: high/low contêm o anterior.

Confiança (0–1): qualidade geométrica (0,55–0,8 base) + 0,1 quando o
volume do candle está acima da média dos 10 anteriores. `strength`:
≥ 0,75 strong, ≥ 0,55 moderate, abaixo weak.

## Estrutura de mercado (`structure.py`, PAT-007)

| Item | Função | Regra objetiva |
|---|---|---|
| Topos e fundos | `find_swings` | extremo estrito na janela de 2+1+2 candles |
| Tendência | `classify_trend` | HH+HL → alta; LH+LL → baixa; senão lateral |
| Suporte / resistência | `find_levels` | ≥ 2 toques de swings no mesmo preço (±0,5%) |
| BOS / CHoCH | `detect_bos_choch` | fechamento além do último swing confirmado; na direção da tendência → BOS, contra → CHoCH |
| Breakout e reteste | `detect_breakout_retest` | fechamento além do nível; reteste = retorno ao nível (±0,5%) com fechamento do lado do breakout em até 5 candles |
| Pullback | `detect_pullbacks` | retração de 38,2%–78,6% da perna sem romper o swing de origem |
| Liquidity Sweep | `detect_liquidity_sweeps` | pavio além de um swing com fechamento de volta para dentro no mesmo candle |
| FVG | `detect_fvg` | gap entre máxima de i-2 e mínima de i (alta) ou inversa; `filled` quando um candle posterior fecha além da borda oposta |
| Order Blocks | `detect_order_blocks` | último candle de cor oposta antes do candle do BOS (busca até 5 candles) |
| Fibonacci | `fib_retracement`, `fib_extension` | níveis 0 / 23,6 / 38,2 / 50 / 61,8 / 78,6 / 100% e extensões 127,2 / 161,8 / 261,8% |

ICT/SMC e Wyckoff entram apenas como as regras acima. **Wyckoff
(Spring, SOS, UTAD) não foi implementado como conceito**: não há
regra objetiva testável para ele sem volume de mercado agregado e
contexto de acumulação — o que existe de testável (sweep + BOS +
reteste) está nas funções acima. **Padrões harmônicos** ficaram fora
desta fase (não há tarefa PAT para eles).

## Testes

`tests/patterns/` — cada padrão/evento com teste positivo e negativo,
sobre candles sintéticos, sem rede.
