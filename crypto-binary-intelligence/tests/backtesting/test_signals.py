"""Testes de geração de sinais sem look-ahead e de cobertura — Fase 12
(BKT-001/BKT-004/BKT-007). Sem rede.
"""

from __future__ import annotations

import pytest

from signals import generate_signals_series
from strategies import get_strategy


def trend_closes(n=120, start=100.0, step=0.004):
    return [start * (1 + step) ** i for i in range(n)]


def test_no_lookahead_signal_unchanged_by_future(candle_factory):
    """O sinal do candle i não muda quando os candles após i mudam.

    Duas séries idênticas até o candle 60, divergentes depois:
    todos os sinais com índice <= 60 devem ser idênticos.
    """
    closes_a = trend_closes(120)
    closes_b = trend_closes(61) + [50.0] * 59  # crash após o candle 60
    strat = get_strategy("STR-001")
    gen_a = generate_signals_series(strat, candle_factory(closes_a))
    gen_b = generate_signals_series(strat, candle_factory(closes_b))
    sig_a = [(s.index, s.direction) for s in gen_a.signals if s.index <= 60]
    sig_b = [(s.index, s.direction) for s in gen_b.signals if s.index <= 60]
    assert sig_a == sig_b
    assert sig_a, "a série de tendência deve gerar ao menos um sinal"


def test_signal_generation_counts_coverage(candle_factory):
    strat = get_strategy("STR-001")
    gen = generate_signals_series(strat, candle_factory(trend_closes(120)))
    # Warm-up: min_candles=50 -> 70 candles avaliados.
    assert gen.evaluated_bars == 70
    assert gen.warmup_bars == 50
    assert gen.n_signals >= 1
    assert gen.coverage_per_100_bars == pytest.approx(100.0 * gen.n_signals / 70)


def test_signal_generation_start_index(candle_factory):
    strat = get_strategy("STR-001")
    gen = generate_signals_series(
        strat, candle_factory(trend_closes(120)), start_index=100)
    assert gen.evaluated_bars == 20
    assert all(s.index >= 100 for s in gen.signals)


def test_flat_series_generates_no_signals(candle_factory):
    strat = get_strategy("STR-001")
    gen = generate_signals_series(strat, candle_factory([100.0] * 120))
    assert gen.n_signals == 0
    assert gen.evaluated_bars == 70
