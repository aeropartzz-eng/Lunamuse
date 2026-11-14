"""Testes do Strategy Lab — Fase 11 (STR-001…STR-010).

Cada estratégia tem ao menos um teste positivo (série construída para
o setup gera sinal) e um negativo (série sem setup não gera sinal).
Reprodutibilidade e versionamento também são testados. Sem rede.
"""

from __future__ import annotations

import pytest

from market_regime import Regime
from strategies import (
    COMBINER_THRESHOLD,
    COMBINER_WEIGHTS,
    get_strategy,
    list_strategies,
    STRATEGY_REGISTRY,
)


def regime(label):
    return Regime(label=label, confidence=0.8, reason="teste", index=0)


def trend_closes(n=80, start=100.0, step=0.004):
    return [start * (1 + step) ** i for i in range(n)]


def trend_volumes(n=80, last=150.0):
    return [100.0] * (n - 1) + [last]


# --- Catálogo / framework (STR-001) --------------------------------------------

def test_registry_has_ten_strategies():
    assert len(STRATEGY_REGISTRY) == 10
    assert sorted(STRATEGY_REGISTRY) == [f"STR-{i:03d}" for i in range(1, 11)]


def test_list_strategies_describes_all():
    catalog = list_strategies()
    assert len(catalog) == 10
    for entry in catalog:
        assert entry["version"] >= 1
        assert entry["markets"] and entry["timeframes"]
        assert entry["status"] in ("experimental", "testing", "approved", "disabled")


def test_get_strategy_unknown_raises():
    with pytest.raises(KeyError):
        get_strategy("STR-999")


def test_combiner_weights_sum_to_one():
    assert abs(sum(COMBINER_WEIGHTS.values()) - 1.0) < 1e-9
    assert COMBINER_THRESHOLD == 0.50


# --- STR-001 Trend Following -----------------------------------------------------

def test_str001_trend_following_long(candle_factory):
    closes = trend_closes()
    signals = get_strategy("STR-001").generate_signals(
        candle_factory(closes, trend_volumes()), regime=regime("TREND_UP"))
    assert len(signals) == 1
    sig = signals[0]
    assert sig.direction == "long"
    assert sig.strategy_id == "STR-001" and sig.strategy_version == 1
    assert sig.stop_loss < sig.entry_price < sig.take_profit
    assert 0.55 <= sig.probability <= 0.85
    assert sig.rationale and all("EMA" in r or "ADX" in r or "MACD" in r for r in sig.rationale)
    assert sig.valid_until_ms > 0
    assert sig.regime == "TREND_UP"


def test_str001_no_signal_without_trend(candle_factory):
    closes = [100 + 2 * __import__("math").sin(i * 2 * __import__("math").pi / 20) for i in range(80)]
    signals = get_strategy("STR-001").generate_signals(
        candle_factory(closes), regime=regime("RANGE"))
    assert signals == []


def test_str001_regime_gate_blocks(candle_factory):
    # Série de tendência, mas regime incompatível -> nenhum sinal.
    signals = get_strategy("STR-001").generate_signals(
        candle_factory(trend_closes(), trend_volumes()), regime=regime("RANGE"))
    assert signals == []


# --- STR-002 Momentum --------------------------------------------------------------

def test_str002_momentum_long(candle_factory):
    closes = [100 * 1.005 ** i for i in range(60)]
    signals = get_strategy("STR-002").generate_signals(
        candle_factory(closes, trend_volumes(60)), regime=regime("TREND_UP"))
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert any("RSI" in r for r in signals[0].rationale)
    assert any("ROC" in r for r in signals[0].rationale)


def test_str002_no_signal_flat(candle_factory):
    signals = get_strategy("STR-002").generate_signals(
        candle_factory([100.0] * 60), regime=regime("RANGE"))
    assert signals == []


# --- STR-003 Pullback -----------------------------------------------------------------

def test_str003_pullback_long(candle_factory):
    closes = [100 * 1.002 ** i for i in range(50)]
    price = closes[-1]
    for _ in range(5):
        price *= 0.998
        closes.append(price)
    closes.append(closes[-1] * 1.004)
    signals = get_strategy("STR-003").generate_signals(
        candle_factory(closes), regime=regime("TREND_UP"))
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert signals[0].stop_loss < signals[0].entry_price < signals[0].take_profit


def test_str003_no_signal_on_pure_trend(candle_factory):
    # Tendência sem pullback: preço longe demais da EMA20.
    signals = get_strategy("STR-003").generate_signals(
        candle_factory(trend_closes()), regime=regime("TREND_UP"))
    assert signals == []


# --- STR-004 Breakout -------------------------------------------------------------------

def test_str004_breakout_long(candle_factory):
    closes = [100.0] * 50 + [108.0]
    volumes = [100.0] * 50 + [300.0]
    signals = get_strategy("STR-004").generate_signals(
        candle_factory(closes, volumes), regime=regime("EXPANSION"))
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert any("Bollinger" in r or "banda superior" in r for r in signals[0].rationale)


