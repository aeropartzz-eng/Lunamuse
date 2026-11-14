"""Testes do gerenciador de conexões (Fase 3 — CON-005/CON-006, §5).

Cobre: token bucket (rate limit), deduplicação, sequenciamento/gaps,
heartbeat/staleness, reconexão exponencial com jitter e recuperação
de assinaturas. Tudo com relógio, sleep e RNG injetados — nenhuma
rede real.
"""

from __future__ import annotations

import random

import pytest

from connection import (
    ConnectionManager,
    ConnectionState,
    MessageDeduplicator,
    SequenceStatus,
    SequenceTracker,
    TokenBucket,
    next_backoff,
)
from errors import ErrorCode, ExchangeError


# ---------------------------------------------------------------------------
# Relógio falso (ms e segundos) para testes determinísticos
# ---------------------------------------------------------------------------

class FakeClock:
    """Relógio controlável: ms para o manager, segundos para o bucket."""

    def __init__(self, start_ms: int = 1_791_000_000_000) -> None:
        self.now_ms = start_ms

    def ms(self) -> int:
        return self.now_ms

    def seconds(self) -> float:
        return self.now_ms / 1000.0

    def advance_ms(self, ms: int) -> None:
        self.now_ms += ms


def make_manager(clock: FakeClock, **kwargs) -> ConnectionManager:
    """Manager com transporte fake (sem rede) e sleep que só registra."""
    sleeps: list[float] = []
    manager = ConnectionManager(
        "fake",
        time_fn_ms=clock.ms,
        sleep_fn=sleeps.append,
        rng=random.Random(42),
        **kwargs,
    )
    manager._recorded_sleeps = sleeps  # type: ignore[attr-defined]
    return manager


# ---------------------------------------------------------------------------
# Backoff exponencial com jitter
# ---------------------------------------------------------------------------

def test_next_backoff_grows_and_caps():
    rng = random.Random(7)
    delays = [next_backoff(i, base_s=1.0, max_s=8.0, jitter=0.0, rng=rng)
              for i in range(6)]
    assert delays == [1.0, 2.0, 4.0, 8.0, 8.0, 8.0]


def test_next_backoff_jitter_stays_within_bounds():
    rng = random.Random(7)
    for attempt in range(5):
        delay = next_backoff(attempt, base_s=2.0, max_s=60.0,
                             jitter=0.25, rng=rng)
        base = min(2.0 * (2 ** attempt), 60.0)
        assert base * 0.75 <= delay <= base * 1.25


def test_next_backoff_rejects_negative_attempt():
    with pytest.raises(ValueError):
        next_backoff(-1)


# ---------------------------------------------------------------------------
# Token bucket (rate limiting por exchange)
# ---------------------------------------------------------------------------

def test_token_bucket_burst_then_blocks_then_refills():
    clock = FakeClock()
    bucket = TokenBucket(rate_per_sec=10.0, capacity=3, clock=clock.seconds)
    assert bucket.try_acquire()
    assert bucket.try_acquire()
    assert bucket.try_acquire()
    assert bucket.try_acquire() is False  # estourou o burst
    clock.advance_ms(200)  # +2 tokens (10/s * 0.2s)
    assert bucket.try_acquire()
    assert bucket.try_acquire()
    assert bucket.try_acquire() is False


def test_token_bucket_acquire_or_raise_rate_limit():
    clock = FakeClock()
    bucket = TokenBucket(rate_per_sec=1.0, capacity=1, clock=clock.seconds)
    bucket.try_acquire()
    with pytest.raises(ExchangeError) as excinfo:
        bucket.acquire_or_raise()
    assert excinfo.value.code == ErrorCode.RATE_LIMIT
    assert excinfo.value.retryable is True


def test_token_bucket_rejects_invalid_params():
    with pytest.raises(ValueError):
        TokenBucket(rate_per_sec=0, capacity=5)
    with pytest.raises(ValueError):
        TokenBucket(rate_per_sec=1, capacity=0)


# ---------------------------------------------------------------------------
# Deduplicação
# ---------------------------------------------------------------------------

def test_deduplicator_drops_repeated_message():
    dedup = MessageDeduplicator(max_size=10)
    assert dedup.is_duplicate("msg-1") is False
    assert dedup.is_duplicate("msg-1") is True
    assert dedup.is_duplicate("msg-2") is False
    assert len(dedup) == 2


def test_deduplicator_evicts_oldest_when_full():
    dedup = MessageDeduplicator(max_size=2)
    dedup.is_duplicate("a")
    dedup.is_duplicate("b")
    dedup.is_duplicate("c")  # "a" sai
    assert dedup.is_duplicate("a") is False  # esquecida: aceita de novo
    assert dedup.is_duplicate("c") is True  # ainda lembrada


# ---------------------------------------------------------------------------
# Sequenciamento e gaps
# ---------------------------------------------------------------------------

def test_sequence_tracker_ok_duplicate_gap():
    tracker = SequenceTracker()
    assert tracker.check("trades", 100) == SequenceStatus.FIRST
    assert tracker.check("trades", 101) == SequenceStatus.OK
    assert tracker.check("trades", 101) == SequenceStatus.DUPLICATE
    assert tracker.check("trades", 105) == SequenceStatus.GAP  # faltaram 3
    assert tracker.total_gaps() == 3
    assert tracker.gap_events == 1
    assert tracker.check("trades", 106) == SequenceStatus.OK


def test_sequence_tracker_channels_are_independent():
    tracker = SequenceTracker()
    tracker.check("trades", 10)
    assert tracker.check("book", 1) == SequenceStatus.FIRST
    assert tracker.check("trades", 11) == SequenceStatus.OK


