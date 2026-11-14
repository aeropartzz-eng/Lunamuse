"""Strategy Engine / Strategy Lab — Fase 11 (STR-001…STR-010),
especificação v4.1 §6 e §9.

Framework de estratégias versionadas e reproduzíveis, só análise e
geração de sinais **em memória**: nenhuma chave de API, nenhum envio
de ordem, nenhuma conexão a conta. A execução continua bloqueada
(403) e o scaffold força RESEARCH quando EXECUTION_MODE=LIVE.

Contrato do sinal (compatível com a tabela ``strategy_signals`` da
Fase 2, §9): exchange, market, symbol, timeframe, direction
(``long``/``short``), strategy_id (código, ex.: ``STR-001``) e
``strategy_version``, preço de referência, entrada, stop e alvo,
probabilidade (0..1, nunca acima de 0,85 aqui — a meta de 85% é
objetivo de pesquisa, não promessa), validade (``valid_until_ms``,
derivada do timestamp do último candle, nunca do relógio da máquina),
spread/liquidez quando informados, justificativas (``rationale`` —
sinal sem justificativa **não é emitido**) e status ``DETECTED``.

Como funciona
--------------
- :class:`BaseStrategy`: id, nome, versão, mercados, timeframes,
  parâmetros, filtros globais e o método
  :meth:`BaseStrategy.generate_signals`. Cada subclasse implementa
  :meth:`BaseStrategy._evaluate`, que avalia **só o último candle
  fechado** da série e devolve no máximo um sinal (ou ``None``).
- Reproduzibilidade: mesmos inputs + mesma versão = mesmos sinais.
  Não há aleatoriedade, relógio ou estado mutável entre chamadas;
  ``params`` e ``version`` fazem parte da identidade da versão.
- Filtros globais (aplicados pela base, antes de qualquer emissão):
  regime compatível (cada estratégia declara ``allowed_regimes``),
  spread máximo (quando informado), liquidez mínima (quando
  informada), probabilidade mínima e validade definida. O caminho de
  produção (Fase 14) deve exigir spread **e** liquidez informados —
  ver :meth:`BaseStrategy.check_filters`.
- Registro: :func:`get_strategy` / :func:`list_strategies` devolvem
  as estratégias do catálogo por código e versão.

Estratégias implementadas (STR-001…STR-010, mapeamento da tarefa —
a numeração do §6 difere: STR-008 aqui funde Engulfing + Doji,
STR-009 é o Multi-Timeframe do §6 STR-016 e STR-010 é o Combinador;
ver README):
- STR-001 Trend Following (EMA + ADX + MACD)
- STR-002 Momentum (RSI + ROC + Volume)
- STR-003 Pullback (EMA + VWAP + Price Action)
- STR-004 Breakout (Bollinger + ATR + Volume)
- STR-005 False Breakout (Liquidity Sweep + Rejection)
- STR-006 Mean Reversion (RSI + Bollinger + Z-Score)
- STR-007 Range Trading (Support/Resistance + ADX)
- STR-008 Engulfing/Doji (Engolfo/Doji + Volume + Momentum)
- STR-009 Multi-Timeframe (M15 + M5 + M1)
- STR-010 Combinador de indicadores (confluência ponderada)

STR-011…STR-016 (Wyckoff, ICT Liquidity, VWAP Reversion, Order Flow
Scalping, Volatility Compression, Multi-Timeframe completo do §6)
ficam documentadas como próximas no README, não implementadas aqui.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type

import numpy as np

try:
    import indicators
except ImportError:  # diretório services/indicators fora do sys.path
    sys.path.append(str(Path(__file__).resolve().parents[1] / "indicators"))
    import indicators

try:
    import market_regime as _market_regime
except ImportError:
    try:
        sys.path.append(str(Path(__file__).resolve().parents[1] / "market-regime"))
        import market_regime as _market_regime
    except ImportError:
        _market_regime = None  # type: ignore[assignment]

try:
    import patterns as _patterns
except ImportError:
    try:
        sys.path.append(str(Path(__file__).resolve().parents[1] / "patterns"))
        import patterns as _patterns
    except ImportError:
        _patterns = None  # type: ignore[assignment]

try:
    import structure as _structure
except ImportError:
    try:
        sys.path.append(str(Path(__file__).resolve().parents[1] / "patterns"))
        import structure as _structure
    except ImportError:
        _structure = None  # type: ignore[assignment]

__all__ = [
    "Signal",
    "GlobalFilters",
    "BaseStrategy",
    "TrendFollowingStrategy",
    "MomentumStrategy",
    "PullbackStrategy",
    "BreakoutStrategy",
    "FalseBreakoutStrategy",
    "MeanReversionStrategy",
    "RangeTradingStrategy",
    "EngulfingDojiStrategy",
    "MultiTimeframeStrategy",
    "ConfluenceStrategy",
    "STRATEGY_REGISTRY",
    "get_strategy",
    "list_strategies",
    "COMBINER_WEIGHTS",
    "COMBINER_THRESHOLD",
]

# --- Filtros globais ---------------------------------------------------------
MAX_SPREAD_BPS = 50.0       # spread máximo aceito (quando informado), em bps
MIN_LIQUIDITY_USD = 1_000.0  # liquidez mínima aceita (quando informada), em USD
MIN_PROBABILITY = 0.55      # probabilidade mínima para emitir um sinal
MAX_PROBABILITY = 0.85      # teto: a meta de 85% é objetivo de pesquisa
DEFAULT_VALIDITY_CANDLES = 5  # validade padrão, em candles do timeframe

# Pesos do combinador STR-010 (somam 1,0) — ver README.
COMBINER_WEIGHTS = {
    "trend": 0.25,
    "momentum": 0.25,
    "volatility": 0.20,
    "volume": 0.15,
    "pattern": 0.15,
}
COMBINER_THRESHOLD = 0.50  # |score| >= 0,50 para entrar

TIMEFRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
    "1d": 1440, "1w": 10080,
}


# --- Sinal --------------------------------------------------------------------

@dataclass(frozen=True)
class Signal:
    """Um sinal gerado por uma estratégia (schema de ``strategy_signals``).

    ``rationale`` nunca é vazio: sinal sem justificativa não é emitido
    (a base rejeita). ``valid_until_ms`` é derivado do último candle,
    nunca do relógio — reproduzibilidade.
    """

    exchange: str
    market: str  # "spot" | "perp" | "futures" | "options"
    symbol: str  # normalizado, ex.: "BTC/USDT"
    timeframe: str
    direction: str  # "long" | "short"
    strategy_id: str  # código, ex.: "STR-001"
    strategy_version: int
    reference_price: float
    entry_price: float
    stop_loss: float
    take_profit: float
    probability: float  # 0..1, calibrada na origem (teto 0,85)
    valid_until_ms: int
    rationale: Tuple[str, ...]
    status: str = "DETECTED"
    regime: Optional[str] = None
    spread_bps: Optional[float] = None
    liquidity_usd: Optional[float] = None

    def __post_init__(self) -> None:
        if self.direction not in ("long", "short"):
            raise ValueError(f"direction inválido: {self.direction!r}")
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"probability fora de [0, 1]: {self.probability}")
        if not self.rationale:
            raise ValueError("sinal sem justificativa não pode ser emitido")
        if self.valid_until_ms <= 0:
            raise ValueError("valid_until_ms deve ser definido e > 0")

    def to_dict(self) -> Dict[str, Any]:
        """Dict compatível com a tabela ``strategy_signals`` (Fase 2)."""
        return {
            "exchange": self.exchange,
            "market": self.market,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "reference_price": self.reference_price,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "probability": self.probability,
            "valid_until_ms": self.valid_until_ms,
            "rationale": list(self.rationale),
            "status": self.status,
            "regime": self.regime,
            "spread_bps": self.spread_bps,
            "liquidity_usd": self.liquidity_usd,
        }


@dataclass(frozen=True)
class GlobalFilters:
    """Filtros globais aplicados a todo sinal antes da emissão."""

    max_spread_bps: float = MAX_SPREAD_BPS
    min_liquidity_usd: float = MIN_LIQUIDITY_USD
    min_probability: float = MIN_PROBABILITY
    require_market_data: bool = False  # True no caminho de produção (Fase 14)


# --- Contexto de avaliação ----------------------------------------------------

@dataclass
class _Ctx:
    """Tudo que uma estratégia precisa para avaliar o último candle."""

    candles: list
    computed: Dict[str, Any]
    close: np.ndarray
    high: np.ndarray
    low: np.ndarray
    open_: np.ndarray
    volume: np.ndarray
    patterns: list
    regime: Any  # Regime ou None
    last: int  # índice do último candle

    @property
    def price(self) -> float:
        return float(self.close[self.last])

    @property
    def atr(self) -> float:
        return float(self.computed["atr_14"][self.last])

    def val(self, arr: np.ndarray, idx: Optional[int] = None) -> float:
        """Valor no índice (NaN -> float('nan'), sem levantar)."""
        i = self.last if idx is None else idx
        return float(arr[i])

    def volume_ratio(self, lookback: int = 10) -> float:
        """Volume do último candle / média dos `lookback` anteriores."""
        if self.last < 1:
            return float("nan")
        window = self.volume[max(0, self.last - lookback):self.last]
        avg = float(np.mean(window)) if len(window) else 0.0
        vol = float(self.volume[self.last])
        return vol / avg if avg > 0 else float("nan")

    def patterns_at_last(self, names: Optional[set] = None) -> list:
        """Padrões que terminam no último candle (opcionalmente filtrados)."""
        out = [p for p in self.patterns if getattr(p, "index", None) == self.last]
        if names is not None:
            out = [p for p in out if getattr(p, "name", None) in names]
        return out


# --- Classe base ----------------------------------------------------------------

class BaseStrategy:
    """Base de toda estratégia versionada (STR-001).

    Subclasses definem os atributos de classe (``code``, ``name``,
    ``version``, ``markets``, ``timeframes``, ``params``,
    ``allowed_regimes``, ``min_candles``) e implementam ``_evaluate``.
    """

    code: str = "STR-000"
    name: str = "Base"
    version: int = 1
    markets: Tuple[str, ...] = ("spot",)
    timeframes: Tuple[str, ...] = ("5m", "15m", "1h")
    params: Dict[str, Any] = {}
    allowed_regimes: Optional[frozenset] = None  # None = qualquer regime
    min_candles: int = 50
    status: str = "experimental"  # experimental | testing | approved | disabled

    def __init__(
        self,
        version: Optional[int] = None,
        params: Optional[Dict[str, Any]] = None,
        filters: Optional[GlobalFilters] = None,
        status: Optional[str] = None,
    ) -> None:
        if version is not None:
            if version < 1:
                raise ValueError(f"version deve ser >= 1, recebido {version}")
            self.version = int(version)
        # Parâmetros da versão: cópia fundida (a versão é reproduzível —
        # os params efetivos fazem parte da identidade do sinal).
        merged = dict(type(self).params)
        if params:
            merged.update(params)
        self.params = merged
        self.filters = filters or GlobalFilters()
        if status is not None:
            self.status = status

    # -- identidade / registro -------------------------------------------------
    @property
    def strategy_id(self) -> str:
        return self.code

    def describe(self) -> Dict[str, Any]:
        """Catálogo da estratégia (o que vai para ``strategies`` + versão)."""
        return {
            "code": self.code,
            "name": self.name,
            "version": self.version,
            "markets": list(self.markets),
            "timeframes": list(self.timeframes),
            "params": dict(self.params),
            "allowed_regimes": sorted(self.allowed_regimes) if self.allowed_regimes else None,
            "status": self.status,
        }

    # -- filtros globais ---------------------------------------------------------
    def check_filters(
        self,
        regime_label: Optional[str],
        probability: float,
        spread_bps: Optional[float] = None,
        liquidity_usd: Optional[float] = None,
    ) -> Tuple[bool, List[str]]:
        """Filtros globais: regime, probabilidade, spread e liquidez.

        Spread/liquidez só bloqueiam quando informados — sem dado de
        mercado não há o que filtrar (lab). Com
        ``filters.require_market_data=True`` (caminho de produção,
        Fase 14), a ausência deles também bloqueia.
        """
        reasons: List[str] = []
        if self.status == "disabled":
            reasons.append("estratégia desativada")
        if self.allowed_regimes is not None:
            if regime_label is None:
                reasons.append("regime desconhecido: sem regime compatível")
            elif regime_label not in self.allowed_regimes:
                reasons.append(
                    f"regime {regime_label} incompatível "
                    f"(permitidos: {sorted(self.allowed_regimes)})"
                )
        if probability < self.filters.min_probability:
            reasons.append(
                f"probabilidade {probability:.2f} < mínima {self.filters.min_probability:.2f}"
            )
        if spread_bps is None or liquidity_usd is None:
            if self.filters.require_market_data:
                reasons.append("spread/liquidez não informados (obrigatórios em produção)")
        if spread_bps is not None and spread_bps > self.filters.max_spread_bps:
            reasons.append(
                f"spread {spread_bps:.1f} bps > máximo {self.filters.max_spread_bps:.1f} bps"
            )
        if liquidity_usd is not None and liquidity_usd < self.filters.min_liquidity_usd:
            reasons.append(
                f"liquidez US$ {liquidity_usd:.0f} < mínima US$ {self.filters.min_liquidity_usd:.0f}"
            )
        return (not reasons, reasons)

    # -- pipeline ------------------------------------------------------------------
    def generate_signals(
        self,
        candles: Sequence[Any],
        indicators_cache: Optional[Dict[str, Any]] = None,
        patterns: Optional[list] = None,
        regime: Any = None,
        *,
        symbol: str = "BTC/USDT",
        exchange: str = "binance",
        market: str = "spot",
        timeframe: Optional[str] = None,
        spread_bps: Optional[float] = None,
        liquidity_usd: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Signal]:
        """Gera sinais (no máximo 1, no último candle fechado).

        ``indicators_cache``/``patterns``/``regime`` podem ser passados
        prontos (o chamador reutiliza o cálculo entre estratégias);
        quando ausentes, são calculados aqui. ``context`` carrega dados
        extras por estratégia (ex.: candles de outros timeframes p/
        STR-009). Sem candles suficientes, sem regime compatível ou
        sem setup, devolve ``[]`` — nunca levanta por falta de setup.
        """
        candles = list(candles)
        if len(candles) < self.min_candles:
            return []
        if self.status == "disabled":
            return []
        computed = indicators_cache or indicators.compute_all(candles)
        data = indicators.candles_to_arrays(candles)
        if patterns is None:
            patterns = self._detect_patterns(candles)
        if regime is None:
            regime = self._detect_regime(candles)
        ctx = _Ctx(
            candles=candles,
            computed=computed,
            close=data["close"],
            high=data["high"],
            low=data["low"],
            open_=data["open"],
            volume=data["volume"],
            patterns=patterns or [],
            regime=regime,
            last=len(candles) - 1,
        )
        spec = self._evaluate(ctx, context or {})
        if spec is None:
            return []
        signal = self._build_signal(ctx, spec, symbol, exchange, market,
                                    timeframe or self._timeframe_of(candles),
                                    spread_bps, liquidity_usd)
        return [signal] if signal is not None else []

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Regras da estratégia. Devolve o spec do sinal ou ``None``.

        Spec: ``{"direction", "probability", "rationale": [...],
        "entry"?, "stop_loss"?, "take_profit"?}``. Sem ``stop``/``alvo``,
        a base calcula a partir do ATR (``atr_stop_mult`` x ATR de stop
        e ``risk_reward`` de alvo).
        """
        raise NotImplementedError

    # -- construção do sinal -------------------------------------------------------
    def _build_signal(
        self, ctx: _Ctx, spec: Dict[str, Any], symbol: str, exchange: str,
        market: str, timeframe: str,
        spread_bps: Optional[float], liquidity_usd: Optional[float],
    ) -> Optional[Signal]:
        rationale = [str(r) for r in spec.get("rationale") or []]
        if not rationale:
            return None  # sinal sem justificativa não é emitido
        probability = float(spec.get("probability", 0.0))
        probability = max(0.0, min(MAX_PROBABILITY, probability))
        regime_label = ctx.regime.label if ctx.regime is not None else None
        ok, _reasons = self.check_filters(regime_label, probability, spread_bps, liquidity_usd)
        if not ok:
            return None
        entry = float(spec.get("entry", ctx.price))
        atr = ctx.atr
        stop_mult = float(self.params.get("atr_stop_mult", 1.5))
        rr = float(self.params.get("risk_reward", 2.0))
        direction = spec["direction"]
        if direction == "long":
            stop = float(spec.get("stop_loss", entry - stop_mult * atr))
            target = float(spec.get("take_profit", entry + rr * (entry - stop)))
        else:
            stop = float(spec.get("stop_loss", entry + stop_mult * atr))
            target = float(spec.get("take_profit", entry - rr * (stop - entry)))
        if not (np.isfinite(entry) and np.isfinite(stop) and np.isfinite(target)):
            return None
        validity = int(self.params.get("validity_candles", DEFAULT_VALIDITY_CANDLES))
        tf_minutes = TIMEFRAME_MINUTES.get(timeframe, 5)
        last_close_ms = int(float(ctx.candles[ctx.last].close_time_ms)) \
            if hasattr(ctx.candles[ctx.last], "close_time_ms") \
            else int(ctx.candles[ctx.last]["close_time_ms"])
        valid_until_ms = last_close_ms + validity * tf_minutes * 60_000
        return Signal(
            exchange=exchange,
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            strategy_id=self.code,
            strategy_version=self.version,
            reference_price=round(ctx.price, 6),
            entry_price=round(entry, 6),
            stop_loss=round(stop, 6),
            take_profit=round(target, 6),
            probability=round(probability, 4),
            valid_until_ms=valid_until_ms,
            rationale=tuple(rationale),
            regime=regime_label,
            spread_bps=spread_bps,
            liquidity_usd=liquidity_usd,
        )

    # -- utilidades -------------------------------------------------------------------
    @staticmethod
    def _timeframe_of(candles: Sequence[Any]) -> str:
        first = candles[0]
        tf = getattr(first, "timeframe", None)
        if tf is None and isinstance(first, dict):
            tf = first.get("timeframe")
        return str(tf or "5m")

    @staticmethod
    def _detect_patterns(candles: Sequence[Any]) -> list:
        if _patterns is None:
            return []
        try:
            return _patterns.detect_all(list(candles))
        except Exception:
            return []

    @staticmethod
    def _detect_regime(candles: Sequence[Any]) -> Any:
        if _market_regime is None:
            return None
        try:
            return _market_regime.detect_regime(list(candles))
        except Exception:
            return None

    def _zscore_close(self, ctx: _Ctx, window: int = 20) -> float:
        return float(indicators.zscore(ctx.close, window)[ctx.last])


