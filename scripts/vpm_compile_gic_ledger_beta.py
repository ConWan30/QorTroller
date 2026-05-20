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
    compute_input_commitment,
)
from vpm_visual_grammar import (  # noqa: E402
    VISUAL_STATES,
    cert_section,
    render_vpm_certificate,
)


_VPM_ID = "HONESTY-BOARD-v1"
_GIC_BETA_INTERNAL_ID = "GIC-LEDGER-BETA-v1"


def _short_hex(h: str) -> str:
    """Space-group a hex string into 4-char blocks for compact table display
    (design head_hash/genesis_hash style: '7f3a 4b21 c8e0 …')."""
    s = str(h).lower().removeprefix("0x")
    if not s or any(c not in "0123456789abcdef" for c in s):
        return html.escape(str(h))
    return " ".join(s[i:i + 4] for i in range(0, min(len(s), 32), 4))


def _render_gic_ledger_beta_html(inputs: dict) -> str:
    """Render GIC Continuity Ledger Beta as the Claude-Design certificate
    (TEMPLATE v3). Content block: Chain · Continuity."""
    state = inputs["visual_state"]

    chain_head = str(inputs["gic_chain_head_hex"])
    chain_length = int(inputs["gic_chain_length"])
    genesis = str(inputs["gic_genesis_hash_hex"])
    genesis_ts = int(inputs["gic_genesis_ts_ns"])
    anchor_tx = str(inputs["on_chain_anchor_tx_hash"])
    anchor_block = int(inputs["on_chain_anchor_block"])
    session_id = html.escape(str(inputs["grind_session_id"]))
    zkba_hash = str(inputs["zkba_manifest_hash_hex"])

    on_chain = bool(anchor_tx and anchor_tx not in ("", "n/a") and anchor_block > 0)
    # Milestone text — machine + human; T-VPM-GIC-5 pins these literals.
    if chain_length >= 100:
        milestone_v = f"GIC_{chain_length} MILESTONE · INTACT"
    else:
        milestone_v = f"{chain_length} / 100 links · INTACT"

    if on_chain:
        anchor_v = (
            '<span data-gic-on-chain="true">'
            f'ANCHORED at block {anchor_block} '
            f'(tx <code>{html.escape(anchor_tx[:10])}…'
            f'{html.escape(anchor_tx[-8:])}</code>)</span>'
        )
        anchor_cls = "chain mono"
    else:
        anchor_v = '<span data-gic-on-chain="false">NOT ON CHAIN · filesystem-only</span>'
        anchor_cls = "dim mono"

    content = cert_section(
        "Chain · Continuity",
        f"chain_length {chain_length}",
        [
            ("grind_session_id", "amber mono", session_id),
            ("chain_length", "chain mono", html.escape(milestone_v)),
            ("head_hash", "chain mono",
             f'<code data-gic-head>{html.escape(chain_head)}</code>'),
            ("genesis_hash", "dim mono",
             f'<code data-gic-genesis>{html.escape(genesis)}</code>'),
            ("genesis_ts", "mono", str(genesis_ts)),
            ("on_chain_anchor", anchor_cls, anchor_v),
            ("zkba_manifest_hash", "dim mono", _short_hex(zkba_hash)),
        ],
    )

    return render_vpm_certificate(
        vpm_class=_GIC_BETA_INTERNAL_ID,
        title_text=_GIC_BETA_INTERNAL_ID,
        subtitle="Proof-of-continuity ledger · IoTeX-anchored",
        visual_state=state,
        commitment_hex=compute_input_commitment(inputs),
        content_html=content,
        integrity_label=inputs["integrity_label"],
        footer_fields=[
            ("schema", "gic-ledger-beta-v1"),
            ("vpm_id", _VPM_ID),
            ("zkba_manifest", _short_hex(zkba_hash)),
            ("ts_ns", str(int(inputs["ts_ns"]))),
        ],
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
