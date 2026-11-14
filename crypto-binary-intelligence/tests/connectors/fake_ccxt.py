"""Fake de exchange CCXT para os testes dos conectores da Fase 5.

Imita as respostas unificadas do CCXT (dicts/listas) sem nenhuma rede
real e sem importar o CCXT — os testes rodam com o Python do sistema,
onde o CCXT pode não estar instalado. As exceções falsas têm os
mesmos nomes de classe das exceções reais do CCXT, porque a tradução
de erros em :mod:`ccxt_adapter` é feita por nome de classe
(duck typing).

Uso: cada teste constrói o adapter com ``exchange=FakeCCXTExchange(...)``
e, quando quiser simular falha, ``fake.fail_with = {"fetch_ticker":
RateLimitExceeded("slow")}``.
"""

from __future__ import annotations

from typing import Any, Optional

TS = 1_790_985_600_000  # 2026-10-03 00:00:00 UTC, em ms


# Exceções falsas com os nomes das exceções reais do CCXT.
class RateLimitExceeded(Exception):
    """ccxt.RateLimitExceeded (HTTP 429)."""


class RequestTimeout(Exception):
    """ccxt.RequestTimeout."""


class NetworkError(Exception):
    """ccxt.NetworkError."""


class BadSymbol(Exception):
    """ccxt.BadSymbol."""


class NotSupported(Exception):
    """ccxt.NotSupported."""


class ExchangeNotAvailable(Exception):
    """ccxt.ExchangeNotAvailable."""


DEFAULT_TIMEFRAMES = {
    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "12h": 43200,
    "1d": 86400, "1w": 604800,
}


def default_markets() -> list[dict[str, Any]]:
    """Mercados spot + swap no formato unificado do CCXT."""
    return [
        {
            "symbol": "BTC/USDT", "base": "BTC", "quote": "USDT",
            "type": "spot", "active": True,
            "precision": {"price": 2, "amount": 8},
            "limits": {"amount": {"min": 0.0001}},
        },
        {
            "symbol": "ETH/USDT", "base": "ETH", "quote": "USDT",
            "type": "spot", "active": True,
            "precision": {"price": 2, "amount": 8},
            "limits": {"amount": {"min": 0.001}},
        },
        {
            "symbol": "BTC/USDT:USDT", "base": "BTC", "quote": "USDT",
            "type": "swap", "active": True,
            "precision": {"price": 1, "amount": 3},
            "limits": {"amount": {"min": 0.001}},
        },
    ]


def default_ticker(symbol: str = "BTC/USDT") -> dict[str, Any]:
    return {
        "symbol": symbol, "last": 67000.0, "bid": 66990.0, "ask": 67010.0,
        "timestamp": TS, "quoteVolume": 1234567.89, "percentage": 1.5,
    }


def default_trades() -> list[dict[str, Any]]:
    return [
        {"id": "t1", "price": 67000.0, "amount": 0.01,
         "side": "buy", "timestamp": TS},
        {"id": "t2", "price": 67010.0, "amount": 0.02,
         "side": "sell", "timestamp": TS + 1000},
    ]


def default_ohlcv() -> list[list[Any]]:
    """3 candles de 1m consecutivos (sem gap)."""
    return [
        [TS, 67000.0, 67100.0, 66900.0, 67050.0, 12.5],
        [TS + 60_000, 67050.0, 67200.0, 67000.0, 67150.0, 9.25],
        [TS + 120_000, 67150.0, 67300.0, 67100.0, 67250.0, 7.75],
    ]


def gapped_ohlcv() -> list[list[Any]]:
    """Candles de 1m com um intervalo faltando (TS+120000 ausente)."""
    return [
        [TS, 67000.0, 67100.0, 66900.0, 67050.0, 12.5],
        [TS + 60_000, 67050.0, 67200.0, 67000.0, 67150.0, 9.25],
        [TS + 180_000, 67150.0, 67300.0, 67100.0, 67250.0, 7.75],
    ]


