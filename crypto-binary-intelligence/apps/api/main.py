"""
Crypto & Binary Intelligence — API (esqueleto / scaffold).

FastAPI mínima com:
  - GET  /health             — health check do serviço
  - GET  /v1/exchanges       — stub: catálogo de exchanges (Fase 4)
  - GET  /v1/system/health   — stub: saúde do sistema (§16)
  - demais rotas da especificação v4.1 (§13) como stubs HTTP 501
  - rotas de execução BLOQUEADAS com HTTP 403 (LIVE desabilitado)

NÃO há execução real de ordens neste scaffold. Nenhuma conexão com
exchange é feita. Nenhuma credencial é lida daqui além das variáveis
de ambiente de infraestrutura (DATABASE_URL / REDIS_URL / NATS_URL).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

VERSION = "0.1.0-scaffold"

# --- Trava de segurança (§10) ------------------------------------------------
# O scaffold só aceita RESEARCH. Qualquer outro valor no ambiente é
# ignorado e registrado: o sistema nunca muda sozinho para LIVE.
_RAW_MODE = os.getenv("EXECUTION_MODE", "RESEARCH").strip().upper()
EXECUTION_MODE = "RESEARCH"
if _RAW_MODE != "RESEARCH":
    print(
        f"[SECURITY] EXECUTION_MODE='{_RAW_MODE}' ignorado pelo scaffold: "
        "modo forçado para RESEARCH. LIVE exige homologação (EXE-014)."
    )

LIVE_ENABLED = False

app = FastAPI(
    title="Crypto & Binary Intelligence API",
    description=(
        "Esqueleto / scaffold do MVP (especificação v4.1). "
        "Rotas de leitura são stubs; rotas de execução estão bloqueadas "
        "(LIVE desabilitado por padrão)."
    ),
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


# --- Modelos de stub -----------------------------------------------------------
# Catálogo do primeiro grupo de CEX (§3). `status: scaffold` significa que o
# conector ainda não existe; nada aqui implica conexão ativa com a exchange.
EXCHANGES_CATALOG = [
    {"id": "binance", "name": "Binance", "group": "priority", "status": "scaffold"},
    {"id": "bybit", "name": "Bybit", "group": "priority", "status": "scaffold"},
    {"id": "okx", "name": "OKX", "group": "priority", "status": "scaffold"},
    {"id": "coinbase", "name": "Coinbase Advanced", "group": "priority", "status": "scaffold"},
    {"id": "kraken", "name": "Kraken", "group": "priority", "status": "scaffold"},
    {"id": "bitget", "name": "Bitget", "group": "priority", "status": "scaffold"},
    {"id": "gateio", "name": "Gate.io", "group": "priority", "status": "scaffold"},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stub(route: str) -> JSONResponse:
    """Resposta padrão de rota ainda não implementada (Fase correspondente)."""
    return JSONResponse(
        status_code=501,
        content={
            "detail": f"Rota {route} ainda não implementada neste scaffold.",
            "status": "not_implemented",
            "version": VERSION,
        },
    )


# --- Health --------------------------------------------------------------------
@app.get("/health", tags=["system"])
def health() -> dict[str, Any]:
    """Health check do serviço (usado pelo healthcheck do Docker Compose)."""
    return {
        "status": "ok",
        "service": "crypto-binary-intelligence",
        "version": VERSION,
        "execution_mode": EXECUTION_MODE,
        "live_enabled": LIVE_ENABLED,
        "timestamp": _now_iso(),
    }


@app.get("/", tags=["system"])
def root() -> dict[str, Any]:
    return {
        "service": "Crypto & Binary Intelligence API",
        "version": VERSION,
        "mode": "scaffold",
        "execution_mode": EXECUTION_MODE,
        "live_enabled": LIVE_ENABLED,
        "docs": "/docs",
    }


# --- Exchanges (§13) -----------------------------------------------------------
@app.get("/v1/exchanges", tags=["exchanges"])
def list_exchanges() -> dict[str, Any]:
    """Stub: catálogo de exchanges do primeiro grupo (§3)."""
    return {"exchanges": EXCHANGES_CATALOG, "count": len(EXCHANGES_CATALOG)}


@app.get("/v1/exchanges/status", tags=["exchanges"])
def exchanges_status() -> dict[str, Any]:
    """Stub: status de conexão por exchange (Fase 4 — CEX-006)."""
    return {
        "exchanges": [
            {"id": e["id"], "connected": False, "last_message_age_ms": None}
            for e in EXCHANGES_CATALOG
        ],
        "note": "Conectores ainda não implementados (scaffold).",
    }


# --- Mercado / inteligência (stubs — Fases 7–13) -------------------------------
@app.get("/v1/instruments", tags=["market"])
def list_instruments() -> JSONResponse:
    return _stub("GET /v1/instruments")


@app.get("/v1/markets", tags=["market"])
def list_markets() -> JSONResponse:
    return _stub("GET /v1/markets")


@app.get("/v1/market/{symbol}/trades", tags=["market"])
def market_trades(symbol: str) -> JSONResponse:
    return _stub(f"GET /v1/market/{symbol}/trades")


@app.get("/v1/market/{symbol}/candles", tags=["market"])
def market_candles(symbol: str) -> JSONResponse:
    return _stub(f"GET /v1/market/{symbol}/candles")


@app.get("/v1/market/{symbol}/orderbook", tags=["market"])
def market_orderbook(symbol: str) -> JSONResponse:
    return _stub(f"GET /v1/market/{symbol}/orderbook")


@app.get("/v1/indicators/{symbol}", tags=["intelligence"])
def indicators(symbol: str) -> JSONResponse:
    return _stub(f"GET /v1/indicators/{symbol}")


@app.get("/v1/patterns/{symbol}", tags=["intelligence"])
def patterns(symbol: str) -> JSONResponse:
    return _stub(f"GET /v1/patterns/{symbol}")


@app.get("/v1/opportunities", tags=["intelligence"])
def opportunities() -> JSONResponse:
    return _stub("GET /v1/opportunities")


@app.get("/v1/strategies", tags=["strategies"])
def list_strategies() -> JSONResponse:
    return _stub("GET /v1/strategies")


@app.post("/v1/strategies", tags=["strategies"])
def create_strategy() -> JSONResponse:
    return _stub("POST /v1/strategies")


@app.patch("/v1/strategies/{strategy_id}", tags=["strategies"])
def update_strategy(strategy_id: str) -> JSONResponse:
    return _stub(f"PATCH /v1/strategies/{strategy_id}")


@app.get("/v1/signals", tags=["signals"])
def list_signals() -> JSONResponse:
    return _stub("GET /v1/signals")


@app.get("/v1/signals/{signal_id}", tags=["signals"])
def get_signal(signal_id: str) -> JSONResponse:
    return _stub(f"GET /v1/signals/{signal_id}")


@app.get("/v1/portfolio", tags=["execution"])
def portfolio() -> JSONResponse:
    return _stub("GET /v1/portfolio")


@app.post("/v1/webhooks/tradingview", tags=["webhooks"])
def tradingview_webhook() -> JSONResponse:
    # Fonte complementar (§9). Validação e enfileiramento entram na Fase 14.
    return _stub("POST /v1/webhooks/tradingview")


# --- Execução — BLOQUEADA (§10) ------------------------------------------------
def _execution_blocked() -> None:
    raise HTTPException(
        status_code=403,
        detail=(
            "Execução bloqueada: LIVE desabilitado por padrão. "
            "Modo atual: RESEARCH. A execução real exige homologação "
            "(Fase 15, EXE-014) e autorização expressa do responsável."
        ),
    )


@app.post("/v1/execution/preview", tags=["execution"])
def execution_preview() -> None:
    _execution_blocked()


@app.post("/v1/execution/orders", tags=["execution"])
def execution_orders() -> None:
    _execution_blocked()


@app.post("/v1/execution/cancel", tags=["execution"])
def execution_cancel() -> None:
    _execution_blocked()


@app.get("/v1/execution/positions", tags=["execution"])
def execution_positions() -> JSONResponse:
    return _stub("GET /v1/execution/positions")


@app.post("/v1/execution/kill-switch", tags=["execution"])
def kill_switch() -> JSONResponse:
    # Kill switch existe como controle desde o scaffold, mas sem nenhuma
    # ordem real para cancelar: retorna o estado atual (desarmado/inativo).
    return {
        "kill_switch": "armed",
        "live_enabled": LIVE_ENABLED,
        "open_positions": 0,
        "note": "Scaffold: nenhuma posição real existe; nada a cancelar.",
    }


# --- Sistema (§13, §16) ---------------------------------------------------------
@app.get("/v1/system/health", tags=["system"])
def system_health() -> dict[str, Any]:
    """Stub: saúde agregada do sistema (Fase 2 — métricas de infra)."""
    return {
        "status": "scaffold",
        "version": VERSION,
        "execution_mode": EXECUTION_MODE,
        "live_enabled": LIVE_ENABLED,
        "components": {
            "postgres_timescale": "not_checked",
            "redis": "not_checked",
            "nats": "not_checked",
            "connectors": "not_implemented",
        },
        "timestamp": _now_iso(),
    }


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("API_PORT", "8000")))
