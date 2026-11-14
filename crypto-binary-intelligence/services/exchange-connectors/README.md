# services/exchange-connectors — Conectores CEX

Camada 2 — Ingestão (especificação v4.1, Fases 3–5).

## Contrato universal (Fase 3 — CON-001…CON-007) ✅

O contrato universal está implementado neste diretório, como módulos
planos em Python (o diretório tem hífen e não é um pacote importável;
os módulos são carregados com este diretório no `sys.path` — ver
`tests/conftest.py`. A conversão para pacote instalável é trabalho de
empacotamento futuro, não desta fase).

| Módulo | Tarefa | Conteúdo |
|---|---|---|
| `base.py` | CON-001 | `ExchangeAdapter` (ABC) — interface universal |
| `models.py` | CON-002 | Dataclasses validadas: `Exchange`, `Market`, `Instrument`, `Trade`, `Candle`, `OrderBook`, `Ticker`, `FundingRate`, `OpenInterest`, `Order`, `Fill`, `Position` |
| `normalization.py` | CON-003 | Símbolos (`BTC/USDT`), timestamps (ms UTC), lados, tipos de ordem, alias por exchange, timeframes reais |
| `errors.py` + `envelope.py` | CON-004 | `ExchangeError` com códigos (`RATE_LIMIT`, `TIMEOUT`, `INVALID_SYMBOL`, `CONNECTION_LOST`, `BAD_RESPONSE`) + envelope `ok/error/code/message/retryable` |
| `connection.py` | CON-005/006 | `ConnectionManager`: heartbeat, reconexão exponencial com jitter, recuperação de assinaturas, token bucket, dedup, sequenciamento/gaps, métricas de latência |

### `ExchangeAdapter` — interface

Somente **leitura pública de mercado**. Nenhum método usa
autenticação ou chave de API; nenhum envia ordens.

```python
class ExchangeAdapter(ABC):
    exchange_id: str  # ex.: "binance"
    name: str         # ex.: "Binance"

    # Ciclo de vida
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def health(self) -> dict[str, Any]: ...  # idade da última msg, sequência, atraso

    # Leitura pública (retornam os modelos de models.py)
    def fetch_markets(self) -> list[Market]: ...
    def fetch_ticker(self, symbol: str) -> Ticker: ...
    def fetch_trades(self, symbol: str, limit: int = 100) -> list[Trade]: ...
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> list[Candle]: ...
    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBook: ...
    def fetch_funding_rate(self, symbol: str) -> FundingRate: ...
    def fetch_open_interest(self, symbol: str) -> OpenInterest: ...
```

Os nomes antigos do scaffold (`list_markets`, `get_ticker`,
`get_trades`, `get_candles`, `get_orderbook`, `subscribe`) continuam
existindo como wrappers concretos que delegam aos métodos canônicos.

### Como implementar um novo conector (Fases 4–5)

1. Criar `<exchange>/adapter.py` com uma classe herdando de
   `ExchangeAdapter` (ver `binance/adapter.py` como modelo).
2. Implementar os 7 métodos `fetch_*` + `connect`/`disconnect`/
   `health`, traduzindo o formato nativo da exchange para os modelos
   de `models.py`.
3. Normalizar tudo com `normalization` (`normalize_symbol`,
   `normalize_timestamp`, `normalize_side`); símbolo canônico é
   `BASE/QUOTE` (`BTC/USDT`); perpétuo é `BTC/USDT:USDT`.
4. Preservar o payload original em `raw` (CEX-005).
5. Erros sempre como `ExchangeError` com o código adequado; nunca
   vazar credencial em mensagem ou log.
6. Usar `ConnectionManager` para o WebSocket: injetar os callbacks de
   transporte (`on_connect`/`on_disconnect`/`on_subscribe`) e deixar
   heartbeat, reconexão, dedup e gaps com ele.
7. **Não inventar granularidade**: só timeframes que a fonte fornece
   (`validate_timeframe` rejeita o resto); se a fonte não dá trades
   individuais, não simular ticks.
8. Testes em `tests/connectors/` com fakes — nunca rede real nos
   testes (CON-007).

### `ConnectionManager` — resumo

