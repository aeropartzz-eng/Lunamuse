"""Smoke check ao vivo da Fase 6 (DEX e Crypto Shield).

Uma consulta pública real por fonte (somente leitura, sem chave),
para provar que as integrações funcionam fora dos mocks. Uso::

    python3 scripts/smoke_phase6.py

Saída esperada: cada fonte imprime OK + 1 dado real, ou FALHA com o
motivo (sem fingir sucesso). Não executa nada, não envia transação.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "services" / "dex-connectors"))
sys.path.append(str(ROOT / "services" / "dex-connectors" / "rpc"))
sys.path.append(str(ROOT / "services" / "crypto-shield"))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    dex = ROOT / "services" / "dex-connectors"
    dexscreener = load("smoke_dexscreener", dex / "dexscreener" / "adapter.py")
    raydium = load("smoke_raydium", dex / "raydium" / "adapter.py")
    jupiter = load("smoke_jupiter", dex / "jupiter" / "adapter.py")
    evm_rpc = load("smoke_evm_rpc", dex / "rpc" / "evm_rpc.py")
    sol_rpc = load("smoke_solana_rpc", dex / "rpc" / "solana_rpc.py")

    failures = 0

    def check(label, fn):
        nonlocal failures
        try:
            detail = fn()
            print(f"OK    {label}: {detail}")
        except Exception as exc:  # noqa: BLE001 - smoke reporta e segue
            failures += 1
            print(f"FALHA {label}: {exc}")

    ds = dexscreener.DexscreenerAdapter()

    def _dexscreener_search():
        pairs = ds.search_pairs("BONK")
        first = pairs[0]
        return (
            f"{len(pairs)} pares; "
            f"1o={first['dex']} {first['base_token']['symbol']} "
            f"liq USD {first['liquidity_usd']}"
        )

    check("DEX Screener search BONK", _dexscreener_search)
    ray = raydium.RaydiumAdapter()
    check(
        "Raydium pools BONK",
        lambda: (
            f"{len(ray.get_pools_by_mint('DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263', page_size=2))} pools"
        ),
    )
    jup = jupiter.JupiterAdapter()
    check(
        "Jupiter price SOL (v3)",
        lambda: (
            "USD "
            + str(
                jup.get_price(
                    ["So11111111111111111111111111111111111111112"]
                )["So11111111111111111111111111111111111111112"]["usdPrice"]
            )
        ),
    )
    bsc = evm_rpc.EvmRpcClient(chain_id=56)
    check("BSC RPC blockNumber", lambda: f"bloco {bsc.block_number()}")
    sol = sol_rpc.SolanaRpcClient()
    check("Solana RPC getSlot", lambda: f"slot {sol.get_slot()}")

    print(f"\nSmoke Fase 6: {'OK' if failures == 0 else f'{failures} falha(s)'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
