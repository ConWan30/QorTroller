"""AST-driven extractor for the agents_rulings store domain (D-DECON-2 residue #8).

Tables: agent_sessions, agent_events, agent_rulings, ruling_streaks,
on_chain_rulings, ruling_validation_log, ruling_provenance_anchors,
agent_calibration_health, agent_context_log, agent_commit_log,
mythos_finding_log, mythos_cadence_log, escalation_ruling_log,
reactive_adjudication_log, supervisor_health_log, shadow_enforcement_log,
divergence_triage_reports (+ protocol insight/digest helpers).

STAY in _core (FROZEN-span scan 2026-06-19):
  insert_mythos_finding  — INV-MYTHOS-FROZEN-PROTECTION-001 pins store/_core.py
  get_curator_session_aggregate — INV-VHR-WIRING-003 pins store/_core.py
  get_prev_grind_chain_hash — INV-024 pins ORDER BY gic_ts_ns in _core.py

_init_schema STAY (CREATE TABLE anchor per D-DECON-2 sub-decision 4).

Usage:
    python scripts/_extract_agents_rulings_mixin.py --scan
    python scripts/_extract_agents_rulings_mixin.py --apply
"""
from __future__ import annotations

import ast
import builtins
import sys

CORE = "bridge/vapi_bridge/store/_core.py"
OUT = "bridge/vapi_bridge/store/agents.py"

TARGETS = [
    "store_agent_session",
    "get_agent_session",
    "delete_agent_session",
    "prune_old_agent_sessions",
    "store_protocol_insight",
    "get_recent_insights",
    "prune_old_insights",
    "get_insights_since",
    "store_insight_digest",
    "get_latest_digest",
    "get_all_latest_digests",
    "prune_old_digests",
    "write_agent_event",
    "read_unconsumed_events",
    "mark_event_consumed",
    "get_last_sbd_fire_ts",
    "insert_agent_ruling",
    "get_agent_rulings",
    "get_agent_ruling_by_id",
    "upsert_ruling_streak",
    "get_ruling_streak",
    "set_streak_escalation",
    "insert_on_chain_ruling",
    "get_on_chain_rulings",
    "get_on_chain_ruling_by_commitment",
    "get_unvalidated_rulings",
    "insert_validation_record",
    "override_gameplay_context",
    "insert_active_play_occupancy_log",
    "get_active_play_logs_for_validation_ids",
    "get_latest_active_play_occupancy_status",
    "get_validation_gate_status",
    "get_campaign_status",
    "insert_provenance_anchor",
    "get_provenance_anchor",
    "count_operator_overrides",
    "count_ceremony_key_rotations",
    "get_agent_activity",
    "insert_supervisor_health_log",
    "get_latest_supervisor_health",
    "insert_reactive_adjudication_log",
    "get_reactive_adjudication_log",
    "insert_synthetic_session",
    "get_corpus_status",
    "insert_protocol_intelligence_report",
    "get_latest_protocol_intelligence_report",
    "insert_shadow_enforcement_log",
    "get_shadow_enforcement_log",
    "get_shadow_enforcement_stats",
    "insert_divergence_triage_report",
    "get_divergence_triage_report",
    "insert_escalation_ruling_log",
    "get_escalation_ruling_log",
    "insert_class_j_assessment",
    "get_class_j_assessment",
    "insert_agent_calibration_health",
    "get_agent_calibration_health",
    "insert_mythos_cadence_run",
    "get_mythos_findings",
    "get_mythos_cadence_status",
    "upsert_agent_context_hash",
    "get_agent_context_status",
    "get_all_agent_context_status",
    "update_grind_chain_hash",
    "get_ruling_rows_for_chain",
    "get_grind_chain_status",
    "get_prev_gic_ts_ns",
    "insert_agent_commit",
    "get_agent_commit_status",
    "get_agent_commit_history",
]

_FORBIDDEN = {
    "_init_schema",
    "insert_mythos_finding",
    "get_curator_session_aggregate",
    "get_prev_grind_chain_hash",
    "get_validation_summary",
}

_BUILTINS = set(dir(builtins))

assert not (set(TARGETS) & _FORBIDDEN), "TARGETS overlaps a STAY/forbidden method!"


def _method_spans(src: str):
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    store = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Store")
    spans = {}
    nodes = {}
    for node in store.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS:
            start = node.lineno
            if node.decorator_list:
                start = min(d.lineno for d in node.decorator_list)
            spans[node.name] = (start, node.end_lineno)
            nodes[node.name] = node
    return lines, spans, nodes