# ---------------------------------------------------------------------------
# ConnectionManager: ciclo de vida e reconexão
# ---------------------------------------------------------------------------

def test_manager_connect_disconnect_state():
    manager = make_manager(FakeClock())
    assert manager.state == ConnectionState.DISCONNECTED
    manager.connect()
    assert manager.state == ConnectionState.CONNECTED
    manager.disconnect()
    assert manager.state == ConnectionState.DISCONNECTED


def test_manager_reconnect_retries_then_succeeds():
    clock = FakeClock()
    attempts = {"n": 0}

    def flaky_connect():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ExchangeError(ErrorCode.CONNECTION_LOST, "caiu")

    manager = make_manager(clock, on_connect=flaky_connect,
                           backoff_base_s=1.0, backoff_max_s=60.0)
    assert manager.reconnect(max_attempts=5) is True
    assert attempts["n"] == 3
    assert manager.state == ConnectionState.CONNECTED
    assert manager.metrics.reconnects == 1
    # backoff cresceu: 1s, 2s, 4s (com jitter ±25%) — um sleep por
    # tentativa, incluindo a que teve sucesso
    sleeps = manager._recorded_sleeps  # type: ignore[attr-defined]
    assert len(sleeps) == 3
    assert 0.75 <= sleeps[0] <= 1.25
    assert 1.5 <= sleeps[1] <= 2.5
    assert 3.0 <= sleeps[2] <= 5.0


def test_manager_reconnect_gives_up_after_max_attempts():
    def always_fail():
        raise ExchangeError(ErrorCode.CONNECTION_LOST, "sempre cai")

    manager = make_manager(FakeClock(), on_connect=always_fail)
    assert manager.reconnect(max_attempts=3) is False
    assert manager.state == ConnectionState.DISCONNECTED
    assert manager.metrics.last_error == "[CONNECTION_LOST] sempre cai"


def test_manager_handle_disconnect_recovers():
    clock = FakeClock()
    calls = {"connect": 0}

    def connect():
        calls["connect"] += 1

    manager = make_manager(clock, on_connect=connect)
    manager.connect()
    assert manager.handle_disconnect(
        ExchangeError(ErrorCode.CONNECTION_LOST, "queda")) is True
    assert manager.state == ConnectionState.CONNECTED
    assert calls["connect"] == 2


def test_manager_restores_subscriptions_on_reconnect():
    clock = FakeClock()
    subscribed: list[list[str]] = []
    manager = make_manager(
        clock, on_subscribe=lambda ch: subscribed.append(list(ch)))
    manager.subscribe(["ticker:BTC/USDT", "trades:BTC/USDT"])
    manager.connect()  # restaura as assinaturas guardadas
    assert subscribed == [["ticker:BTC/USDT", "trades:BTC/USDT"]]
    # queda + reconexão: assina de novo
    manager.handle_disconnect()
    assert len(subscribed) == 2
    assert subscribed[1] == ["ticker:BTC/USDT", "trades:BTC/USDT"]


# ---------------------------------------------------------------------------
# ConnectionManager: mensagens, dedup, gaps, heartbeat e latência
# ---------------------------------------------------------------------------

def test_manager_drops_duplicate_message():
    clock = FakeClock()
    manager = make_manager(clock)
    manager.connect()
    first = manager.on_message("trades", dedup_key="t-1",
                               received_at_ms=clock.ms())
    assert first["status"] == "accepted"
    second = manager.on_message("trades", dedup_key="t-1",
                                received_at_ms=clock.ms())
    assert second["status"] == "duplicate"
    assert manager.metrics.messages_received == 1
    assert manager.metrics.duplicates_dropped == 1


def test_manager_detects_sequence_gap():
    clock = FakeClock()
    manager = make_manager(clock)
    manager.connect()
    manager.on_message("trades", sequence=100, received_at_ms=clock.ms())
    result = manager.on_message("trades", sequence=103,
                                received_at_ms=clock.ms())
    assert result["status"] == "accepted"
    assert result["gap"] is True
    assert result["sequence_status"] == "gap"
    assert manager.metrics.gaps_detected == 2
    assert manager.health()["gaps_detected"] == 2


def test_manager_heartbeat_stale_and_latency():
    clock = FakeClock()
    manager = make_manager(clock, heartbeat_interval_ms=10_000,
                           max_missed_heartbeats=3)
    # sem nenhuma mensagem: feed parado
    assert manager.is_stale() is True
    assert manager.last_message_age_ms() is None

    manager.connect()
    manager.on_message("ticker", received_at_ms=clock.ms())
    assert manager.is_stale() is False
    assert manager.last_message_age_ms() == 0

    clock.advance_ms(29_000)
    assert manager.is_stale() is False
    assert manager.last_message_age_ms() == 29_000
    clock.advance_ms(2_000)  # 31s > 3 x 10s
    assert manager.is_stale() is True
    assert manager.health()["stale"] is True
    assert manager.health()["last_message_age_ms"] == 31_000


def test_manager_rate_limit_blocks_acquire():
    clock = FakeClock()
    manager = make_manager(clock, rate_per_sec=1.0, rate_burst=1)
    manager.acquire()  # consome o único token
    with pytest.raises(ExchangeError) as excinfo:
        manager.acquire()
    assert excinfo.value.code == ErrorCode.RATE_LIMIT


def test_manager_health_shape():
    clock = FakeClock()
    manager = make_manager(clock)
    manager.connect()
    manager.on_message("ticker", received_at_ms=clock.ms())
    health = manager.health()
    assert health["exchange"] == "fake"
    assert health["connected"] is True
    assert health["messages_received"] == 1
    assert health["duplicates_dropped"] == 0
    assert health["gaps_detected"] == 0
    assert health["reconnects"] == 0
    assert health["subscriptions"] == []
