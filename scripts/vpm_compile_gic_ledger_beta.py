"""Phase O4-VPM-INTEGRATION Stream A.1.d — GIC Continuity Ledger BETA VPM compiler.

Fourth internal-projection VPM. Promotes the existing GIC Continuity Ledger
Alpha (`scripts/zkba_compile_gic_ledger.py` — Phase O3 commit `3b3081d3`,
class 2 ZKBA Continuity Ledger Alpha) to a VPM-wrapped artifact under the
Phase O4 compiler discipline.

The Alpha shipped as a raw ZKBA projection (HTML + `vapi-zkba-manifest-v1`
manifest); the Beta wraps that projection with:

  - 6-state Anti-Hype Visual Grammar (compiles in any of the 6 FROZEN
    visual states; tested by T-VPM-GRAMMAR-1..6)
  - 9-field Integrity Nutrition Label
  - Static-guard compiler discipline (no external resources, no runtime
    network/randomness/wall-clock)
  - VPM artifact manifest schema `vapi-vpm-artifact-v1`
  - Composition link to the underlying ZKBA Alpha manifest via
    zkba_manifest_hash_hex

The Beta is purely additive to the Alpha — the Alpha compiler is unchanged;
operators can continue to emit Alpha artifacts directly via the original
script. Beta is the operator-console-facing surface that goes through the
VPM Registry tab (Phase O4 Stream C).

Registered VPM ID per VBDIP-0002A §10: `HONESTY-BOARD-v1` (umbrella; GIC
Beta is a specialization, like CDRR DAG)
Internal ID: `GIC-LEDGER-BETA-v1`
Lifecycle status after this commit: `Test Fixture`
Owning agent lane: Sentry (writes to `zk_artifacts/`)

Composition profile (inputs):
  gic_chain_head_hex          str (64-char hex; GIC_N head per Phase 235-A)
  gic_chain_length            int (N, e.g. 100 for GIC_100 milestone)
  gic_genesis_hash_hex        str (64-char hex; Phase 235-A genesis)
  gic_genesis_ts_ns           int (uint64; nanos)
  on_chain_anchor_tx_hash     str (e.g. 0xe807347eb... if anchored on chain)
  on_chain_anchor_block       int (block number; 0 if not anchored)
  grind_session_id            str (e.g. 'grind_phase235_v1')

ZKBA class: GIC (= 2). Proof weight: CHAIN_ONLY.

Author: VAPI Architect (Phase O4 Commit 4)
Date: 2026-05-13
"""
from __future__ import annotations

import argparse
import html
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


_VPM_ID = "HONESTY-BOARD-v1"
_GIC_BETA_INTERNAL_ID = "GIC-LEDGER-BETA-v1"


def _render_gic_chain_svg(chain_length: int) -> str:
    """Render a deterministic horizontal chain-link sparkline as inline SVG.

    For chain_length N we render min(N, 50) link dots arranged horizontally.
    No xmlns attribute (HTML5 inline-SVG); no animation; no scripting;
    fully self-contained.

    Layout: 50 dots × 12px stride = 600px wide; height 24px. Color amber
    (#f0a868) for completed links, dimmer (#1a2a40) for absent (when
    chain_length < 50).
    """
    visible = max(0, min(50, int(chain_length)))
    dots: list[str] = []
    for i in range(50):
        x = 12 + (i * 12)
        if i < visible:
            color = "#f0a868"
        else:
            color = "#1a2a40"
        dots.append(
            f'<circle cx="{x}" cy="12" r="4" fill="{color}" data-gic-link-index="{i}"/>'
        )
    return (
        '<svg class="gic-chain-sparkline" width="612" height="24" '
        'viewBox="0 0 612 24" aria-label="GIC chain dots; one dot per link">\n'
        '<rect x="0" y="0" width="612" height="24" fill="#0a0e14"/>\n'
        + '\n'.join(dots) + '\n'
        '</svg>'
    )


