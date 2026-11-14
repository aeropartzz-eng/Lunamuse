"""Testes das regras de promoção/despromoção (Fase 8 — SCN-004)."""

from __future__ import annotations

from decimal import Decimal

from promotion import PromotionEngine, ScannerThresholds
from scanner import MAX_ACTIVE, MAX_PRIORITY

D = Decimal
TS = 1_790_985_600_000


def strong_active_kwargs():
    return dict(
        timestamp_ms=TS, score=D("5"), rel_volume=D("2"),
        change_pct=D("4"), volatility_pct=D("2"),
        liquidity_usd=D("100000"),
    )


def test_promote_discovery_to_active_with_reason():
    engine = PromotionEngine()
    events = engine.evaluate("binance", "BTC/USDT", **strong_active_kwargs())
    assert len(events) == 1
    assert events[0].from_level == "discovery"
    assert events[0].to_level == "active"
    assert "rel_volume" in events[0].reason
    assert engine.counts()["active"] == 1


def test_no_promotion_below_thresholds():
    engine = PromotionEngine()
    events = engine.evaluate(
        "binance", "BTC/USDT", timestamp_ms=TS, score=D("1"),
        rel_volume=D("1"), change_pct=D("0.5"), volatility_pct=D("1"),
        liquidity_usd=D("100000"),
    )
    assert events == []
    assert engine.counts()["discovery"] == 1


def test_no_promotion_when_illiquid_even_with_strong_signal():
    engine = PromotionEngine()
    events = engine.evaluate(
        "binance", "BTC/USDT", timestamp_ms=TS, score=D("9"),
        rel_volume=D("5"), change_pct=D("9"), volatility_pct=D("9"),
        liquidity_usd=D("1000"),  # abaixo dos US$ 50 mil
    )
    assert events == []


def test_promote_straight_to_priority_on_strong_signal():
    engine = PromotionEngine()
    events = engine.evaluate(
        "binance", "BTC/USDT", timestamp_ms=TS, score=D("9"),
        rel_volume=D("4"), change_pct=D("6"), volatility_pct=D("4"),
        liquidity_usd=D("500000"),
    )
    # Dois eventos: discovery->active e active->priority.
    assert [e.to_level for e in events] == ["active", "priority"]
    assert engine.counts()["priority"] == 1


def test_promote_to_priority_via_imbalance_and_tight_spread():
    engine = PromotionEngine()
    events = engine.evaluate(
        "binance", "BTC/USDT", timestamp_ms=TS, score=D("9"),
        rel_volume=D("1"), change_pct=D("0.5"), volatility_pct=D("1"),
        liquidity_usd=D("500000"), spread_bps=D("10"),
        imbalance=D("0.7"),
    )
    assert [e.to_level for e in events] == ["active", "priority"]


def test_demotion_needs_streak_then_drops():
    engine = PromotionEngine()
    engine.evaluate("binance", "BTC/USDT", **strong_active_kwargs())
    weak = dict(
        timestamp_ms=TS, score=D("0.5"), rel_volume=D("0.5"),
        change_pct=D("0.5"), volatility_pct=D("0.5"),
        liquidity_usd=D("100000"),
    )
    assert engine.evaluate("binance", "BTC/USDT", **weak) == []
    assert engine.evaluate("binance", "BTC/USDT", **weak) == []
    events = engine.evaluate("binance", "BTC/USDT", **weak)
    assert len(events) == 1
    assert events[0].to_level == "discovery"
    assert "weak_streak=3" in events[0].reason


def test_demotion_immediate_when_illiquid():
    engine = PromotionEngine()
    engine.evaluate("binance", "BTC/USDT", **strong_active_kwargs())
    events = engine.evaluate(
        "binance", "BTC/USDT", timestamp_ms=TS, score=D("1"),
        rel_volume=D("2"), change_pct=D("4"),
        liquidity_usd=D("100"),  # ilíquido para active
    )
    assert len(events) == 1 and events[0].to_level == "discovery"


def test_weak_streak_resets_on_strong_evaluation():
    engine = PromotionEngine()
    engine.evaluate("binance", "BTC/USDT", **strong_active_kwargs())
    weak = dict(
        timestamp_ms=TS, score=D("0.5"), rel_volume=D("0.5"),
        change_pct=D("0.5"), liquidity_usd=D("100000"),
    )
    engine.evaluate("binance", "BTC/USDT", **weak)
    engine.evaluate("binance", "BTC/USDT", **strong_active_kwargs())
    assert engine.instruments[("binance", "BTC/USDT")].weak_streak == 0


def test_caps_demote_lowest_score():
    engine = PromotionEngine()
    # Enche o Active com scores altos e promove mais um com score baixo.
    for i in range(MAX_ACTIVE):
        engine.evaluate(
            "binance", f"SYM{i}/USDT", timestamp_ms=TS, score=D("10"),
            rel_volume=D("2"), change_pct=D("4"),
            liquidity_usd=D("100000"),
        )
    assert engine.counts()["active"] == MAX_ACTIVE
    events = engine.evaluate(
        "binance", "LOW/USDT", timestamp_ms=TS, score=D("1"),
        rel_volume=D("2"), change_pct=D("4"), liquidity_usd=D("100000"),
    )
    assert engine.counts()["active"] == MAX_ACTIVE
    assert any("cap de active" in e.reason for e in events)
    assert engine.instruments[("binance", "LOW/USDT")].level == "discovery"


def test_deep_book_only_top_20_priority():
    engine = PromotionEngine()
    for i in range(25):
        engine.evaluate(
            "binance", f"SYM{i}/USDT", timestamp_ms=TS, score=D(str(i + 1)),
            rel_volume=D("4"), change_pct=D("6"), volatility_pct=D("4"),
            liquidity_usd=D("500000"),
        )
    assert engine.counts()["priority"] == 25
    deep = [i for i in engine.by_level("priority") if i.deep_book]
    assert len(deep) == 20
    assert engine.instruments[("binance", "SYM24/USDT")].deep_book is True
    assert engine.instruments[("binance", "SYM0/USDT")].deep_book is False
    assert MAX_PRIORITY == 50
