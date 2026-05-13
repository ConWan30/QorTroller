"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — AIT Separation Snapshot artifact builder.

Third ZKBA artifact target after the GIC Continuity Ledger Alpha (commit 3b3081d3)
and VHP Verification Card (commit 4f399282). Empirically proves Layer 7 holds for
a first non-CHAIN_ONLY proof weight class (CALIBRATION_PLUS_CONTEXT) — i.e. the
ZKBA pipeline composes correctly across multiple proof_weight values, not just
the single CHAIN_ONLY profile exercised by the first two artifacts.

Composition profile:
  - ZKBAClass.AIT                          (= 1 in the FROZEN-v1 enum)
  - ProofWeightClass.CALIBRATION_PLUS_CONTEXT  (matches the default per
                                                DEFAULT_PROOF_WEIGHT_BY_CLASS in
                                                scripts/zkba_manifest_validator.py)
  - Single 32-byte component hash composed from:
        SHA-256( ratio_milli_be(8) || n_sessions_be(8) ||
                 analysis_date_be(8) || pair_distances_root(32) )
    where pair_distances_root is the SHA-256 root over a sorted-key
    canonical-JSON encoding of the pair_distances dict (e.g.
    {"P1vP2":1.850,"P1vP3":1.846,"P2vP3":1.349}).

Owning agent: **Sentry** (canonical name "anchor_sentry"). AIT snapshots write
to the `zk_artifacts/` lane authorized by anchor_sentry_o2_suggest_v2.json
(Cedar v2 LIVE since commit ad0f7d11). Same lane as the VHP Verification
Card — Sentry handles all ZKBA artifact emission per the CFSS invariant.

Track 1 invariants enforced:
  - No on-chain submission (anchor_tx_hash stays NULL in zkba_artifact_log)
  - No fresh biometric capture (CALIBRATION_PLUS_CONTEXT — uses already-anchored
    calibration corpus state, not a live capture session)
  - Caller-supplied ts_ns (no wall-clock read)
  - Deterministic compile (same inputs → same output bytes)

Real input fixture (canonical AIT corpus per Phase 229 + Phase 231):
  separation_ratio   = 1.199          → ratio_milli = 1199000
  n_sessions         = 37             → P1=13 P2=10 P3=14
  all_pairs_above_1  = True
  pair_distances     = {"P1vP2":1.850, "P1vP3":1.846, "P2vP3":1.349}
  analysis_date      = 1745539200     (2026-04-20 UTC; Phase 231 corpus close)

Run via CLI (offline; uses provided inputs):
    python scripts/zkba_compile_ait_snapshot.py --ratio-milli 1199000 \\
        --n-sessions 37 --analysis-date 1745539200 \\
        --pair-distances '{"P1vP2":1.850,"P1vP3":1.846,"P2vP3":1.349}' \\
        --ts-ns 1778900000000000000

Or via Python:
    from scripts.zkba_compile_ait_snapshot import build_ait_snapshot_artifact

Pairs with G4 manifest validator + VPM wrapper at scripts/vsd_vpm_wrapper.py
for the end-to-end Layer 7 pipeline.

Author: VAPI Architect (post-VHP third-artifact ship 2026-05-12)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Mapping

_HERE = os.path.dirname(os.path.abspath(__file__))
_BRIDGE_DIR = os.path.normpath(os.path.join(_HERE, "..", "bridge"))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from vapi_bridge.zkba_artifact import (  # noqa: E402
    ZKBAClass,
    ProofWeightClass,
    compute_zkba_commitment,
)
from vsd_ui_compiler import ZKBAManifest, compile_artifact  # noqa: E402


# ---------------------------------------------------------------------------
# Deterministic component composition
# ---------------------------------------------------------------------------

