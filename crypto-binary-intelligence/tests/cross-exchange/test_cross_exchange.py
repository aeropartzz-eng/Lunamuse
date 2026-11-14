"""Testes do Cross-Exchange Intelligence (Fase 8 — XCH-001…XCH-005).

Fakes de Ticker; sem rede, sem chave de API, sem execução.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cross_exchange import (
    DEFAULT_TAKER_FEES,
    FeeSchedule,
    canonical_pair,
    detect_divergences,
    equivalent_pairs,
    find_arbitrage_opportunities,
    group_tickers_by_pair,
    reference_price,
    simulate_arbitrage,
)
from models import Ticker

TS = 1_790_985_600_000
D = Decimal


def ticker(exchange, symbol, price, volume=None):
    return Ticker(
        exchange=exchange, symbol=symbol, last=D(str(price)),
        timestamp_ms=TS,
        volume_24h=D(str(volume)) if volume is not None else None,
    )


# -- XCH-001: normalização ----------------------------------------------------


def test_canonical_pair_forms():
    assert canonical_pair("BTC/USDT") == "BTC/USDT"
    assert canonical_pair("BTCUSDT") == "BTC/USDT"
    assert canonical_pair("btc-usdt") == "BTC/USDT"
    assert canonical_pair("BTC_USDT") == "BTC/USDT"
    assert canonical_pair("BTC/USDT:USDT") == "BTC/USDT:USDT"
    assert canonical_pair("BTCUSDT-PERP") == "BTC/USDT:USDT"


def test_canonical_pair_kraken_alias():
    assert canonical_pair("XBT/USD", exchange="kraken") == "BTC/USD"
    assert canonical_pair("XBTUSD", exchange="kraken") == "BTC/USD"


def test_canonical_pair_invalid_raises():
    with pytest.raises(ValueError):
        canonical_pair("BTC")


def test_equivalent_pairs_groups_forms():
    groups = equivalent_pairs(["BTCUSDT", "BTC/USDT", "ETH/USDT"])
    assert groups["BTC/USDT"] == ["BTCUSDT", "BTC/USDT"]
    assert groups["ETH/USDT"] == ["ETH/USDT"]


# -- XCH-002 / XCH-003: comparação e referência -------------------------------


def test_group_tickers_by_pair_across_exchanges():
    tickers = [
        ticker("binance", "BTCUSDT", 100),
        ticker("bybit", "BTC/USDT", 101),
        ticker("kraken", "XBT/USD", 99),
    ]
    groups = group_tickers_by_pair(tickers)
    assert len(groups["BTC/USDT"]) == 2
    assert len(groups["BTC/USD"]) == 1


def test_reference_price_volume_weighted():
    tickers = [
        ticker("binance", "BTC/USDT", 100, volume=900),
        ticker("bybit", "BTC/USDT", 110, volume=100),
    ]
    # quote vol: 900*100=90000 vs 100*110=11000 -> (100*90000+110*11000)/101000
    ref = reference_price(tickers)
    assert ref == (D("100") * D("90000") + D("110") * D("11000")) / D("101000")


def test_reference_price_equal_weight_without_volume():
    tickers = [ticker("binance", "BTC/USDT", 100), ticker("bybit", "BTC/USDT", 110)]
    assert reference_price(tickers) == D("105")


def test_reference_price_empty_is_none():
    assert reference_price([]) is None


# -- XCH-004: divergência ------------------------------------------------------


def test_detect_divergences_flagged_above_threshold():
    tickers = [
        ticker("binance", "BTC/USDT", 100, volume=1000),
        ticker("bybit", "BTC/USDT", 101, volume=1000),
    ]
    divs = detect_divergences(tickers, threshold_bps=D("50"))
    assert len(divs) == 1
    assert divs[0].pair == "BTC/USDT"
    assert divs[0].min_exchange == "binance"
    assert divs[0].max_exchange == "bybit"
    # (101-100)/100.5 * 10000 ≈ 99.5 bps
    assert divs[0].spread_bps > D("50")
    assert divs[0].flagged is True


def test_detect_divergences_not_flagged_below_threshold():
    tickers = [
        ticker("binance", "BTC/USDT", 100),
        ticker("bybit", "BTC/USDT", 100.01),
    ]
    divs = detect_divergences(tickers, threshold_bps=D("50"))
    assert len(divs) == 1
    assert divs[0].flagged is False


def test_detect_divergences_ignores_single_exchange_pair():
    tickers = [ticker("binance", "BTC/USDT", 100)]
    assert detect_divergences(tickers) == []


# -- XCH-005: simulação de arbitragem com custos -------------------------------


def test_arbitrage_viable_when_net_positive():
    sim = simulate_arbitrage(
        pair="BTC/USDT", buy_exchange="binance", sell_exchange="bybit",
        buy_price=D("100"), sell_price=D("102"), quantity=D("1"),
        fees=FeeSchedule(taker_fees={"binance": D("0.001"), "bybit": D("0.001")}),
    )
    # bruto 2.00; taxas 0.10+0.102=0.202; slippage 10bps x2 pernas ~0.202
    assert sim.gross_profit_usd == D("2")
    assert sim.net_profit_usd > 0
    assert sim.viable is True
    assert sim.capital_locked_usd == D("100")


def test_arbitrage_rejected_when_gross_positive_but_net_negative():
    # Divergência de 0,1% é comida pelas taxas + slippage.
    sim = simulate_arbitrage(
        pair="BTC/USDT", buy_exchange="binance", sell_exchange="bybit",
        buy_price=D("100"), sell_price=D("100.10"), quantity=D("1"),
        fees=FeeSchedule(taker_fees={"binance": D("0.001"), "bybit": D("0.001")}),
    )
    assert sim.gross_profit_usd == D("0.10")
    assert sim.net_profit_usd < 0
    assert sim.viable is False
    assert "líquido negativo" in sim.reason


def test_arbitrage_rejected_when_no_divergence():
    sim = simulate_arbitrage(
        pair="BTC/USDT", buy_exchange="binance", sell_exchange="bybit",
        buy_price=D("102"), sell_price=D("100"), quantity=D("1"),
    )
    assert sim.viable is False
    assert sim.gross_profit_usd < 0


def test_arbitrage_transfer_fee_can_kill_it():
    sim = simulate_arbitrage(
        pair="BTC/USDT", buy_exchange="binance", sell_exchange="bybit",
        buy_price=D("100"), sell_price=D("102"), quantity=D("1"),
        fees=FeeSchedule(
            taker_fees={"binance": D("0.001"), "bybit": D("0.001")},
            transfer_fee_usd=D("5"),
        ),
    )
    assert sim.viable is False
    assert sim.transfer_fee_usd == D("5")


def test_arbitrage_min_net_bps_threshold():
    sim = simulate_arbitrage(
        pair="BTC/USDT", buy_exchange="binance", sell_exchange="bybit",
        buy_price=D("100"), sell_price=D("102"), quantity=D("1"),
        fees=FeeSchedule(
            taker_fees={"binance": D("0.001"), "bybit": D("0.001")},
            min_net_bps=D("500"),  # exige 5% líquido
        ),
    )
    assert sim.viable is False
    assert "mínimo exigido" in sim.reason


def test_arbitrage_invalid_inputs_raise():
    with pytest.raises(ValueError):
        simulate_arbitrage(
            "BTC/USDT", "binance", "bybit", D("0"), D("100"), D("1"),
        )


def test_find_arbitrage_opportunities_cheapest_to_dearest():
    tickers = [
        ticker("binance", "BTC/USDT", 100, volume=1000),
        ticker("bybit", "BTC/USDT", 102, volume=1000),
        ticker("okx", "BTC/USDT", 101, volume=1000),
        ticker("binance", "ETH/USDT", 50, volume=1000),  # só 1 exchange
    ]
    sims = find_arbitrage_opportunities(
        tickers, D("1"),
        fees=FeeSchedule(taker_fees={k: D("0.001") for k in DEFAULT_TAKER_FEES}),
    )
    assert len(sims) == 1
    assert sims[0].buy_exchange == "binance"
    assert sims[0].sell_exchange == "bybit"
    assert sims[0].pair == "BTC/USDT"


def test_default_taker_fees_documented_per_exchange():
    assert DEFAULT_TAKER_FEES["binance"] == D("0.001")
    assert DEFAULT_TAKER_FEES["coinbase"] > DEFAULT_TAKER_FEES["binance"]
