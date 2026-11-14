# Backtest exemplo — STR-001 (Trend Following) — DADOS SINTÉTICOS

> ⚠️ **DADOS SINTÉTICOS — EXEMPLO, NÃO É RESULTADO REAL.** As séries usadas aqui foram geradas por simulação (seed fixa, regimes mistos) para demonstrar o motor. Nenhum número deste relatório valida a estratégia em mercado real. A validação com dados reais é trabalho da VPS (Fase 12, pendência registrada).

- Estratégia: **STR-001 v1** (status: `experimental` — nenhuma estratégia é aprovada só por backtest otimizado; §0, premissa 3).
- Custos: taxa 10.0 bps/lado; spread 5.0 bps; slippage 5.0 bps; gas US$ 0.0; latência 0 candle(s); fills parciais em 1 chunk(s).

## Por série

### BTC/USDT (sintético)

- Símbolo: `BTC/USDT` · timeframe: `5m` · candles avaliados: 1050 · sinais gerados: 453.

| Métrica | Valor |
|---|---|
| Trades fechados | 57 |
| Vitórias / derrotas / breakeven | 45 / 12 / 0 |
| Win Rate (= precisão sobre trades) | 78.95% |
| IC 95% do Win Rate (Wilson) | 66.7% – 87.5% |
| Cobertura — sinais por 100 candles avaliados | 43.14 |
| Cobertura — taxa de execução (trades / sinais) | 12.6% (57/453 sinais) |
| Expectativa matemática (líquida, por trade) | US$ 305.71 (3.057% do capital; 1.05 R) |
| Retorno líquido total | 188.13% (anualizado: n/d — série curta demais para anualizar) |
| Profit Factor | 2.94 |
| Sharpe (anualizado) | n/d |
| Sortino (anualizado) | n/d |
| Maximum Drawdown | 16.03% |
| Calmar | n/d |
| Payoff (ganho médio / perda média) | 0.78 |
| Ganho médio / perda média (US$) | 586.90 / -748.72 |
| Maior sequência de vitórias / derrotas | 15 / 3 |
| Tempo médio em trade | 8.6 candles |
| Brier Score (probabilidade do sinal) | 0.1591 |
| Log Loss (probabilidade do sinal) | 0.5006 |
| Custos totais (taxas + slippage + gas) | US$ 3607.19 (taxas US$ 2220.35; slippage US$ 1386.85; gas US$ 0.00; 114 fills) |

| Critério de referência (§8) | Observado | Resultado |
|---|---|---|
| Profit Factor > 1,3 | 2.94 | ✅ PASS |
| Sharpe > 1,5 | n/d | ❌ FAIL |
| Maximum Drawdown < 10% | 16.03 | ❌ FAIL |
| >= 500 operações fora da amostra | 57 | ❌ FAIL |
| Expectativa líquida positiva | 305.71 | ✅ PASS |

**Resultado global:** ❌ nem todos os critérios foram atendidos (fora da amostra: sim). Estes critérios são de **triagem** (§8) — nenhum deles, sozinho ou em conjunto, aprova a estratégia (§0, premissa 3).

### ETH/USDT (sintético)

- Símbolo: `ETH/USDT` · timeframe: `5m` · candles avaliados: 1050 · sinais gerados: 437.

| Métrica | Valor |
|---|---|
| Trades fechados | 52 |
| Vitórias / derrotas / breakeven | 40 / 12 / 0 |
| Win Rate (= precisão sobre trades) | 76.92% |
| IC 95% do Win Rate (Wilson) | 63.9% – 86.3% |
| Cobertura — sinais por 100 candles avaliados | 41.62 |
| Cobertura — taxa de execução (trades / sinais) | 11.9% (52/437 sinais) |
| Expectativa matemática (líquida, por trade) | US$ 335.04 (3.350% do capital; 1.04 R) |
| Retorno líquido total | 186.37% (anualizado: n/d — série curta demais para anualizar) |
| Profit Factor | 3.25 |
| Sharpe (anualizado) | n/d |
| Sortino (anualizado) | n/d |
| Maximum Drawdown | 17.57% |
| Calmar | n/d |
| Payoff (ganho médio / perda média) | 0.97 |
| Ganho médio / perda média (US$) | 629.15 / -645.34 |
| Maior sequência de vitórias / derrotas | 16 / 5 |
| Tempo médio em trade | 8.9 candles |
| Brier Score (probabilidade do sinal) | 0.1630 |
| Log Loss (probabilidade do sinal) | 0.5067 |
| Custos totais (taxas + slippage + gas) | US$ 3159.72 (taxas US$ 1944.94; slippage US$ 1214.78; gas US$ 0.00; 104 fills) |

