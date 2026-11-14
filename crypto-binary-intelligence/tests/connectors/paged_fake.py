"""Fake CCXT com paginação (Fase 4 — CEX-001…CEX-003).

Estende :class:`tests.connectors.fake_ccxt.FakeCCXTExchange` com
conjuntos grandes de trades/candles e filtragem por ``since``/``limit``,
para testar a paginação de :meth:`ccxt_adapter.CCXTAdapter.fetch_trades`
e :meth:`fetch_ohlcv` (limite > 1000 por chamada, dedup entre páginas).
Sem rede real, sem CCXT instalado.
"""

from __future__ import annotations

from typing import Any, Optional

from tests.connectors.fake_ccxt import TS, FakeCCXTExchange


class PagedFakeCCXTExchange(FakeCCXTExchange):
    """Fake com N trades e M candles consecutivos, pagináveis."""

    def __init__(
        self,
        *,
        n_trades: int = 0,
        n_candles: int = 0,
        timeframes: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(timeframes=timeframes, **kwargs)
        self._all_trades = [
            {
                "id": f"t{i}",
                "price": 67000.0 + i,
                "amount": 0.01,
                "side": "buy" if i % 2 == 0 else "sell",
                "timestamp": TS + i * 1000,
            }
            for i in range(n_trades)
        ]
        self._all_candles = [
            [
                TS + i * 60_000,
                67000.0 + i,
                67100.0 + i,
                66900.0 + i,
                67050.0 + i,
                10.0,
            ]
            for i in range(n_candles)
        ]

    def fetch_trades(self, symbol: str, since: Any = None,
                     limit: Optional[int] = None) -> list[dict[str, Any]]:
        self._maybe_fail("fetch_trades")
        rows = [
            t for t in self._all_trades
            if since is None or t["timestamp"] >= since
        ]
        return rows[:limit] if limit is not None else rows

    def fetch_ohlcv(self, symbol: str, timeframe: str = "1m",
                    since: Any = None,
                    limit: Optional[int] = None) -> list[list[Any]]:
        self._maybe_fail("fetch_ohlcv")
        rows = [
            list(r) for r in self._all_candles
            if since is None or r[0] >= since
        ]
        return rows[:limit] if limit is not None else rows


__all__ = ["PagedFakeCCXTExchange"]
