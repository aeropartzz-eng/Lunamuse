"""Cliente HTTP compartilhado dos conectores DEX / on-chain (Fase 6).

Somente leitura pública, sem nenhuma chave de API. Centraliza timeout,
throttle mínimo entre chamadas, retry com backoff em 429/5xx e o erro
padronizado :class:`DexHttpError`.

Uso típico (a ``session`` pode ser injetada nos testes)::

    client = DexHttpClient("https://api.dexscreener.com", timeout=10.0)
    data = client.get("/latest/dex/search", params={"q": "BONK"})
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

import requests

DEFAULT_USER_AGENT = (
    "crypto-binary-intelligence/0.1 (Fase 6; somente leitura publica; "
    "https://github.com/aeropartz/crypto-binary-intelligence)"
)
DEFAULT_TIMEOUT_S = 10.0
MAX_RETRIES = 2
RETRYABLE_STATUS = (429, 500, 502, 503, 504)


class DexHttpError(Exception):
    """Falha de HTTP em uma fonte DEX pública (sem credencial envolvida)."""

    def __init__(
        self,
        message: str,
        status: Optional[int] = None,
        url: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.url = url


class DexHttpClient:
    """GET/POST JSON com timeout, throttle e retry. Sem autenticação."""

    def __init__(
        self,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT_S,
        min_interval_s: float = 0.0,
        user_agent: str = DEFAULT_USER_AGENT,
        session: Optional[Any] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.min_interval_s = min_interval_s
        self._session = session or requests.Session()
        self._session.headers.update(
            {"User-Agent": user_agent, "Accept": "application/json"}
        )
        self._sleep = sleep
        self._last_call_at = 0.0

    # -- throttle -----------------------------------------------------
    def _throttle(self) -> None:
        if self.min_interval_s <= 0:
            return
        elapsed = time.monotonic() - self._last_call_at
        wait = self.min_interval_s - elapsed
        if wait > 0:
            self._sleep(wait)

    # -- verbos -------------------------------------------------------
    def get(
        self, path: str, params: Optional[dict[str, Any]] = None
    ) -> Any:
        """GET JSON. Levanta :class:`DexHttpError` em falha HTTP/rede."""
        url = f"{self.base_url}{path}"
        return self._request("GET", url, params=params)

    def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        """POST JSON (usado pelo JSON-RPC)."""
        url = f"{self.base_url}{path}"
        return self._request("POST", url, payload=payload)

    def post_url(self, url: str, payload: dict[str, Any]) -> Any:
        """POST JSON em URL absoluta (JSON-RPC com endpoint próprio)."""
        return self._request("POST", url, payload=payload)

    # -- núcleo -------------------------------------------------------
    def _request(
        self,
        method: str,
        url: str,
        params: Optional[dict[str, Any]] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            try:
                if method == "GET":
                    response = self._session.get(
                        url, params=params, timeout=self.timeout
                    )
                else:
                    response = self._session.post(
                        url, json=payload, timeout=self.timeout
                    )
            except requests.RequestException as exc:
                last_error = DexHttpError(
                    f"falha de rede em {method} {url}: {exc}", url=url
                )
                break
            self._last_call_at = time.monotonic()
            status = getattr(response, "status_code", 0)
            if status == 429 and attempt < MAX_RETRIES:
                retry_after = response.headers.get("Retry-After") if hasattr(response, "headers") else None
                wait = float(retry_after) if retry_after else 2.0 * (attempt + 1)
                self._sleep(wait)
                continue
            if status in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                self._sleep(1.0 * (attempt + 1))
                continue
            if status >= 400:
                raise DexHttpError(
                    f"HTTP {status} em {method} {url}",
                    status=status,
                    url=url,
                )
            try:
                return response.json()
            except ValueError as exc:
                raise DexHttpError(
                    f"resposta nao-JSON em {method} {url}: {exc}",
                    status=status,
                    url=url,
                ) from exc
        assert last_error is not None
        raise last_error
