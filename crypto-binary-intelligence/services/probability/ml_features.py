"""Feature Store — Fase 13 (ML-001), especificação v4.1 §8.

Constrói a matriz de features para os modelos probabilísticos a
partir de candles OHLCV + indicadores da Fase 9
(:func:`indicators.compute_features`) + regime da Fase 11 +
padrões de candle (geometria simples, PAT-001…PAT-003).

Garantia de não-look-ahead
--------------------------
A feature da linha ``i`` só usa dados até o candle ``i``:

- os indicadores da Fase 9 são sem look-ahead por construção
  (IND-008 — cada valor só usa dados até o seu índice);
- as flags de padrão usam o candle ``i`` e, no máximo, o candle
  ``i - 1`` (engolfo);
- o regime de ``i`` vem de ``market_regime.classify_series``,
  que classifica cada índice só com dados até ele.

O **rótulo** usa o futuro (fechamento ``i + horizon``) — isso é o
alvo a prever, não uma feature; é documentado e nunca entra em ``X``.

Versionamento
-------------
``FEATURE_SET_VERSION`` identifica o conjunto de features. Qualquer
mudança na lista (``FEATURE_NAMES``) exige bump da versão; o
``FeatureStore`` grava a versão junto com os dados.

Armazenamento: em memória (``FeatureStore``) + serialização para
``data/features/`` (``.npz`` + ``.json`` de metadados).

Nenhuma função aqui acessa rede, credenciais ou envia ordens.
"""

from __future__ import annotations

import json
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

try:
    import market_regime as _market_regime
except ImportError:
    try:
        sys.path.append(str(Path(__file__).resolve().parents[1] / "market-regime"))
        import market_regime as _market_regime
    except ImportError:
        _market_regime = None  # type: ignore[assignment]

__all__ = [
    "FEATURE_SET_VERSION",
    "FEATURE_NAMES",
    "FeatureSet",
    "FeatureStore",
    "build_feature_matrix",
    "make_labels",
    "pattern_flags",
]

FEATURE_SET_VERSION = "v1"

# 29 features: 7 de compute_features + 11 indicadores + 5 padrões + 6 regime.
FEATURE_NAMES: List[str] = [
    # IND-007 (compute_features)
    "log_return",
    "realized_vol_20",
    "dist_sma_20",
    "dist_ema_20",
    "zscore_close_20",
    "zscore_volume_20",
    "volume_ratio",
    # Indicadores Fase 9
    "rsi_14",
    "macd_hist",
    "adx_14",
    "atr_pct",
    "bb_percent_b",
    "bb_bandwidth",
    "stoch_k",
    "roc_12",
    "cci_20",
    "mfi_14",
    "dist_vwap_pct",
    # Padrões de candle (geometria; só candle i e i-1)
    "is_doji",
    "is_hammer",
    "is_shooting_star",
    "engulfing_bull",
    "engulfing_bear",
    # Regime (one-hot, Fase 11)
    "regime_TREND_UP",
    "regime_TREND_DOWN",
    "regime_RANGE",
    "regime_COMPRESSION",
    "regime_EXPANSION",
    "regime_TRANSITION",
]

REGIME_LABELS = (
    "TREND_UP",
    "TREND_DOWN",
    "RANGE",
    "COMPRESSION",
    "EXPANSION",
    "TRANSITION",
)


def pattern_flags(
    open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray
) -> Dict[str, np.ndarray]:
    """Flags de padrões de candle (0/1), sem look-ahead.

    Cada flag da linha ``i`` usa só os candles ``i`` e ``i - 1``:

    - ``is_doji``: corpo <= 10% do range;
    - ``is_hammer``: pavio inferior >= 2x o corpo e pavio superior
      <= corpo;
    - ``is_shooting_star``: espelho do hammer no pavio superior;
    - ``engulfing_bull`` / ``engulfing_bear``: corpo de ``i`` engolfa
      o corpo de ``i - 1`` em direção oposta.

    Geometria simplificada (PAT-001…PAT-003); o Pattern Engine
    completo, com confiança e contexto, continua em ``patterns.py``.
    """
    n = len(close)
    body = np.abs(close - open_)
    rng = high - low
    upper_wick = high - np.maximum(open_, close)
    lower_wick = np.minimum(open_, close) - low
    safe_body = np.where(body > 0, body, 1e-12)
    safe_range = np.where(rng > 0, rng, np.nan)

    is_doji = np.where(
        (rng > 0) & (body <= 0.10 * safe_range), 1.0, 0.0
    )
    is_hammer = np.where(
        (lower_wick >= 2.0 * safe_body) & (upper_wick <= safe_body), 1.0, 0.0
    )
    is_shooting = np.where(
        (upper_wick >= 2.0 * safe_body) & (lower_wick <= safe_body), 1.0, 0.0
    )
    eng_bull = np.zeros(n)
    eng_bear = np.zeros(n)
    if n > 1:
        prev_bear = close[:-1] < open_[:-1]
        prev_bull = close[:-1] > open_[:-1]
        cur_bull = close[1:] > open_[1:]
        cur_bear = close[1:] < open_[1:]
        eng_bull[1:] = np.where(
            prev_bear & cur_bull
            & (close[1:] >= open_[:-1]) & (open_[1:] <= close[:-1]),
            1.0, 0.0,
        )
        eng_bear[1:] = np.where(
            prev_bull & cur_bear
            & (close[1:] <= open_[:-1]) & (open_[1:] >= close[:-1]),
            1.0, 0.0,
        )
    return {
        "is_doji": is_doji,
        "is_hammer": is_hammer,
        "is_shooting_star": is_shooting,
        "engulfing_bull": eng_bull,
        "engulfing_bear": eng_bear,
    }


