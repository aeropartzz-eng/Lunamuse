"""Normalização de símbolos, timestamps, lados e tipos (Fase 3 — CON-003).

Regras do contrato universal:

- Símbolo canônico: ``BASE/QUOTE`` (ex.: ``BTC/USDT``). Formas aceitas:
  ``BTC/USDT``, ``BTCUSDT``, ``btc-usdt``, ``BTC_USDT``, ``BTC USDT``.
  Para perpétuos, o sufixo canônico é ``:USDT`` (estilo CCXT),
  ex.: ``BTC-PERP`` ou ``BTCUSDT-PERP`` -> ``BTC/USDT:USDT`` quando a
  moeda de liquidação é conhecida.
- Timestamps: sempre inteiros em **milissegundos UTC**.
- Lados: ``buy`` / ``sell`` (aceita bid/ask, long/short, B/S, etc.).
- Tipos de ordem: ``limit`` / ``market`` / ``stop_limit`` / ``stop_market``.
- **Nunca inventar granularidade**: se a fonte não dá trades
  individuais, não simular ticks nem candles de 1s. Não há função de
  síntese de ticks neste módulo — por decisão de projeto.

Alias por exchange (tabela): alguns ativos têm códigos diferentes
conforme a exchange (ex.: Kraken usa ``XBT`` para BTC e ``XDG`` para
DOGE). A tabela vive aqui para que todos os conectores compartilhem
a mesma tradução.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from errors import ExchangeError, ErrorCode

# Moedas de cotação reconhecidas ao separar um símbolo concatenado
# (ex.: "BTCUSDT" -> base "BTC", quote "USDT"). Ordem: mais longas
# primeiro, para "USDT" vencer "USD" e "USDC" vencer "USD".
QUOTE_CURRENCIES = (
    "USDT",
    "USDC",
    "USDD",
    "FDUSD",
    "TUSD",
    "PYUSD",
    "BUSD",
    "DAI",
    "USD",
    "EUR",
    "GBP",
    "BRL",
    "TRY",
    "BTC",
    "ETH",
    "BNB",
    "SOL",
)

# Alias de ativo por exchange: código nativo -> código canônico.
# Ex.: Kraken chama BTC de XBT e DOGE de XDG.
ASSET_ALIASES: dict[str, dict[str, str]] = {
    "kraken": {"XBT": "BTC", "XDG": "DOGE", "XETH": "ETH"},
    "coinbase": {"BTC": "BTC"},
    "binance": {},
    "bybit": {},
    "okx": {},
    "bitget": {},
    "gateio": {},
}

# Timeframes reais da especificação (§3). Nenhum outro é aceito aqui:
# granularidade não é inventada.
ALLOWED_TIMEFRAMES = frozenset(
    {
        "1s", "5s", "15s", "30s",
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "8h", "12h",
        "1d", "1w",
    }
)

_SIDE_MAP = {
    "buy": "buy", "b": "buy", "bid": "buy", "long": "buy",
    "sell": "sell", "s": "sell", "ask": "sell", "short": "sell",
}

_ORDER_TYPE_MAP = {
    "limit": "limit", "lmt": "limit",
    "market": "market", "mkt": "market",
    "stop_limit": "stop_limit", "stop-limit": "stop_limit",
    "stop_market": "stop_market", "stop-market": "stop_market",
    "stop": "stop_market",
}


def canonical_asset(code: str, exchange: Optional[str] = None) -> str:
    """Código canônico de um ativo (ex.: Kraken ``XBT`` -> ``BTC``)."""
    upper = code.strip().upper()
    if exchange:
        aliases = ASSET_ALIASES.get(exchange.lower(), {})
        return aliases.get(upper, upper)
    for aliases in ASSET_ALIASES.values():
        if upper in aliases:
            return aliases[upper]
    return upper


# Ativos conhecidos (códigos canônicos e nativos com alias). Usados para
# desambiguar símbolos concatenados: "XBTUSD" é XBT/USD, não XB/TUSD.
KNOWN_ASSETS = frozenset(
    {
        "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "LTC", "DOT",
        "AVAX", "LINK", "ATOM", "NEAR", "TRX", "TON", "XLM", "BCH",
        "USDT", "USDC", "USDD", "FDUSD", "TUSD", "PYUSD", "BUSD", "DAI",
        "USD", "EUR", "GBP", "BRL", "TRY",
        "XBT", "XDG", "XETH",  # códigos nativos com alias (Kraken)
    }
)


def _split_concatenated(compact: str) -> tuple[str, str]:
    """Separa ``BTCUSDT`` em (``BTC``, ``USDT``) pela quote conhecida.

    Quando há mais de uma separação possível (ex.: ``XBTUSD`` poderia
    ser ``XB/TUSD`` ou ``XBT/USD``), prefere a que deixa uma base de
    ativo conhecido; senão, a quote mais longa.
    """
    candidates: list[tuple[str, str]] = []
    for quote in QUOTE_CURRENCIES:
        if compact.endswith(quote) and len(compact) > len(quote):
            candidates.append((compact[: -len(quote)], quote))
    if not candidates:
        raise ValueError(
            f"não foi possível separar base/quote em {compact!r}: "
            "quote desconhecida"
        )
    for base, quote in candidates:
        if base in KNOWN_ASSETS:
            return base, quote
    return candidates[0]


def normalize_symbol(
    raw_symbol: str,
    exchange: Optional[str] = None,
    *,
    market_type: str = "spot",
) -> str:
    """Normaliza um símbolo para o formato canônico ``BASE/QUOTE``.

    Aceita ``BTC/USDT``, ``BTCUSDT``, ``btc-usdt``, ``BTC_USDT``,
    ``BTC USDT`` e, para perpétuos, ``BTC-PERP`` / ``BTCUSDT-PERP``
    (vira ``BTC/USDT:USDT`` quando a quote é conhecida).

    Raises:
        ExchangeError: com código ``INVALID_SYMBOL`` se o símbolo não
            puder ser interpretado.
    """
    if not raw_symbol or not str(raw_symbol).strip():
        raise ExchangeError(
            ErrorCode.INVALID_SYMBOL,
            f"símbolo vazio ou inválido: {raw_symbol!r}",
            exchange=exchange,
        )
    text = str(raw_symbol).strip().upper()

    is_perp = False
    # Sufixo ":QUOTE" de perpétuo já canônico (ex.: "BTC/USDT:USDT").
    if ":" in text:
        text, _settlement = text.split(":", 1)
        is_perp = True

    for suffix in ("-PERP", "_PERP", "/PERP", "PERP", "-PERPETUAL"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            is_perp = True
            break

    if "/" in text:
        parts = [p for p in re.split(r"[/\-_ ]+", text) if p]
        if len(parts) != 2:
            raise ExchangeError(
                ErrorCode.INVALID_SYMBOL,
                f"símbolo inválido: {raw_symbol!r}",
                exchange=exchange,
            )
        base, quote = parts
    elif re.search(r"[-_ ]", text):
        parts = [p for p in re.split(r"[-_ ]+", text) if p]
        if len(parts) != 2:
            raise ExchangeError(
                ErrorCode.INVALID_SYMBOL,
                f"símbolo inválido: {raw_symbol!r}",
                exchange=exchange,
            )
        base, quote = parts
    else:
        try:
            base, quote = _split_concatenated(text)
        except ValueError as exc:
            raise ExchangeError(
                ErrorCode.INVALID_SYMBOL,
                f"símbolo inválido: {raw_symbol!r} ({exc})",
                exchange=exchange,
            ) from exc

    base = canonical_asset(base, exchange)
    quote = canonical_asset(quote, exchange)
    canonical = f"{base}/{quote}"
    if is_perp or market_type in ("perp", "futures"):
        canonical = f"{canonical}:{quote}"
    return canonical


def denormalize_symbol(canonical: str, exchange: str) -> str:
    """Converte o símbolo canônico para a forma nativa da exchange.

    Por padrão, remove ``/`` e o sufixo ``:QUOTE`` de perpétuo
    (``BTC/USDT`` -> ``BTCUSDT``). Kraken usa ``XBT`` para BTC.
    Conectores com formato próprio (ex.: OKX ``BTC-USDT``) devem
    sobrescrever este comportamento no adapter da Fase 4/5.
    """
    symbol = canonical.strip().upper()
    if ":" in symbol:
        symbol = symbol.split(":")[0]
    if "/" in symbol:
        base, quote = symbol.split("/", 1)
    else:  # já concatenado
        base, quote = _split_concatenated(symbol)
    reverse: dict[str, str] = {}
    for native, canon in ASSET_ALIASES.get(exchange.lower(), {}).items():
        reverse.setdefault(canon, native)
    base = reverse.get(base, base)
    quote = reverse.get(quote, quote)
    return f"{base}{quote}"


def normalize_timestamp(value: int | float | str | datetime) -> int:
    """Normaliza um timestamp para inteiro em milissegundos UTC.

    Aceita: ms (int/float), segundos (int/float < 1e12), ISO 8601
    (``2026-11-13T06:00:00Z``) e ``datetime`` (naive = UTC).
    Raises:
        ValueError: se o valor não puder ser interpretado.
    """
    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # < 1e12: segundos; >= 1e12: milissegundos (ms desde 1970 já
        # passa de 1.7e12 em 2026; segundos ficam em ~1.7e9).
        if abs(value) < 1e12:
            return int(value * 1000)
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"timestamp inválido: {value!r}") from exc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    raise ValueError(f"timestamp inválido: {value!r}")


def normalize_side(value: str) -> str:
    """Normaliza lado para ``buy`` ou ``sell``.

    Aceita buy/bid/long/B e sell/ask/short/S (qualquer caixa).
    """
    key = str(value).strip().lower()
    if key not in _SIDE_MAP:
        raise ValueError(f"lado inválido: {value!r}")
    return _SIDE_MAP[key]


def normalize_order_type(value: str) -> str:
    """Normaliza tipo de ordem para limit/market/stop_limit/stop_market."""
    key = str(value).strip().lower().replace(" ", "_")
    if key not in _ORDER_TYPE_MAP:
        raise ValueError(f"tipo de ordem inválido: {value!r}")
    return _ORDER_TYPE_MAP[key]


def validate_timeframe(timeframe: str) -> str:
    """Valida um timeframe contra os timeframes reais da especificação.

    Não inventa granularidade: qualquer valor fora da lista é rejeitado.
    """
    tf = str(timeframe).strip().lower()
    if tf not in ALLOWED_TIMEFRAMES:
        raise ValueError(
            f"timeframe inválido ou não fornecido pela fonte: {timeframe!r} "
            f"(permitidos: {sorted(ALLOWED_TIMEFRAMES)})"
        )
    return tf