# --- STR-001 Trend Following ---------------------------------------------------

class TrendFollowingStrategy(BaseStrategy):
    """STR-001 Trend Following — EMA + ADX + MACD (v1).

    Long: EMA20 > EMA50, preço acima da EMA20, ADX >= 25 e MACD acima
    do sinal (histograma > 0). Short: espelho. Só em regime de
    tendência (TREND_UP p/ long, TREND_DOWN p/ short).
    """

    code = "STR-001"
    name = "Trend Following"
    version = 1
    markets = ("spot", "perp", "futures")
    timeframes = ("15m", "1h", "4h")
    params = {"ema_fast": 20, "ema_slow": 50, "adx_min": 25.0,
              "atr_stop_mult": 1.5, "risk_reward": 2.0, "validity_candles": 5}
    allowed_regimes = frozenset({"TREND_UP", "TREND_DOWN", "EXPANSION"})

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ema20 = float(ctx.computed["ema_20"][ctx.last])
        ema50 = float(indicators.ema(ctx.close, 50)[ctx.last])
        adx = float(ctx.computed["dmi"]["adx"][ctx.last])
        macd = ctx.computed["macd"]
        hist = float(macd["histogram"][ctx.last])
        macd_line = float(macd["macd"][ctx.last])
        if any(np.isnan(v) for v in (ema20, ema50, adx, hist, macd_line)):
            return None
        adx_min = float(self.params["adx_min"])
        if (ema20 > ema50 and ctx.price > ema20 and adx >= adx_min
                and hist > 0 and macd_line > 0):
            prob = 0.60 + (0.10 if adx >= 40 else 0.0) + (0.05 if hist > 0.1 * ctx.price / 100 else 0.0)
            return {"direction": "long", "probability": prob, "rationale": [
                f"EMA20 {ema20:.2f} > EMA50 {ema50:.2f}",
                f"preço {ctx.price:.2f} acima da EMA20",
                f"ADX {adx:.1f} >= {adx_min:.0f}",
                f"MACD {macd_line:.3f} acima do sinal (hist {hist:.3f} > 0)",
            ]}
        if (ema20 < ema50 and ctx.price < ema20 and adx >= adx_min
                and hist < 0 and macd_line < 0):
            prob = 0.60 + (0.10 if adx >= 40 else 0.0)
            return {"direction": "short", "probability": prob, "rationale": [
                f"EMA20 {ema20:.2f} < EMA50 {ema50:.2f}",
                f"preço {ctx.price:.2f} abaixo da EMA20",
                f"ADX {adx:.1f} >= {adx_min:.0f}",
                f"MACD {macd_line:.3f} abaixo do sinal (hist {hist:.3f} < 0)",
            ]}
        return None


