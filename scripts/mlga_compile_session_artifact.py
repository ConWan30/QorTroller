"""Phase O5-MLGA Stage 4 — VPM artifact compiler for MLGA session dataproofs.

Sibling of `scripts/zkba_compile_gic_ledger.py`. Each closed MLGA session
(per `bridge/vapi_bridge/mlga_session_tracker.py`) becomes a tamper-evident
VPM artifact rendered through the Phase O4 FROZEN compile_vpm_artifact()
discipline:
  - Deterministic HTML (no external URLs / no network / no randomness /
    no wall-clock)
  - FROZEN 9-field Integrity Label DOM
  - 6-state Anti-Hype Visual Grammar
  - 3-layer enforcement (compile-time + bridge audit + browser-side
    VpmGrammarVerifier)

VAPI-EXCLUSIVITY synthesis (Stage 4 closure):
  MLGA dataproof commitment (32-byte FROZEN SHA-256 over 89-byte preimage)
  → cryptographic anchor on the VPM artifact's zkba_manifest_hash_hex field
  → deterministic HTML projection (this compiler)
  → vpm_artifact_log table row (Phase O4 1200 migration)
  → vpm-list endpoint surface
  → VpmRegistryView frontend tab (existing 6th top-level tab)
  → iframe-rendered via Phase O4 VpmIframe with VpmGrammarVerifier
    Layer-3 enforcement.

Each gameplay session becomes an independently-verifiable published
artifact. No other DePIN protocol has this stack.

Call pattern (from MLGASessionTracker.close_session):
    from mlga_compile_session_artifact import build_mlga_session_artifact
    manifest = build_mlga_session_artifact(
        session_id=...,
        session_start_ts_ns=...,
        ...,
        dataproof_hex=dataproof.hex(),
        output_dir=Path("frontend/src/artifacts/mlga"),
    )

Returns: a dict matching VPMArtifactManifest fields (suitable for
insert_vpm_artifact()) + a `preimage_json` field containing the
canonical-JSON-sorted inputs for downstream audit reproduction.

Track 1 invariants enforced:
  - No `chain.py` import (no on-chain calls)
  - No `cedar_shadow_runtime` import
  - No operator-agent draft emission
  - Pure local artifact: writes HTML + manifest sidecar to output_dir.
    The MLGASessionTracker writes the row to vpm_artifact_log; this
    compiler only produces the manifest dict + the HTML on disk.

Author: VAPI Architect — Phase O5-MLGA Stage 4
Date: 2026-05-15
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

# sys.path setup — mirrors scripts/zkba_compile_gic_ledger.py pattern.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BRIDGE_DIR = os.path.normpath(os.path.join(_HERE, "..", "bridge"))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

try:
    from vapi_bridge.zkba_artifact import (  # noqa: E402
        ZKBAClass,
        ProofWeightClass,
    )
except ImportError:
    # When invoked from within the running bridge process
    # (python -m bridge.vapi_bridge.main), the project root is on
    # sys.path so the package surfaces as bridge.vapi_bridge.* instead
    # of bare vapi_bridge.*. Both code paths reach the same module
    # object; the dual-import is a sys.path-layout adapter, not a
    # second source of truth.
    from bridge.vapi_bridge.zkba_artifact import (  # noqa: E402
        ZKBAClass,
        ProofWeightClass,
    )
from vsd_ui_compiler import (  # noqa: E402
    compile_vpm_artifact,
)
from vpm_visual_grammar import (  # noqa: E402
    cert_section,
    render_vpm_certificate,
)


# ---------------------------------------------------------------------------
# FROZEN schema literal — MLGA VPM artifact wrapper schema name.
# Pinned by INV-MLGA-VPM-SCHEMA-001 (Stream D PV-CI ceremony).
# Read by Mythos-Crypto via _KNOWN_CAPABILITY_TAGS pattern; appears in
# the vpm_artifact_log.wrapper_schema column.
# ---------------------------------------------------------------------------
MLGA_VPM_WRAPPER_SCHEMA: str = "vapi-mlga-session-artifact-v1"


def _truncate_hex(h: str, n: int = 16) -> str:
    """Render hex prefix for display (no semantic significance — display only)."""
    if not isinstance(h, str):
        return ""
    s = h[2:] if h.startswith("0x") else h
    return s[:n] + ("..." if len(s) > n else "")


def _determine_visual_state(
    *,
    n_poac_records: int,
    gic_advances_in_session: int,
    bt_observability: int,
) -> str:
    """Per Phase O4 Anti-Hype Visual Grammar 6-state FROZEN dispatch:

      - "live"       : session captured real data (records > 0 OR gic_advances > 0)
      - "unverified" : session opened but captured nothing (degraded close)
      - "demo" / "dry-run" / "emulated" / "frozen-disabled" / "revoked" :
                       reserved for other modes; NOT emitted by MLGA v1
                       compile-path (tracker enabled + opened session always
                       reaches this code via close).

    Bt_observability is informational; doesn't change visual_state for v1.
    """
    if n_poac_records > 0 or gic_advances_in_session > 0:
        return "live"
    return "unverified"


def _build_integrity_label(
    *,
    visual_state: str,
    n_poac_records: int,
    gic_advances_in_session: int,
    bt_observability: int,
) -> Dict[str, str]:
    """Populate the FROZEN 9-field Integrity Label per
    scripts/vsd_ui_compiler.py _VPM_INTEGRITY_LABEL_FIELDS.

    All 9 fields hardcoded for MLGA v1 except visual_state-derived
    revocation_status. Anti-Hype Visual Grammar requires each field
    surface in the DOM with `data-vpm-field=<name>` marker — done in
    _render_html below.
    """
    return {
        "proof_type":              "mlga_session",
        "capture_mode":            "live",  # FROZEN _VPM_CAPTURE_MODES value
        "raw_biometrics_exposed":  "no",
        "consent_active":          "n/a",
        "zk_verified":             "no",
        "on_chain_anchor":         "no",
        "proof_weight":            "CHAIN_ONLY",
        "revocation_status":       "active" if visual_state == "live" else "unverified",
        "limitations": (
            "MLGA v1 ambient capture; supplements lab measurements; "
            "does not replace controlled-environment baseline"
        ),
    }


def _render_html(inputs: dict) -> str:
    """Deterministic HTML renderer.

    Inputs dict shape (all keys required; all values deterministic):
      - session_id            : str
      - session_start_ts_ns   : int (uint64)
      - session_end_ts_ns     : int (uint64)
      - session_duration_s    : float (display only)
      - n_poac_records        : int
      - n_trigger_pulls_r2    : int
      - n_trigger_pulls_l2    : int
      - apop_state_counts     : dict[str, int] (deterministic; sorted at render)
      - bt_observability      : int (0/1/2)
      - gic_advances_in_session : int
      - dataproof_hex         : str (64 lowercase hex)
      - visual_state          : str (1-of-6 FROZEN states)
      - integrity_label       : dict (9 FROZEN fields)
      - ts_ns                 : int (uint64 — required by compile_vpm_artifact contract)

    Compiler-discipline constraints (enforced by _enforce_vpm_compiler_discipline
    post-render): no https?://, no fetch, no Math.random, no Date.now, no
    @font-face, no <link rel>. Mandatory 9-field Integrity Label DOM with
    `vpm-integrity-label` class + 9 `data-vpm-field=` markers.
    """
    sid                 = inputs["session_id"]
    start_ts            = int(inputs["session_start_ts_ns"])
    end_ts              = int(inputs["session_end_ts_ns"])
    duration_s          = float(inputs["session_duration_s"])
    n_records           = int(inputs["n_poac_records"])
    n_r2                = int(inputs["n_trigger_pulls_r2"])
    n_l2                = int(inputs["n_trigger_pulls_l2"])
    apop_counts         = inputs["apop_state_counts"]
    bt_obs              = int(inputs["bt_observability"])
    gic_advances        = int(inputs["gic_advances_in_session"])
    dataproof_hex       = str(inputs["dataproof_hex"])
    visual_state        = inputs["visual_state"]

    import html as _html  # local alias; module top has no html import

    bt_label = {0: "Not observed", 1: "Observed",
                2: "Held↔Placed identified"}.get(bt_obs, "Unknown")
    if duration_s >= 60:
        dur_disp = f"{int(duration_s // 60)} m {int(duration_s % 60)} s"
    else:
        dur_disp = f"{duration_s:.2f} s"

    trigger_v = (
        '<div class="row"><span class="lbl">R2 · special-cancel</span>'
        f'<span class="val amber">{n_r2:,}</span></div>'
        '<div class="row"><span class="lbl">L2 · guard-cancel</span>'
        f'<span class="val amber">{n_l2:,}</span></div>'
    )

    _apop_cls = {"NOMINAL": "chain", "DEGRADED": "amber", "CONTESTED": "err"}
    apop_parts = []
    for st in sorted(apop_counts.keys()):
        cnt = int(apop_counts[st])
        cls = _apop_cls.get(str(st).upper(), "dim")
        apop_parts.append(
            f'<div class="row"><span class="lbl">{_html.escape(str(st))}</span>'
            f'<span class="val {cls}">{cnt:,}</span></div>'
        )
    apop_v = "".join(apop_parts) if apop_parts else "no APOP samples in session"
    apop_cls = "mono" if apop_parts else "dim mono"

    content = cert_section(
        "Session · Aggregates",
        f"{n_records:,} records · APOP-bounded",
        [
            ("session_id", "amber mono", f"<code>{_html.escape(str(sid))}</code>"),
            ("session_window", "dim mono",
             '<div class="row"><span class="lbl">start_ts_ns</span>'
             f'<span class="val">{start_ts}</span></div>'
             '<div class="row"><span class="lbl">end_ts_ns</span>'
             f'<span class="val">{end_ts}</span></div>'),
            ("session_duration", "amber mono", _html.escape(dur_disp)),
            ("n_poac_records", "chain mono", f"{n_records:,} · all body[:164]-hashed"),
            ("trigger_pulls", "mono", trigger_v),
            ("gic_advances", "chain mono", f"{gic_advances} · genesis → milestone"),
            ("bt_observability", "dim mono",
             f"{_html.escape(bt_label)} · 0x{bt_obs:02x}"),
            ("apop_state_counts", apop_cls, apop_v),
        ],
    )

    return render_vpm_certificate(
        vpm_class="MLGA-SESSION-v1",
        title_text="MLGA-SESSION-v1",
        subtitle="Tournament-grade gameplay session · operator-verifiable",
        visual_state=visual_state,
        commitment_hex=dataproof_hex,  # MLGA dataproof IS the cryptographic commitment
        content_html=content,
        integrity_label=inputs["integrity_label"],
        footer_fields=[
            ("schema", "mlga-session-v1"),
            ("vpm_id", "MLGA-SESSION-v1"),
            ("dataproof", dataproof_hex[:16] + "…"),
            ("ts_ns", str(int(inputs["ts_ns"]))),
        ],
    )


def build_mlga_session_artifact(
    *,
    session_id: str,
    session_start_ts_ns: int,
    session_end_ts_ns: int,
    n_poac_records: int,
    n_trigger_pulls_r2: int,
    n_trigger_pulls_l2: int,
    apop_state_counts: Dict[str, int],
    bt_observability: int,
    gic_advances_in_session: int,
    dataproof_hex: str,
    output_dir: Path,
) -> Dict[str, Any]:
    """Public entry — compile one MLGA session artifact.

    Returns a dict matching VPMArtifactManifest fields:
      commitment_hex (== output_hash_hex; the artifact's cryptographic ID)
      vpm_id, visual_state, capture_mode, integrity_label_hash_hex,
      wrapper_schema, zkba_manifest_hash_hex, manifest_uri, output_hash_hex,
      input_commitment_hex, ts_ns

    Plus:
      preimage_json: canonical-JSON of inputs (for downstream audit).

    Raises:
      ValueError / TypeError on invalid input.
      VPMComplianceError if the rendered HTML violates compiler discipline.
    """
    # ---- Input validation ----
    if not isinstance(dataproof_hex, str) or len(dataproof_hex) != 64:
        raise ValueError(
            f"dataproof_hex must be 64-char hex (32 bytes); got len="
            f"{len(dataproof_hex) if isinstance(dataproof_hex, str) else type(dataproof_hex).__name__}"
        )
    try:
        int(dataproof_hex, 16)
    except ValueError:
        raise ValueError(f"dataproof_hex not valid hex: {dataproof_hex!r}")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError(f"session_id must be non-empty str; got {session_id!r}")
    for name, val in (
        ("session_start_ts_ns", session_start_ts_ns),
        ("session_end_ts_ns", session_end_ts_ns),
        ("n_poac_records", n_poac_records),
        ("n_trigger_pulls_r2", n_trigger_pulls_r2),
        ("n_trigger_pulls_l2", n_trigger_pulls_l2),
        ("bt_observability", bt_observability),
        ("gic_advances_in_session", gic_advances_in_session),
    ):
        if not isinstance(val, int) or val < 0:
            raise ValueError(f"{name} must be non-negative int; got {val!r}")
    if not isinstance(apop_state_counts, dict):
        raise TypeError(
            f"apop_state_counts must be dict; got {type(apop_state_counts).__name__}"
        )

    # ---- Determine visual state + integrity label ----
    visual_state = _determine_visual_state(
        n_poac_records=n_poac_records,
        gic_advances_in_session=gic_advances_in_session,
        bt_observability=bt_observability,
    )
    integrity_label = _build_integrity_label(
        visual_state=visual_state,
        n_poac_records=n_poac_records,
        gic_advances_in_session=gic_advances_in_session,
        bt_observability=bt_observability,
    )

    # ---- Build inputs dict (compiler requires 'ts_ns' key) ----
    duration_s = max(0.0, (session_end_ts_ns - session_start_ts_ns) / 1e9)
    inputs = {
        "session_id":              session_id,
        "session_start_ts_ns":     int(session_start_ts_ns),
        "session_end_ts_ns":       int(session_end_ts_ns),
        "session_duration_s":      round(duration_s, 2),
        "n_poac_records":          int(n_poac_records),
        "n_trigger_pulls_r2":      int(n_trigger_pulls_r2),
        "n_trigger_pulls_l2":      int(n_trigger_pulls_l2),
        "apop_state_counts":       dict(apop_state_counts),
        "bt_observability":        int(bt_observability),
        "gic_advances_in_session": int(gic_advances_in_session),
        "dataproof_hex":           dataproof_hex.lower(),
        "visual_state":            visual_state,
        "integrity_label":         integrity_label,
        "ts_ns":                   int(session_end_ts_ns),  # compiler requires uint64
    }

    # ---- Call FROZEN compile_vpm_artifact ----
    output_dir_path = Path(output_dir)
    manifest_obj = compile_vpm_artifact(
        vpm_id="MLGA-SESSION-v1",
        zkba_class=ZKBAClass.GIC,                  # =2; MLGA sessions track GIC chain advancement
        proof_weight=ProofWeightClass.CHAIN_ONLY,  # =1; matches GIC-LEDGER-BETA precedent
        visual_state=visual_state,
        capture_mode="live",                       # FROZEN _VPM_CAPTURE_MODES value
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=dataproof_hex.lower(),  # MLGA dataproof IS the manifest hash
        inputs=inputs,
        output_dir=output_dir_path,
        html_renderer=_render_html,
    )

    # ---- Serialize manifest to dict shape suitable for insert_vpm_artifact ----
    # Override wrapper_schema to the MLGA-specific value (the underlying
    # compile_vpm_artifact returns the generic Phase O4 wrapper schema; MLGA
    # uses a more specific identifier for downstream filter / audit).
    manifest_dict = asdict(manifest_obj)
    manifest_dict["wrapper_schema"] = MLGA_VPM_WRAPPER_SCHEMA
    manifest_dict["commitment_hex"] = manifest_obj.output_hash_hex
    manifest_dict["manifest_uri"] = manifest_obj.output_path
    # Canonical-JSON-sorted preimage for downstream audit reproduction.
    manifest_dict["preimage_json"] = json.dumps(
        inputs,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return manifest_dict


# ---------------------------------------------------------------------------
# CLI entry point — operator can manually compile a session artifact for
# testing / debugging without running the bridge.
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile a single MLGA session VPM artifact."
    )
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--start-ts-ns", type=int, required=True)
    parser.add_argument("--end-ts-ns", type=int, required=True)
    parser.add_argument("--n-poac", type=int, default=0)
    parser.add_argument("--n-r2", type=int, default=0)
    parser.add_argument("--n-l2", type=int, default=0)
    parser.add_argument("--apop-counts-json", default="{}",
        help="JSON object of APOP state name → count")
    parser.add_argument("--bt-obs", type=int, default=0,
        choices=[0, 1, 2])
    parser.add_argument("--gic-advances", type=int, default=0)
    parser.add_argument("--dataproof-hex", required=True)
    parser.add_argument("--output-dir",
        default="frontend/src/artifacts/mlga")
    args = parser.parse_args(argv)

    try:
        apop_counts = json.loads(args.apop_counts_json)
    except Exception as exc:
        print(f"Invalid --apop-counts-json: {exc}")
        return 2

    try:
        manifest = build_mlga_session_artifact(
            session_id=args.session_id,
            session_start_ts_ns=args.start_ts_ns,
            session_end_ts_ns=args.end_ts_ns,
            n_poac_records=args.n_poac,
            n_trigger_pulls_r2=args.n_r2,
            n_trigger_pulls_l2=args.n_l2,
            apop_state_counts=apop_counts,
            bt_observability=args.bt_obs,
            gic_advances_in_session=args.gic_advances,
            dataproof_hex=args.dataproof_hex,
            output_dir=Path(args.output_dir),
        )
    except Exception as exc:
        print(f"Compilation failed: {type(exc).__name__}: {exc}")
        return 1

    print(json.dumps(manifest, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
