"""AST-driven extractor for the biometric store domain (D-DECON-2 residue #7).

Tables: biometric_fingerprint_store, continuity_claims, gsr_samples,
biometric_renewal_log, biometric_renewal_chain_log, biometric_stationarity_log,
biometric_snapshot_log, persona_break_log, persona_break_attestation_log,
attestation_opsec_log, attestation_bound_renewal_log, maturity_elevation_log,
renewal_consent_snapshot_log, gsr_hmac_validation_log, ipact_renewal_commitments.

_init_schema STAY (CREATE TABLE anchor per D-DECON-2 sub-decision 4).

Usage:
    python scripts/_extract_biometric_mixin.py --scan
    python scripts/_extract_biometric_mixin.py --apply
"""
from __future__ import annotations

import ast
import builtins
import sys

CORE = "bridge/vapi_bridge/store/_core.py"
OUT = "bridge/vapi_bridge/store/biometric.py"

TARGETS = [
    "store_fingerprint_state",
    "get_fingerprint_variance",
    "mark_device_claimed",
    "is_device_claimed",
    "get_continuity_chain",
    "get_all_fingerprinted_devices",
    "get_controller_twin_snapshot",
    "insert_gsr_sample",
    "get_gsr_samples",
    "get_ipact_renewal_head",
    "get_prev_ipact_ts_ns",
    "insert_ipact_renewal_commitment",
    "get_ipact_renewal_chain",
    "insert_gsr_hmac_validation",
    "get_gsr_hmac_validation_status",
    "insert_biometric_renewal_chain_log",
    "get_biometric_renewal_chain_status",
    "insert_biometric_renewal_log",
    "get_biometric_credential_age_status",
    "insert_biometric_stationarity_log",
    "get_biometric_stationarity_status",
    "insert_attestation_opsec_log",
    "get_attestation_opsec_status",
    "insert_attestation_bound_renewal_log",
    "get_attestation_bound_renewal_status",
    "insert_persona_break_attestation",
    "get_active_attestation",
    "expire_stale_attestations",
    "insert_maturity_elevation_log",
    "get_maturity_elevation_status",
    "insert_persona_break_log",
    "get_persona_break_status",
    "insert_renewal_consent_snapshot",
    "get_renewal_consent_snapshot",
    "insert_biometric_snapshot",
    "get_latest_biometric_snapshot",
    "get_biometric_snapshot_status",
]

_FORBIDDEN = {"_init_schema"}

_BUILTINS = set(dir(builtins))

assert not (set(TARGETS) & _FORBIDDEN)


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
    use_hashlib = "hashlib" in all_free

    header = [
        '"""BiometricMixin — D-DECON-2 biometric domain extraction.',
        "",
        "Extracted verbatim from store/_core.py via the diff-oracle pattern.",
        "_init_schema (CREATE TABLE anchors) STAY in _core.",
        '"""',
        "from __future__ import annotations",
        "",
    ]
    if use_hashlib:
        header.append("import hashlib")
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
        "class BiometricMixin:",
        '    """Biometric fingerprint / renewal / persona-break methods; via MRO."""',
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
    omix = next(n for n in otree.body if isinstance(n, ast.ClassDef) and n.name == "BiometricMixin")
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
