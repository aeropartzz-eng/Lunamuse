"""Gerenciador de conexões (Fase 3 — CON-005/CON-006, especificação §5).

Camada de transporte agnóstica: não abre socket nem faz HTTP. O
transporte real (REST/WebSocket da Fase 4) é injetado por callbacks
(``on_connect`` / ``on_disconnect`` / ``on_subscribe``); aqui vive só
a política de resiliência:

- Heartbeat e detecção de feed parado (idade da última mensagem).
- Reconexão exponencial com jitter e recuperação de assinaturas.
- Rate limiting por exchange (token bucket).
- Deduplicação de mensagens (chave + TTL por tamanho limitado).
- Sequenciamento e detecção de gaps por canal.
- Métricas de latência: idade da última mensagem, atraso, contadores.

Relógio, sleep e aleatoriedade são injetáveis para testes
determinísticos (sem rede real). Uma conexão aberta não significa
conexão saudável: :meth:`ConnectionManager.health` mede idade da
última mensagem, sequência, atraso e integridade.
"""

from __future__ import annotations

import random
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from errors import ErrorCode, ExchangeError


# ---------------------------------------------------------------------------
# Backoff exponencial com jitter
# ---------------------------------------------------------------------------

def next_backoff(
    attempt: int,
    *,
    base_s: float = 1.0,
    max_s: float = 60.0,
    factor: float = 2.0,
    jitter: float = 0.25,
    rng: Optional[random.Random] = None,
) -> float:
    """Atraso de reconexão para a tentativa ``attempt`` (0-based).

    ``base * factor**attempt``, limitado a ``max_s``, com jitter
    uniforme de ±``jitter`` fração do valor (ex.: 0.25 = ±25%).
    Com ``rng`` fixo (seed), o resultado é determinístico — usado nos
    testes.
    """
    if attempt < 0:
        raise ValueError("attempt não pode ser negativo")
    delay = min(base_s * (factor ** attempt), max_s)
    source = rng if rng is not None else random
    jitter_amount = delay * jitter * (source.uniform(-1.0, 1.0))
    return max(0.0, delay + jitter_amount)


# ---------------------------------------------------------------------------
# Token bucket (rate limiting por exchange)
# ---------------------------------------------------------------------------

class TokenBucket:
    """Rate limiter token bucket, thread-safe.

    ``rate_per_sec`` tokens entram por segundo, até ``capacity``.
    ``try_acquire`` consome 1 token (ou ``cost``) e retorna False
    quando não há saldo — sem bloquear.
    """

    def __init__(
        self,
        rate_per_sec: float,
        capacity: int,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate_per_sec <= 0 or capacity <= 0:
            raise ValueError("rate_per_sec e capacity devem ser > 0")
        self.rate_per_sec = rate_per_sec
        self.capacity = float(capacity)
        self._tokens = float(capacity)
        self._clock = clock
        self._last_refill = clock()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last_refill)
        self._tokens = min(
            self.capacity, self._tokens + elapsed * self.rate_per_sec
        )
        self._last_refill = now

    def try_acquire(self, cost: int = 1) -> bool:
        """Consome ``cost`` tokens; False se não houver saldo."""
        if cost <= 0:
            raise ValueError("cost deve ser > 0")
        with self._lock:
            self._refill()
            if self._tokens >= cost:
                self._tokens -= cost
                return True
            return False

    def acquire_or_raise(self, cost: int = 1) -> None:
        """Consome tokens ou levanta RATE_LIMIT (retryable)."""
        if not self.try_acquire(cost):
            raise ExchangeError(
                ErrorCode.RATE_LIMIT,
                "rate limit local excedido (token bucket vazio)",
            )

    @property
    def available(self) -> float:
        """Tokens disponíveis no instante (sem consumir)."""
        with self._lock:
            self._refill()
            return self._tokens


# ---------------------------------------------------------------------------
# Deduplicação
# ---------------------------------------------------------------------------

class MessageDeduplicator:
    """Descarta mensagens repetidas por chave, com tamanho limitado.

    Chaves vistas ficam em um OrderedDict (FIFO): quando o limite é
    atingido, a chave mais antiga é esquecida. Retorna True quando a
    chave já foi vista (duplicata) e False na primeira vez.
    """

    def __init__(self, max_size: int = 10_000) -> None:
        if max_size <= 0:
            raise ValueError("max_size deve ser > 0")
        self.max_size = max_size
        self._seen: OrderedDict[Any, None] = OrderedDict()
        self._lock = threading.Lock()

    def is_duplicate(self, key: Any) -> bool:
        """True se a chave já foi vista (duplicata descartada)."""
        with self._lock:
            if key in self._seen:
                self._seen.move_to_end(key)
                return True
            self._seen[key] = None
            while len(self._seen) > self.max_size:
                self._seen.popitem(last=False)
            return False

    def __len__(self) -> int:
        with self._lock:
            return len(self._seen)


