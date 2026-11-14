"""Validador Fase 2 — sem banco: sqlparse + checagens estruturais.
Uso: python3 /tmp/validate_fase2.py
"""
import re, sys
import sqlparse
import yaml

FILES = [
    "/home/hatch/workspace/crypto-binary-intelligence/infrastructure/database/001_init.sql",
    "/home/hatch/workspace/crypto-binary-intelligence/infrastructure/database/002_market.sql",
    "/home/hatch/workspace/crypto-binary-intelligence/infrastructure/database/003_intelligence.sql",
    "/home/hatch/workspace/crypto-binary-intelligence/infrastructure/database/004_execution.sql",
    "/home/hatch/workspace/crypto-binary-intelligence/infrastructure/database/005_operations.sql",
]
YAML_FILE = "/home/hatch/workspace/crypto-binary-intelligence/infrastructure/messaging/nats-streams.yaml"

EXPECTED_TABLES = {
    "001_init.sql": ["exchanges", "system_events", "audit_logs", "connection_status",
                     "exchange_products", "markets", "instruments", "networks", "tokens", "pools"],
    "002_market.sql": ["market_trades", "market_candles", "orderbook_snapshots", "orderbook_events",
                       "market_tickers", "funding_rates", "open_interest", "liquidations", "onchain_events"],
    "003_intelligence.sql": ["market_indicators", "market_patterns", "market_regimes", "market_features",
                             "strategies", "strategy_versions", "strategy_signals", "strategy_results",
                             "model_versions", "model_predictions"],
    "004_execution.sql": ["exchange_accounts", "execution_orders", "execution_fills", "positions",
                          "portfolio_snapshots", "risk_events", "reconciliation_events"],
    "005_operations.sql": ["users", "roles", "permissions", "role_permissions", "user_roles",
                           "notifications", "notification_deliveries", "schema_migrations"],
}
HYPERTABLES = ["market_trades", "market_candles", "orderbook_snapshots", "orderbook_events",
               "market_tickers", "funding_rates", "open_interest", "liquidations", "onchain_events",
               "market_indicators", "market_patterns", "market_regimes", "market_features",
               "strategy_signals", "model_predictions", "execution_fills", "portfolio_snapshots"]

errors, warnings = [], []
all_tables, all_hypertables = {}, set()

for path in FILES:
    name = path.split("/")[-1]
    sql = open(path, encoding="utf-8").read()
    # sem senhas literais
    for pat in [r"(?i)password\s*=\s*'[^']+'", r"(?i)api[_-]?key\s*=\s*'[^']{8,}'"]:
        if re.search(pat, sql):
            errors.append(f"{name}: possivel segredo literal ({pat})")
    stmts = [s for s in sqlparse.split(sql) if s.strip()]
    # ignora blocos formados só por comentários (ex.: nota final do arquivo)
    def _has_code(s):
        txt = sqlparse.format(s, strip_comments=True).strip()
        return bool(txt)
    stmts = [s for s in stmts if _has_code(s)]
    # parênteses balanceados por statement (ignorando strings/comentários via tokens)
    for i, s in enumerate(stmts, 1):
        depth = 0
        for tok in sqlparse.parse(s)[0].flatten():
            if tok.ttype in sqlparse.tokens.String or tok.ttype in sqlparse.tokens.Comment:
                continue
            for ch in tok.value:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth < 0:
                        errors.append(f"{name} stmt#{i}: parentese extra ')'")
        if depth != 0:
            errors.append(f"{name} stmt#{i}: parenteses desbalanceados (depth={depth})")
        if not s.strip().endswith(";"):
            errors.append(f"{name} stmt#{i}: nao termina com ';'")
    # CREATE TABLE -> PK?
    for m in re.finditer(r"(?i)CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*\(", sql):
        tbl = m.group(1)
        all_tables.setdefault(name, []).append(tbl)
        # corpo: do '(' até o matching ')'
        j, d = m.end() - 1, 0
        while j < len(sql):
            if sql[j] == "(":
                d += 1
            elif sql[j] == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        body = sql[m.end():j]
        if "PRIMARY KEY" not in body.upper():
            errors.append(f"{name}: tabela {tbl} sem PRIMARY KEY")
    # hypertables declaradas
    for m in re.finditer(r"(?i)create_hypertable\('(\w+)'", sql):
        all_hypertables.add(m.group(1))
    # duplicatas de CREATE TABLE no mesmo arquivo
    dupes = {t for t in all_tables[name] if all_tables[name].count(t) > 1}
    if dupes:
        errors.append(f"{name}: CREATE TABLE duplicado: {dupes}")
    # esperado presente?
    missing = [t for t in EXPECTED_TABLES[name] if t not in all_tables[name]]
    if missing:
        errors.append(f"{name}: tabelas esperadas ausentes: {missing}")
    extra = [t for t in all_tables[name] if t not in EXPECTED_TABLES[name]]
    if extra:
        warnings.append(f"{name}: tabelas extras (fora do esperado): {extra}")
    print(f"{name}: {len(stmts)} statements, {len(all_tables[name])} tabelas — OK estrutural")

# duplicatas entre arquivos
seen = {}
for fname, tbls in all_tables.items():
    for t in tbls:
        if t in seen:
            errors.append(f"tabela {t} definida em {seen[t]} e em {fname}")
        seen[t] = fname

missing_hyper = [t for t in HYPERTABLES if t not in all_hypertables]
if missing_hyper:
    errors.append(f"hypertables sem create_hypertable: {missing_hyper}")
print(f"hypertables declaradas: {len(all_hypertables)} (esperadas {len(HYPERTABLES)})")

# YAML
try:
    data = yaml.safe_load(open(YAML_FILE, encoding="utf-8"))
    streams = {s["name"]: s for s in data["streams"]}
    assert set(streams) == {"MARKET", "SIGNALS", "EXECUTION", "SYSTEM"}, streams.keys()
    for sname, s in streams.items():
        assert s["subjects"], f"{sname} sem subjects"
        assert s["max_age"] and s["retention"] == "limits" and s["storage"] == "file"
        assert s["num_replicas"] == 1
    assert data["consumer_defaults"]["ack_policy"] == "explicit"
    print(f"YAML OK: {len(streams)} streams, subjects totais={sum(len(s['subjects']) for s in streams.values())}")
except Exception as e:
    errors.append(f"YAML invalido: {e}")

print(f"\nTOTAL tabelas: {sum(len(v) for v in all_tables.values())}")
for w in warnings:
    print("AVISO:", w)
if errors:
    print(f"\nERROS ({len(errors)}):")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("\nVALIDACAO OK — nenhum erro.")
