"""Testes de persistência (DAT-009) e retenção (DAT-010).

Repositório contra o schema ``002_market.sql`` com fake em memória
e com conexão fake (o SQL é verificado sem Postgres real); política
de retenção §11 como código.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from market_data import (
    InMemoryMarketDataRepository,
    PostgresMarketDataRepository,
    RetentionPolicy,
)
from models import Candle, OrderBook, Ticker, Trade

T0 = 1_793_000_000_000  # ms UTC (2026-11-13)


def make_trade(trade_id: str = "1", price: str = "90000") -> Trade:
    return Trade(
        exchange="binance",
        symbol="BTC/USDT",
        trade_id=trade_id,
        price=Decimal(price),
        quantity=Decimal("0.01"),
        side="buy",
        timestamp_ms=T0,
    )


def make_candle(tf: str = "1m", open_ms: int = T0) -> Candle:
    return Candle(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe=tf,
        open_time_ms=open_ms,
        close_time_ms=open_ms + 59_999,
        open=Decimal("90000"),
        high=Decimal("90010"),
        low=Decimal("89990"),
        close=Decimal("90005"),
        volume=Decimal("1.5"),
        trades=3,
    )


class FakeCursor:
    """Cursor DB-API fake: registra executes, finge rowcount=1."""

    def __init__(self, log: list) -> None:
        self.log = log
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.log.append((sql, params))


class FakeConnection:
    """Conexão DB-API fake (sem Postgres)."""

    def __init__(self) -> None:
        self.log: list = []
        self.commits = 0

    def cursor(self):
        return FakeCursor(self.log)

    def commit(self):
        self.commits += 1


# -- InMemory ---------------------------------------------------------------

def test_inmemory_save_trades_and_idempotent_replay():
    repo = InMemoryMarketDataRepository()
    assert repo.save_trades([make_trade("1"), make_trade("2")]) == 2
    assert repo.save_trades([make_trade("1")]) == 0  # replay: nada novo
    rows = repo.rows("market_trades")
    assert len(rows) == 2
    assert rows[0]["quote_quantity"] == Decimal("900")
    assert rows[0]["is_buyer_maker"] is False
    assert rows[0]["time"] == T0


def test_inmemory_save_candles_source_builder():
    repo = InMemoryMarketDataRepository()
    assert repo.save_candles([make_candle()], source="builder") == 1
    assert repo.save_candles([make_candle()], source="builder") == 0
    row = repo.rows("market_candles")[0]
    assert row["source"] == "builder"
    assert row["is_closed"] is True
    assert row["trades_count"] == 3
    with pytest.raises(ValueError, match="source inválido"):
        repo.save_candles([make_candle()], source="outra")


def test_inmemory_save_book_ticker_events():
    repo = InMemoryMarketDataRepository()
    book = OrderBook(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp_ms=T0,
        bids=((Decimal("89999"), Decimal("1")),),
        asks=((Decimal("90001"), Decimal("1")),),
        sequence=10,
    )
    assert repo.save_orderbook_snapshot(book) == 1
    snap = repo.rows("orderbook_snapshots")[0]
    assert snap["best_bid"] == Decimal("89999")
    assert snap["spread"] == Decimal("2")
    assert snap["mid_price"] == Decimal("90000")
    assert repo.save_orderbook_event(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp_ms=T0,
        event_type="update",
        side="bid",
        price=Decimal("89999"),
        quantity=Decimal("2"),
        sequence=11,
    ) == 1
    assert len(repo.rows("orderbook_events")) == 1
    ticker = Ticker(
        exchange="binance",
        symbol="BTC/USDT",
        last=Decimal("90000"),
        timestamp_ms=T0,
        bid=Decimal("89999"),
        ask=Decimal("90001"),
        volume_24h=Decimal("100"),
    )
    assert repo.save_ticker(ticker) == 1
    assert repo.rows("market_tickers")[0]["last_price"] == Decimal("90000")
    with pytest.raises(ValueError, match="tabela desconhecida"):
        repo.rows("nao_existe")


# -- Postgres (SQL gerado, conexão fake) --------------------------------------

def test_postgres_builders_match_schema_columns():
    sql, params = PostgresMarketDataRepository.build_save_trades(
        [make_trade("1")]
    )
    assert "INSERT INTO market_trades" in sql
    assert "ON CONFLICT (time, exchange, symbol, trade_id) DO NOTHING" in sql
    assert params[0][2] == "BTC/USDT"  # symbol
    sql, params = PostgresMarketDataRepository.build_save_candles(
        [make_candle()], source="exchange"
    )
    assert "INSERT INTO market_candles" in sql
    assert "ON CONFLICT (time, exchange, symbol, timeframe) DO NOTHING" in sql
    assert params[0][10] == "exchange"
    sql, params = PostgresMarketDataRepository.build_save_orderbook_snapshot(
        OrderBook(
            exchange="binance",
            symbol="BTC/USDT",
            timestamp_ms=T0,
            bids=((Decimal("1"), Decimal("2")),),
            asks=((Decimal("3"), Decimal("4")),),
            sequence=5,
        )
    )
    assert "INSERT INTO orderbook_snapshots" in sql
    assert params[3] == '[["1", "2"]]'  # bids como JSON
    with pytest.raises(ValueError, match="source inválido"):
        PostgresMarketDataRepository.build_save_candles(
            [make_candle()], source="x"
        )


def test_postgres_executes_via_injected_connection():
    conn = FakeConnection()
    repo = PostgresMarketDataRepository(conn)
    assert repo.save_trades([make_trade("1"), make_trade("2")]) == 2
    assert repo.save_candles([make_candle()]) == 1
    assert conn.commits == 2
    assert len(conn.log) == 3
    assert all("INSERT INTO" in sql for sql, _ in conn.log)
    assert repo.save_trades([]) == 0  # vazio não executa nada
    assert repo.save_candles([]) == 0


# -- Retenção (§11) -----------------------------------------------------------

def test_retention_policies_match_spec_section_11():
    assert RetentionPolicy.retention_for("market_trades") == timedelta(days=7)
    assert RetentionPolicy.retention_for("orderbook_snapshots") == timedelta(days=7)
    assert RetentionPolicy.retention_for("orderbook_events") == timedelta(days=7)
    assert RetentionPolicy.retention_for("market_tickers") == timedelta(days=30)
    assert RetentionPolicy.retention_for("market_candles", "1s") == timedelta(days=30)
    assert RetentionPolicy.retention_for("market_candles", "1m") == timedelta(days=730)
    assert RetentionPolicy.retention_for("market_candles", "5m") == timedelta(days=730)
    assert RetentionPolicy.retention_for("market_candles", "1h") == timedelta(days=1095)
    assert RetentionPolicy.retention_for("funding_rates") == timedelta(days=730)
    with pytest.raises(ValueError, match="exige timeframe"):
        RetentionPolicy.retention_for("market_candles")
    with pytest.raises(ValueError, match="sem política"):
        RetentionPolicy.retention_for("audit_logs")


def test_retention_sql_and_purge_sql():
    sql = RetentionPolicy.retention_sql("market_trades")
    assert "add_retention_policy('market_trades', INTERVAL '7 days')" in sql
    with pytest.raises(ValueError, match="por timeframe"):
        RetentionPolicy.retention_sql("market_candles")
    sql, params = RetentionPolicy.purge_sql("market_trades", before_ms=T0)
    assert sql.startswith("DELETE FROM market_trades")
    assert params == (T0,)
    sql, params = RetentionPolicy.purge_sql(
        "market_candles", timeframe="1s", before_ms=T0
    )
    assert "timeframe = %s" in sql
    assert params == ("1s", T0)
    sql, params = RetentionPolicy.purge_sql("market_candles", timeframe="1m")
    assert "INTERVAL '730 days'" in sql
    assert params == ("1m",)
    sql, params = RetentionPolicy.export_sql("market_trades", before_ms=T0)
    assert sql.startswith("SELECT * FROM market_trades")
    assert params == (T0,)
