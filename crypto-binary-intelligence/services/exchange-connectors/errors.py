"""Erros padronizados do contrato universal (Fase 3 — CON-004).

Toda falha de um conector de exchange é expressa como :class:`ExchangeError`
com um código estável (:class:`ErrorCode`). Códigos que indicam falha
transitória são ``retryable=True`` e podem ser tentados novamente pelo
:class:`~connection.ConnectionManager`; os demais não devem ser repetidos
sem mudar a requisição.

Nenhuma chamada de rede é feita aqui. Nenhuma credencial é usada.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class ErrorCode(str, Enum):
    """Códigos de erro estáveis do contrato universal (CON-004)."""

    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    CONNECTION_LOST = "CONNECTION_LOST"
    BAD_RESPONSE = "BAD_RESPONSE"
    UNKNOWN = "UNKNOWN"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


# Códigos que indicam falha transitória: repetir pode resolver.
RETRYABLE_CODES = frozenset(
    {ErrorCode.RATE_LIMIT, ErrorCode.TIMEOUT, ErrorCode.CONNECTION_LOST}
)


class ExchangeError(Exception):
    """Erro padronizado de qualquer conector de exchange.

    Attributes:
        code: Código estável (:class:`ErrorCode`).
        message: Mensagem legível, sem credenciais ou dados sensíveis.
        retryable: ``True`` quando uma nova tentativa pode resolver.
        exchange: Identificador da exchange (ex.: ``"binance"``).
        symbol: Símbolo normalizado envolvido, quando aplicável.
        raw: Payload original da fonte, preservado quando relevante
            (CEX-005). Nunca incluir credenciais aqui.
    """

    def __init__(
        self,
        code: ErrorCode | str,
        message: str,
        *,
        retryable: Optional[bool] = None,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
        raw: Any = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        self.code = ErrorCode(code) if isinstance(code, str) else code
        self.message = message
        self.retryable = (
            self.code in RETRYABLE_CODES if retryable is None else retryable
        )
        self.exchange = exchange
        self.symbol = symbol
        self.raw = raw
        super().__init__(f"[{self.code.value}] {message}")
        if cause is not None:
            self.__cause__ = cause

    def to_dict(self) -> dict[str, Any]:
        """Representação serializável do erro (para o envelope)."""
        return {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
            "exchange": self.exchange,
            "symbol": self.symbol,
        }


def error_from_http_status(
    status: int,
    message: str,
    *,
    exchange: Optional[str] = None,
    symbol: Optional[str] = None,
    raw: Any = None,
) -> ExchangeError:
    """Mapeia um status HTTP público para o :class:`ErrorCode` adequado.

    429 é rate limit; 408/504 é timeout; 400/404 em símbolo é símbolo
    inválido; 5xx é resposta ruim/conexão perdida conforme o caso
    (aqui: BAD_RESPONSE). Qualquer outro status vira UNKNOWN.
    """
    if status == 429:
        code = ErrorCode.RATE_LIMIT
    elif status in (408, 504):
        code = ErrorCode.TIMEOUT
    elif status in (400, 404):
        code = ErrorCode.INVALID_SYMBOL
    elif 500 <= status <= 599:
        code = ErrorCode.BAD_RESPONSE
    else:
        code = ErrorCode.UNKNOWN
    return ExchangeError(
        code, message, exchange=exchange, symbol=symbol, raw=raw
    )
