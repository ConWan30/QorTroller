"""Phase O4-VPM-INTEGRATION Stream A.1.a — HONESTY-BOARD-v1 VPM compiler.

First internal-projection VPM per Phase O4 plan §2.4 internal-first sequencing.
Produces a deterministic, self-contained HTML projection of VAPI's current
protocol-state at a caller-supplied timestamp — a single audit-friendly
surface summarizing what the protocol is publicly committing to right now.

Registered VPM ID per VBDIP-0002A §10 registry: `HONESTY-BOARD-v1`
Lifecycle status after this commit (per plan §2.3 table): `Test Fixture`
Owning agent lane: Sentry (writes to `zk_artifacts/` via existing v2 bundle
permit `tool:zk-artifact-anchor` — verified by CFSS triangle audit in
zkba_post_ceremony_audit.py Section 3).

Composition profile:
  Inputs (caller-supplied, deterministic):
    fleet_phase_aligned          bool (whether Sentry+Guardian+Curator phase-align)
    fleet_phase_target           str ("O1_SHADOW" | "O2_SUGGEST" | "O3_ACT")
    zkba_class_coverage_count    int 0..7 (how many ZKBAClass values shipped)
    chain_submission_paused      bool (current kill-switch state)
    cedar_v2_bundles_anchored    bool (Cedar v2 ceremony fired = True)
    pv_ci_invariants_count       int (current INV-* gate cardinality)
    wallet_balance_iotx          str (display-only — never used for decisions)
    last_anchor_tx_hash          str ("0x..." or "n/a")
    last_anchor_block            int (block number or 0)
  Wrapped ZKBA primitive reference:
    zkba_manifest_hash_hex       str (64-char hex; binds VPM to specific
                                 underlying ZKBA projection)

Visual state defaults to `live` but the compiler accepts any of the 6
FROZEN VPMVisualState values; the grammar test band uses this parameter
to drive T-VPM-GRAMMAR-1..6 across all six states.

Track 1 invariants enforced:
  - No on-chain submission (the artifact is filesystem-only HTML)
  - Caller-supplied state inputs (no live chain/store reads at compile time)
  - Caller-supplied ts_ns (no wall-clock read)
  - Deterministic compile (same inputs -> byte-identical output)
  - Static-guard discipline enforced by compile_vpm_artifact()

Author: VAPI Architect (Phase O4 Commit 4)
Date: 2026-05-13
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_BRIDGE_DIR = os.path.normpath(os.path.join(_HERE, "..", "bridge"))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402
from vsd_ui_compiler import (  # noqa: E402
    VPMArtifactManifest,
    compile_vpm_artifact,
)
from vpm_visual_grammar import (  # noqa: E402
    VISUAL_STATES,
    assemble_vpm_head,
    integrity_label_html,
    visual_state_aria_block,
    visual_state_overlay,
    vpm_body_class,
)


# Registered VPM ID per VBDIP-0002A §10
_VPM_ID = "HONESTY-BOARD-v1"


# ---------------------------------------------------------------------------
# Deterministic HTML renderer
# ---------------------------------------------------------------------------

def _render_honesty_board_html(inputs: dict) -> str:
    """Render the HONESTY-BOARD-v1 HTML body deterministically.

    Inputs dict shape (all keys required; all values deterministic):
      - "fleet_phase_aligned":        bool
      - "fleet_phase_target":         str
      - "zkba_class_coverage_count":  int 0..7
      - "chain_submission_paused":    bool
      - "cedar_v2_bundles_anchored":  bool
      - "pv_ci_invariants_count":     int
      - "wallet_balance_iotx":        str
      - "last_anchor_tx_hash":        str
      - "last_anchor_block":          int
      - "visual_state":               str (1-of-6 VISUAL_STATES)
      - "integrity_label":            dict (9 fields per INTEGRITY_LABEL_FIELDS)
      - "zkba_manifest_hash_hex":     str
      - "ts_ns":                      int
    """
    state = inputs["visual_state"]
    head = assemble_vpm_head(
        title=f"VAPI Honesty Board — {state.upper()}",
        visual_state=state,
    )

    overlay = visual_state_overlay(state)
    aria_block = visual_state_aria_block(state)
    integrity_block = integrity_label_html(inputs["integrity_label"])

    fleet_aligned = "ALIGNED" if inputs["fleet_phase_aligned"] else "DRIFT"
    fleet_target = html.escape(str(inputs["fleet_phase_target"]))
    coverage = int(inputs["zkba_class_coverage_count"])
    paused = "PAUSED (kill-switch held)" if inputs["chain_submission_paused"] else "ACTIVE"
    cedar_anchored = "ANCHORED" if inputs["cedar_v2_bundles_anchored"] else "PENDING"
    pv_ci = int(inputs["pv_ci_invariants_count"])
    wallet = html.escape(str(inputs["wallet_balance_iotx"]))
    last_tx = html.escape(str(inputs["last_anchor_tx_hash"]))
    last_block = int(inputs["last_anchor_block"])
    ts_ns = int(inputs["ts_ns"])
    zkba_hash = html.escape(inputs["zkba_manifest_hash_hex"])

    body_class = vpm_body_class(state)
    body = (
        '<body>\n'
        f'  <div class="{body_class}">\n'
        f'  {overlay}\n'
        '  <h1>VAPI Honesty Board</h1>\n'
        f'  {aria_block}\n'
        '  <h2>Protocol State Summary</h2>\n'
        '  <table class="vpm-status">\n'
        f'    <tr><td>Operator fleet phase:</td><td>{fleet_target} '
        f'<span class="vpm-state-pill vpm-state-{state}">{fleet_aligned}</span></td></tr>\n'
        f'    <tr><td>ZKBA class coverage:</td><td>{coverage} / 7</td></tr>\n'
        f'    <tr><td>Chain submission gate:</td><td>{paused}</td></tr>\n'
        f'    <tr><td>Cedar v2 lane bundles:</td><td>{cedar_anchored}</td></tr>\n'
        f'    <tr><td>PV-CI invariants:</td><td>{pv_ci}</td></tr>\n'
        f'    <tr><td>Operator wallet:</td><td><code>{wallet}</code></td></tr>\n'
        '  </table>\n'
        '  <h2>Last Anchor</h2>\n'
        '  <div class="vpm-meta">\n'
        f'    <div>Last anchor tx: <code>{last_tx}</code></div>\n'
        f'    <div>Block: <code>{last_block}</code></div>\n'
        '  </div>\n'
        '  <h2>Underlying ZKBA Projection</h2>\n'
        '  <div class="vpm-meta">\n'
        f'    <div>ZKBA manifest hash: <code>{zkba_hash}</code></div>\n'
        '  </div>\n'
        f'  {integrity_block}\n'
        '  <div class="vpm-footer">\n'
        f'    VPM ID: <code>{_VPM_ID}</code>. Lifecycle: Test Fixture. '
        'Self-contained projection. No CDN; no network; no wall-clock; '
        f'compile-time ts_ns: <code>{ts_ns}</code>.\n'
        '  </div>\n'
        '  </div>\n'
        '</body>\n'
    )

    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        f'{head}\n'
        f'{body}'
        '</html>\n'
    )


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def build_honesty_board_artifact(
    *,
    fleet_phase_aligned: bool,
    fleet_phase_target: str,
    zkba_class_coverage_count: int,
    chain_submission_paused: bool,
    cedar_v2_bundles_anchored: bool,
    pv_ci_invariants_count: int,
    wallet_balance_iotx: str,
    last_anchor_tx_hash: str,
    last_anchor_block: int,
    integrity_label: dict,
    zkba_manifest_hash_hex: str,
    visual_state: str,
    capture_mode: str,
    output_dir: Path,
    ts_ns: int,
) -> VPMArtifactManifest:
    """Build a HONESTY-BOARD-v1 VPM artifact deterministically.

    Args mirror the renderer's inputs dict shape exactly. The compiler
    enforces the strict Phase O4 discipline via compile_vpm_artifact()
    (no external resources, no runtime network, no wall-clock, no random,
    9-field Integrity Label visible in DOM).

    The ZKBA class context for this VPM is GIC (= 2 in the FROZEN enum) —
    the HONESTY-BOARD is conceptually grouped with the GIC Continuity
    Ledger family since both surface protocol-state continuity. CHAIN_ONLY
    proof weight (no fresh biometric capture).

    Returns the VPMArtifactManifest produced by the compiler.
    """
    if visual_state not in VISUAL_STATES:
        raise ValueError(
            f"visual_state must be one of {VISUAL_STATES}; got {visual_state!r}"
        )

    inputs = {
        "fleet_phase_aligned":         bool(fleet_phase_aligned),
        "fleet_phase_target":          str(fleet_phase_target),
        "zkba_class_coverage_count":   int(zkba_class_coverage_count),
        "chain_submission_paused":     bool(chain_submission_paused),
        "cedar_v2_bundles_anchored":   bool(cedar_v2_bundles_anchored),
        "pv_ci_invariants_count":      int(pv_ci_invariants_count),
        "wallet_balance_iotx":         str(wallet_balance_iotx),
        "last_anchor_tx_hash":         str(last_anchor_tx_hash),
        "last_anchor_block":           int(last_anchor_block),
        "visual_state":                str(visual_state),
        "integrity_label":             dict(integrity_label),
        "zkba_manifest_hash_hex":      str(zkba_manifest_hash_hex),
        "ts_ns":                       int(ts_ns),
    }

    return compile_vpm_artifact(
        vpm_id=_VPM_ID,
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        visual_state=visual_state,
        capture_mode=capture_mode,
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=zkba_manifest_hash_hex,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_honesty_board_html,
    )


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a HONESTY-BOARD-v1 VPM artifact "
                    "(Phase O4-VPM-INTEGRATION Stream A.1.a)."
    )
    parser.add_argument("--fleet-phase-aligned", action="store_true")
    parser.add_argument("--fleet-phase-target", default="O1_SHADOW")
    parser.add_argument("--zkba-class-coverage-count", type=int, default=7)
    parser.add_argument("--chain-submission-paused", action="store_true", default=True)
    parser.add_argument("--cedar-v2-bundles-anchored", action="store_true", default=True)
    parser.add_argument("--pv-ci-invariants-count", type=int, default=67)
    parser.add_argument("--wallet-balance-iotx", default="15.03")
    parser.add_argument("--last-anchor-tx-hash", default="0xe807347eb837a2ac9db0da51de7ddba5952a3e0e2509e197d9cac3375d23aa23")
    parser.add_argument("--last-anchor-block", type=int, default=43348052)
    parser.add_argument("--zkba-manifest-hash-hex", required=True)
    parser.add_argument("--visual-state", default="live", choices=list(VISUAL_STATES))
    parser.add_argument("--capture-mode", default="live")
    parser.add_argument("--ts-ns", type=int, required=True)
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "honesty_board",
        )),
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    integrity_label = {
        "proof_type":             "VPM-HONESTY-BOARD",
        "capture_mode":           args.capture_mode,
        "raw_biometrics_exposed": False,
        "consent_active":         True,
        "zk_verified":            False,
        "on_chain_anchor":        bool(args.last_anchor_tx_hash and args.last_anchor_tx_hash != "n/a"),
        "proof_weight":           "CHAIN_ONLY",
        "revocation_status":      "active",
        "limitations":            ["Internal protocol-state projection; not a humanity proof"],
    }

    manifest = build_honesty_board_artifact(
        fleet_phase_aligned=args.fleet_phase_aligned,
        fleet_phase_target=args.fleet_phase_target,
        zkba_class_coverage_count=args.zkba_class_coverage_count,
        chain_submission_paused=args.chain_submission_paused,
        cedar_v2_bundles_anchored=args.cedar_v2_bundles_anchored,
        pv_ci_invariants_count=args.pv_ci_invariants_count,
        wallet_balance_iotx=args.wallet_balance_iotx,
        last_anchor_tx_hash=args.last_anchor_tx_hash,
        last_anchor_block=args.last_anchor_block,
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=args.zkba_manifest_hash_hex,
        visual_state=args.visual_state,
        capture_mode=args.capture_mode,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"HONESTY-BOARD-v1 compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  visual_state:          {manifest.visual_state}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
