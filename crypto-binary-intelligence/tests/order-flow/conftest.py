"""Configuração de testes da Fase 10 (Order Flow).

O módulo vive em diretório com hífen (não é pacote importável); entra
no ``sys.path`` com ``append`` (ver tests/dex/conftest.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ORDER_FLOW_DIR = _PROJECT_ROOT / "services" / "order-flow"

if str(_ORDER_FLOW_DIR) not in sys.path:
    sys.path.append(str(_ORDER_FLOW_DIR))
