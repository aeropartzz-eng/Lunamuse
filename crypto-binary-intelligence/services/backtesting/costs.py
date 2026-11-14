"""Modelo de custos do backtest — Fase 12 (BKT-002/BKT-003), §8.

Taxas, spread, slippage, gas (DEX), latência simulada e fills
parciais. Tudo é parâmetro explícito: nenhum custo fica escondido
no motor. Os valores padrão seguem a referência da Fase 12
(ver README do serviço) e são sempre exibidos no relatório.

Convenções
----------
- ``fee_bps``: taxa taker por lado, em basis points do valor
  negociado (ex.: 10 bps = 0,10%).
- ``spread_bps``: spread total (ask - bid) em bps do preço médio.
  Na entrada a mercado paga-se metade do spread; na saída, a outra
  metade. Em saídas por stop/alvo (nível acionado, não abertura de
  mercado) aplica-se só o slippage, não o spread — documentado no
  motor.
- ``slippage_bps``: deslizamento adverso em bps, aplicado a todo
  fill a mercado e a toda saída por stop/alvo.
- ``gas_usd``: custo de gas por ordem, em USD (0 por padrão — só
  faz sentido em DEX; ver Fase 19).
- ``latency_bars``: atraso **extra** em candles além da abertura do
  próximo candle. O sinal do candle ``i`` nunca executa no próprio
  candle ``i`` (sem look-ahead): a execução mais cedo possível é a
  abertura do candle ``i + 1``; ``latency_bars=1`` adia para a
  abertura do candle ``i + 2``.
- ``partial_fill_chunks``: em quantos fills o pedido é dividido
  (1 = fill único). Os chunks executam em candles consecutivos a
  partir do candle de fill, cada um ao preço de abertura do seu
  candle, com custos próprios. Se a série acabar antes de todos os
  chunks, o restante é cancelado e registrado.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "CostModel",
    "DEFAULT_FEE_BPS",
    "DEFAULT_SPREAD_BPS",
    "DEFAULT_SLIPPAGE_BPS",
    "DEFAULT_GAS_USD",
    "DEFAULT_LATENCY_BARS",
    "DEFAULT_PARTIAL_FILL_CHUNKS",
    "bps_to_frac",
    "buy_fill_price",
    "sell_fill_price",
]

# Padrões da Fase 12 (documentados no README do serviço).
DEFAULT_FEE_BPS = 10.0            # 0,10% taker por lado (referência Binance spot)
DEFAULT_SPREAD_BPS = 5.0          # 5 bps de spread total
DEFAULT_SLIPPAGE_BPS = 5.0        # 5 bps de slippage adverso
DEFAULT_GAS_USD = 0.0             # sem gas em CEX; DEX usa valor explícito
DEFAULT_LATENCY_BARS = 0          # fill na abertura do próximo candle
DEFAULT_PARTIAL_FILL_CHUNKS = 1   # fill único por padrão


def bps_to_frac(bps: float) -> float:
    """Basis points -> fração (10 bps = 0,001)."""
    return float(bps) / 10_000.0


@dataclass(frozen=True)
class CostModel:
    """Custos e fricções da simulação (BKT-002/BKT-003)."""

    fee_bps: float = DEFAULT_FEE_BPS
    spread_bps: float = DEFAULT_SPREAD_BPS
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS
    gas_usd: float = DEFAULT_GAS_USD
    latency_bars: int = DEFAULT_LATENCY_BARS
    partial_fill_chunks: int = DEFAULT_PARTIAL_FILL_CHUNKS

    def __post_init__(self) -> None:
        if self.fee_bps < 0:
            raise ValueError("fee_bps não pode ser negativo")
        if self.spread_bps < 0:
            raise ValueError("spread_bps não pode ser negativo")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps não pode ser negativo")
        if self.gas_usd < 0:
            raise ValueError("gas_usd não pode ser negativo")
        if self.latency_bars < 0:
            raise ValueError("latency_bars não pode ser negativo")
        if self.partial_fill_chunks < 1:
            raise ValueError("partial_fill_chunks deve ser >= 1")

    @property
    def fee_frac(self) -> float:
        return bps_to_frac(self.fee_bps)

    @property
    def half_spread_frac(self) -> float:
        return bps_to_frac(self.spread_bps) / 2.0

    @property
    def slippage_frac(self) -> float:
        return bps_to_frac(self.slippage_bps)

    def to_dict(self) -> dict:
        return {
            "fee_bps": self.fee_bps,
            "spread_bps": self.spread_bps,
            "slippage_bps": self.slippage_bps,
            "gas_usd": self.gas_usd,
            "latency_bars": self.latency_bars,
            "partial_fill_chunks": self.partial_fill_chunks,
        }


def buy_fill_price(reference_price: float, costs: CostModel) -> float:
    """Preço de fill de uma compra a mercado na abertura do candle.

    Paga metade do spread + slippage adverso sobre o preço de
    referência (abertura do candle de execução).
    """
    return float(reference_price) * (1.0 + costs.half_spread_frac + costs.slippage_frac)


def sell_fill_price(reference_price: float, costs: CostModel) -> float:
    """Preço de fill de uma venda a mercado na abertura do candle."""
    return float(reference_price) * (1.0 - costs.half_spread_frac - costs.slippage_frac)


def stop_target_exit_price(level_price: float, direction: str, costs: CostModel) -> float:
    """Preço de saída por stop/alvo: o nível acionado, com slippage
    adverso (sem spread — o nível já é o preço de disparo)."""
    if direction == "long":
        return float(level_price) * (1.0 - costs.slippage_frac)
    return float(level_price) * (1.0 + costs.slippage_frac)
