"""Fakes de HTTP/RPC para os testes da Fase 6 (sem rede real)."""

from __future__ import annotations

import json


class FakeResponse:
    """Resposta HTTP fake (status + JSON)."""

    def __init__(self, payload, status=200, headers=None):
        self._payload = payload
        self.status_code = status
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, str):
            return json.loads(self._payload)
        return self._payload


class FakeSession:
    """Sessão requests-like: responde por (método, URL) ou por prefixo."""

    def __init__(self):
        self.headers = {}
        self.calls = []  # (método, url, kwargs)
        self._routes = {}  # (método, url exata) -> FakeResponse
        self._prefix_routes = []  # (método, prefixo, FakeResponse)

    def route(self, method, url, payload, status=200, headers=None):
        self._routes[(method, url)] = FakeResponse(payload, status, headers)

    def route_prefix(self, method, prefix, payload, status=200, headers=None):
        self._prefix_routes.append((method, prefix, FakeResponse(payload, status, headers)))

    def _find(self, method, url):
        if (method, url) in self._routes:
            return self._routes[(method, url)]
        for m, prefix, response in self._prefix_routes:
            if m == method and url.startswith(prefix):
                return response
        raise AssertionError(f"FakeSession: rota nao mapeada: {method} {url}")

    def get(self, url, params=None, timeout=None):
        full = url
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            full = f"{url}?{query}"
        self.calls.append(("GET", full, {"params": params}))
        return self._find("GET", url)

    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, {"json": json}))
        return self._find("POST", url)
