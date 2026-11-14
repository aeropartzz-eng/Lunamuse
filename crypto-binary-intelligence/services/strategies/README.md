# Strategy Engine / Strategy Lab

- **Camada:** Camada 4
- **Fase:** Fase 11 — STR-001…STR-010
- **Módulo:** `strategies.py`

Framework de estratégias versionadas e reproduzíveis, só análise e geração de sinais **em memória**: nenhuma chave de API, nenhum envio de ordem, nenhuma conexão a conta. A execução continua bloqueada (403) e o scaffold força RESEARCH quando `EXECUTION_MODE=LIVE`.

## Sinal

Compatível com a tabela `strategy_signals` da Fase 2 (§9): exchange, market, symbol, timeframe, direction (`long`/`short`), `strategy_id` (código, ex.: `STR-001`) e `strategy_version`, preço de referência, entrada, stop e alvo, probabilidade (0–1, **teto de 0,85** — a meta de 85% é objetivo de pesquisa, não promessa), validade (`valid_until_ms`, derivada do timestamp do último candle, nunca do relógio da máquina), spread/liquidez quando informados, justificativas (`rationale`) e status `DETECTED`.

**Sinal sem justificativa não é emitido.** `Signal.to_dict()` devolve o dict pronto para persistir em `strategy_signals`.

## Framework (STR-001)

`BaseStrategy` — id, nome, versão, mercados, timeframes, parâmetros, filtros e `generate_signals(candles, indicators, patterns, regime) -> list[Signal]`. Cada estratégia avalia **só o último candle fechado** e devolve no máximo um sinal (ou `[]`).

- **Versionamento:** `version` e `params` fazem parte da identidade da versão — mudar a versão muda `strategy_version` no sinal. Mesmos inputs + mesma versão = mesmos sinais (sem aleatoriedade, relógio ou estado mutável entre chamadas).
- **Registro:** `get_strategy("STR-001", version=2)`, `list_strategies()`, `STRATEGY_REGISTRY`.
- **Filtros globais** (aplicados pela base antes de qualquer emissão): regime compatível (`allowed_regimes` por estratégia), spread máximo (**50 bps**, quando informado), liquidez mínima (**US$ 1.000**, quando informada), probabilidade mínima (**0,55**) e validade definida. Sem dado de mercado não há o que filtrar (lab); com `GlobalFilters(require_market_data=True)` — caminho de produção, Fase 14 — a ausência de spread/liquidez também bloqueia.
- **Stop/alvo padrão:** stop a `atr_stop_mult` × ATR, alvo com `risk_reward` 2,0 sobre o risco (cada estratégia pode sobrescrever). Validade padrão: 5 candles do timeframe.

## Estratégias implementadas (STR-001…STR-010)

Mapeamento da tarefa (a numeração do §6 difere: STR-008 aqui funde Engulfing + Doji, STR-009 é o Multi-Timeframe do §6 STR-016 e STR-010 é o Combinador).

