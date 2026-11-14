"""Smoke check ao vivo — Fase 7 (Market Data Engine, DAT-001…DAT-004).

Uma conexão WebSocket pública curta (trades BTC/USDT da Binance,
~8 s), ligada ao TradePipeline + CandleBuilder (1s e 1m), para provar
que o pipeline funciona com dados reais — sem nenhuma chave de API
e sem envio de ordens.

Fallback: se a rede bloquear o WebSocket, tenta REST público
(``BinanceAdapter.fetch_trades``) e registra o fallback. Se ambos
falharem, registra a falha honestamente e sai com código de erro —
nunca finge que o smoke rodou.

Uso (com o venv do projeto, que tem ``websockets``)::

    .venv/bin/python scripts/smoke_phase7.py

O resultado é registrado em
``data/reports/fase7-smoke-YYYY-MM-DD.md``.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CONNECTORS_DIR = _PROJECT_ROOT / "services" / "exchange-connectors"
_MARKET_DATA_DIR = _PROJECT_ROOT / "services" / "market-data"
_CANDLE_BUILDER_DIR = _PROJECT_ROOT / "services" / "candle-builder"
_REPORTS_DIR = _PROJECT_ROOT / "data" / "reports"

sys.path.insert(0, str(_CONNECTORS_DIR))
sys.path.append(str(_MARKET_DATA_DIR))
sys.path.append(str(_CANDLE_BUILDER_DIR))

from candle_builder import CandleBuilder  # noqa: E402
from market_data import LiveTradeFeed, TradePipeline  # noqa: E402

SYMBOL = "BTC/USDT"
DURATION_S = 8.0


async def _run_ws() -> dict:
    pipeline = TradePipeline("binance")
    builder = CandleBuilder("binance", SYMBOL, ["1s", "1m"])
    closed: list = []
    pipeline.subscribe(lambda t: closed.extend(builder.add_trade(t)))
    feed = LiveTradeFeed(
        "binance", SYMBOL, pipeline, duration_s=DURATION_S
    )
    stats = await feed.run()
    stats["candles_closed"] = len(closed)
    stats["candles_1s"] = sum(1 for c in closed if c.timeframe == "1s")
    stats["candles_1m"] = sum(1 for c in closed if c.timeframe == "1m")
    stats["open_candles"] = len(builder.open_candles())
    stats["builder_metrics"] = builder.metrics.as_dict()
    if closed:
        first = closed[0]
        stats["first_candle"] = (
            f"{first.timeframe} open={first.open} high={first.high} "
            f"low={first.low} close={first.close} vol={first.volume} "
            f"trades={first.trades}"
        )
    return stats


def _run_rest_fallback() -> dict:
    """Trades recentes via REST público (sem chave).

    Tenta Binance primeiro; se a rede bloquear (ex.: HTTP 451 por
    restrição geográfica do egresso, como na Fase 4), tenta OKX.
    """
    import ccxt

    last_error: Exception | None = None
    for adapter_cls, ccxt_id in (
        ("binance", "binance"),
        ("okx", "okx"),
    ):
        try:
            return _run_rest_one(adapter_cls, ccxt_id, ccxt)
        except Exception as exc:  # noqa: BLE001 - tentar a próxima
            last_error = exc
            print(f"REST {adapter_cls} FALHOU — {type(exc).__name__}: {exc}")
    raise RuntimeError(f"REST fallback falhou em todas: {last_error}")


def _run_rest_one(adapter_name: str, ccxt_id: str, ccxt) -> dict:
    if adapter_name == "binance":
        from binance.adapter import BinanceAdapter as Adapter
    else:
        from okx.adapter import OkxAdapter as Adapter

    config: dict = {"enableRateLimit": True, "timeout": 15_000}
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        config["httpsProxy"] = proxy
    exchange = getattr(ccxt, ccxt_id)(config)
    ca_bundle = os.environ.get("SSL_CERT_FILE")
    if ca_bundle:
        exchange.validateServerSsl = ca_bundle
    adapter = Adapter(exchange=exchange)
    try:
        adapter.connect()
        trades = adapter.fetch_trades(SYMBOL, limit=10)
        # Os trades já vêm normalizados pelo adapter (REST público);
        # vão direto ao builder — não passam pelo parser de WS nativo.
        builder = CandleBuilder(adapter.exchange_id, SYMBOL, ["1s", "1m"])
        closed: list = []
        for trade in trades:
            closed.extend(builder.add_trade(trade))
        return {
            "mode": "REST-fallback",
            "exchange": adapter.exchange_id,
            "trades_fetched": len(trades),
            "trades_accepted": builder.metrics.trades_accepted,
            "out_of_order_rejected": builder.metrics.out_of_order_rejected,
            "candles_closed": len(closed),
            "first_trade_price": str(trades[0].price) if trades else None,
        }
    finally:
        adapter.disconnect()


def main() -> int:
    now = datetime.now(timezone.utc)
    lines: list[str] = [
        "# Smoke check ao vivo — Fase 7 (Market Data Engine)",
        "",
        f"- Data (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}",
        "- Modo: somente endpoints públicos, sem nenhuma chave de API, "
        "sem envio de ordens.",
        f"- Alvo: trades BTC/USDT da Binance por {DURATION_S:.0f} s "
        "(WebSocket), com fallback REST.",
        "",
    ]
    try:
        stats = asyncio.run(_run_ws())
        if stats["trades_accepted"] == 0:
            # Conectou mas não entregou nenhum trade em 8 s num par
            # hiperlíquido: não é sucesso — cair no fallback.
            raise RuntimeError(
                "WebSocket conectou mas entregou 0 trades em "
                f"{DURATION_S:.0f} s"
            )
        print(
            f"WS OK — {stats['messages_received']} mensagens, "
            f"{stats['trades_accepted']} trades aceitos, "
            f"{stats['candles_closed']} candles fechados "
            f"({stats['candles_1s']} de 1s, {stats['candles_1m']} de 1m)"
        )
        lines += [
            "## WebSocket (Binance `wss://stream.binance.com:9443/ws/btcusdt@trade`)",
            "",
            f"- Mensagens recebidas: {stats['messages_received']}",
            f"- Trades aceitos: {stats['trades_accepted']}",
            f"- Duplicatas descartadas: {stats['duplicates_dropped']}",
            f"- Erros de parse: {stats['parse_errors']}",
            f"- Reconexões: {stats['reconnects']}",
            f"- Candles fechados: {stats['candles_closed']} "
            f"({stats['candles_1s']} de 1s, {stats['candles_1m']} de 1m)",
            f"- Candles abertos (parciais): {stats['open_candles']}",
            f"- Métricas do builder: {stats['builder_metrics']}",
        ]
        if "first_candle" in stats:
            lines.append(f"- Primeiro candle fechado: {stats['first_candle']}")
        lines += ["", "OK — pipeline ao vivo funcionou.", ""]
        failures = 0
    except Exception as exc:  # noqa: BLE001 - registrar e tentar fallback
        print(f"WS FALHOU — {type(exc).__name__}: {exc}")
        lines += [
            "## WebSocket (Binance)",
            "",
            f"- FALHOU: {type(exc).__name__}: {exc}",
            "",
            "## Fallback REST",
            "",
        ]
        try:
            stats = _run_rest_fallback()
            print(
                f"REST OK — {stats['trades_fetched']} trades, "
                f"{stats['candles_closed']} candles fechados"
            )
            lines += [
                f"- Exchange do fallback: {stats['exchange']}",
                f"- Trades buscados: {stats['trades_fetched']}",
                f"- Trades aceitos no builder: {stats['trades_accepted']}",
                f"- Fora de ordem rejeitados: {stats['out_of_order_rejected']}",
                f"- Candles fechados: {stats['candles_closed']}",
                f"- Primeiro trade: {stats['first_trade_price']}",
                "",
                "PARCIAL — WebSocket falhou, REST funcionou (fallback).",
                "",
            ]
            failures = 0
        except Exception as exc2:  # noqa: BLE001 - registrar honestamente
            print(f"REST FALHOU — {type(exc2).__name__}: {exc2}")
            lines += [
                f"- FALHOU: {type(exc2).__name__}: {exc2}",
                "",
                "FALHOU — nem WebSocket nem REST responderam.",
                "",
            ]
            failures = 1
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = _REPORTS_DIR / f"fase7-smoke-{now.strftime('%Y-%m-%d')}.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Relatório: {report}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
