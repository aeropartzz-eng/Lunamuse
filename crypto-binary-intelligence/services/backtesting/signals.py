"""Geração de sinais ao longo da série — Fase 12 (BKT-001/BKT-004).

O motor nunca vê o futuro: para decidir o que acontece no candle
``i``, a estratégia só recebe os candles até ``i`` (prefixo
``candles[:i + 1]``). É o mesmo contrato de :func:`BaseStrategy.
generate_signals` (que avalia só o último candle fechado), aplicado
bar a bar. Um teste de look-ahead em ``tests/backtesting`` verifica
que o sinal do candle ``i`` não muda quando os candles após ``i``
são alterados.

Cobertura (§8 / protocolo do 85%): cada chamada conta como um
candle avaliado; cada sinal emitido conta como sinal gerado; o
motor conta quantos viraram trades. O relatório sempre informa os
três números juntos com a precisão.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    import indicators as _indicators
except ImportError:  # diretório services/indicators fora do sys.path
    sys.path.append(str(Path(__file__).resolve().parents[1] / "indicators"))
    import indicators as _indicators

try:
    import market_regime as _market_regime
except ImportError:
    try:
        sys.path.append(str(Path(__file__).resolve().parents[1] / "market-regime"))
        import market_regime as _market_regime
    except ImportError:
        _market_regime = None  # type: ignore[assignment]

try:
    import patterns as _patterns
except ImportError:
    try:
        sys.path.append(str(Path(__file__).resolve().parents[1] / "patterns"))
        import patterns as _patterns
    except ImportError:
        _patterns = None  # type: ignore[assignment]

__all__ = [
    "SeriesSignal",
    "SignalGeneration",
    "generate_signals_series",
]


@dataclass(frozen=True)
class SeriesSignal:
    """Um sinal emitido no candle ``index`` da série."""

    index: int  # índice do candle que gerou o sinal
    signal: Any  # strategies.Signal (entry/stop/target/probabilidade)
    strategy_id: str
    strategy_version: int

    @property
    def direction(self) -> str:
        return self.signal.direction

    @property
    def entry_price(self) -> float:
        return float(self.signal.entry_price)

    @property
    def stop_loss(self) -> float:
        return float(self.signal.stop_loss)

    @property
    def take_profit(self) -> float:
        return float(self.signal.take_profit)

    @property
    def probability(self) -> float:
        return float(self.signal.probability)

    @property
    def valid_until_ms(self) -> int:
        return int(self.signal.valid_until_ms)


@dataclass
class SignalGeneration:
    """Resultado da varredura: sinais + contadores de cobertura."""

    signals: List[SeriesSignal] = field(default_factory=list)
    evaluated_bars: int = 0  # candles avaliados (a partir do warm-up)
    warmup_bars: int = 0  # candles pulados por falta de histórico

    @property
    def n_signals(self) -> int:
        return len(self.signals)

    @property
    def coverage_per_100_bars(self) -> float:
        """Sinais gerados por 100 candles avaliados."""
        if self.evaluated_bars == 0:
            return 0.0
        return 100.0 * self.n_signals / self.evaluated_bars


def generate_signals_series(
    strategy: Any,
    candles: Sequence[Any],
    *,
    symbol: str = "BTC/USDT",
    exchange: str = "binance",
    market: str = "spot",
    timeframe: Optional[str] = None,
    spread_bps: Optional[float] = None,
    liquidity_usd: Optional[float] = None,
    start_index: int = 0,
) -> SignalGeneration:
    """Varre a série gerando sinais sem look-ahead.

    Para cada índice ``i >= max(start_index, strategy.min_candles)``,
    chama ``strategy.generate_signals(candles[:i + 1], ...)`` — a
    estratégia só vê o prefixo até ``i``. Sinais de um mesmo candle
    nunca se repetem (a base emite no máximo 1 por chamada).

    ``start_index`` permite varrer só um trecho (ex.: a janela de
    teste do walk-forward); ``evaluated_bars`` conta só o trecho
    varrido. O warm-up (``min_candles``) é respeitado: índices
    anteriores não são avaliados.

    Desempenho: indicadores, regimes e padrões são calculados **uma
    vez** sobre a série inteira e reutilizados a cada candle. Isso
    não vaza o futuro: os indicadores da Fase 9 são causais
    (IND-008 — o valor no índice ``i`` só usa dados até ``i``), o
    regime classificado no índice ``i`` só usa dados até ``i`` e os
    padrões terminam no índice ``i``; a estratégia só lê os caches
    no índice do último candle do prefixo. O teste de look-ahead
    (``tests/backtesting/test_signals.py``) verifica que mudar os
    candles após ``i`` não muda o sinal de ``i``.
    """
    candles = list(candles)
    n = len(candles)
    warmup = max(int(getattr(strategy, "min_candles", 0)), 0)
    first = max(start_index, warmup)
    out = SignalGeneration(warmup_bars=first)
    if first >= n:
        return out
    indicators_cache = None
    regimes: Dict[int, Any] = {}
    patterns_list: Optional[list] = None
    if _indicators is not None:
        try:
            indicators_cache = _indicators.compute_all(candles)
        except Exception:
            indicators_cache = None
    if _market_regime is not None:
        try:
            classified = _market_regime.classify_series(candles)
            start_regime = _market_regime.MIN_CANDLES - 1
            regimes = {start_regime + k: r for k, r in enumerate(classified)}
        except Exception:
            regimes = {}
    if _patterns is not None:
        try:
            patterns_list = _patterns.detect_all(candles)
        except Exception:
            patterns_list = []
    for i in range(first, n):
        out.evaluated_bars += 1
        try:
            found = strategy.generate_signals(
                candles[: i + 1],
                indicators_cache=indicators_cache,
                patterns=patterns_list,
                regime=regimes.get(i),
                symbol=symbol,
                exchange=exchange,
                market=market,
                timeframe=timeframe,
                spread_bps=spread_bps,
                liquidity_usd=liquidity_usd,
            )
        except Exception:
            # Série sintética ou prefixo curto não pode derrubar a
            # varredura: sem sinal neste candle.
            continue
        for sig in found or []:
            out.signals.append(
                SeriesSignal(
                    index=i,
                    signal=sig,
                    strategy_id=getattr(sig, "strategy_id", strategy.code),
                    strategy_version=int(getattr(sig, "strategy_version", strategy.version)),
                )
            )
    return out
