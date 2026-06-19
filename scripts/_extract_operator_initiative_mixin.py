"""AST-driven extractor for the operator_initiative store domain (D-DECON-2 residue #5).

Diff-oracle discipline: the exact source lines removed from store/_core.py ARE the
canonical source written into store/operator_initiative.py (byte-identical move).

INV-022-class treatment (FROZEN-span scan, 2026-06-19): the auto_supersede and
chain_spending clusters (7 methods) carry INV-O3-SUPERSEDE-003 / INV-PATH-B-002 with
NO _init_schema anchor (their CREATE TABLEs live in _ensure_*_table methods), so they
STAY in _core and are deliberately excluded from TARGETS. _init_schema also stays (it
anchors INV-OPERATOR-AGENT-002/003/006 via its CREATE TABLEs). This moves only the
26 unpinned domain methods; invariant definitions are untouched.

Usage:
    python scripts/_extract_operator_initiative_mixin.py --scan    # report deps, no writes
    python scripts/_extract_operator_initiative_mixin.py --apply   # write mixin + rewrite _core.py
"""
from __future__ import annotations

import ast
import builtins
import sys

CORE = "bridge/vapi_bridge/store/_core.py"
OUT = "bridge/vapi_bridge/store/operator_initiative.py"

TARGETS = [
    "get_operator_agent_activation_log",
    "get_current_operational_phase",
    "get_operator_agent_shadow_log",
    "get_operator_agent_shadow_summary",
    "get_operator_agent_drift_log",
    "get_latest_operator_agent_activation",
    "get_first_operator_agent_activation",
    "count_cedar_shadow_evaluations",
    "count_operator_agent_drift_findings",
    "insert_operator_agent_draft",
    "count_operator_agent_drafts",
    "record_operator_decision",
    "compute_operator_agent_disagreement_rate",
    "compute_operator_agent_false_positive_rate",
    "get_operator_agent_drafts",
    "insert_operator_initiative_advancement_log",
    "get_latest_operator_initiative_advancement",
    "get_operator_initiative_advancement_history",
    "get_accepted_unexecuted_drafts",
    "mark_draft_executed",
    "claim_draft_for_execution",
    "unclaim_draft_execution",
    "mark_draft_refused",
]

# Methods that MUST NOT move — guard against accidental inclusion.
# 7 cluster methods (FROZEN-span scan: INV-O3-SUPERSEDE-003 / INV-PATH-B-002, no
# _init_schema anchor) + _init_schema + the 3 operator_agent insert methods whose
# UNIQUE(...) docstrings the gate DIGESTS for INV-OPERATOR-AGENT-002/003/006 (P-check
# 2026-06-19: min_matches survived a move but the matched-line digest did not).
_FORBIDDEN = {
    "_init_schema",
    "_ensure_operator_initiative_auto_supersede_table",
    "insert_operator_initiative_auto_supersede",
    "get_latest_operator_initiative_auto_supersede",
    "get_operator_initiative_auto_supersede_status",
    "_ensure_operator_agent_chain_spending_table",
    "insert_chain_spending_event",
    "get_daily_chain_spending_for_agent",
    "insert_operator_agent_activation",
    "insert_operator_agent_shadow_log",
    "insert_operator_agent_drift",
}

_BUILTINS = set(dir(builtins))

assert not (set(TARGETS) & _FORBIDDEN), "TARGETS overlaps a STAY/forbidden method!"


def _method_spans(src: str):
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    store = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "Store"
    )
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
    captured = {name: "".join(lines[s - 1:e]) for name, (s, e) in ordered}

    all_free: set[str] = set()
    per_method = {}
    for name, _ in ordered:
        free = _free_globals(nodes[name])
        per_method[name] = sorted(free)
        all_free |= free

    print(f"=== {len(ordered)} methods, line spans (file order) ===")
    for name, (s, e) in ordered:
        print(f"  {s:>6}-{e:<6} {name}  ({e - s + 1} lines)")
    print("\n=== free-global names referenced (must be importable into mixin) ===")
    for name in sorted(all_free):
        users = [m for m in per_method if name in per_method[m]]
        print(f"  {name:<28} <- {', '.join(users)}")
    if not all_free:
        print("  (none — methods only use self.* + builtins)")

    # bare TARGET-name calls would break under MRO (must be self.<m>); flag them
    bare_target_refs = {t for t in TARGETS if t in all_free}
    if bare_target_refs:
        print("\n!!! bare peer-method refs (should be self.<m>):", bare_target_refs)

    if mode == "--scan":
        return 0

    use_time = any("time." in c for c in captured.values())
    use_json = any("json." in c for c in captured.values())
    use_log = "log" in all_free

    header = ['"""OperatorInitiativeMixin — D-DECON-2 operator_initiative domain extraction.',
              "",
              "Extracted verbatim from store/_core.py via the diff-oracle pattern",
              "(removal diff is the canonical source). The auto_supersede + chain_spending",
              "clusters (INV-O3-SUPERSEDE-003 / INV-PATH-B-002, no _init_schema anchor) and",
              "_init_schema itself STAY in _core.py per the 2026-06-19 FROZEN-span scan;",
              "only the 26 unpinned domain methods move here. Resolved via MRO.",
              '"""',
              "from __future__ import annotations",
              ""]
    if use_json:
        header.append("import json")
    if use_log:
        header.append("import logging")
    if use_time:
        header.append("import time")
    header.append("")
    if use_log:
        header += ["log = logging.getLogger(__name__)", ""]
    header += ["", "class OperatorInitiativeMixin:",
               '    """Operator Initiative (activation/shadow/drift/drafts/advancement) methods',
               '    extracted from Store; resolved via MRO."""',
               ""]

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
    omix = next(
        n for n in otree.body
        if isinstance(n, ast.ClassDef) and n.name == "OperatorInitiativeMixin"
    )
    mismatches = []
    seen = set()
    for node in omix.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS:
            seen.add(node.name)
            s = node.lineno
            if node.decorator_list:
                s = min(d.lineno for d in node.decorator_list)
            moved = "".join(out_lines[s - 1:node.end_lineno]).strip("\n")
            orig = captured[node.name].strip("\n")
            if moved != orig:
                mismatches.append(node.name)
    missing_moved = [t for t in TARGETS if t not in seen]
    if mismatches or missing_moved:
        print("DIFF-ORACLE FAIL:", {"byte_mismatch": mismatches, "absent": missing_moved})
        return 3
    print(f"DIFF-ORACLE PASS: {len(seen)}/{len(TARGETS)} methods byte-identical to pre-removal source")

    delete = set()
    for name, (s, e) in ordered:
        for ln in range(s, e + 1):
            delete.add(ln)
        if e < len(lines) and lines[e].strip() == "":
            delete.add(e + 1)
    new_lines = [ln for i, ln in enumerate(lines, start=1) if i not in delete]
    open(CORE, "w", encoding="utf-8", newline="\n").write("".join(new_lines))
    removed = len(lines) - len(new_lines)
    print(f"REWROTE {CORE} (removed {removed} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