# ---------------------------------------------------------------------------
# Sequenciamento / detecção de gaps
# ---------------------------------------------------------------------------

class SequenceStatus(str, Enum):
    """Resultado da checagem de sequência de um canal."""

    OK = "ok"
    DUPLICATE = "duplicate"
    GAP = "gap"
    FIRST = "first"


@dataclass
class SequenceTracker:
    """Rastreia a sequência esperada por canal e detecta gaps.

    A primeira mensagem de um canal estabelece a base (status FIRST).
    Depois: seq == esperado -> OK; seq < esperado -> DUPLICATE;
    seq > esperado -> GAP (conta quantas mensagens faltaram).
    """

    expected: dict[str, int] = field(default_factory=dict)
    gaps: dict[str, int] = field(default_factory=dict)
    gap_events: int = 0

    def check(self, channel: str, sequence: int) -> SequenceStatus:
        """Avalia uma sequência e atualiza o estado do canal."""
        if channel not in self.expected:
            self.expected[channel] = sequence + 1
            return SequenceStatus.FIRST
        expected = self.expected[channel]
        if sequence == expected:
            self.expected[channel] = sequence + 1
            return SequenceStatus.OK
        if sequence < expected:
            return SequenceStatus.DUPLICATE
        missed = sequence - expected
        self.gaps[channel] = self.gaps.get(channel, 0) + missed
        self.gap_events += 1
        self.expected[channel] = sequence + 1
        return SequenceStatus.GAP

    def total_gaps(self) -> int:
        """Total de mensagens faltantes detectadas em todos os canais."""
        return sum(self.gaps.values())


# ---------------------------------------------------------------------------
# Métricas e estado
# ---------------------------------------------------------------------------

