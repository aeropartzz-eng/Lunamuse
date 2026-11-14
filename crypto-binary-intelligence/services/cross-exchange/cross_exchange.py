"""Cross-Exchange Intelligence (Fase 8 — XCH-001…XCH-005).

- XCH-001: normalizar pares equivalentes (``BTC/USDT`` na Binance =
  ``BTC/USDT`` na Bybit, mesmo com códigos nativos diferentes, ex.
  Kraken ``XBT`` -> ``BTC``).
- XCH-002: comparar preços entre exchanges.
- XCH-003: preço de referência ponderado por volume/liquidez.
- XCH-004: detectar divergências.
- XCH-005: simular arbitragem líquida COM custos (taxas de cada
  exchange, transferência, slippage estimado, capital imobilizado).

Somente leitura pública e **simulação**. Nenhuma função aqui envia
ordens, conecta contas ou usa chave de API — arbitragem é calculada,
nunca executada. A execução continua bloqueada (403) e o scaffold
força RESEARCH quando EXECUTION_MODE=LIVE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

# Alias de ativo por exchange (mesma tabela de CON-003, replicada
# aqui para este serviço não depender do sys.path dos conectores).
ASSET_ALIASES: dict[str, dict[str, str]] = {
    "kraken": {"XBT": "BTC", "XDG": "DOGE", "XETH": "ETH"},
    "binance": {},
    "bybit": {},
    "okx": {},
    "coinbase": {},
    "bitget": {},
    "gateio": {},
    "gate": {},
}

QUOTE_CURRENCIES = (
    "USDT", "USDC", "USDD", "FDUSD", "TUSD", "PYUSD", "BUSD", "DAI",
    "USD", "EUR", "GBP", "BRL", "TRY", "BTC", "ETH", "BNB", "SOL",
)

# Taxas taker padrão (planejamento — XCH-005). São defaults
# configuráveis, NÃO cotações ao vivo: cada exchange muda a taxa por
# tier/volume. Confirmar na documentação da exchange antes de usar
# qualquer simulação como base de decisão.
DEFAULT_TAKER_FEES: dict[str, Decimal] = {
    "binance": Decimal("0.001"),
    "bybit": Decimal("0.001"),
    "okx": Decimal("0.001"),
    "coinbase": Decimal("0.006"),
    "kraken": Decimal("0.0026"),
    "bitget": Decimal("0.001"),
    "gateio": Decimal("0.002"),
    "gate": Decimal("0.002"),
}

ZERO = Decimal("0")


def _d(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def canonical_pair(symbol: str, exchange: Optional[str] = None) -> str:
    """Normaliza um par para o canônico ``BASE/QUOTE`` (XCH-001).

    Aceita ``BTC/USDT``, ``BTCUSDT``, ``btc-usdt``, ``BTC_USDT``,
    ``BTC USDT`` e perpétuos (``BTC/USDT:USDT``, ``BTCUSDT-PERP``).
    Aplica alias por exchange (Kraken ``XBT`` -> ``BTC``).
    Levanta ``ValueError`` se não der para separar base/quote.
    """
    raw = symbol.strip().upper()
    settlement = ""
    if ":" in raw:
        raw, settlement = raw.split(":", 1)
    is_perp = raw.endswith("-PERP") or raw.endswith(":PERP")
    raw = raw.removesuffix("-PERP").removesuffix(":PERP")
    for sep in ("/", "-", "_", " ", ":"):
        if sep in raw:
            base, quote = raw.split(sep, 1)
            break
    else:
        base, quote = "", ""
        # Vários quotes podem casar como sufixo ("XBTUSD" termina em
        # "USD" e em "TUSD"); desempata preferindo a base mais longa
        # (quote mais curto) — "XBT"+"USD", não "XB"+"TUSD".
        candidates = [
            q for q in QUOTE_CURRENCIES
            if raw.endswith(q) and len(raw) > len(q)
        ]
        if candidates:
            quote = min(candidates, key=len)
            base = raw[: -len(quote)]
        if not base:
            raise ValueError(f"não foi possível normalizar o par: {symbol!r}")
    aliases = ASSET_ALIASES.get((exchange or "").lower(), {})
    base = aliases.get(base, base)
    quote = aliases.get(quote, quote)
    canonical = f"{base}/{quote}"
    if settlement:
        canonical += f":{aliases.get(settlement, settlement)}"
    elif is_perp:
        canonical += f":{quote}"
    return canonical


def equivalent_pairs(
    symbols: list[str], exchange: Optional[str] = None
) -> dict[str, list[str]]:
    """Agrupa símbolos equivalentes pelo par canônico (XCH-001)."""
    groups: dict[str, list[str]] = {}
    for s in symbols:
        groups.setdefault(canonical_pair(s, exchange), []).append(s)
    return groups


def group_tickers_by_pair(tickers: list[Any]) -> dict[str, list[Any]]:
    """Agrupa tickers de várias exchanges pelo par canônico."""
    groups: dict[str, list[Any]] = {}
    for t in tickers:
        key = canonical_pair(t.symbol, getattr(t, "exchange", None))
        groups.setdefault(key, []).append(t)
    return groups


def reference_price(
    tickers: list[Any], weight_by: str = "volume"
) -> Optional[Decimal]:
    """Preço de referência ponderado por volume/liquidez (XCH-003).

    Peso = ``volume_24h`` do ticker (quando disponível e > 0); sem
    volume, peso igual para todos. Retorna None sem tickers.
    """
    if not tickers:
        return None
    total_weight = ZERO
    weighted = ZERO
    for t in tickers:
        weight = Decimal("1")
        if weight_by == "volume":
            vol = getattr(t, "volume_24h", None)
            if vol is not None and _d(vol) > 0:
                # Pondera por volume em moeda de cotação quando o
                # volume é base: volume × preço aproxima o quote vol.
                weight = _d(vol) * _d(t.last)
        total_weight += weight
        weighted += _d(t.last) * weight
    if total_weight == 0:
        return None
    return weighted / total_weight


@dataclass
class Divergence:
    """Divergência de preço entre exchanges para um par (XCH-004)."""

    pair: str
    reference_price: Decimal
    min_price: Decimal
    min_exchange: str
    max_price: Decimal
    max_exchange: str
    spread_bps: Decimal
    threshold_bps: Decimal
    flagged: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair": self.pair,
            "reference_price": str(self.reference_price),
            "min_price": str(self.min_price),
            "min_exchange": self.min_exchange,
            "max_price": str(self.max_price),
            "max_exchange": self.max_exchange,
            "spread_bps": str(self.spread_bps),
            "threshold_bps": str(self.threshold_bps),
            "flagged": self.flagged,
        }


def compare_prices(tickers: list[Any]) -> dict[str, list[Any]]:
    """XCH-002: tickers agrupados por par canônico, para comparação."""
    return group_tickers_by_pair(tickers)


def detect_divergences(
    tickers: list[Any], threshold_bps: Decimal = Decimal("50")
) -> list[Divergence]:
    """Detecta divergências por par (XCH-004).

    ``spread_bps`` = (max - min) / referência × 10.000. Um par é
    sinalizado quando o spread passa do threshold (default 50 bps =
    0,5%). Divergência é observação, não oportunidade: a arbitragem
    só é avaliada com custos em ``simulate_arbitrage``.
    """
    divergences: list[Divergence] = []
    for pair, group in group_tickers_by_pair(tickers).items():
        if len(group) < 2:
            continue
        ref = reference_price(group)
        if ref is None or ref == 0:
            continue
        cheapest = min(group, key=lambda t: _d(t.last))
        dearest = max(group, key=lambda t: _d(t.last))
        spread = (_d(dearest.last) - _d(cheapest.last)) / ref * Decimal("10000")
        divergences.append(
            Divergence(
                pair=pair,
                reference_price=ref,
                min_price=_d(cheapest.last),
                min_exchange=cheapest.exchange,
                max_price=_d(dearest.last),
                max_exchange=dearest.exchange,
                spread_bps=spread,
                threshold_bps=_d(threshold_bps),
                flagged=spread >= _d(threshold_bps),
            )
        )
    divergences.sort(key=lambda d: d.spread_bps, reverse=True)
    return divergences


@dataclass
class ArbitrageSimulation:
    """Resultado da simulação de arbitragem líquida (XCH-005).

    Só simulação — nunca execução. ``viable`` exige lucro líquido
    positivo E acima de ``min_net_bps``; lucro bruto positivo com
    líquido negativo é rejeitado (``viable=False``).
    """

    pair: str
    buy_exchange: str
    sell_exchange: str
    buy_price: Decimal
    sell_price: Decimal
    quantity: Decimal
    gross_profit_usd: Decimal
    fees_usd: Decimal
    slippage_usd: Decimal
    transfer_fee_usd: Decimal
    net_profit_usd: Decimal
    net_bps: Decimal
    capital_locked_usd: Decimal
    viable: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair": self.pair,
            "buy_exchange": self.buy_exchange,
            "sell_exchange": self.sell_exchange,
            "buy_price": str(self.buy_price),
            "sell_price": str(self.sell_price),
            "quantity": str(self.quantity),
            "gross_profit_usd": str(self.gross_profit_usd),
            "fees_usd": str(self.fees_usd),
            "slippage_usd": str(self.slippage_usd),
            "transfer_fee_usd": str(self.transfer_fee_usd),
            "net_profit_usd": str(self.net_profit_usd),
            "net_bps": str(self.net_bps),
            "capital_locked_usd": str(self.capital_locked_usd),
            "viable": self.viable,
            "reason": self.reason,
        }


@dataclass
class FeeSchedule:
    """Custos usados na simulação (tudo configurável)."""

    taker_fees: dict[str, Decimal] = field(
        default_factory=lambda: dict(DEFAULT_TAKER_FEES)
    )
    transfer_fee_usd: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("10")  # 0,10% estimado por perna
    min_net_bps: Decimal = Decimal("0")

    def taker_fee(self, exchange: str) -> Decimal:
        return self.taker_fees.get(exchange.lower(), Decimal("0.001"))


def simulate_arbitrage(
    pair: str,
    buy_exchange: str,
    sell_exchange: str,
    buy_price: Decimal,
    sell_price: Decimal,
    quantity: Decimal,
    fees: Optional[FeeSchedule] = None,
    transfer_fee_usd: Optional[Decimal] = None,
    slippage_bps: Optional[Decimal] = None,
) -> ArbitrageSimulation:
    """Simula arbitragem líquida entre duas exchanges (XCH-005).

    Custos: taxa taker de compra (buy_price × qty × fee) + taxa taker
    de venda + slippage estimado nas duas pernas + taxa de
    transferência (rede/saque, quando houver). ``capital_locked_usd``
    = custo de compra — o capital imobilizado na perna de compra.
    Não modela tempo de transferência nem risco de execução (o preço
    pode andar enquanto a transferência confirma); por isso a
    simulação é triagem, não garantia.
    """
    fees = fees or FeeSchedule()
    transfer = (
        _d(transfer_fee_usd)
        if transfer_fee_usd is not None
        else fees.transfer_fee_usd
    )
    slip_bps = (
        _d(slippage_bps) if slippage_bps is not None else fees.slippage_bps
    )
    buy_price, sell_price, quantity = _d(buy_price), _d(sell_price), _d(quantity)
    if buy_price <= 0 or sell_price <= 0 or quantity <= 0:
        raise ValueError("preços e quantidade devem ser > 0")
    capital = buy_price * quantity
    gross = (sell_price - buy_price) * quantity
    fee_cost = capital * fees.taker_fee(buy_exchange) + (
        sell_price * quantity
    ) * fees.taker_fee(sell_exchange)
    # Slippage estimado nas duas pernas, sobre o valor negociado.
    slip_cost = (capital + sell_price * quantity) * slip_bps / Decimal("10000")
    net = gross - fee_cost - slip_cost - transfer
    net_bps = (net / capital * Decimal("10000")) if capital > 0 else ZERO
    viable = net > 0 and net_bps >= fees.min_net_bps
    if gross <= 0:
        reason = "sem divergência: preço de venda <= preço de compra"
    elif net <= 0:
        reason = (
            "rejeitada: lucro bruto positivo mas líquido negativo "
            "após taxas, slippage e transferência"
        )
    elif net_bps < fees.min_net_bps:
        reason = "rejeitada: lucro líquido abaixo do mínimo exigido"
    else:
        reason = "viável na simulação (triagem — sem execução)"
    return ArbitrageSimulation(
        pair=pair,
        buy_exchange=buy_exchange,
        sell_exchange=sell_exchange,
        buy_price=buy_price,
        sell_price=sell_price,
        quantity=quantity,
        gross_profit_usd=gross,
        fees_usd=fee_cost,
        slippage_usd=slip_cost,
        transfer_fee_usd=transfer,
        net_profit_usd=net,
        net_bps=net_bps,
        capital_locked_usd=capital,
        viable=viable,
        reason=reason,
    )


def find_arbitrage_opportunities(
    tickers: list[Any],
    quantity: Decimal,
    fees: Optional[FeeSchedule] = None,
) -> list[ArbitrageSimulation]:
    """Varre os pares com 2+ exchanges e simula a melhor arbitragem.

    Para cada par, compra na exchange mais barata e vende na mais
    cara. Retorna simulações ordenadas por lucro líquido.
    """
    results: list[ArbitrageSimulation] = []
    for pair, group in group_tickers_by_pair(tickers).items():
        if len(group) < 2:
            continue
        cheapest = min(group, key=lambda t: _d(t.last))
        dearest = max(group, key=lambda t: _d(t.last))
        if cheapest.exchange == dearest.exchange:
            continue
        results.append(
            simulate_arbitrage(
                pair=pair,
                buy_exchange=cheapest.exchange,
                sell_exchange=dearest.exchange,
                buy_price=_d(cheapest.last),
                sell_price=_d(dearest.last),
                quantity=_d(quantity),
                fees=fees,
            )
        )
    results.sort(key=lambda s: s.net_profit_usd, reverse=True)
    return results


def not_implemented(*args, **kwargs):
    """Compatibilidade com o scaffold: nada aqui ficou pendente."""
    raise NotImplementedError(
        "Cross-Exchange Intelligence implementado na Fase 8; "
        "esta função do scaffold não é mais usada."
    )


__all__ = [
    "ASSET_ALIASES",
    "DEFAULT_TAKER_FEES",
    "canonical_pair",
    "equivalent_pairs",
    "group_tickers_by_pair",
    "reference_price",
    "Divergence",
    "compare_prices",
    "detect_divergences",
    "ArbitrageSimulation",
    "FeeSchedule",
    "simulate_arbitrage",
    "find_arbitrage_opportunities",
]
