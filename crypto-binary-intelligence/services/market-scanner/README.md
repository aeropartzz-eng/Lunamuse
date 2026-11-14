# Market Scanner — Scanner multinível

Camada 4 — Inteligência (especificação v4.1, §4, Fase 8 — SCN-001…SCN-004).

## Decisão de colocação

Serviço próprio em `services/market-scanner/` (não dentro de
`services/market-data/`): o `docker-compose.yml` / §11 lista
`market-scanner` como serviço Docker separado, e o scanner é
consumidor do Market Data Engine, não parte do pipeline de dados.
Ele consome o protocolo `MarketDataSource` e nunca duplica o
pipeline da Fase 7 (trades, dedup, candle builder, book manager).

## Módulos

| Módulo | Tarefa | Conteúdo |
|---|---|---|
| `source.py` | SCN-001…003 (integração) | Protocolo `MarketDataSource` + `AdapterMarketDataSource` |
| `scanner.py` | SCN-001/002/003 | `DiscoveryScanner`, `ActiveScanner`, `PriorityScanner` + métricas puras |
| `promotion.py` | SCN-004 | `PromotionEngine`, `ScannerThresholds`, `PromotionEvent` |

## Interface `MarketDataSource` (ponto de integração com a Fase 7)

Uma instância por exchange, somente leitura pública:

```python
get_ticker(symbol) -> Ticker
get_candles(symbol, timeframe, limit=100) -> list[Candle]
get_trades(symbol, limit=100) -> list[Trade]
get_order_book(symbol, depth=20) -> OrderBook
```

A Fase 7 (em paralelo) vai expor esse protocolo no engine. Como ele
ainda não existe no repo, o protocolo é definido aqui como
`typing.Protocol` estrutural — qualquer objeto com esses métodos
serve, sem herança. Até lá, `AdapterMarketDataSource(adapter)` liga
um `ExchangeAdapter` da Fase 3 (Binance, Bybit, OKX, Coinbase,
Kraken, Bitget, Gate.io) ao scanner. Quando o engine da Fase 7
estiver pronto, basta passar a instância dele; o adaptador vira
fallback de leitura direta.

Os módulos não importam `models` em runtime (evita acoplamento de
`sys.path` entre diretórios com hífen); trabalham por duck typing
sobre os modelos validados do contrato universal. Os testes importam
os módulos com os diretórios no `sys.path` (ver `tests/conftest.py`).

## Níveis e metas de dimensionamento (§4)

| Nível | Conteúdo | Meta |
|---|---|---|
| 1 Discovery | ticker, preço/variação, volume, candles de referência, liquidez estimada, novos pares | até 2.000 pares |
| 2 Active | trades, candles de alta resolução, volatilidade, volume relativo, padrões | até 200 instrumentos |
| 3 Priority | book, bid/ask, CVD, imbalance, absorção, liquidity sweep | até 50 ativos; até 20 com book aprofundado |

Os números são metas de dimensionamento, não limites de corretora.

## Regras de promoção/despromoção (SCN-004)

Thresholds em `ScannerThresholds` (todos configuráveis; valores
iniciais conservadores, **não calibrados com dados reais** —
calibração com o feed ao vivo na VPS é pendência):

- **Discovery → Active**: liquidez estimada ≥ US$ 50 mil E
  (volume relativo ≥ 1,5 com |variação| ≥ 2% OU volume relativo
  ≥ 3,0 OU volatilidade ≥ 5% com volume relativo ≥ 1,2).
- **Active → Priority**: liquidez ≥ US$ 250 mil E
  (volume relativo ≥ 3,0 com volatilidade ≥ 3% OU |imbalance|
  ≥ 0,6 com spread ≤ 20 bps). Sinal forte pode subir dois níveis
  numa avaliação (um evento por transição).
- **Despromoção**: exige `demote_streak` = 3 avaliações fracas
  seguidas (volume relativo < 0,8 E |variação| < 1%), ou é imediata
  se ilíquido para o nível ou (Priority) com spread > 100 bps.
- **Caps**: ao estourar 200 Active / 50 Priority, sai o menor
  score (registrado como despromoção por cap). Deep book: só os 20
  Priority de maior score.

Toda transição gera um `PromotionEvent` com motivo
(`engine.events`), auditável. A liquidez do Nível 1 é *estimada*
(`volume_24h × preço`, assume volume em moeda base); a profundidade
real vem do book no Nível 3.

## Limitações conhecidas

- `detect_sweep` e a heurística de absorção usam o snapshot de book
  vigente — com book posterior ao trade, são aproximações de
  triagem, não prova de sweep/absorção.
- Padrões de candle aqui são só triagem (doji, engulfing,
  hammer); o Pattern Engine completo é a Fase 10.
- Thresholds não calibrados com dados reais (ver acima).

## Testes

```bash
python3 -m pytest tests/scanner/ -q
```

Fakes do `MarketDataSource`; sem rede, sem chave de API.
