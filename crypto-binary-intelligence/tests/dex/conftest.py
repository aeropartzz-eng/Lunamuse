"""Configuração de testes da Fase 6 (DEX e Crypto Shield).

Os módulos da Fase 6 vivem em diretórios com hífen (não são pacotes
importáveis) e alguns nomes colidem com os da Fase 3 (``base``,
``models``). Por isso os diretórios entram no ``sys.path`` com
``append`` (nunca ``insert(0)`` — os módulos da Fase 3 continuam
tendo precedência). Os adapters são carregados por caminho de arquivo
via :func:`tests.dex.helpers.load_module`.

Nenhum teste aqui usa rede real: sessões HTTP/RPC são fakes.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEX_DIR = _PROJECT_ROOT / "services" / "dex-connectors"
_RPC_DIR = _DEX_DIR / "rpc"
_SHIELD_DIR = _PROJECT_ROOT / "services" / "crypto-shield"

for _dir in (_DEX_DIR, _RPC_DIR, _SHIELD_DIR):
    if str(_dir) not in sys.path:
        sys.path.append(str(_dir))
