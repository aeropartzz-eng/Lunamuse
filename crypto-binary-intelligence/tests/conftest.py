"""Configuração de testes do projeto.

Os módulos do contrato universal vivem em
``services/exchange-connectors/`` como módulos planos (o diretório tem
hífen e não é um pacote importável — ver o README do serviço). Este
conftest coloca esse diretório no ``sys.path`` para que os testes
importem ``base``, ``models``, ``normalization``, ``errors``,
``envelope`` e ``connection`` diretamente.

O mesmo vale para os demais serviços de módulo plano: ``market-scanner``,
``cross-exchange`` e ``indicators`` (Fase 9).
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CONNECTORS_DIR = _PROJECT_ROOT / "services" / "exchange-connectors"
_SCANNER_DIR = _PROJECT_ROOT / "services" / "market-scanner"
_CROSS_EXCHANGE_DIR = _PROJECT_ROOT / "services" / "cross-exchange"
_INDICATORS_DIR = _PROJECT_ROOT / "services" / "indicators"
_PATTERNS_DIR = _PROJECT_ROOT / "services" / "patterns"
_ORDER_FLOW_DIR = _PROJECT_ROOT / "services" / "order-flow"
_MARKET_REGIME_DIR = _PROJECT_ROOT / "services" / "market-regime"
_STRATEGIES_DIR = _PROJECT_ROOT / "services" / "strategies"
_BACKTESTING_DIR = _PROJECT_ROOT / "services" / "backtesting"
_PROBABILITY_DIR = _PROJECT_ROOT / "services" / "probability"

for _dir in (_CONNECTORS_DIR, _SCANNER_DIR, _CROSS_EXCHANGE_DIR, _INDICATORS_DIR,
             _PATTERNS_DIR, _ORDER_FLOW_DIR, _MARKET_REGIME_DIR, _STRATEGIES_DIR,
             _BACKTESTING_DIR, _PROBABILITY_DIR):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))