# --- STR-002 Momentum ----------------------------------------------------------

class MomentumStrategy(BaseStrategy):
    """STR-002 Momentum — RSI + ROC + Volume (v1).

    Long: RSI >= 55, ROC(12) >= 2% e volume >= 1,2x a média.
    Short: RSI <= 45, ROC(12) <= -2% e volume >= 1,2x a média.
    RSI alto não é teto aqui: momentum pode permanecer sobrecomprado.
    """

    code = "STR-002"
    name = "Momentum"
    version = 1
    markets = ("spot", "perp", "futures")
    timeframes = ("5m", "15m", "1h")
    params = {"rsi_period": 14, "rsi_long_min": 55.0, "rsi_short_max": 45.0,
              "roc_period": 12, "roc_min_pct": 2.0, "volume_ratio_min": 1.2,
              "atr_stop_mult": 1.5, "risk_reward": 2.0, "validity_candles": 5}
    allowed_regimes = frozenset({"TREND_UP", "TREND_DOWN", "EXPANSION"})

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rsi = float(ctx.computed["rsi_14"][ctx.last])
        roc = float(ctx.computed["roc_12"][ctx.last])
        vol_ratio = ctx.volume_ratio()
        if any(np.isnan(v) for v in (rsi, roc, vol_ratio)):
            return None
        roc_min = float(self.params["roc_min_pct"])
        vol_min = float(self.params["volume_ratio_min"])
        if (rsi >= float(self.params["rsi_long_min"]) and roc >= roc_min
                and vol_ratio >= vol_min):
            return {"direction": "long", "probability": 0.60 + min(0.10, max(0.0, roc - roc_min) * 0.01),
                    "rationale": [
                        f"RSI {rsi:.1f} >= {self.params['rsi_long_min']:.0f}",
                        f"ROC(12) {roc:.2f}% >= {roc_min:.0f}%",
                        f"volume {vol_ratio:.2f}x a média (>= {vol_min:.1f}x)",
                    ]}
        if (rsi <= float(self.params["rsi_short_max"]) and roc <= -roc_min
                and vol_ratio >= vol_min):
            return {"direction": "short", "probability": 0.60 + min(0.10, max(0.0, -roc - roc_min) * 0.01),
                    "rationale": [
                        f"RSI {rsi:.1f} <= {self.params['rsi_short_max']:.0f}",
                        f"ROC(12) {roc:.2f}% <= -{roc_min:.0f}%",
                        f"volume {vol_ratio:.2f}x a média (>= {vol_min:.1f}x)",
                    ]}
        return None


