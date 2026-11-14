"""Helpers de carregamento dos módulos da Fase 6 nos testes."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEX_DIR = _PROJECT_ROOT / "services" / "dex-connectors"
_SHIELD_DIR = _PROJECT_ROOT / "services" / "crypto-shield"


def load_module(name: str, path: Path) -> ModuleType:
    """Carrega um módulo por caminho de arquivo, com nome único.

    Se o nome já foi carregado, retorna o mesmo objeto (uma única
    identidade de classe — sem isso, ``except DexHttpError`` de um
    módulo não reconhece o erro lançado por outro).
    """
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def adapter_path(*parts: str) -> Path:
    """Caminho de um arquivo dentro de services/dex-connectors."""
    return _DEX_DIR.joinpath(*parts)


def shield_path(name: str) -> Path:
    """Caminho de um módulo dentro de services/crypto-shield."""
    return _SHIELD_DIR / name