def test_str004_no_signal_without_volume(candle_factory):
    closes = [100.0] * 50 + [108.0]
    volumes = [100.0] * 51  # rompimento sem volume: não confirma
    signals = get_strategy("STR-004").generate_signals(
        candle_factory(closes, volumes), regime=regime("EXPANSION"))
    assert signals == []


# --- STR-005 False Breakout --------------------------------------------------------------

def test_str005_false_breakout_long(candle_factory, ohlc_factory):
    # Sobe até ~110, recua, depois varre a mínima e fecha de volta acima.
    closes = [100 * 1.0035 ** i for i in range(30)]
    for _ in range(5):
        closes.append(closes[-1] * 0.995)
    candles = candle_factory(closes)
    prev_low = min(float(c.low) for c in candles[-20:])
    last = candles[-1]
    sweep = ohlc_factory([(
        float(last.close), float(last.close) + 1.5,
        prev_low - 1.0, float(last.close) + 1.0, 200.0,
    )])
    candles = candles + sweep
    signals = get_strategy("STR-005").generate_signals(candles, regime=regime("RANGE"))
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert any("sweep" in r for r in signals[0].rationale)


def test_str005_no_signal_on_clean_break(candle_factory):
    # Rompimento verdadeiro (fecha abaixo da mínima): não é false breakout.
    closes = [100.0] * 40
    candles = candle_factory(closes)
    signals = get_strategy("STR-005").generate_signals(candles, regime=regime("RANGE"))
    assert signals == []


# --- STR-006 Mean Reversion -----------------------------------------------------------------

def test_str006_mean_reversion_long(candle_factory):
    closes = [100.0] * 60
    price = 100.0
    for _ in range(10):
        price *= 0.98
        closes.append(price)
    signals = get_strategy("STR-006").generate_signals(
        candle_factory(closes), regime=regime("RANGE"))
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert any("RSI" in r for r in signals[0].rationale)
    assert any("Z-score" in r for r in signals[0].rationale)


def test_str006_gate_blocks_in_trend(candle_factory):
    # Mesmo setup, mas regime de tendência -> o filtro de regime bloqueia.
    closes = [100.0] * 60
    price = 100.0
    for _ in range(10):
        price *= 0.98
        closes.append(price)
    signals = get_strategy("STR-006").generate_signals(
        candle_factory(closes), regime=regime("TREND_DOWN"))
    assert signals == []


# --- STR-007 Range Trading --------------------------------------------------------------------

def test_str007_range_long(candle_factory):
    pattern = [100, 101, 102, 101, 100, 99, 98, 99]
    closes = (pattern * 10)[:80]
    assert closes[-1] == 99  # perto do suporte 98
    signals = get_strategy("STR-007").generate_signals(
        candle_factory([float(c) for c in closes]), regime=regime("RANGE"))
    assert len(signals) == 1
    assert signals[0].direction == "long"


def test_str007_no_signal_mid_range(candle_factory):
    pattern = [100, 101, 102, 101, 100, 99, 98, 99]
    closes = (pattern * 10)[:80]
    closes[-1] = 100.0  # meio do range: longe de suporte e resistência
    signals = get_strategy("STR-007").generate_signals(
        candle_factory([float(c) for c in closes]), regime=regime("RANGE"))
    assert signals == []


# --- STR-008 Engulfing/Doji ---------------------------------------------------------------------

def test_str008_bullish_engulfing(candle_factory, ohlc_factory):
    rows = []
    price = 110.0
    for _ in range(30):
        open_ = price
        close = price * 0.997
        rows.append((open_, open_ + 0.3, close - 0.3, close, 100.0))
        price = close
    # Candle pequeno de baixa, depois engolfo de alta com volume.
    rows.append((100.0, 100.3, 98.0, 98.5, 100.0))
    rows.append((98.0, 101.5, 97.8, 101.0, 250.0))
    signals = get_strategy("STR-008").generate_signals(
        ohlc_factory(rows), regime=regime("TREND_DOWN"))
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert any("engulfing" in r for r in signals[0].rationale)


def test_str008_no_signal_without_pattern(candle_factory):
    signals = get_strategy("STR-008").generate_signals(
        candle_factory(trend_closes()), regime=regime("TREND_UP"))
    assert signals == []


# --- STR-009 Multi-Timeframe ----------------------------------------------------------------------

def test_str009_mtf_long(candle_factory):
    closes = trend_closes(60)
    signals = get_strategy("STR-009").generate_signals(
        candle_factory(closes, trend_volumes(60)), regime=regime("TREND_UP"))
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert any("M15" in r for r in signals[0].rationale)
    assert any("M5" in r for r in signals[0].rationale)


def test_str009_with_explicit_context(candle_factory):
    closes = trend_closes(60)
    higher = candle_factory(trend_closes(60), timeframe="15m")
    lower = candle_factory([100.0, 101.0], timeframe="1m")
    signals = get_strategy("STR-009").generate_signals(
        candle_factory(closes, trend_volumes(60)), regime=regime("TREND_UP"),
        context={"higher": higher, "lower": lower})
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert signals[0].probability == 0.65


