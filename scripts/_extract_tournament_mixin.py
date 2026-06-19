"""AST-driven extractor for the tournament_activation store domain (D-DECON-2 residue #4).

Diff-oracle discipline: the exact source lines removed from store/_core.py ARE the
canonical source written into store/tournament.py (byte-identical move). CREATE TABLE
statements stay in _core.py._init_schema per D-DECON-2(4) — this only moves methods.

Usage:
    python scripts/_extract_tournament_mixin.py --scan    # report free-global deps, no writes
    python scripts/_extract_tournament_mixin.py --apply   # write tournament.py + rewrite _core.py
"""
from __future__ import annotations

import ast
import builtins
import sys

CORE = "bridge/vapi_bridge/store/_core.py"
OUT = "bridge/vapi_bridge/store/tournament.py"

TARGETS = [
    "store_tournament_passport",
    "get_tournament_passport",
    "insert_tournament_readiness_snapshot",
    "get_latest_tournament_readiness_snapshot",
    "insert_tournament_preflight_log",
    "get_tournament_preflight_status",
    "insert_tournament_activation_chain",
    "get_tournament_activation_chain",
    "get_tournament_blocker_summary",
    "insert_graduation_stage",
    "record_graduation_clean_session",
    "record_graduation_false_positive",
    "trigger_graduation_rollback",
    "get_graduation_stage_status",
    "get_all_graduation_stages",
    "insert_graduation_autowatch_log",
    "get_graduation_autowatch_status",
]

_BUILTINS = set(dir(builtins))


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
    """Names loaded but not bound locally/by params — i.e. resolved at module scope."""
    bound = {"self"}
    loaded = set()
    for fn in [node]:
        for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs:
            bound.add(a.arg)
        if fn.args.vararg:
            bound.add(fn.args.vararg.arg)
        if fn.args.kwarg:
            bound.add(fn.args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            if isinstance(child.ctx, (ast.Store,)):
                bound.add(child.id)
            elif isinstance(child.ctx, ast.Load):
                loaded.add(child.id)
        elif isinstance(child, (ast.comprehension,)):
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

    # dependency scan
    all_free: set[str] = set()
    per_method = {}
    for name, _ in ordered:
        free = _free_globals(nodes[name])
        # peer target methods called as bare names would be a problem, but these are
        # all self.<method> calls; bare TARGET names should never appear.
        per_method[name] = sorted(free)
        all_free |= free

    print(f"=== {len(ordered)} methods, line spans (file order) ===")
    for name, (s, e) in ordered:
        print(f"  {s:>6}-{e:<6} {name}  ({e - s + 1} lines)")
    print("\n=== free-global names referenced (must be importable into tournament.py) ===")
    for name in sorted(all_free):
        users = [m for m in per_method if name in per_method[m]]
        print(f"  {name:<28} <- {', '.join(users)}")
    if not all_free:
        print("  (none — methods only use self.* + builtins)")

    if mode == "--scan":
        return 0

    # --apply: build tournament.py
    use_time = any("time." in c for c in captured.values())
    use_json = any("json." in c for c in captured.values())
    use_log = "log" in all_free

    header = ['"""TournamentMixin — D-DECON-2 tournament_activation domain extraction.',
              "",
              "Extracted verbatim from store/_core.py via the diff-oracle pattern",
              "(removal diff is the canonical source). CREATE TABLE statements stay",
              "centralized in _core.py._init_schema per D-DECON-2(4).",
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
    header += ["", "class TournamentMixin:",
               '    """Tournament + graduation domain methods extracted from Store; resolved via MRO."""',
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

    # ---- in-process diff-oracle: post-move source == pre-removal capture ----
    out_src = open(OUT, encoding="utf-8").read()
    out_lines = out_src.splitlines(keepends=True)
    otree = ast.parse(out_src)
    omix = next(
        n for n in otree.body
        if isinstance(n, ast.ClassDef) and n.name == "TournamentMixin"
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

    # rewrite _core.py: delete the method spans (+ one trailing blank line each)
    delete = set()
    for name, (s, e) in ordered:
        for ln in range(s, e + 1):
            delete.add(ln)
        # one trailing blank line if present
        if e < len(lines) and lines[e].strip() == "":
            delete.add(e + 1)
    new_lines = [ln for i, ln in enumerate(lines, start=1) if i not in delete]
    open(CORE, "w", encoding="utf-8", newline="\n").write("".join(new_lines))
    removed = len(lines) - len(new_lines)
    print(f"REWROTE {CORE} (removed {removed} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