| Critério de referência (§8) | Observado | Resultado |
|---|---|---|
| Profit Factor > 1,3 | 3.25 | ✅ PASS |
| Sharpe > 1,5 | n/d | ❌ FAIL |
| Maximum Drawdown < 10% | 17.57 | ❌ FAIL |
| >= 500 operações fora da amostra | 52 | ❌ FAIL |
| Expectativa líquida positiva | 335.04 | ✅ PASS |

**Resultado global:** ❌ nem todos os critérios foram atendidos (fora da amostra: sim). Estes critérios são de **triagem** (§8) — nenhum deles, sozinho ou em conjunto, aprova a estratégia (§0, premissa 3).

### SOL/USDT (sintético)

- Símbolo: `SOL/USDT` · timeframe: `5m` · candles avaliados: 1050 · sinais gerados: 450.

| Métrica | Valor |
|---|---|
| Trades fechados | 53 |
| Vitórias / derrotas / breakeven | 42 / 11 / 0 |
| Win Rate (= precisão sobre trades) | 79.25% |
| IC 95% do Win Rate (Wilson) | 66.5% – 88.0% |
| Cobertura — sinais por 100 candles avaliados | 42.86 |
| Cobertura — taxa de execução (trades / sinais) | 11.8% (53/450 sinais) |
| Expectativa matemática (líquida, por trade) | US$ 436.02 (4.360% do capital; 1.13 R) |
| Retorno líquido total | 244.20% (anualizado: n/d — série curta demais para anualizar) |
| Profit Factor | 4.91 |
| Sharpe (anualizado) | n/d |
| Sortino (anualizado) | n/d |
| Maximum Drawdown | 9.68% |
| Calmar | n/d |
| Payoff (ganho médio / perda média) | 1.29 |
| Ganho médio / perda média (US$) | 690.78 / -536.69 |
| Maior sequência de vitórias / derrotas | 13 / 4 |
| Tempo médio em trade | 8.4 candles |
| Brier Score (probabilidade do sinal) | 0.1652 |
| Log Loss (probabilidade do sinal) | 0.5137 |
| Custos totais (taxas + slippage + gas) | US$ 3410.47 (taxas US$ 2099.50; slippage US$ 1310.97; gas US$ 0.00; 106 fills) |

| Critério de referência (§8) | Observado | Resultado |
|---|---|---|
| Profit Factor > 1,3 | 4.91 | ✅ PASS |
| Sharpe > 1,5 | n/d | ❌ FAIL |
| Maximum Drawdown < 10% | 9.68 | ✅ PASS |
| >= 500 operações fora da amostra | 53 | ❌ FAIL |
| Expectativa líquida positiva | 436.02 | ✅ PASS |

**Resultado global:** ❌ nem todos os critérios foram atendidos (fora da amostra: sim). Estes critérios são de **triagem** (§8) — nenhum deles, sozinho ou em conjunto, aprova a estratégia (§0, premissa 3).

## Consolidado (todas as séries)

| Métrica | Valor |
|---|---|
| Séries | 3 |
| Trades (agregados) | 162 |
| Win Rate (agregado) | 78.40% |
| Profit Factor (agregado) | 3.56 |
| Expectativa (líquida, por trade) | US$ 357.76 |
| Retorno líquido (capital total alocado) | 206.23% |

## Walk-forward

- Janelas: 3 · trades agregados nos testes: 13.

| Janela | Treino | Teste | Trades | Win Rate | Retorno líq. | PF | Max DD |
|---|---|---|---|---|---|---|---|
| 1 | (0, 400) | (405, 505) | 1 | 0.0% | -2.48% | 0.00 | 4.77% |
| 2 | (200, 600) | (605, 705) | 8 | 87.5% | 23.55% | 8.20 | 3.75% |
| 3 | (400, 800) | (805, 905) | 4 | 25.0% | -7.40% | 0.27 | 10.85% |

