"""Cliente JSON-RPC EVM — somente leitura (Fase 6 — DEX-002/DEX-004).

Endpoints públicos sem chave, com failover entre eles. Nenhum método
envia transação, assina nada ou conecta carteira: só ``eth_call``,
``eth_getBalance``, ``eth_getLogs``, ``eth_blockNumber`` e ``eth_chainId``.

Endpoints (públicos, compartilhados — rate limit e congestionamento
são esperados; produção exige RPC dedicado com chave do Will):
- BNB Chain (56): dataseeds oficiais bsc-dataseed.binance.org,
  defibit e ninicoin (testados em 2026-11-13).
- Ethereum (1): cloudflare-eth.com e ethereum-rpc.publicnode.com
  (testados em 2026-11-13); eth.llamarpc.com instável (HTTP 525).
- Base (8453): mainnet.base.org (testado); OnFinality público com
  429 frequente (limite do plano gratuito compartilhado).

REMOVIDO em 2026-11-13: ``rpc.ankr.com/*`` — passou a exigir API key
("Unauthorized: You must authenticate your request with an API key").
"""

from __future__ import annotations

from typing import Any, Optional

import requests

# Seletores de 4 bytes (padrão ABI, valores fixos conhecidos).
SEL_TOTAL_SUPPLY = "0x18160ddd"  # totalSupply()
SEL_BALANCE_OF = "0x70a08231"  # balanceOf(address)
SEL_DECIMALS = "0x313ce567"  # decimals()
SEL_SYMBOL = "0x95d89b41"  # symbol()
SEL_OWNER = "0x8da5cb5b"  # owner()
SEL_GET_RESERVES = "0x0902f1ac"  # getReserves() (par V2)
SEL_TOKEN0 = "0x0dfe1681"  # token0()
SEL_TOKEN1 = "0xd21220a7"  # token1()
SEL_GET_PAIR = "0xe6a43905"  # getPair(address,address) (factory V2)
SEL_SLOT0 = "0x3850c7bd"  # slot0() (pool V3)
SEL_LIQUIDITY = "0x1a686502"  # liquidity() (pool V3)

# Endereço zero / burn canônico (EVM).
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
DEAD_ADDRESS = "0x000000000000000000000000000000000000dEaD"

DEFAULT_ENDPOINTS: dict[int, list[str]] = {
    56: [  # BNB Chain (dataseeds oficiais; testados em 2026-11-13)
        "https://bsc-dataseed.binance.org",
        "https://bsc-dataseed1.defibit.io",
        "https://bsc-dataseed1.ninicoin.io",
    ],
    1: [  # Ethereum (testados em 2026-11-13; LlamaRPC instável — 525)
        "https://cloudflare-eth.com",
        "https://ethereum-rpc.publicnode.com",
        "https://eth.llamarpc.com",
    ],
    8453: [  # Base (mainnet.base.org OK; OnFinality público com 429)
        "https://mainnet.base.org",
        "https://base.api.onfinality.io/public",
    ],
}


class EvmRpcError(Exception):
    """Falha de RPC EVM (rede, chain errada ou erro do nó)."""


def encode_address_arg(address: str) -> str:
    """Codifica um endereço como argumento ABI de 32 bytes (hex)."""
    addr = address.lower().removeprefix("0x")
    if len(addr) != 40 or any(c not in "0123456789abcdef" for c in addr):
        raise ValueError(f"endereco EVM invalido: {address!r}")
    return addr.rjust(64, "0")


def decode_uint256(hex_data: str, offset: int = 0) -> int:
    """Decodifica um uint256 de 32 bytes a partir de hex (0x...)."""
    raw = hex_data.removeprefix("0x")
    chunk = raw[offset * 64 : (offset + 1) * 64]
    if len(chunk) != 64:
        raise EvmRpcError(f"resposta eth_call curta demais: {hex_data!r}")
    return int(chunk, 16)


def decode_address(hex_data: str, offset: int = 0) -> str:
    """Decodifica um address (últimos 20 bytes do slot de 32)."""
    raw = hex_data.removeprefix("0x")
    chunk = raw[offset * 64 : (offset + 1) * 64]
    if len(chunk) != 64:
        raise EvmRpcError(f"resposta eth_call curta demais: {hex_data!r}")
    return "0x" + chunk[24:]