def make_labels(
    close: np.ndarray, horizon: int = 1
) -> Dict[str, np.ndarray]:
    """Rótulo de direção e retorno futuro (o alvo — usa o futuro).

    ``y[i] = 1`` se ``close[i + horizon] > close[i]``, senão ``0``;
    ``future_log_return[i] = ln(close[i+horizon] / close[i])``.
    Linhas sem fechamento futuro (``i + horizon >= n``) recebem
    ``NaN`` e são descartadas na construção da matriz.
    """
    close = np.asarray(close, dtype=float)
    n = len(close)
    y = np.full(n, np.nan)
    fut = np.full(n, np.nan)
    if horizon < 1:
        raise ValueError(f"horizon deve ser >= 1, recebido {horizon}")
    if n > horizon:
        with np.errstate(invalid="ignore", divide="ignore"):
            fut[: n - horizon] = np.where(
                (close[horizon:] > 0) & (close[: n - horizon] > 0),
                np.log(close[horizon:] / close[: n - horizon]),
                np.nan,
            )
        y[: n - horizon] = (close[horizon:] > close[: n - horizon]).astype(float)
    return {"y": y, "future_log_return": fut}


@dataclass
class FeatureSet:
    """Matriz de features + rótulos, já alinhada e sem NaN.

    ``X`` tem uma linha por candle válido; ``row_index`` guarda o
    índice original do candle na série (para rastrear o warm-up
    descartado). ``y`` é o rótulo de direção e ``future_returns``
    o retorno log no horizonte (para expectativa do sinal, ML-007).
    """

    X: np.ndarray
    y: np.ndarray
    future_returns: np.ndarray
    row_index: np.ndarray
    feature_names: List[str] = field(default_factory=lambda: list(FEATURE_NAMES))
    version: str = FEATURE_SET_VERSION
    symbol: str = ""
    timeframe: str = ""
    horizon: int = 1
    n_dropped_nan: int = 0
    n_dropped_no_label: int = 0
    regime_available: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def n_rows(self) -> int:
        return int(self.X.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.X.shape[1])

    def to_metadata(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "feature_names": list(self.feature_names),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "horizon": self.horizon,
            "n_rows": self.n_rows,
            "n_features": self.n_features,
            "n_dropped_nan": self.n_dropped_nan,
            "n_dropped_no_label": self.n_dropped_no_label,
            "regime_available": self.regime_available,
            "positive_rate": float(np.mean(self.y)) if self.n_rows else 0.0,
            **self.metadata,
        }


