# Relatório do 85% — Machine Learning (Fase 13)

> ⚠️ **DADOS SINTÉTICOS — NÃO É RESULTADO REAL.** Todas as séries usadas aqui foram geradas por simulação (seeds fixas, regimes mistos) para demonstrar e validar o pipeline de ML. Nenhum número deste relatório valida qualquer modelo em mercado real, nem promete acerto, lucro ou rentabilidade. A meta de 85% é um objetivo de pesquisa para sinais seletivos (§0, premissa 1). A validação com dados reais é trabalho da VPS (pendência registrada).

- Data: **2026-11-13** · Fase 13 (ML-001…ML-011) · especificação v4.1 §8.
- Feature set: **v1** (29 features) · horizonte do rótulo: 1 candle(s).
- Séries sintéticas: BTC/USDT, ETH/USDT, SOL/USDT · timeframe 5m · seeds 7, 8, 9.
- Split cronológico (Fase 12): treino 1917 · validação 639 · **teste (fora da amostra) 642**.
- Custos por trade: **30 bps** (taxa 10 bps/lado + spread 5 bps + slippage 5 bps — mesmas premissas da Fase 12).
- Calibração: Platt (sigmoid) ajustada na validação. A calibração isotônica existe em `CalibratedModel(method='isotonic')` como alternativa, mas não é usada neste relatório.

## Veredicto

**❌ META DE 85% NÃO ATINGIDA (nesta amostra sintética):** precisão seletiva 71.95% < 85%; subconjunto seletivo com 82 amostras < 500 (referência §8 para crypto scalping); expectativa líquida -2.140005874884895 bps <= 0 (não positiva após custos). O número não foi forçado — a precisão é reportada como medida, junto com cobertura, IC 95%, expectativa e custos, como exige o protocolo do 85%.

## 1. Modelos fora da amostra (teste, calibrados na validação)

| Modelo | Acurácia | Precision | Recall | Brier (cru → calibrado) | Log Loss (cru → calibrado) | Win Rate (sinal) | Expectativa líq. (bps/trade) | n |
|---|---|---|---|---|---|---|---|---|
| lightgbm | 66.98% | 68.35% | 95.88% | 0.2550 → 0.2264 | 0.7291 → 0.6453 | 48.61% | -2.0122294380920693 | 642 |
| logistic_regression | 68.07% | 68.07% | 100.00% | 0.2207 → 0.2204 | 0.6345 → 0.6329 | 48.75% | -2.140005874884895 | 642 |
| random_forest | 68.54% | 68.39% | 100.00% | 0.2279 → 0.2222 | 0.6502 → 0.6367 | 48.98% | -1.7293634649045213 | 642 |
| xgboost | 67.76% | 68.08% | 99.08% | 0.2398 → 0.2291 | 0.6790 → 0.6510 | 48.58% | -2.3585469910606327 | 642 |

Melhor modelo individual (menor Brier fora da amostra): **logistic_regression**.

## 2. Selective Prediction — precisão SEMPRE com cobertura

| Limiar de confiança | Cobertura | n coberto | Precisão (cobertos) | Acurácia (cobertos) |
|---|---|---|---|---|
| 0.55 | 99.07% | 636 | 68.08% | 68.08% |
| 0.60 | 82.24% | 528 | 67.99% | 67.99% |
| 0.65 | 25.39% | 163 | 71.17% | 71.17% |
| 0.70 | 0.00% | 0 | n/d | n/d |
| 0.75 | 0.00% | 0 | n/d | n/d |
| 0.80 | 0.00% | 0 | n/d | n/d |
| 0.85 | 0.00% | 0 | n/d | n/d |
| 0.90 | 0.00% | 0 | n/d | n/d |
| 0.95 | 0.00% | 0 | n/d | n/d |

Limiar escolhido: **0.66** (maior precisão encontrada na varredura 0,50–0,99 com cobertura >= 5% — a meta de 85% não foi atingida em nenhum limiar).
Precisão seletiva: **71.95%** · cobertura **12.77%** (82/642) · IC 95% (Wilson): **61.41% – 80.52%** (59/82 acertos).

## 3. Ensemble vs. melhor modelo individual

| Modelo | Acurácia | Brier | Log Loss | Rank (Brier) |
|---|---|---|---|---|
| ensemble_stacking | 68.07% | 0.2195 | 0.6311 | 1 |
| logistic_regression | 68.07% | 0.2204 | 0.6329 | 2 |
| random_forest | 68.54% | 0.2222 | 0.6367 | 3 |
| ensemble_weighted | 67.29% | 0.2246 | 0.6428 | 4 |
| lightgbm | 66.98% | 0.2264 | 0.6453 | 5 |
| xgboost | 67.76% | 0.2291 | 0.6510 | 6 |

O ensemble (**ensemble_stacking**) venceu o melhor modelo individual em Brier fora da amostra (0.2195).

## 4. Concept Drift (treino vs. teste)

- PSI máximo: **3.423** (limite de alerta: 0.25) · PSI médio: 0.952.
- Drift detectado: **SIM**.
- Alerta: DRIFT: 17 feature(s) com PSI >= 0.25 (máx. 3.423): dist_vwap_pct, rsi_14, dist_ema_20, adx_14, dist_sma_20, roc_12, mfi_14, zscore_close_20, bb_percent_b, regime_TREND_DOWN, cci_20, stoch_k, regime_TREND_UP, regime_RANGE, realized_vol_20, atr_pct, macd_hist — re-treino recomendado.
- Maiores PSIs por feature:
  - dist_vwap_pct: 3.423 (significativo)
  - rsi_14: 2.857 (significativo)
  - dist_ema_20: 2.661 (significativo)
  - adx_14: 2.231 (significativo)
  - dist_sma_20: 2.088 (significativo)

## 5. Critérios do §8 / protocolo do 85%

| Critério | Observado | Resultado |
|---|---|---|
| Precisão seletiva >= 85% | 71.95% | ❌ FAIL |
| Cobertura divulgada junto com a precisão | 12.77% (82/642) | ✅ PASS |
| IC 95% da precisão seletiva | 61.41% – 80.52% | ✅ PASS |
| Expectativa líquida positiva (custos incluídos) | -2.140005874884895 bps/trade | ❌ FAIL |
| Amostra fora da amostra (crypto: >= 500; binárias: >= 1.000) | 642 (teste) / 82 (seletivo) | ❌ FAIL |
| Win Rate do melhor modelo como sinal | 48.75% | — |

Estes critérios são de **triagem** (§8) — nenhum deles, sozinho ou em conjunto, aprova o modelo (§0, premissa 3). Correlação temporal entre operações exige métodos de validação adicionais.

## 6. Limitações e pendências

- **Dados sintéticos**: séries geradas por simulação (random walk com regimes); o sinal aprendido aqui pode não existir em mercado real.
- Amostra fora da amostra pequena para o §8 (ver §5): o subconjunto seletivo raramente chega a 500 amostras com séries de ~1.100 candles.
- Rótulo de 1 candle à frente: horizonte curto, ruidoso; horizontes maiores e custos de latência real não foram testados.
- Sem walk-forward de ML nesta fase: o split é um único bloco cronológico 60/20/20 por série (walk-forward de modelos fica para a validação na VPS).
- **Pendente: treino com dados reais na VPS** (Fase 13, ML-011) — re-treinar, re-calibrar e reemitir este relatório com dados de exchange, antes de qualquer homologação.
- Execução continua bloqueada (403); nenhum modelo deste relatório gera ordem real.

_Gerado pelo pipeline de ML da Fase 13 — só pesquisa, nenhuma ordem real foi enviada._
