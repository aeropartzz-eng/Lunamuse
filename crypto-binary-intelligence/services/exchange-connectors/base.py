"""Contrato universal de exchanges (Fase 3 — CON-001).

Interface que todo conector CEX deve implementar. Somente leitura
pública de mercado — nenhum método aqui usa autenticação, chave de
API ou envia ordens. A execução real continua bloqueada (403) e o
scaffold força RESEARCH quando EXECUTION_MODE=LIVE.

Métodos canônicos (CON-001): ``fetch_markets``, ``fetch_ticker``,
``fetch_trades``, ``fetch_ohlcv``, ``fetch_order_book``,
``fetch_funding_rate`` e ``fetch_open_interest``, mais o ciclo de vida
``connect`` / ``disconnect`` / ``health``.

Compatibilidade com o scaffold: os nomes antigos (``list_markets``,
``get_ticker``, ``get_trades``, ``get_candles``, ``get_orderbook``,
``subscribe``) continuam existindo como wrappers concretos que
delegam aos métodos canônicos. Conectores novos implementam só os
canônicos.

Módulos do contrato (todos no mesmo diretório; importar com o
diretório no ``sys.path`` — ver README):

- ``errors`` — :class:`errors.ExchangeError` e códigos (CON-004).
- ``models`` — dataclasses validadas (CON-002).
- ``normalization`` — símbolos, timestamps, lados, tipos (CON-003).
- ``envelope`` — envelope ``ok/error/code/message/retryable`` (CON-004).
- ``connection`` — gerenciador de conexões, heartbeat, reconexão,
  rate limiting, dedup, sequenciamento e gaps (CON-005/CON-006).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from envelope import ResponseEnvelope
from errors import ExchangeError
from models import (
    Candle,
    FundingRate,
    Market,
    OpenInterest,
    OrderBook,
    Ticker,
    Trade,
)
from normalization import normalize_symbol as _normalize_symbol


class ExchangeAdapter(ABC):
    """Adapter universal: REST + WebSocket de uma exchange centralizada.

    Somente leitura pública. Implementações concretas (Fases 4–5)
    traduzem os formatos nativos da exchange para os modelos de
    :mod:`models`, normalizam símbolos/timestamps com
    :mod:`normalization` e preservam o payload original em ``raw``
    (CEX-005).
    """

    exchange_id: str = ""
    name: str = ""

    # -- ciclo de vida -------------------------------------------------------

    @abstractmethod
    def connect(self) -> None:
        """Abre a conexão (REST/WS) da exchange."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Fecha a conexão da exchange."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Saúde da conexão: idade da última mensagem, sequência, atraso.

        Ver :meth:`connection.ConnectionManager.health` para o formato
        recomendado.
        """
        raise NotImplementedError

    # -- leitura pública de mercado (CON-001) --------------------------------

    @abstractmethod
    def fetch_markets(self) -> list[Market]:
        """Lista mercados/instrumentos (spot, perps, futuros, opções)."""
        raise NotImplementedError

    @abstractmethod
    def fetch_ticker(self, symbol: str) -> Ticker:
        """Último preço / ticker de um símbolo normalizado."""
        raise NotImplementedError

    @abstractmethod
    def fetch_trades(
        self, symbol: str, limit: int = 100
    ) -> list[Trade]:
        """Trades recentes (REST). Não simular ticks."""
        raise NotImplementedError

    @abstractmethod
    def fetch_ohlcv(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[Candle]:
        """OHLCV. Só granularidades fornecidas pela fonte (§3)."""
        raise NotImplementedError

    @abstractmethod
    def fetch_order_book(
        self, symbol: str, depth: int = 20
    ) -> OrderBook:
        """Snapshot do livro de ofertas."""
        raise NotImplementedError

    @abstractmethod
    def fetch_funding_rate(self, symbol: str) -> FundingRate:
        """Funding rate atual de um perpétuo (leitura pública)."""
        raise NotImplementedError

    @abstractmethod
    def fetch_open_interest(self, symbol: str) -> OpenInterest:
        """Open interest atual de um contrato (leitura pública)."""
        raise NotImplementedError

    # -- compatibilidade com o scaffold ---------------------------------------
    # Wrappers concretos sobre os métodos canônicos. Conectores novos
    # não precisam reimplementá-los.

    def list_markets(self) -> list[dict[str, Any]]:
        """Legado (scaffold): delega a :meth:`fetch_markets`."""
        return [
            {
                "exchange": m.exchange,
                "symbol": m.symbol,
                "base": m.base,
                "quote": m.quote,
                "market_type": m.market_type,
                "active": m.active,
            }
            for m in self.fetch_markets()
        ]

    def get_ticker(self, symbol: str) -> dict[str, Any]:
        """Legado (scaffold): delega a :meth:`fetch_ticker`."""
        ticker = self.fetch_ticker(self.normalize(symbol))
        return {
            "exchange": ticker.exchange,
            "symbol": ticker.symbol,
            "last": str(ticker.last),
            "bid": str(ticker.bid) if ticker.bid is not None else None,
            "ask": str(ticker.ask) if ticker.ask is not None else None,
            "timestamp_ms": ticker.timestamp_ms,
        }

    def get_trades(self, symbol: str, limit: int = 100) -> list[dict[str, Any]]:
        """Legado (scaffold): delega a :meth:`fetch_trades`."""
        return [
            {
                "exchange": t.exchange,
                "symbol": t.symbol,
                "trade_id": t.trade_id,
                "price": str(t.price),
                "quantity": str(t.quantity),
                "side": t.side,
                "timestamp_ms": t.timestamp_ms,
            }
            for t in self.fetch_trades(self.normalize(symbol), limit=limit)
        ]

    def get_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Legado (scaffold): delega a :meth:`fetch_ohlcv`."""
        return [
            {
                "exchange": c.exchange,
                "symbol": c.symbol,
                "timeframe": c.timeframe,
                "open_time_ms": c.open_time_ms,
                "close_time_ms": c.close_time_ms,
                "open": str(c.open),
                "high": str(c.high),
                "low": str(c.low),
                "close": str(c.close),
                "volume": str(c.volume),
            }
            for c in self.fetch_ohlcv(
                self.normalize(symbol), timeframe, limit=limit
            )
        ]

    def get_orderbook(self, symbol: str, depth: int = 20) -> dict[str, Any]:
        """Legado (scaffold): delega a :meth:`fetch_order_book`."""
        book = self.fetch_order_book(self.normalize(symbol), depth=depth)
        return {
            "exchange": book.exchange,
            "symbol": book.symbol,
            "timestamp_ms": book.timestamp_ms,
            "bids": [[str(p), str(q)] for p, q in book.bids],
            "asks": [[str(p), str(q)] for p, q in book.asks],
            "sequence": book.sequence,
        }

    def subscribe(self, channels: list[str]) -> None:
        """Legado (scaffold): assinatura de canais WebSocket.

        O gerenciamento de assinaturas com recuperação vive em
        :class:`connection.ConnectionManager` (CON-005/CON-006);
        conectores da Fase 4 implementam a assinatura real aqui ou
        delegam ao gerenciador.
        """
        raise NotImplementedError(
            f"{self.name or self.exchange_id}: subscribe ainda não "
            "implementado — usar ConnectionManager (Fase 3) e o "
            "conector da Fase 4."
        )

    # -- helpers ---------------------------------------------------------------

    def normalize(self, symbol: str) -> str:
        """Normaliza um símbolo para o canônico ``BASE/QUOTE``."""
        return _normalize_symbol(symbol, exchange=self.exchange_id or None)

    @staticmethod
    def envelope_ok(
        data: Any, *, raw: Any = None
    ) -> ResponseEnvelope:
        """Envelope de sucesso (CON-004)."""
        from envelope import ok_response

        return ok_response(data, raw=raw)

    @staticmethod
    def envelope_error(error: ExchangeError) -> ResponseEnvelope:
        """Envelope de erro (CON-004)."""
        from envelope import error_response

        return error_response(error)


def normalize_symbol(exchange_symbol: str) -> str:
    """Normaliza símbolo para o formato interno canônico (``BTC/USDT``).

    Compatibilidade com o scaffold: a versão anterior retornava
    ``BTCUSDT`` (concatenado). O canônico da Fase 3 é ``BASE/QUOTE``
    (CON-003); use :func:`normalization.normalize_symbol` para
    controle de exchange e de mercado (spot/perp).
    """
    return _normalize_symbol(exchange_symbol)


__all__ = [
    "ExchangeAdapter",
    "ExchangeError",
    "normalize_symbol",
]
