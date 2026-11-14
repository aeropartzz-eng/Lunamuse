"""Adaptador base sobre CCXT para conectores CEX públicos (Fase 5).

Camada 2 — Ingestão (especificação v4.1, CEX-007…CEX-010, CEX-012).

Implementa o contrato :class:`base.ExchangeAdapter` sobre a API
unificada do CCXT, **somente em modo público, sem nenhuma credencial**:

- Nenhuma chave de API, segredo ou senha é passada ao CCXT — a
  configuração pública está em :meth:`CCXTAdapter.public_config` e os
  testes verificam que ela não contém credenciais.
- Nenhum método envia ordens (não existe método de execução aqui); a
  execução real continua bloqueada (403) e o scaffold força RESEARCH
  quando ``EXECUTION_MODE=LIVE``.
- Símbolos e timestamps são normalizados com :mod:`normalization`
  (canônico ``BASE/QUOTE``, ms UTC); o payload original é preservado
  em ``raw`` (CEX-005).
- Latência de cada chamada é medida e gaps de candles são detectados
  e expostos em :meth:`health` (§5, CEX-006).
- Rate limiting local via :class:`connection.ConnectionManager`
  (token bucket por exchange, CEX-012); erros do CCXT são traduzidos
  para :class:`errors.ExchangeError` com código estável (CON-004).

O CCXT é importado **preguiçosamente** (só dentro de
:meth:`CCXTAdapter._build_ccxt_exchange`), para que o módulo — e a
suíte de testes, que injeta um exchange falso — funcione sem o CCXT
instalado. Para uso real: ``pip install ccxt`` (ver
``requirements.txt`` neste diretório) ou o venv do projeto.

Conectores concretos (um por exchange) herdam daqui e só definem os
atributos de classe: ``ccxt_id``, ``rate_per_sec`` / ``rate_burst``,
``supports_funding`` / ``supports_open_interest`` e ``default_type``.

Particularidades tratadas aqui e nos adapters concretos:

- Kraken usa alias de símbolos (``XBT`` → ``BTC``, ``XDG`` → ``DOGE``)
  — a tabela vive em :mod:`normalization` (``ASSET_ALIASES``) e é
  aplicada em todos os métodos.
- Coinbase aqui é o **Coinbase Advanced Trade** (id CCXT
  ``coinbase``, API em ``api.coinbase.com``), não o Coinbase comum.
- Bitget e Gate.io têm futuros/perpétuos: funding rate e open
  interest usam o símbolo swap canônico ``BASE/QUOTE:USDT``.
- Funding rate / open interest indisponível numa exchange levanta
  :class:`errors.ExchangeError` (``BAD_RESPONSE``, não retryable) com
  mensagem clara — o dado nunca é inventado.
- Timeframes: além de :func:`normalization.validate_timeframe`
  (rejeita granularidade inventada), o timeframe precisa estar entre
  os suportados pela exchange (``exchange.timeframes`` do CCXT); cada
  exchange cobre um subconjunto diferente (ver README de cada
  conector).
"""

from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from base import ExchangeAdapter
from connection import ConnectionManager
from envelope import ResponseEnvelope  # noqa: F401  (re-export p/ adapters)
from errors import ErrorCode, ExchangeError, error_from_http_status
from models import (
    Candle,
    FundingRate,
    Market,
    OpenInterest,
    OrderBook,
    Ticker,
    Trade,
)
from normalization import (
    canonical_asset,
    normalize_side,
    normalize_symbol,
    normalize_timestamp,
    validate_timeframe,
)

# Duração de cada timeframe em milissegundos (para close_time de
# candles e detecção de gaps — CEX-006). Só timeframes reais (§3).
TIMEFRAME_MS: dict[str, int] = {
    "1s": 1_000,
    "5s": 5_000,
    "15s": 15_000,
    "30s": 30_000,
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "1w": 604_800_000,
}