# --- STR-003 Pullback ----------------------------------------------------------

class PullbackStrategy(BaseStrategy):
    """STR-003 Pullback — EMA + VWAP + Price Action (v1).

    Em tendência de alta (EMA20 > EMA50, ADX >= 20): o preço recuou
    até a EMA20 (ou o VWAP) nos últimos 6 candles e fechou de volta
    acima dela, com candle de recuperação (fechamento > abertura) e
    RSI entre 35 e 85. Short: espelho. Stop abaixo da mínima do
    pullback; alvo 2x o risco.
    """

    code = "STR-003"
    name = "Pullback"
    version = 1
    markets = ("spot", "perp", "futures")
    timeframes = ("5m", "15m", "1h")
    params = {"ema_fast": 20, "ema_slow": 50, "adx_min": 20.0,
              "pullback_bars": 6, "rsi_min": 35.0, "rsi_max": 85.0,
              "atr_stop_mult": 0.5, "risk_reward": 2.0, "validity_candles": 5}
    allowed_regimes = frozenset({"TREND_UP", "TREND_DOWN"})

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ema20 = ctx.computed["ema_20"]
        ema50 = float(indicators.ema(ctx.close, 50)[ctx.last])
        adx = float(ctx.computed["dmi"]["adx"][ctx.last])
        rsi = float(ctx.computed["rsi_14"][ctx.last])
        vwap = float(ctx.computed["vwap"][ctx.last])
        atr = ctx.atr
        if any(np.isnan(v) for v in (ema50, rsi, atr)):
            return None
        adx_eff = adx if not np.isnan(adx) else abs(
            float(ctx.computed["dmi"]["plus_di"][ctx.last])
            - float(ctx.computed["dmi"]["minus_di"][ctx.last]))
        bars = int(self.params["pullback_bars"])
        lo = ctx.last - bars
        if lo < 0:
            return None
        ema20_now = float(ema20[ctx.last])
        recovery = ctx.close[ctx.last] > ctx.open_[ctx.last]
        if (ema20_now > ema50 and adx_eff >= float(self.params["adx_min"])
                and float(self.params["rsi_min"]) <= rsi <= float(self.params["rsi_max"])
                and recovery and ctx.price > ema20_now
                and 0 <= ctx.price - ema20_now <= 1.0 * atr):
            touched = any(
                float(ctx.low[i]) <= float(ema20[i]) or abs(float(ctx.low[i]) - vwap) <= 1.5 * atr
                for i in range(lo, ctx.last + 1)
                if not np.isnan(ema20[i])
            )
            if touched:
                stop = float(np.min(ctx.low[lo:ctx.last + 1])) - 0.5 * atr
                return {"direction": "long", "probability": 0.62,
                        "stop_loss": stop,
                        "take_profit": ctx.price + 2.0 * (ctx.price - stop),
                        "rationale": [
                            f"tendência de alta: EMA20 {ema20_now:.2f} > EMA50 {ema50:.2f}, ADX {adx_eff:.1f}",
                            f"pullback tocou a EMA20/VWAP nos últimos {bars} candles e fechou acima da EMA20",
                            f"candle de recuperação (fechamento {ctx.price:.2f} > abertura {float(ctx.open_[ctx.last]):.2f})",
                            f"RSI {rsi:.1f} entre {self.params['rsi_min']:.0f} e {self.params['rsi_max']:.0f}",
                        ]}
        if (ema20_now < ema50 and adx_eff >= float(self.params["adx_min"])
                and float(self.params["rsi_min"]) <= rsi <= float(self.params["rsi_max"])
                and not recovery and ctx.price < ema20_now
                and 0 <= ema20_now - ctx.price <= 1.0 * atr):
            touched = any(
                float(ctx.high[i]) >= float(ema20[i]) or abs(float(ctx.high[i]) - vwap) <= 1.5 * atr
                for i in range(lo, ctx.last + 1)
                if not np.isnan(ema20[i])
            )
            if touched:
                stop = float(np.max(ctx.high[lo:ctx.last + 1])) + 0.5 * atr
                return {"direction": "short", "probability": 0.62,
                        "stop_loss": stop,
                        "take_profit": ctx.price - 2.0 * (stop - ctx.price),
                        "rationale": [
                            f"tendência de baixa: EMA20 {ema20_now:.2f} < EMA50 {ema50:.2f}, ADX {adx_eff:.1f}",
                            f"pullback tocou a EMA20/VWAP nos últimos {bars} candles e fechou abaixo da EMA20",
                            f"candle de recuperação de baixa (fechamento {ctx.price:.2f} < abertura {float(ctx.open_[ctx.last]):.2f})",
                            f"RSI {rsi:.1f} entre {self.params['rsi_min']:.0f} e {self.params['rsi_max']:.0f}",
                        ]}
        return None


