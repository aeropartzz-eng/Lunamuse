"""Testes do Order Book Manager (DAT-007/008).

Snapshot + deltas sequenciados, divergência, spread e profundidade.
Sem rede.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from market_data import OrderBookManager
from models import OrderBook

T0 = 1_793_000_000_000  # ms UTC (2026-11-13)


def snapshot(seq: int = 100, ts: int = T0) -> OrderBook:
    return OrderBook(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp_ms=ts,
        bids=((Decimal("89999"), Decimal("1")), (Decimal("89998"), Decimal("2"))),
        asks=((Decimal("90001"), Decimal("1")), (Decimal("90002"), Decimal("3"))),
        sequence=seq,
    )


def test_snapshot_sets_state_and_spread():
    manager = OrderBookManager("binance", "BTC/USDT")
    assert manager.apply_snapshot(snapshot()) == "snapshot"
    book = manager.snapshot()
    assert book.best_bid == Decimal("89999")
    assert book.best_ask == Decimal("90001")
    assert book.spread == Decimal("2")
    assert book.mid_price == Decimal("90000")
    assert book.sequence == 100
    assert manager.metrics.snapshots_applied == 1
    assert manager.diverged is False


def test_sequential_updates_applied_and_level_removed():
    manager = OrderBookManager("binance", "BTC/USDT")
    manager.apply_snapshot(snapshot())
    status = manager.apply_update(
        sequence=101,
        bids=[(Decimal("89999"), Decimal("0.5"))],  # atualiza nível
        asks=[(Decimal("90002"), Decimal("0"))],  # remove nível
        timestamp_ms=T0 + 1,
    )
    assert status == "ok"
    book = manager.snapshot()
    assert book.bids[0] == (Decimal("89999"), Decimal("0.5"))
    assert len(book.asks) == 1  # 90002 removido
    assert manager.metrics.updates_applied == 1


def test_duplicate_sequence_dropped():
    manager = OrderBookManager("binance", "BTC/USDT")
    manager.apply_snapshot(snapshot(seq=100))
    manager.apply_update(
        sequence=101, bids=[], asks=[], timestamp_ms=T0 + 1
    )
    assert (
        manager.apply_update(
            sequence=101, bids=[], asks=[], timestamp_ms=T0 + 2
        )
        == "duplicate"
    )
    assert (
        manager.apply_update(
            sequence=99, bids=[], asks=[], timestamp_ms=T0 + 3
        )
        == "duplicate"
    )
    assert manager.metrics.duplicates_dropped == 2
    assert manager.metrics.updates_applied == 1


def test_gap_marks_divergence_and_requires_resync():
    manager = OrderBookManager("binance", "BTC/USDT")
    manager.apply_snapshot(snapshot(seq=100))
    # Salto 100 -> 105: delta NÃO aplicado, book divergente.
    status = manager.apply_update(
        sequence=105,
        bids=[(Decimal("89999"), Decimal("9"))],
        asks=[],
        timestamp_ms=T0 + 1,
    )
    assert status == "gap"
    assert manager.diverged is True
    assert manager.resync_required is True
    assert manager.metrics.gaps_detected == 1
    assert manager.snapshot().bids[0][1] == Decimal("1")  # sem aplicar
    # Novo snapshot resincroniza.
    assert manager.apply_snapshot(snapshot(seq=200)) == "snapshot"
    assert manager.diverged is False
    assert manager.resync_required is False


def test_update_without_snapshot_refused():
    manager = OrderBookManager("binance", "BTC/USDT")
    status = manager.apply_update(
        sequence=1, bids=[], asks=[], timestamp_ms=T0
    )
    assert status == "no_snapshot"
    assert manager.metrics.updates_without_snapshot == 1


def test_crossed_book_is_divergence():
    manager = OrderBookManager("binance", "BTC/USDT")
    manager.apply_snapshot(snapshot())
    status = manager.apply_update(
        sequence=101,
        bids=[(Decimal("90005"), Decimal("1"))],  # bid acima do ask
        asks=[],
        timestamp_ms=T0 + 1,
    )
    assert status == "diverged"
    assert manager.diverged is True
    assert manager.metrics.divergences == 1


def test_unsequenced_updates_applied():
    manager = OrderBookManager("binance", "BTC/USDT")
    manager.apply_snapshot(snapshot(seq=None))
    status = manager.apply_update(
        sequence=None,
        bids=[(Decimal("89999"), Decimal("2"))],
        asks=[],
        timestamp_ms=T0 + 1,
    )
    assert status == "ok_unsequenced"
    assert manager.snapshot().bids[0][1] == Decimal("2")


def test_snapshot_wrong_pair_rejected():
    manager = OrderBookManager("binance", "BTC/USDT")
    other = OrderBook(
        exchange="binance",
        symbol="ETH/USDT",
        timestamp_ms=T0,
        bids=((Decimal("1"), Decimal("1")),),
        asks=((Decimal("2"), Decimal("1")),),
    )
    with pytest.raises(ValueError, match="não pertence"):
        manager.apply_snapshot(other)


def test_depth_quantity_and_imbalance():
    manager = OrderBookManager("binance", "BTC/USDT")
    manager.apply_snapshot(snapshot())
    assert manager.depth_quantity("bid", levels=1) == Decimal("1")
    assert manager.depth_quantity("bid", levels=2) == Decimal("3")
    assert manager.depth_quantity("ask", levels=2) == Decimal("4")
    # (3-4)/(3+4) = -1/7
    assert manager.imbalance(levels=2) == Decimal("-1") / Decimal("7")
    with pytest.raises(ValueError, match="side inválido"):
        manager.depth_quantity("mid", levels=1)


def test_depth_limit_and_health():
    manager = OrderBookManager("binance", "BTC/USDT", depth=1)
    manager.apply_snapshot(snapshot())
    book = manager.snapshot()
    assert len(book.bids) == 1
    assert len(book.asks) == 1
    health = manager.health()
    assert health["has_snapshot"] is True
    assert health["spread"] == "2"
    assert health["bid_levels"] == 2  # estado interno mantém tudo