## Verificação cruzada (vectorbt)

- Backend: `vectorbt 1.2.1` (replay dos fills exatos do motor).
- Retorno bruto de taxas (vectorbt): 210.33% · trades: 57 · max DD: 13.82% · Sharpe: 60.51 · Profit Factor: 3.60.
- Reconciliação: final_vectorbt − (final_motor + taxas + gas) = US$ 0.00 (taxas US$ 2220.35; gas US$ 0.00). Delta ~0 indica que a contabilidade dos dois lados concorda.
- Replay dos fills exatos do motor (preço e quantidade); taxas e gas reconciliados fora do replay: final_vectorbt == final_motor + taxas + gas.

## Combinações testadas (§8 — registro completo)

Total: **6** combinações (estratégia × versão × parâmetros × custos × série × janela).

1. `STR-001` v1 · série `BTC/USDT (sintético)` · janela [0:1100] · capital US$ 10000 · posição 100% · custos {'fee_bps': 10.0, 'spread_bps': 5.0, 'slippage_bps': 5.0, 'gas_usd': 0.0, 'latency_bars': 0, 'partial_fill_chunks': 1}.
2. `STR-001` v1 · série `ETH/USDT (sintético)` · janela [0:1100] · capital US$ 10000 · posição 100% · custos {'fee_bps': 10.0, 'spread_bps': 5.0, 'slippage_bps': 5.0, 'gas_usd': 0.0, 'latency_bars': 0, 'partial_fill_chunks': 1}.
3. `STR-001` v1 · série `SOL/USDT (sintético)` · janela [0:1100] · capital US$ 10000 · posição 100% · custos {'fee_bps': 10.0, 'spread_bps': 5.0, 'slippage_bps': 5.0, 'gas_usd': 0.0, 'latency_bars': 0, 'partial_fill_chunks': 1}.
4. `STR-001` v1 · série `BTC/USDT [janela 1]` · janela [405:505] · capital US$ 10000 · posição 100% · custos {'fee_bps': 10.0, 'spread_bps': 5.0, 'slippage_bps': 5.0, 'gas_usd': 0.0, 'latency_bars': 0, 'partial_fill_chunks': 1}.
5. `STR-001` v1 · série `BTC/USDT [janela 2]` · janela [605:705] · capital US$ 10000 · posição 100% · custos {'fee_bps': 10.0, 'spread_bps': 5.0, 'slippage_bps': 5.0, 'gas_usd': 0.0, 'latency_bars': 0, 'partial_fill_chunks': 1}.
6. `STR-001` v1 · série `BTC/USDT [janela 3]` · janela [805:905] · capital US$ 10000 · posição 100% · custos {'fee_bps': 10.0, 'spread_bps': 5.0, 'slippage_bps': 5.0, 'gas_usd': 0.0, 'latency_bars': 0, 'partial_fill_chunks': 1}.

## Notas e pendências

- Métricas anualizadas (Sharpe, Sortino, retorno anualizado, Calmar) só são calculadas com >= 30 dias de candles; com séries mais curtas a anualização explode e o número vira lixo — nestes casos o relatório mostra n/d.
- A probabilidade das STR-001…STR-010 é escore de confluência, NÃO calibrada (Fase 13): Brier/Log Loss medem o afastamento, sem fingir calibração.
- Recall não é computável sem um conjunto rotulado de oportunidades perdidas; a cobertura (sinais/100 candles e taxa de execução) é o substituto informado junto com a precisão.
- Purged CV com embargo **não** foi aplicada ao backtest orientado a eventos: o walk-forward cronológico com embargo cumpre o mesmo papel; a purged CV fica reservada à Fase 13 (features com janelas sobrepostas).
- Walk-forward com embargo de 5 candles entre treino e teste.
- Séries sintéticas geradas por `synthetic.make_mixed_regime_series` (seeds 7/8/9; regimes TREND_UP, RANGE, TREND_DOWN, EXPANSION).
- Validação com dados reais na VPS e calibração de probabilidade são pendências (Fase 13).

_Gerado pelo motor de backtest da Fase 12 (só simulação — nenhuma ordem real foi enviada)._