def _canonical_pair_distances_bytes(pair_distances: Mapping[str, float]) -> bytes:
    """Sorted-key canonical-JSON bytes of the pair_distances dict.

    Discipline matches scripts/vsd_ui_compiler.canonical_json — sorted keys,
    no whitespace, UTF-8. Floats are serialized via Python's default repr;
    callers MUST supply rationals that round-trip cleanly (e.g. 1.850 ok;
    1.85 ambiguous).
    """
    if not isinstance(pair_distances, Mapping):
        raise ValueError("pair_distances must be a mapping")
    return json.dumps(
        dict(pair_distances),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _compose_ait_component(
    *,
    ratio_milli: int,
    n_sessions: int,
    analysis_date: int,
    pair_distances: Mapping[str, float],
) -> bytes:
    """Compose a single 32-byte ZKBA component from AIT separation state.

    Byte layout (FROZEN at v1; downstream verifiers reproduce this exact order):

        SHA-256(
            ratio_milli_be(8)         # 8 bytes (uint64 BE; ratio*1e6 rounded)
            || n_sessions_be(8)       # 8 bytes (uint64 BE)
            || analysis_date_be(8)    # 8 bytes (uint64 BE; unix ts)
            || pair_distances_root    # 32 bytes (SHA-256 of canonical JSON)
        )                             # = 32 bytes after SHA-256

    The ratio is encoded as a uint64 milliratio (ratio × 1e6 rounded) per the
    same convention as CORPUS-SNAPSHOT v1 (CLAUDE.md hard rule under PATTERN-016)
    — OS-deterministic byte encoding regardless of float64 representation.
    """
    if not isinstance(ratio_milli, int) or ratio_milli < 0 or ratio_milli > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"ratio_milli must be uint64; got {ratio_milli!r}")
    if not isinstance(n_sessions, int) or n_sessions < 0 or n_sessions > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"n_sessions must be uint64; got {n_sessions!r}")
    if not isinstance(analysis_date, int) or analysis_date < 0 or analysis_date > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"analysis_date must be uint64; got {analysis_date!r}")

    pair_bytes = _canonical_pair_distances_bytes(pair_distances)
    pair_root = hashlib.sha256(pair_bytes).digest()

    preimage = (
        ratio_milli.to_bytes(8, "big")
        + n_sessions.to_bytes(8, "big")
        + analysis_date.to_bytes(8, "big")
        + pair_root
    )
    return hashlib.sha256(preimage).digest()


# ---------------------------------------------------------------------------
# Deterministic HTML renderer
# ---------------------------------------------------------------------------