# Tradução de exceções do CCXT por nome de classe (duck typing): os
# testes injetam um exchange falso e não importam o CCXT, por isso a
# tradução não pode depender de ``isinstance(exc, ccxt.X)``.
_CCXT_ERROR_CODES: dict[str, ErrorCode] = {
    "RateLimitExceeded": ErrorCode.RATE_LIMIT,
    "DDoSProtection": ErrorCode.RATE_LIMIT,
    "RequestTimeout": ErrorCode.TIMEOUT,
    "NetworkError": ErrorCode.CONNECTION_LOST,
    "ExchangeNotAvailable": ErrorCode.CONNECTION_LOST,
    "BadSymbol": ErrorCode.INVALID_SYMBOL,
    "BadRequest": ErrorCode.INVALID_SYMBOL,
    "NotSupported": ErrorCode.BAD_RESPONSE,
    "BadResponse": ErrorCode.BAD_RESPONSE,
    "ExchangeError": ErrorCode.BAD_RESPONSE,
    "AuthenticationError": ErrorCode.BAD_RESPONSE,
}

_CREDENTIAL_KEYS = frozenset(
    {"apiKey", "secret", "password", "uid", "privateKey", "accessToken"}
)


def _to_decimal(value: Any, field: str) -> Decimal:
    """Converte um número da fonte para Decimal (via str, sem float)."""
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ExchangeError(
            ErrorCode.BAD_RESPONSE,
            f"valor numérico inválido em {field}: {value!r}",
        ) from exc
    return result


