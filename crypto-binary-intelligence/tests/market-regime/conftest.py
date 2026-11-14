"""Configuração de testes da Fase 11 (Market Regime).

Os módulos vivem em diretórios com hífen (não são pacotes importáveis);
por isso entram no ``sys.path`` (ver tests/dex/conftest.py).
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from models import Candle

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
for _name in ("exchange-connectors", "indicators", "market-regime"):
    _dir = _PROJECT_ROOT / "services" / _name
    if str(_dir) not in sys.path:
        sys.path.append(str(_dir))

BASE_MS = 1_767_000_000_000  # 2026-01-01T00:00:00Z, em ms


def make_candles(closes, volumes=None, timeframe="5m"):
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
                open_time_ms=BASE_MS + i * 300_000,
                close_time_ms=BASE_MS + (i + 1) * 300_000,
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
    return make_candles
