"""Envelope padronizado de respostas (Fase 3 — CON-004).

Toda resposta de um conector (REST ou WebSocket, sucesso ou erro) usa
o mesmo envelope::

    {"ok": True, "data": {...}, "error": None, "meta": {...}}
    {"ok": False, "data": None,
     "error": {"code": "RATE_LIMIT", "message": "...", "retryable": True},
     "meta": {...}}

``meta.raw`` preserva o payload original da fonte quando relevante
(CEX-005). ``meta`` carrega ainda a exchange, o instante de recebimento
(ms UTC) e a latência observada, quando conhecida.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from errors import ExchangeError, ErrorCode


@dataclass
class ResponseEnvelope:
    """Envelope único de resposta de um conector."""

    ok: bool
    data: Any = None
    error: Optional[dict[str, Any]] = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Representação serializável do envelope."""
        return {"ok": self.ok, "data": self.data, "error": self.error,
                "meta": self.meta}


def _meta(
    *,
    exchange: Optional[str] = None,
    received_at_ms: Optional[int] = None,
    latency_ms: Optional[float] = None,
    raw: Any = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "received_at_ms": (
            received_at_ms if received_at_ms is not None
            else int(time.time() * 1000)
        )
    }
    if exchange is not None:
        meta["exchange"] = exchange
    if latency_ms is not None:
        meta["latency_ms"] = latency_ms
    if raw is not None:
        meta["raw"] = raw  # payload original preservado (CEX-005)
    return meta


def ok_response(
    data: Any,
    *,
    exchange: Optional[str] = None,
    received_at_ms: Optional[int] = None,
    latency_ms: Optional[float] = None,
    raw: Any = None,
) -> ResponseEnvelope:
    """Envelope de sucesso."""
    return ResponseEnvelope(
        ok=True,
        data=data,
        error=None,
        meta=_meta(
            exchange=exchange,
            received_at_ms=received_at_ms,
            latency_ms=latency_ms,
            raw=raw,
        ),
    )


def error_response(
    error: ExchangeError | str,
    *,
    code: ErrorCode | str = ErrorCode.UNKNOWN,
    exchange: Optional[str] = None,
    received_at_ms: Optional[int] = None,
    raw: Any = None,
) -> ResponseEnvelope:
    """Envelope de erro, a partir de um ExchangeError ou de texto."""
    if isinstance(error, ExchangeError):
        payload = error.to_dict()
        if raw is None:
            raw = error.raw
        exchange = exchange or error.exchange
    else:
        payload = ExchangeError(code, str(error)).to_dict()
    return ResponseEnvelope(
        ok=False,
        data=None,
        error=payload,
        meta=_meta(exchange=exchange, received_at_ms=received_at_ms, raw=raw),
    )


def envelope_from_exception(
    exc: BaseException,
    *,
    exchange: Optional[str] = None,
    raw: Any = None,
) -> ResponseEnvelope:
    """Converte qualquer exceção em envelope de erro.

    ExchangeError vira seu próprio código; qualquer outra exceção vira
    UNKNOWN (nunca vaza traceback nem credencial na mensagem).
    """
    if isinstance(exc, ExchangeError):
        return error_response(exc, exchange=exchange, raw=raw)
    return error_response(
        ExchangeError(ErrorCode.UNKNOWN, f"{type(exc).__name__}: {exc}"),
        exchange=exchange,
        raw=raw,
    )
