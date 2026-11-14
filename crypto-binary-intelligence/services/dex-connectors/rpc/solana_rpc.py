"""Cliente JSON-RPC Solana — somente leitura (Fase 6 — DEX-003).

Endpoints públicos sem chave (compartilhados, com rate limit; produção
exige RPC dedicado com chave do Will):
- https://api.mainnet-beta.solana.com
- https://solana-rpc.publicnode.com

Usado pelo Crypto Shield para: top holders (getTokenLargestAccounts),
mint/freeze authority (getAccountInfo + parse do layout SPL Mint) e
identificação do criador (primeira assinatura do mint).

Nenhum método envia transação, assina nada ou conecta carteira.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

import requests

DEFAULT_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-rpc.publicnode.com",
]

# Layout do SPL Token Mint (82 bytes):
#   0..4    mint_authority: COption<Pubkey> (u32 0/1 + 32 bytes)
#   36..44  supply: u64 LE
#   44      decimals: u8
#   45      is_initialized: u8
#   46..50  freeze_authority: COption<Pubkey>
#   50..82  pubkey (se presente)
MINT_ACCOUNT_LEN = 82


class SolanaRpcError(Exception):
    """Falha de RPC Solana (rede ou erro do nó)."""


def parse_spl_mint_account(data_b64: str) -> dict[str, Any]:
    """Decodifica o layout SPL Mint a partir do base64 de getAccountInfo.

    Retorna mint_authority / freeze_authority (None = revogada),
    supply e decimals. Levanta ValueError se o dado não for um Mint.
    """
    raw = base64.b64decode(data_b64)
    if len(raw) < MINT_ACCOUNT_LEN:
        raise ValueError(
            f"dado de conta Solana com {len(raw)} bytes; "
            f"esperado >= {MINT_ACCOUNT_LEN} (SPL Mint)"
        )

    def _coption_pubkey(offset: int) -> Optional[str]:
        flag = int.from_bytes(raw[offset : offset + 4], "little")
        if flag == 0:
            return None
        return raw[offset + 4 : offset + 36].hex()

    mint_authority = _coption_pubkey(0)
    supply = int.from_bytes(raw[36:44], "little")
    decimals = raw[44]
    freeze_authority = _coption_pubkey(46)
    return {
        "mint_authority": mint_authority,
        "freeze_authority": freeze_authority,
        "supply": supply,
        "decimals": decimals,
        "is_initialized": bool(raw[45]),
    }


class SolanaRpcClient:
    """JSON-RPC Solana com failover. Somente leitura."""

    def __init__(
        self,
        endpoints: Optional[list[str]] = None,
        timeout: float = 10.0,
        session: Optional[Any] = None,
    ) -> None:
        self.endpoints = endpoints or list(DEFAULT_ENDPOINTS)
        self.timeout = timeout
        self._session = session or requests.Session()
        self._id = 0

    # -- núcleo -------------------------------------------------------
    def call_rpc(self, method: str, params: Optional[list[Any]] = None) -> Any:
        """Uma chamada JSON-RPC com failover entre endpoints."""
        self._id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or [],
        }
        last_error: Optional[Exception] = None
        for url in self.endpoints:
            try:
                response = self._session.post(url, json=payload, timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = SolanaRpcError(f"rede em {url}: {exc}")
                continue
            if getattr(response, "status_code", 0) >= 400:
                last_error = SolanaRpcError(f"HTTP {response.status_code} em {url}")
                continue
            try:
                body = response.json()
            except ValueError as exc:
                last_error = SolanaRpcError(f"resposta nao-JSON em {url}: {exc}")
                continue
            if "error" in body and body["error"]:
                last_error = SolanaRpcError(
                    f"RPC {method} em {url}: {body['error']}"
                )
                continue
            result = body.get("result")
            if isinstance(result, dict) and "value" in result:
                return result["value"]
            return result
        assert last_error is not None
        raise last_error

    # -- leituras ------------------------------------------------------
    def get_slot(self) -> int:
        """Slot atual."""
        return int(self.call_rpc("getSlot"))

    def get_token_supply(self, mint: str) -> dict[str, Any]:
        """Supply de um mint: {amount (str), decimals, uiAmount}."""
        value = self.call_rpc("getTokenSupply", [mint])
        return value if isinstance(value, dict) else {}

    def get_token_largest_accounts(
        self, mint: str, commitment: str = "confirmed"
    ) -> list[dict[str, Any]]:
        """Top 20 holders de um mint (maior conta primeiro).

        Base do Top 10/20 do Crypto Shield (SEC-003) em Solana.
        """
        value = self.call_rpc(
            "getTokenLargestAccounts",
            [mint, {"commitment": commitment}],
        )
        return value if isinstance(value, list) else []

    def get_account_info(
        self, pubkey: str, commitment: str = "confirmed"
    ) -> Optional[dict[str, Any]]:
        """Conta (owner, lamports, data base64) ou None se inexistente."""
        value = self.call_rpc(
            "getAccountInfo",
            [pubkey, {"encoding": "base64", "commitment": commitment}],
        )
        return value if isinstance(value, dict) else None

    def get_mint_info(self, mint: str) -> dict[str, Any]:
        """Mint/freeze authority, supply e decimals de um mint SPL."""
        account = self.get_account_info(mint)
        if not account:
            raise SolanaRpcError(f"mint {mint} nao encontrado")
        data = (account.get("data") or [])[0] if account.get("data") else None
        if not data:
            raise SolanaRpcError(f"mint {mint} sem dados de conta")
        return parse_spl_mint_account(data)

    def get_signatures_for_address(
        self, address: str, limit: int = 100, before: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Assinaturas de uma conta (mais recentes primeiro)."""
        params: dict[str, Any] = {"limit": limit}
        if before:
            params["before"] = before
        value = self.call_rpc("getSignaturesForAddress", [address, params])
        return value if isinstance(value, list) else []

    def get_transaction(self, signature: str) -> Optional[dict[str, Any]]:
        """Transação decodificada (jsonParsed) ou None."""
        value = self.call_rpc(
            "getTransaction",
            [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
        )
        return value if isinstance(value, dict) else None

    def find_mint_creator(
        self, mint: str, max_pages: int = 5, page_size: int = 1000
    ) -> dict[str, Any]:
        """Identifica o criador provável de um mint (SEC-002).

        Caminha as assinaturas do mint até a mais antiga e lê o fee
        payer da transação de criação. Retorna ``{"creator": ...}`` ou
        ``{"creator": None, "reason": ...}`` quando não dá para
        determinar (muitas assinaturas, transação indisponível).
        Sem evidência, nenhum vínculo é presumido.
        """
        oldest: Optional[dict[str, Any]] = None
        before: Optional[str] = None
        truncated = False
        for _ in range(max_pages):
            page = self.get_signatures_for_address(
                mint, limit=page_size, before=before
            )
            if not page:
                break
            oldest = page[-1]
            if len(page) < page_size:
                break
            before = page[-1].get("signature")
            truncated = True
        if oldest is None:
            return {"creator": None, "reason": "mint sem assinaturas"}
        if truncated:
            return {
                "creator": None,
                "reason": (
                    "muitas assinaturas no mint; criador nao determinado "
                    "dentro do limite de paginas"
                ),
            }
        tx = self.get_transaction(oldest["signature"])
        if not tx:
            return {
                "creator": None,
                "reason": "transacao de criacao indisponivel no RPC",
            }
        try:
            payer = tx["transaction"]["message"]["accountKeys"][0]["pubkey"]
        except (KeyError, IndexError, TypeError):
            return {
                "creator": None,
                "reason": "fee payer nao legivel na transacao",
            }
        return {"creator": payer, "signature": oldest["signature"]}

    def health(self) -> dict[str, Any]:
        """Estado: tenta ler o slot atual (uma chamada real)."""
        try:
            slot = self.get_slot()
            return {"connected": True, "status": "ok", "slot": slot}
        except SolanaRpcError as exc:
            return {"connected": False, "status": "error", "error": str(exc)}
