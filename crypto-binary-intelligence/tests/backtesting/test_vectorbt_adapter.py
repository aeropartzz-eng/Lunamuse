"""Teste da verificação cruzada com vectorbt — Fase 12 (BKT-001).

O replay usa as mesmas entradas/saídas do motor próprio; a
contabilidade (taxas, retornos, contagem de trades) deve concordar
dentro da tolerância. Sem rede. Pulado se o vectorbt não estiver
instalado.
"""

from __future__ import annotations

import pytest

vectorbt = pytest.importorskip("vectorbt")

from costs import CostModel
from engine import BacktestEngine
from vectorbt_adapter import run_vectorbt_crosscheck, vectorbt_available


def test_vectorbt_crosscheck_agrees_with_engine(rising_candles):
    """Série +1%/candle; último candle plano para alinhar o preço de
    saída (motor fecha no close; vectorbt executa no open passado)."""
    candles = list(rising_candles)
    assert vectorbt_available()
    costs = CostModel(fee_bps=10.0, spread_bps=0.0, slippage_bps=0.0,
                      latency_bars=0, partial_fill_chunks=1)
    engine = BacktestEngine(costs=costs, initial_capital=10_000.0)
    signal = {"index": 0, "direction": "long", "entry_price": 100.0,
              "stop_loss": None, "take_profit": None,
              "probability": 0.6, "valid_until_ms": None}
    result = engine.run(candles, [signal])
    check = run_vectorbt_crosscheck(
        candles, result.trades, result.fills, costs, 10_000.0,
        engine_final_equity=result.final_equity)
    assert check["available"] is True
    assert check["n_trades"] == result.n_trades == 1
    # Reconciliação exata: final_vectorbt == final_motor + taxas + gas.
    assert check["reconciled_delta_usd"] == pytest.approx(0.0, abs=0.01)
    # O retorno do vectorbt é bruto de taxas; o do motor, líquido.
    assert check["total_return_pct"] > result.total_return_pct


def test_vectorbt_crosscheck_no_trades(flat_candles):
    costs = CostModel()
    check = run_vectorbt_crosscheck(flat_candles, [], [], costs, 10_000.0)
    assert check["available"] is True
    assert check["n_trades"] == 0


def test_vectorbt_crosscheck_mixed_long_short(candle_factory):
    """Long + short no mesmo replay: shorts vão para
    short_entries/short_exits, não viram longs."""
    # Sobe 100 -> 110 (bars 0-9), cai 110 -> 100 (bars 10-19).
    closes = [100.0 * 1.01 ** i for i in range(10)]
    closes += [closes[-1] * 0.99 ** i for i in range(1, 11)]
    candles = candle_factory(closes)
    costs = CostModel(fee_bps=0.0, spread_bps=0.0, slippage_bps=0.0)
    engine = BacktestEngine(costs=costs, initial_capital=10_000.0)
    signals = [
        {"index": 0, "direction": "long", "entry_price": 100.0,
         "stop_loss": None, "take_profit": 105.0,
         "probability": 0.6, "valid_until_ms": None},
        {"index": 10, "direction": "short", "entry_price": 110.0,
         "stop_loss": None, "take_profit": None,
         "probability": 0.6, "valid_until_ms": None},
    ]
    result = engine.run(candles, signals)
    assert result.n_trades == 2
    assert {t.direction for t in result.trades} == {"long", "short"}
    assert result.trades[0].exit_reason == "target"
    check = run_vectorbt_crosscheck(
        candles, result.trades, result.fills, costs, 10_000.0,
        engine_final_equity=result.final_equity)
    assert check["available"] is True
    assert check["n_trades"] == 2
    # Custos zero: reconciliação exata (delta ~0) e retornos iguais.
    assert check["reconciled_delta_usd"] == pytest.approx(0.0, abs=0.01)
    assert check["total_return_pct"] == pytest.approx(
        result.total_return_pct, abs=0.01)
    assert check["total_return_pct"] > 0  # long ganhou na subida, short na descida
