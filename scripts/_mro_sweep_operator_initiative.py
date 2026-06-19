"""MRO + duplicate sweep for the operator_initiative extraction (residue #5)."""
from __future__ import annotations

from bridge.vapi_bridge.store._core import Store
from bridge.vapi_bridge.store.operator_initiative import OperatorInitiativeMixin

MOVED = [
    "get_operator_agent_activation_log",
    "get_current_operational_phase",
    "get_operator_agent_shadow_log", "get_operator_agent_shadow_summary",
    "get_operator_agent_drift_log",
    "get_latest_operator_agent_activation", "get_first_operator_agent_activation",
    "count_cedar_shadow_evaluations", "count_operator_agent_drift_findings",
    "insert_operator_agent_draft", "count_operator_agent_drafts",
    "record_operator_decision", "compute_operator_agent_disagreement_rate",
    "compute_operator_agent_false_positive_rate", "get_operator_agent_drafts",
    "insert_operator_initiative_advancement_log",
    "get_latest_operator_initiative_advancement",
    "get_operator_initiative_advancement_history",
    "get_accepted_unexecuted_drafts", "mark_draft_executed",
    "claim_draft_for_execution", "unclaim_draft_execution", "mark_draft_refused",
]

STAY = [
    "_ensure_operator_initiative_auto_supersede_table",
    "insert_operator_initiative_auto_supersede",
    "get_latest_operator_initiative_auto_supersede",
    "get_operator_initiative_auto_supersede_status",
    "_ensure_operator_agent_chain_spending_table",
    "insert_chain_spending_event",
    "get_daily_chain_spending_for_agent",
    # P-check 2026-06-19: kept in _core to preserve INV-OPERATOR-AGENT-002/003/006 digests
    "insert_operator_agent_activation",
    "insert_operator_agent_shadow_log",
    "insert_operator_agent_drift",
]

fail = []

# 1. all 26 moved methods resolve on Store
for m in MOVED:
    if not hasattr(Store, m):
        fail.append(f"MOVED not resolvable on Store: {m}")

# 2. moved methods come FROM the mixin (not _core's Store dict)
core_dict = Store.__dict__
for m in MOVED:
    if m in core_dict:
        fail.append(f"MOVED still in Store.__dict__ (duplicate in _core): {m}")
    if m not in OperatorInitiativeMixin.__dict__:
        fail.append(f"MOVED not in OperatorInitiativeMixin.__dict__: {m}")

# 3. STAY methods remain defined in _core's Store dict
for m in STAY:
    if m not in core_dict:
        fail.append(f"STAY missing from Store.__dict__ (_core): {m}")
    if m in OperatorInitiativeMixin.__dict__:
        fail.append(f"STAY leaked into mixin: {m}")

# 4. mixin is in the MRO
if OperatorInitiativeMixin not in Store.__mro__:
    fail.append("OperatorInitiativeMixin not in Store.__mro__")

if fail:
    print("MRO SWEEP FAIL:")
    for f in fail:
        print("  -", f)
    raise SystemExit(1)

print(f"MRO SWEEP PASS: {len(MOVED)}/23 moved methods resolve via OperatorInitiativeMixin; "
      f"{len(STAY)}/10 STAY methods remain in _core Store.__dict__; no duplicates.")