class ConnectionState(str, Enum):
    """Estado de uma conexão gerenciada."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DEGRADED = "degraded"


@dataclass
class ConnectionMetrics:
    """Contadores e latência de uma conexão (§5, §16)."""

    messages_received: int = 0
    duplicates_dropped: int = 0
    gaps_detected: int = 0
    reconnects: int = 0
    last_message_at_ms: Optional[int] = None
    last_error: Optional[str] = None

    def last_message_age_ms(self, now_ms: int) -> Optional[int]:
        """Idade da última mensagem em ms (None se nunca houve)."""
        if self.last_message_at_ms is None:
            return None
        return max(0, now_ms - self.last_message_at_ms)


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Gerencia uma conexão de exchange com resiliência (§5).

    O transporte é injetado por callbacks — este gerenciador nunca
    abre socket nem faz HTTP:

    - ``on_connect``: abre a conexão (REST/WS). Pode levantar
      :class:`ExchangeError` para simular falha.
    - ``on_disconnect``: fecha a conexão.
    - ``on_subscribe(channels)``: (re)assina canais; chamado a cada
      (re)conexão para recuperação de assinaturas.

    ``time_fn_ms`` retorna o instante atual em ms UTC (padrão:
    ``time.time() * 1000``); ``sleep_fn`` dorme em segundos (padrão:
    ``time.sleep``). Injetar ambos nos testes para determinismo.
    """

    def __init__(
        self,
        exchange_id: str,
        *,
        rate_per_sec: float = 10.0,
        rate_burst: int = 20,
        heartbeat_interval_ms: int = 30_000,
        max_missed_heartbeats: int = 3,
        backoff_base_s: float = 1.0,
        backoff_max_s: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: float = 0.25,
        dedup_max_size: int = 10_000,
        time_fn_ms: Optional[Callable[[], int]] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        rng: Optional[random.Random] = None,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        on_subscribe: Optional[Callable[[list[str]], None]] = None,
    ) -> None:
        self.exchange_id = exchange_id
        self.state = ConnectionState.DISCONNECTED
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.max_missed_heartbeats = max_missed_heartbeats
        self.backoff_base_s = backoff_base_s
        self.backoff_max_s = backoff_max_s
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self._time_fn_ms = time_fn_ms or (lambda: int(time.time() * 1000))
        self._sleep_fn = sleep_fn
        self._rng = rng if rng is not None else random.Random()
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_subscribe = on_subscribe
        self._attempts = 0
        self._subscriptions: set[str] = set()
        self.rate_limiter = TokenBucket(
            rate_per_sec, rate_burst, clock=time.monotonic
        )
        self.deduplicator = MessageDeduplicator(max_size=dedup_max_size)
        self.sequencer = SequenceTracker()
        self.metrics = ConnectionMetrics()

    # -- ciclo de vida ------------------------------------------------------

    def connect(self) -> None:
        """Abre a conexão e restaura as assinaturas conhecidas."""
        self.state = ConnectionState.CONNECTING
        try:
            if self._on_connect is not None:
                self._on_connect()
        except Exception as exc:
            self.state = ConnectionState.DISCONNECTED
            self.metrics.last_error = str(exc)
            raise
        self.state = ConnectionState.CONNECTED
        self._attempts = 0
        self._restore_subscriptions()

    def disconnect(self) -> None:
        """Fecha a conexão (sem reconectar)."""
        if self._on_disconnect is not None:
            self._on_disconnect()
        self.state = ConnectionState.DISCONNECTED

    def reconnect(self, max_attempts: int = 10) -> bool:
        """Reconecta com backoff exponencial + jitter.

        Retorna True quando a conexão foi restabelecida, False quando
        ``max_attempts`` se esgotou. Cada tentativa falha conta como
        reconexão nas métricas.
        """
        self.state = ConnectionState.RECONNECTING
        for attempt in range(max_attempts):
            delay = next_backoff(
                attempt,
                base_s=self.backoff_base_s,
                max_s=self.backoff_max_s,
                factor=self.backoff_factor,
                jitter=self.jitter,
                rng=self._rng,
            )
            self._sleep_fn(delay)
            try:
                self.connect()
                self.metrics.reconnects += 1
                return True
            except Exception as exc:  # noqa: BLE001 - qualquer falha
                self.metrics.last_error = str(exc)
                self._attempts = attempt + 1
        self.state = ConnectionState.DISCONNECTED
        return False

    def handle_disconnect(self, error: Optional[BaseException] = None) -> bool:
        """Trata uma queda: marca o erro e tenta reconectar."""
        if error is not None:
            self.metrics.last_error = str(error)
        self.state = ConnectionState.RECONNECTING
        return self.reconnect()

    # -- assinaturas ----------------------------------------------------------

    def subscribe(self, channels: list[str]) -> None:
        """Assina canais; a lista é guardada para recuperação."""
        self._subscriptions.update(channels)
        if self.state == ConnectionState.CONNECTED and self._on_subscribe:
            self._on_subscribe(sorted(self._subscriptions))

    def _restore_subscriptions(self) -> None:
        if self._subscriptions and self._on_subscribe is not None:
            self._on_subscribe(sorted(self._subscriptions))

    @property
    def subscriptions(self) -> frozenset[str]:
        """Canais assinados (recuperados a cada reconexão)."""
        return frozenset(self._subscriptions)

    # -- mensagens ------------------------------------------------------------

    def on_message(
        self,
        channel: str,
        *,
        sequence: Optional[int] = None,
        dedup_key: Any = None,
        received_at_ms: Optional[int] = None,
        payload: Any = None,
    ) -> dict[str, Any]:
        """Processa uma mensagem recebida: dedup, sequência, métricas.

        Retorna ``{"status": "accepted"|"duplicate", "gap": bool, ...}``.
        Mensagem duplicada é descartada (não conta como recebida).
        ``payload`` é aceito para futura inspeção; não é interpretado
        aqui.
        """
        now_ms = (
            received_at_ms if received_at_ms is not None else self._now_ms()
        )
        if dedup_key is not None and self.deduplicator.is_duplicate(dedup_key):
            self.metrics.duplicates_dropped += 1
            return {"status": "duplicate", "gap": False, "channel": channel}
        gap = False
        seq_status = None
        if sequence is not None:
            seq_status = self.sequencer.check(channel, sequence)
            if seq_status == SequenceStatus.GAP:
                gap = True
                self.metrics.gaps_detected = self.sequencer.total_gaps()
        self.metrics.messages_received += 1
        self.metrics.last_message_at_ms = now_ms
        return {
            "status": "accepted",
            "gap": gap,
            "sequence_status": seq_status.value if seq_status else None,
            "channel": channel,
        }

    def acquire(self, cost: int = 1) -> None:
        """Consome ``cost`` tokens do rate limiter da exchange."""
        self.rate_limiter.acquire_or_raise(cost)

    # -- saúde / latência ------------------------------------------------------

    def _now_ms(self) -> int:
        return self._time_fn_ms()

    def last_message_age_ms(self) -> Optional[int]:
        """Idade da última mensagem (ms) — métrica de latência (§5)."""
        return self.metrics.last_message_age_ms(self._now_ms())

    def is_stale(self) -> bool:
        """True quando o feed está parado além do limite de heartbeat.

        Sem nenhuma mensagem ainda, considera-se parado (stale).
        """
        age = self.last_message_age_ms()
        if age is None:
            return True
        return age > self.heartbeat_interval_ms * self.max_missed_heartbeats

    def health(self) -> dict[str, Any]:
        """Saúde da conexão: estado, idade da última mensagem, gaps."""
        age = self.last_message_age_ms()
        return {
            "exchange": self.exchange_id,
            "state": self.state.value,
            "connected": self.state == ConnectionState.CONNECTED,
            "last_message_age_ms": age,
            "stale": self.is_stale(),
            "messages_received": self.metrics.messages_received,
            "duplicates_dropped": self.metrics.duplicates_dropped,
            "gaps_detected": self.metrics.gaps_detected,
            "gap_events": self.sequencer.gap_events,
            "reconnects": self.metrics.reconnects,
            "subscriptions": sorted(self._subscriptions),
            "last_error": self.metrics.last_error,
        }
