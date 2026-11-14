"""Testes do Candle Builder (DAT-003/004/005/006).

Trades sintéticos: OHLCV correto, agregação de timeframes, sem
look-ahead, validação cronológica e detecção de gaps. Sem rede.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from candle_builder import (
    TIMEFRAME_MS,
    aggregate_candles,
    bucket_start_ms,
    detect_gaps,
)
from candle_builder import CandleBuilder
from models import Candle, Trade

T0 = int(datetime(2026, 11, 13, tzinfo=timezone.utc).timestamp() * 1000)
EXCHANGE = "binance"
SYMBOL = "BTC/USDT"


def trade(price: str, qty: str, ts: int, trade_id: str = "1") -> Trade:
    return Trade(
        exchange=EXCHANGE,
        symbol=SYMBOL,
        trade_id=trade_id,
        price=Decimal(price),
        quantity=Decimal(qty),
        side="buy",
        timestamp_ms=ts,
    )


def test_timeframe_table_matches_spec():
    # §3: os 17 timeframes, nem um a mais nem um a menos.
    assert set(TIMEFRAME_MS) == {
        "1s", "5s", "15s", "30s",
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "8h", "12h",
        "1d", "1w",
    }
    assert TIMEFRAME_MS["1m"] == 60_000
    assert TIMEFRAME_MS["1d"] == 86_400_000
    assert TIMEFRAME_MS["1w"] == 604_800_000


def test_bucket_start_aligns_to_epoch():
    assert bucket_start_ms(T0 + 61_000, "1m") == T0 + 60_000
    assert bucket_start_ms(T0, "1m") == T0


def test_ohlcv_correct_single_bucket():
    builder = CandleBuilder(EXCHANGE, SYMBOL, ["1m"])
    # 4 trades no mesmo bucket de 1m.
    assert builder.add_trade(trade("100", "1", T0 + 1_000, "1")) == []
    assert builder.add_trade(trade("102", "2", T0 + 2_000, "2")) == []
    assert builder.add_trade(trade("98", "1", T0 + 3_000, "3")) == []
    assert builder.add_trade(trade("101", "3", T0 + 4_000, "4")) == []
    # Trade no bucket seguinte fecha o candle.
    closed = builder.add_trade(trade("101", "1", T0 + 60_000, "5"))
    assert len(closed) == 1
    candle = closed[0]
    assert candle.open == Decimal("100")
    assert candle.high == Decimal("102")
    assert candle.low == Decimal("98")
    assert candle.close == Decimal("101")
    assert candle.volume == Decimal("7")
    assert candle.trades == 4
    assert candle.open_time_ms == T0
    assert candle.close_time_ms == T0 + 60_000 - 1
    assert candle.timeframe == "1m"


def test_no_lookahead_open_candle_not_emitted():
    builder = CandleBuilder(EXCHANGE, SYMBOL, ["1m"])
    builder.add_trade(trade("100", "1", T0 + 1_000, "1"))
    # O bucket corrente é parcial: não aparece como fechado.
    assert builder.flush(T0 + 30_000) == []
    partial = builder.open_candles()
    assert len(partial) == 1
    assert partial[0].open == Decimal("100")
    # Só depois do fim do bucket o flush fecha.
    closed = builder.flush(T0 + 60_000)
    assert len(closed) == 1
    assert closed[0].close == Decimal("100")


def test_multiple_timeframes_close_together():
    builder = CandleBuilder(EXCHANGE, SYMBOL, ["1m", "5m"])
    builder.add_trade(trade("100", "1", T0 + 1_000, "1"))
    closed = builder.add_trade(trade("100", "1", T0 + 300_000, "2"))
    by_tf = {c.timeframe: c for c in closed}
    assert set(by_tf) == {"1m", "5m"}
    assert by_tf["1m"].open_time_ms == T0
    assert by_tf["5m"].open_time_ms == T0
    assert by_tf["5m"].volume == Decimal("1")


def test_out_of_order_trade_rejected():
    builder = CandleBuilder(EXCHANGE, SYMBOL, ["1m"])
    builder.add_trade(trade("100", "1", T0 + 5_000, "1"))
    # Trade com timestamp anterior: rejeitado, sem candle, sem efeito.
    assert builder.add_trade(trade("999", "1", T0 + 1_000, "2")) == []
    assert builder.metrics.out_of_order_rejected == 1
    assert builder.metrics.trades_accepted == 1
    # O candle parcial mantém o preço do trade aceito.
    assert builder.open_candles()[0].high == Decimal("100")


def test_gap_buckets_skipped_not_invented():
    builder = CandleBuilder(EXCHANGE, SYMBOL, ["1m"])
    builder.add_trade(trade("100", "1", T0 + 1_000, "1"))
    # Pulo de 3 buckets: só o primeiro fecha; 2 buckets sem trades.
    closed = builder.add_trade(trade("101", "1", T0 + 180_000, "2"))
    assert len(closed) == 1
    assert closed[0].open_time_ms == T0
    assert builder.metrics.gap_buckets_skipped == 2
    # Nenhum candle inventado para os buckets vazios.
    assert builder.metrics.candles_closed == 1


def test_wrong_pair_rejected():
    builder = CandleBuilder(EXCHANGE, SYMBOL, ["1m"])
    other = Trade(
        exchange=EXCHANGE,
        symbol="ETH/USDT",
        trade_id="1",
        price=Decimal("10"),
        quantity=Decimal("1"),
        side="buy",
        timestamp_ms=T0,
    )
    with pytest.raises(ValueError, match="não pertence"):
        builder.add_trade(other)


def test_invalid_timeframe_rejected():
    with pytest.raises(ValueError, match="timeframe inválido"):
        CandleBuilder(EXCHANGE, SYMBOL, ["2m"])
    with pytest.raises(ValueError, match="timeframe inválido"):
        CandleBuilder(EXCHANGE, SYMBOL, ["90s"])
    with pytest.raises(ValueError):
        CandleBuilder(EXCHANGE, SYMBOL, [])


def _closed_1m_candles() -> list[Candle]:
    """5 candles de 1m fechados (preços 100..104, 1 trade cada)."""
    builder = CandleBuilder(EXCHANGE, SYMBOL, ["1m"])
    closed: list[Candle] = []
    for i in range(5):
        closed.extend(
            builder.add_trade(
                trade(str(100 + i), "1", T0 + i * 60_000, str(i + 1))
            )
        )
    closed.extend(builder.flush(T0 + 5 * 60_000))
    assert len(closed) == 5
    return closed


def test_aggregate_1m_to_5m():
    candles = _closed_1m_candles()
    agg = aggregate_candles(candles, "5m")
    assert len(agg) == 1
    c = agg[0]
    assert c.timeframe == "5m"
    assert c.open == Decimal("100")
    assert c.high == Decimal("104")
    assert c.low == Decimal("100")
    assert c.close == Decimal("104")
    assert c.volume == Decimal("5")
    assert c.trades == 5
    assert c.open_time_ms == T0
    assert c.close_time_ms == T0 + 300_000 - 1


def test_aggregate_requires_exact_multiple():
    candles = _closed_1m_candles()
    # 1m -> 3m é múltiplo; 1m -> 2h também; 1m -> 4m não existe.
    assert len(aggregate_candles(candles, "3m")) == 2  # 3 + 2
    with pytest.raises(ValueError, match="múltiplo exato"):
        aggregate_candles(candles, "1m")  # alvo <= origem
    with pytest.raises(ValueError, match="timeframe inválido"):
        aggregate_candles(candles, "4m")


def test_aggregate_1d_to_1w():
    # Semanas alinham à época Unix (quinta 00:00 UTC): começar numa
    # quinta para os 7 dias caírem no mesmo bucket semanal.
    t_thu = T0 - 86_400_000  # 2026-11-12, quinta-feira
    assert t_thu % TIMEFRAME_MS["1w"] == 0
    builder = CandleBuilder(EXCHANGE, SYMBOL, ["1d"])
    closed: list[Candle] = []
    for i in range(7):
        closed.extend(
            builder.add_trade(
                trade("100", "1", t_thu + i * 86_400_000, str(i + 1))
            )
        )
    closed.extend(builder.flush(t_thu + 7 * 86_400_000))
    assert len(closed) == 7
    agg = aggregate_candles(closed, "1w")
    assert len(agg) == 1
    assert agg[0].volume == Decimal("7")


def test_aggregate_rejects_mixed_pairs_and_empty():
    candles = _closed_1m_candles()
    mixed = candles + [
        Candle(
            exchange=EXCHANGE,
            symbol="ETH/USDT",
            timeframe="1m",
            open_time_ms=T0,
            close_time_ms=T0 + 59_999,
            open=Decimal("1"),
            high=Decimal("1"),
            low=Decimal("1"),
            close=Decimal("1"),
            volume=Decimal("1"),
        )
    ]
    with pytest.raises(ValueError, match="um só par"):
        aggregate_candles(mixed, "5m")
    assert aggregate_candles([], "5m") == []


def test_detect_gaps_finds_missing_buckets():
    candles = _closed_1m_candles()
    # Remove o 3º candle (bucket T0+120000).
    present = [c for c in candles if c.open_time_ms != T0 + 120_000]
    assert detect_gaps(present, "1m") == [T0 + 120_000]
    assert detect_gaps(candles, "1m") == []
    assert detect_gaps(candles[:1], "1m") == []
    assert detect_gaps([], "1m") == []


def test_builder_health_reports_metrics():
    builder = CandleBuilder(EXCHANGE, SYMBOL, ["1m"])
    builder.add_trade(trade("100", "1", T0 + 1_000, "1"))
    health = builder.health()
    assert health["exchange"] == EXCHANGE
    assert health["symbol"] == SYMBOL
    assert health["trades_accepted"] == 1
    assert health["open_buckets"] == {"1m": T0}
