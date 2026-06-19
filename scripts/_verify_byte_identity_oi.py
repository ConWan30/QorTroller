"""Final diff-oracle: every operator_initiative method (23 moved to mixin + 3 returned
to _core) is byte-identical to its HEAD source. ioID WIP does not touch these methods,
so `git show HEAD:store/_core.py` is the canonical oracle.
"""
from __future__ import annotations

import ast
import subprocess

MOVED = {
    "get_operator_agent_activation_log", "get_current_operational_phase",
    "get_operator_agent_shadow_log", "get_operator_agent_shadow_summary",
    "get_operator_agent_drift_log", "get_latest_operator_agent_activation",
    "get_first_operator_agent_activation", "count_cedar_shadow_evaluations",
    "count_operator_agent_drift_findings", "insert_operator_agent_draft",
    "count_operator_agent_drafts", "record_operator_decision",
    "compute_operator_agent_disagreement_rate", "compute_operator_agent_false_positive_rate",
    "get_operator_agent_drafts", "insert_operator_initiative_advancement_log",
    "get_latest_operator_initiative_advancement", "get_operator_initiative_advancement_history",
    "get_accepted_unexecuted_drafts", "mark_draft_executed", "claim_draft_for_execution",
    "unclaim_draft_execution", "mark_draft_refused",
}
RETURNED = {
    "insert_operator_agent_activation", "insert_operator_agent_shadow_log",
    "insert_operator_agent_drift",
}
ALL = MOVED | RETURNED


def bodies(src: str, class_name: str, names: set[str]) -> dict[str, str]:
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    out = {}
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            s = node.lineno
            if node.decorator_list:
                s = min(d.lineno for d in node.decorator_list)
            out[node.name] = "".join(lines[s - 1:node.end_lineno]).strip("\n")
    return out


head_src = subprocess.run(
    ["git", "show", "HEAD:bridge/vapi_bridge/store/_core.py"],
    capture_output=True, check=True,
).stdout.decode("utf-8")
head = bodies(head_src, "Store", ALL)

mix = bodies(open("bridge/vapi_bridge/store/operator_initiative.py", encoding="utf-8").read(),
             "OperatorInitiativeMixin", MOVED)
core = bodies(open("bridge/vapi_bridge/store/_core.py", encoding="utf-8").read(),
              "Store", RETURNED)

fail = []
for n in sorted(MOVED):
    if n not in head:
        fail.append(f"{n}: absent in HEAD")
    elif n not in mix:
        fail.append(f"{n}: absent in mixin")
    elif head[n] != mix[n]:
        fail.append(f"{n}: BYTE MISMATCH (moved)")
for n in sorted(RETURNED):
    if n not in head:
        fail.append(f"{n}: absent in HEAD")
    elif n not in core:
        fail.append(f"{n}: absent in _core")
    elif head[n] != core[n]:
        fail.append(f"{n}: BYTE MISMATCH (returned)")

if fail:
    print("BYTE-IDENTITY FAIL:")
    for f in fail:
        print("  -", f)
    raise SystemExit(1)
print(f"BYTE-IDENTITY PASS: {len(MOVED)} moved + {len(RETURNED)} returned = "
      f"{len(ALL)}/{len(ALL)} byte-identical to HEAD source.")
