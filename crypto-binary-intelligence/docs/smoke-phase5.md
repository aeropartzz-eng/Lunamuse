# Smoke check ao vivo — Fase 5 (CEX-007…CEX-010)

> Data: **2026-11-13, ~06:26–06:28 -03** (09:26–09:28 UTC).
> Script: `/tmp/smoke_phase5.py` (fora da suíte de testes).
> Método: uma chamada pública real por exchange —
> `connect()` (carrega mercados) + `fetch_ticker("BTC/USDT")` —
> sem nenhuma chave de API. Rodado com o Python do venv do projeto
> (`.venv/bin/python`, CCXT 4.5.92).

## Resultado: 4/4 OK

| Exchange | Símbolo | Last (USD) | Bid | Ask | Timestamp (ms UTC) | Latência total* |
|---|---|---|---|---|---|---|
| Coinbase Advanced | BTC/USDT | 69050.89 | 69016.1 | 69075.14 | 1794562373882 | 1.500 ms |
| Kraken | BTC/USDT | 69037.1 | 69047.4 | 69051.0 | 1794562393919 | 2.211 ms |
| Bitget | BTC/USDT | 69023.51 | 69022.8 | 69022.81 | 1794562397389 | 3.826 ms |
| Gate.io | BTC/USDT | 69025.7 | 69025.5 | 69025.6 | 1794562411684 | 13.936 ms |

\* Latência total = `connect()` (load_markets) + `fetch_ticker`.
A latência só do `fetch_ticker` (em `health()["latency_ms"]`)
ficou entre ~500 e ~600 ms nas 4. Os preços são consistentes
entre as exchanges (~69.023–69.051), o que valida o ticker.

## Nota de ambiente (VM de desenvolvimento)

A primeira tentativa falhou nas 4 exchanges com
`CONNECTION_LOST`. Causa raiz, diagnosticada na hora:

1. O CCXT desliga `trust_env` por padrão, então ignorava o
   proxy de egresso da VM (`HTTPS_PROXY`) e o CA bundle do
   ambiente (`REQUESTS_CA_BUNDLE`) — sem proxy, a conexão direta
   falhava com `SSL: WRONG_VERSION_NUMBER`; com proxy explícito,
   a verificação TLS falhava (`self-signed certificate`, CA de
   interceptação do egresso fora do bundle do `certifi`).
2. Solução **só no script de smoke** (não no código do projeto):
   injetar o exchange CCXT construído com
   `{'requests_trust_env': True}` — o CCXT passa então a honrar
   `HTTPS_PROXY` e `REQUESTS_CA_BUNDLE` do ambiente. Nenhum
   segredo foi lido ou registrado: proxy e CA continuam nas
   variáveis de ambiente da VM.

Na VPS de produção (Fase 1, sem esse proxy), o caminho normal —
`Adapter()` + `connect()` — deve funcionar sem esse ajuste.