| ID | Estratégia | Regras (resumo) | Parâmetros principais | Regimes permitidos |
|---|---|---|---|---|
| STR-001 | Trend Following | EMA20 > EMA50, preço > EMA20, ADX ≥ 25, MACD acima do sinal (hist > 0); espelho p/ short | `adx_min=25`, `atr_stop_mult=1,5`, `risk_reward=2,0` | TREND_UP/DOWN, EXPANSION |
| STR-002 | Momentum | RSI ≥ 55 (≤ 45 short), ROC(12) ≥ 2% (≤ −2%), volume ≥ 1,2x a média | `rsi_long_min=55`, `roc_min_pct=2,0`, `volume_ratio_min=1,2` | TREND_UP/DOWN, EXPANSION |
| STR-003 | Pullback | Em tendência (ADX ≥ 20): preço recuou até EMA20/VWAP nos últimos 6 candles e fechou de volta acima, candle de recuperação, RSI 35–85 | `pullback_bars=6`, `rsi 35–85`, stop na mínima do pullback | TREND_UP/DOWN |
| STR-004 | Breakout | Fechamento acima da banda superior de Bollinger **e** da máxima de 20 candles, volume ≥ 1,5x | `volume_ratio_min=1,5`, `lookback_high=20` | TREND_UP/DOWN, EXPANSION, TRANSITION |
| STR-005 | False Breakout | Pavio varre a mínima/máxima de 20 candles e fecha de volta p/ dentro (regra equivalente a FLOW-005), candle de rejeição, volume ≥ 1,0x | `lookback=20`, `volume_ratio_min=1,0` | RANGE, TREND_UP/DOWN, TRANSITION, COMPRESSION |
| STR-006 | Mean Reversion | RSI ≤ 30 (≥ 70), %B ≤ 0,05 (≥ 0,95), Z-score(20) ≤ −1,5 (≥ 1,5) | `rsi 30/70`, `zscore_min=1,5` | RANGE, COMPRESSION |
| STR-007 | Range Trading | Perto do suporte/resistência (≤ 1 ATR ou ≤ 1% do preço) com ADX < 25; níveis de `structure.find_levels` (mín. 2 toques) ou extremos de 30 candles; largura do range ≥ 2 ATR | `adx_max=25`, `level_tol_atr=1,0` | RANGE, COMPRESSION |
| STR-008 | Engulfing/Doji | Engolfo/doji/estrela no último candle (Fase 10) + volume ≥ 1,0x + momentum (hist MACD na direção ou RSI 20–75) | `volume_ratio_min=1,0` | todos |
| STR-009 | Multi-Timeframe | M15 em tendência **e** M5 em tendência **e** gatilho no M1; sem `context`, o M15 é derivado por agregação x3 da série (M5 → M15) e o gatilho é o próprio candle de execução | `higher_factor=3`, `volume_ratio_min=1,0` | TREND_UP/DOWN, EXPANSION, TRANSITION |
| STR-010 | Combinador | Confluência ponderada (ver abaixo); score ≥ +0,50 (long) ou ≤ −0,50 (short) | pesos + `threshold=0,50` | todos |

## STR-010 Combinador — pesos e threshold (decisão)

| Componente | Peso | Voto +1 | Voto −1 |
|---|---|---|---|
| trend | 0,25 | EMA20 > EMA50 e preço > EMA20 | EMA20 < EMA50 e preço < EMA20 |
| momentum | 0,25 | RSI > 50 e hist MACD > 0 | RSI < 50 e hist MACD < 0 |
| volatility | 0,20 | %B Bollinger > 0,8 | %B < 0,2 |
| volume | 0,15 | volume ≥ 1,5x e candle de alta | volume ≥ 1,5x e candle de baixa |
| pattern | 0,15 | engolfo/estrela/hammer de alta no último candle | engolfo/estrela/shooting de baixa |

Score = Σ peso × voto (votos em −1/0/+1). Probabilidade = 0,50 + 0,30 × |score|. O `rationale` registra cada componente com voto, peso e contribuição — a justificativa por sinal é auditável.

## Próximas (não implementadas aqui)

STR-011 Wyckoff (Spring + SOS + Volume), STR-012 ICT Liquidity (FVG + BOS + Liquidity Sweep), STR-013 VWAP Reversion (VWAP + Desvio + ATR), STR-014 Order Flow Scalping (CVD + Imbalance + Absorção), STR-015 Volatility Compression (BB Width + ATR Expansion) e STR-016 Multi-Timeframe completo do §6. Ficam para as próximas fases — dependem de calibração com dados reais e, no caso de STR-011/STR-012, de regras objetivas adicionais sobre a estrutura da Fase 10.

## Testes

`tests/strategies/test_strategies.py` — cada estratégia com teste positivo (série construída para o setup gera sinal) e negativo (série sem setup não gera sinal), mais: nenhum sinal em série plana para as 10 estratégias, reprodutibilidade (duas chamadas → sinais idênticos), versionamento (versão 2 muda `strategy_version` no sinal), filtros globais (spread/liquidez) e schema do sinal. Sem rede.