def _render_ait_snapshot_html(inputs: dict) -> str:
    """Deterministic HTML rendering of an AIT Separation Snapshot card.

    Inputs dict shape (all keys required; all values deterministic):
      - "ratio_milli":         int (uint64; ratio × 1e6 rounded)
      - "n_sessions":          int (uint64)
      - "analysis_date":       int (unix ts)
      - "all_pairs_above_1":   bool (advisory display field; not in commitment)
      - "pair_distances_json": str (canonical JSON of pair_distances dict)
      - "zkba_commitment_hex": str (64 lowercase hex)
      - "ts_ns":               int (uint64; caller-supplied, no wall-clock)
    """
    ratio_milli = int(inputs["ratio_milli"])
    n_sessions = int(inputs["n_sessions"])
    analysis_date = int(inputs["analysis_date"])
    all_pairs_above_1 = bool(inputs["all_pairs_above_1"])
    pair_distances_json = inputs["pair_distances_json"]
    zkba_hex = inputs["zkba_commitment_hex"]
    ts_ns = int(inputs["ts_ns"])

    ratio_display = f"{ratio_milli / 1_000_000:.6f}"
    gate_label = "ALL PAIRS > 1.0" if all_pairs_above_1 else "PAIRS BELOW 1.0"
    gate_color = "#5bd6a3" if all_pairs_above_1 else "#d65b78"

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>AIT Separation Snapshot - N={n_sessions} ratio={ratio_display}</title>\n"
        "  <style>\n"
        "    body { font-family: 'Courier New', monospace; "
        "background: #020408; color: #cfe8ff; margin: 0; padding: 1.5em; }\n"
        "    h1 { color: #5a8fb8; border-bottom: 1px solid #1a2a40; "
        "padding-bottom: 0.3em; }\n"
        "    .meta { color: #93a5b8; font-size: 0.9em; line-height: 1.6; }\n"
        "    code { color: #d4f0ff; background: #0a0e14; padding: 1px 4px; "
        "border-radius: 2px; }\n"
        "    .footer { margin-top: 2em; color: #607a93; font-size: 0.8em; "
        "border-top: 1px solid #1a2a40; padding-top: 0.5em; }\n"
        "    .weight { background: #1a2a40; color: #93a5b8; padding: 2px 8px; "
        "border-radius: 4px; }\n"
        f"    .gate-badge {{ background: {gate_color}; color: #020408; "
        "padding: 4px 12px; border-radius: 4px; font-weight: bold; }}\n"
        "    pre { background: #0a0e14; padding: 0.5em; border-radius: 4px; "
        "color: #d4f0ff; overflow-x: auto; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>AIT Separation Snapshot</h1>\n"
        "  <div class=\"meta\">\n"
        f"    <div>Separation ratio: <code>{ratio_display}</code> "
        f"(ratio_milli = {ratio_milli})</div>\n"
        f"    <div>Total sessions: <code>{n_sessions}</code></div>\n"
        f"    <div>Analysis date: <code>{analysis_date}</code> (unix ts)</div>\n"
        f"    <div>Gate status: <span class=\"gate-badge\">{gate_label}</span></div>\n"
        f"    <div>Pair distances (canonical JSON):</div>\n"
        f"    <pre>{pair_distances_json}</pre>\n"
        f"    <div>ZKBA commitment: <code>{zkba_hex}</code></div>\n"
        f"    <div>ts_ns: <code>{ts_ns}</code></div>\n"
        "    <div>Proof weight: <span class=\"weight\">CALIBRATION_PLUS_CONTEXT</span> "
        "(AIT separation derived from anchored calibration corpus)</div>\n"
        "  </div>\n"
        "  <div class=\"footer\">\n"
        "    Deterministic projection compiled by vsd_ui_compiler v0.1.0. "
        "Manifest schema vapi-zkba-manifest-v1. "
        "ZKBA class AIT (= 1 in PATTERN-017 FROZEN-v1 enum). "
        "Phase O3-ZKBA-TRACK1 Track 2 third-artifact ship — Sentry "
        "lane authority via Cedar v2 zk_artifacts/. "
        "No CDN; no network; no wall-clock; self-contained.\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def build_ait_snapshot_artifact(
    *,
    store,
    ratio_milli: int,
    n_sessions: int,
    analysis_date: int,
    pair_distances: Mapping[str, float],
    all_pairs_above_1: bool,
    output_dir: Path,
    ts_ns: int,
) -> ZKBAManifest:
    """Build an AIT Separation Snapshot ZKBA artifact deterministically.

    Composes the ZKBA commitment from AIT separation state, calls
    compile_artifact() to emit HTML + manifest, and inserts a row into
    zkba_artifact_log.

    Args:
        store:             bridge.vapi_bridge.store.Store instance.
        ratio_milli:       Separation ratio × 1e6 rounded (uint64).
        n_sessions:        Total AIT sessions in the corpus (uint64).
        analysis_date:     Unix timestamp of the analysis run (uint64).
        pair_distances:    {"P1vP2": float, "P1vP3": float, "P2vP3": float, ...}
                           Mapping of pair_key → Mahalanobis distance.
        all_pairs_above_1: bool advisory display flag (not in commitment).
        output_dir:        Directory under which to write artifact + manifest.
        ts_ns:             Caller-supplied uint64 timestamp (NO wall-clock).

    Returns:
        ZKBAManifest describing the emitted artifact.
    """
    # Compose component hash from AIT separation state
    component = _compose_ait_component(
        ratio_milli=ratio_milli,
        n_sessions=n_sessions,
        analysis_date=analysis_date,
        pair_distances=pair_distances,
    )

    # Compute the ZKBA commitment: single 32B component
    zkba_commitment = compute_zkba_commitment(
        zkba_class=ZKBAClass.AIT,
        proof_weight=ProofWeightClass.CALIBRATION_PLUS_CONTEXT,
        component_hashes=(component,),
        ts_ns=ts_ns,
    )
    zkba_hex = zkba_commitment.hex()

    # Canonical pair_distances JSON string (for HTML + preimage_json)
    pair_distances_json = _canonical_pair_distances_bytes(pair_distances).decode("utf-8")

    # Compile the artifact
    inputs = {
        "ratio_milli":          int(ratio_milli),
        "n_sessions":           int(n_sessions),
        "analysis_date":        int(analysis_date),
        "all_pairs_above_1":    bool(all_pairs_above_1),
        "pair_distances_json":  pair_distances_json,
        "zkba_commitment_hex":  zkba_hex,
        "ts_ns":                int(ts_ns),
    }

    manifest = compile_artifact(
        zkba_class=ZKBAClass.AIT,
        proof_weight=ProofWeightClass.CALIBRATION_PLUS_CONTEXT,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_ait_snapshot_html,
    )

    # Insert row into zkba_artifact_log (Track 1: anchor_tx_hash stays NULL)
    preimage_json = json.dumps({
        "zkba_class": int(ZKBAClass.AIT),
        "proof_weight": int(ProofWeightClass.CALIBRATION_PLUS_CONTEXT),
        "component_hashes_hex": [component.hex()],
        "ts_ns": int(ts_ns),
        "ait_ratio_milli": int(ratio_milli),
        "ait_n_sessions": int(n_sessions),
        "ait_analysis_date": int(analysis_date),
    }, sort_keys=True, separators=(",", ":"))

    store.insert_zkba_artifact(
        zkba_class=int(ZKBAClass.AIT),
        proof_weight=int(ProofWeightClass.CALIBRATION_PLUS_CONTEXT),
        commitment_hex=zkba_hex,
        preimage_json=preimage_json,
        ts_ns=int(ts_ns),
        manifest_uri=manifest.output_path.replace("\\", "/"),
        compiler_output_hash_hex=manifest.output_hash_hex,
    )

    return manifest


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an AIT Separation Snapshot ZKBA artifact (Phase O3-ZKBA-TRACK1 Track 2 third-artifact)."
    )
    parser.add_argument(
        "--db",
        default=os.path.normpath(os.path.join(_HERE, "..", "bridge", "vapi_store.db")),
        help="Path to bridge SQLite DB.",
    )
    parser.add_argument(
        "--ratio-milli",
        type=int,
        required=True,
        help="Separation ratio × 1e6 rounded (uint64; e.g. 1199000 for ratio 1.199).",
    )
    parser.add_argument(
        "--n-sessions",
        type=int,
        required=True,
        help="Total AIT sessions in the corpus (uint64).",
    )
    parser.add_argument(
        "--analysis-date",
        type=int,
        required=True,
        help="Unix timestamp of the analysis run.",
    )
    parser.add_argument(
        "--pair-distances",
        required=True,
        help="JSON mapping of pair_key → Mahalanobis distance, e.g. "
             "'{\"P1vP2\":1.850,\"P1vP3\":1.846,\"P2vP3\":1.349}'.",
    )
    parser.add_argument(
        "--all-pairs-above-1",
        action="store_true",
        help="Advisory display flag (NOT in the commitment; informational only).",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "ait_separation_snapshot",
        )),
        help="Output directory (default: frontend/src/artifacts/ait_separation_snapshot/).",
    )
    parser.add_argument(
        "--ts-ns",
        type=int,
        required=True,
        help="Caller-supplied uint64 timestamp (no wall-clock; provide explicitly).",
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    pair_distances = json.loads(args.pair_distances)
    if not isinstance(pair_distances, dict):
        raise ValueError("--pair-distances must decode to a JSON object")

    from vapi_bridge.store import Store  # noqa: E402
    store = Store(args.db)
    manifest = build_ait_snapshot_artifact(
        store=store,
        ratio_milli=args.ratio_milli,
        n_sessions=args.n_sessions,
        analysis_date=args.analysis_date,
        pair_distances=pair_distances,
        all_pairs_above_1=args.all_pairs_above_1,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"AIT Separation Snapshot compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  zkba_class:            AIT (= {int(ZKBAClass.AIT)})")
    print(f"  proof_weight:          CALIBRATION_PLUS_CONTEXT")
    print(f"  compiler_version:      {manifest.compiler_version}")
    print(f"  manifest path:         {manifest.output_path.rsplit('.', 1)[0]}.manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
