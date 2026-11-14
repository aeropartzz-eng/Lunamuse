"""Testes do Trade Pipeline (DAT-001/002/005/006).

Parsers nativos (Binance/Bybit/OKX), deduplicação, validação
cronológica e métricas. Sem rede.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from market_data import TradePipeline, parse_trade_message
from models import Trade

T0 = 1_793_000_000_000  # ms UTC (2026-11-13)


def binance_trade(trade_id: int, price: str, ts: int, *, maker: bool = False) -> dict:
    return {
        "e": "trade",
        "E": ts,
        "s": "BTCUSDT",
        "t": trade_id,
        "p": price,
        "q": "0.01",
        "T": ts,
        "m": maker,
    }


def test_parse_binance_trade():
    trades = parse_trade_message("binance", binance_trade(1, "90000.5", T0))
    assert len(trades) == 1
    t = trades[0]
    assert isinstance(t, Trade)
    assert (t.exchange, t.symbol) == ("binance", "BTC/USDT")
    assert t.trade_id == "1"
    assert t.price == Decimal("90000.5")
    assert t.quantity == Decimal("0.01")
    assert t.side == "buy"  # m=false: o comprador é o agressor
    assert t.timestamp_ms == T0
    assert t.raw["e"] == "trade"


def test_parse_binance_maker_means_aggressor_sold():
    trades = parse_trade_message(
        "binance", binance_trade(2, "90000.5", T0, maker=True)
    )
    assert trades[0].side == "sell"


def test_parse_binance_json_string_and_non_trade():
    raw = json.dumps(binance_trade(3, "1", T0))
    assert len(parse_trade_message("binance", raw)) == 1
    # Ack de subscribe / pong não é trade: [] sem erro.
    assert parse_trade_message("binance", {"e": "subscribe", "result": None}) == []
    assert parse_trade_message("binance", {"e": "depthUpdate"}) == []


def test_parse_bybit_trades():
    payload = {
        "topic": "publicTrade.BTCUSDT",
        "data": [
            {"i": "a1", "T": T0, "p": "90001", "v": "0.02", "S": "Buy"},
            {"i": "a2", "T": T0 + 1, "p": "90002", "v": "0.03", "S": "Sell"},
        ],
    }
    trades = parse_trade_message("bybit", payload)
    assert len(trades) == 2
    assert trades[0].trade_id == "a1"
    assert trades[0].side == "buy"
    assert trades[1].side == "sell"
    assert all(t.symbol == "BTC/USDT" for t in trades)
    assert parse_trade_message("bybit", {"topic": "orderbook.1.BTCUSDT"}) == []


def test_parse_okx_trades_string_timestamp():
    payload = {
        "arg": {"channel": "trades", "instId": "BTC-USDT"},
        "data": [
            {
                "tradeId": "b1",
                "px": "90003",
                "sz": "0.04",
                "side": "buy",
                "ts": str(T0),
            }
        ],
    }
    trades = parse_trade_message("okx", payload)
    assert len(trades) == 1
    assert trades[0].trade_id == "b1"
    assert trades[0].timestamp_ms == T0
    assert parse_trade_message("okx", {"arg": {"channel": "tickers"}}) == []


def test_parse_unknown_exchange_raises():
    with pytest.raises(ValueError, match="sem parser de trades"):
        parse_trade_message("kraken", {"e": "trade"})


def test_pipeline_dedup_by_trade_id():
    pipeline = TradePipeline("binance")
    msg = binance_trade(10, "90000", T0)
    assert len(pipeline.ingest(msg)) == 1
    assert pipeline.ingest(msg) == []  # duplicata descartada
    assert pipeline.ingest(dict(msg)) == []  # mesmo id, outro objeto
    assert pipeline.metrics.duplicates_dropped == 2
    assert pipeline.metrics.trades_accepted == 1


def test_pipeline_dedup_fallback_without_trade_id():
    # Fonte sem id: o id sintético (ts, preço, qty) dedup igual.
    pipeline = TradePipeline("bybit")
    payload = {
        "topic": "publicTrade.BTCUSDT",
        "data": [{"T": T0, "p": "90000", "v": "0.01", "S": "Buy"}],
    }
    assert len(pipeline.ingest(payload)) == 1
    assert pipeline.ingest(payload) == []
    assert pipeline.metrics.duplicates_dropped == 1


def test_pipeline_rejects_out_of_order():
    pipeline = TradePipeline("binance")
    pipeline.ingest(binance_trade(1, "90000", T0 + 5_000))
    assert pipeline.ingest(binance_trade(2, "90000", T0 + 1_000)) == []
    assert pipeline.metrics.out_of_order_rejected == 1
    assert pipeline.metrics.trades_accepted == 1


def test_pipeline_parse_error_counts_not_crashes():
    pipeline = TradePipeline("binance")
    assert pipeline.ingest("isto não é json") == []
    assert pipeline.ingest({"e": "trade"}) == []  # trade malformado
    assert pipeline.metrics.parse_errors == 2
    # O pipeline continua funcionando depois do erro.
    assert len(pipeline.ingest(binance_trade(1, "1", T0))) == 1


def test_pipeline_notifies_subscribers_only_accepted():
    pipeline = TradePipeline("binance")
    received: list[Trade] = []
    pipeline.subscribe(received.append)
    msg = binance_trade(1, "90000", T0)
    pipeline.ingest(msg)
    pipeline.ingest(msg)  # duplicata: não notifica
    assert len(received) == 1
    assert received[0].trade_id == "1"


def test_pipeline_health():
    pipeline = TradePipeline("binance")
    pipeline.ingest(binance_trade(1, "90000", T0))
    health = pipeline.health()
    assert health["exchange"] == "binance"
    assert health["messages_received"] == 1
    assert health["pipeline"]["trades_accepted"] == 1
    assert health["stale"] is False
