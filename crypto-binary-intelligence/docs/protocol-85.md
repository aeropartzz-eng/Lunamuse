# Protocolo do 85% — Crypto & Binary Intelligence

> Fonte: especificação **v4.1 (13/11/2026), §0, §6, §8 e §17**.
> Fase 0 — GOV-006. Versão 1.0 — 13/11/2026.
> Status: **rascunho aguardando aprovação formal do responsável**
> (ver `governance-checklist.md`).
>
> **A meta de 85% é um objetivo de pesquisa para sinais seletivos,
> NÃO uma promessa de acerto, lucro ou rentabilidade** (§0,
> premissa 1; §8).

## 1. O que a meta significa — e o que não significa

1. 85% é a **taxa de acerto de referência** buscada em **subconjuntos
   seletivos** de sinais — isto é, sinais filtrados por critérios
   rigorosos, não todos os sinais gerados.
2. Não é promessa de acerto, lucro ou rentabilidade (§0, premissa 1).
   Nenhum material de divulgação, sinal ou relatório pode apresentar
   85% como garantia.
3. **Precisão deve ser avaliada junto com cobertura, expectativa
   matemática, custos, intervalo de confiança e desempenho fora da
   amostra** (§0, premissa 2).
4. **Um sistema pode ter alta precisão e cobertura muito baixa;
   ambos devem ser informados** (§8). Precisão sem cobertura é
   informação incompleta e não pode aprovar uma estratégia.
5. **Nenhuma estratégia será aprovada somente por backtest
   otimizado** (§0, premissa 3).

## 2. Amostras mínimas e critérios de referência (§8)

### 2.1 Opções binárias (pesquisa/simulação)

| Critério | Valor de referência |
|---|---|
| Resultados fora da amostra | **≥ 1.000** |
| Intervalo de confiança | **95%** |
| Payout | considerado no cálculo |
| Expectativa matemática | **positiva** (líquida de custos) |
| Cobertura | divulgada junto com a precisão |

### 2.2 Crypto scalping (por estratégia)

| Critério | Valor de referência |
|---|---|
| Operações fora da amostra por estratégia | **≥ 500** |
| Custos | incluídos (taxas, spread, slippage, liquidez, latência) |
| Profit Factor de referência | **> 1,3** |
| Sharpe de referência | **> 1,5** |
| Drawdown (máximo) de referência | **< 10%** |

Notas:

- Estes critérios são **parâmetros internos propostos** (§8), não
  garantias de desempenho futuro.
- **Correlação temporal entre operações exige métodos de validação
  adicionais** (§8): amostras de operações correlacionadas no tempo
  não podem ser tratadas como independentes sem ajuste.
- Os valores de Profit Factor, Sharpe e drawdown são **de
  referência** (§8): servem como barra inicial de triagem, não como
  aprovação automática.

## 3. Separação treino / validação / teste e walk-forward (§8)

1. **Separar treino, validação e teste** cronologicamente. Dados de
   teste nunca participam de ajuste de parâmetros, seleção de
   estratégia ou calibração de probabilidade.
2. **Sem dados futuros (sem look-ahead):** nenhuma informação
   posterior ao instante da decisão pode entrar no cálculo do sinal,
   do indicador ou da probabilidade (ver também §9, IND-008, e §12,
   BKT-004).
3. **Walk-Forward** obrigatório: janelas de treino e teste avançam
   no tempo; resultados reportados por janela.
4. **Purged Cross-Validation e embargo quando adequados** (§8,
   §12 BKT-006), para evitar vazamento por sobreposição de janelas e
   autocorrelação.
5. **Registrar todas as combinações testadas** (§8): o relatório de
   uma estratégia inclui quantas variantes foram testadas, para que
   o risco de overfitting (múltiplos testes) seja visível.
6. Testar em **ativos, meses e regimes diferentes** (§8, §12
   BKT-008): resultado válido num só ativo, mês ou regime não
   aprova a estratégia.

## 4. Custos e métricas obrigatórias (§8)

Todo relatório de validação inclui, no mínimo:

- **Custos incluídos:** taxas, spread, slippage, liquidez e
  latência; fills parciais considerados (§8, §12 BKT-002/BKT-003).
- **Métricas:** Win Rate, expectativa matemática, retorno líquido,
  Profit Factor, Sharpe e Sortino, Maximum Drawdown, Calmar, Brier
  Score, Log Loss, Precision e Recall, **Coverage** e intervalos de
  confiança (§8).
- **Probabilidade calibrada:** Brier Score e Log Loss medem a
  qualidade da probabilidade, não só o acerto binário (§8, §13
  ML-006/ML-007); selective prediction e incerteza explícita (§8,
  ML-008).

## 5. Regra de divulgação

Toda vez que a precisão for informada — em relatório, sinal, painel
ou mensagem — ela vem acompanhada de:

1. cobertura;
2. expectativa matemática líquida;
3. custos considerados;
4. intervalo de confiança (95%);
5. desempenho fora da amostra (tamanho da amostra e período).

**Precisão isolada, sem esses cinco elementos, não pode ser usada
para aprovar, promover ou divulgar uma estratégia.**

## 6. Status das estratégias (§6)

Cada estratégia tem ID, regras, parâmetros, versão, mercados,
timeframes, filtros, custos, histórico de testes e status:
**experimental, em teste, aprovada ou desativada**. Só estratégias
com status **aprovada** — após cumprir este protocolo e as
aprovações da `execution-policy.md` — podem gerar sinais para
execução.

## 7. Cobertura GOV

Este protocolo atende **GOV-006** (protocolo de 85%: amostras,
cobertura, intervalo de confiança, teste fora da amostra — aceite:
protocolo estatístico).
Mapeamento completo GOV-001 a GOV-007 em
[`governance-checklist.md`](governance-checklist.md).

## 8. Linha de base aceita pelo Will (2026-11-13)

- **Precisão seletiva atual: 71,95% (~72%)**, medida no relatório
  de 85% com dados sintéticos (82 amostras seletivas; IC 95% de
  Wilson 61,41%–80,52%). Abaixo da meta de 85%, mas aceita como
  **linha de base de partida** — "já é muita coisa".
- **Caminho de melhoria definido:** novos indicadores, nova
  configuração (parâmetros/recalibração) e acúmulo de histórico com
  dados reais no VPS. A porcentagem se ajusta com o tempo, conforme
  o histórico cresce.
- **A meta de 85% não muda.** E a precisão sozinha continua não
  aprovando estratégia (§5): expectativa líquida (que no teste
  sintético ficou em −2,14 bps/operação com custos), cobertura
  (mín. 500 amostras) e desempenho fora da amostra continuam
  obrigatórios antes de qualquer promoção a "aprovada" ou execução.