- **Heartbeat/staleness**: `is_stale()` quando a idade da última
  mensagem passa de `heartbeat_interval_ms × max_missed_heartbeats`
  (padrão 30 s × 3). `health()` expõe estado, idade da última
  mensagem, gaps, duplicatas e reconexões.
- **Reconexão**: backoff `base × factor^attempt` (padrão 1 s, ×2,
  teto 60 s) com jitter uniforme de ±25%; assinaturas guardadas são
  restauradas a cada reconexão.
- **Rate limiting**: token bucket por exchange
  (`rate_per_sec`/`rate_burst`); `acquire_or_raise()` levanta
  `RATE_LIMIT` (retryable).
- **Dedup**: `MessageDeduplicator` por chave, tamanho limitado (FIFO).
- **Sequência**: `SequenceTracker` por canal — `OK`/`DUPLICATE`/`GAP`
  com contagem de mensagens faltantes.
- **Latência**: `last_message_age_ms()` e contadores em `health()`.

Relógio, sleep e RNG são injetáveis (`time_fn_ms`, `sleep_fn`, `rng`)
para testes determinísticos.

## Primeiro grupo (§3)

| Exchange | Tarefa | Fase | Status |
|---|---|---|---|
| Binance | CEX-001 — mercados, trades, ticker, candles e book | 4 | ✅ implementado (`binance/adapter.py`) |
| Bybit | CEX-002 — Spot e contratos suportados | 4 | ✅ implementado (`bybit/adapter.py`) |
| OKX | CEX-003 — instrumentos, trades e books | 4 | ✅ implementado (`okx/adapter.py`) |
| Coinbase Advanced | CEX-007 | 5 | ✅ implementado (`coinbase/adapter.py`) |
| Kraken | CEX-008 | 5 | ✅ implementado (`kraken/adapter.py`) |
| Bitget | CEX-009 | 5 | ✅ implementado (`bitget/adapter.py`) |
| Gate.io | CEX-010 | 5 | ✅ implementado (`gateio/adapter.py`) |

Expansão (CEX-011): KuCoin, MEXC, BingX, Bitfinex, HTX, Crypto.com.

### Fase 4 — o que foi entregue (CEX-001…CEX-006)

Os três conectores herdam de `ccxt_adapter.CCXTAdapter` (base
compartilhada com a Fase 5) e usam o CCXT **somente em modo público,
sem nenhuma credencial** (`public_config()` não contém `apiKey` /
`secret` / `password` — verificado em teste). Nenhum envia ordens.

- **CEX-001/002/003**: mercados, ticker, trades, candles, book,
  funding rate e open interest (contratos) nas 3 exchanges.
- **CEX-004**: símbolos (`BASE/QUOTE`, perpétuo `BASE/QUOTE:USDT`)
  e timestamps (ms UTC) normalizados com `normalization.py`.
- **CEX-005**: payload original preservado em `raw` de cada modelo.
- **CEX-006**: latência por método e gaps de candles expostos em
  `health()`; sequência do book (`nonce`) acompanhada quando a
  exchange fornece.
- **CEX-012 / GOV-002**: token bucket local por exchange
  (Binance 10 req/s, Bybit 10 req/s, OKX 5 req/s) e limites +
  restrições regionais documentados no README de cada conector.
- **Paginação**: `fetch_trades` / `fetch_ohlcv` aceitam `since_ms`
  e paginam acima de 1000 itens, com dedup entre páginas.
- **Testes**: `tests/connectors/test_binance.py`,
  `test_bybit.py`, `test_okx.py` (+ `paged_fake.py`) — fakes do
  CCXT, sem rede real. Smoke ao vivo separado:
  `tests/connectors/smoke_public.py` (relatório em
  `data/reports/fase4-smoke-*.md`).
- **Pendente**: WebSocket de trades/book em tempo real (Fase 7,
  Market Data Engine); chaves de API — só o Will pode criá-las,
  e só serão usadas a partir da Fase 15 (testnet).

### Fase 5 — o que foi entregue (CEX-007…CEX-012)

