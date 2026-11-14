"""Fonte de dados de mercado consumida pelo scanner (Fase 8 — SCN-001…003).

A Fase 7 (Market Data Engine, DAT-001…DAT-010, em paralelo) vai expor
um ``MarketDataSource`` com exatamente esta interface — uma instância
por exchange, somente leitura pública:

- ``get_ticker(symbol)``
- ``get_candles(symbol, timeframe, limit)``
- ``get_trades(symbol, limit)``
- ``get_order_book(symbol, depth)``

Como a Fase 7 ainda não entregou o engine, o protocolo é definido
aqui localmente (``typing.Protocol``, estrutural: qualquer objeto com
esses métodos serve, sem herança obrigatória) e o scanner é construído
contra ele. Quando o engine da Fase 7 existir, basta passar a
instância dele — nenhuma mudança no scanner. **Não duplicar** o
pipeline de dados da Fase 7 aqui: este módulo só define o contrato
de leitura e um adaptador fino sobre o ``ExchangeAdapter`` da Fase 3.

Ponto de integração (VPS): ``AdapterMarketDataSource(adapter)`` liga
um conector CEX existente (Binance, Bybit, OKX, Coinbase, Kraken,
Bitget, Gate.io) ao scanner; o engine da Fase 7 substituirá esse
adaptador quando estiver pronto (cache, dedup, candle builder).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MarketDataSource(Protocol):
    """Fonte de dados de mercado de UMA exchange (leitura pública).

    Os objetos retornados são os modelos validados do contrato
    universal (``services/exchange-connectors/models.py``): ``Ticker``,
    ``Candle``, ``Trade`` e ``OrderBook``. Este módulo não importa
    ``models`` em runtime (evita acoplamento de ``sys.path`` entre
    diretórios com hífen); os tipos abaixo são documentais e o uso é
    estrutural (duck typing).
    """

    def get_ticker(self, symbol: str) -> Any:
        """Último preço / ticker de ``symbol`` (ex.: ``"BTC/USDT"``)."""
        ...

    def get_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[Any]:
        """Candles OHLCV; só granularidades fornecidas pela fonte (§3)."""
        ...

    def get_trades(self, symbol: str, limit: int = 100) -> list[Any]:
        """Trades recentes. Nunca simular ticks."""
        ...

    def get_order_book(self, symbol: str, depth: int = 20) -> Any:
        """Snapshot do livro de ofertas."""
        ...


class AdapterMarketDataSource:
    """Liga um ``ExchangeAdapter`` (Fase 3) ao protocolo acima.

    Adaptador fino: delega cada método ao ``fetch_*`` canônico do
    adapter. Usado até o engine da Fase 7 estar disponível; depois,
    o engine assume este lugar e este adaptador vira fallback de
    leitura direta (útil em testes e no smoke ao vivo).
    """

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter
        self.exchange = getattr(adapter, "exchange_id", "") or ""

    def get_ticker(self, symbol: str) -> Any:
        return self.adapter.fetch_ticker(symbol)

    def get_candles(
        self, symbol: str, timeframe: str, limit: int = 100
    ) -> list[Any]:
        return self.adapter.fetch_ohlcv(symbol, timeframe, limit=limit)

    def get_trades(self, symbol: str, limit: int = 100) -> list[Any]:
        return self.adapter.fetch_trades(symbol, limit=limit)

    def get_order_book(self, symbol: str, depth: int = 20) -> Any:
        return self.adapter.fetch_order_book(symbol, depth=depth)

    def list_symbols(self) -> list[str]:
        """Símbolos do catálogo da exchange (para o Discovery)."""
        return [m.symbol for m in self.adapter.fetch_markets()]


__all__ = ["MarketDataSource", "AdapterMarketDataSource"]
