"""Testes do motor de backtest — Fase 12 (BKT-001/BKT-002/BKT-003).

Valores calculados à mão; sem rede.
"""

from __future__ import annotations

import math

import pytest

from costs import CostModel
from engine import BacktestEngine


ZERO_COSTS = CostModel(
    fee_bps=0.0, spread_bps=0.0, slippage_bps=0.0,
    gas_usd=0.0, latency_bars=0, partial_fill_chunks=1,
)


def buy_signal(index, entry=100.0, stop=None, take=None):
    return {
        "index": index,
        "direction": "long",
        "entry_price": entry,
        "stop_loss": stop,
        "take_profit": take,
        "probability": 0.6,
        "valid_until_ms": None,
    }


# --- Buy-and-hold com retorno conhecido -------------------------------------

def test_buy_and_hold_known_return(rising_candles):
    """Série +1%/candle, 20 candles: 100 -> 100*1.01**19 no close final.

    Compra no sinal do candle 0 (fill na abertura do candle 1 =
    close do candle 0 = 100), sem stop/alvo: fecha no último close.
    Custos zero: retorno = 1.01**19 - 1 = 20,81%.
    """
    engine = BacktestEngine(costs=ZERO_COSTS, initial_capital=10_000.0)
    result = engine.run(rising_candles, [buy_signal(0)])
    assert result.n_trades == 1
    trade = result.trades[0]
    assert trade.entry_index == 1
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.quantity == pytest.approx(100.0)
    expected_close = 100.0 * 1.01 ** 19
    assert trade.exit_price == pytest.approx(expected_close)
    assert trade.exit_reason == "end_of_data"
    assert result.final_equity == pytest.approx(100.0 * expected_close)
    assert result.total_return_pct == pytest.approx((1.01 ** 19 - 1) * 100)
    assert result.equity_curve[-1] == pytest.approx(result.final_equity)
    assert result.n_signals_executed == 1


def test_costs_reduce_return_by_expected_amount(rising_candles):
    """Custos padrão reduzem o retorno; cada fill registra preço,
    custo e slippage."""
    engine = BacktestEngine(costs=CostModel(), initial_capital=10_000.0)
    result = engine.run(rising_candles, [buy_signal(0)])
    assert result.n_trades == 1
    trade = result.trades[0]
    # Fill de compra: open 100 + metade do spread (2,5 bps) + slippage (5 bps).
    assert trade.entry_fills[0].price == pytest.approx(100.0 * (1 + 0.00025 + 0.0005))
    assert trade.entry_fills[0].fee_usd == pytest.approx(
        trade.entry_fills[0].notional_usd * 0.001)
    assert trade.entry_fills[0].slippage_usd == pytest.approx(
        (trade.entry_fills[0].price - 100.0) * trade.entry_fills[0].quantity)
    assert result.final_equity < 100.0 * (100.0 * 1.01 ** 19)
    assert result.final_equity > 12_000.0  # ainda lucra, menos que sem custos
    assert result.total_cost_usd > 0
    assert result.total_cost_usd == pytest.approx(
        sum(f.total_cost_usd for f in result.fills))


def test_gas_is_charged_once_per_order(rising_candles):
    costs = CostModel(fee_bps=0.0, spread_bps=0.0, slippage_bps=0.0, gas_usd=5.0)
    engine = BacktestEngine(costs=costs, initial_capital=10_000.0)
    result = engine.run(rising_candles, [buy_signal(0)])
    assert result.total_gas_usd == pytest.approx(5.0)
    # Gas sai do capital alocado: qty = (10000 - 5) / 100 = 99,95.
    expected = (10_000.0 - 5.0) / 100.0 * (100.0 * 1.01 ** 19)
    assert result.final_equity == pytest.approx(expected)


# --- Stop / alvo --------------------------------------------------------------

def test_stop_loss_exit(candle_factory):
    closes = [100.0] * 10 + [98.0, 96.0, 94.0] + [94.0] * 7
    candles = candle_factory(closes)
    engine = BacktestEngine(costs=ZERO_COSTS)
    result = engine.run(candles, [buy_signal(0, stop=95.0, take=110.0)])
    assert result.n_trades == 1
    trade = result.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == pytest.approx(95.0)
    # Low do candle 12 é 93.5 (close 94 - 0.5): stop tocado no candle 12.
    assert trade.exit_index == 12
    assert trade.net_pnl_usd == pytest.approx((95.0 - 100.0) * 100.0)


def test_take_profit_exit(candle_factory):
    closes = [100.0] * 10 + [102.0, 104.0, 106.0] + [106.0] * 7
    candles = candle_factory(closes)
    engine = BacktestEngine(costs=ZERO_COSTS)
    result = engine.run(candles, [buy_signal(0, stop=95.0, take=105.0)])
    trade = result.trades[0]
    assert trade.exit_reason == "target"
    assert trade.exit_price == pytest.approx(105.0)
    assert trade.exit_index == 12
    assert trade.net_pnl_usd == pytest.approx((105.0 - 100.0) * 100.0)


