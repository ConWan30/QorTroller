"""Enumerate the operator_initiative domain surface in store/_core.py.

Maps each Store method to the operator-initiative tables it references, then
partitions into STAY (the 7 cluster methods pinned by INV-O3-SUPERSEDE-003 /
INV-PATH-B-002 with no _init_schema anchor) vs MOVE (the rest of the domain).
"""
from __future__ import annotations

import ast
import re

CORE = "bridge/vapi_bridge/store/_core.py"

DOMAIN_TABLES = [
    "operator_agent_activation_log",
    "operator_agent_shadow_log",
    "operator_agent_drift_log",
    "operator_initiative_auto_supersede_log",
    "operator_agent_chain_spending_log",
    "operator_agent_drafts",
    "advancement_log",
    "operator_agent_readiness",
]

# The 7 methods that MUST stay in _core (per FROZEN-span scan + GO design).
STAY = {
    "_ensure_operator_initiative_auto_supersede_table",
    "insert_operator_initiative_auto_supersede",
    "get_latest_operator_initiative_auto_supersede",
    "get_operator_initiative_auto_supersede_status",
    "_ensure_operator_agent_chain_spending_table",
    "insert_chain_spending_event",
    "get_daily_chain_spending_for_agent",
}

src = open(CORE, encoding="utf-8").read()
lines = src.splitlines()
tree = ast.parse(src)
store = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Store")

tbl_rx = re.compile("|".join(re.escape(t) for t in DOMAIN_TABLES))

methods = []  # (name, start, end, tables_referenced)
for node in store.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        s = node.lineno
        if node.decorator_list:
            s = min(d.lineno for d in node.decorator_list)
        e = node.end_lineno
        body_txt = "\n".join(lines[s - 1 : e])
        tables = sorted({m.group(0) for m in tbl_rx.finditer(body_txt)})
        if tables:
            methods.append((node.name, s, e, tables))

move = [m for m in methods if m[0] not in STAY]
stay = [m for m in methods if m[0] in STAY]

print(f"=== operator_initiative domain: {len(methods)} methods touch domain tables ===\n")
print(f"--- STAY in _core ({len(stay)}) ---")
for name, s, e, tables in stay:
    print(f"  {name:<52} L{s}-{e}  {tables}")
print(f"\n--- MOVE to mixin ({len(move)}) ---")
for name, s, e, tables in move:
    print(f"  {name:<52} L{s}-{e}  {tables}")

# sanity: did we capture all 7 STAY methods?
captured = {m[0] for m in stay}
missing = STAY - captured
if missing:
    print(f"\n!!! STAY methods NOT found by table-ref enumeration: {missing}")
    print("    (they may reference the table only via _ensure helper call — check manually)")
