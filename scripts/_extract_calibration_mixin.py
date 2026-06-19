"""AST-driven extractor for the calibration store domain (D-DECON-2 residue #9).

STAY in _core (FROZEN-span / digest pins):
  insert_l4_router_log — INV-003/004 literal 7.009/5.367 digest in _core.py
  insert_controller_hardware_profile — INV-003/004 literal digest in _core.py
  STRUCTURED_PROBE_TYPES class attribute — INV-SS2-PROBE-TYPE-001 pins _core.py
  _init_schema — CREATE TABLE anchors (D-DECON-2 sub-decision 4)

Usage:
    python scripts/_extract_calibration_mixin.py --scan
    python scripts/_extract_calibration_mixin.py --apply
"""
from __future__ import annotations

import ast
import builtins
import sys

CORE = "bridge/vapi_bridge/store/_core.py"
OUT = "bridge/vapi_bridge/store/calibration.py"

TARGETS = [
    "insert_l6b_probe",
    "get_l6b_baseline",
    "get_nominal_records_for_calibration",
    "upsert_player_calibration_profile",
    "get_player_calibration_profile",
    "get_all_player_calibration_profiles",
    "store_l6_capture",
    "query_l6_captures",
    "count_l6_captures_by_profile",
    "write_threshold_history",
    "get_threshold_history",
    "get_last_global_recalibration_time",
    "count_records_since_last_calibration",
    "store_calib_agent_session",
    "load_calib_agent_session",
    "insert_epistemic_threshold_change",
    "get_epistemic_threshold_history",
    "insert_readiness_report",
    "get_latest_readiness_report",
    "insert_device_epoch_override",
    "get_device_epoch_override",
    "get_all_device_epoch_overrides",
    "delete_device_epoch_override",
    "increment_override_use_count",
    "get_override_lifecycle_status",
    "insert_bt_transport_log",
    "get_bt_transport_status",
    "insert_l4_calibration_log",
    "get_l4_calibration_log",
    "insert_l4_threshold_track",
    "get_l4_threshold_tracks",
    "insert_separation_ratio_snapshot",
    "get_separation_ratio_status",
    "insert_confidence_multiplier_log",
    "get_confidence_multiplier_log",
    "insert_l4_battery_calibration_run",
    "get_l4_battery_calibration_runs",
    "get_l4_router_log",
    "insert_readiness_score",
    "get_readiness_scores",
    "insert_separation_ratio_breakthrough",
    "get_separation_ratio_breakthrough",
    "insert_usb_reconnect_log",
    "get_usb_stability_status",
    "insert_l4_recalibration_job",
    "update_l4_recalibration_job",
    "get_l4_recalibration_jobs",
    "insert_separation_defensibility_log",
    "insert_separation_defensibility_log_guarded",
    "insert_corpus_regression_override",
    "get_corpus_regression_guard_status",
    "insert_l4_dim_sync",
    "get_l4_dim_sync_status",
    "insert_per_pair_gap",
    "get_per_pair_gap_status",
    "get_per_pair_gap_trend",
    "get_separation_defensibility_status",
    "get_enrollment_capture_guidance",
    "insert_centroid_velocity_log",
    "get_centroid_velocity_status",
    "compute_centroid_velocity",
    "insert_separation_ratio_registry_log",
    "get_separation_ratio_registry_status",
    "update_separation_ratio_registry_committed",
    "compute_separation_ratio_commit_hash",
    "insert_capture_stagnation_log",
    "get_capture_stagnation_status",
    "compute_capture_stagnation",
    "get_capture_velocity_oracle_status",
    "get_per_pair_gap_projection",
    "get_controller_hardware_profiles",
    "insert_enrollment_guidance_log",
    "get_enrollment_guidance_status",
    "insert_separation_ratio_recovery_log",
    "get_separation_ratio_recovery_status",
    "register_calibration_session",
    "insert_tremor_convergence_log",
    "get_tremor_convergence_status",
    "get_tremor_convergence_history",
    "insert_ait_session",
    "get_ait_separation_status",
    "insert_capture_health_event",
    "get_capture_health_status",
    "insert_gamer_readiness_log",
    "get_gamer_readiness_status",
]

_FORBIDDEN = {
    "_init_schema",
    "insert_l4_router_log",
    "insert_controller_hardware_profile",
}

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
    use_corpus_err = any("CorpusRegressionError" in c for c in captured.values())

    header = [
        '"""CalibrationMixin — D-DECON-2 calibration domain extraction.',
        "",
        "Extracted verbatim from store/_core.py via the diff-oracle pattern.",
        "STAY in _core: insert_l4_router_log, insert_controller_hardware_profile,",
        "STRUCTURED_PROBE_TYPES (INV pins), _init_schema.",
        '"""',
        "from __future__ import annotations",
        "",
    ]
    if use_corpus_err:
        header.append("from ._core import CorpusRegressionError")
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
        "class CalibrationMixin:",
        '    """L4/L6 calibration, separation defensibility, capture health; via MRO."""',
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
    omix = next(n for n in otree.body if isinstance(n, ast.ClassDef) and n.name == "CalibrationMixin")
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
