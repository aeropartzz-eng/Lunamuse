# Smoke ao vivo — Fase 8 (SCN/XCH)

Data: 2026-11-13 ~09:39 (-03, horário de Brasília).
Método: `urllib` direto aos endpoints públicos de ticker, sem chave
de API, sem conta, sem ordem. Preços de BTC/USD(BTC/USDT) lidos em
sequência (não é um snapshot simultâneo — há segundos entre as
leituras; a divergência abaixo é observação, não oportunidade).

| Exchange | Endpoint | Resultado | Preço |
|---|---|---|---|
| Kraken | `api.kraken.com/0/public/Ticker?pair=XBTUSD` | 200 | US$ 69.040,70 |
| Coinbase | `api.exchange.coinbase.com/products/BTC-USD/ticker` | 200 | US$ 69.039,23 |
| OKX | `www.okx.com/api/v5/market/ticker?instId=BTC-USDT` | 200 | US$ 69.107,10 |
| Gate.io | `api.gateio.ws/api/v4/spot/tickers?currency_pair=BTC_USDT` | 200 | US$ 69.108,10 |
| Binance | `api.binance.com/api/v3/ticker/price?symbol=BTCUSDT` | HTTP 451 | — (bloqueio geográfico a partir desta VM) |
| Bybit | `api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT` | HTTP 403 | — (bloqueado a partir desta VM) |

## Divergência observada (4 exchanges com preço)

- Menor: Coinbase US$ 69.039,23; maior: Gate.io US$ 69.108,10.
- Referência (média simples, ~US$ 69.073,76): spread
  (69.108,10 − 69.039,23) / 69.073,76 × 10.000 ≈ **9,97 bps**.
- Threshold da Fase 8: 50 bps → **não sinalizada** (`flagged=False`
  pelo critério de `detect_divergences`).
- A divergência de ~10 bps é ordem de grandeza menor que os custos
  típicos (taxas taker ~10 bps por perna + slippage): a simulação de
  arbitragem a rejeitaria como líquida negativa — coerente com o
  teste `test_arbitrage_rejected_when_gross_positive_but_net_negative`.

## Observações

- Binance (451) e Bybit (403) bloqueiam a partir desta VM; na VPS
  (região a confirmar) o acesso pode diferir — revalidar lá.
- Kraken devolve o par como `XXBTZUSD` e o preço em USD, não USDT:
  a normalização `XBT`→`BTC` (XCH-001) é o que permite agrupá-lo
  com os demais — e a comparação BTC/USD vs BTC/USDT mistura
  stablecoin com dólar, diferença que a Fase 8 registra mas não
  corrige (não há conversão USD/USDT no escopo).