Os quatro conectores herdam de `ccxt_adapter.CCXTAdapter` (a mesma
base da Fase 4) e usam o CCXT **somente em modo público, sem nenhuma
credencial** (`public_config()` não contém `apiKey` / `secret` /
`password` — verificado em teste). Nenhum envia ordens.

- **CEX-007 Coinbase Advanced** (`coinbase/adapter.py`, CCXT id
  `coinbase`): spot; sem funding/OI via API pública.
- **CEX-008 Kraken** (`kraken/adapter.py`, CCXT id `kraken`):
  spot, com alias `XBT`→`BTC` e `XDG`→`DOGE` (tabela em
  `normalization.py`); sem funding/OI no Spot via CCXT.
- **CEX-009 Bitget** (`bitget/adapter.py`, CCXT id `bitget`):
  spot + perpétuos USDT, com funding rate e open interest
  (símbolo swap `BTC/USDT:USDT`).
- **CEX-010 Gate.io** (`gateio/adapter.py`, CCXT id `gate`):
  spot + perpétuos USDT, com funding rate; open interest
  indisponível no CCXT (`has.fetchOpenInterest = False`).
- **CEX-005/CEX-006**: payload original em `raw`; latência por
  método e gaps de candles em `health()`.
- **CEX-011**: avaliação das 6 exchanges de expansão (KuCoin,
  MEXC, BingX, Bitfinex, HTX, Crypto.com) em
  `docs/exchanges-expansion.md` — todas viáveis via CCXT, sem
  implementar os conectores.
- **CEX-012 / GOV-002**: token bucket local por exchange
  (Coinbase 10 req/s, Kraken 1 req/s, Bitget 20 req/s, Gate.io
  20 req/s) e limites + restrições regionais documentados no
  README de cada conector.
- **Testes**: `tests/connectors/test_coinbase.py`,
  `test_kraken.py`, `test_bitget.py`, `test_gateio.py` (+
  `fake_ccxt.py` compartilhado) — fakes do CCXT, sem rede real.
  Funding/OI ausente levanta `ExchangeError` (BAD_RESPONSE) em
  vez de inventar dado.
- **Smoke ao vivo**: `docs/smoke-phase5.md` — ticker BTC/USDT
  nas 4 exchanges em 2026-11-13, 4/4 OK.
- **Pendente**: WebSocket em tempo real (Fase 7); OI do Gate.io
  via endpoint nativo (fora do CCXT); funding/OI do Kraken
  Futures (fora do conector spot).

## Regras

- **Conectores das Fases 4–5 implementados** (Binance, Bybit, OKX,
  Coinbase, Kraken, Bitget, Gate.io) sobre `ccxt_adapter.py`,
  somente com endpoints públicos e sem credenciais. Nenhum deles
  levanta mais `NotImplementedError`; o que ainda falta é o
  WebSocket em tempo real (Fase 7).
- Somente endpoints públicos de mercado. Chaves de API **sem saque**,
  com restrição de IP quando disponível — e só a partir da Fase 15
  (testnet), criadas pelo Will; os conectores das Fases 4–5 não
  usam nenhuma chave.
- Respeitar rate limits de cada exchange (CEX-012).
- Uma conexão aberta não significa conexão saudável: medir idade da
  última mensagem, sequência, atraso e integridade (§5).
- Presença no catálogo não garante disponibilidade regional de todos os
  produtos — cada conector verifica documentação, permissões,
  elegibilidade e condições de uso.
- Execução real continua bloqueada: a API força `RESEARCH` mesmo com
  `EXECUTION_MODE=LIVE` e rejeita ordens com HTTP 403.

## Testes

```bash
python3 -m pytest tests/ -q
```

`tests/connectors/test_adapter.py` (interface, modelos, normalização,
erros/envelope) e `tests/connectors/test_connection_manager.py`
(desconexão/reconexão, duplicidade, rate limit, gaps, heartbeat) —
todos com mocks/fakes, sem rede real. Os conectores das Fases 4–5
têm um arquivo de testes por exchange (`test_binance.py`,
`test_bybit.py`, `test_okx.py`, `test_coinbase.py`, `test_kraken.py`,
`test_bitget.py`, `test_gateio.py`) com fakes do CCXT
(`fake_ccxt.py`, `paged_fake.py`).