class EvmRpcClient:
    """JSON-RPC EVM com failover. Somente leitura."""

    def __init__(
        self,
        chain_id: int,
        endpoints: Optional[list[str]] = None,
        timeout: float = 10.0,
        session: Optional[Any] = None,
    ) -> None:
        self.chain_id = chain_id
        self.endpoints = endpoints or DEFAULT_ENDPOINTS.get(chain_id, [])
        if not self.endpoints:
            raise ValueError(f"sem endpoints publicos conhecidos p/ chain {chain_id}")
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
                last_error = EvmRpcError(f"rede em {url}: {exc}")
                continue
            if getattr(response, "status_code", 0) >= 400:
                last_error = EvmRpcError(
                    f"HTTP {response.status_code} em {url}"
                )
                continue
            try:
                body = response.json()
            except ValueError as exc:
                last_error = EvmRpcError(f"resposta nao-JSON em {url}: {exc}")
                continue
            if "error" in body and body["error"]:
                last_error = EvmRpcError(
                    f"RPC {method} em {url}: {body['error']}"
                )
                continue
            return body.get("result")
        assert last_error is not None
        raise last_error

    # -- leituras ------------------------------------------------------
    def block_number(self) -> int:
        """Altura atual do bloco."""
        return int(self.call_rpc("eth_blockNumber"), 16)

    def verify_chain_id(self) -> int:
        """Confere que o endpoint responde a chain esperada."""
        got = int(self.call_rpc("eth_chainId"), 16)
        if got != self.chain_id:
            raise EvmRpcError(
                f"chain_id divergente: esperado {self.chain_id}, obtido {got}"
            )
        return got

    def get_balance_wei(self, address: str) -> int:
        """Saldo nativo (wei) de um endereço."""
        return int(self.call_rpc("eth_getBalance", [address, "latest"]), 16)

    def get_code(self, address: str) -> str:
        """Bytecode de um endereço ('0x' = EOA, sem contrato)."""
        return str(self.call_rpc("eth_getCode", [address, "latest"]))

    def eth_call(self, to: str, data: str, block: str = "latest") -> str:
        """Chamada de leitura a um contrato. Retorna o hex bruto."""
        return str(
            self.call_rpc(
                "eth_call", [{"to": to, "data": data}, block]
            )
        )

    def get_logs(
        self,
        address: str,
        topics: list[str],
        from_block: str = "latest",
        to_block: str = "latest",
    ) -> list[dict[str, Any]]:
        """Logs de eventos (ex.: Swap de um par). Sem índice próprio."""
        result = self.call_rpc(
            "eth_getLogs",
            [
                {
                    "address": address,
                    "topics": topics,
                    "fromBlock": from_block,
                    "toBlock": to_block,
                }
            ],
        )
        return result if isinstance(result, list) else []

    # -- conveniências de leitura de token/par -------------------------
    def token_total_supply(self, token: str) -> int:
        return decode_uint256(self.eth_call(token, SEL_TOTAL_SUPPLY))

    def token_balance_of(self, token: str, holder: str) -> int:
        data = SEL_BALANCE_OF + encode_address_arg(holder)
        return decode_uint256(self.eth_call(token, data))

    def token_decimals(self, token: str) -> int:
        return decode_uint256(self.eth_call(token, SEL_DECIMALS))

    def contract_owner(self, contract: str) -> Optional[str]:
        """owner() de contrato Ownable; None se o contrato não tem owner."""
        try:
            return decode_address(self.eth_call(contract, SEL_OWNER))
        except (EvmRpcError, ValueError):
            return None

    def pair_reserves(self, pair: str) -> tuple[int, int, int]:
        """getReserves() de par V2: (reserve0, reserve1, timestamp)."""
        raw = self.eth_call(pair, SEL_GET_RESERVES)
        return (
            decode_uint256(raw, 0),
            decode_uint256(raw, 1),
            decode_uint256(raw, 2),
        )

    def pair_tokens(self, pair: str) -> tuple[str, str]:
        """(token0, token1) de um par V2."""
        token0 = decode_address(self.eth_call(pair, SEL_TOKEN0))
        token1 = decode_address(self.eth_call(pair, SEL_TOKEN1))
        return token0, token1

    def factory_get_pair(self, factory: str, token_a: str, token_b: str) -> str:
        """Endereço do par V2 na factory, ou o endereço zero."""
        data = (
            SEL_GET_PAIR
            + encode_address_arg(token_a)
            + encode_address_arg(token_b)
        )
        return decode_address(self.eth_call(factory, data))

    def v3_slot0(self, pool: str) -> tuple[int, int]:
        """slot0() de pool V3: (sqrtPriceX96, tick)."""
        raw = self.eth_call(pool, SEL_SLOT0)
        return decode_uint256(raw, 0), decode_uint256(raw, 1)

    def v3_liquidity(self, pool: str) -> int:
        """liquidity() de pool V3 (uint128)."""
        return decode_uint256(self.eth_call(pool, SEL_LIQUIDITY))

    def health(self) -> dict[str, Any]:
        """Estado: tenta ler o bloco atual (uma chamada real)."""
        try:
            block = self.block_number()
            return {
                "chain_id": self.chain_id,
                "connected": True,
                "status": "ok",
                "block_number": block,
            }
        except EvmRpcError as exc:
            return {
                "chain_id": self.chain_id,
                "connected": False,
                "status": "error",
                "error": str(exc),
            }
