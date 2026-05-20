"""Regenerate every vpm_artifact_log HTML file with the current compiler
template, then reconcile each row's compiler_output_hash_hex.

Why this exists
---------------
The served VPM proof artifacts are immutable HTML files on disk (operator_api
serves them verbatim via read_bytes; no regenerate-on-serve). When the shared
certificate template in scripts/vpm_visual_grammar.py changes (v2 -> v3 design
certificate), the already-emitted artifacts keep their OLD HTML until they are
re-rendered. This script re-renders each registry row in place.

Determinism / identity discipline
---------------------------------
- The artifact's IDENTITY is its commitment_hex (registry unique key + the
  /operator/vpm-artifact/{commit} URL key). It is NOT touched here, so every
  URL + filter stays stable.
  * VPM-family (CDRR / GIC / HONESTY): commitment_hex = input_commitment (over
    inputs) — unchanged by a template swap anyway.
  * MLGA: commitment_hex historically == output_hash; left stable so URLs hold.
- Only compiler_output_hash_hex is updated, to the SHA-256 of the new served
  bytes, so VpmProofView's in-browser HASH-OK check (served-sha256 ==
  compiler_output_hash_hex) passes.
- Files are written with write_bytes (NOT write_text) so Windows does not
  rewrite '\n' -> '\r\n' and desync the byte hash.

Inputs are reconstructed from each row's stored preimage_json exactly the way
the originating tracker built them (see bridge/vapi_bridge/*_tracker.py), so the
re-rendered content is faithful to the artifact's committed state.

Usage:
  python scripts/regenerate_vpm_artifacts.py            # dry-run (no writes)
  python scripts/regenerate_vpm_artifacts.py --apply    # write files + DB
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import traceback
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
_BRIDGE_DIR = os.path.join(_ROOT, "bridge")
for _p in (_HERE, _BRIDGE_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Renderers (module-level deterministic fns)
import vpm_compile_cdrr_dag as _cdrr            # noqa: E402
import vpm_compile_gic_ledger_beta as _gic      # noqa: E402
import vpm_compile_honesty_board as _hb         # noqa: E402
import mlga_compile_session_artifact as _mlga   # noqa: E402

# Tracker integrity-label builders (single source of truth for the label dict)
from vapi_bridge.cdrr_dag_tracker import _build_integrity_label as _cdrr_label   # noqa: E402
from vapi_bridge.gic_ledger_beta_tracker import _build_integrity_label as _gic_label  # noqa: E402
from vapi_bridge.honesty_board_tracker import _build_integrity_label as _hb_label      # noqa: E402

from vsd_ui_compiler import (  # noqa: E402
    _enforce_vpm_compiler_discipline,
    _verify_integrity_label_in_dom,
)
from vpm_visual_grammar import VISUAL_STATE_SIGNATURES  # noqa: E402

# Canonical GIC genesis ts_ns for grind_phase235_v1 (display-only field; not in
# the GIC preimage). Matches scripts/vpm_compile_gic_ledger_beta.py CLI default
# + CLAUDE.md Phase 235-A genesis. Used only to render the genesis_ts row.
_GRIND_PHASE235_GENESIS_TS_NS = 1777142267690827300


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _reconstruct(vpm_id: str, pre: dict, preimage_str: str, col_state: str):
    """Return (renderer_fn, inputs_dict) for a registry row."""
    if vpm_id == "MLGA-SESSION-v1":
        # preimage IS the compiler inputs dict.
        return _mlga._render_html, dict(pre)

    if vpm_id == "GIC-LEDGER-BETA-v1":
        il = _gic_label(
            on_chain_anchor=bool(pre.get("on_chain_anchor")),
            chain_length=int(pre.get("gic_chain_length", 0)),
        )
        inputs = {
            "gic_chain_head_hex":      str(pre.get("gic_chain_head_hex", "")),
            "gic_chain_length":        int(pre.get("gic_chain_length", 0)),
            "gic_genesis_hash_hex":    str(pre.get("gic_genesis_hash", "")),
            "gic_genesis_ts_ns":       _GRIND_PHASE235_GENESIS_TS_NS,
            "on_chain_anchor_tx_hash": str(pre.get("anchor_tx_hash", "")),
            "on_chain_anchor_block":   int(pre.get("anchor_block", 0)),
            "grind_session_id":        str(pre.get("grind_session_id", "")),
            "visual_state":            col_state,
            "integrity_label":         il,
            "zkba_manifest_hash_hex":  str(pre.get("gic_chain_head_hex", "")),
            "ts_ns":                   int(pre.get("ts_ns", 0)),
        }
        return _gic._render_gic_ledger_beta_html, inputs

    if vpm_id == "HONESTY-BOARD-v1":
        snap = dict(pre.get("snapshot", {}))
        il = _hb_label(snapshot=snap)
        digest = hashlib.sha256(_canon(snap).encode("utf-8")).hexdigest()
        inputs = {
            **{k: snap.get(k) for k in (
                "fleet_phase_aligned", "fleet_phase_target",
                "zkba_class_coverage_count", "chain_submission_paused",
                "cedar_v2_bundles_anchored", "pv_ci_invariants_count",
                "wallet_balance_iotx", "last_anchor_tx_hash", "last_anchor_block",
            )},
            "visual_state":           col_state,
            "integrity_label":        il,
            "zkba_manifest_hash_hex": digest,
            "ts_ns":                  int(pre.get("ts_ns", 0)),
        }
        return _hb._render_honesty_board_html, inputs

    # CDRR-DAG-v1 (default): preimage is the FSCA snapshot {vpm_id,
    # trigger_row_id, rule_name, severity, coherence_id, ts_ns}.
    il = _cdrr_label(
        severity=str(pre.get("severity", "HIGH")),
        rule_name=str(pre.get("rule_name", "UNKNOWN")),
        coherence_id=str(pre.get("coherence_id", "")),
    )
    digest = hashlib.sha256(preimage_str.encode("utf-8")).hexdigest()
    inputs = {
        "visual_state":           col_state,
        "integrity_label":        il,
        "zkba_manifest_hash_hex": digest,
        "ts_ns":                  int(pre.get("ts_ns", 0)),
    }
    return _cdrr._render_cdrr_dag_html, inputs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write files + update DB (default: dry-run)")
    ap.add_argument("--db", default=os.path.expanduser("~/.vapi/bridge.db"))
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, vpm_id, visual_state, manifest_uri, commitment_hex, "
        "       compiler_output_hash_hex, preimage_json "
        "FROM vpm_artifact_log ORDER BY id"
    ).fetchall()

    updates = []          # (id, new_hash)
    writes = []           # (Path, bytes)
    errors = []
    by_class = {}
    for r in rows:
        try:
            pre = json.loads(r["preimage_json"])
            fn, inputs = _reconstruct(
                r["vpm_id"], pre, r["preimage_json"], r["visual_state"]
            )
            html = fn(inputs)
            # Discipline + grammar gate per artifact (fail before any write).
            _enforce_vpm_compiler_discipline(html)
            _verify_integrity_label_in_dom(html)
            st = inputs.get("visual_state", r["visual_state"])
            miss = [s for s in VISUAL_STATE_SIGNATURES.get(st, ()) if s not in html]
            if miss:
                raise AssertionError(f"missing grammar sigs: {miss}")
            if 'role="status"' not in html or '<meta name="vpm-visual-state"' not in html:
                raise AssertionError("missing meta/aria marker")
            data = html.encode("utf-8")
            new_hash = hashlib.sha256(data).hexdigest()
            p = Path(r["manifest_uri"])
            if not p.is_absolute():
                p = Path(_ROOT) / p
            writes.append((p, data))
            updates.append((r["id"], new_hash))
            by_class[r["vpm_id"]] = by_class.get(r["vpm_id"], 0) + 1
        except Exception as e:  # noqa: BLE001
            errors.append((r["id"], r["vpm_id"], type(e).__name__, str(e)[:200]))
            traceback.print_exc()

    print(f"rows={len(rows)} ok={len(updates)} errors={len(errors)}")
    print("by_class:", by_class)
    for e in errors[:30]:
        print("ERR", e)
    if errors:
        print("ABORT — errors present; no writes performed.")
        con.close()
        return 1

    if not args.apply:
        print("DRY-RUN — re-add --apply to write files + update DB.")
        con.close()
        return 0

    # Write files (write_bytes preserves '\n'; avoids Windows CRLF desync).
    missing_dir = 0
    for p, data in writes:
        if not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            missing_dir += 1
        p.write_bytes(data)
    # Update compiler_output_hash_hex only (commitment_hex left stable).
    con.executemany(
        "UPDATE vpm_artifact_log SET compiler_output_hash_hex=? WHERE id=?",
        [(h, i) for (i, h) in updates],
    )
    con.commit()
    print(f"APPLIED — wrote {len(writes)} files ({missing_dir} new dirs), "
          f"updated {len(updates)} rows.")

    # Verify: served bytes sha256 == updated compiler_output_hash_hex.
    bad = 0
    want = dict(updates)
    vrows = con.execute(
        "SELECT id, manifest_uri, compiler_output_hash_hex FROM vpm_artifact_log"
    ).fetchall()
    for r in vrows:
        if r["id"] not in want:
            continue
        p = Path(r["manifest_uri"])
        if not p.is_absolute():
            p = Path(_ROOT) / p
        try:
            disk = hashlib.sha256(p.read_bytes()).hexdigest()
        except Exception:
            bad += 1
            continue
        if disk != r["compiler_output_hash_hex"]:
            bad += 1
    print(f"VERIFY — hash mismatches: {bad} (expect 0)")
    con.close()
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