# --- STR-004 Breakout ----------------------------------------------------------

class BreakoutStrategy(BaseStrategy):
    """STR-004 Breakout — Bollinger + ATR + Volume (v1).

    Long: fechamento acima da banda superior de Bollinger **e** acima
    da máxima dos 20 candles anteriores, com volume >= 1,5x a média.
    Short: espelho com a banda inferior. Stop a 1 ATR; alvo 2 ATR.
    """

    code = "STR-004"
    name = "Breakout"
    version = 1
    markets = ("spot", "perp", "futures")
    timeframes = ("5m", "15m", "1h")
    params = {"bollinger_period": 20, "bollinger_std": 2.0, "lookback_high": 20,
              "volume_ratio_min": 1.5, "atr_stop_mult": 1.0,
              "risk_reward": 2.0, "validity_candles": 5}
    allowed_regimes = frozenset({"TREND_UP", "TREND_DOWN", "EXPANSION", "TRANSITION"})
    min_candles = 30

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        bb = ctx.computed["bollinger"]
        upper = float(bb["upper"][ctx.last])
        lower = float(bb["lower"][ctx.last])
        vol_ratio = ctx.volume_ratio()
        if any(np.isnan(v) for v in (upper, lower, vol_ratio)):
            return None
        lookback = int(self.params["lookback_high"])
        prev_high = float(np.max(ctx.high[max(0, ctx.last - lookback):ctx.last])) if ctx.last > 0 else float("nan")
        prev_low = float(np.min(ctx.low[max(0, ctx.last - lookback):ctx.last])) if ctx.last > 0 else float("nan")
        vol_min = float(self.params["volume_ratio_min"])
        if ctx.price > upper and ctx.price > prev_high and vol_ratio >= vol_min:
            return {"direction": "long", "probability": 0.62,
                    "rationale": [
                        f"fechamento {ctx.price:.2f} acima da banda superior {upper:.2f}",
                        f"rompeu a máxima dos últimos {lookback} candles ({prev_high:.2f})",
                        f"volume {vol_ratio:.2f}x a média (>= {vol_min:.1f}x)",
                    ]}
        if ctx.price < lower and ctx.price < prev_low and vol_ratio >= vol_min:
            return {"direction": "short", "probability": 0.62,
                    "rationale": [
                        f"fechamento {ctx.price:.2f} abaixo da banda inferior {lower:.2f}",
                        f"rompeu a mínima dos últimos {lookback} candles ({prev_low:.2f})",
                        f"volume {vol_ratio:.2f}x a média (>= {vol_min:.1f}x)",
                    ]}
        return None


# --- STR-005 False Breakout ----------------------------------------------------

class FalseBreakoutStrategy(BaseStrategy):
    """STR-005 False Breakout — Liquidity Sweep + Rejection (v1).

    Regra objetiva (equivalente a FLOW-005 / ``structure``: pavio além
    de um extremo com fechamento de volta para dentro): o último candle
    varre a mínima (long) ou a máxima (short) dos 20 candles anteriores
    com o pavio e fecha de volta para dentro, com candle de rejeição
    (fechamento na direção da reversão) e volume acima da média.
    Stop além do extremo varrido; alvo 2x o risco.
    """

    code = "STR-005"
    name = "False Breakout"
    version = 1
    markets = ("spot", "perp", "futures")
    timeframes = ("5m", "15m", "1h")
    params = {"lookback": 20, "volume_ratio_min": 1.0,
              "atr_stop_mult": 0.5, "risk_reward": 2.0, "validity_candles": 5}
    allowed_regimes = frozenset({"RANGE", "TREND_UP", "TREND_DOWN", "TRANSITION", "COMPRESSION"})
    min_candles = 30

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        lookback = int(self.params["lookback"])
        if ctx.last < lookback:
            return None
        vol_ratio = ctx.volume_ratio()
        atr = ctx.atr
        if np.isnan(vol_ratio) or np.isnan(atr):
            return None
        prev_low = float(np.min(ctx.low[ctx.last - lookback:ctx.last]))
        prev_high = float(np.max(ctx.high[ctx.last - lookback:ctx.last]))
        low_now, high_now = float(ctx.low[ctx.last]), float(ctx.high[ctx.last])
        vol_min = float(self.params["volume_ratio_min"])
        if (low_now < prev_low and ctx.price > prev_low
                and ctx.price > float(ctx.open_[ctx.last]) and vol_ratio >= vol_min):
            stop = prev_low - 0.5 * atr
            return {"direction": "long", "probability": 0.60,
                    "stop_loss": stop,
                    "take_profit": ctx.price + 2.0 * (ctx.price - stop),
                    "rationale": [
                        f"liquidity sweep: mínima {low_now:.2f} varreu {prev_low:.2f} e fechou de volta acima",
                        f"rejeição: fechamento {ctx.price:.2f} > abertura {float(ctx.open_[ctx.last]):.2f}",
                        f"volume {vol_ratio:.2f}x a média (>= {vol_min:.1f}x)",
                    ]}
        if (high_now > prev_high and ctx.price < prev_high
                and ctx.price < float(ctx.open_[ctx.last]) and vol_ratio >= vol_min):
            stop = prev_high + 0.5 * atr
            return {"direction": "short", "probability": 0.60,
                    "stop_loss": stop,
                    "take_profit": ctx.price - 2.0 * (stop - ctx.price),
                    "rationale": [
                        f"liquidity sweep: máxima {high_now:.2f} varreu {prev_high:.2f} e fechou de volta abaixo",
                        f"rejeição: fechamento {ctx.price:.2f} < abertura {float(ctx.open_[ctx.last]):.2f}",
                        f"volume {vol_ratio:.2f}x a média (>= {vol_min:.1f}x)",
                    ]}
        return None


# --- STR-006 Mean Reversion ----------------------------------------------------

