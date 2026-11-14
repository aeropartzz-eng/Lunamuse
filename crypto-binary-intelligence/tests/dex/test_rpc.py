"""Testes dos clientes RPC públicos (Fase 6 — DEX-002…DEX-004).

Somente mocks, sem rede. Cobre: failover entre endpoints, verificação
de chain id, decodificação de eth_call (getReserves) e parse do layout
SPL Mint (mint/freeze authority).
"""

from __future__ import annotations

import base64

import pytest

from .helpers import adapter_path, load_module
from .fakes import FakeSession

evm = load_module("evm_rpc", adapter_path("rpc", "evm_rpc.py"))
sol = load_module("solana_rpc", adapter_path("rpc", "solana_rpc.py"))

EvmRpcClient = evm.EvmRpcClient
EvmRpcError = evm.EvmRpcError
SolanaRpcClient = sol.SolanaRpcClient
SolanaRpcError = sol.SolanaRpcError

PAIR = "0x1111111111111111111111111111111111111111"
TOKEN_A = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TOKEN_B = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _uint256(value: int) -> str:
    return format(value, "064x")


def _rpc_result(result, rpc_id=1):
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _evm_session_failover():
    """1o endpoint falha (rede via rota ausente), 2o responde."""
    session = FakeSession()
    # Endpoint 1: sem rota -> FakeSession levanta AssertionError, não
    # RequestException; por isso o failover é testado via HTTP 500.
    session.route("POST", "https://rpc1.example", {"error": "boom"}, status=500)
    session.route("POST", "https://rpc2.example",
                  _rpc_result("0x10"))
    return session


def test_evm_failover_para_segundo_endpoint():
    session = _evm_session_failover()
    client = EvmRpcClient(
        chain_id=56,
        endpoints=["https://rpc1.example", "https://rpc2.example"],
        session=session,
    )
    assert client.block_number() == 16
    assert len(session.calls) == 2


def test_evm_todos_endpoints_falham():
    session = FakeSession()
    session.route("POST", "https://rpc1.example", {"error": "boom"}, status=500)
    client = EvmRpcClient(chain_id=56, endpoints=["https://rpc1.example"], session=session)
    with pytest.raises(EvmRpcError):
        client.block_number()


def test_evm_verify_chain_id_ok_e_divergente():
    session = FakeSession()
    session.route("POST", "https://rpc1.example", _rpc_result("0x38"))
    client = EvmRpcClient(chain_id=56, endpoints=["https://rpc1.example"], session=session)
    assert client.verify_chain_id() == 56

    session2 = FakeSession()
    session2.route("POST", "https://rpc1.example", _rpc_result("0x1"))
    client2 = EvmRpcClient(chain_id=56, endpoints=["https://rpc1.example"], session=session2)
    with pytest.raises(EvmRpcError, match="chain_id divergente"):
        client2.verify_chain_id()


def test_evm_pair_reserves_decode():
    session = FakeSession()
    reserves = "0x" + _uint256(1_000_000) + _uint256(2_000_000) + _uint256(1_700_000_000)
    session.route("POST", "https://rpc1.example", _rpc_result(reserves))
    client = EvmRpcClient(chain_id=56, endpoints=["https://rpc1.example"], session=session)
    r0, r1, ts = client.pair_reserves(PAIR)
    assert (r0, r1, ts) == (1_000_000, 2_000_000, 1_700_000_000)


def test_evm_pair_tokens_e_factory():
    session = FakeSession()
    session.route_prefix("POST", "https://rpc1.example",
                         _rpc_result("0x" + _uint256(int(TOKEN_A, 16))))
    client = EvmRpcClient(chain_id=56, endpoints=["https://rpc1.example"], session=session)
    token0, token1 = client.pair_tokens(PAIR)
    assert token0.lower() == TOKEN_A.lower()
    assert token1.lower() == TOKEN_A.lower()  # fake responde o mesmo p/ ambos
    pair = client.factory_get_pair("0x00000000000000000000000000000000000000f0", TOKEN_A, TOKEN_B)
    assert pair.lower() == TOKEN_A.lower()


