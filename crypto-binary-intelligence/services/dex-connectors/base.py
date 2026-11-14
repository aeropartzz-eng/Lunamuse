"""Contrato base de conectores DEX / on-chain (Fase 6).

Esqueleto: define a interface que todo conector DEX deve implementar.
Nenhum método faz chamada de rede neste scaffold.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DexAdapter(ABC):
    """Adapter de uma fonte DEX / agregadora."""

    source_id: str = ""
    name: str = ""

    @abstractmethod
    def search_pairs(self, query: str) -> list[dict[str, Any]]:
        """Descoberta de pares (DEX Screener e similares)."""
        raise NotImplementedError

    @abstractmethod
    def get_pool(self, pool_address: str) -> dict[str, Any]:
        """Dados de um pool: liquidez, volume, preço."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> dict[str, Any]:
        raise NotImplementedError
