"""Smoke check ao vivo — Fase 4 (CEX-001…CEX-003).

Uma chamada pública real por exchange (ticker BTC/USDT) para provar
que os conectores Binance, Bybit e OKX funcionam de verdade — sem
nenhuma chave de API e sem envio de ordens.

NÃO é teste automatizado: não roda no pytest (o nome do arquivo não
começa com ``test_``) e precisa de rede + CCXT instalado. Rodar com
o venv do projeto:

    .venv/bin/python tests/connectors/smoke_public.py

O resultado é registrado em
``data/reports/fase4-smoke-YYYY-MM-DD.md``. Se a rede estiver
bloqueada, o script registra a falha honestamente e sai com código
de erro — nunca finge que o smoke rodou.

Rede do sandbox: o CCXT desativa ``trust_env`` e ignora as variáveis
de ambiente do proxy de egresso (``HTTPS_PROXY``) e do bundle de CA
(``SSL_CERT_FILE``). Por isso o script, quando essas variáveis
existem, passa ``httpsProxy`` ao CCXT e aponta
``validateServerSsl`` para o bundle de CA — sem isso, nem o OKX
(resposta 200 via curl) completa o TLS. Isso é configuração de rede
do ambiente de teste, não do conector (na VPS não há esse proxy).
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONNECTORS_DIR = _PROJECT_ROOT / "services" / "exchange-connectors"
_REPORTS_DIR = _PROJECT_ROOT / "data" / "reports"

sys.path.insert(0, str(_CONNECTORS_DIR))

from binance.adapter import BinanceAdapter  # noqa: E402
from bybit.adapter import BybitAdapter  # noqa: E402
from okx.adapter import OkxAdapter  # noqa: E402

ADAPTERS = (BinanceAdapter, BybitAdapter, OkxAdapter)


def _build_ccxt_exchange(adapter_cls):
    """Objeto CCXT real, com a rede do sandbox quando ela existe.

    Sem proxy/CA nas variáveis de ambiente, constrói o exchange
    padrão (caso da VPS). Nenhuma credencial é configurada.
    """
    import ccxt

    config: dict = {"enableRateLimit": True, "timeout": 15_000}
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        config["httpsProxy"] = proxy
    exchange = getattr(ccxt, adapter_cls.ccxt_id)(config)
    ca_bundle = os.environ.get("SSL_CERT_FILE")
    if ca_bundle:
        # CCXT usa verify = self.verify and self.validateServerSsl:
        # apontar validateServerSsl para o bundle faz o requests
        # verificar o TLS com a CA do proxy de egresso.
        exchange.validateServerSsl = ca_bundle
    return exchange


def main() -> int:
    try:
        import ccxt
    except ImportError:
        print("ERRO: pacote ccxt não instalado — "
              "rode `.venv/bin/pip install ccxt` primeiro.")
        return 2

    now = datetime.now(timezone.utc)
    lines: list[str] = [
        "# Smoke check ao vivo — Fase 4 (CEX-001…CEX-003)",
        "",
        f"- Data (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- CCXT: {ccxt.__version__}",
        "- Modo: somente endpoints públicos, sem nenhuma chave de API, "
        "sem envio de ordens.",
        "- Chamada por exchange: `connect()` (carrega mercados públicos) "
        "+ `fetch_ticker('BTC/USDT')`.",
        "",
        "| Exchange | Status | BTC/USDT (last) | Latência ticker (ms) | "
        "Detalhe |",
        "|---|---|---|---|---|",
    ]
    failures = 0
    for cls in ADAPTERS:
        adapter = cls(exchange=_build_ccxt_exchange(cls))
        started = time.monotonic()
        try:
            adapter.connect()
            ticker = adapter.fetch_ticker("BTC/USDT")
            latency = adapter.health()["latency_ms"].get("fetch_ticker")
            elapsed = (time.monotonic() - started) * 1000
            lines.append(
                f"| {adapter.name} | OK | {ticker.last} "
                f"| {latency} | connect+fetch em {elapsed:.0f} ms; "
                f"timestamp {ticker.timestamp_ms} |"
            )
            print(f"{adapter.name}: OK — BTC/USDT last={ticker.last} "
                  f"(ticker {latency} ms)")
        except Exception as exc:  # noqa: BLE001 - registrar e continuar
            failures += 1
            lines.append(
                f"| {adapter.name} | FALHOU | — | — | "
                f"{type(exc).__name__}: {exc} |"
            )
            print(f"{adapter.name}: FALHOU — {type(exc).__name__}: {exc}")
        finally:
            try:
                adapter.disconnect()
            except Exception:  # noqa: BLE001 - fechar não pode falhar
                pass
    lines += [
        "",
        "OK" if failures == 0 else f"{failures} exchange(s) falharam.",
        "",
    ]
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = _REPORTS_DIR / f"fase4-smoke-{now.strftime('%Y-%m-%d')}.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Relatório: {report}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
