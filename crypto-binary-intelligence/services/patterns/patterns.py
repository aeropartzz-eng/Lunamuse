"""Pattern Engine — padrões de velas (Fase 10 — PAT-001…PAT-006).

Regras objetivas e testáveis sobre :class:`Candle` (contrato universal,
Fase 3). Nenhuma rede, nenhuma chave, nenhum envio de ordem.

REGRA CENTRAL (§6, PAT-006): um padrão isolado NÃO gera entrada
automática. Toda detecção carrega ``requires_confirmation=True`` e
``generates_entry=False``; :func:`assess_pattern` anexa o contexto
mínimo (tendência, localização, volume, volatilidade) e o que seria a
confirmação. A decisão de operar pertence às fases 11/14/15, nunca a
este módulo.

Thresholds (documentados, não mágicos — ver README do serviço):
- Doji: corpo <= 10% do range.
- Hammer / Shooting Star: corpo <= 35% do range, sombra longa >= 2x o
  corpo, sombra oposta <= 1x o corpo.
- Marubozu: corpo >= 90% do range, sombras <= 5% do range cada.
- Spinning Top: corpo <= 30% do range, ambas as sombras >= 1x o corpo.
- Engulfing: corpo do candle 2 engole o corpo do candle 1, cores opostas.
- Harami: corpo do candle 2 dentro do corpo do candle 1, cores opostas.
- Piercing / Dark Cloud: candle 2 abre além do extremo do candle 1 e
  fecha além do ponto médio do corpo do candle 1.
- Morning / Evening Star: candle 1 longo, candle 2 de corpo pequeno com
  gap, candle 3 fecha além do ponto médio do corpo do candle 1.
- Three White Soldiers / Black Crows: 3 candles da mesma cor, corpos
  >= 50% do range, cada abertura dentro do corpo anterior, fechamentos
  progressivos, sem sombra longa na direção do movimento.
- Tweezers: máximas (topo) ou mínimas (fundo) iguais dentro de 0,1% do
  preço, cores opostas.
- Inside / Outside Bar: high/low contidos em / contendo o candle anterior.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

try:
    from models import Candle
except ImportError:  # diretório services/exchange-connectors fora do sys.path
    sys.path.append(
        str(Path(__file__).resolve().parents[1] / "exchange-connectors")
    )
    from models import Candle

# --- Thresholds (ver docstring do módulo) ---------------------------------
DOJI_BODY_MAX = 0.10          # corpo/range
HAMMER_BODY_MAX = 0.35        # corpo/range
HAMMER_SHADOW_MIN = 2.0       # sombra longa / corpo
HAMMER_SHADOW_MAX = 1.0       # sombra oposta / corpo
MARUBOZU_BODY_MIN = 0.90      # corpo/range
MARUBOZU_SHADOW_MAX = 0.05    # sombra/range
SPINNING_BODY_MAX = 0.30      # corpo/range
SOLDIER_BODY_MIN = 0.50       # corpo/range
SOLDIER_SHADOW_MAX = 0.25     # sombra na direção do movimento / range
TWEEZER_TOL_PCT = 0.001       # 0,1% do preço
STAR_BODY_MAX = 0.35          # corpo do candle do meio (morning/evening star)
STAR_LONG_BODY_MIN = 0.50     # corpo do candle 1 (morning/evening star)

BULLISH = "bullish"
BEARISH = "bearish"
NEUTRAL = "neutral"

# Confirmação esperada por padrão (PAT-006). Texto curto, objetivo.
CONFIRMATIONS: dict[str, str] = {
    "doji": "Próximo candle fechar na direção da reversão, com volume acima da média; doji sozinho é indecisão, não sinal.",
    "gravestone_doji": "Próximo candle fechar abaixo da mínima do doji, com volume acima da média.",
    "dragonfly_doji": "Próximo candle fechar acima da máxima do doji, com volume acima da média.",
    "long_legged_doji": "Próximo candle fechar com corpo claro na direção da reversão, com volume acima da média.",
    "four_price_doji": "Aguardar o próximo candle: four-price doji é ausência de movimento, não há direção implícita.",
    "hammer": "Próximo candle fechar acima da máxima do hammer, com volume acima da média.",
    "hanging_man": "Próximo candle fechar abaixo da mínima do hanging man, com volume acima da média.",
    "inverted_hammer": "Próximo candle fechar acima da máxima do inverted hammer, com volume acima da média.",
    "shooting_star": "Próximo candle fechar abaixo da mínima da shooting star, com volume acima da média.",
    "bullish_engulfing": "Próximo candle fechar acima da máxima do engolfo; volume do engolfo acima da média reforça.",
    "bearish_engulfing": "Próximo candle fechar abaixo da mínima do engolfo; volume do engolfo acima da média reforça.",
    "bullish_harami": "Próximo candle fechar acima da máxima do harami, com volume acima da média.",
    "bearish_harami": "Próximo candle fechar abaixo da mínima do harami, com volume acima da média.",
    "piercing_line": "Próximo candle fechar acima da máxima da piercing line, com volume acima da média.",
    "dark_cloud_cover": "Próximo candle fechar abaixo da mínima da dark cloud, com volume acima da média.",
    "morning_star": "Próximo candle fechar acima da máxima do terceiro candle, com volume acima da média.",
    "evening_star": "Próximo candle fechar abaixo da mínima do terceiro candle, com volume acima da média.",
    "three_white_soldiers": "Continuação com volume sustentado; invalida se o próximo candle fechar abaixo da mínima do segundo soldier.",
    "three_black_crows": "Continuação com volume sustentado; invalida se o próximo candle fechar acima da máxima do segundo crow.",
    "tweezer_bottom": "Próximo candle fechar acima da máxima do segundo candle, com volume acima da média.",
    "tweezer_top": "Próximo candle fechar abaixo da mínima do segundo candle, com volume acima da média.",
    "marubozu_bullish": "Continuação na direção; invalida se o próximo candle fechar abaixo da mínima do marubozu.",
    "marubozu_bearish": "Continuação na direção; invalida se o próximo candle fechar acima da máxima do marubozu.",
    "spinning_top": "Aguardar o próximo candle: spinning top é indecisão, não há direção implícita.",
    "inside_bar": "Romper a máxima (alta) ou a mínima (baixa) do candle anterior com volume acima da média; inside bar sozinha é consolidação.",
    "outside_bar_bullish": "Próximo candle fechar acima da máxima do outside bar, com volume acima da média.",
    "outside_bar_bearish": "Próximo candle fechar abaixo da mínima do outside bar, com volume acima da média.",
}


@dataclass(frozen=True)
class PatternDetection:
    """Uma detecção de padrão de velas.

    ``generates_entry`` é sempre False: padrão isolado não gera entrada
    (PAT-006). ``context`` é preenchido por :func:`assess_pattern`.
    """

    name: str
    direction: str  # "bullish" | "bearish" | "neutral"
    index: int  # índice do último candle do padrão na série
    confidence: float  # 0..1 — qualidade geométrica (+ volume quando dado)
    strength: str  # "weak" | "moderate" | "strong"
    confirmation: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = True
    generates_entry: bool = False
    details: dict[str, Any] = field(default_factory=dict)


def _f(value: Decimal) -> float:
    return float(value)


def _geometry(c: Candle) -> dict[str, float]:
    """Medidas geométricas de um candle, em float."""
    o, h, l, cl = _f(c.open), _f(c.high), _f(c.low), _f(c.close)
    rng = h - l
    body = abs(cl - o)
    upper = h - max(o, cl)
    lower = min(o, cl) - l
    return {
        "open": o, "high": h, "low": l, "close": cl,
        "range": rng, "body": body, "upper": upper, "lower": lower,
        "bullish": cl > o, "bearish": cl < o,
        "body_ratio": (body / rng) if rng > 0 else 0.0,
    }


def _strength(confidence: float) -> str:
    if confidence >= 0.75:
        return "strong"
    if confidence >= 0.55:
        return "moderate"
    return "weak"


def _make(name: str, direction: str, index: int, confidence: float,
          details: Optional[dict[str, Any]] = None) -> PatternDetection:
    confidence = max(0.0, min(0.95, confidence))
    return PatternDetection(
        name=name,
        direction=direction,
        index=index,
        confidence=round(confidence, 3),
        strength=_strength(confidence),
        confirmation=CONFIRMATIONS.get(name, ""),
        details=details or {},
    )


def _volume_boost(candles: list[Candle], index: int, lookback: int = 10) -> float:
    """+0,1 de confiança se o volume do candle está acima da média.

    Devolve 0,0 quando não há histórico suficiente ou volume zero.
    """
    if index < 1 or lookback < 1:
        return 0.0
    window = candles[max(0, index - lookback):index]
    if not window:
        return 0.0
    avg = sum(_f(c.volume) for c in window) / len(window)
    if avg <= 0:
        return 0.0
    return 0.1 if _f(candles[index].volume) > avg else 0.0


def _prior_trend(candles: list[Candle], index: int, lookback: int = 5) -> str:
    """Tendência prévia ao índice: compara closes com `lookback` atrás."""
    if index < lookback:
        return NEUTRAL
    start = _f(candles[index - lookback].close)
    end = _f(candles[index - 1].close)
    if start <= 0:
        return NEUTRAL
    change = (end - start) / start
    if change > 0.005:
        return BULLISH
    if change < -0.005:
        return BEARISH
    return NEUTRAL


# --- Padrões de 1 candle ---------------------------------------------------

def detect_doji(candles: list[Candle], index: int) -> Optional[PatternDetection]:
    """Doji e variações (PAT-001). Corpo <= 10% do range."""
    if index < 0 or index >= len(candles):
        return None
    g = _geometry(candles[index])
    if g["range"] <= 0:
        # Four-price doji: open == high == low == close.
        return _make("four_price_doji", NEUTRAL, index, 0.9,
                     {"body_ratio": 0.0, "range": 0.0})
    if g["body_ratio"] > DOJI_BODY_MAX:
        return None
    conf = 0.6 + 0.2 * (1.0 - g["body_ratio"] / DOJI_BODY_MAX)
    if g["lower"] <= 0.10 * g["range"] and g["upper"] >= 0.60 * g["range"]:
        return _make("gravestone_doji", BEARISH, index,
                     conf + _volume_boost(candles, index),
                     {"body_ratio": g["body_ratio"]})
    if g["upper"] <= 0.10 * g["range"] and g["lower"] >= 0.60 * g["range"]:
        return _make("dragonfly_doji", BULLISH, index,
                     conf + _volume_boost(candles, index),
                     {"body_ratio": g["body_ratio"]})
    if g["upper"] >= 0.35 * g["range"] and g["lower"] >= 0.35 * g["range"]:
        return _make("long_legged_doji", NEUTRAL, index,
                     conf + _volume_boost(candles, index),
                     {"body_ratio": g["body_ratio"]})
    return _make("doji", NEUTRAL, index,
                 conf + _volume_boost(candles, index),
                 {"body_ratio": g["body_ratio"]})


def _hammer_shape(g: dict[str, float]) -> bool:
    return (
        g["range"] > 0
        and g["body"] > 0
        and g["body_ratio"] <= HAMMER_BODY_MAX
        and g["lower"] >= HAMMER_SHADOW_MIN * g["body"]
        and g["upper"] <= HAMMER_SHADOW_MAX * g["body"]
    )


def _shooting_shape(g: dict[str, float]) -> bool:
    return (
        g["range"] > 0
        and g["body"] > 0
        and g["body_ratio"] <= HAMMER_BODY_MAX
        and g["upper"] >= HAMMER_SHADOW_MIN * g["body"]
        and g["lower"] <= HAMMER_SHADOW_MAX * g["body"]
    )


def detect_hammer(candles: list[Candle], index: int) -> Optional[PatternDetection]:
    """Hammer / Hanging Man (PAT-002).

    Mesma geometria; o nome depende da tendência prévia: tendência de
    baixa -> hammer (reversão de alta); tendência de alta -> hanging man
    (alerta de reversão de baixa). Sem tendência prévia clara, "hammer".
    """
    if index < 0 or index >= len(candles):
        return None
    g = _geometry(candles[index])
    if not _hammer_shape(g):
        return None
    conf = 0.6 + 0.15 * min(g["lower"] / max(g["body"], 1e-12), 4.0) / 4.0
    conf += _volume_boost(candles, index)
    trend = _prior_trend(candles, index)
    if trend == BULLISH:
        return _make("hanging_man", BEARISH, index, conf,
                     {"prior_trend": trend, "lower_shadow_body_ratio":
                      g["lower"] / g["body"]})
    return _make("hammer", BULLISH, index, conf,
                 {"prior_trend": trend,
                  "lower_shadow_body_ratio": g["lower"] / g["body"]})


def detect_shooting_star(candles: list[Candle],
                         index: int) -> Optional[PatternDetection]:
    """Shooting Star / Inverted Hammer (PAT-002).

    Mesma geometria; tendência prévia de alta -> shooting star (reversão
    de baixa); tendência de baixa -> inverted hammer (reversão de alta).
    Sem tendência prévia clara, "inverted_hammer".
    """
    if index < 0 or index >= len(candles):
        return None
    g = _geometry(candles[index])
    if not _shooting_shape(g):
        return None
    conf = 0.6 + 0.15 * min(g["upper"] / max(g["body"], 1e-12), 4.0) / 4.0
    conf += _volume_boost(candles, index)
    trend = _prior_trend(candles, index)
    if trend == BULLISH:
        return _make("shooting_star", BEARISH, index, conf,
                     {"prior_trend": trend, "upper_shadow_body_ratio":
                      g["upper"] / g["body"]})
    return _make("inverted_hammer", BULLISH, index, conf,
                 {"prior_trend": trend,
                  "upper_shadow_body_ratio": g["upper"] / g["body"]})


def detect_marubozu(candles: list[Candle], index: int) -> Optional[PatternDetection]:
    """Marubozu (PAT-005): corpo >= 90% do range, sombras <= 5% do range."""
    if index < 0 or index >= len(candles):
        return None
    g = _geometry(candles[index])
    if g["range"] <= 0 or g["body_ratio"] < MARUBOZU_BODY_MIN:
        return None
    if g["upper"] > MARUBOZU_SHADOW_MAX * g["range"]:
        return None
    if g["lower"] > MARUBOZU_SHADOW_MAX * g["range"]:
        return None
    direction = BULLISH if g["bullish"] else (BEARISH if g["bearish"] else NEUTRAL)
    if direction == NEUTRAL:
        return None
    name = "marubozu_bullish" if direction == BULLISH else "marubozu_bearish"
    conf = 0.65 + 0.2 * (g["body_ratio"] - MARUBOZU_BODY_MIN) / 0.10
    return _make(name, direction, index,
                 conf + _volume_boost(candles, index),
                 {"body_ratio": g["body_ratio"]})


def detect_spinning_top(candles: list[Candle],
                        index: int) -> Optional[PatternDetection]:
    """Spinning Top (PAT-005): corpo pequeno, ambas as sombras >= corpo."""
    if index < 0 or index >= len(candles):
        return None
    g = _geometry(candles[index])
    if g["range"] <= 0 or g["body"] <= 0:
        return None
    if g["body_ratio"] > SPINNING_BODY_MAX:
        return None
    if g["upper"] < g["body"] or g["lower"] < g["body"]:
        return None
    conf = 0.6 + 0.15 * (1.0 - g["body_ratio"] / SPINNING_BODY_MAX)
    return _make("spinning_top", NEUTRAL, index,
                 conf + _volume_boost(candles, index),
                 {"body_ratio": g["body_ratio"]})


# --- Padrões de 2 candles --------------------------------------------------

def detect_engulfing(candles: list[Candle],
                     index: int) -> Optional[PatternDetection]:
    """Bullish / Bearish Engulfing (PAT-003)."""
    if index < 1 or index >= len(candles):
        return None
    g1, g2 = _geometry(candles[index - 1]), _geometry(candles[index])
    if g1["body"] <= 0 or g2["body"] <= 0:
        return None
    if g1["bullish"] == g2["bullish"]:
        return None
    lo1, hi1 = min(g1["open"], g1["close"]), max(g1["open"], g1["close"])
    lo2, hi2 = min(g2["open"], g2["close"]), max(g2["open"], g2["close"])
    if not (lo2 <= lo1 and hi2 >= hi1):
        return None
    if lo2 == lo1 and hi2 == hi1:
        return None  # engolfo exato não acrescenta informação
    direction = BULLISH if g2["bullish"] else BEARISH
    name = "bullish_engulfing" if direction == BULLISH else "bearish_engulfing"
    ratio = g2["body"] / g1["body"]
    conf = 0.6 + 0.15 * min(ratio, 3.0) / 3.0 + _volume_boost(candles, index)
    return _make(name, direction, index, conf,
                 {"engulf_ratio": round(ratio, 3)})


def detect_harami(candles: list[Candle], index: int) -> Optional[PatternDetection]:
    """Bullish / Bearish Harami (PAT-003)."""
    if index < 1 or index >= len(candles):
        return None
    g1, g2 = _geometry(candles[index - 1]), _geometry(candles[index])
    if g1["body"] <= 0 or g2["body"] <= 0:
        return None
    if g1["bullish"] == g2["bullish"]:
        return None
    lo1, hi1 = min(g1["open"], g1["close"]), max(g1["open"], g1["close"])
    lo2, hi2 = min(g2["open"], g2["close"]), max(g2["open"], g2["close"])
    if not (lo2 >= lo1 and hi2 <= hi1):
        return None
    direction = BULLISH if g2["bullish"] else BEARISH
    name = "bullish_harami" if direction == BULLISH else "bearish_harami"
    conf = 0.55 + 0.15 * (1.0 - g2["body"] / g1["body"])
    return _make(name, direction, index,
                 conf + _volume_boost(candles, index),
                 {"inside_ratio": round(g2["body"] / g1["body"], 3)})


def detect_piercing_dark_cloud(candles: list[Candle],
                               index: int) -> Optional[PatternDetection]:
    """Piercing Line / Dark Cloud Cover (PAT-003)."""
    if index < 1 or index >= len(candles):
        return None
    g1, g2 = _geometry(candles[index - 1]), _geometry(candles[index])
    if g1["body"] <= 0 or g2["body"] <= 0:
        return None
    midpoint1 = (g1["open"] + g1["close"]) / 2
    if g1["bearish"] and g2["bullish"]:
        if g2["open"] < g1["low"] and g2["close"] > midpoint1 \
                and g2["close"] < g1["open"]:
            conf = 0.6 + 0.15 * (g2["close"] - midpoint1) / max(g1["body"], 1e-12)
            return _make("piercing_line", BULLISH, index,
                         conf + _volume_boost(candles, index),
                         {"close_above_midpoint": True})
        return None
    if g1["bullish"] and g2["bearish"]:
        if g2["open"] > g1["high"] and g2["close"] < midpoint1 \
                and g2["close"] > g1["open"]:
            conf = 0.6 + 0.15 * (midpoint1 - g2["close"]) / max(g1["body"], 1e-12)
            return _make("dark_cloud_cover", BEARISH, index,
                         conf + _volume_boost(candles, index),
                         {"close_below_midpoint": True})
        return None
    return None


def detect_tweezers(candles: list[Candle],
                    index: int) -> Optional[PatternDetection]:
    """Tweezer Top / Tweezer Bottom (PAT-005).

    Máximas (topo) ou mínimas (fundo) iguais dentro de 0,1% do preço,
    com cores opostas.
    """
    if index < 1 or index >= len(candles):
        return None
    g1, g2 = _geometry(candles[index - 1]), _geometry(candles[index])
    if g1["bullish"] == g2["bullish"]:
        return None
    tol_top = TWEEZER_TOL_PCT * g1["high"]
    tol_bottom = TWEEZER_TOL_PCT * g1["low"]
    if abs(g1["high"] - g2["high"]) <= tol_top and g1["bullish"] and g2["bearish"]:
        return _make("tweezer_top", BEARISH, index,
                     0.65 + _volume_boost(candles, index),
                     {"high_diff_pct": round(
                         abs(g1["high"] - g2["high"]) / g1["high"], 5)})
    if abs(g1["low"] - g2["low"]) <= tol_bottom and g1["bearish"] and g2["bullish"]:
        return _make("tweezer_bottom", BULLISH, index,
                     0.65 + _volume_boost(candles, index),
                     {"low_diff_pct": round(
                         abs(g1["low"] - g2["low"]) / g1["low"], 5)})
    return None


def detect_inside_bar(candles: list[Candle],
                      index: int) -> Optional[PatternDetection]:
    """Inside Bar (PAT-005): high/low contidos no candle anterior."""
    if index < 1 or index >= len(candles):
        return None
    g1, g2 = _geometry(candles[index - 1]), _geometry(candles[index])
    if g2["high"] <= g1["high"] and g2["low"] >= g1["low"] and (
            g2["high"] < g1["high"] or g2["low"] > g1["low"]):
        conf = 0.6 + 0.1 * (1.0 - g2["range"] / g1["range"]) if g1["range"] > 0 else 0.6
        return _make("inside_bar", NEUTRAL, index, conf,
                     {"range_ratio": round(
                         g2["range"] / g1["range"], 3) if g1["range"] > 0 else 0.0})
    return None


def detect_outside_bar(candles: list[Candle],
                       index: int) -> Optional[PatternDetection]:
    """Outside Bar (PAT-005): high/low contêm o candle anterior."""
    if index < 1 or index >= len(candles):
        return None
    g1, g2 = _geometry(candles[index - 1]), _geometry(candles[index])
    if g2["high"] > g1["high"] and g2["low"] < g1["low"]:
        direction = BULLISH if g2["bullish"] else (
            BEARISH if g2["bearish"] else NEUTRAL)
        if direction == NEUTRAL:
            return None
        name = ("outside_bar_bullish" if direction == BULLISH
                else "outside_bar_bearish")
        return _make(name, direction, index,
                     0.65 + _volume_boost(candles, index),
                     {"range_ratio": round(
                         g2["range"] / g1["range"], 3) if g1["range"] > 0 else 0.0})
    return None


# --- Padrões de 3 candles --------------------------------------------------

def detect_morning_evening_star(candles: list[Candle],
                                index: int) -> Optional[PatternDetection]:
    """Morning Star / Evening Star (PAT-004)."""
    if index < 2 or index >= len(candles):
        return None
    g1 = _geometry(candles[index - 2])
    g2 = _geometry(candles[index - 1])
    g3 = _geometry(candles[index])
    midpoint1 = (g1["open"] + g1["close"]) / 2
    if g1["bearish"] and g1["body_ratio"] >= STAR_LONG_BODY_MIN \
            and g2["body_ratio"] <= STAR_BODY_MAX \
            and g2["close"] < g1["close"] \
            and g3["bullish"] and g3["close"] > midpoint1:
        conf = 0.65 + 0.15 * (g3["close"] - midpoint1) / max(g1["body"], 1e-12)
        return _make("morning_star", BULLISH, index,
                     conf + _volume_boost(candles, index),
                     {"midpoint_crossed": True})
    if g1["bullish"] and g1["body_ratio"] >= STAR_LONG_BODY_MIN \
            and g2["body_ratio"] <= STAR_BODY_MAX \
            and g2["close"] > g1["close"] \
            and g3["bearish"] and g3["close"] < midpoint1:
        conf = 0.65 + 0.15 * (midpoint1 - g3["close"]) / max(g1["body"], 1e-12)
        return _make("evening_star", BEARISH, index,
                     conf + _volume_boost(candles, index),
                     {"midpoint_crossed": True})
    return None


def detect_soldiers_crows(candles: list[Candle],
                          index: int) -> Optional[PatternDetection]:
    """Three White Soldiers / Three Black Crows (PAT-005)."""
    if index < 2 or index >= len(candles):
        return None
    gs = [_geometry(candles[i]) for i in (index - 2, index - 1, index)]
    for direction, name in ((True, "three_white_soldiers"),
                            (False, "three_black_crows")):
        ok = True
        for k, g in enumerate(gs):
            is_bull = g["bullish"] if direction else g["bearish"]
            if not is_bull or g["body_ratio"] < SOLDIER_BODY_MIN:
                ok = False
                break
            shadow = g["upper"] if direction else g["lower"]
            if shadow > SOLDIER_SHADOW_MAX * g["range"]:
                ok = False
                break
            if k > 0:
                prev = gs[k - 1]
                lo, hi = min(prev["open"], prev["close"]), max(prev["open"], prev["close"])
                if not (lo <= g["open"] <= hi):
                    ok = False
                    break
                if direction and not g["close"] > prev["close"]:
                    ok = False
                    break
                if not direction and not g["close"] < prev["close"]:
                    ok = False
                    break
        if ok:
            conf = 0.7 + _volume_boost(candles, index)
            return _make(name, BULLISH if direction else BEARISH, index, conf,
                         {"bodies": [round(g["body_ratio"], 3) for g in gs]})
    return None


# --- Orquestração ----------------------------------------------------------

_SINGLE = (detect_doji, detect_hammer, detect_shooting_star,
           detect_marubozu, detect_spinning_top)
_DOUBLE = (detect_engulfing, detect_harami, detect_piercing_dark_cloud,
           detect_tweezers, detect_inside_bar, detect_outside_bar)
_TRIPLE = (detect_morning_evening_star, detect_soldiers_crows)


def detect_at(candles: list[Candle], index: int) -> list[PatternDetection]:
    """Todos os padrões que terminam no candle `index`."""
    found: list[PatternDetection] = []
    for fn in _SINGLE:
        det = fn(candles, index)
        if det is not None:
            found.append(det)
    for fn in _DOUBLE:
        det = fn(candles, index)
        if det is not None:
            found.append(det)
    for fn in _TRIPLE:
        det = fn(candles, index)
        if det is not None:
            found.append(det)
    return found


def detect_all(candles: list[Candle]) -> list[PatternDetection]:
    """Todos os padrões da série, em ordem de índice."""
    found: list[PatternDetection] = []
    for i in range(len(candles)):
        found.extend(detect_at(candles, i))
    return found


# --- PAT-006: contexto e confirmação ---------------------------------------

def _atr(candles: list[Candle], index: int, lookback: int = 14) -> float:
    """ATR simplificado (média dos ranges) até `index` (exclusive)."""
    window = candles[max(0, index - lookback):index]
    if not window:
        return 0.0
    return sum(_geometry(c)["range"] for c in window) / len(window)


def build_context(candles: list[Candle], index: int,
                  lookback: int = 20,
                  levels: Optional[list[float]] = None) -> dict[str, Any]:
    """Contexto mínimo de uma detecção (PAT-006).

    Tendência (closes), volume relativo, volatilidade (range/ATR) e
    localização (distância ao nível de suporte/resistência mais próximo,
    quando `levels` é informado).
    """
    if index < 0 or index >= len(candles):
        return {}
    atr = _atr(candles, index)
    trend = _prior_trend(candles, index, lookback=min(lookback, index))
    window = candles[max(0, index - lookback):index]
    avg_vol = (sum(_f(c.volume) for c in window) / len(window)) if window else 0.0
    vol = _f(candles[index].volume)
    volume_ratio = (vol / avg_vol) if avg_vol > 0 else None
    rng = _geometry(candles[index])["range"]
    ctx: dict[str, Any] = {
        "trend": trend,
        "atr": round(atr, 6),
        "volatility_ratio": round(rng / atr, 3) if atr > 0 else None,
        "volume_ratio": round(volume_ratio, 3) if volume_ratio is not None else None,
        "volume_above_average": bool(volume_ratio is not None and volume_ratio > 1.0),
        "lookback": lookback,
    }
    if levels:
        price = _f(candles[index].close)
        nearest = min(levels, key=lambda lv: abs(lv - price))
        ctx["nearest_level"] = nearest
        ctx["distance_to_level_pct"] = round(abs(nearest - price) / price, 5)
        ctx["near_level"] = ctx["distance_to_level_pct"] <= 0.005
    return ctx


def assess_pattern(detection: PatternDetection, candles: list[Candle],
                   levels: Optional[list[float]] = None,
                   lookback: int = 20) -> PatternDetection:
    """Anexa contexto a uma detecção (PAT-006).

    Devolve uma cópia com ``context`` preenchido. Não altera
    ``generates_entry`` (sempre False) nem ``requires_confirmation``
    (sempre True): o padrão, sozinho, continua sem gerar entrada.

    ``trend_aligned``: para padrões de reversão, a tendência prévia
    deve ser **oposta** à direção do padrão (ex.: hammer de alta após
    tendência de baixa); para padrões de continuação, deve ser a
    **mesma** direção. Tendência lateral ou padrão neutro: alinhado.
    """
    ctx = build_context(candles, detection.index, lookback=lookback, levels=levels)
    trend = ctx.get("trend")
    direction = detection.direction
    reversal = {
        "doji", "gravestone_doji", "dragonfly_doji", "long_legged_doji",
        "four_price_doji", "hammer", "hanging_man", "inverted_hammer",
        "shooting_star", "bullish_engulfing", "bearish_engulfing",
        "bullish_harami", "bearish_harami", "piercing_line",
        "dark_cloud_cover", "morning_star", "evening_star",
        "tweezer_bottom", "tweezer_top",
    }
    continuation = {
        "three_white_soldiers", "three_black_crows",
        "marubozu_bullish", "marubozu_bearish",
    }
    if trend == NEUTRAL or direction == NEUTRAL:
        aligned = True
    elif detection.name in reversal:
        aligned = trend != direction
    elif detection.name in continuation:
        aligned = trend == direction
    else:
        aligned = trend == direction
    ctx["trend_aligned"] = aligned
    return PatternDetection(
        name=detection.name,
        direction=detection.direction,
        index=detection.index,
        confidence=detection.confidence,
        strength=detection.strength,
        confirmation=detection.confirmation,
        context=ctx,
        requires_confirmation=True,
        generates_entry=False,
        details=detection.details,
    )


def assess_all(candles: list[Candle],
               levels: Optional[list[float]] = None,
               lookback: int = 20) -> list[PatternDetection]:
    """Detecta todos os padrões da série já com contexto (PAT-006)."""
    return [assess_pattern(d, candles, levels=levels, lookback=lookback)
            for d in detect_all(candles)]


__all__ = [
    "PatternDetection",
    "CONFIRMATIONS",
    "detect_doji", "detect_hammer", "detect_shooting_star",
    "detect_marubozu", "detect_spinning_top", "detect_engulfing",
    "detect_harami", "detect_piercing_dark_cloud", "detect_tweezers",
    "detect_inside_bar", "detect_outside_bar",
    "detect_morning_evening_star", "detect_soldiers_crows",
    "detect_at", "detect_all",
    "build_context", "assess_pattern", "assess_all",
]
