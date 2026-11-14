# Backtesting — Fase 12 (BKT-001…BKT-008)

- **Camada:** Camada 4 (apoio)
- **Fase:** Fase 12 — BKT-001…BKT-008
- **Status:** implementado e testado (38 testes em `tests/backtesting/`,
  suíte completa passando). Só simulação: nenhuma chave de API, nenhum
  envio de ordem, nenhuma conexão a conta.

## Motor escolhido (BKT-001)

O vectorbt **foi instalado e integrado** (`vectorbt 1.2.1`, ver
`requirements.txt`), mas **não é o motor canônico**: ele não modela
latência em candles, fills parciais, gas por ordem nem registro de
fill por ordem (preço/custo/slippage) — todos exigidos pelo §8
(BKT-002/BKT-003). O motor canônico é próprio (`engine.py`:
vetorizado onde faz sentido — curva de equity e métricas em NumPy —
e loop de eventos sobre os sinais, que são poucos e ficam
auditáveis). O vectorbt entra como **backend independente de
verificação cruzada** (`vectorbt_adapter.py`): os fills exatos do
motor são replayados por `vbt.Portfolio.from_orders` e o valor final
é reconciliado (`final_vectorbt == final_motor + taxas + gas`;
delta US$ 0,00 no relatório de exemplo). Se o vectorbt não estiver
instalado, o motor funciona normalmente — o adapter devolve
`{"available": False}` em vez de levantar.

## Arquivos

| Arquivo | Papel |
|---|---|
| `costs.py` | `CostModel`: taxas, spread, slippage, gas, latência, fills parciais |
| `signals.py` | Geração de sinais sem look-ahead + contadores de cobertura |
| `engine.py` | Motor de simulação, `Fill`, `Trade`, `BacktestResult` |
| `metrics.py` | Métricas §8, IC 95% (Wilson), Brier/Log Loss, checagem do protocolo 85% |
| `splits.py` | Treino/validação/teste cronológicos, walk-forward, purged CV + embargo |
| `runner.py` | Backtest único, walk-forward, multi-série |
| `vectorbt_adapter.py` | Verificação cruzada com vectorbt |
| `synthetic.py` | Séries sintéticas determinísticas (exemplo e testes) |
| `report.py` | Relatório Markdown fora da amostra |
| `backtesting.py` | Fachada (reexporta a API pública) |
| `requirements.txt` | NumPy, pandas, vectorbt |

## Regras de execução (sem look-ahead)

- O sinal do candle `i` só executa a partir da abertura do candle
  `i + 1 + latency_bars`. O sinal nunca vê o próprio candle de
  execução, e os indicadores da Fase 9 são causais (IND-008).
- Entrada a mercado na abertura do candle de execução: compra paga
  metade do spread + slippage adverso; venda, o espelho.
- Stop/alvo verificados na máxima/mínima de cada candle após o
  candle do primeiro fill. Se ambos forem tocados no mesmo candle,
  sai no stop (regra conservadora). A saída é no nível acionado,
  com slippage adverso (sem spread — o nível já é o preço de disparo).
- Fills parciais (`partial_fill_chunks > 1`): o pedido é dividido em
  chunks iguais em candles consecutivos, cada um com preço/custo/
  slippage próprios. Se o caixa não cobrir um chunk (ex.: preços
  subindo com alocação de 100%), o restante é cancelado e registrado.
- Uma posição por vez; sinais novos com posição aberta (ou pedido
  pendente) são contados como ignorados. Sinal com `valid_until_ms`
  vencido antes do candle de execução é descartado como expirado.
- Ao fim da série, a posição aberta fecha no último fechamento
  (`exit_reason="end_of_data"`, `open_at_end=True`).
- Tamanho: fração `position_size_pct` do patrimônio no primeiro
  fill, dimensionada sobre o preço efetivo de fill para que
  notional + taxa + gas caiba no capital alocado. Sem alavancagem.
- Cada fill registra `fill_id`, `order_id`, candle, lado, preço
  efetivo, preço de referência, quantidade, taxa, slippage e gas.

## Parâmetros de custo padrão (BKT-002)

| Parâmetro | Padrão | Base |
|---|---|---|
| `fee_bps` | 10 (0,10% por lado) | taxa taker de referência (Binance spot) |
| `spread_bps` | 5 | spread total; metade por lado |
| `slippage_bps` | 5 | deslizamento adverso por fill/saída |
| `gas_usd` | 0 | sem gas em CEX; DEX usa valor explícito |
| `latency_bars` | 0 | fill na abertura do próximo candle |
| `partial_fill_chunks` | 1 | fill único |

## Como rodar