class CCXTAdapter(ExchangeAdapter):
    """Adapter público sobre CCXT (sem credenciais, sem ordens).

    Subclasses definem apenas atributos de classe; toda a lógica vive
    aqui. O exchange CCXT pode ser injetado (``exchange=`` — usado
    pelos testes, com um fake) ou construído preguiçosamente em
    :meth:`connect` / no primeiro ``fetch_*``.
    """

    # -- atributos definidos por cada conector concreto -------------------
    ccxt_id: str = ""  # id do CCXT, ex.: "kraken", "coinbase"
    rate_per_sec: float = 10.0  # limite local (token bucket, CEX-012)
    rate_burst: int = 20
    supports_funding: bool = False  # has.fetchFundingRate no CCXT
    supports_open_interest: bool = False  # has.fetchOpenInterest
    default_type: str = "spot"  # tipo padrão de mercado do CCXT

    def __init__(
        self,
        exchange: Any = None,
        *,
        rate_per_sec: Optional[float] = None,
        rate_burst: Optional[int] = None,
    ) -> None:
        """Constrói o adapter.

        ``exchange`` injeta o exchange CCXT (ou um fake, nos testes).
        ``rate_per_sec`` / ``rate_burst`` sobrescrevem os limites
        locais da classe (útil em testes e em tuning de produção).
        """
        self._exchange = exchange
        self._connected = False
        self._calls_total = 0
        self._errors_total = 0
        self._gaps_detected = 0
        self._latency_last_ms: dict[str, float] = {}
        self._latency_sum_ms: dict[str, float] = {}
        self._latency_count: dict[str, int] = {}
        self.manager = ConnectionManager(
            self.exchange_id,
            rate_per_sec=(
                self.rate_per_sec if rate_per_sec is None else rate_per_sec
            ),
            rate_burst=(
                self.rate_burst if rate_burst is None else rate_burst
            ),
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
        )

    # -- configuração pública (sem credenciais) -----------------------------

    def public_config(self) -> dict[str, Any]:
        """Configuração passada ao construtor do CCXT.

        Somente opções públicas. Nenhuma credencial: sem ``apiKey``,
        ``secret``, ``password`` ou ``uid`` — os testes verificam isso.
        """
        return {
            "enableRateLimit": True,
            "options": {"defaultType": self.default_type},
        }

    def _build_ccxt_exchange(self) -> Any:
        """Constrói o exchange CCXT real (import preguiçoso)."""
        try:
            import ccxt  # noqa: PLC0415 - import local de propósito
        except ImportError as exc:
            raise ExchangeError(
                ErrorCode.UNKNOWN,
                f"ccxt não instalado — instalar com `pip install ccxt` "
                f"(requirements.txt). Exchange: {self.exchange_id}",
                exchange=self.exchange_id,
            ) from exc
        if not self.ccxt_id or not hasattr(ccxt, self.ccxt_id):
            raise ExchangeError(
                ErrorCode.UNKNOWN,
                f"id CCXT desconhecido para {self.exchange_id}: "
                f"{self.ccxt_id!r}",
                exchange=self.exchange_id,
            )
        return getattr(ccxt, self.ccxt_id)(self.public_config())

    def _ensure_exchange(self) -> Any:
        if self._exchange is None:
            self._exchange = self._build_ccxt_exchange()
        return self._exchange

    # -- ciclo de vida ---------------------------------------------------------

    def _on_connect(self) -> None:
        """Callback do ConnectionManager: carrega mercados (público)."""
        exchange = self._ensure_exchange()
        load_markets = getattr(exchange, "load_markets", None)
        if callable(load_markets):
            self._translate_errors("load_markets", load_markets)

    def _on_disconnect(self) -> None:
        close = getattr(self._exchange, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001 - fechar não pode falhar
                pass

    def connect(self) -> None:
        """Abre a conexão gerenciada e carrega os mercados públicos."""
        self._ensure_exchange()
        self.manager.connect()
        self._connected = True

    def disconnect(self) -> None:
        """Fecha a conexão gerenciada (sem reconectar)."""
        self.manager.disconnect()
        self._connected = False

    def health(self) -> dict[str, Any]:
        """Saúde: estado, latência por método, gaps, chamadas, erros."""
        base = self.manager.health()
        base.update(
            {
                "exchange": self.exchange_id,
                "ccxt_id": self.ccxt_id,
                "connected": self._connected
                and base.get("connected", False),
                "latency_ms": dict(self._latency_last_ms),
                "latency_avg_ms": {
                    method: round(total / self._latency_count[method], 2)
                    for method, total in self._latency_sum_ms.items()
                },
                "calls": self._calls_total,
                "errors": self._errors_total,
                "gaps_detected": self._gaps_detected,
                "supports_funding": self.supports_funding,
                "supports_open_interest": self.supports_open_interest,
            }
        )
        return base

    def subscribe(self, channels: list[str]) -> None:
        """Registra canais para recuperação futura (Fase 7 — WS).

        O streaming WebSocket ao vivo ainda não existe nesta fase; as
        chamadas REST abaixo são polling. Os canais ficam guardados no
        ConnectionManager e serão restaurados quando o WS chegar.
        """
        self.manager.subscribe(channels)

    # -- infra de chamada -------------------------------------------------------

    def _translate_errors(self, method: str, func: Any, *args: Any,
                          **kwargs: Any) -> Any:
        """Executa ``func`` traduzindo exceções do CCXT/HTTP.

        Erros de rede do CCXT chegam como classes do próprio CCXT; sem
        importar o CCXT aqui, a tradução usa o nome da classe e, quando
        presente, o ``httpStatusCode`` do erro.
        """
        try:
            return func(*args, **kwargs)
        except ExchangeError:
            raise
        except Exception as exc:  # noqa: BLE001 - tradução genérica
            status = getattr(exc, "httpStatusCode", None)
            if isinstance(status, int):
                raise error_from_http_status(
                    status,
                    f"{self.name}: {method} falhou (HTTP {status}): {exc}",
                    exchange=self.exchange_id,
                ) from exc
            code = _CCXT_ERROR_CODES.get(type(exc).__name__)
            if code is not None:
                raise ExchangeError(
                    code,
                    f"{self.name}: {method} falhou: {exc}",
                    exchange=self.exchange_id,
                ) from exc
            raise ExchangeError(
                ErrorCode.UNKNOWN,
                f"{self.name}: {method} falhou "
                f"({type(exc).__name__}: {exc})",
                exchange=self.exchange_id,
            ) from exc

    def _call(self, method: str, func: Any, *args: Any,
              **kwargs: Any) -> Any:
        """Chamada pública com rate limit local + medição de latência.

        Registra a mensagem no ConnectionManager (idade da última
        mensagem, contadores) e guarda a latência para :meth:`health`.
        """
        self.manager.acquire()  # token bucket; RATE_LIMIT se vazio
        started = time.monotonic()
        try:
            result = self._translate_errors(method, func, *args, **kwargs)
        except ExchangeError:
            self._errors_total += 1
            raise
        finally:
            elapsed_ms = (time.monotonic() - started) * 1000.0
            self._calls_total += 1
            self._latency_last_ms[method] = round(elapsed_ms, 2)
            self._latency_sum_ms[method] = (
                self._latency_sum_ms.get(method, 0.0) + elapsed_ms
            )
            self._latency_count[method] = (
                self._latency_count.get(method, 0) + 1
            )
        self.manager.on_message(channel=method)
        return result

    # -- símbolos ---------------------------------------------------------------

    def _ccxt_symbol(self, symbol: str, *, market_type: str = "spot") -> str:
        """Símbolo canônico (``BASE/QUOTE``) aceito pelo CCXT unificado."""
        return normalize_symbol(
            symbol, exchange=self.exchange_id, market_type=market_type
        )

    def _swap_symbol(self, symbol: str) -> str:
        """Símbolo perpétuo canônico ``BASE/QUOTE:USDT`` p/ funding/OI."""
        canonical = self._ccxt_symbol(symbol)
        if ":" in canonical:
            return canonical
        base, quote = canonical.split("/", 1)
        return f"{base}/{quote}:USDT"

    def _check_timeframe(self, timeframe: str) -> str:
        """Valida o timeframe na especificação e na exchange (CCXT)."""
        tf = validate_timeframe(timeframe)
        exchange = self._ensure_exchange()
        supported = getattr(exchange, "timeframes", None)
        if isinstance(supported, dict) and supported and tf not in supported:
            raise ExchangeError(
                ErrorCode.BAD_RESPONSE,
                f"timeframe {tf!r} não suportado por {self.name} "
                f"(suportados: {sorted(supported)})",
                exchange=self.exchange_id,
            )
        return tf

    def _unsupported(self, feature: str, symbol: str) -> ExchangeError:
        """Erro claro para dado indisponível — nunca inventar o dado."""
        return ExchangeError(
            ErrorCode.BAD_RESPONSE,
            f"{feature} não disponível em {self.name} via API pública "
            f"(CCXT has.fetch* = False); dado não inventado — ver README "
            f"do conector",
            exchange=self.exchange_id,
            symbol=symbol,
            retryable=False,
        )

    # -- leitura pública de mercado (CON-001) -----------------------------------

    def fetch_markets(self) -> list[Market]:
        """Mercados públicos (spot, perps, futuros, opções)."""
        exchange = self._ensure_exchange()
        raw_markets = self._call("fetch_markets", exchange.fetch_markets)
        markets: list[Market] = []
        for raw in raw_markets or []:
            base = canonical_asset(str(raw.get("base", "")),
                                   self.exchange_id)
            quote = canonical_asset(str(raw.get("quote", "")),
                                    self.exchange_id)
            raw_type = str(raw.get("type", "spot")).lower()
            market_type = {
                "spot": "spot", "swap": "perp",
                "future": "futures", "option": "options",
            }.get(raw_type, "spot")
            try:
                symbol = normalize_symbol(
                    f"{base}/{quote}", exchange=self.exchange_id,
                    market_type=market_type,
                )
            except ExchangeError:
                continue  # mercado sem símbolo interpretável: descartado
            precision = raw.get("precision") or {}
            tick_size = None
            price_precision = precision.get("price")
            if isinstance(price_precision, int):
                tick_size = Decimal(1).scaleb(-price_precision)
            elif isinstance(price_precision, float):
                tick_size = Decimal(str(price_precision))
            limits = raw.get("limits") or {}
            amount_limits = limits.get("amount") or {}
            min_qty = None
            if amount_limits.get("min") is not None:
                min_qty = _to_decimal(amount_limits["min"], "min_qty")
            markets.append(Market(
                exchange=self.exchange_id, symbol=symbol, base=base,
                quote=quote, market_type=market_type,  # type: ignore[arg-type]
                active=bool(raw.get("active", True)),
                tick_size=tick_size, min_qty=min_qty, raw=raw,
            ))
        return markets

    def fetch_ticker(self, symbol: str) -> Ticker:
        """Último preço / ticker (público)."""
        canonical = self._ccxt_symbol(symbol)
        exchange = self._ensure_exchange()
        raw = self._call("fetch_ticker", exchange.fetch_ticker, canonical)
        last = raw.get("last")
        if last is None:
            last = raw.get("close")
        if last is None and raw.get("bid") and raw.get("ask"):
            last = (Decimal(str(raw["bid"])) + Decimal(str(raw["ask"]))) / 2
        if last is None:
            raise ExchangeError(
                ErrorCode.BAD_RESPONSE,
                f"ticker sem último preço para {canonical}",
                exchange=self.exchange_id, symbol=canonical, raw=raw,
            )
        timestamp = raw.get("timestamp")
        timestamp_ms = (
            normalize_timestamp(timestamp)
            if timestamp is not None else int(time.time() * 1000)
        )
        volume = raw.get("quoteVolume")
        if volume is None:
            volume = raw.get("baseVolume")
        percentage = raw.get("percentage")
        return Ticker(
            exchange=self.exchange_id, symbol=canonical,
            last=_to_decimal(last, "last"), timestamp_ms=timestamp_ms,
            bid=_to_decimal(raw["bid"], "bid") if raw.get("bid") else None,
            ask=_to_decimal(raw["ask"], "ask") if raw.get("ask") else None,
            volume_24h=_to_decimal(volume, "volume_24h")
            if volume is not None else None,
            change_24h_pct=_to_decimal(percentage, "change_24h_pct")
            if percentage is not None else None,
            raw=raw,
        )

    def fetch_trades(self, symbol: str, limit: int = 100,
                     *, since_ms: Optional[int] = None) -> list[Trade]:
        """Trades recentes (REST pública). Não simula ticks.

        ``since_ms`` (opcional) limita a trades a partir de um instante
        (ms UTC). Quando ``limit > 1000`` (teto de uma chamada CCXT)
        ou ``since_ms`` é dado, as trades são buscadas em páginas de
        1000, com deduplicação por ``trade_id`` (CEX-004/CEX-006).
        """
        canonical = self._ccxt_symbol(symbol)
        exchange = self._ensure_exchange()
        if limit <= 1000 and since_ms is None:
            raw_trades = self._call(
                "fetch_trades", exchange.fetch_trades, canonical,
                limit=limit,
            )
            return self._parse_trades(raw_trades, canonical)
        collected: list[Trade] = []
        seen: set[str] = set()
        since = since_ms
        for _ in range(10):  # no máximo 10 páginas (evita loop infinito)
            raw_trades = self._call(
                "fetch_trades", exchange.fetch_trades, canonical,
                since=since, limit=1000,
            )
            page = self._parse_trades(raw_trades, canonical)
            new = [t for t in page if t.trade_id not in seen]
            if not new:
                break
            seen.update(t.trade_id for t in new)
            collected.extend(new)
            if len(page) < 1000 or len(collected) >= limit:
                break
            since = max(t.timestamp_ms for t in new)
        return collected[:limit]

    def _parse_trades(self, raw_trades: Any, canonical: str) -> list[Trade]:
        """Traduz a lista bruta do CCXT para :class:`Trade`."""
        trades: list[Trade] = []
        for raw in raw_trades or []:
            try:
                side = normalize_side(str(raw.get("side", "")))
                trades.append(Trade(
                    exchange=self.exchange_id, symbol=canonical,
                    trade_id=str(raw["id"]),
                    price=_to_decimal(raw["price"], "price"),
                    quantity=_to_decimal(raw["amount"], "quantity"),
                    side=side,  # type: ignore[arg-type]
                    timestamp_ms=normalize_timestamp(raw["timestamp"]),
                    raw=raw,
                ))
            except (KeyError, ValueError, ExchangeError):
                continue  # trade malformado: descartado, sem inventar
        if raw_trades and not trades:
            raise ExchangeError(
                ErrorCode.BAD_RESPONSE,
                f"trades de {canonical} sem campos interpretáveis",
                exchange=self.exchange_id, symbol=canonical,
                raw=raw_trades,
            )
        return trades

    def fetch_ohlcv(self, symbol: str, timeframe: str,
                    limit: int = 100,
                    *, since_ms: Optional[int] = None) -> list[Candle]:
        """OHLCV na granularidade real da fonte (sem inventar).

        ``since_ms`` (opcional) limita a candles a partir de um
        instante (ms UTC). Quando ``limit > 1000`` (teto de uma
        chamada CCXT) ou ``since_ms`` é dado, os candles são buscados
        em páginas de 1000, com deduplicação por ``open_time_ms``;
        gaps entre páginas também são contados (CEX-006).
        """
        canonical = self._ccxt_symbol(symbol)
        tf = self._check_timeframe(timeframe)
        exchange = self._ensure_exchange()
        step_ms = TIMEFRAME_MS[tf]
        if limit <= 1000 and since_ms is None:
            raw_rows = self._call(
                "fetch_ohlcv", exchange.fetch_ohlcv, canonical, tf, None,
                limit,
            )
            candles, _ = self._parse_ohlcv(
                raw_rows, canonical, tf, step_ms
            )
            return candles
        collected: list[Candle] = []
        since = since_ms
        previous_open: Optional[int] = None
        for _ in range(10):  # no máximo 10 páginas (evita loop infinito)
            raw_rows = self._call(
                "fetch_ohlcv", exchange.fetch_ohlcv, canonical, tf, since,
                1000,
            )
            page, previous_open = self._parse_ohlcv(
                raw_rows, canonical, tf, step_ms,
                previous_open_ms=previous_open,
            )
            if not page:
                break
            collected.extend(page)
            if len(page) < 1000 or len(collected) >= limit:
                break
            since = page[-1].open_time_ms + step_ms
        deduped: dict[int, Candle] = {}
        for candle in collected:
            deduped[candle.open_time_ms] = candle
        return [deduped[k] for k in sorted(deduped)][:limit]

    def _parse_ohlcv(self, raw_rows: Any, canonical: str, tf: str,
                     step_ms: int, *,
                     previous_open_ms: Optional[int] = None
                     ) -> tuple[list[Candle], Optional[int]]:
        """Traduz as linhas brutas do CCXT para :class:`Candle`.

        Conta gaps (candles faltantes) e devolve o último
        ``open_time_ms`` para a detecção continuar entre páginas.
        """
        candles: list[Candle] = []
        previous_open = previous_open_ms
        for row in raw_rows or []:
            try:
                open_ms = normalize_timestamp(row[0])
                candle = Candle(
                    exchange=self.exchange_id, symbol=canonical, timeframe=tf,
                    open_time_ms=open_ms, close_time_ms=open_ms + step_ms,
                    open=_to_decimal(row[1], "open"),
                    high=_to_decimal(row[2], "high"),
                    low=_to_decimal(row[3], "low"),
                    close=_to_decimal(row[4], "close"),
                    volume=_to_decimal(row[5], "volume"),
                    raw=row,
                )
            except (IndexError, TypeError, ValueError, ExchangeError) as exc:
                raise ExchangeError(
                    ErrorCode.BAD_RESPONSE,
                    f"candle malformado de {canonical} ({tf}): {row!r}",
                    exchange=self.exchange_id, symbol=canonical, raw=row,
                ) from exc
            if previous_open is not None and open_ms > previous_open:
                missing = (open_ms - previous_open) // step_ms - 1
                if missing > 0:
                    self._gaps_detected += int(missing)
            previous_open = open_ms
            candles.append(candle)
        return candles, previous_open

    def fetch_order_book(self, symbol: str, depth: int = 20) -> OrderBook:
        """Snapshot do livro de ofertas (público)."""
        canonical = self._ccxt_symbol(symbol)
        exchange = self._ensure_exchange()
        raw = self._call(
            "fetch_order_book", exchange.fetch_order_book, canonical, depth,
        )
        bids = tuple(
            (_to_decimal(p, "bid"), _to_decimal(q, "bid_qty"))
            for p, q in (raw.get("bids") or [])
        )
        asks = tuple(
            (_to_decimal(p, "ask"), _to_decimal(q, "ask_qty"))
            for p, q in (raw.get("asks") or [])
        )
        # Garantir a ordem exigida pelo modelo (bids desc, asks asc).
        bids = tuple(sorted(bids, key=lambda level: level[0], reverse=True))
        asks = tuple(sorted(asks, key=lambda level: level[0]))
        timestamp = raw.get("timestamp")
        timestamp_ms = (
            normalize_timestamp(timestamp)
            if timestamp is not None else int(time.time() * 1000)
        )
        sequence = raw.get("nonce")
        return OrderBook(
            exchange=self.exchange_id, symbol=canonical,
            timestamp_ms=timestamp_ms, bids=bids, asks=asks,
            sequence=int(sequence) if sequence is not None else None,
            raw=raw,
        )

    def fetch_funding_rate(self, symbol: str) -> FundingRate:
        """Funding rate atual de um perpétuo (público)."""
        canonical = self._ccxt_symbol(symbol)
        if not self.supports_funding:
            raise self._unsupported("funding rate", canonical)
        swap = self._swap_symbol(symbol)
        exchange = self._ensure_exchange()
        raw = self._call("fetch_funding_rate",
                         exchange.fetch_funding_rate, swap)
        rate = raw.get("fundingRate")
        if rate is None:
            raise ExchangeError(
                ErrorCode.BAD_RESPONSE,
                f"funding rate ausente na resposta para {swap}",
                exchange=self.exchange_id, symbol=swap, raw=raw,
            )
        funding_ts = raw.get("fundingTimestamp") or raw.get("timestamp")
        timestamp_ms = (
            normalize_timestamp(funding_ts)
            if funding_ts is not None else int(time.time() * 1000)
        )
        next_funding = raw.get("nextFundingTimestamp")
        return FundingRate(
            exchange=self.exchange_id, symbol=swap,
            rate=_to_decimal(rate, "funding_rate"),
            timestamp_ms=timestamp_ms,
            next_funding_ms=normalize_timestamp(next_funding)
            if next_funding is not None else None,
            raw=raw,
        )

    def fetch_open_interest(self, symbol: str) -> OpenInterest:
        """Open interest atual de um contrato (público)."""
        canonical = self._ccxt_symbol(symbol)
        if not self.supports_open_interest:
            raise self._unsupported("open interest", canonical)
        swap = self._swap_symbol(symbol)
        exchange = self._ensure_exchange()
        raw = self._call("fetch_open_interest",
                         exchange.fetch_open_interest, swap)
        value = raw.get("openInterestAmount")
        if value is None:
            value = raw.get("openInterestValue")
        if value is None:
            raise ExchangeError(
                ErrorCode.BAD_RESPONSE,
                f"open interest ausente na resposta para {swap}",
                exchange=self.exchange_id, symbol=swap, raw=raw,
            )
        timestamp = raw.get("timestamp")
        timestamp_ms = (
            normalize_timestamp(timestamp)
            if timestamp is not None else int(time.time() * 1000)
        )
        return OpenInterest(
            exchange=self.exchange_id, symbol=swap,
            value=_to_decimal(value, "open_interest"),
            timestamp_ms=timestamp_ms, raw=raw,
        )


__all__ = ["CCXTAdapter", "TIMEFRAME_MS"]
