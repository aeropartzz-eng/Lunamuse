"""Market Structure — suporte/resistência, tendência, BOS/CHoCH, FVG,
Order Blocks e Fibonacci (Fase 10 — PAT-007).

Tudo aqui é regra objetiva e testável sobre :class:`Candle`. Conceitos
ICT/SMC e Wyckoff entram apenas quando convertidos em regra (§6):
- **BOS / CHoCH**: fechamento além do último swing high/low confirmado.
- **Liquidity Sweep**: pavio além de um swing/nível com fechamento de
  volta para dentro.
- **FVG**: gap entre a máxima do candle i-2 e a mínima do candle i
  (alta) ou inversa (baixa).
- **Order Block**: último candle de cor oposta antes do candle do BOS.
- **Wyckoff**: NÃO implementado como conceito — Spring/SOS/UTAD não
  têm regra objetiva sem volume de mercado + contexto de acumulação;
  o que existe de testável (sweep + BOS + reteste) está nas funções
  abaixo. Ver README.
- **Harmônicos**: fora desta fase (exigem razões de Fibonacci entre
  pernas com tolerâncias próprias; não há tarefa PAT para eles).

Nenhuma rede, nenhuma chave, nenhum envio de ordem.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional

try:
    from models import Candle
except ImportError:  # diretório services/exchange-connectors fora do sys.path
    sys.path.append(
        str(Path(__file__).resolve().parents[1] / "exchange-connectors")
    )
    from models import Candle

# Pivôs: um swing precisa ser o extremo estrito de uma janela de
# `PIVOT_LEFT + 1 + PIVOT_RIGHT` candles (padrão 2+1+2).
PIVOT_LEFT = 2
PIVOT_RIGHT = 2
# Tolerância padrão para agrupar níveis de S/R e para reteste/sweep:
# 0,5% do preço.
LEVEL_TOL_PCT = 0.005
# Retração de pullback considerada válida: entre 38,2% e 78,6% da perna.
PULLBACK_MIN = 0.382
PULLBACK_MAX = 0.786
# Reteste precisa acontecer em até N candles após o breakout.
RETEST_MAX_BARS = 5

FIB_RETRACEMENT = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
FIB_EXTENSION = (1.272, 1.618, 2.618)


def _f(value: Decimal) -> float:
    return float(value)


@dataclass(frozen=True)
class Swing:
    """Um topo ou fundo (pivô confirmado)."""

    index: int
    price: float
    kind: str  # "high" | "low"


@dataclass(frozen=True)
class Level:
    """Nível de suporte/resistência: preço, toques e tipo."""

    price: float
    touches: int
    kind: str  # "support" | "resistance"


@dataclass(frozen=True)
class StructureEvent:
    """Um evento de estrutura: BOS, CHoCH, breakout, reteste, pullback,
    liquidity sweep. ``direction`` é a direção do evento."""

    kind: str  # "bos" | "choch" | "breakout" | "retest" | "pullback" | "sweep"
    direction: str  # "bullish" | "bearish"
    index: int
    level: float
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FairValueGap:
    """Fair Value Gap (FVG): zona entre dois candles com gap de preço."""

    index: int  # índice do terceiro candle (o que abre o gap)
    direction: str  # "bullish" | "bearish"
    top: float
    bottom: float
    filled: bool = False
    filled_index: Optional[int] = None


@dataclass(frozen=True)
class OrderBlock:
    """Order Block objetivo: último candle de cor oposta antes do BOS."""

    index: int  # índice do candle do order block
    bos_index: int
    direction: str  # "bullish" | "bearish"
    top: float
    bottom: float


# --- Swings ----------------------------------------------------------------

def find_swings(candles: list[Candle], left: int = PIVOT_LEFT,
                right: int = PIVOT_RIGHT) -> list[Swing]:
    """Topos e fundos: extremo estrito na janela [i-left, i+right]."""
    swings: list[Swing] = []
    n = len(candles)
    for i in range(left, n - right):
        highs = [_f(candles[j].high) for j in range(i - left, i + right + 1)]
        lows = [_f(candles[j].low) for j in range(i - left, i + right + 1)]
        hi, lo = _f(candles[i].high), _f(candles[i].low)
        if hi > max(h for j, h in enumerate(highs) if j != left):
            swings.append(Swing(index=i, price=hi, kind="high"))
        if lo < min(v for j, v in enumerate(lows) if j != left):
            swings.append(Swing(index=i, price=lo, kind="low"))
    swings.sort(key=lambda s: s.index)
    return swings


def classify_trend(candles: list[Candle]) -> dict:
    """Classifica a tendência a partir dos swings (HH/HL, LH/LL).

    - >= 2 topos e >= 2 fundos: HH+HL -> "uptrend"; LH+LL -> "downtrend";
      misturado -> "sideways".
    - Sem swings suficientes: compara primeiro/último close; variação
      <= 0,5% -> "sideways", senão a direção do movimento.
    """
    swings = find_swings(candles)
    highs = [s for s in swings if s.kind == "high"]
    lows = [s for s in swings if s.kind == "low"]
    result: dict = {
        "trend": "sideways",
        "swing_highs": [s.price for s in highs],
        "swing_lows": [s.price for s in lows],
        "higher_highs": None,
        "higher_lows": None,
    }
    if len(highs) >= 2 and len(lows) >= 2:
        hh = all(highs[i].price > highs[i - 1].price for i in range(1, len(highs)))
        hl = all(lows[i].price > lows[i - 1].price for i in range(1, len(lows)))
        ll = all(lows[i].price < lows[i - 1].price for i in range(1, len(lows)))
        lh = all(highs[i].price < highs[i - 1].price for i in range(1, len(highs)))
        result["higher_highs"] = hh
        result["higher_lows"] = hl
        result["lower_highs"] = lh
        result["lower_lows"] = ll
        if hh and hl:
            result["trend"] = "uptrend"
        elif lh and ll:
            result["trend"] = "downtrend"
        return result
    if len(candles) >= 2:
        start, end = _f(candles[0].close), _f(candles[-1].close)
        if start > 0:
            change = (end - start) / start
            if change > 0.005:
                result["trend"] = "uptrend"
            elif change < -0.005:
                result["trend"] = "downtrend"
    return result


# --- Suporte / resistência --------------------------------------------------

def find_levels(candles: list[Candle], min_touches: int = 2,
                tol_pct: float = LEVEL_TOL_PCT) -> list[Level]:
    """Suporte/resistência: agrupa preços de swings próximos.

    Um nível precisa de ao menos `min_touches` toques (swings no mesmo
    agrupamento). O preço do nível é a média dos toques.
    """
    swings = find_swings(candles)
    if not swings:
        return []
    ordered = sorted(swings, key=lambda s: s.price)
    groups: list[list[Swing]] = []
    for s in ordered:
        if groups and abs(s.price - groups[-1][0].price) <= tol_pct * s.price:
            groups[-1].append(s)
        else:
            groups.append([s])
    levels: list[Level] = []
    for group in groups:
        if len(group) < min_touches:
            continue
        price = sum(s.price for s in group) / len(group)
        kinds = {s.kind for s in group}
        kind = "support" if kinds == {"low"} else (
            "resistance" if kinds == {"high"} else "support")
        # Grupo misto (topos e fundos no mesmo preço): classifica pelo
        # tipo majoritário; empates viram "support" por convenção.
        if len(kinds) > 1:
            n_low = sum(1 for s in group if s.kind == "low")
            kind = "support" if n_low * 2 >= len(group) else "resistance"
        levels.append(Level(price=round(price, 6), touches=len(group), kind=kind))
    levels.sort(key=lambda lv: lv.price)
    return levels


# --- BOS / CHoCH ------------------------------------------------------------

def detect_bos_choch(candles: list[Candle]) -> list[StructureEvent]:
    """BOS e CHoCH a partir de fechamentos além de swings confirmados.

    Regra: um pivô só vira estrutura depois de confirmado (índice do
    pivô + PIVOT_RIGHT). A partir daí, o primeiro fechamento além do
    último swing high/low gera o evento:
    - Fechamento acima do swing high, tendência de alta ou indefinida
      -> BOS de alta; tendência de baixa -> CHoCH de alta (muda o
      caráter da estrutura).
    - Fechamento abaixo do swing low: espelho.
    Após o evento, a tendência passa a ser a direção do evento.
    """
    swings = find_swings(candles)
    if not swings:
        return []
    events: list[StructureEvent] = []
    trend: Optional[str] = None  # "up" | "down"
    last_high: Optional[float] = None
    last_low: Optional[float] = None
    # Confirmação de pivôs em ordem; varre os candles após cada pivô.
    confirmed_until = -1
    for swing in swings:
        confirm_idx = swing.index + PIVOT_RIGHT
        if confirm_idx >= len(candles):
            break
        if swing.kind == "high":
            last_high = swing.price
        else:
            last_low = swing.price
        for i in range(max(confirmed_until + 1, confirm_idx), len(candles)):
            close = _f(candles[i].close)
            if last_high is not None and close > last_high:
                kind = "bos" if trend in ("up", None) else "choch"
                events.append(StructureEvent(
                    kind=kind, direction="bullish", index=i, level=last_high,
                    details={"broken": "swing_high"}))
                trend = "up"
                last_high = None  # nível rompido; aguarda novo swing high
                break
            if last_low is not None and close < last_low:
                kind = "bos" if trend in ("down", None) else "choch"
                events.append(StructureEvent(
                    kind=kind, direction="bearish", index=i, level=last_low,
                    details={"broken": "swing_low"}))
                trend = "down"
                last_low = None
                break
        confirmed_until = max(confirmed_until, confirm_idx)
    return events


# --- Breakout e reteste ------------------------------------------------------

def detect_breakout_retest(candles: list[Candle],
                           levels: list[Level],
                           tol_pct: float = LEVEL_TOL_PCT,
                           retest_max_bars: int = RETEST_MAX_BARS
                           ) -> list[StructureEvent]:
    """Breakout (fechamento além do nível) e reteste (retorno ao nível
    sem fechar de volta para o outro lado, em até `retest_max_bars`
    candles após o breakout)."""
    events: list[StructureEvent] = []
    for level in levels:
        price = level.price
        tol = tol_pct * price
        for i, c in enumerate(candles):
            close, prev_close = _f(c.close), _f(candles[i - 1].close) if i else None
            if prev_close is None:
                continue
            direction = None
            if prev_close <= price and close > price:
                direction = "bullish"
            elif prev_close >= price and close < price:
                direction = "bearish"
            if direction is None:
                continue
            events.append(StructureEvent(
                kind="breakout", direction=direction, index=i, level=price,
                details={"level_kind": level.kind}))
            # Reteste: nos próximos candles, o preço toca o nível (pavio
            # ou corpo) e fecha do lado do breakout.
            for j in range(i + 1, min(len(candles), i + 1 + retest_max_bars)):
                cj = candles[j]
                touched = _f(cj.low) <= price + tol and _f(cj.high) >= price - tol
                held = (_f(cj.close) > price) if direction == "bullish" \
                    else (_f(cj.close) < price)
                if touched and held:
                    events.append(StructureEvent(
                        kind="retest", direction=direction, index=j, level=price,
                        details={"breakout_index": i}))
                    break
            break  # só o primeiro breakout por nível
    events.sort(key=lambda e: e.index)
    return events


# --- Pullback -----------------------------------------------------------------

def detect_pullbacks(candles: list[Candle]) -> list[StructureEvent]:
    """Pullback: após uma perna de impulso (swing low -> swing high em
    tendência de alta, ou inverso), o preço retrai entre 38,2% e 78,6%
    da perna sem romper o swing de origem."""
    swings = find_swings(candles)
    events: list[StructureEvent] = []
    for a, b in zip(swings, swings[1:]):
        if a.kind == b.kind:
            continue
        if a.kind == "low" and b.kind == "high":
            # Perna de alta; procura a mínima após o topo.
            leg = b.price - a.price
            if leg <= 0:
                continue
            for j in range(b.index + 1, len(candles)):
                low = _f(candles[j].low)
                if low <= a.price:
                    break  # rompeu a origem: não é pullback
                depth = (b.price - low) / leg
                if PULLBACK_MIN <= depth <= PULLBACK_MAX:
                    events.append(StructureEvent(
                        kind="pullback", direction="bullish", index=j,
                        level=round(low, 6),
                        details={"retracement": round(depth, 3),
                                 "leg_start": a.price, "leg_end": b.price}))
                    break
        elif a.kind == "high" and b.kind == "low":
            leg = a.price - b.price
            if leg <= 0:
                continue
            for j in range(b.index + 1, len(candles)):
                high = _f(candles[j].high)
                if high >= a.price:
                    break
                depth = (high - b.price) / leg
                if PULLBACK_MIN <= depth <= PULLBACK_MAX:
                    events.append(StructureEvent(
                        kind="pullback", direction="bearish", index=j,
                        level=round(high, 6),
                        details={"retracement": round(depth, 3),
                                 "leg_start": a.price, "leg_end": b.price}))
                    break
    return events


# --- Liquidity Sweep -----------------------------------------------------------

def detect_liquidity_sweeps(candles: list[Candle],
                            tol_pct: float = LEVEL_TOL_PCT
                            ) -> list[StructureEvent]:
    """Liquidity Sweep: pavio além de um swing high/low (ou nível) com
    fechamento de volta para dentro — a liquidez acima/abaixo foi
    varrida e rejeitada no mesmo candle."""
    swings = find_swings(candles)
    events: list[StructureEvent] = []
    seen: set[tuple[str, int]] = set()
    for swing in swings:
        level = swing.price
        for i in range(swing.index + 1, len(candles)):
            c = candles[i]
            if swing.kind == "high":
                if _f(c.high) > level and _f(c.close) < level:
                    key = ("sweep_high", i)
                    if key not in seen:
                        seen.add(key)
                        events.append(StructureEvent(
                            kind="sweep", direction="bearish", index=i,
                            level=level,
                            details={"wick_beyond": round(
                                _f(c.high) - level, 6),
                                "swept": "swing_high"}))
                    break
                if _f(c.close) > level:
                    break  # rompeu de verdade: não é sweep
            else:
                if _f(c.low) < level and _f(c.close) > level:
                    key = ("sweep_low", i)
                    if key not in seen:
                        seen.add(key)
                        events.append(StructureEvent(
                            kind="sweep", direction="bullish", index=i,
                            level=level,
                            details={"wick_beyond": round(
                                level - _f(c.low), 6),
                                "swept": "swing_low"}))
                    break
                if _f(c.close) < level:
                    break
    events.sort(key=lambda e: e.index)
    return events


# --- FVG -----------------------------------------------------------------------

def detect_fvg(candles: list[Candle]) -> list[FairValueGap]:
    """Fair Value Gap: gap entre a máxima do candle i-2 e a mínima do
    candle i (alta) ou entre a mínima de i-2 e a máxima de i (baixa).
    Um FVG é marcado como preenchido quando um candle posterior fecha
    além da borda oposta da zona."""
    gaps: list[FairValueGap] = []
    for i in range(2, len(candles)):
        c0, c2 = candles[i - 2], candles[i]
        if _f(c2.low) > _f(c0.high):
            gaps.append(FairValueGap(index=i, direction="bullish",
                                     top=_f(c2.low), bottom=_f(c0.high)))
        elif _f(c2.high) < _f(c0.low):
            gaps.append(FairValueGap(index=i, direction="bearish",
                                     top=_f(c0.low), bottom=_f(c2.high)))
    filled: list[FairValueGap] = []
    for gap in gaps:
        filled_index = None
        for j in range(gap.index + 1, len(candles)):
            close = _f(candles[j].close)
            if gap.direction == "bullish" and close < gap.bottom:
                filled_index = j
                break
            if gap.direction == "bearish" and close > gap.top:
                filled_index = j
                break
        filled.append(FairValueGap(
            index=gap.index, direction=gap.direction, top=gap.top,
            bottom=gap.bottom, filled=filled_index is not None,
            filled_index=filled_index))
    return filled


# --- Order Blocks ---------------------------------------------------------------

def detect_order_blocks(candles: list[Candle]) -> list[OrderBlock]:
    """Order Blocks (regra objetiva): para cada BOS, o último candle de
    cor oposta à direção do BOS antes do candle do BOS (busca até 5
    candles para trás). Zona = high/low desse candle."""
    events = detect_bos_choch(candles)
    blocks: list[OrderBlock] = []
    for ev in events:
        if ev.kind != "bos":
            continue
        for j in range(ev.index - 1, max(-1, ev.index - 6), -1):
            c = candles[j]
            is_bull = _f(c.close) > _f(c.open)
            if ev.direction == "bullish" and not is_bull:
                blocks.append(OrderBlock(index=j, bos_index=ev.index,
                                         direction="bullish",
                                         top=_f(c.high), bottom=_f(c.low)))
                break
            if ev.direction == "bearish" and is_bull:
                blocks.append(OrderBlock(index=j, bos_index=ev.index,
                                         direction="bearish",
                                         top=_f(c.high), bottom=_f(c.low)))
                break
    return blocks


# --- Fibonacci -------------------------------------------------------------------

def fib_retracement(swing_low: float, swing_high: float) -> dict[float, float]:
    """Níveis de retração de Fibonacci entre swing low e swing high."""
    if swing_high <= swing_low:
        raise ValueError("fib_retracement precisa de swing_high > swing_low")
    leg = swing_high - swing_low
    return {ratio: round(swing_high - ratio * leg, 6)
            for ratio in FIB_RETRACEMENT}


def fib_extension(swing_low: float, swing_high: float,
                  retrace_low: Optional[float] = None) -> dict[float, float]:
    """Níveis de extensão: projetados a partir de `retrace_low`
    (padrão: o próprio swing low)."""
    if swing_high <= swing_low:
        raise ValueError("fib_extension precisa de swing_high > swing_low")
    base = swing_low if retrace_low is None else retrace_low
    leg = swing_high - swing_low
    return {ratio: round(base + ratio * leg, 6) for ratio in FIB_EXTENSION}


__all__ = [
    "Swing", "Level", "StructureEvent", "FairValueGap", "OrderBlock",
    "find_swings", "classify_trend", "find_levels",
    "detect_bos_choch", "detect_breakout_retest", "detect_pullbacks",
    "detect_liquidity_sweeps", "detect_fvg", "detect_order_blocks",
    "fib_retracement", "fib_extension",
]