```python
import sys
sys.path.insert(0, "services/backtesting")
sys.path.insert(0, "services/strategies")
# ... demais diretórios (ver tests/conftest.py)

from costs import CostModel
from runner import run_backtest, run_multi_series, run_walk_forward
from strategies import get_strategy
from synthetic import make_mixed_regime_series

strategy = get_strategy("STR-001")  # experimental, v1
series = make_mixed_regime_series(seed=7)  # sintética
out = run_backtest(strategy, series, CostModel())
print(out["metrics"]["win_rate"], out["metrics"]["profit_factor"])
```

Relatório de exemplo (STR-001, 3 séries sintéticas + walk-forward
+ vectorbt):

```bash
python3 scripts/run_backtest_str001_example.py
# gera data/reports/backtest-exemplo-STR-001.md
```

## Divisão cronológica e walk-forward (BKT-004/005/006)

- `chronological_split(n, 0.6, 0.2)`: treino/validação/teste em
  blocos contíguos, sem embaralhar.
- `walk_forward_windows(n, train_size, test_size, step, embargo_bars)`:
  janelas deslizantes; o teste sempre começa após o treino +
  embargo, sem sobreposição. No runner, cada janela usa o prefixo
  até o fim do teste como warm-up causal dos indicadores (nada após
  o fim do teste é visto) e as métricas são restritas ao trecho de
  teste. Os parâmetros das STR-001…STR-010 são fixos (v1) — a
  reotimização por janela é trabalho da Fase 13.
- **Purged CV com embargo não é aplicada ao backtest orientado a
  eventos**: o walk-forward cronológico com embargo cumpre o mesmo
  papel sem misturar passado e futuro. A purged CV (`purged_kfold_splits`)
  fica reservada à Fase 13 (features com janelas sobrepostas e
  rótulos autocorrelacionados).

## Métricas (BKT-007)

Win Rate (= precisão sobre trades) com IC 95% de Wilson, expectativa
matemática (US$, % do capital e em R), retorno líquido total,
Profit Factor, Sharpe e Sortino anualizados, Maximum Drawdown,
Calmar, payoff, streaks, Brier Score e Log Loss da probabilidade do
sinal, e **cobertura** (sinais por 100 candles avaliados + taxa de
execução trades/sinais) — sempre junto com a precisão, como exige o
protocolo do 85% (`docs/protocol-85.md`). Recall não é computável
sem um conjunto rotulado de oportunidades perdidas; o relatório
informa isso em vez de inventar um número.

Métricas anualizadas (Sharpe, Sortino, retorno anualizado, Calmar)
só são calculadas com >= 30 dias de candles; com séries mais curtas
a anualização explode — nestes casos o relatório mostra `n/d`.

## Como ler o relatório

- **Por série**: métricas + checagem dos critérios de referência
  do §8 (PF > 1,3; Sharpe > 1,5; Max DD < 10%; >= 500 operações
  fora da amostra; expectativa positiva). São critérios de
  **triagem**, não aprovação: nenhuma estratégia é aprovada só por
  backtest otimizado (§0, premissa 3) e todas as STR-001…STR-010
  continuam `experimental`.
- **Consolidado**: trades agregados das séries + retorno sobre o
  capital total alocado.
- **Walk-forward**: uma linha por janela (treino/teste, trades,
  win rate, retorno, PF, Max DD) — mede a estabilidade fora da amostra.
- **Verificação cruzada (vectorbt)**: retorno bruto de taxas, nº de
  trades e o delta da reconciliação (deve ser ~US$ 0,00).
- **Combinações testadas**: registro completo (§8) de cada
  combinação executada (estratégia × versão × parâmetros × custos ×
  série × janela).

## Relatório de exemplo (BKT-008)

`data/reports/backtest-exemplo-STR-001.md` — STR-001 v1 sobre 3
séries sintéticas de regimes mistos (BTC/ETH/SOL-like, seeds 7/8/9)
+ walk-forward (3 janelas, embargo 5). **DADOS SINTÉTICOS — não é
resultado real.** Resumo: 162 trades agregados, win rate 78,4%,
Profit Factor 3,56, retorno líquido 206,23% sobre o capital total
alocado; walk-forward instável (1 janela com 87,5% de acerto, outra
com 25%) — o que o relatório mostra sem esconder. Drawdown acima
de 10% em 2 das 3 séries e apenas 57 trades por série (longe dos
500 exigidos pelo §8): a estratégia **não** passa na triagem.

## Pendências

- Validação com dados reais na VPS (o exemplo é sintético).
- Calibração de probabilidade (Fase 13): a probabilidade das
  STR-001…STR-010 é escore de confluência, não calibrada.
- Reotimização de parâmetros por janela de walk-forward (Fase 13).
- STR-011…STR-016 ainda não implementadas (Fase 11).
