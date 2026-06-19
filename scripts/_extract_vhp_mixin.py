"""AST-driven extractor for the vhp_credentials store domain (D-DECON-2 residue #6).

Tables (decon-store-map): phg_checkpoints, phg_credential_mints, vhp_issuances,
vhp_renewal_log, vhp_reenrollment_badge_log, vhp_dual_gate_log, tournament_passports
(schema only), credential_enforcement, device_enrollments, device_risk_labels,
detection_policies.

ioid_devices methods STAY in _core (controller-identity domain, cafee3aa seam).
_init_schema STAY (CREATE TABLE anchor per D-DECON-2 sub-decision 4).

Usage:
    python scripts/_extract_vhp_mixin.py --scan
    python scripts/_extract_vhp_mixin.py --apply
"""
from __future__ import annotations

import ast
import builtins
import sys

CORE = "bridge/vapi_bridge/store/_core.py"
OUT = "bridge/vapi_bridge/store/vhp.py"

TARGETS = [
    "get_last_phg_checkpoint",
    "store_phg_checkpoint",
    "get_phg_checkpoints",
    "mark_checkpoint_confirmed",
    "get_unconfirmed_checkpoints",
    "store_credential_mint",
    "get_credential_mint",
    "upsert_enrollment",
    "get_enrollment",
    "get_eligible_unenrolled",
    "get_leaderboard",
    "set_device_risk_label",
    "get_device_risk_label",
    "get_devices_by_risk_label",
    "store_detection_policy",
    "get_detection_policy",
    "get_all_active_policies",
    "clear_detection_policy",
    "get_credential_enforcement",
    "increment_consecutive_critical",
    "reset_consecutive_critical",
    "store_credential_suspension",
    "is_credential_suspended",
    "clear_credential_suspension",
    "get_all_suspended_credentials",
    "get_expired_suspensions",
    "mark_suspension_reinstated",
    "get_device_suspension",
    "insert_vhp_issuance",
    "get_vhp_status",
    "insert_vhp_renewal",
    "get_vhp_renewal_log",
    "get_expiring_vhps",
    "get_total_vhp_count",
    "get_first_vhp_status",
    "get_epoch_window_analytics",
    "get_epoch_window_analytics_by_device",
    "insert_vhp_dual_gate_log",
    "get_vhp_dual_gate_log",
    "insert_reenrollment_badge_log",
    "get_reenrollment_badge_status",
]

_FORBIDDEN = {
    "_init_schema",
    "store_ioid_device",
    "get_ioid_device",
    "get_all_ioid_devices",
    "get_ioid_devices",
}

_BUILTINS = set(dir(builtins))

assert not (set(TARGETS) & _FORBIDDEN), "TARGETS overlaps STAY/forbidden!"


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

    bare_target_refs = {t for t in TARGETS if t in all_free}
    if bare_target_refs:
        print("\n!!! bare peer-method refs:", bare_target_refs)

    if mode == "--scan":
        return 0

    use_time = any("time." in c for c in captured.values())
    use_json = any("json." in c for c in captured.values())
    use_log = "log" in all_free

    header = [
        '"""VhpMixin — D-DECON-2 vhp_credentials domain extraction.',
        "",
        "Extracted verbatim from store/_core.py via the diff-oracle pattern.",
        "_init_schema (CREATE TABLE anchors) and ioid_devices helpers STAY in _core.",
        '"""',
        "from __future__ import annotations",
        "",
    ]
    if use_json:
        header.append("import json")
    if use_log:
        header.append("import logging")
    if use_time:
        header.append("import time")
    header.append("")
    if use_log:
        header += ["log = logging.getLogger(__name__)", ""]
    header += [
        "",
        "class VhpMixin:",
        '    """VHP / PHG credential / enrollment / enforcement methods; resolved via MRO."""',
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
    omix = next(n for n in otree.body if isinstance(n, ast.ClassDef) and n.name == "VhpMixin")
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
    missing_moved = [t for t in TARGETS if t not in seen]
    if mismatches or missing_moved:
        print("DIFF-ORACLE FAIL:", {"byte_mismatch": mismatches, "absent": missing_moved})
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