def test_str009_no_signal_misaligned(candle_factory):
    # Série primária de alta, mas timeframe maior de baixa -> sem sinal.
    closes = trend_closes(60)
    higher = candle_factory([100 * 0.996 ** i for i in range(60)], timeframe="15m")
    signals = get_strategy("STR-009").generate_signals(
        candle_factory(closes, trend_volumes(60)), regime=regime("TREND_UP"),
        context={"higher": higher})
    assert signals == []


# --- STR-010 Combinador ----------------------------------------------------------------------------

def test_str010_confluence_long(candle_factory):
    closes = trend_closes(60)
    signals = get_strategy("STR-010").generate_signals(
        candle_factory(closes, trend_volumes(60, last=200.0)), regime=regime("TREND_UP"))
    assert len(signals) == 1
    assert signals[0].direction == "long"
    assert any("confluência" in r for r in signals[0].rationale)
    assert len([r for r in signals[0].rationale if "peso" in r]) == 5


def test_str010_no_signal_flat(candle_factory):
    signals = get_strategy("STR-010").generate_signals(
        candle_factory([100.0] * 60), regime=regime("RANGE"))
    assert signals == []


# --- Negativo universal, reprodutibilidade, versão, filtros -----------------------------------------

@pytest.mark.parametrize("code", sorted(STRATEGY_REGISTRY))
def test_no_strategy_signals_on_flat_series(candle_factory, code):
    signals = get_strategy(code).generate_signals(
        candle_factory([100.0] * 60), regime=regime("RANGE"))
    assert signals == []


def test_reproducibility(candle_factory):
    candles = candle_factory(trend_closes(), trend_volumes())
    first = get_strategy("STR-001").generate_signals(candles, regime=regime("TREND_UP"))
    second = get_strategy("STR-001").generate_signals(candles, regime=regime("TREND_UP"))
    assert [s.to_dict() for s in first] == [s.to_dict() for s in second]


def test_versioning_changes_signal_version(candle_factory):
    candles = candle_factory(trend_closes(), trend_volumes())
    v1 = get_strategy("STR-001").generate_signals(candles, regime=regime("TREND_UP"))
    v2 = get_strategy("STR-001", version=2).generate_signals(candles, regime=regime("TREND_UP"))
    assert len(v1) == len(v2) == 1
    assert v1[0].strategy_version == 1
    assert v2[0].strategy_version == 2
    assert v2[0].strategy_id == "STR-001"
    assert get_strategy("STR-001", version=2).describe()["version"] == 2


def test_signal_schema_matches_strategy_signals_table(candle_factory):
    sig = get_strategy("STR-001").generate_signals(
        candle_factory(trend_closes(), trend_volumes()), regime=regime("TREND_UP"))[0]
    data = sig.to_dict()
    for key in ("exchange", "market", "symbol", "timeframe", "direction",
                "strategy_id", "strategy_version", "reference_price",
                "entry_price", "stop_loss", "take_profit", "probability",
                "valid_until_ms", "rationale", "status"):
        assert key in data, f"falta {key} no sinal"
    assert data["status"] == "DETECTED"
    assert data["direction"] in ("long", "short")
    assert data["valid_until_ms"] > int(candle_factory(trend_closes())[0].close_time_ms)


def test_global_filters_spread_and_liquidity(candle_factory):
    candles = candle_factory(trend_closes(), trend_volumes())
    strat = get_strategy("STR-001")
    assert strat.generate_signals(candles, regime=regime("TREND_UP"), spread_bps=100.0) == []
    assert strat.generate_signals(candles, regime=regime("TREND_UP"), liquidity_usd=100.0) == []
    assert len(strat.generate_signals(
        candles, regime=regime("TREND_UP"), spread_bps=10.0, liquidity_usd=50_000.0)) == 1


def test_global_filters_require_market_data_in_production(candle_factory):
    from strategies import GlobalFilters
    candles = candle_factory(trend_closes(), trend_volumes())
    strat = get_strategy("STR-001", filters=GlobalFilters(require_market_data=True))
    assert strat.generate_signals(candles, regime=regime("TREND_UP")) == []
    assert len(strat.generate_signals(
        candles, regime=regime("TREND_UP"), spread_bps=10.0, liquidity_usd=50_000.0)) == 1


def test_insufficient_candles_returns_empty(candle_factory):
    signals = get_strategy("STR-001").generate_signals(
        candle_factory([100.0] * 10), regime=regime("TREND_UP"))
    assert signals == []


def test_disabled_strategy_emits_nothing(candle_factory):
    strat = get_strategy("STR-001", status="disabled")
    signals = strat.generate_signals(
        candle_factory(trend_closes(), trend_volumes()), regime=regime("TREND_UP"))
    assert signals == []
