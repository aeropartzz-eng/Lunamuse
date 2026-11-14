"""Configuração de testes da Fase 10 (Patterns).

Os módulos vivem em diretórios com hífen (não são pacotes importáveis);
por isso entram no ``sys.path`` com ``append`` (os módulos da Fase 3
continuam tendo precedência — ver tests/dex/conftest.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PATTERNS_DIR = _PROJECT_ROOT / "services" / "patterns"

if str(_PATTERNS_DIR) not in sys.path:
    sys.path.append(str(_PATTERNS_DIR))