def default_order_book() -> dict[str, Any]:
    # Lados fora de ordem de propósito: o adapter deve ordenar.
    return {
        "bids": [[66990.0, 1.0], [67000.0, 0.5]],
        "asks": [[67020.0, 0.9], [67010.0, 0.4]],
        "timestamp": TS, "nonce": 12345,
    }


def default_funding(symbol: str = "BTC/USDT:USDT") -> dict[str, Any]:
    return {
        "symbol": symbol, "fundingRate": 0.0001,
        "fundingTimestamp": TS, "nextFundingTimestamp": TS + 8 * 3_600_000,
        "timestamp": TS,
    }


def default_open_interest(symbol: str = "BTC/USDT:USDT") -> dict[str, Any]:
    return {
        "symbol": symbol, "openInterestAmount": 123456.0, "timestamp": TS,
    }


class FakeCCXTExchange:
    """Fake do exchange CCXT: respostas fixas, sem rede."""

    def __init__(
        self,
        *,
        timeframes: Optional[dict[str, Any]] = None,
        markets: Optional[list[dict[str, Any]]] = None,
        ohlcv_rows: Optional[list[list[Any]]] = None,
        ticker: Optional[dict[str, Any]] = None,
    ) -> None:
        self.timeframes = (
            dict(DEFAULT_TIMEFRAMES) if timeframes is None else timeframes
        )
        self._markets = (
            default_markets() if markets is None else markets
        )
        self._ohlcv_rows = (
            default_ohlcv() if ohlcv_rows is None else ohlcv_rows
        )
        self._ticker = default_ticker() if ticker is None else ticker
        self.fail_with: dict[str, Exception] = {}
        self.loaded_markets = False
        self.closed = False
        self.calls: list[str] = []

    # -- ciclo de vida (CCXT) ------------------------------------------------

    def load_markets(self) -> dict[str, Any]:
        self.loaded_markets = True
        return {m["symbol"]: m for m in self._markets}

    def close(self) -> None:
        self.closed = True

    # -- leitura pública (CCXT unificado) --------------------------------------

    def _maybe_fail(self, method: str) -> None:
        self.calls.append(method)
        if method in self.fail_with:
            raise self.fail_with[method]

    def fetch_markets(self) -> list[dict[str, Any]]:
        self._maybe_fail("fetch_markets")
        return [dict(m) for m in self._markets]

    def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        self._maybe_fail("fetch_ticker")
        return dict(self._ticker, symbol=symbol)

    def fetch_trades(self, symbol: str, since: Any = None,
                     limit: Optional[int] = None) -> list[dict[str, Any]]:
        self._maybe_fail("fetch_trades")
        trades = default_trades()
        return trades[:limit] if limit is not None else trades

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m",
                    since: Any = None,
                    limit: Optional[int] = None) -> list[list[Any]]:
        self._maybe_fail("fetch_ohlcv")
        rows = [list(r) for r in self._ohlcv_rows]
        return rows[:limit] if limit is not None else rows

    def fetch_order_book(self, symbol: str,
                         limit: Optional[int] = None) -> dict[str, Any]:
        self._maybe_fail("fetch_order_book")
        return default_order_book()

    def fetch_funding_rate(self, symbol: str) -> dict[str, Any]:
        self._maybe_fail("fetch_funding_rate")
        return default_funding(symbol)

    def fetch_open_interest(self, symbol: str) -> dict[str, Any]:
        self._maybe_fail("fetch_open_interest")
        return default_open_interest(symbol)


__all__ = [
    "TS",
    "RateLimitExceeded",
    "RequestTimeout",
    "NetworkError",
    "BadSymbol",
    "NotSupported",
    "ExchangeNotAvailable",
    "DEFAULT_TIMEFRAMES",
    "default_markets",
    "default_ticker",
    "default_trades",
    "default_ohlcv",
    "gapped_ohlcv",
    "default_order_book",
    "default_funding",
    "default_open_interest",
    "FakeCCXTExchange",
]