def _render_gic_ledger_beta_html(inputs: dict) -> str:
    """Render GIC Continuity Ledger Beta HTML body deterministically."""
    state = inputs["visual_state"]
    head = assemble_vpm_head(
        title=f"VAPI GIC Continuity Ledger (BETA) — {state.upper()}",
        visual_state=state,
        extra_style=(
            ".gic-chain-sparkline { display: block; margin: 1em auto; "
            "max-width: 612px; }\n"
            ".gic-milestone-badge { background: #5bd6a3; color: #020408; "
            "padding: 4px 12px; border-radius: 4px; font-weight: bold; }\n"
        ),
    )

    overlay = visual_state_overlay(state)
    aria_block = visual_state_aria_block(state)
    integrity_block = integrity_label_html(inputs["integrity_label"])
    body_class = vpm_body_class(state)

    chain_head = html.escape(str(inputs["gic_chain_head_hex"]))
    chain_length = int(inputs["gic_chain_length"])
    genesis = html.escape(str(inputs["gic_genesis_hash_hex"]))
    genesis_ts = int(inputs["gic_genesis_ts_ns"])
    anchor_tx = html.escape(str(inputs["on_chain_anchor_tx_hash"]))
    anchor_block = int(inputs["on_chain_anchor_block"])
    session_id = html.escape(str(inputs["grind_session_id"]))
    ts_ns = int(inputs["ts_ns"])
    zkba_hash = html.escape(inputs["zkba_manifest_hash_hex"])

    chain_svg = _render_gic_chain_svg(chain_length)
    milestone_html = (
        f'<span class="gic-milestone-badge">GIC_{chain_length} MILESTONE</span>'
        if chain_length >= 100
        else f'<span>{chain_length} / 100 links</span>'
    )
    anchor_status = (
        f'<span data-gic-on-chain="true">ANCHORED at block {anchor_block} '
        f'(tx <code>{anchor_tx[:10]}...{anchor_tx[-8:]}</code>)</span>'
        if anchor_tx and anchor_tx != "n/a" and anchor_block > 0
        else '<span data-gic-on-chain="false">NOT ON CHAIN (filesystem-only)</span>'
    )

    body = (
        '<body>\n'
        f'  <div class="{body_class}" data-gic-beta-id="{_GIC_BETA_INTERNAL_ID}">\n'
        f'  {overlay}\n'
        '  <h1>GIC Continuity Ledger (BETA)</h1>\n'
        f'  {aria_block}\n'
        '  <h2>Chain Continuity</h2>\n'
        '  <table class="vpm-status">\n'
        f'    <tr><td>Grind session ID:</td><td><code>{session_id}</code></td></tr>\n'
        f'    <tr><td>Chain length:</td><td>{milestone_html}</td></tr>\n'
        f'    <tr><td>Head hash:</td><td><code data-gic-head>{chain_head}</code></td></tr>\n'
        f'    <tr><td>Genesis hash:</td><td><code data-gic-genesis>{genesis}</code></td></tr>\n'
        f'    <tr><td>Genesis ts_ns:</td><td><code>{genesis_ts}</code></td></tr>\n'
        '  </table>\n'
        '  <h2>Chain Visualization</h2>\n'
        f'  {chain_svg}\n'
        '  <h2>On-Chain Anchor</h2>\n'
        f'  <div class="vpm-meta">{anchor_status}</div>\n'
        '  <h2>Underlying ZKBA Projection (Alpha)</h2>\n'
        '  <div class="vpm-meta">\n'
        f'    <div>ZKBA manifest hash: <code>{zkba_hash}</code></div>\n'
        '    <div>The Alpha projection is unchanged; this Beta wraps it '
        'with the Phase O4 compiler discipline + Anti-Hype Visual Grammar.</div>\n'
        '  </div>\n'
        f'  {integrity_block}\n'
        '  <div class="vpm-footer">\n'
        f'    Internal ID: <code>{_GIC_BETA_INTERNAL_ID}</code> (under '
        f'<code>{_VPM_ID}</code> umbrella). Lifecycle: Test Fixture. '
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


def build_gic_ledger_beta_artifact(
    *,
    gic_chain_head_hex: str,
    gic_chain_length: int,
    gic_genesis_hash_hex: str,
    gic_genesis_ts_ns: int,
    on_chain_anchor_tx_hash: str,
    on_chain_anchor_block: int,
    grind_session_id: str,
    integrity_label: dict,
    zkba_manifest_hash_hex: str,
    visual_state: str,
    capture_mode: str,
    output_dir: Path,
    ts_ns: int,
) -> VPMArtifactManifest:
    """Build a GIC Continuity Ledger Beta VPM artifact deterministically.

    ZKBA class context: GIC (= 2) — same class as the Alpha. CHAIN_ONLY
    proof weight (GIC state is on-chain anchored at the AdjudicationRegistry
    Phase 239 G3 ship).

    Hash format validation: chain_head and genesis hashes must be 64 hex
    chars (lowercase enforced by caller; uppercase accepted but normalized
    by html.escape at render time).
    """
    if visual_state not in VISUAL_STATES:
        raise ValueError(
            f"visual_state must be one of {VISUAL_STATES}; got {visual_state!r}"
        )
    # Loose validation: hex strings should be 64 chars + parseable as hex
    for field_name, hex_val in [
        ("gic_chain_head_hex", gic_chain_head_hex),
        ("gic_genesis_hash_hex", gic_genesis_hash_hex),
    ]:
        normalized = hex_val.lower()
        if normalized.startswith("0x"):
            normalized = normalized[2:]
        if len(normalized) != 64:
            raise ValueError(
                f"{field_name} must be 64 hex chars (32 bytes); "
                f"got {len(normalized)} chars"
            )
        try:
            int(normalized, 16)
        except ValueError:
            raise ValueError(f"{field_name} not valid hex: {hex_val!r}")

    inputs = {
        "gic_chain_head_hex":      str(gic_chain_head_hex),
        "gic_chain_length":        int(gic_chain_length),
        "gic_genesis_hash_hex":    str(gic_genesis_hash_hex),
        "gic_genesis_ts_ns":       int(gic_genesis_ts_ns),
        "on_chain_anchor_tx_hash": str(on_chain_anchor_tx_hash),
        "on_chain_anchor_block":   int(on_chain_anchor_block),
        "grind_session_id":        str(grind_session_id),
        "visual_state":            str(visual_state),
        "integrity_label":         dict(integrity_label),
        "zkba_manifest_hash_hex":  str(zkba_manifest_hash_hex),
        "ts_ns":                   int(ts_ns),
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
        html_renderer=_render_gic_ledger_beta_html,
    )


def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a GIC Continuity Ledger Beta VPM artifact "
                    "(Phase O4-VPM-INTEGRATION Stream A.1.d). Promotes the "
                    "Phase O3 GIC Continuity Ledger Alpha to a VPM-wrapped "
                    "artifact under the Phase O4 compiler discipline."
    )
    parser.add_argument(
        "--gic-chain-head-hex",
        default="0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da",
        help="GIC_N head hash (default: GIC_100 canonical head)",
    )
    parser.add_argument("--gic-chain-length", type=int, default=100)
    parser.add_argument(
        "--gic-genesis-hash-hex",
        default="87ce52cd21f9037730262debd4d247a76a6439bb754d9219fe10346ee1278c05",
        help="GIC genesis hash (default: Phase 235-A genesis 2026-04-26)",
    )
    parser.add_argument(
        "--gic-genesis-ts-ns", type=int, default=1777142267690827300,
    )
    parser.add_argument(
        "--on-chain-anchor-tx-hash",
        default="0xe807347eb837a2ac9db0da51de7ddba5952a3e0e2509e197d9cac3375d23aa23",
    )
    parser.add_argument("--on-chain-anchor-block", type=int, default=43348052)
    parser.add_argument("--grind-session-id", default="grind_phase235_v1")
    parser.add_argument("--zkba-manifest-hash-hex", required=True)
    parser.add_argument("--visual-state", default="live", choices=list(VISUAL_STATES))
    parser.add_argument("--capture-mode", default="live")
    parser.add_argument("--ts-ns", type=int, required=True)
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "gic_ledger_beta",
        )),
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    integrity_label = {
        "proof_type":             "VPM-GIC-LEDGER-BETA",
        "capture_mode":           args.capture_mode,
        "raw_biometrics_exposed": False,
        "consent_active":         True,
        "zk_verified":            False,
        "on_chain_anchor":        bool(args.on_chain_anchor_tx_hash and args.on_chain_anchor_block > 0),
        "proof_weight":           "CHAIN_ONLY",
        "revocation_status":      "active",
        "limitations":            [
            "Promotion of Phase O3 Alpha projection; same cryptographic content",
        ],
    }

    manifest = build_gic_ledger_beta_artifact(
        gic_chain_head_hex=args.gic_chain_head_hex,
        gic_chain_length=args.gic_chain_length,
        gic_genesis_hash_hex=args.gic_genesis_hash_hex,
        gic_genesis_ts_ns=args.gic_genesis_ts_ns,
        on_chain_anchor_tx_hash=args.on_chain_anchor_tx_hash,
        on_chain_anchor_block=args.on_chain_anchor_block,
        grind_session_id=args.grind_session_id,
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=args.zkba_manifest_hash_hex,
        visual_state=args.visual_state,
        capture_mode=args.capture_mode,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"GIC Continuity Ledger Beta VPM compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  visual_state:          {manifest.visual_state}")
    print(f"  chain_length:          {args.gic_chain_length}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