def build_feature_matrix(
    candles: Sequence[Any],
    horizon: int = 1,
    symbol: str = "",
    timeframe: str = "",
) -> FeatureSet:
    """Constrói a matriz de features (``FEATURE_SET_VERSION``) de uma série.

    Aceita dicts (formato do motor de backtest) ou objetos ``Candle``.
    Linhas com qualquer feature ``NaN`` (warm-up dos indicadores)
    ou sem rótulo futuro são descartadas — os contadores ficam em
    ``n_dropped_nan`` / ``n_dropped_no_label``.
    """
    if len(candles) == 0:
        raise ValueError("candles não pode ser vazio")
    if horizon < 1:
        raise ValueError(f"horizon deve ser >= 1, recebido {horizon}")
    data = indicators.candles_to_arrays(candles)
    o, h, l, c, v = data["open"], data["high"], data["low"], data["close"], data["volume"]
    n = len(c)
    if symbol == "":
        first = candles[0]
        symbol = first.get("symbol", "") if isinstance(first, dict) else getattr(first, "symbol", "")
    if timeframe == "":
        first = candles[0]
        timeframe = first.get("timeframe", "") if isinstance(first, dict) else getattr(first, "timeframe", "")

    feats = indicators.compute_features(c, v)
    macd = indicators.macd(c)
    bb = indicators.bollinger(c)
    stoch = indicators.stochastic(h, l, c)
    dmi = indicators.dmi(h, l, c)
    atr_v = indicators.atr(h, l, c, 14)
    vwap_v = indicators.vwap(h, l, c, v)
    flags = pattern_flags(o, h, l, c)

    columns: Dict[str, np.ndarray] = dict(feats)
    columns.update({
        "rsi_14": indicators.rsi(c, 14),
        "macd_hist": macd["macd"] - macd["signal"],
        "adx_14": dmi["adx"],
        "atr_pct": np.where(c != 0, 100.0 * atr_v / c, np.nan),
        "bb_percent_b": bb["percent_b"],
        "bb_bandwidth": bb["bandwidth"],
        "stoch_k": stoch["k"],
        "roc_12": indicators.roc(c, 12),
        "cci_20": indicators.cci(h, l, c, 20),
        "mfi_14": indicators.mfi(h, l, c, v, 14),
        "dist_vwap_pct": np.where(
            (vwap_v != 0) & ~np.isnan(vwap_v),
            100.0 * (c - vwap_v) / vwap_v, np.nan,
        ),
        **flags,
    })

    # Regime one-hot (Fase 11). Sem look-ahead: classify_series
    # classifica cada índice só com dados até ele. Se a série for
    # curta demais (< 50 candles) ou o módulo indisponível, as
    # colunas ficam em 0 e `regime_available=False`.
    regime_available = False
    regime_cols = {f"regime_{lab}": np.zeros(n) for lab in REGIME_LABELS}
    if _market_regime is not None and n >= 50:
        try:
            regimes = _market_regime.classify_series(candles)
            for reg in regimes:
                if reg.label in REGIME_LABELS:
                    regime_cols[f"regime_{reg.label}"][reg.index] = 1.0
            regime_available = True
        except Exception:
            regime_available = False
    columns.update(regime_cols)

    X_all = np.column_stack([columns[name] for name in FEATURE_NAMES])
    labels = make_labels(c, horizon)
    y_all, fut_all = labels["y"], labels["future_log_return"]

    valid = ~np.isnan(X_all).any(axis=1) & ~np.isnan(y_all) & ~np.isnan(fut_all)
    # Contadores separados: NaN em feature vs. falta de rótulo.
    has_label = ~np.isnan(y_all) & ~np.isnan(fut_all)
    n_dropped_no_label = int((~has_label).sum())
    n_dropped_nan = int((np.isnan(X_all).any(axis=1) & has_label).sum())
    row_index = np.where(valid)[0]
    return FeatureSet(
        X=X_all[valid],
        y=y_all[valid].astype(int),
        future_returns=fut_all[valid],
        row_index=row_index,
        symbol=str(symbol),
        timeframe=str(timeframe),
        horizon=horizon,
        n_dropped_nan=n_dropped_nan,
        n_dropped_no_label=n_dropped_no_label,
        regime_available=regime_available,
    )


class FeatureStore:
    """Feature Store em memória + serialização (ML-001).

    Guarda ``FeatureSet`` por nome (ex.: ``"BTCUSDT-5m-v1"``) e
    persiste cada um como ``<nome>.npz`` + ``<nome>.json``
    (metadados, incluindo a versão do feature set).
    """

    def __init__(self) -> None:
        self._store: Dict[str, FeatureSet] = {}

    def add(self, name: str, feature_set: FeatureSet) -> None:
        if not name:
            raise ValueError("name não pode ser vazio")
        self._store[name] = feature_set

    def get(self, name: str) -> FeatureSet:
        try:
            return self._store[name]
        except KeyError:
            raise KeyError(f"feature set desconhecido: {name!r}") from None

    def list(self) -> List[str]:
        return sorted(self._store)

    def __contains__(self, name: str) -> bool:
        return name in self._store

    def save(self, name: str, directory: str | Path) -> Dict[str, Path]:
        """Serializa um feature set em ``directory`` (.npz + .json)."""
        fs = self.get(name)
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        npz_path = directory / f"{name}.npz"
        json_path = directory / f"{name}.json"
        np.savez_compressed(
            npz_path,
            X=fs.X, y=fs.y,
            future_returns=fs.future_returns,
            row_index=fs.row_index,
        )
        json_path.write_text(
            json.dumps(fs.to_metadata(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return {"npz": npz_path, "json": json_path}

    @classmethod
    def load(cls, name: str, directory: str | Path) -> FeatureSet:
        """Reconstrói um feature set salvo por :meth:`save`."""
        directory = Path(directory)
        data = np.load(directory / f"{name}.npz")
        meta = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
        return FeatureSet(
            X=np.asarray(data["X"], dtype=float),
            y=np.asarray(data["y"], dtype=int),
            future_returns=np.asarray(data["future_returns"], dtype=float),
            row_index=np.asarray(data["row_index"], dtype=int),
            feature_names=list(meta.get("feature_names", FEATURE_NAMES)),
            version=str(meta.get("version", FEATURE_SET_VERSION)),
            symbol=str(meta.get("symbol", "")),
            timeframe=str(meta.get("timeframe", "")),
            horizon=int(meta.get("horizon", 1)),
            n_dropped_nan=int(meta.get("n_dropped_nan", 0)),
            n_dropped_no_label=int(meta.get("n_dropped_no_label", 0)),
            regime_available=bool(meta.get("regime_available", False)),
            metadata={k: v for k, v in meta.items()
                      if k not in {"version", "feature_names", "symbol",
                                   "timeframe", "horizon", "n_rows",
                                   "n_features", "n_dropped_nan",
                                   "n_dropped_no_label", "regime_available",
                                   "positive_rate"}},
        )
