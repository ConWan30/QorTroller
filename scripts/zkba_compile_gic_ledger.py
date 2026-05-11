"""Phase O3-ZKBA-TRACK1 Stream Z4 — GIC Continuity Ledger artifact builder.

First artifact target per VBDIP-0002 §10.1 (Artifact Alpha).  Operator-facing,
privacy-light visualization of the Grind Integrity Chain.  Composes:

  - GIC chain head hash (Phase 235-A primitive output) as the single 32-byte
    component of the ZKBA commitment (CHAIN_ONLY proof weight; no fresh
    biometric capture; chain state is on-chain anchored at GIC_100 head
    0x0e9d453d... per CLAUDE.md current state)
  - chain_length, ts_ns, and a deterministic per-link summary in the input
    dict supplied to the compiler — these affect file naming and HTML
    rendering but NOT the underlying ZKBA primitive commitment

Track 1 invariants enforced:
  - No `chain.py` import (no on-chain calls)
  - No `cedar_shadow_runtime` import (no Cedar evaluation)
  - No operator-agent draft emission
  - Pure local artifact: reads `Store` GIC helpers, writes HTML + manifest,
    inserts row into `zkba_artifact_log`

Run via CLI:
    python scripts/zkba_compile_gic_ledger.py --db <path> --session <id>

Or via Python:
    from scripts.zkba_compile_gic_ledger import build_gic_ledger_artifact
    from bridge.vapi_bridge.store import Store
    store = Store(db_path)
    manifest = build_gic_ledger_artifact(
        store=store,
        grind_session_id="grind_phase235_v1",
        output_dir=Path("frontend/src/artifacts/gic_continuity_ledger"),
        ts_ns=1778000000000000000,
    )

Author: VAPI Architect (bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
Date: 2026-05-10
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

# Add bridge/ + scripts/ to sys.path so imports resolve in both Python and
# CLI invocations.
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
from vsd_ui_compiler import (  # noqa: E402
    ZKBAManifest,
    compile_artifact,
)


# ---------------------------------------------------------------------------
# Deterministic HTML renderer for the GIC Continuity Ledger
# ---------------------------------------------------------------------------

def _render_gic_ledger_html(inputs: dict) -> str:
    """Deterministic HTML rendering of a GIC continuity ledger.

    Inputs dict shape (all keys required; all values deterministic):
      - "grind_session_id":     str
      - "chain_length":         int (0..100+)
      - "chain_head_hex":       str (64 lowercase hex)
      - "genesis_hex":          str (64 lowercase hex; empty if no genesis)
      - "zkba_commitment_hex":  str (64 lowercase hex)
      - "ts_ns":                int (uint64 — must come from caller, not wall-clock)
      - "links_summary":        list[dict] each with {"index", "host_state",
                                "verdict", "ch_short"}  (per-link projection;
                                deterministic order = chain index ASC)
    """
    # All values come from inputs; the renderer does NOT call time.time(),
    # datetime.now(), random, or any network resource.
    sid = inputs["grind_session_id"]
    chain_length = int(inputs["chain_length"])
    head_hex = inputs["chain_head_hex"]
    genesis_hex = inputs["genesis_hex"]
    zkba_hex = inputs["zkba_commitment_hex"]
    ts_ns = int(inputs["ts_ns"])
    links = inputs["links_summary"]

    # Pre-render the per-link table rows (sorted by index ascending)
    rows_html = ""
    for link in links:
        rows_html += (
            "    <tr>"
            f"<td>{int(link['index']):03d}</td>"
            f"<td>{link['host_state']}</td>"
            f"<td>{link['verdict']}</td>"
            f"<td><code>{link['ch_short']}</code></td>"
            "</tr>\n"
        )

    # CSS is inline + minimal; no external font / image / network resource
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>GIC Continuity Ledger - {head_hex[:16]}</title>\n"
        "  <style>\n"
        "    body { font-family: 'Courier New', monospace; "
        "background: #020408; color: #cfe8ff; margin: 0; padding: 1.5em; }\n"
        "    h1 { color: #5a8fb8; border-bottom: 1px solid #1a2a40; "
        "padding-bottom: 0.3em; }\n"
        "    .meta { color: #93a5b8; font-size: 0.9em; line-height: 1.6; }\n"
        "    code { color: #d4f0ff; background: #0a0e14; padding: 1px 4px; "
        "border-radius: 2px; }\n"
        "    table { width: 100%; border-collapse: collapse; "
        "margin-top: 1.5em; font-size: 0.85em; }\n"
        "    th, td { text-align: left; padding: 4px 8px; "
        "border-bottom: 1px solid #1a2a40; }\n"
        "    th { color: #5a8fb8; }\n"
        "    .footer { margin-top: 2em; color: #607a93; font-size: 0.8em; "
        "border-top: 1px solid #1a2a40; padding-top: 0.5em; }\n"
        "    .weight { background: #1a2a40; color: #93a5b8; padding: 2px 8px; "
        "border-radius: 4px; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>GIC Continuity Ledger</h1>\n"
        "  <div class=\"meta\">\n"
        f"    <div>Session: <code>{sid}</code></div>\n"
        f"    <div>Chain length: <code>{chain_length}</code></div>\n"
        f"    <div>Genesis: <code>{genesis_hex or '(none)'}</code></div>\n"
        f"    <div>Head: <code>{head_hex}</code></div>\n"
        f"    <div>ZKBA commitment: <code>{zkba_hex}</code></div>\n"
        f"    <div>ts_ns: <code>{ts_ns}</code></div>\n"
        "    <div>Proof weight: <span class=\"weight\">CHAIN_ONLY</span> "
        "(no fresh biometric capture; chain-anchored state only)</div>\n"
        "  </div>\n"
        "  <table>\n"
        "    <thead><tr><th>Idx</th><th>Host State</th><th>Verdict</th>"
        "<th>Commitment (head 12)</th></tr></thead>\n"
        "    <tbody>\n"
        f"{rows_html}"
        "    </tbody>\n"
        "  </table>\n"
        "  <div class=\"footer\">\n"
        "    Deterministic projection compiled by vsd_ui_compiler v0.1.0. "
        "Manifest schema vapi-zkba-manifest-v1. "
        "Phase O3-ZKBA-TRACK1 Stream Z4 (Artifact Alpha per VBDIP-0002 §10.1). "
        "No CDN; no network; no wall-clock; self-contained.\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def build_gic_ledger_artifact(
    *,
    store,
    grind_session_id: str,
    output_dir: Path,
    ts_ns: int,
    chain_head_hex_override: Optional[str] = None,
    links_summary_override: Optional[list] = None,
) -> ZKBAManifest:
    """Build a GIC Continuity Ledger ZKBA artifact deterministically.

    Reads GIC state from `store` (or accepts overrides for testability),
    composes the ZKBA commitment via compute_zkba_commitment() with a single
    GIC-head component hash, calls compile_artifact() to emit HTML +
    manifest, and inserts a row into `zkba_artifact_log`.

    Args:
        store:                   bridge.vapi_bridge.store.Store instance.
        grind_session_id:        Identifier of the grind run to project.
        output_dir:              Directory under which to write artifact + manifest.
        ts_ns:                   Caller-supplied uint64 timestamp (NO wall-clock).
        chain_head_hex_override: For testing — overrides store-read head.
        links_summary_override:  For testing — overrides store-read links.

    Returns:
        ZKBAManifest describing the emitted artifact.
    """
    # Read GIC state from store (or accept overrides)
    if chain_head_hex_override is not None:
        chain_head_hex = chain_head_hex_override
        chain_length = (
            len(links_summary_override) if links_summary_override is not None else 0
        )
        genesis_hex = ""
    else:
        status = store.get_grind_chain_status(grind_session_id)
        chain_head_hex = (status.get("latest_gic_hash") or "").lower()
        chain_length = int(status.get("chain_length") or 0)
        genesis_hex = (status.get("genesis_gic_hash") or status.get("genesis_hash") or "").lower()

    if not chain_head_hex or len(chain_head_hex) != 64:
        # Empty / invalid head means no chain to project; emit a DEMO artifact
        # rather than fail.  Operator can re-run after grind progresses.
        chain_head_hex = "0" * 64
        chain_length = 0

    if links_summary_override is not None:
        links_summary = list(links_summary_override)
    else:
        # Read up to 100 ruling rows for the chain; project a compact summary
        raw_rows = store.get_ruling_rows_for_chain(grind_session_id)
        links_summary = []
        for idx, row in enumerate(raw_rows[:100]):
            ch_full = (row.get("commitment_hash_hex") or "")
            links_summary.append({
                "index": idx,
                "host_state": (row.get("pcc_host_state") or "UNKNOWN"),
                "verdict": (row.get("fallback_verdict") or "UNKNOWN"),
                "ch_short": ch_full[:12] if ch_full else "(none)",
            })

    # Compute the ZKBA commitment: single 32B component = GIC head
    head_bytes = bytes.fromhex(chain_head_hex)
    zkba_commitment = compute_zkba_commitment(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(head_bytes,),
        ts_ns=ts_ns,
    )
    zkba_hex = zkba_commitment.hex()

    # Compile the artifact
    inputs = {
        "grind_session_id":    str(grind_session_id),
        "chain_length":        int(chain_length),
        "chain_head_hex":      chain_head_hex,
        "genesis_hex":         genesis_hex,
        "zkba_commitment_hex": zkba_hex,
        "ts_ns":               int(ts_ns),
        "links_summary":       links_summary,
    }

    manifest = compile_artifact(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_gic_ledger_html,
    )

    # Insert row into zkba_artifact_log (Track 1: anchor_tx_hash stays NULL)
    preimage_json = json.dumps({
        "zkba_class": int(ZKBAClass.GIC),
        "proof_weight": int(ProofWeightClass.CHAIN_ONLY),
        "component_hashes_hex": [chain_head_hex],
        "ts_ns": int(ts_ns),
    }, sort_keys=True, separators=(",", ":"))

    store.insert_zkba_artifact(
        zkba_class=int(ZKBAClass.GIC),
        proof_weight=int(ProofWeightClass.CHAIN_ONLY),
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
        description="Build a GIC Continuity Ledger ZKBA artifact (Phase O3-ZKBA-TRACK1 Z4)."
    )
    parser.add_argument(
        "--db",
        default=os.path.normpath(os.path.join(_HERE, "..", "bridge", "vapi_store.db")),
        help="Path to bridge SQLite DB.",
    )
    parser.add_argument(
        "--session",
        required=True,
        help="Grind session ID to project (e.g., grind_phase235_v1).",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "gic_continuity_ledger",
        )),
        help="Output directory (default: frontend/src/artifacts/gic_continuity_ledger/).",
    )
    parser.add_argument(
        "--ts-ns",
        type=int,
        required=True,
        help="Caller-supplied uint64 timestamp (no wall-clock; provide explicitly).",
    )
    args = parser.parse_args()

    from vapi_bridge.store import Store  # noqa: E402
    store = Store(args.db)
    manifest = build_gic_ledger_artifact(
        store=store,
        grind_session_id=args.session,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"GIC Continuity Ledger compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  zkba_commitment_hex:   (from artifact metadata; see manifest)")
    print(f"  compiler_version:      {manifest.compiler_version}")
    print(f"  manifest path:         {manifest.output_path.rsplit('.', 1)[0]}.manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
