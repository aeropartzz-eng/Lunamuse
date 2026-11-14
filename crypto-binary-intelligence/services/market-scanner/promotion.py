"""Regras de promoção e despromoção entre os níveis (Fase 8 — SCN-004).

Promoção/despromoção automáticas, com thresholds configuráveis e
toda transição registrada com motivo (auditoria). Os números abaixo
são valores iniciais de triagem, escolhidos para serem conservadores
com dados de teste — **não calibrados com dados reais**; a
calibração com o feed ao vivo na VPS é pendência documentada no
README. Histerese: a promoção é imediata quando o sinal é forte, a
despromoção exige ``demote_streak`` avaliações fracas seguidas, para
não ficar oscilando (flapping) a cada candle.

Thresholds (defaults):

- Promoção Discovery -> Active: liquidez estimada >= US$ 50 mil E
  (volume relativo >= 1,5 com |variação| >= 2% OU volume relativo
  >= 3,0 OU volatilidade >= 5% com volume relativo >= 1,2).
- Promoção Active -> Priority: liquidez >= US$ 250 mil E
  (volume relativo >= 3,0 com volatilidade >= 3% OU |imbalance|
  >= 0,6 com spread <= 20 bps).
- Despromoção: liquidez abaixo do mínimo do nível OU (volume
  relativo < 0,8 E |variação| < 1%) por ``demote_streak`` avaliações
  seguidas; Priority despromove também com spread > 100 bps.
- Deep book (order book aprofundado): só os ``MAX_DEEP_BOOK`` (20)
  Priority de maior score; o resto do Priority usa book raso.

Caps de dimensionamento (§4): 200 Active, 50 Priority. Quando a
promoção estouraria o cap, entra o maior score e sai o menor score
do nível (registrado como despromoção por cap).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from scanner import MAX_ACTIVE, MAX_DEEP_BOOK, MAX_PRIORITY

LEVELS = ("discovery", "active", "priority")
ZERO = Decimal("0")


@dataclass
class ScannerThresholds:
    """Thresholds configuráveis de promoção/despromoção (SCN-004)."""

    min_liquidity_active_usd: Decimal = Decimal("50000")
    min_liquidity_priority_usd: Decimal = Decimal("250000")
    promote_rel_volume: Decimal = Decimal("1.5")
    promote_change_pct: Decimal = Decimal("2")
    promote_rel_volume_strong: Decimal = Decimal("3")
    promote_volatility_pct: Decimal = Decimal("5")
    promote_volatility_with_rel_volume: Decimal = Decimal("1.2")
    priority_rel_volume: Decimal = Decimal("3")
    priority_volatility_pct: Decimal = Decimal("3")
    priority_min_imbalance: Decimal = Decimal("0.6")
    priority_max_spread_bps: Decimal = Decimal("20")
    demote_rel_volume: Decimal = Decimal("0.8")
    demote_change_pct: Decimal = Decimal("1")
    demote_spread_bps: Decimal = Decimal("100")
    demote_streak: int = 3


@dataclass
class PromotionEvent:
    """Uma transição de nível, registrada com motivo (auditoria)."""

    exchange: str
    symbol: str
    from_level: str
    to_level: str
    reason: str
    timestamp_ms: int
    score: Decimal = ZERO

    def to_dict(self) -> dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "from_level": self.from_level,
            "to_level": self.to_level,
            "reason": self.reason,
            "timestamp_ms": self.timestamp_ms,
            "score": str(self.score),
        }


@dataclass
class TrackedInstrument:
    """Estado de um instrumento no scanner hierárquico."""

    exchange: str
    symbol: str
    level: str = "discovery"
    score: Decimal = ZERO
    weak_streak: int = 0
    deep_book: bool = False


@dataclass
class PromotionEngine:
    """Avalia métricas e move instrumentos entre os níveis."""

    thresholds: ScannerThresholds = field(default_factory=ScannerThresholds)
    events: list[PromotionEvent] = field(default_factory=list)
    instruments: dict[tuple[str, str], TrackedInstrument] = field(
        default_factory=dict
    )

    # -- registro -----------------------------------------------------------

    def register(self, exchange: str, symbol: str) -> TrackedInstrument:
        key = (exchange, symbol)
        if key not in self.instruments:
            self.instruments[key] = TrackedInstrument(exchange, symbol)
        return self.instruments[key]

    def _move(
        self,
        inst: TrackedInstrument,
        to_level: str,
        reason: str,
        timestamp_ms: int,
    ) -> Optional[PromotionEvent]:
        if inst.level == to_level:
            return None
        event = PromotionEvent(
            exchange=inst.exchange,
            symbol=inst.symbol,
            from_level=inst.level,
            to_level=to_level,
            reason=reason,
            timestamp_ms=timestamp_ms,
            score=inst.score,
        )
        inst.level = to_level
        inst.weak_streak = 0
        self.events.append(event)
        return event

    # -- avaliação ----------------------------------------------------------

    def evaluate(
        self,
        exchange: str,
        symbol: str,
        *,
        timestamp_ms: int,
        score: Decimal = ZERO,
        rel_volume: Optional[Decimal] = None,
        change_pct: Optional[Decimal] = None,
        volatility_pct: Optional[Decimal] = None,
        liquidity_usd: Optional[Decimal] = None,
        spread_bps: Optional[Decimal] = None,
        imbalance: Optional[Decimal] = None,
    ) -> list[PromotionEvent]:
        """Avalia um instrumento e aplica promoção/despromoção.

        Aceita métricas dos três níveis (campos ausentes = None e não
        participam da regra). Retorna os eventos gerados (0, 1 ou 2 —
        um instrumento pode subir dois níveis numa avaliação forte,
        com um evento por transição).
        """
        th = self.thresholds
        inst = self.register(exchange, symbol)
        inst.score = score
        events: list[PromotionEvent] = []
        liq = liquidity_usd if liquidity_usd is not None else ZERO
        rv = rel_volume if rel_volume is not None else ZERO
        chg = abs(change_pct) if change_pct is not None else ZERO
        vol = volatility_pct if volatility_pct is not None else ZERO

        strong_active = (
            liq >= th.min_liquidity_active_usd
            and (
                (rv >= th.promote_rel_volume and chg >= th.promote_change_pct)
                or rv >= th.promote_rel_volume_strong
                or (
                    vol >= th.promote_volatility_pct
                    and rv >= th.promote_volatility_with_rel_volume
                )
            )
        )
        strong_priority = (
            liq >= th.min_liquidity_priority_usd
            and (
                (rv >= th.priority_rel_volume and vol >= th.priority_volatility_pct)
                or (
                    imbalance is not None
                    and abs(imbalance) >= th.priority_min_imbalance
                    and spread_bps is not None
                    and spread_bps <= th.priority_max_spread_bps
                )
            )
        )
        weak = rv < th.demote_rel_volume and chg < th.demote_change_pct
        illiquid = (
            (inst.level == "active" and liq < th.min_liquidity_active_usd)
            or (
                inst.level == "priority"
                and liq < th.min_liquidity_priority_usd
            )
        )
        wide_spread = (
            inst.level == "priority"
            and spread_bps is not None
            and spread_bps > th.demote_spread_bps
        )

        if strong_priority and inst.level != "priority":
            if inst.level == "discovery":
                ev = self._move(
                    inst, "active", "promoção discovery->active (sinal de priority)",
                    timestamp_ms,
                )
                if ev:
                    events.append(ev)
            ev = self._move(
                inst,
                "priority",
                f"promoção para priority: rel_volume={rv} vol={vol}% "
                f"liq=${liq} imbalance={imbalance} spread={spread_bps}bps",
                timestamp_ms,
            )
            if ev:
                events.append(ev)
        elif strong_active and inst.level == "discovery":
            ev = self._move(
                inst,
                "active",
                f"promoção para active: rel_volume={rv} change={chg}% "
                f"vol={vol}% liq=${liq}",
                timestamp_ms,
            )
            if ev:
                events.append(ev)
        elif weak or illiquid or wide_spread:
            inst.weak_streak += 1
            reason = (
                f"despromoção: rel_volume={rv} change={chg}% liq=${liq} "
                f"spread={spread_bps}bps weak_streak={inst.weak_streak}"
            )
            if inst.weak_streak >= th.demote_streak or illiquid or wide_spread:
                target = "discovery" if inst.level == "priority" else "discovery"
                # Priority cai direto para discovery quando ilíquido
                # ou com spread largo; Active cai para discovery.
                ev = self._move(inst, target, reason, timestamp_ms)
                if ev:
                    events.append(ev)
        else:
            inst.weak_streak = 0

        self._enforce_caps(timestamp_ms, events)
        self._assign_deep_book()
        return events

    # -- caps e deep book ----------------------------------------------------

    def _enforce_caps(
        self, timestamp_ms: int, events: list[PromotionEvent]
    ) -> None:
        for level, cap in (("active", MAX_ACTIVE), ("priority", MAX_PRIORITY)):
            members = [
                i for i in self.instruments.values() if i.level == level
            ]
            if len(members) <= cap:
                continue
            members.sort(key=lambda i: i.score)
            for inst in members[: len(members) - cap]:
                ev = self._move(
                    inst,
                    "discovery",
                    f"despromoção por cap de {level} ({cap}): score={inst.score} "
                    "é o menor do nível",
                    timestamp_ms,
                )
                if ev:
                    events.append(ev)

    def _assign_deep_book(self) -> None:
        priority = [
            i for i in self.instruments.values() if i.level == "priority"
        ]
        priority.sort(key=lambda i: i.score, reverse=True)
        for inst in self.instruments.values():
            inst.deep_book = False
        for inst in priority[:MAX_DEEP_BOOK]:
            inst.deep_book = True

    # -- consultas -----------------------------------------------------------

    def by_level(self, level: str) -> list[TrackedInstrument]:
        return [i for i in self.instruments.values() if i.level == level]

    def counts(self) -> dict[str, int]:
        return {level: len(self.by_level(level)) for level in LEVELS}


__all__ = [
    "LEVELS",
    "ScannerThresholds",
    "PromotionEvent",
    "TrackedInstrument",
    "PromotionEngine",
]
