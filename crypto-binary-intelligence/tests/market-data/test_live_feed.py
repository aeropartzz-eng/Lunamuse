"""Testes do LiveTradeFeed (DAT-001) com websocket fake.

Sem rede: o transporte é injetado via ``connect_fn`` e o loop é
executado com ``asyncio.run`` (sem pytest-asyncio).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from market_data import LiveTradeFeed, TradePipeline

T0 = 1_793_000_000_000  # ms UTC (2026-11-13)


def binance_msg(trade_id: int, ts: int) -> str:
    return json.dumps(
        {
            "e": "trade",
            "s": "BTCUSDT",
            "t": trade_id,
            "p": "90000",
            "q": "0.01",
            "T": ts,
            "m": False,
        }
    )


class FakeWS:
    """WebSocket fake: itera mensagens fixas, registra sends."""

    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)
        self.sent: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


def test_feed_ingests_trades_from_fake_ws():
    pipeline = TradePipeline("binance")
    received: list = []
    pipeline.subscribe(received.append)
    ws = FakeWS(
        [binance_msg(1, T0), binance_msg(2, T0 + 1), binance_msg(3, T0 + 2)]
    )

    async def connect_fn(url, **kwargs):
        assert url == "wss://stream.binance.com:9443/ws/btcusdt@trade"
        return ws

    feed = LiveTradeFeed(
        "binance", "BTC/USDT", pipeline,
        max_messages=3, connect_fn=connect_fn,
    )
    stats = asyncio.run(feed.run())
    assert stats["messages_received"] == 3
    assert stats["trades_accepted"] == 3
    assert len(received) == 3
    assert received[0].trade_id == "1"
    assert ws.closed is True
    # Binance assina pela URL: nenhuma mensagem de subscribe.
    assert ws.sent == []


def test_feed_sends_subscribe_for_bybit():
    pipeline = TradePipeline("bybit")
    ws = FakeWS(
        [
            json.dumps(
                {
                    "topic": "publicTrade.BTCUSDT",
                    "data": [
                        {"i": "x1", "T": T0, "p": "90000", "v": "0.01", "S": "Buy"}
                    ],
                }
            )
        ]
    )

    async def connect_fn(url, **kwargs):
        assert url == "wss://stream.bybit.com/v5/public/spot"
        return ws

    feed = LiveTradeFeed(
        "bybit", "BTC/USDT", pipeline, max_messages=1, connect_fn=connect_fn
    )
    stats = asyncio.run(feed.run())
    assert stats["trades_accepted"] == 1
    assert len(ws.sent) == 1
    assert json.loads(ws.sent[0]) == {
        "op": "subscribe",
        "args": ["publicTrade.BTCUSDT"],
    }


def test_feed_reconnects_after_connect_failure():
    pipeline = TradePipeline("binance")
    attempts = {"n": 0}
    ws = FakeWS([binance_msg(1, T0)])

    async def connect_fn(url, **kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ConnectionError("queda simulada")
        return ws

    feed = LiveTradeFeed(
        "binance", "BTC/USDT", pipeline,
        max_messages=1, max_reconnects=3, connect_fn=connect_fn,
    )
    stats = asyncio.run(feed.run())
    assert stats["trades_accepted"] == 1
    assert stats["reconnects"] == 1
    assert attempts["n"] == 2


def test_feed_rejects_unknown_exchange():
    pipeline = TradePipeline("kraken")
    with pytest.raises(ValueError, match="sem feed de trades"):
        LiveTradeFeed("kraken", "BTC/USDT", pipeline)