class MeanReversionStrategy(BaseStrategy):
    """STR-006 Mean Reversion — RSI + Bollinger + Z-Score (v1).

    Long: RSI <= 30, %B <= 0,05 (abaixo/na banda inferior) e
    Z-score(20) <= -1,5. Short: RSI >= 70, %B >= 0,95 e Z >= 1,5.
    Contra-tendência por definição: só em RANGE ou COMPRESSION.
    """

    code = "STR-006"
    name = "Mean Reversion"
    version = 1
    markets = ("spot", "perp")
    timeframes = ("5m", "15m", "1h")
    params = {"rsi_period": 14, "rsi_oversold": 30.0, "rsi_overbought": 70.0,
              "zscore_window": 20, "zscore_min": 1.5,
              "atr_stop_mult": 1.5, "risk_reward": 2.0, "validity_candles": 5}
    allowed_regimes = frozenset({"RANGE", "COMPRESSION"})
    min_candles = 30

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rsi = float(ctx.computed["rsi_14"][ctx.last])
        pct_b = float(ctx.computed["bollinger"]["percent_b"][ctx.last])
        z = self._zscore_close(ctx, int(self.params["zscore_window"]))
        if any(np.isnan(v) for v in (rsi, pct_b, z)):
            return None
        z_min = float(self.params["zscore_min"])
        if (rsi <= float(self.params["rsi_oversold"]) and pct_b <= 0.05 and z <= -z_min):
            return {"direction": "long", "probability": 0.60,
                    "rationale": [
                        f"RSI {rsi:.1f} <= {self.params['rsi_oversold']:.0f} (sobrevendido)",
                        f"%B {pct_b:.2f} <= 0,05 (na/abaixo da banda inferior)",
                        f"Z-score {z:.2f} <= -{z_min}",
                    ]}
        if (rsi >= float(self.params["rsi_overbought"]) and pct_b >= 0.95 and z >= z_min):
            return {"direction": "short", "probability": 0.60,
                    "rationale": [
                        f"RSI {rsi:.1f} >= {self.params['rsi_overbought']:.0f} (sobrecomprado)",
                        f"%B {pct_b:.2f} >= 0,95 (na/acima da banda superior)",
                        f"Z-score {z:.2f} >= {z_min}",
                    ]}
        return None


# --- STR-007 Range Trading -----------------------------------------------------

class RangeTradingStrategy(BaseStrategy):
    """STR-007 Range Trading — Support/Resistance + ADX (v1).

    Em regime lateral (ADX efetivo < 25): compra perto do suporte
    (distância <= 1 ATR ou <= 1% do preço) com RSI < 60; venda perto
    da resistência com RSI > 40. Níveis de ``structure.find_levels``
    (mín. 2 toques); sem níveis, usa os extremos dos últimos 30
    candles. Stop além do nível; alvo no nível oposto (ou 2x o risco).
    """

    code = "STR-007"
    name = "Range Trading"
    version = 1
    markets = ("spot", "perp")
    timeframes = ("5m", "15m", "1h")
    params = {"adx_max": 25.0, "level_tol_atr": 1.0, "level_tol_pct": 0.01,
              "lookback": 30, "atr_stop_mult": 0.75,
              "risk_reward": 2.0, "validity_candles": 5}
    allowed_regimes = frozenset({"RANGE", "COMPRESSION"})
    min_candles = 30

    def _levels(self, ctx: _Ctx) -> Tuple[Optional[float], Optional[float]]:
        support = resistance = None
        if _structure is not None:
            try:
                levels = _structure.find_levels(list(ctx.candles))
                supports = [lv.price for lv in levels if lv.kind == "support"]
                resistances = [lv.price for lv in levels if lv.kind == "resistance"]
                if supports:
                    support = max(supports)  # suporte mais próximo por baixo
                if resistances:
                    resistance = min(resistances)
            except Exception:
                pass
        lookback = int(self.params["lookback"])
        if support is None:
            support = float(np.min(ctx.low[max(0, ctx.last - lookback):ctx.last + 1]))
        if resistance is None:
            resistance = float(np.max(ctx.high[max(0, ctx.last - lookback):ctx.last + 1]))
        return support, resistance

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rsi = float(ctx.computed["rsi_14"][ctx.last])
        adx = float(ctx.computed["dmi"]["adx"][ctx.last])
        atr = ctx.atr
        if any(np.isnan(v) for v in (rsi, atr)):
            return None
        adx_eff = adx if not np.isnan(adx) else abs(
            float(ctx.computed["dmi"]["plus_di"][ctx.last])
            - float(ctx.computed["dmi"]["minus_di"][ctx.last]))
        if adx_eff >= float(self.params["adx_max"]):
            return None
        support, resistance = self._levels(ctx)
        if support is None or resistance is None:
            return None
        # Um range precisa ter largura para operar: sem largura mínima
        # (2 ATR ou 2% do preço), uma série plana "vira" range à toa.
        if resistance - support < max(2.0 * atr, 0.02 * ctx.price):
            return None
        tol = max(float(self.params["level_tol_atr"]) * atr,
                  float(self.params["level_tol_pct"]) * ctx.price)
        if support is not None and ctx.price - support <= tol and rsi < 60:
            stop = support - 0.75 * atr
            target = resistance if resistance and resistance > ctx.price else ctx.price + 2.0 * (ctx.price - stop)
            return {"direction": "long", "probability": 0.60,
                    "stop_loss": stop, "take_profit": target,
                    "rationale": [
                        f"preço {ctx.price:.2f} perto do suporte {support:.2f} (dist. {ctx.price - support:.2f} <= {tol:.2f})",
                        f"ADX {adx_eff:.1f} < {self.params['adx_max']:.0f} (lateral)",
                        f"RSI {rsi:.1f} < 60",
                    ]}
        if resistance is not None and resistance - ctx.price <= tol and rsi > 40:
            stop = resistance + 0.75 * atr
            target = support if support and support < ctx.price else ctx.price - 2.0 * (stop - ctx.price)
            return {"direction": "short", "probability": 0.60,
                    "stop_loss": stop, "take_profit": target,
                    "rationale": [
                        f"preço {ctx.price:.2f} perto da resistência {resistance:.2f} (dist. {resistance - ctx.price:.2f} <= {tol:.2f})",
                        f"ADX {adx_eff:.1f} < {self.params['adx_max']:.0f} (lateral)",
                        f"RSI {rsi:.1f} > 40",
                    ]}
        return None


# --- STR-008 Engulfing/Doji ----------------------------------------------------