def test_evm_decode_curto_levanta():
    with pytest.raises(EvmRpcError):
        evm.decode_uint256("0x1234")


def test_evm_encode_address_invalido():
    with pytest.raises(ValueError):
        evm.encode_address_arg("nao-um-endereco")


def test_evm_health_ok_e_erro():
    session = FakeSession()
    session.route("POST", "https://rpc1.example", _rpc_result("0x10"))
    client = EvmRpcClient(chain_id=56, endpoints=["https://rpc1.example"], session=session)
    health = client.health()
    assert health["connected"] is True and health["block_number"] == 16

    session2 = FakeSession()
    session2.route("POST", "https://rpc1.example", {"error": "x"}, status=500)
    client2 = EvmRpcClient(chain_id=56, endpoints=["https://rpc1.example"], session=session2)
    assert client2.health()["connected"] is False


def _mint_account_bytes(mint_authority=None, freeze_authority=None,
                        supply=1_000_000_000, decimals=6):
    raw = bytearray(82)
    if mint_authority is not None:
        raw[0:4] = (1).to_bytes(4, "little")
        raw[4:36] = bytes.fromhex(mint_authority)
    raw[36:44] = supply.to_bytes(8, "little")
    raw[44] = decimals
    raw[45] = 1
    if freeze_authority is not None:
        raw[46:50] = (1).to_bytes(4, "little")
        raw[50:82] = bytes.fromhex(freeze_authority)
    return base64.b64encode(bytes(raw)).decode()


def test_solana_parse_mint_com_authorities():
    mint_auth = "aa" * 32
    freeze_auth = "bb" * 32
    data = _mint_account_bytes(mint_auth, freeze_auth)
    parsed = sol.parse_spl_mint_account(data)
    assert parsed["mint_authority"] == mint_auth
    assert parsed["freeze_authority"] == freeze_auth
    assert parsed["supply"] == 1_000_000_000
    assert parsed["decimals"] == 6
    assert parsed["is_initialized"] is True


def test_solana_parse_mint_authorities_revogadas():
    parsed = sol.parse_spl_mint_account(_mint_account_bytes())
    assert parsed["mint_authority"] is None
    assert parsed["freeze_authority"] is None


def test_solana_parse_mint_dado_curto():
    with pytest.raises(ValueError):
        sol.parse_spl_mint_account(base64.b64encode(b"curto").decode())


def test_solana_largest_accounts_e_supply():
    session = FakeSession()
    session.route_prefix("POST", "https://sol1.example",
                         _rpc_result({"value": {"amount": "1000000000", "decimals": 6, "uiAmount": 1000.0}}))
    client = SolanaRpcClient(endpoints=["https://sol1.example"], session=session)
    supply = client.get_token_supply("MINT")
    assert supply["amount"] == "1000000000"

    session2 = FakeSession()
    largest = [
        {"address": "AAA", "amount": "600000000", "decimals": 6, "uiAmount": 600.0},
        {"address": "BBB", "amount": "100000000", "decimals": 6, "uiAmount": 100.0},
    ]
    session2.route_prefix("POST", "https://sol1.example", _rpc_result({"value": largest}))
    client2 = SolanaRpcClient(endpoints=["https://sol1.example"], session=session2)
    accounts = client2.get_token_largest_accounts("MINT")
    assert len(accounts) == 2
    assert accounts[0]["address"] == "AAA"


def test_solana_find_creator_sem_assinaturas():
    session = FakeSession()
    session.route_prefix("POST", "https://sol1.example", _rpc_result({"value": []}))
    client = SolanaRpcClient(endpoints=["https://sol1.example"], session=session)
    result = client.find_mint_creator("MINT")
    assert result["creator"] is None
    assert "sem assinaturas" in result["reason"]


def test_solana_rpc_error_no_resultado():
    session = FakeSession()
    session.route_prefix("POST", "https://sol1.example",
                         {"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Invalid param"}})
    client = SolanaRpcClient(endpoints=["https://sol1.example"], session=session)
    with pytest.raises(SolanaRpcError):
        client.get_slot()
