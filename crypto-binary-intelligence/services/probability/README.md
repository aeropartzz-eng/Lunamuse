# Probability Engine — Machine Learning (Fase 13)

- **Camada:** Camada 4
- **Fase:** Fase 13 — ML-001…ML-011 (especificação v4.1, §8)
- **Status:** implementado e validado com dados sintéticos (2026-11-13)

Modelos probabilísticos, calibração e o relatório do 85%.
A probabilidade calibrada alimenta o Signal Engine — nunca operar
com probabilidade não calibrada (premissa 7).

> ⚠️ **Só pesquisa com dados sintéticos.** Nenhum número aqui
> valida qualquer modelo em mercado real. A meta de 85% é um
> objetivo de pesquisa para sinais seletivos, não uma promessa
> (§0, premissa 1). Execução continua bloqueada (403).

## Módulos

Os módulos usam o prefixo `ml_` para não colidir com `metrics.py` /
`report.py` de backtesting e `models.py` dos conectores (todos no
`sys.path` dos testes). `probability.py` é a fachada que re-exporta
a API pública.

| Módulo | Tarefa | Conteúdo |
|---|---|---|
| `ml_features.py` | ML-001 | Feature Store: 29 features (v1) de candles + indicadores (Fase 9) + regime (Fase 11) + padrões; versionamento; sem look-ahead; save/load em `data/features/` |
| `ml_models.py` | ML-002…ML-005 | Logistic Regression, Random Forest, XGBoost, LightGBM — mesma interface `fit` / `predict` / `predict_proba` |
| `ml_calibration.py` | ML-006 | Platt (sigmoid) e isotônica, ajustadas na validação; curva de calibração e ECE |
| `ml_metrics.py` | ML-007 | Brier Score, Log Loss, Precision/Recall/F1, IC de Wilson 95%, Win Rate e Expectancy do sinal |
| `ml_selective.py` | ML-008 | Selective Prediction: precisão **sempre** com cobertura |
| `ml_drift.py` | ML-009 | Concept Drift por PSI (alerta em PSI ≥ 0,25) + mudança de média/desvio |
| `ml_ensemble.py` | ML-010 | Ensemble por média ponderada (pesos otimizados na validação) e stacking; comparação honesta |
| `ml_report.py` | ML-011 | Relatório do 85% (`data/reports/relatorio-85.md`) |

## Modelos e ambiente

- scikit-learn 1.9.1 (Logistic Regression, Random Forest, calibração, stacking).
- **XGBoost 3.4.1 e LightGBM 4.7.0 instalados neste ambiente** via
  `pip install --user --break-system-packages xgboost lightgbm`
  (o Python do sistema é "externally managed", PEP 668 — o
  `--break-system-packages` foi necessário). Os quatro modelos
  treinaram na Fase 13.
- Se um pacote não estiver instalado, o modelo fica marcado como
  indisponível em `AVAILABLE_MODELS` e `train_models` o lista em
  `skipped` — nenhum resultado dele é inventado.
- O `.venv` do projeto **não** tem scikit-learn/xgboost/lightgbm;
  rode os testes e o pipeline com o **Python do sistema**
  (`python3 -m pytest tests/ -q`). Na VPS, instalar os pacotes do
  `requirements.txt` no venv do projeto.

## Como treinar

```bash
# Pipeline completo (sintético): features, treino, calibração,
# selective, drift, ensemble e relatório do 85%
python3 scripts/run_ml_phase13.py
```

O pipeline usa 3 séries sintéticas (BTC/ETH/SOL, seeds 7/8/9,
mesmos regimes do exemplo da Fase 12), split cronológico 60/20/20
por série (Fase 12), calibração Platt na validação e avaliação no
teste. Artefatos:

- `data/features/BTC-USDT-5m-v1.{npz,json}` (e ETH/SOL);
- `data/models/{logistic_regression,random_forest,xgboost,lightgbm}.pkl`,
  `ensemble_stacking.pkl`, `ensemble-weights.json`;
- `data/reports/relatorio-85.md`.

## Como calibrar

```python
from ml_calibration import CalibratedModel
cal = CalibratedModel(modelo_treinado, method="sigmoid")  # ou "isotonic"
cal.fit(X_validacao, y_validacao)   # nunca o teste
proba_calibrada = cal.predict_proba(X_teste)[:, 1]
```

`compare_calibration(y, proba_crua, proba_calibrada)` devolve
Brier/Log Loss/ECE antes e depois. A calibração é Platt scaling
(regressão logística sobre a proba crua) ou isotônica — implementação
direta, sem `CalibratedClassifierCV` (o `cv="prefit"` foi removido
no scikit-learn 1.9).

## Como ler o relatório do 85%

`data/reports/relatorio-85.md` traz, sempre juntos (§5 do protocolo
do 85%): precisão seletiva **com cobertura**, IC 95% (Wilson),
expectativa líquida de custos (30 bps/trade), amostra fora da
amostra e comparação com os critérios do §8. O veredicto é
**ATINGIDA** só se precisão seletiva ≥ 85% **e** subconjunto
seletivo ≥ 500 amostras **e** expectativa líquida positiva —
caso contrário, **NÃO ATINGIDA**, com os motivos.

**Resultado da Fase 13 (sintético, 2026-11-13): ❌ NÃO ATINGIDA.**
Melhor modelo individual: Logistic Regression (Brier calibrado
0,2204 no teste; acurácia 68,07%). Selective: precisão 71,95% com
cobertura 12,77% (82/642; IC 95% 61,41%–80,52%) no limiar 0,66.
Expectativa líquida do melhor modelo: −2,14 bps/trade (custos de
30 bps incluídos). Stacking venceu o melhor individual por pouco
(Brier 0,2195 vs. 0,2204). Drift detectado entre treino e teste
(PSI máx. 3,423 — regimes diferentes entre os blocos). Detalhes e
limitações no próprio relatório.

## Decisões

- **Rótulo:** direção do fechamento 1 candle à frente
  (`y=1` se `close[i+1] > close[i]`); horizonte curto e ruidoso —
  horizontes maiores ficam para a validação na VPS.
- **Sinal do modelo:** prevê 1 → opera comprado; prevê 0 → WAIT /
  NO TRADE (sem short). Custo de 30 bps/trade (Fase 12).
- **Limiar seletivo:** menor limiar (varredura 0,50–0,99) com
  precisão ≥ 85% e cobertura ≥ 5%; se nenhum cumpre, reporta-se o
  de maior precisão — nunca se inventa um limiar.
- **Drift:** PSI < 0,10 estável; 0,10–0,25 moderado; ≥ 0,25 alerta
  (limite padrão da literatura de risco de modelos).
- **Pesos do ensemble:** busca aleatória determinística (seed 42,
  2.000 amostras do simplex) minimizando o Brier **na validação**.

## Testes

`tests/probability/` (33 testes, sem rede): feature store sem
look-ahead (perturbação de candles futuros não muda as features
passadas), cada modelo treina e prevê, calibração melhora o Brier
de um classificador propositalmente superconfiante, selective
reduz cobertura e aumenta precisão, drift detectado numa mudança
de regime, ensemble roda e é comparado, relatório gerado com
marcador de sintético e veredicto.

## Pendências

- Treino com **dados reais na VPS** (re-treinar, re-calibrar e
  reemitir o relatório do 85% com dados de exchange).
- Walk-forward de ML (hoje é um único split cronológico 60/20/20).
- Horizontes de rótulo maiores e latência real.
- Nada disso autoriza execução: LIVE continua bloqueado (403).