def test_stop_wins_when_both_hit_same_bar(candle_factory):
    """Stop e alvo tocados no mesmo candle: sai no stop (conservador)."""
    closes = [100.0] * 10 + [100.0, 100.0] + [100.0] * 8
    candles = candle_factory(closes)
    # Candle 11: high 100.5 / low 99.5 não toca nada; forçamos com
    # stop 99.6 e alvo 100.4 — ambos dentro do range do candle 11.
    engine = BacktestEngine(costs=ZERO_COSTS)
    result = engine.run(candles, [buy_signal(0, stop=99.6, take=100.4)])
    trade = result.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == pytest.approx(99.6)


def test_short_trade(rising_candles):
    """Short numa série que sobe perde; preço de fill espelhado."""
    signal = {
        "index": 0, "direction": "short", "entry_price": 100.0,
        "stop_loss": None, "take_profit": None,
        "probability": 0.6, "valid_until_ms": None,
    }
    engine = BacktestEngine(costs=ZERO_COSTS, initial_capital=10_000.0)
    result = engine.run(rising_candles, [signal])
    trade = result.trades[0]
    assert trade.direction == "short"
    assert trade.net_pnl_usd == pytest.approx(
        (100.0 - 100.0 * 1.01 ** 19) * 100.0)


# --- Latência e fills parciais -------------------------------------------------

def test_latency_delays_entry(rising_candles):
    costs = CostModel(fee_bps=0.0, spread_bps=0.0, slippage_bps=0.0, latency_bars=1)
    engine = BacktestEngine(costs=costs)
    result = engine.run(rising_candles, [buy_signal(0)])
    # Sinal no candle 0 -> fill na abertura do candle 2 (1 + latência 1).
    assert result.trades[0].entry_index == 2
    assert result.trades[0].entry_price == pytest.approx(100.0 * 1.01)


def test_partial_fills_split_order(rising_candles):
    costs = CostModel(fee_bps=0.0, spread_bps=0.0, slippage_bps=0.0,
                      partial_fill_chunks=3)
    # Alocação de 90%: com preços subindo, os 3 chunks a 100% do
    # capital não caberiam no caixa (o motor cancela o restante —
    # comportamento correto; ver engine).
    engine = BacktestEngine(costs=costs, position_size_pct=0.9)
    result = engine.run(rising_candles, [buy_signal(0)])
    trade = result.trades[0]
    assert len(trade.entry_fills) == 3
    assert all(f.status == "partial" for f in trade.entry_fills[:2])
    assert trade.entry_fills[2].status == "filled"
    assert [f.index for f in trade.entry_fills] == [1, 2, 3]
    assert trade.quantity == pytest.approx(90.0)
    # Preço médio ponderado dos 3 fills (aberturas 100, 101, 102.01).
    assert trade.entry_price == pytest.approx((100.0 + 101.0 + 102.01) / 3.0)


def test_partial_fills_cancelled_when_cash_runs_out(rising_candles):
    """Alocação de 100% com preços subindo: o 3º chunk não cabe no
    caixa restante e é cancelado (o que já entrou permanece)."""
    costs = CostModel(fee_bps=0.0, spread_bps=0.0, slippage_bps=0.0,
                      partial_fill_chunks=3)
    engine = BacktestEngine(costs=costs, position_size_pct=1.0)
    result = engine.run(rising_candles, [buy_signal(0)])
    trade = result.trades[0]
    assert len(trade.entry_fills) == 2
    assert result.n_signals_cancelled_partial == 1


def test_signal_expired_before_fill(rising_candles):
    """Sinal com validade anterior ao candle de execução é descartado."""
    signal = buy_signal(0)
    signal["valid_until_ms"] = 1_767_000_000_000 + 1 * 300_000  # fecha candle 0
    engine = BacktestEngine(costs=ZERO_COSTS)
    result = engine.run(rising_candles, [signal])
    assert result.n_trades == 0
    assert result.n_signals_expired == 1


def test_second_signal_ignored_while_in_position(rising_candles):
    engine = BacktestEngine(costs=ZERO_COSTS)
    result = engine.run(rising_candles, [buy_signal(0), buy_signal(5)])
    assert result.n_trades == 1
    assert result.n_signals_ignored_in_position == 1


def test_no_signal_no_trade(flat_candles):
    engine = BacktestEngine(costs=ZERO_COSTS)
    result = engine.run(flat_candles, [])
    assert result.n_trades == 0
    assert result.final_equity == pytest.approx(10_000.0)
    assert all(e == pytest.approx(10_000.0) for e in result.equity_curve)
