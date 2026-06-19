"""FROZEN-span scan for store/_core.py (pre-extraction gate, D-DECON-2 residue #5).

Maps every one of the 14 store-pinned invariants to the method that contains each
match. A pin whose matches all live in _init_schema (CREATE TABLE region) or in a
method that will STAY in _core is safe. A pin match inside a method slated to MOVE
is a finding — surface before the move.

The 14 patterns are copied verbatim from scripts/vapi_invariant_gate.py (the source
of truth); keep in sync if the gate changes.
"""
from __future__ import annotations

import ast
import re

CORE = "bridge/vapi_bridge/store/_core.py"

PINS = {
    "INV-003": r"7\.009",
    "INV-004": r"5\.367",
    "INV-022": r"governance_provenance_chain|insert_governance_provenance",
    "INV-024": r"gic_ts_ns\s+DESC|ORDER\s+BY\s+gic_ts_ns",
    "INV-025": r"_gic_chain_broken|set_gic_chain_broken",
    "INV-OPERATOR-AGENT-002": r"UNIQUE\(agent_id, to_scope_root\)",
    "INV-OPERATOR-AGENT-003": r"UNIQUE\(agent_id, action, resource, evaluated_at_bucket\)",
    "INV-OPERATOR-AGENT-006": r"UNIQUE\(agent_id, drift_type, detected_at_bucket\)",
    "INV-O3-SUPERSEDE-003": r"operator_initiative_auto_supersede_log|insert_operator_initiative_auto_supersede",
    "INV-PATH-B-002": r"operator_agent_chain_spending_log|insert_chain_spending_event|get_daily_chain_spending_for_agent",
    "INV-MYTHOS-FROZEN-PROTECTION-001": r"INV-MYTHOS-FROZEN-PROTECTION-001",
    "INV-SS2-PROBE-TYPE-001": r'"trigger_force_curve"',
    "INV-MLGA-STORE-TABLE-001": r"CREATE TABLE IF NOT EXISTS mlga_session_log",
    "INV-VHR-WIRING-003": r"def get_curator_session_aggregate\(self, session_id\)",
}

# min_matches from the gate (so we can flag if a move would drop _core below the floor)
MIN_MATCHES = {
    "INV-O3-SUPERSEDE-003": 2,
    "INV-PATH-B-002": 3,
}

src = open(CORE, encoding="utf-8").read()
lines = src.splitlines()
tree = ast.parse(src)
store = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Store")

members = {}  # name -> (start, end)
for node in store.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        s = node.lineno
        if node.decorator_list:
            s = min(d.lineno for d in node.decorator_list)
        members[node.name] = (s, node.end_lineno)


def containing(lineno: int) -> str:
    for name, (s, e) in members.items():
        if s <= lineno <= e:
            return name
    return "<class/module-level>"


print("=== FROZEN-span scan: 14 store pins -> containing method ===\n")
for pin, pat in PINS.items():
    rx = re.compile(pat)
    by_method: dict[str, list[int]] = {}
    total = 0
    for i, line in enumerate(lines, start=1):
        if rx.search(line):
            total += 1
            by_method.setdefault(containing(i), []).append(i)
    floor = MIN_MATCHES.get(pin)
    floor_s = f" (min_matches={floor})" if floor else ""
    print(f"{pin}: {total} match(es){floor_s}")
    for m, lns in sorted(by_method.items(), key=lambda kv: kv[1][0]):
        print(f"    {m:<46} @ {lns}")
    print()
