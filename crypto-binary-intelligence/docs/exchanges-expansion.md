# Expansão CEX — avaliação (CEX-011)

> Especificação v4.1, §3 (CEX — Expansão) e Fase 5, tarefa CEX-011.
> Avaliação feita em 2026-11-13, **sem implementar** estes
> conectores: só viabilidade do conector público via CCXT e o que
> faltaria para implementar. Nenhuma rede foi usada para avaliar —
> a verificação é sobre o CCXT 4.5.92 instalado no projeto
> (`ccxt.exchanges` + flags `has.*`) e a documentação pública.

## Veredicto geral

**As 6 exchanges são viáveis como conector público via CCXT.**
Todas têm `fetch_markets`, `fetch_ticker`, `fetch_trades`,
`fetch_ohlcv` e `fetch_order_book` públicos implementados no CCXT.
Nenhuma exigiria código novo na base compartilhada
(`ccxt_adapter.CCXTAdapter`): o trabalho por exchange seria o
mesmo da Fase 5 — uma subclasse de ~40 linhas (id CCXT, token
bucket local, flags de funding/OI), um README com limites e
restrições regionais, testes com fakes e um smoke ao vivo.

| Exchange | CCXT id | Ticker | Trades | OHLCV | Book | Funding | OI | Timeframes |
|---|---|---|---|---|---|---|---|---|
| KuCoin | `kucoin` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 14 |
| MEXC | `mexc` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | 10 |
| BingX | `bingx` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 14 |
| Bitfinex | `bitfinex` | ✅ | ✅ | ✅ | ✅ | ⚠️ emulado | ✅ | 13 |
| HTX | `htx` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 10 |
| Crypto.com | `cryptocom` | ✅ | ✅ | ✅ | ✅ | ✅ | ❓ | 12 |

`rateLimit` do CCXT (ms entre chamadas): KuCoin 7,5 · MEXC 50 ·
BingX 100 · Bitfinex 250 · HTX 100 · Crypto.com 10.

## Por exchange

### KuCoin — ✅ viável
- CCXT `kucoin` (+ `kucoinfutures` separado para futuros).
- Market data público sem chave; WebSocket público exige token
  (endpoint público de token, sem autenticação de conta).
- Rate limit: pool spot VIP0 de 4.000 req / 30 s (fonte: docs
  KuCoin / compilação 2026-10-29); confirmar o valor atual antes
  de implementar.
- Faltaria: adapter + README (limites, regiões) + testes + smoke.
  Atenção: KuCoin não atende várias jurisdições (inclui EUA e
  China continental); futuros ficam no id `kucoinfutures`.

### MEXC — ✅ viável, com ressalva de OI
- CCXT `mexc`; spot e futuros no mesmo id.
- Rate limit: spot 500 req / 10 s por endpoint (fonte:
  compilação 2026-10-29); confirmar antes de implementar.
- Ressalva: **`fetchOpenInterest` não implementado no CCXT**
  (`has = False`) — o OI levantaria `ExchangeError` (BAD_RESPONSE)
  como no Gate.io, ou exigiria chamada nativa ao endpoint de
  contratos.
- Faltaria: adapter + README + testes + smoke; documentar a
  ausência de OI e a instabilidade histórica da documentação MEXC.

### BingX — ✅ viável
- CCXT `bingx`; spot e swap no mesmo id.
- Rate limit: market data 500 req / 10 s por IP (fonte:
  compilação 2026-10-29); ordens de futuros 10/s.
- Faltaria: adapter + README + testes + smoke. Atenção às
  restrições regionais da BingX (lista oficial; inclui EUA).

### Bitfinex — ✅ viável, com ressalva de funding
- CCXT `bitfinex`.
- Ressalva: **`fetchFundingRate` é "emulado" no CCXT** (derivado
  de outros campos, não lido de um endpoint nativo de funding) —
  o valor precisa ser validado contra a API antes de uso em
  sinais; documentar como dado derivado, não nativo.
- Bitfinex não atende "US persons" nem várias jurisdições.
- Faltaria: adapter + README + testes + smoke + validação do
  funding emulado contra o endpoint nativo.

### HTX — ✅ viável
- CCXT `htx` (ex-Huobi).
- Faltaria: adapter + README + testes + smoke. Atenção: a HTX
  não atende China continental, EUA e jurisdições sancionadas;
  confirmar a lista atual antes de implementar.

### Crypto.com Exchange — ✅ viável, com ressalva de OI
- CCXT `cryptocom`.
- Ressalva: **`fetchOpenInterest` com status desconhecido no
  CCXT** (`has = None`) — testar contra a API real antes de
  prometer OI; se ausente, erro claro (BAD_RESPONSE) como no
  Gate.io.
- Faltaria: adapter + README + testes + smoke + teste real de OI.

## O que falta para qualquer uma das 6 (checklist)

1. Subclasse de `CCXTAdapter` (id CCXT, `rate_per_sec`/`rate_burst`,
   `supports_funding`/`supports_open_interest`, `default_type`).
2. README do conector com rate limits e restrições regionais
   (GOV-002), verificados na documentação oficial da época.
3. Testes em `tests/connectors/test_<exchange>.py` com fakes do
   CCXT (reutilizar `tests/connectors/fake_ccxt.py`), sem rede real.
4. Smoke ao vivo separado (um ticker público por exchange),
   registrado em `docs/smoke-*.md`.
5. Linha na matriz de cobertura (`docs/exchanges.md` e
   `services/exchange-connectors/README.md`).

Nenhuma das 6 precisa de chave de API para market data público,
e nenhuma exige mudança no contrato universal (Fase 3) nem na
base `ccxt_adapter.py`.
