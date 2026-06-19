"""Surgical move-back: return the 3 operator_agent insert methods from the mixin
to _core.py (P-check fix — DIGEST DRIFT on INV-OPERATOR-AGENT-002/003/006).

The 3 inserts carry the UNIQUE(...) docstring citations that those invariants
digest alongside the _init_schema CREATE TABLE line; they must stay in _core.
Byte-identical: methods are lifted verbatim from the mixin (which is itself
byte-identical to the pre-extraction _core source) and verified against
`git show HEAD`.
"""
from __future__ import annotations

import ast

CORE = "bridge/vapi_bridge/store/_core.py"
MIX = "bridge/vapi_bridge/store/operator_initiative.py"

RETURN = {
    "insert_operator_agent_activation": "    # --- Phase O1 C1: Operator Agent activation log helpers ---\n",
    "insert_operator_agent_shadow_log": "    # --- Phase O1 C2: Operator Agent Shadow Log helpers ---\n",
    "insert_operator_agent_drift": "    # --- Phase O1 C3: Operator Agent Drift Log helpers ---\n",
}


def _class_method_spans(src: str, class_name: str):
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    spans = {}
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            s = node.lineno
            if node.decorator_list:
                s = min(d.lineno for d in node.decorator_list)
            spans[node.name] = (s, node.end_lineno)
    return lines, spans


# 1. capture the 3 methods from the mixin (byte-identical)
msrc = open(MIX, encoding="utf-8").read()
mlines, mspans = _class_method_spans(msrc, "OperatorInitiativeMixin")
captured = {n: "".join(mlines[s - 1:e]) for n, (s, e) in mspans.items() if n in RETURN}
assert set(captured) == set(RETURN), f"missing in mixin: {set(RETURN) - set(captured)}"

# 2. remove them from the mixin (+ one trailing blank line each)
delete = set()
for n in RETURN:
    s, e = mspans[n]
    for ln in range(s, e + 1):
        delete.add(ln)
    if e < len(mlines) and mlines[e].strip() == "":
        delete.add(e + 1)
new_mlines = [ln for i, ln in enumerate(mlines, start=1) if i not in delete]
open(MIX, "w", encoding="utf-8", newline="\n").write("".join(new_mlines))
print(f"mixin: removed {len(mlines) - len(new_mlines)} lines (3 methods)")

# 3. insert each method into _core right after its section-header comment
csrc = open(CORE, encoding="utf-8").read()
clines = csrc.splitlines(keepends=True)
for name, header in RETURN.items():
    idx = next((i for i, ln in enumerate(clines) if ln == header), None)
    if idx is None:
        raise SystemExit(f"anchor header not found for {name}: {header!r}")
    block = captured[name]
    if not block.endswith("\n"):
        block += "\n"
    # header line at idx; insert method block right after it
    clines = clines[:idx + 1] + [block] + clines[idx + 1:]
open(CORE, "w", encoding="utf-8", newline="\n").write("".join(clines))
print(f"_core: inserted 3 methods after their C1/C2/C3 headers")
print("done")
