"""Fixtures compartilhadas dos testes de indicadores (Fase 9).

Constrói candles válidos (:class:`Candle`) a partir de séries de
fechamento, para testar ``candles_to_arrays`` / ``compute_all``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from models import Candle

BASE_MS = 1_767_000_000_000  # 2026-01-01T00:00:00Z, em ms


def make_candles(closes, volumes=None, timeframe="1m"):
    """Candles OHLCV válidos: open = fechamento anterior, high/low com
    folga de 0.5 em torno de open/close."""
    candles = []
    prev = closes[0]
    for i, close in enumerate(closes):
        open_ = prev
        high = max(open_, close) + 0.5
        low = min(open_, close) - 0.5
        vol = 100.0 if volumes is None else volumes[i]
        candles.append(
            Candle(
                exchange="binance",
                symbol="BTC/USDT",
                timeframe=timeframe,
                open_time_ms=BASE_MS + i * 60_000,
                close_time_ms=BASE_MS + (i + 1) * 60_000,
                open=Decimal(str(open_)),
                high=Decimal(str(high)),
                low=Decimal(str(low)),
                close=Decimal(str(close)),
                volume=Decimal(str(vol)),
            )
        )
        prev = close
    return candles


@pytest.fixture
def candle_factory():
    """Fábrica de candles válidos para os testes deste diretório."""
    return make_candles


@pytest.fixture
def closes():
    return [10, 11, 12, 13, 14, 15, 14, 13, 12, 11]


@pytest.fixture
def ohlc(closes):
    """H/L/C coerentes com ``closes`` (high/low com folga de 1)."""
    high = [c + 1 for c in closes]
    low = [c - 1 for c in closes]
    return high, low, closes
