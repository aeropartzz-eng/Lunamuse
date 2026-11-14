"""Market Regime Engine — Fase 11 (REG-001…REG-005), especificação v4.1 §6.

Classifica o regime de mercado a partir de candles OHLCV, com regras
objetivas e testáveis, **sem look-ahead**: o regime no índice ``i`` só
usa dados até ``i``.

Regimes (rótulos; os mesmos valores em minúsculo vivem na tabela
``market_regimes`` da Fase 2 — ``trend_up``, ``trend_down``, ``range``,
``compression``, ``expansion``, ``transition``):

- ``TREND_UP`` / ``TREND_DOWN`` (REG-001): tendência direcional.
- ``RANGE`` (REG-002): lateralização.
- ``COMPRESSION`` (REG-003): volatilidade comprimida (pré-expansão).
- ``EXPANSION`` (REG-004): volatilidade em expansão.
- ``TRANSITION`` (REG-005): nenhum dos estados acima se confirma —
  o mercado está entre regimes; nenhuma estratégia direcional deve
  presumir tendência aqui.

Regras (thresholds documentados — ver README do serviço)
---------------------------------------------------------
Todas as medidas são calculadas sobre o último candle da janela:

- Tendência: ADX >= 25 **e** EMA(20) acima/abaixo da EMA(50) **e**
  fechamento do mesmo lado da EMA(20) **e** inclinação da EMA(20)
  (5 candles) no sentido do movimento. ADX ``NaN`` (ex.: série longa
  e plana seguida de movimento — a suavização de Wilder da Fase 9 não
  encontra janela limpa) usa como proxy ``| +DI − −DI |``.
- Compressão: razão da largura de Bollinger (largura atual / mediana
  das últimas 50 larguras) <= 0,65 **e** razão de ATR
  (ATR atual / SMA(ATR, 20)) <= 1,15 **e** ADX efetivo < 25.
  A largura de Bollinger — e não o ATR — é o discriminante principal:
  numa série sintética de amplitude decrescente o ATR quase não cai
  (o ruído de high/low impõe um piso), enquanto a largura cai para
  ~0,42 da mediana (medido em testes).
- Expansão: razão de ATR >= 1,40 **ou** razão de largura de Bollinger
  >= 1,50. Numa tendência estável as duas razões ficam ~1,0, então
  tendência não vira expansão por engano.
- Lateralização: ADX efetivo < 25 **e** eficiência (variação líquida
  de 20 candles / soma das variações absolutas) <= 0,35 **e**
  variação líquida de 20 candles <= 3%.
- Nada acima: ``TRANSITION``.

Precedência: compressão e expansão são estados de volatilidade e são
testados **antes** da tendência — uma expansão forte durante uma alta
é classificada ``EXPANSION``, não ``TREND_UP``.

Mudança de regime (REG-005)
----------------------------
:func:`detect_regime` classifica o último candle (rótulo bruto).
A confirmação com persistência vive em :class:`RegimeTracker`: um
novo rótulo só vira o regime confirmado depois de
``min_persistence`` classificações consecutivas com esse rótulo
(padrão 3 candles). Sem isso, um candle isolado faria o regime
oscilar a cada barra. :func:`detect_regime_changes` aplica o tracker
sobre a série inteira e devolve as mudanças confirmadas.

Nenhuma rede, nenhuma chave, nenhum envio de ordem — só cálculo.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

try:
    import indicators
except ImportError:  # diretório services/indicators fora do sys.path
    sys.path.append(str(Path(__file__).resolve().parents[1] / "indicators"))
    import indicators

__all__ = [
    "TREND_UP",
    "TREND_DOWN",
    "RANGE",
    "COMPRESSION",
    "EXPANSION",
    "TRANSITION",
    "REGIMES",
    "Regime",
    "RegimeTracker",
    "detect_regime",
    "classify_series",
    "detect_regime_changes",
    "MIN_CANDLES",
]

TREND_UP = "TREND_UP"
TREND_DOWN = "TREND_DOWN"
RANGE = "RANGE"
COMPRESSION = "COMPRESSION"
EXPANSION = "EXPANSION"
TRANSITION = "TRANSITION"

REGIMES = (TREND_UP, TREND_DOWN, RANGE, COMPRESSION, EXPANSION, TRANSITION)

# --- Thresholds (ver docstring do módulo) ---------------------------------
MIN_CANDLES = 50            # warm-up: EMA(50) + ADX + Bollinger(20)
ADX_TREND = 25.0            # ADX >= 25 -> tendência (Wilder)
ADX_RANGE_MAX = 25.0        # ADX < 25 -> sem tendência direcional
EMA_SLOPE_MIN_PCT = 0.0005  # inclinação mínima da EMA(20) em 5 candles
BB_RATIO_COMPRESSION = 0.65  # largura BB / mediana(50) <= 0,65
ATR_RATIO_COMPRESSION_MAX = 1.15
ATR_RATIO_EXPANSION = 1.40
BB_RATIO_EXPANSION = 1.50
EFFICIENCY_RANGE_MAX = 0.35  # eficiência de 20 candles <= 0,35
CHANGE_20_RANGE_MAX_PCT = 3.0
DEFAULT_PERSISTENCE = 3      # candles consecutivos p/ confirmar mudança


@dataclass(frozen=True)
class Regime:
    """Um regime classificado num índice da série."""

    label: str  # um dos REGIMES
    confidence: float  # 0..1
    reason: str  # motivo legível, com os números que decidiram
    index: int  # índice do candle classificado
    features: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.label not in REGIMES:
            raise ValueError(f"regime inválido: {self.label!r}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence fora de [0, 1]: {self.confidence}")


def _nan_to_none(value: float) -> Optional[float]:
    return None if value is None or (isinstance(value, float) and np.isnan(value)) else float(value)


def _features_at(arrays: Dict[str, Any], i: int) -> Dict[str, Any]:
    """Medidas objetivas no índice ``i`` (só dados até ``i``)."""
    close = arrays["close"]
    ema20 = arrays["ema_20"]
    ema50 = arrays["ema_50"]
    dmi = arrays["dmi"]
    atr = arrays["atr_14"]
    bbw = arrays["bollinger"]["bandwidth"]

    def _at(arr: np.ndarray, idx: int) -> float:
        return float(arr[idx]) if 0 <= idx < len(arr) else float("nan")

    adx = _at(dmi["adx"], i)
    plus_di = _at(dmi["plus_di"], i)
    minus_di = _at(dmi["minus_di"], i)
    # ADX NaN -> proxy pela separação dos DIs (ver docstring).
    if np.isnan(adx):
        if not np.isnan(plus_di) and not np.isnan(minus_di):
            adx_eff = abs(plus_di - minus_di)
        else:
            adx_eff = 0.0
    else:
        adx_eff = adx

    atr_now = _at(atr, i)
    atr_ma = _at(arrays["atr_ma_20"], i)
    atr_ratio = atr_now / atr_ma if atr_ma and atr_ma > 0 and not np.isnan(atr_now) else float("nan")

    window = bbw[max(0, i - 49):i + 1]
    median_bbw = float(np.nanmedian(window)) if len(window) else float("nan")
    bb_now = _at(bbw, i)
    bb_ratio = bb_now / median_bbw if median_bbw and median_bbw > 0 and not np.isnan(bb_now) else float("nan")

    # Inclinação da EMA(20) em 5 candles, em fração.
    ema_now = _at(ema20, i)
    ema_prev = _at(ema20, i - 5)
    slope = (ema_now - ema_prev) / ema_prev if ema_prev and ema_prev != 0 and not np.isnan(ema_now) else float("nan")

    # Eficiência e variação líquida de 20 candles.
    if i >= 20:
        segment = close[i - 20:i + 1]
        net = float(segment[-1] - segment[0])
        gross = float(np.sum(np.abs(np.diff(segment))))
        efficiency = abs(net) / gross if gross > 0 else float("nan")
        change_pct = 100.0 * net / segment[0] if segment[0] != 0 else float("nan")
    else:
        efficiency = float("nan")
        change_pct = float("nan")

    return {
        "close": _nan_to_none(_at(close, i)),
        "ema_20": _nan_to_none(ema_now),
        "ema_50": _nan_to_none(_at(ema50, i)),
        "adx": _nan_to_none(adx),
        "adx_effective": round(float(adx_eff), 3),
        "plus_di": _nan_to_none(plus_di),
        "minus_di": _nan_to_none(minus_di),
        "ema_slope_pct": _nan_to_none(slope),
        "atr": _nan_to_none(atr_now),
        "atr_ratio": _nan_to_none(atr_ratio),
        "bb_bandwidth": _nan_to_none(bb_now),
        "bb_bandwidth_ratio": _nan_to_none(bb_ratio),
        "efficiency_20": _nan_to_none(efficiency),
        "change_20_pct": _nan_to_none(change_pct),
    }


def _classify_at(arrays: Dict[str, Any], i: int) -> Regime:
    """Classifica o regime no índice ``i`` (rótulo bruto, sem persistência)."""
    f = _features_at(arrays, i)
    close = f["close"]
    ema20, ema50 = f["ema_20"], f["ema_50"]
    adx_eff = f["adx_effective"]
    slope = f["ema_slope_pct"]
    atr_ratio = f["atr_ratio"]
    bb_ratio = f["bb_bandwidth_ratio"]
    efficiency = f["efficiency_20"]
    change_pct = f["change_20_pct"]

    def _conf(base: float, bonus: float) -> float:
        return round(max(0.5, min(0.95, base + bonus)), 3)

    # 1. Compressão (REG-003) — volatilidade comprimida.
    if (
        bb_ratio is not None and bb_ratio <= BB_RATIO_COMPRESSION
        and (atr_ratio is None or atr_ratio <= ATR_RATIO_COMPRESSION_MAX)
        and adx_eff < ADX_TREND
    ):
        conf = _conf(0.55, 0.30 * (BB_RATIO_COMPRESSION - bb_ratio) / BB_RATIO_COMPRESSION)
        return Regime(
            label=COMPRESSION, confidence=conf, index=i, features=f,
            reason=(
                f"compressão: largura de Bollinger {bb_ratio:.2f}x a mediana "
                f"(<= {BB_RATIO_COMPRESSION}), ATR {atr_ratio if atr_ratio is None else round(atr_ratio, 2)}x "
                f"a média, ADX {adx_eff:.1f} < {ADX_TREND:.0f}"
            ),
        )

    # 2. Expansão (REG-004) — volatilidade em expansão.
    if (
        (atr_ratio is not None and atr_ratio >= ATR_RATIO_EXPANSION)
        or (bb_ratio is not None and bb_ratio >= BB_RATIO_EXPANSION)
    ):
        atr_part = max(0.0, (atr_ratio - ATR_RATIO_EXPANSION) * 0.25) if atr_ratio is not None else 0.0
        bb_part = min(0.25, (bb_ratio - BB_RATIO_EXPANSION) * 0.02) if bb_ratio is not None else 0.0
        conf = _conf(0.60, max(atr_part, bb_part))
        return Regime(
            label=EXPANSION, confidence=conf, index=i, features=f,
            reason=(
                f"expansão: ATR {atr_ratio if atr_ratio is None else round(atr_ratio, 2)}x "
                f"a média (>= {ATR_RATIO_EXPANSION}) e/ou largura de Bollinger "
                f"{bb_ratio if bb_ratio is None else round(bb_ratio, 2)}x a mediana "
                f"(>= {BB_RATIO_EXPANSION})"
            ),
        )

    # 3. Tendência (REG-001).
    trend_up = (
        adx_eff >= ADX_TREND
        and ema20 is not None and ema50 is not None and close is not None
        and ema20 > ema50 and close > ema20
        and slope is not None and slope > EMA_SLOPE_MIN_PCT
    )
    trend_down = (
        adx_eff >= ADX_TREND
        and ema20 is not None and ema50 is not None and close is not None
        and ema20 < ema50 and close < ema20
        and slope is not None and slope < -EMA_SLOPE_MIN_PCT
    )
    if trend_up or trend_down:
        label = TREND_UP if trend_up else TREND_DOWN
        direction = "alta" if trend_up else "baixa"
        conf = _conf(0.55, min(0.30, (adx_eff - ADX_TREND) / 100.0) + 0.05)
        return Regime(
            label=label, confidence=conf, index=i, features=f,
            reason=(
                f"tendência de {direction}: ADX {adx_eff:.1f} >= {ADX_TREND:.0f}, "
                f"EMA20 {ema20:.2f} {'acima' if trend_up else 'abaixo'} da EMA50 {ema50:.2f}, "
                f"inclinação da EMA20 {slope * 100:.2f}% em 5 candles"
            ),
        )

    # 4. Lateralização (REG-002).
    if (
        adx_eff < ADX_RANGE_MAX
        and efficiency is not None and efficiency <= EFFICIENCY_RANGE_MAX
        and change_pct is not None and abs(change_pct) <= CHANGE_20_RANGE_MAX_PCT
    ):
        conf = _conf(0.55, 0.30 * (EFFICIENCY_RANGE_MAX - efficiency) / EFFICIENCY_RANGE_MAX)
        return Regime(
            label=RANGE, confidence=conf, index=i, features=f,
            reason=(
                f"lateralização: ADX {adx_eff:.1f} < {ADX_RANGE_MAX:.0f}, "
                f"eficiência de 20 candles {efficiency:.2f} "
                f"(<= {EFFICIENCY_RANGE_MAX}), variação líquida {change_pct:.2f}%"
            ),
        )

    # 5. Transição (REG-005) — nada se confirma.
    return Regime(
        label=TRANSITION, confidence=0.50, index=i, features=f,
        reason=(
            f"transição: ADX {adx_eff:.1f}, EMA20/EMA50 sem alinhamento "
            f"ou eficiência {efficiency if efficiency is None else round(efficiency, 2)} "
            f"fora dos limites de tendência/lateralização"
        ),
    )


def _prepare_arrays(candles: Sequence[Any]) -> Dict[str, Any]:
    """Arrays de indicadores sobre a série inteira (sem look-ahead por
    construção da Fase 9: cada valor só usa dados até o seu índice)."""
    if len(candles) < MIN_CANDLES:
        raise ValueError(
            f"detect_regime precisa de ao menos {MIN_CANDLES} candles, "
            f"recebidos {len(candles)}"
        )
    data = indicators.candles_to_arrays(candles)
    computed = indicators.compute_all(candles)
    arrays: Dict[str, Any] = {
        "close": data["close"],
        "ema_20": computed["ema_20"],
        "ema_50": indicators.ema(data["close"], 50),
        "dmi": computed["dmi"],
        "atr_14": computed["atr_14"],
        "atr_ma_20": indicators.sma(computed["atr_14"], 20),
        "bollinger": computed["bollinger"],
    }
    return arrays


def detect_regime(
    candles: Sequence[Any],
    indicators_cache: Optional[Dict[str, Any]] = None,
) -> Regime:
    """Classifica o regime no último candle da série (rótulo bruto).

    A confirmação com persistência é responsabilidade de
    :class:`RegimeTracker` / :func:`detect_regime_changes` — um único
    candle não confirma mudança de regime.
    """
    arrays = _prepare_arrays(candles) if indicators_cache is None else indicators_cache
    return _classify_at(arrays, len(candles) - 1)


def classify_series(candles: Sequence[Any]) -> List[Regime]:
    """Classifica o regime em cada índice a partir do warm-up
    (rótulos brutos, sem persistência — ver :class:`RegimeTracker`)."""
    arrays = _prepare_arrays(candles)
    return [_classify_at(arrays, i) for i in range(MIN_CANDLES - 1, len(candles))]


class RegimeTracker:
    """Regime confirmado com persistência mínima (REG-005).

    O rótulo bruto de cada chamada é comparado com o regime confirmado:
    se for diferente, vira *pendente*; só depois de ``min_persistence``
    classificações consecutivas com o novo rótulo ele é confirmado e
    entra no histórico. Enquanto isso, o regime confirmado não muda —
    nada de flip a cada candle.
    """

    def __init__(self, min_persistence: int = DEFAULT_PERSISTENCE) -> None:
        if min_persistence < 1:
            raise ValueError(f"min_persistence deve ser >= 1, recebido {min_persistence}")
        self.min_persistence = min_persistence
        self.current: Optional[Regime] = None
        self.pending_label: Optional[str] = None
        self.pending_count: int = 0
        self.history: List[Dict[str, Any]] = []  # mudanças confirmadas

    def observe(self, raw: Regime) -> Regime:
        """Alimenta um rótulo bruto; devolve o regime confirmado."""
        if self.current is None:
            self.current = raw
            self.pending_label = None
            self.pending_count = 0
            return self.current
        if raw.label == self.current.label:
            self.pending_label = None
            self.pending_count = 0
            self.current = raw  # atualiza confiança/motivo, mantém o rótulo
            return self.current
        if raw.label == self.pending_label:
            self.pending_count += 1
        else:
            self.pending_label = raw.label
            self.pending_count = 1
        if self.pending_count >= self.min_persistence:
            change = {
                "index": raw.index,
                "from": self.current.label,
                "to": raw.label,
                "confidence": raw.confidence,
                "reason": raw.reason,
            }
            self.history.append(change)
            self.current = raw
            self.pending_label = None
            self.pending_count = 0
        return self.current

    def update(self, candles: Sequence[Any]) -> Regime:
        """Classifica o último candle da série e alimenta o tracker."""
        return self.observe(detect_regime(candles))


def detect_regime_changes(
    candles: Sequence[Any],
    min_persistence: int = DEFAULT_PERSISTENCE,
) -> List[Dict[str, Any]]:
    """Mudanças de regime confirmadas ao longo da série.

    Devolve ``[{"index", "from", "to", "confidence", "reason"}]`` —
    só mudanças que persistiram ``min_persistence`` candles.
    """
    tracker = RegimeTracker(min_persistence=min_persistence)
    for raw in classify_series(candles):
        tracker.observe(raw)
    return list(tracker.history)