class EngulfingDojiStrategy(BaseStrategy):
    """STR-008 Engulfing/Doji — Engolfo/Doji + Volume + Momentum (v1).

    Engolfo de alta/baixa no último candle (Fase 10) com volume acima
    da média e momentum a favor (histograma MACD subindo ou RSI entre
    20 e 75); ou doji de reversão (dragonfly/gravestone) com RSI no
    lado favorável. Morning/Evening Star também contam como reversão.
    Padrão isolado não basta (PAT-006): volume e momentum são a
    confirmação mínima exigida aqui.
    """

    code = "STR-008"
    name = "Engulfing/Doji"
    version = 1
    markets = ("spot", "perp", "futures")
    timeframes = ("5m", "15m", "1h")
    params = {"volume_ratio_min": 1.0, "atr_stop_mult": 1.0,
              "risk_reward": 2.0, "validity_candles": 5}
    allowed_regimes = frozenset({"TREND_UP", "TREND_DOWN", "RANGE", "TRANSITION", "COMPRESSION", "EXPANSION"})
    min_candles = 10

    _BULLISH = {"bullish_engulfing", "dragonfly_doji", "morning_star"}
    _BEARISH = {"bearish_engulfing", "gravestone_doji", "evening_star"}

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        vol_ratio = ctx.volume_ratio()
        rsi = float(ctx.computed["rsi_14"][ctx.last])
        hist = ctx.computed["macd"]["histogram"]
        hist_rising = (
            ctx.last >= 1 and not np.isnan(hist[ctx.last]) and not np.isnan(hist[ctx.last - 1])
            and float(hist[ctx.last]) > float(hist[ctx.last - 1])
        )
        hist_falling = (
            ctx.last >= 1 and not np.isnan(hist[ctx.last]) and not np.isnan(hist[ctx.last - 1])
            and float(hist[ctx.last]) < float(hist[ctx.last - 1])
        )
        if np.isnan(vol_ratio) or vol_ratio < float(self.params["volume_ratio_min"]):
            return None
        bullish = ctx.patterns_at_last(self._BULLISH)
        bearish = ctx.patterns_at_last(self._BEARISH)
        momentum_ok_long = hist_rising or (not np.isnan(rsi) and 20 <= rsi <= 75)
        momentum_ok_short = hist_falling or (not np.isnan(rsi) and 25 <= rsi <= 80)
        if bullish and momentum_ok_long:
            names = ", ".join(sorted({p.name for p in bullish}))
            return {"direction": "long", "probability": 0.60,
                    "rationale": [
                        f"padrão de reversão de alta no último candle: {names}",
                        f"volume {vol_ratio:.2f}x a média (>= {self.params['volume_ratio_min']:.1f}x)",
                        f"momentum a favor (hist MACD subindo: {hist_rising}, RSI {rsi:.1f})",
                    ]}
        if bearish and momentum_ok_short:
            names = ", ".join(sorted({p.name for p in bearish}))
            return {"direction": "short", "probability": 0.60,
                    "rationale": [
                        f"padrão de reversão de baixa no último candle: {names}",
                        f"volume {vol_ratio:.2f}x a média (>= {self.params['volume_ratio_min']:.1f}x)",
                        f"momentum a favor (hist MACD caindo: {hist_falling}, RSI {rsi:.1f})",
                    ]}
        return None


# --- STR-009 Multi-Timeframe -----------------------------------------------------

def _aggregate_candles(candles: Sequence[Any], factor: int) -> List[Dict[str, Any]]:
    """Agrega `factor` candles consecutivos em um só (Fase 7: agregação
    de timeframes — open do primeiro, high/low extremos, close do
    último, volume somado). Devolve dicts, que ``compute_all`` aceita.
    """
    out: List[Dict[str, Any]] = []
    rows = list(candles)
    for start in range(0, len(rows) - factor + 1, factor):
        group = rows[start:start + factor]
        def _v(c, name):
            val = getattr(c, name, None)
            return float(val) if val is not None else float(c[name])
        out.append({
            "open": _v(group[0], "open"),
            "high": max(_v(c, "high") for c in group),
            "low": min(_v(c, "low") for c in group),
            "close": _v(group[-1], "close"),
            "volume": sum(_v(c, "volume") for c in group),
            "open_time_ms": _v(group[0], "open_time_ms"),
            "close_time_ms": _v(group[-1], "close_time_ms"),
            "timeframe": "15m",
        })
    return out


class MultiTimeframeStrategy(BaseStrategy):
    """STR-009 Multi-Timeframe — M15 + M5 + M1 (v1).

    Alinhamento: tendência do timeframe maior (M15) + tendência do
    timeframe de execução (M5, a série recebida) + gatilho no
    timeframe menor (M1). Quando ``context`` traz ``{"higher": [...],
    "lower": [...]}`` usam-se os candles reais; sem eles, o timeframe
    maior é derivado por agregação x3 da série (M5 -> M15) e o gatilho
    é o próprio candle de execução (documentado no sinal).
    """

    code = "STR-009"
    name = "Multi-Timeframe"
    version = 1
    markets = ("spot", "perp", "futures")
    timeframes = ("1m", "5m", "15m")
    params = {"higher_factor": 3, "volume_ratio_min": 1.0,
              "atr_stop_mult": 1.5, "risk_reward": 2.0, "validity_candles": 5}
    allowed_regimes = frozenset({"TREND_UP", "TREND_DOWN", "EXPANSION", "TRANSITION"})

    def _trend(self, candles: Sequence[Any]) -> Optional[int]:
        """+1 tendência de alta, -1 de baixa, 0/None sem alinhamento.

        EMA(20) vs EMA(50) quando há ao menos 50 candles; com série
        curta (ex.: M15 agregado a partir de poucos M5), EMA(10) vs
        EMA(20) — a regra é a mesma, só o warm-up muda.
        """
        try:
            data = indicators.candles_to_arrays(candles)
        except Exception:
            return None
        n = len(data["close"])
        fast, slow = (20, 50) if n >= 50 else ((10, 20) if n >= 20 else (None, None))
        if fast is None:
            return None
        ema_fast = indicators.ema(data["close"], fast)
        ema_slow = indicators.ema(data["close"], slow)
        if np.isnan(ema_fast[-1]) or np.isnan(ema_slow[-1]):
            return None
        if ema_fast[-1] > ema_slow[-1] and data["close"][-1] > ema_fast[-1]:
            return 1
        if ema_fast[-1] < ema_slow[-1] and data["close"][-1] < ema_fast[-1]:
            return -1
        return 0

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        higher = context.get("higher") or _aggregate_candles(ctx.candles, int(self.params["higher_factor"]))
        lower = context.get("lower")
        higher_trend = self._trend(higher)
        primary_trend = self._trend(ctx.candles)
        if higher_trend in (None, 0) or primary_trend in (None, 0):
            return None
        if higher_trend != primary_trend:
            return None  # timeframes desalinhados: sem sinal
        vol_ratio = ctx.volume_ratio()
        if np.isnan(vol_ratio) or vol_ratio < float(self.params["volume_ratio_min"]):
            return None
        trigger_up = float(ctx.close[ctx.last]) > float(ctx.open_[ctx.last])
        trigger_down = float(ctx.close[ctx.last]) < float(ctx.open_[ctx.last])
        lower_ok = True
        lower_note = "gatilho no próprio candle de execução (M1 não informado)"
        if lower:
            try:
                ldata = indicators.candles_to_arrays(lower)
                lower_ok = (float(ldata["close"][-1]) > float(ldata["open"][-1])) if higher_trend == 1 \
                    else (float(ldata["close"][-1]) < float(ldata["open"][-1]))
                lower_note = "gatilho M1 confirmado"
            except Exception:
                lower_ok = True
        if higher_trend == 1 and trigger_up and lower_ok:
            return {"direction": "long", "probability": 0.65 if lower else 0.60,
                    "rationale": [
                        "M15 em tendência de alta (EMA20 > EMA50, preço acima da EMA20)",
                        "M5 em tendência de alta (EMA20 > EMA50, preço acima da EMA20)",
                        f"{lower_note}",
                        f"volume {vol_ratio:.2f}x a média",
                    ]}
        if higher_trend == -1 and trigger_down and lower_ok:
            return {"direction": "short", "probability": 0.65 if lower else 0.60,
                    "rationale": [
                        "M15 em tendência de baixa (EMA20 < EMA50, preço abaixo da EMA20)",
                        "M5 em tendência de baixa (EMA20 < EMA50, preço abaixo da EMA20)",
                        f"{lower_note}",
                        f"volume {vol_ratio:.2f}x a média",
                    ]}
        return None


