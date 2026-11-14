# Cross-Exchange Intelligence

Camada 4 — Inteligência (especificação v4.1, Fase 8 — XCH-001…XCH-005).

## Módulo

`cross_exchange.py` (módulo plano; o diretório tem hífen — os testes
o importam com o diretório no `sys.path`, ver `tests/conftest.py`).

| Função | Tarefa | Conteúdo |
|---|---|---|
| `canonical_pair` / `equivalent_pairs` | XCH-001 | Normaliza pares equivalentes (`BTCUSDT`, `btc-usdt`, `XBT/USD` na Kraken → `BTC/USD`; perpétuo → `BTC/USDT:USDT`) |
| `compare_prices` / `group_tickers_by_pair` | XCH-002 | Compara preços entre exchanges, agrupados por par canônico |
| `reference_price` | XCH-003 | Preço de referência ponderado por volume (quote vol ≈ `volume_24h × preço`; sem volume, peso igual) |
| `detect_divergences` | XCH-004 | Divergência por par; sinalizada acima do threshold (default 50 bps = 0,5%) |
| `simulate_arbitrage` / `find_arbitrage_opportunities` | XCH-005 | Simulação de arbitragem líquida com custos |

## Arbitragem líquida (XCH-005) — só simulação, nunca execução

`simulate_arbitrage` calcula, para compra na exchange mais barata e
venda na mais cara:

- **lucro bruto** = (preço de venda − preço de compra) × quantidade;
- **custos** = taxa taker de compra + taxa taker de venda
  (`FeeSchedule`, defaults em `DEFAULT_TAKER_FEES`) + slippage
  estimado nas duas pernas (default 10 bps por perna) + taxa de
  transferência (default US$ 0);
- **lucro líquido** e **líquido em bps**; `capital_locked_usd` é o
  custo da perna de compra (capital imobilizado).

`viable` exige lucro líquido positivo E acima de `min_net_bps`.
Lucro bruto positivo com líquido negativo é **rejeitado** — é o caso
típico de divergência pequena comida por taxas e slippage.

Limites da simulação (documentados no código):

- As taxas taker padrão são **defaults de planejamento, não
  cotações ao vivo** (variam por tier/volume); confirmar na
  documentação da exchange antes de usar como base de decisão.
- Não modela tempo de transferência nem risco de execução (o preço
  pode andar enquanto a transferência confirma); divergência é
  observação, não oportunidade garantida.

Nenhuma função aqui envia ordens, conecta contas ou usa chave de
API. A execução continua bloqueada (403) e o scaffold força
RESEARCH quando `EXECUTION_MODE=LIVE`.

## Testes

```bash
python3 -m pytest tests/cross-exchange/ -q
```

Fakes de `Ticker`; sem rede, sem chave de API, sem execução.
Cobrem: normalização (incluindo alias Kraken `XBT`→`BTC` e o
desempate `XBTUSD` → `BTC/USD`, não `XB/TUSD`), referência
ponderada, divergência acima/abaixo do threshold, arbitragem
viável, bruto positivo/líquido negativo rejeitado, taxa de
transferência e `min_net_bps`.

## Smoke ao vivo

Ver `data/reports/fase8-smoke.md` — comparação de BTC/USDT em
exchanges públicas (endpoints públicos, sem chave).
