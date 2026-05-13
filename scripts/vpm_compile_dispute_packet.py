"""Phase O4-VPM-INTEGRATION Stream A.2.a — DISPUTE-PACKET-v1 VPM compiler.

First consumer-facing VPM per Phase O4 plan section 3 Stream A.2. Produces a
deterministic, self-contained HTML packet a Referee or Operations team can
share with disputing parties when a tournament adjudication ruling is
challenged.

Registered VPM ID per VBDIP-0002A section 10 registry: `DISPUTE-PACKET-v1`
Lifecycle status after this commit (per plan section 2.3 table): `Compiler Target`
Owning agent lane: Guardian (writes to `zk_verifications/` via existing v2
bundle permit `tool:zk-audit-trail`)

The packet is Guardian-lane because the audit-trail of a contested ruling
is Guardian's structural responsibility — the same lane that holds
shadow-log + drift-log surfaces. Sentry's `tool:zk-artifact-anchor` permit
applies only to `zk_artifacts/`; Curator's `tool:zk-marketplace-listing`
permit applies only to `zk_listings/`. Both are FORBIDDEN from compiling
DISPUTE-PACKET-v1 artifacts at the Cedar policy level — this is asserted
by T-VPM-DP-CFSS-1.

Composition profile:
  Inputs (caller-supplied, deterministic):
    dispute_id                  str ('dispute-NNNNNN' — operator-assigned)
    tournament_id               int (Phase O3 tournament canonical id)
    disputed_player_address     str (20-byte hex; the contesting party)
    disputed_ruling_hash_hex    str (64-char hex; Phase O3 agent ruling
                                hash being contested)
    adjudicator_agent_id        str ('anchor_sentry' | 'guardian' | 'curator')
    evidence_count              int (>= 0; how many evidence rows referenced)
    attestation_chain_hash_hex  str (64-char hex; chain of operator
                                decisions leading to this dispute)
    dispute_status              str ('open' | 'under_review' | 'resolved' |
                                'escalated')
    created_ts_ns               int (uint64)
  Wrapped ZKBA primitive reference:
    zkba_manifest_hash_hex      str

ZKBA class: CONSENT (= 5; same as AGENT-REVIEW for Guardian-lane audit
surfaces). Proof weight: CHAIN_ONLY.

Author: VAPI Architect (Phase O4 Commit 5)
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


_VPM_ID = "DISPUTE-PACKET-v1"

_VALID_AGENTS = ("anchor_sentry", "guardian", "curator")
_VALID_STATUSES = ("open", "under_review", "resolved", "escalated")


def _render_dispute_packet_html(inputs: dict) -> str:
    state = inputs["visual_state"]
    head = assemble_vpm_head(
        title=f"VAPI Dispute Packet — {html.escape(str(inputs['dispute_id']))} — {state.upper()}",
        visual_state=state,
        extra_style=(
            ".dispute-status-badge { padding: 4px 12px; border-radius: 4px; "
            "font-weight: bold; }\n"
            ".dispute-status-open { background: #f0a868; color: #020408; }\n"
            ".dispute-status-under_review { background: #5a8fb8; color: #020408; }\n"
            ".dispute-status-resolved { background: #5bd6a3; color: #020408; }\n"
            ".dispute-status-escalated { background: #d65b78; color: #020408; }\n"
        ),
    )

    overlay = visual_state_overlay(state)
    aria_block = visual_state_aria_block(state)
    integrity_block = integrity_label_html(inputs["integrity_label"])
    body_class = vpm_body_class(state)

    dispute_id = html.escape(str(inputs["dispute_id"]))
    tournament_id = int(inputs["tournament_id"])
    disputed_player = html.escape(str(inputs["disputed_player_address"]))
    ruling_hash = html.escape(str(inputs["disputed_ruling_hash_hex"]))
    adjudicator = html.escape(str(inputs["adjudicator_agent_id"]))
    evidence_count = int(inputs["evidence_count"])
    attestation_hash = html.escape(str(inputs["attestation_chain_hash_hex"]))
    dispute_status = str(inputs["dispute_status"])
    created_ts = int(inputs["created_ts_ns"])
    ts_ns = int(inputs["ts_ns"])
    zkba_hash = html.escape(inputs["zkba_manifest_hash_hex"])

    body = (
        '<body>\n'
        f'  <div class="{body_class}" data-dispute-id="{dispute_id}">\n'
        f'  {overlay}\n'
        f'  <h1>VAPI Dispute Packet</h1>\n'
        f'  {aria_block}\n'
        '  <h2>Case Header</h2>\n'
        '  <table class="vpm-status">\n'
        f'    <tr><td>Dispute ID:</td><td><code data-dispute-field="id">{dispute_id}</code></td></tr>\n'
        f'    <tr><td>Tournament ID:</td><td><code data-dispute-field="tournament">{tournament_id}</code></td></tr>\n'
        f'    <tr><td>Status:</td><td><span class="dispute-status-badge dispute-status-{dispute_status}" data-dispute-field="status">{html.escape(dispute_status.upper())}</span></td></tr>\n'
        f'    <tr><td>Created ts_ns:</td><td><code>{created_ts}</code></td></tr>\n'
        '  </table>\n'
        '  <h2>Contesting Party</h2>\n'
        '  <div class="vpm-meta">\n'
        f'    <div>Player address: <code data-dispute-field="player">{disputed_player}</code></div>\n'
        '  </div>\n'
        '  <h2>Disputed Ruling</h2>\n'
        '  <table class="vpm-status">\n'
        f'    <tr><td>Ruling hash:</td><td><code data-dispute-field="ruling_hash">{ruling_hash}</code></td></tr>\n'
        f'    <tr><td>Adjudicating agent:</td><td><code data-dispute-field="adjudicator">{adjudicator}</code></td></tr>\n'
        f'    <tr><td>Evidence count:</td><td>{evidence_count}</td></tr>\n'
        '  </table>\n'
        '  <h2>Attestation Chain</h2>\n'
        '  <div class="vpm-meta">\n'
        f'    <div>Chain hash: <code data-dispute-field="attestation_chain">{attestation_hash}</code></div>\n'
        '    <div>The attestation chain records the operator-decision sequence '
        'that led to the disputed ruling. Verifiers reproduce the chain hash '
        'from the bridge operator_agent_drafts table over the disputed ts_ns '
        'window to confirm chain integrity.</div>\n'
        '  </div>\n'
        '  <h2>Underlying ZKBA Projection</h2>\n'
        '  <div class="vpm-meta">\n'
        f'    <div>ZKBA manifest hash: <code>{zkba_hash}</code></div>\n'
        '  </div>\n'
        f'  {integrity_block}\n'
        '  <div class="vpm-footer">\n'
        f'    VPM ID: <code>{_VPM_ID}</code>. Lifecycle: Compiler Target. '
        'Guardian-lane audit-trail surface. Sentry + Curator FORBIDDEN at '
        'Cedar policy level. Self-contained projection. compile-time ts_ns: '
        f'<code>{ts_ns}</code>.\n'
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


def build_dispute_packet_artifact(
    *,
    dispute_id: str,
    tournament_id: int,
    disputed_player_address: str,
    disputed_ruling_hash_hex: str,
    adjudicator_agent_id: str,
    evidence_count: int,
    attestation_chain_hash_hex: str,
    dispute_status: str,
    created_ts_ns: int,
    integrity_label: dict,
    zkba_manifest_hash_hex: str,
    visual_state: str,
    capture_mode: str,
    output_dir: Path,
    ts_ns: int,
) -> VPMArtifactManifest:
    """Build a DISPUTE-PACKET-v1 VPM artifact deterministically.

    ZKBA class: CONSENT (Guardian-lane audit artifact family).
    Proof weight: CHAIN_ONLY (attestation chain references already on-chain
    or in operator_agent_drafts which is itself chain-derivable).

    Validates enum-style inputs (adjudicator_agent_id, dispute_status)
    against FROZEN sets and 64-hex-char fields against length.
    """
    if visual_state not in VISUAL_STATES:
        raise ValueError(
            f"visual_state must be one of {VISUAL_STATES}; got {visual_state!r}"
        )
    if adjudicator_agent_id not in _VALID_AGENTS:
        raise ValueError(
            f"adjudicator_agent_id must be one of {_VALID_AGENTS}; "
            f"got {adjudicator_agent_id!r}"
        )
    if dispute_status not in _VALID_STATUSES:
        raise ValueError(
            f"dispute_status must be one of {_VALID_STATUSES}; "
            f"got {dispute_status!r}"
        )
    if evidence_count < 0:
        raise ValueError(
            f"evidence_count must be non-negative; got {evidence_count!r}"
        )
    for field_name, hex_val in [
        ("disputed_ruling_hash_hex", disputed_ruling_hash_hex),
        ("attestation_chain_hash_hex", attestation_chain_hash_hex),
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
        "dispute_id":                  str(dispute_id),
        "tournament_id":               int(tournament_id),
        "disputed_player_address":     str(disputed_player_address),
        "disputed_ruling_hash_hex":    str(disputed_ruling_hash_hex),
        "adjudicator_agent_id":        str(adjudicator_agent_id),
        "evidence_count":              int(evidence_count),
        "attestation_chain_hash_hex":  str(attestation_chain_hash_hex),
        "dispute_status":              str(dispute_status),
        "created_ts_ns":               int(created_ts_ns),
        "visual_state":                str(visual_state),
        "integrity_label":             dict(integrity_label),
        "zkba_manifest_hash_hex":      str(zkba_manifest_hash_hex),
        "ts_ns":                       int(ts_ns),
    }

    return compile_vpm_artifact(
        vpm_id=_VPM_ID,
        zkba_class=ZKBAClass.CONSENT,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        visual_state=visual_state,
        capture_mode=capture_mode,
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=zkba_manifest_hash_hex,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_dispute_packet_html,
    )


def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a DISPUTE-PACKET-v1 VPM artifact "
                    "(Phase O4-VPM-INTEGRATION Stream A.2.a)."
    )
    parser.add_argument("--dispute-id", required=True)
    parser.add_argument("--tournament-id", type=int, required=True)
    parser.add_argument("--disputed-player-address", required=True)
    parser.add_argument("--disputed-ruling-hash-hex", required=True)
    parser.add_argument("--adjudicator-agent-id", choices=list(_VALID_AGENTS), required=True)
    parser.add_argument("--evidence-count", type=int, default=0)
    parser.add_argument("--attestation-chain-hash-hex", required=True)
    parser.add_argument("--dispute-status", choices=list(_VALID_STATUSES), default="open")
    parser.add_argument("--created-ts-ns", type=int, required=True)
    parser.add_argument("--zkba-manifest-hash-hex", required=True)
    parser.add_argument("--visual-state", default="live", choices=list(VISUAL_STATES))
    parser.add_argument("--capture-mode", default="live")
    parser.add_argument("--ts-ns", type=int, required=True)
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "dispute_packet",
        )),
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    integrity_label = {
        "proof_type":             "VPM-DISPUTE-PACKET",
        "capture_mode":           args.capture_mode,
        "raw_biometrics_exposed": False,
        "consent_active":         True,
        "zk_verified":            False,
        "on_chain_anchor":        True,
        "proof_weight":           "CHAIN_ONLY",
        "revocation_status":      "active",
        "limitations":            [
            "Audit-trail packet for a single dispute; not a humanity proof",
        ],
    }

    manifest = build_dispute_packet_artifact(
        dispute_id=args.dispute_id,
        tournament_id=args.tournament_id,
        disputed_player_address=args.disputed_player_address,
        disputed_ruling_hash_hex=args.disputed_ruling_hash_hex,
        adjudicator_agent_id=args.adjudicator_agent_id,
        evidence_count=args.evidence_count,
        attestation_chain_hash_hex=args.attestation_chain_hash_hex,
        dispute_status=args.dispute_status,
        created_ts_ns=args.created_ts_ns,
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=args.zkba_manifest_hash_hex,
        visual_state=args.visual_state,
        capture_mode=args.capture_mode,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"DISPUTE-PACKET-v1 compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  dispute_status:        {args.dispute_status}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