# --- STR-010 Combinador ----------------------------------------------------------

class ConfluenceStrategy(BaseStrategy):
    """STR-010 Combinador de indicadores — confluência ponderada (v1).

    Cada componente vota -1, 0 ou +1; o score é a soma ponderada
    (pesos em :data:`COMBINER_WEIGHTS`, somam 1,0):

    - trend (0,25): EMA20 vs EMA50 e preço vs EMA20;
    - momentum (0,25): RSI acima/abaixo de 50 com histograma MACD;
    - volatility (0,20): %B de Bollinger (> 0,8 / < 0,2);
    - volume (0,15): volume >= 1,5x a média com candle na direção;
    - pattern (0,15): engolfo/estrela/hammer de alta/baixa no último
      candle (Fase 10).

    Entrada: score >= +0,50 (long) ou <= -0,50 (short).
    Probabilidade = 0,50 + 0,30 * |score| (teto 0,85).
    """

    code = "STR-010"
    name = "Combinador de Indicadores"
    version = 1
    markets = ("spot", "perp", "futures")
    timeframes = ("5m", "15m", "1h")
    params = {"weights": dict(COMBINER_WEIGHTS), "threshold": COMBINER_THRESHOLD,
              "volume_ratio_min": 1.5, "atr_stop_mult": 1.5,
              "risk_reward": 2.0, "validity_candles": 5}
    allowed_regimes = frozenset({"TREND_UP", "TREND_DOWN", "RANGE", "EXPANSION", "TRANSITION", "COMPRESSION"})

    def _votes(self, ctx: _Ctx) -> Dict[str, int]:
        ema20 = float(ctx.computed["ema_20"][ctx.last])
        ema50 = float(indicators.ema(ctx.close, 50)[ctx.last])
        rsi = float(ctx.computed["rsi_14"][ctx.last])
        hist = float(ctx.computed["macd"]["histogram"][ctx.last])
        pct_b = float(ctx.computed["bollinger"]["percent_b"][ctx.last])
        vol_ratio = ctx.volume_ratio()
        votes: Dict[str, int] = {}
        if not np.isnan(ema20) and not np.isnan(ema50):
            votes["trend"] = 1 if (ema20 > ema50 and ctx.price > ema20) else (
                -1 if (ema20 < ema50 and ctx.price < ema20) else 0)
        else:
            votes["trend"] = 0
        if not np.isnan(rsi) and not np.isnan(hist):
            votes["momentum"] = 1 if (rsi > 50 and hist > 0) else (
                -1 if (rsi < 50 and hist < 0) else 0)
        else:
            votes["momentum"] = 0
        if not np.isnan(pct_b):
            votes["volatility"] = 1 if pct_b > 0.8 else (-1 if pct_b < 0.2 else 0)
        else:
            votes["volatility"] = 0
        if not np.isnan(vol_ratio) and vol_ratio >= float(self.params["volume_ratio_min"]):
            votes["volume"] = 1 if ctx.price > float(ctx.open_[ctx.last]) else (
                -1 if ctx.price < float(ctx.open_[ctx.last]) else 0)
        else:
            votes["volume"] = 0
        bullish = ctx.patterns_at_last({"bullish_engulfing", "morning_star", "hammer", "dragonfly_doji"})
        bearish = ctx.patterns_at_last({"bearish_engulfing", "evening_star", "hanging_man", "shooting_star", "gravestone_doji"})
        votes["pattern"] = 1 if bullish else (-1 if bearish else 0)
        return votes

    def _evaluate(self, ctx: _Ctx, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        weights = self.params.get("weights", COMBINER_WEIGHTS)
        votes = self._votes(ctx)
        score = sum(float(weights[k]) * votes[k] for k in weights)
        threshold = float(self.params.get("threshold", COMBINER_THRESHOLD))
        if abs(score) < threshold:
            return None
        direction = "long" if score > 0 else "short"
        rationale = [
            f"confluência ponderada: score {score:+.2f} (limiar {threshold:.2f})",
        ]
        labels = {
            "trend": "tendência EMA20/EMA50",
            "momentum": "momentum RSI+MACD",
            "volatility": "volatilidade %B Bollinger",
            "volume": "volume",
            "pattern": "padrão de candle",
        }
        for key in ("trend", "momentum", "volatility", "volume", "pattern"):
            sign = "+" if votes[key] > 0 else ("-" if votes[key] < 0 else "0")
            rationale.append(
                f"{labels[key]}: voto {sign}1 x peso {float(weights[key]):.2f} = {votes[key] * float(weights[key]):+.2f}"
            )
        probability = 0.50 + 0.30 * abs(score)
        return {"direction": direction, "probability": probability, "rationale": rationale}


# --- Registro ----------------------------------------------------------------------

STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {
    cls.code: cls
    for cls in (
        TrendFollowingStrategy,
        MomentumStrategy,
        PullbackStrategy,
        BreakoutStrategy,
        FalseBreakoutStrategy,
        MeanReversionStrategy,
        RangeTradingStrategy,
        EngulfingDojiStrategy,
        MultiTimeframeStrategy,
        ConfluenceStrategy,
    )
}


def get_strategy(code: str, **kwargs: Any) -> BaseStrategy:
    """Instancia uma estratégia do catálogo por código (ex.: ``STR-001``).

    ``version`` e ``params`` vão para o construtor — mudar a versão
    muda ``strategy_version`` no sinal (reprodutibilidade por versão).
    """
    cls = STRATEGY_REGISTRY.get(code)
    if cls is None:
        raise KeyError(f"estratégia desconhecida: {code!r} (catálogo: {sorted(STRATEGY_REGISTRY)})")
    return cls(**kwargs)


def list_strategies() -> List[Dict[str, Any]]:
    """Catálogo de estratégias implementadas (descrição + versão atual)."""
    return [cls().describe() for cls in STRATEGY_REGISTRY.values()]
