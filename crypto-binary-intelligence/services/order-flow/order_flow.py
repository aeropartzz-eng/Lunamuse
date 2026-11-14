"""Order Flow Engine — Volume Delta, CVD, Imbalance, absorção,
exaustão, Liquidity Sweep, profundidade, spread e slippage
(Fase 10 — FLOW-001…FLOW-005).

Regras objetivas sobre :class:`Trade` e :class:`OrderBook` (contrato
universal, Fase 3) e sobre :class:`Candle`. Nenhuma rede, nenhuma
chave, nenhum envio de ordem.

FOOTPRINT: indisponível nesta fase. O footprint exige volume de
compra/venda agressivo **por nível de preço** dentro de cada candle,
dado que os conectores atuais não fornecem (só trades agregados por
lado e snapshots de book). :func:`build_footprint` levanta
``NotImplementedError`` documentando o dado que falta — nada é
inventado aqui. Ver README do serviço.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional

try:
    from models import Candle, OrderBook, Trade
except ImportError:  # diretório services/exchange-connectors fora do sys.path
    sys.path.append(
        str(Path(__file__).resolve().parents[1] / "exchange-connectors")
    )
    from models import Candle, OrderBook, Trade

# Thresholds (ver README):
IMBALANCE_STRONG = 0.30        # |imbalance| >= 0,30 -> lado dominante
ABSORPTION_MIN_ONE_SIDED = 0.60  # >= 60% do volume agressivo num só lado
ABSORPTION_MAX_MOVE_ATR = 0.20   # e o preço se move <= 0,2 ATR
EXHAUSTION_VOL_MIN = 2.0         # volume >= 2x a média
EXHAUSTION_WICK_MIN = 0.50       # pavio >= 50% do range do candle

FOOTPRINT_AVAILABLE = False


def _f(value: Decimal) -> float:
    return float(value)


# --- FLOW-001: Volume Delta ---------------------------------------------------

@dataclass(frozen=True)
class VolumeDelta:
    """Volume agressivo por lado em um conjunto de trades."""

    buy_volume: Decimal
    sell_volume: Decimal
    delta: Decimal  # buy - sell
    total_volume: Decimal
    buy_ratio: float  # buy / total (0..1), 0 se total == 0

    @property
    def dominant_side(self) -> Optional[str]:
        if self.total_volume == 0:
            return None
        return "buy" if self.delta > 0 else ("sell" if self.delta < 0 else None)


def volume_delta(trades: list[Trade]) -> VolumeDelta:
    """Soma o volume agressivo de compra e de venda (FLOW-001)."""
    buy = sum((t.quantity for t in trades if t.side == "buy"), Decimal("0"))
    sell = sum((t.quantity for t in trades if t.side == "sell"), Decimal("0"))
    total = buy + sell
    ratio = float(buy / total) if total > 0 else 0.0
    return VolumeDelta(buy_volume=buy, sell_volume=sell, delta=buy - sell,
                       total_volume=total, buy_ratio=round(ratio, 4))


# --- FLOW-002: CVD ------------------------------------------------------------

@dataclass(frozen=True)
class CVDPoint:
    """Um ponto da curva de CVD: CVD acumulado após um trade."""

    timestamp_ms: int
    cvd: Decimal
    delta: Decimal  # delta deste trade (+qty buy, -qty sell)


def cumulative_cvd(trades: list[Trade]) -> list[CVDPoint]:
    """CVD cumulativo (FLOW-002): soma corrente de +qty (buy) / -qty (sell).

    Os trades devem chegar em ordem cronológica; a função não reordena
    (a ordenação é responsabilidade da ingestão, Fase 7).
    """
    points: list[CVDPoint] = []
    running = Decimal("0")
    for t in trades:
        step = t.quantity if t.side == "buy" else -t.quantity
        running += step
        points.append(CVDPoint(timestamp_ms=t.timestamp_ms, cvd=running,
                               delta=step))
    return points


def final_cvd(trades: list[Trade]) -> Decimal:
    """CVD final de uma sequência de trades (== delta total)."""
    points = cumulative_cvd(trades)
    return points[-1].cvd if points else Decimal("0")


# --- FLOW-003: Order Book Imbalance -------------------------------------------

@dataclass(frozen=True)
class BookImbalance:
    """Imbalance do book nos N primeiros níveis de cada lado."""

    bid_qty: Decimal
    ask_qty: Decimal
    imbalance: float  # (bid-ask)/(bid+ask), em [-1, 1]; 0 se vazio
    levels: int
    dominant_side: Optional[str]  # "bid" | "ask" | None
    strong: bool  # |imbalance| >= IMBALANCE_STRONG


def book_imbalance(book: OrderBook, levels: int = 5) -> BookImbalance:
    """Bid/Ask Imbalance (FLOW-003) nos `levels` primeiros níveis."""
    bids = book.bids[:levels]
    asks = book.asks[:levels]
    bid_qty = sum((q for _, q in bids), Decimal("0"))
    ask_qty = sum((q for _, q in asks), Decimal("0"))
    total = bid_qty + ask_qty
    if total == 0:
        imbalance = 0.0
    else:
        imbalance = float((bid_qty - ask_qty) / total)
    dominant = None
    if imbalance > 0:
        dominant = "bid"
    elif imbalance < 0:
        dominant = "ask"
    return BookImbalance(
        bid_qty=bid_qty, ask_qty=ask_qty,
        imbalance=round(imbalance, 4), levels=levels,
        dominant_side=dominant,
        strong=abs(imbalance) >= IMBALANCE_STRONG)


@dataclass(frozen=True)
class DepthChange:
    """Mudança de profundidade entre dois snapshots do book."""

    bid_qty_delta: Decimal
    ask_qty_delta: Decimal
    total_qty_delta: Decimal
    levels: int
    bid_change_pct: Optional[float]
    ask_change_pct: Optional[float]


def depth_change(previous: OrderBook, current: OrderBook,
                 levels: int = 5) -> DepthChange:
    """Mudança de profundidade (FLOW-003): variação de qty por lado."""
    def _qty(book: OrderBook, side: str) -> Decimal:
        rows = book.bids[:levels] if side == "bid" else book.asks[:levels]
        return sum((q for _, q in rows), Decimal("0"))

    prev_bid, prev_ask = _qty(previous, "bid"), _qty(previous, "ask")
    cur_bid, cur_ask = _qty(current, "bid"), _qty(current, "ask")
    bid_delta, ask_delta = cur_bid - prev_bid, cur_ask - prev_ask

    def _pct(delta: Decimal, base: Decimal) -> Optional[float]:
        return round(float(delta / base), 4) if base > 0 else None

    return DepthChange(
        bid_qty_delta=bid_delta, ask_qty_delta=ask_delta,
        total_qty_delta=bid_delta + ask_delta, levels=levels,
        bid_change_pct=_pct(bid_delta, prev_bid),
        ask_change_pct=_pct(ask_delta, prev_ask))


# --- Spread e slippage estimado ------------------------------------------------

def spread_bps(book: OrderBook) -> Optional[float]:
    """Spread em basis points sobre o mid price. None se book vazio."""
    if book.spread is None or book.mid_price is None or book.mid_price == 0:
        return None
    return round(float(book.spread / book.mid_price) * 10_000, 3)


@dataclass(frozen=True)
class SlippageEstimate:
    """Slippage estimado ao executar `quantity` contra o book."""

    side: str
    quantity: Decimal
    filled_quantity: Decimal
    avg_fill_price: Optional[Decimal]
    mid_price: Optional[Decimal]
    slippage_bps: Optional[float]  # vs mid; None se nada foi preenchido
    fully_filled: bool


def estimated_slippage(book: OrderBook, side: str,
                       quantity: Decimal) -> SlippageEstimate:
    """Slippage estimado (FLOW-005, apoio): percorre o book e calcula o
    preço médio de execução contra o mid price.

    Compra consome asks (do menor preço); venda consome bids (do maior).
    Não envia ordem: é só simulação sobre o snapshot.
    """
    if side not in ("buy", "sell"):
        raise ValueError(f"side inválido: {side!r}")
    if quantity <= 0:
        raise ValueError("quantity deve ser > 0")
    rows = book.asks if side == "buy" else book.bids
    remaining = quantity
    filled = Decimal("0")
    notional = Decimal("0")
    for price, qty in rows:
        if remaining <= 0:
            break
        take = min(qty, remaining)
        filled += take
        notional += take * price
        remaining -= take
    mid = book.mid_price
    if filled == 0 or mid is None or mid == 0:
        return SlippageEstimate(side=side, quantity=quantity,
                                filled_quantity=filled, avg_fill_price=None,
                                mid_price=mid, slippage_bps=None,
                                fully_filled=False)
    avg = notional / filled
    if side == "buy":
        slip = float((avg - mid) / mid) * 10_000
    else:
        slip = float((mid - avg) / mid) * 10_000
    return SlippageEstimate(
        side=side, quantity=quantity, filled_quantity=filled,
        avg_fill_price=avg, mid_price=mid,
        slippage_bps=round(slip, 3), fully_filled=remaining == 0)


# --- FLOW-004: absorção e exaustão ---------------------------------------------

@dataclass(frozen=True)
class AbsorptionEvent:
    """Absorção: volume agressivo concentrado num lado sem deslocar o
    preço — alguém absorveu a agressão no lado oposto."""

    absorbed_side: str  # lado agressor absorvido ("buy" | "sell")
    delta: Decimal
    total_volume: Decimal
    one_sided_ratio: float
    price_move: float
    atr: float
    index: Optional[int] = None


def detect_absorption(trades: list[Trade], start_price: float,
                      end_price: float, atr: float,
                      index: Optional[int] = None) -> Optional[AbsorptionEvent]:
    """Absorção (FLOW-004) sobre uma janela de trades.

    Regra: >= 60% do volume agressivo num só lado E deslocamento de
    preço <= 0,2 ATR no período. Se `atr` <= 0, usa o deslocamento
    absoluto de preço como referência (<= 0,05% do preço inicial).
    """
    vd = volume_delta(trades)
    if vd.total_volume == 0:
        return None
    one_sided = max(vd.buy_volume, vd.sell_volume) / vd.total_volume
    if float(one_sided) < ABSORPTION_MIN_ONE_SIDED:
        return None
    move = abs(end_price - start_price)
    if atr > 0:
        moved = move <= ABSORPTION_MAX_MOVE_ATR * atr
    else:
        moved = move <= 0.0005 * start_price if start_price > 0 else move == 0
    if not moved:
        return None
    side = "buy" if vd.delta > 0 else "sell"
    return AbsorptionEvent(
        absorbed_side=side, delta=vd.delta, total_volume=vd.total_volume,
        one_sided_ratio=round(float(one_sided), 4),
        price_move=round(move, 6), atr=atr, index=index)


@dataclass(frozen=True)
class ExhaustionEvent:
    """Exaustão: volume em climax (>= 2x a média) com pavio longo e
    fechamento revertido — a agressão se esgotou no extremo."""

    direction: str  # lado que se exauriu ("bullish" = exaustão vendedora)
    index: int
    volume_ratio: float
    wick_ratio: float
    details: dict = field(default_factory=dict)


def detect_exhaustion(candle: Candle, avg_volume: Decimal,
                      index: int) -> Optional[ExhaustionEvent]:
    """Exaustão (FLOW-004) em um candle.

    Regra: volume >= 2x a média E pavio >= 50% do range E fechamento no
    lado oposto ao pavio (reversão). Pavio superior longo + fechamento
    na metade inferior -> exaustão compradora (bearish); espelho para
    a exaustão vendedora (bullish).
    """
    if avg_volume <= 0:
        return None
    vol_ratio = float(candle.volume / avg_volume)
    if vol_ratio < EXHAUSTION_VOL_MIN:
        return None
    o, h, l, cl = (_f(candle.open), _f(candle.high), _f(candle.low),
                   _f(candle.close))
    rng = h - l
    if rng <= 0:
        return None
    upper = h - max(o, cl)
    lower = min(o, cl) - l
    mid = (h + l) / 2
    if upper >= EXHAUSTION_WICK_MIN * rng and cl < mid:
        return ExhaustionEvent(direction="bearish", index=index,
                               volume_ratio=round(vol_ratio, 3),
                               wick_ratio=round(upper / rng, 3),
                               details={"wick": "upper"})
    if lower >= EXHAUSTION_WICK_MIN * rng and cl > mid:
        return ExhaustionEvent(direction="bullish", index=index,
                               volume_ratio=round(vol_ratio, 3),
                               wick_ratio=round(lower / rng, 3),
                               details={"wick": "lower"})
    return None


# --- FLOW-005: Liquidity Sweep (order flow) --------------------------------------

@dataclass(frozen=True)
class LiquiditySweep:
    """Liquidity Sweep: o preço varre um nível (máxima/mínima) com o
    pavio e fecha de volta para dentro — no candle ou no seguinte."""

    direction: str  # direção da reversão após o sweep ("bullish"|"bearish")
    index: int
    level: float
    wick_beyond: float


def detect_liquidity_sweep(candles: list[Candle], level: float,
                           direction: str) -> list[LiquiditySweep]:
    """Liquidity Sweep (FLOW-005) sobre um nível dado.

    `direction="bullish"`: varredura da mínima (abaixo do nível) com
    fechamento acima dele. `direction="bearish"`: varredura da máxima
    com fechamento abaixo. O fechamento de volta pode ser no mesmo
    candle ou no candle seguinte.
    """
    if direction not in ("bullish", "bearish"):
        raise ValueError(f"direction inválido: {direction!r}")
    sweeps: list[LiquiditySweep] = []
    for i, c in enumerate(candles):
        if direction == "bullish":
            if _f(c.low) < level:
                closed_back = _f(c.close) > level or (
                    i + 1 < len(candles) and _f(candles[i + 1].close) > level)
                if closed_back:
                    sweeps.append(LiquiditySweep(
                        direction="bullish", index=i, level=level,
                        wick_beyond=round(level - _f(c.low), 6)))
        else:
            if _f(c.high) > level:
                closed_back = _f(c.close) < level or (
                    i + 1 < len(candles) and _f(candles[i + 1].close) < level)
                if closed_back:
                    sweeps.append(LiquiditySweep(
                        direction="bearish", index=i, level=level,
                        wick_beyond=round(_f(c.high) - level, 6)))
    return sweeps


# --- Footprint: indisponível ------------------------------------------------------

def footprint_status() -> dict:
    """Por que o footprint não existe nesta fase (FLOW, §6).

    O footprint precisa, por nível de preço dentro de cada candle, do
    volume agressivo de compra e de venda separadamente. Os conectores
    atuais entregam trades (lado do agressor) e snapshots de book, mas
    não a agregação por preço por candle — sem esse dado, qualquer
    footprint seria inventado. Quando o market-data passar a agregar
    trades por preço, esta função passa a construir o footprint.
    """
    return {
        "available": False,
        "reason": "Falta agregação de trades por nível de preço dentro "
                  "do candle (volume bid/ask por preço).",
        "required_data": "trades com preço e lado do agressor, "
                         "agregados por preço por candle",
        "current_data": "trades individuais + snapshots de book "
                        "(sem agregação por preço por candle)",
    }


def build_footprint(*args, **kwargs):
    """Footprint — INDISPONÍVEL (ver :func:`footprint_status`)."""
    raise NotImplementedError(
        "Footprint indisponível: falta agregação de trades por nível de "
        "preço dentro do candle (ver footprint_status()). Nada é "
        "inventado no lugar do dado que não existe.")


__all__ = [
    "VolumeDelta", "CVDPoint", "BookImbalance", "DepthChange",
    "SlippageEstimate", "AbsorptionEvent", "ExhaustionEvent",
    "LiquiditySweep",
    "volume_delta", "cumulative_cvd", "final_cvd",
    "book_imbalance", "depth_change", "spread_bps", "estimated_slippage",
    "detect_absorption", "detect_exhaustion", "detect_liquidity_sweep",
    "footprint_status", "build_footprint", "FOOTPRINT_AVAILABLE",
]