def _free_globals(node: ast.AST) -> set[str]:
    bound = {"self"}
    loaded = set()
    fn = node
    for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs:
        bound.add(a.arg)
    if fn.args.vararg:
        bound.add(fn.args.vararg.arg)
    if fn.args.kwarg:
        bound.add(fn.args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            if isinstance(child.ctx, ast.Store):
                bound.add(child.id)
            elif isinstance(child.ctx, ast.Load):
                loaded.add(child.id)
        elif isinstance(child, ast.comprehension):
            for t in ast.walk(child.target):
                if isinstance(t, ast.Name):
                    bound.add(t.id)
    return {n for n in loaded if n not in bound and n not in _BUILTINS}


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--scan"
    src = open(CORE, encoding="utf-8").read()
    lines, spans, nodes = _method_spans(src)

    missing = [t for t in TARGETS if t not in spans]
    if missing:
        print("MISSING METHODS:", missing)
        return 2

    ordered = sorted(spans.items(), key=lambda kv: kv[1][0])
    captured = {name: "".join(lines[s - 1 : e]) for name, (s, e) in ordered}

    all_free: set[str] = set()
    per_method = {}
    for name, _ in ordered:
        free = _free_globals(nodes[name])
        per_method[name] = sorted(free)
        all_free |= free

    print(f"=== {len(ordered)} methods, line spans (file order) ===")
    for name, (s, e) in ordered:
        print(f"  {s:>6}-{e:<6} {name}  ({e - s + 1} lines)")
    print("\n=== free-global names referenced ===")
    for name in sorted(all_free):
        users = [m for m in per_method if name in per_method[m]]
        print(f"  {name:<28} <- {', '.join(users)}")
    if not all_free:
        print("  (none)")

    if mode == "--scan":
        return 0

    use_time = any("time." in c for c in captured.values())
    use_json = any("json." in c for c in captured.values())
    use_log = "log" in all_free
    use_math = "math" in all_free or "_math" in all_free

    header = [
        '"""AgentsRulingsMixin — D-DECON-2 agents_rulings domain extraction.',
        "",
        "Extracted verbatim from store/_core.py via the diff-oracle pattern.",
        "STAY in _core: insert_mythos_finding, get_curator_session_aggregate,",
        "get_prev_grind_chain_hash (FROZEN-span / INV pins).",
        '"""',
        "from __future__ import annotations",
        "",
    ]
    if use_json:
        header.append("import json")
    if use_log:
        header.append("import logging")
    if use_math:
        header.append("import math")
    if use_time:
        header.append("import time")
    header.append("")
    if use_log:
        header += ["log = logging.getLogger(__name__)", ""]
    header += [
        "",
        "class AgentsRulingsMixin:",
        '    """Agent sessions, rulings, validation, mythos cadence, commits; via MRO."""',
        "",
    ]

    body_parts = []
    for name, _ in ordered:
        block = captured[name]
        if not block.endswith("\n"):
            block += "\n"
        body_parts.append(block)
    out_text = "\n".join(header) + "\n".join(body_parts)
    open(OUT, "w", encoding="utf-8", newline="\n").write(out_text)
    print(f"\nWROTE {OUT} ({out_text.count(chr(10))} lines)")

    out_src = open(OUT, encoding="utf-8").read()
    out_lines = out_src.splitlines(keepends=True)
    otree = ast.parse(out_src)
    omix = next(n for n in otree.body if isinstance(n, ast.ClassDef) and n.name == "AgentsRulingsMixin")
    mismatches = []
    seen = set()
    for node in omix.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS:
            seen.add(node.name)
            s = node.lineno
            if node.decorator_list:
                s = min(d.lineno for d in node.decorator_list)
            moved = "".join(out_lines[s - 1 : node.end_lineno]).strip("\n")
            orig = captured[node.name].strip("\n")
            if moved != orig:
                mismatches.append(node.name)
    if mismatches or [t for t in TARGETS if t not in seen]:
        print("DIFF-ORACLE FAIL:", mismatches)
        return 3
    print(f"DIFF-ORACLE PASS: {len(seen)}/{len(TARGETS)} byte-identical")

    delete = set()
    for _name, (s, e) in ordered:
        for ln in range(s, e + 1):
            delete.add(ln)
        if e < len(lines) and lines[e].strip() == "":
            delete.add(e + 1)
    new_lines = [ln for i, ln in enumerate(lines, start=1) if i not in delete]
    open(CORE, "w", encoding="utf-8", newline="\n").write("".join(new_lines))
    print(f"REWROTE {CORE} (removed {len(lines) - len(new_lines)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
