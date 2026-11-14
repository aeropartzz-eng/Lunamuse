"""Configuração de testes da Fase 7 (Market Data Engine).

Os módulos da Fase 7 vivem em diretórios com hífen (não são pacotes
importáveis): ``services/market-data/`` (``market_data``) e
``services/candle-builder/`` (``candle_builder``). Os diretórios
entram no ``sys.path`` com ``append`` — os módulos da Fase 3
(``models``, ``normalization``, ``connection``) continuam tendo
precedência via o ``insert(0)`` do conftest raiz.

Nenhum teste aqui usa rede real: WebSocket e conexão Postgres são
fakes.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MARKET_DATA_DIR = _PROJECT_ROOT / "services" / "market-data"
_CANDLE_BUILDER_DIR = _PROJECT_ROOT / "services" / "candle-builder"

for _dir in (_MARKET_DATA_DIR, _CANDLE_BUILDER_DIR):
    if str(_dir) not in sys.path:
        sys.path.append(str(_dir))
