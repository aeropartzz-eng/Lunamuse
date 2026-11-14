"""Motor de backtest — Fase 12 (BKT-001/BKT-002/BKT-003).

Motor próprio, vetorizado onde faz sentido (curva de equity e
métricas usam NumPy) e com loop de eventos sobre os sinais — o
número de sinais é pequeno e o loop deixa cada decisão auditável.
O vectorbt é integrado como backend independente de verificação
cruzada (ver ``vectorbt_adapter.py``): ele não modela latência em
candles, fills parciais, gas nem registro de fill por ordem, que o
§8 exige — por isso o motor canônico é este, e o vectorbt confere
o mesmo fluxo de sinais por outro caminho.

Regras de execução (sem look-ahead)
-----------------------------------
- O sinal do candle ``i`` só pode executar a partir da abertura do
  candle ``i + 1 + latency_bars`` (ver ``costs.CostModel``).
- A entrada é a mercado na abertura do candle de execução, ao preço
  de abertura + metade do spread + slippage adverso (compra) ou o
  espelho (venda). Se o sinal tiver ``valid_until_ms`` e o candle de
  execução fechar depois dele, o sinal expirou e é descartado.
- Fills parciais (``partial_fill_chunks > 1``): o pedido é dividido
  em chunks iguais, executados em candles consecutivos a partir do
  candle de execução, cada um ao preço de abertura do seu candle.
  O restante não executado ao fim da série é cancelado.
- Stop/alvo: verificados na máxima/mínima de cada candle após o
  candle do primeiro fill. Se stop e alvo forem tocados no mesmo
  candle, sai no stop (regra conservadora). A saída é no nível
  acionado, com slippage adverso.
- Uma posição por vez: sinais novos enquanto há posição aberta (ou
  pedido pendente) são contados como ignorados, não executados.
- Ao fim da série, posição aberta é fechada no último fechamento
  (``exit_reason="end_of_data"``) e marcada como tal no trade.
- Tamanho: fração ``position_size_pct`` do patrimônio no momento do
  primeiro fill, dividida pelo preço de referência (abertura do
  candle de execução). Sem alavancagem.

Só simulação: nenhum método aqui envia ordem, conecta a conta ou
usa chave de API. A execução continua bloqueada (403).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from costs import CostModel, buy_fill_price, sell_fill_price, stop_target_exit_price

__all__ = [
    "Fill",
    "Trade",
    "BacktestResult",
    "BacktestEngine",
    "DEFAULT_INITIAL_CAPITAL",
    "DEFAULT_POSITION_SIZE_PCT",
]

DEFAULT_INITIAL_CAPITAL = 10_000.0  # USD (capital fictício da simulação)
DEFAULT_POSITION_SIZE_PCT = 1.0     # 100% do patrimônio por trade


def _get(candle: Any, name: str) -> Any:
    value = getattr(candle, name, None)
    if value is None and isinstance(candle, dict):
        value = candle.get(name)
    return value


def _f(candle: Any, name: str) -> float:
    return float(_get(candle, name))


@dataclass(frozen=True)
class Fill:
    """Um fill (parcial ou total) de uma ordem simulada."""

    fill_id: str
    order_id: str
    index: int  # candle do fill
    timestamp_ms: int
    side: str  # "buy" | "sell"
    price: float  # preço efetivo de fill (já com spread/slippage)
    reference_price: float  # preço de referência (abertura ou nível)
    quantity: float
    fee_usd: float
    slippage_usd: float  # custo adverso vs. referência (>= 0)
    gas_usd: float = 0.0
    status: str = "filled"  # "filled" | "partial"

    @property
    def notional_usd(self) -> float:
        return self.price * self.quantity

    @property
    def total_cost_usd(self) -> float:
        return self.fee_usd + self.slippage_usd + self.gas_usd


@dataclass
class Trade:
    """Um trade fechado (ou aberto ao fim da série)."""

    trade_id: int
    direction: str  # "long" | "short"
    entry_index: int
    exit_index: Optional[int]
    entry_price: float  # preço médio ponderado de entrada
    exit_price: Optional[float]
    quantity: float
    entry_fills: List[Fill] = field(default_factory=list)
    exit_fills: List[Fill] = field(default_factory=list)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    probability: Optional[float] = None  # escore do sinal (não calibrado)
    exit_reason: Optional[str] = None  # "stop" | "target" | "end_of_data"
    open_at_end: bool = False

    @property
    def entry_cost_usd(self) -> float:
        return sum(f.total_cost_usd for f in self.entry_fills)

    @property
    def exit_cost_usd(self) -> float:
        return sum(f.total_cost_usd for f in self.exit_fills)

    @property
    def gross_pnl_usd(self) -> float:
        """PnL bruto (sem custos), None se o trade não fechou."""
        if self.exit_price is None:
            return 0.0
        if self.direction == "long":
            return (self.exit_price - self.entry_price) * self.quantity
        return (self.entry_price - self.exit_price) * self.quantity

    @property
    def net_pnl_usd(self) -> float:
        return self.gross_pnl_usd - self.entry_cost_usd - self.exit_cost_usd

    @property
    def risk_usd(self) -> float:
        """Risco inicial (distância até o stop x quantidade)."""
        if self.stop_loss is None or self.entry_price is None:
            return 0.0
        return abs(self.entry_price - self.stop_loss) * self.quantity

    @property
    def pnl_r(self) -> float:
        """PnL em múltiplos do risco inicial (R)."""
        risk = self.risk_usd
        return self.net_pnl_usd / risk if risk > 0 else 0.0

    @property
    def is_win(self) -> bool:
        return self.net_pnl_usd > 0

    @property
    def holding_bars(self) -> Optional[int]:
        if self.exit_index is None:
            return None
        return self.exit_index - self.entry_index


@dataclass
class BacktestResult:
    """Resultado de um backtest sobre uma série."""

    symbol: str
    strategy_id: str
    strategy_version: int
    initial_capital: float
    final_equity: float
    equity_curve: np.ndarray  # por candle (mark-to-market no close)
    trades: List[Trade] = field(default_factory=list)
    fills: List[Fill] = field(default_factory=list)
    n_signals: int = 0
    n_signals_executed: int = 0
    n_signals_ignored_in_position: int = 0
    n_signals_expired: int = 0
    n_signals_skipped_no_capital: int = 0
    n_signals_cancelled_partial: int = 0
    evaluated_bars: int = 0
    costs: Optional[CostModel] = None
    params: Dict[str, Any] = field(default_factory=dict)
    series_label: str = ""

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def closed_trades(self) -> List[Trade]:
        return [t for t in self.trades if t.exit_index is not None]

    @property
    def total_return_pct(self) -> float:
        if self.initial_capital <= 0:
            return 0.0
        return 100.0 * (self.final_equity - self.initial_capital) / self.initial_capital

    @property
    def execution_rate(self) -> float:
        """Trades executados / sinais gerados."""
        if self.n_signals == 0:
            return 0.0
        return self.n_signals_executed / self.n_signals

    @property
    def total_fees_usd(self) -> float:
        return float(sum(f.fee_usd for f in self.fills))

    @property
    def total_slippage_usd(self) -> float:
        return float(sum(f.slippage_usd for f in self.fills))

    @property
    def total_gas_usd(self) -> float:
        return float(sum(f.gas_usd for f in self.fills))

    @property
    def total_cost_usd(self) -> float:
        return float(sum(f.total_cost_usd for f in self.fills))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "series_label": self.series_label,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "initial_capital": self.initial_capital,
            "final_equity": self.final_equity,
            "total_return_pct": self.total_return_pct,
            "n_trades": self.n_trades,
            "n_signals": self.n_signals,
            "n_signals_executed": self.n_signals_executed,
            "evaluated_bars": self.evaluated_bars,
            "execution_rate": self.execution_rate,
        }


@dataclass
class _PendingOrder:
    signal_index: int
    direction: str
    entry_price_hint: float
    stop_loss: float
    take_profit: float
    probability: Optional[float]
    valid_until_ms: Optional[int]
    fill_bar: int  # primeiro candle de execução
    chunks: int
    chunk_index: int = 0
    quantity: Optional[float] = None  # definida no primeiro fill
    order_id: str = ""


@dataclass
class _OpenPosition:
    trade: Trade
    filled_qty: float = 0.0
    entry_value: float = 0.0  # soma(price*qty) dos fills de entrada
    pending_chunks: int = 0
    pending_order: Optional[_PendingOrder] = None


class BacktestEngine:
    """Simula execução de sinais sobre candles, com custos."""

    def __init__(
        self,
        costs: Optional[CostModel] = None,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        position_size_pct: float = DEFAULT_POSITION_SIZE_PCT,
    ) -> None:
        if initial_capital <= 0:
            raise ValueError("initial_capital deve ser > 0")
        if not 0.0 < position_size_pct <= 1.0:
            raise ValueError("position_size_pct deve estar em (0, 1]")
        self.costs = costs or CostModel()
        self.initial_capital = float(initial_capital)
        self.position_size_pct = float(position_size_pct)

    # -- API principal ------------------------------------------------------
    def run(
        self,
        candles: Sequence[Any],
        signals: Sequence[Any],
        *,
        symbol: str = "BTC/USDT",
        strategy_id: str = "",
        strategy_version: int = 1,
        series_label: str = "",
        evaluated_bars: int = 0,
        params: Optional[Dict[str, Any]] = None,
    ) -> BacktestResult:
        """Roda o backtest.

        ``signals`` aceita ``SeriesSignal`` (de ``signals.py``), dicts
        com ``index``/``direction``/``entry_price``/``stop_loss``/
        ``take_profit``/``probability``/``valid_until_ms``, ou objetos
        ``Signal`` da Fase 11 acompanhados de ``index`` em dict.
        Sinais fora de ordem são ordenados por índice; sinais com
        índice fora da série são descartados.
        """
        candles = list(candles)
        n = len(candles)
        if n == 0:
            raise ValueError("backtest precisa de ao menos 1 candle")
        norm = self._normalize_signals(signals)
        by_index: Dict[int, list] = {}
        for sig in norm:
            if 0 <= sig["index"] < n:
                by_index.setdefault(sig["index"], []).append(sig)

        opens = np.array([_f(c, "open") for c in candles], dtype=float)
        highs = np.array([_f(c, "high") for c in candles], dtype=float)
        lows = np.array([_f(c, "low") for c in candles], dtype=float)
        closes = np.array([_f(c, "close") for c in candles], dtype=float)
        close_ms = np.array([int(_get(c, "close_time_ms") or 0) for c in candles], dtype=np.int64)

        cash = self.initial_capital
        position: Optional[_OpenPosition] = None
        pending: Optional[_PendingOrder] = None
        trades: List[Trade] = []
        fills: List[Fill] = []
        equity = np.empty(n, dtype=float)
        fill_seq = 0
        order_seq = 0
        counters = {
            "executed": 0, "ignored_in_position": 0, "expired": 0,
            "skipped_no_capital": 0, "cancelled_partial": 0,
        }

        def new_fill(order_id, index, side, price, ref, qty, status, gas=0.0):
            nonlocal fill_seq
            fill_seq += 1
            fee = price * qty * self.costs.fee_frac
            slip = abs(price - ref) * qty
            f = Fill(
                fill_id=f"F{fill_seq:06d}",
                order_id=order_id,
                index=index,
                timestamp_ms=int(close_ms[index]),
                side=side,
                price=round(price, 8),
                reference_price=round(ref, 8),
                quantity=qty,
                fee_usd=round(fee, 8),
                slippage_usd=round(slip, 8),
                gas_usd=round(gas, 8),
                status=status,
            )
            fills.append(f)
            return f

        for i in range(n):
            # 1) Novos sinais neste candle: viram pedido pendente (se livre).
            for sig in by_index.get(i, []):
                if position is not None or pending is not None:
                    counters["ignored_in_position"] += 1
                    continue
                order_seq += 1
                pending = _PendingOrder(
                    signal_index=i,
                    direction=sig["direction"],
                    entry_price_hint=sig["entry_price"],
                    stop_loss=sig["stop_loss"],
                    take_profit=sig["take_profit"],
                    probability=sig.get("probability"),
                    valid_until_ms=sig.get("valid_until_ms"),
                    fill_bar=i + 1 + self.costs.latency_bars,
                    chunks=self.costs.partial_fill_chunks,
                    order_id=f"O{order_seq:06d}",
                )

            # 2) Execução de fills (entrada) no candle atual.
            if pending is not None and i >= pending.fill_bar:
                # Expiração: o candle de execução fechou após a validade.
                if pending.valid_until_ms is not None and int(close_ms[i]) > pending.valid_until_ms:
                    counters["expired"] += 1
                    pending = None
                else:
                    if pending.quantity is None:
                        # Sizing no primeiro fill: fração do patrimônio
                        # (aqui igual ao caixa, sem posição aberta),
                        # dimensionada sobre o preço efetivo de fill
                        # para que notional + taxa + gas caiba no
                        # capital alocado.
                        ref0 = opens[i]
                        price0 = buy_fill_price(ref0, self.costs) if pending.direction == "long" \
                            else sell_fill_price(ref0, self.costs)
                        gas0 = self.costs.gas_usd
                        alloc = cash * self.position_size_pct
                        qty_total = max(0.0, (alloc - gas0) / (price0 * (1.0 + self.costs.fee_frac)))
                        pending.quantity = qty_total
                    qty_total = pending.quantity or 0.0
                    remaining_chunks = pending.chunks - pending.chunk_index
                    chunk_qty = qty_total / pending.chunks
                    if pending.chunk_index == pending.chunks - 1:
                        chunk_qty = qty_total - chunk_qty * (pending.chunks - 1)
                    if chunk_qty <= 0:
                        pending = None
                    else:
                        ref = opens[i]
                        price = buy_fill_price(ref, self.costs) if pending.direction == "long" \
                            else sell_fill_price(ref, self.costs)
                        gas = self.costs.gas_usd if pending.chunk_index == 0 else 0.0
                        status = "partial" if remaining_chunks > 1 else "filled"
                        f = new_fill(pending.order_id, i,
                                     "buy" if pending.direction == "long" else "sell",
                                     price, ref, chunk_qty, status, gas=gas)
                        cost = f.notional_usd + f.fee_usd + f.gas_usd
                        if pending.direction == "long" and cost > cash:
                            # Sem capital para este chunk: cancela o
                            # restante do pedido (o que já entrou fica).
                            fills.pop()
                            if position is None:
                                counters["skipped_no_capital"] += 1
                            else:
                                counters["cancelled_partial"] += 1
                                position.pending_order = None
                            pending = None
                        else:
                            if position is None:
                                trade = Trade(
                                    trade_id=len(trades) + 1,
                                    direction=pending.direction,
                                    entry_index=i,
                                    exit_index=None,
                                    entry_price=price,
                                    exit_price=None,
                                    quantity=0.0,
                                    stop_loss=pending.stop_loss,
                                    take_profit=pending.take_profit,
                                    probability=pending.probability,
                                )
                                position = _OpenPosition(trade=trade, pending_order=pending)
                                counters["executed"] += 1
                            if pending.direction == "long":
                                cash -= f.notional_usd + f.fee_usd + f.gas_usd
                            else:
                                cash += f.notional_usd - f.fee_usd - f.gas_usd
                            position.trade.entry_fills.append(f)
                            position.filled_qty += chunk_qty
                            position.entry_value += price * chunk_qty
                            position.trade.quantity = position.filled_qty
                            position.trade.entry_price = (
                                position.entry_value / position.filled_qty
                                if position.filled_qty > 0 else price
                            )
                            position.pending_chunks = remaining_chunks - 1
                            pending.chunk_index += 1
                            if pending.chunk_index >= pending.chunks:
                                position.pending_order = None
                                pending = None
                            else:
                                position.pending_order = pending

            # 3) Stop/alvo na máxima/mínima do candle (só após o candle
            #    do primeiro fill — sem ambiguidade intrabar no fill).
            if position is not None and i > position.trade.entry_index:
                exit_level, reason = self._check_exit(position, highs[i], lows[i])
                if exit_level is not None:
                    cash = self._close_position(
                        position, i, exit_level, reason, new_fill, cash,
                    )
                    trades.append(position.trade)
                    position = None
                    pending = None  # pedido pendente morre com a saída

            # 4) Mark-to-market no fechamento do candle.
            equity[i] = cash + self._position_value(position, closes[i])

        # 5) Fim da série: posição aberta fecha no último close.
        if position is not None:
            trade = position.trade
            if position.pending_order is not None:
                counters["cancelled_partial"] += 1
            exit_price = closes[-1]
            # Saída a mercado no último close (sem spread extra além
            # do slippage, como stop/alvo).
            eff = stop_target_exit_price(exit_price, trade.direction, self.costs)
            order_seq += 1
            exit_id = f"O{order_seq:06d}"
            f = new_fill(exit_id, n - 1,
                         "sell" if trade.direction == "long" else "buy",
                         eff, exit_price, position.filled_qty, "filled")
            trade.exit_fills.append(f)
            trade.exit_index = n - 1
            trade.exit_price = eff
            trade.exit_reason = "end_of_data"
            trade.open_at_end = True
            if trade.direction == "long":
                cash += f.notional_usd - f.fee_usd - f.gas_usd
            else:
                cash -= f.notional_usd + f.fee_usd + f.gas_usd
            trades.append(trade)
            position = None
            equity[-1] = cash
        if pending is not None:
            counters["cancelled_partial"] += 1

        return BacktestResult(
            symbol=symbol,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            initial_capital=self.initial_capital,
            final_equity=float(equity[-1]),
            equity_curve=equity,
            trades=trades,
            fills=fills,
            n_signals=len(norm),
            n_signals_executed=counters["executed"],
            n_signals_ignored_in_position=counters["ignored_in_position"],
            n_signals_expired=counters["expired"],
            n_signals_skipped_no_capital=counters["skipped_no_capital"],
            n_signals_cancelled_partial=counters["cancelled_partial"],
            evaluated_bars=evaluated_bars,
            costs=self.costs,
            params=params or {},
            series_label=series_label,
        )

    # -- auxiliares ---------------------------------------------------------
    def _close_position(self, position, index, level, reason, new_fill, cash):
        """Fecha a posição no nível acionado; devolve o caixa atualizado."""
        trade = position.trade
        eff = stop_target_exit_price(level, trade.direction, self.costs)
        order_id = (position.pending_order.order_id + "-X") if position.pending_order else f"OX{trade.trade_id:06d}"
        f = new_fill(order_id, index,
                     "sell" if trade.direction == "long" else "buy",
                     eff, level, position.filled_qty, "filled")
        trade.exit_fills.append(f)
        trade.exit_index = index
        trade.exit_price = eff
        trade.exit_reason = reason
        if trade.direction == "long":
            cash += f.notional_usd - f.fee_usd - f.gas_usd
        else:
            cash -= f.notional_usd + f.fee_usd + f.gas_usd
        return cash

    @staticmethod
    def _position_value(position: Optional[_OpenPosition], price: float) -> float:
        if position is None or position.filled_qty == 0:
            return 0.0
        # Valor de mercado da posição (long: +qty*price; short: o
        # caixa já recebeu a venda — o valor é -qty*price no equity).
        if position.trade.direction == "long":
            return position.filled_qty * price
        return -position.filled_qty * price

    @staticmethod
    def _check_exit(position: _OpenPosition, high: float, low: float):
        trade = position.trade
        if trade.direction == "long":
            hit_stop = trade.stop_loss is not None and low <= trade.stop_loss
            hit_target = trade.take_profit is not None and high >= trade.take_profit
            if hit_stop:
                return trade.stop_loss, "stop"
            if hit_target:
                return trade.take_profit, "target"
        else:
            hit_stop = trade.stop_loss is not None and high >= trade.stop_loss
            hit_target = trade.take_profit is not None and low <= trade.take_profit
            if hit_stop:
                return trade.stop_loss, "stop"
            if hit_target:
                return trade.take_profit, "target"
        return None, None

    @staticmethod
    def _normalize_signals(signals: Sequence[Any]) -> List[Dict[str, Any]]:
        """Normaliza sinais para dicts ordenados por índice."""
        out: List[Dict[str, Any]] = []
        for s in signals:
            if hasattr(s, "signal"):  # SeriesSignal
                sig = s.signal
                out.append({
                    "index": int(s.index),
                    "direction": sig.direction,
                    "entry_price": float(sig.entry_price),
                    "stop_loss": float(sig.stop_loss),
                    "take_profit": float(sig.take_profit),
                    "probability": float(sig.probability),
                    "valid_until_ms": int(sig.valid_until_ms),
                })
            elif isinstance(s, dict):
                out.append({
                    "index": int(s["index"]),
                    "direction": s["direction"],
                    "entry_price": float(s["entry_price"]),
                    "stop_loss": (float(s["stop_loss"]) if s.get("stop_loss") else None),
                    "take_profit": (float(s["take_profit"]) if s.get("take_profit") else None),
                    "probability": s.get("probability"),
                    "valid_until_ms": s.get("valid_until_ms"),
                })
            else:  # objeto Signal solto: exige .index
                out.append({
                    "index": int(getattr(s, "index")),
                    "direction": s.direction,
                    "entry_price": float(s.entry_price),
                    "stop_loss": float(s.stop_loss),
                    "take_profit": float(s.take_profit),
                    "probability": float(s.probability),
                    "valid_until_ms": int(s.valid_until_ms),
                })
        out.sort(key=lambda d: d["index"])
        return out
