"""Phase O4-VPM-INTEGRATION Stream A.1.b — AGENT-REVIEW-v1 VPM compiler.

Second internal-projection VPM per Phase O4 plan §2.4. Produces a deterministic,
self-contained HTML accountability card for a single Operator Initiative agent
(anchor_sentry / guardian / curator) at a caller-supplied timestamp.

Registered VPM ID per VBDIP-0002A §10 registry: `AGENT-REVIEW-v1`
Lifecycle status after this commit (per plan §2.3 table): `Test Fixture`
Owning agent lane: Guardian (writes to `zk_verifications/` via existing v2 bundle
permit `tool:zk-audit-trail`). Conceptually a Guardian-lane audit-trail surface
covering operator-decision provenance for ANY of the three agents.

Composition profile:
  Inputs (caller-supplied, deterministic):
    agent_canonical_name        str ('anchor_sentry' | 'guardian' | 'curator')
    agent_id_hex                str (Q9-frozen agentId 64-char hex; the live
                                on-chain identity from Phase O0 / Sessions 1)
    current_phase               str ('O1_SHADOW' | 'O2_SUGGEST' | 'O3_ACT')
    shadow_log_row_count        int (count of cedar_shadow_log rows)
    drift_log_row_count         int (count of operator_agent_drift_log rows)
    last_operator_decision      str ('accept' | 'reject' | 'overturn_curator' | 'none')
    last_decision_ts_ns         int (uint64 timestamp; 0 if no decision yet)
    disagreement_rate_30d       float (0..1; from compute_operator_agent_disagreement_rate)
    false_positive_rate_30d     float (0..1; Curator-only; 0 for non-Curator)
    o2_ready                    bool
    o3_ready                    bool
  Wrapped ZKBA primitive reference:
    zkba_manifest_hash_hex      str

Track 1 invariants: same as A.1.a (filesystem-only, caller-supplied state,
deterministic compile, static-guard discipline).

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


_VPM_ID = "AGENT-REVIEW-v1"

_VALID_AGENTS = ("anchor_sentry", "guardian", "curator")
_VALID_PHASES = ("O1_SHADOW", "O2_SUGGEST", "O3_ACT")
_VALID_DECISIONS = ("accept", "reject", "overturn_curator", "none")


def _short_hex(h: str) -> str:
    """4-char space-grouped hex for compact table display."""
    s = str(h).lower().removeprefix("0x")
    if not s or any(c not in "0123456789abcdef" for c in s):
        return html.escape(str(h))
    return " ".join(s[i:i + 4] for i in range(0, min(len(s), 32), 4))


def _render_agent_review_html(inputs: dict) -> str:
    """Render AGENT-REVIEW-v1 as the Claude-Design certificate (TEMPLATE v3)."""
    state = inputs["visual_state"]

    agent_name = html.escape(str(inputs["agent_canonical_name"]))
    agent_id = str(inputs["agent_id_hex"])
    phase = html.escape(str(inputs["current_phase"]))
    shadow_count = int(inputs["shadow_log_row_count"])
    drift_count = int(inputs["drift_log_row_count"])
    last_decision = html.escape(str(inputs["last_operator_decision"]))
    last_decision_ts = int(inputs["last_decision_ts_ns"])
    disagreement = float(inputs["disagreement_rate_30d"])
    false_positive = float(inputs["false_positive_rate_30d"])
    o2_ready = bool(inputs["o2_ready"])
    o3_ready = bool(inputs["o3_ready"])
    zkba_hash = str(inputs["zkba_manifest_hash_hex"])

    drift_cls = "amber mono" if drift_count > 0 else "chain mono"
    o2_v = ('<span class="pill chain">READY</span>' if o2_ready
            else '<span class="pill dim">PENDING</span>')
    o3_v = ('<span class="pill chain">READY</span>' if o3_ready
            else '<span class="pill dim">PENDING</span>')

    content = (
        cert_section(
            "Agent · Identity", agent_name,
            [
                ("canonical_name", "amber mono", agent_name),
                ("on_chain_agent_id", "chain mono",
                 f'<code>{html.escape(agent_id)}</code>'),
                ("current_phase", "chain mono", phase),
            ],
        )
        + "\n"
        + cert_section(
            "Activity · 30d", "",
            [
                ("cedar_shadow_log_rows", "mono", str(shadow_count)),
                ("drift_findings", drift_cls, str(drift_count)),
                ("last_operator_decision", "mono", f"<code>{last_decision}</code>"),
                ("last_decision_ts_ns", "dim mono",
                 str(last_decision_ts) if last_decision_ts else "none"),
                ("disagreement_rate_30d", "mono", f"{disagreement:.4f}"),
                ("false_positive_rate_30d", "mono", f"{false_positive:.4f}"),
            ],
        )
        + "\n"
        + cert_section(
            "Phase · Readiness", "",
            [
                ("o2_suggest", "mono", o2_v),
                ("o3_acting", "mono", o3_v),
                ("zkba_manifest_hash", "dim mono", _short_hex(zkba_hash)),
            ],
        )
    )

    return render_vpm_certificate(
        vpm_class=_VPM_ID,
        title_text=f"AGENT-REVIEW · {agent_name}",
        subtitle="Operator-decision provenance · Guardian-lane audit surface",
        visual_state=state,
        commitment_hex=compute_input_commitment(inputs),
        content_html=content,
        integrity_label=inputs["integrity_label"],
        footer_fields=[
            ("schema", "agent-review-v1"),
            ("vpm_id", _VPM_ID),
            ("zkba_manifest", _short_hex(zkba_hash)),
            ("ts_ns", str(int(inputs["ts_ns"]))),
        ],
    )


def build_agent_review_artifact(
    *,
    agent_canonical_name: str,
    agent_id_hex: str,
    current_phase: str,
    shadow_log_row_count: int,
    drift_log_row_count: int,
    last_operator_decision: str,
    last_decision_ts_ns: int,
    disagreement_rate_30d: float,
    false_positive_rate_30d: float,
    o2_ready: bool,
    o3_ready: bool,
    integrity_label: dict,
    zkba_manifest_hash_hex: str,
    visual_state: str,
    capture_mode: str,
    output_dir: Path,
    ts_ns: int,
) -> VPMArtifactManifest:
    """Build an AGENT-REVIEW-v1 VPM artifact deterministically.

    ZKBA class context: CONSENT (= 5) — AGENT-REVIEW is conceptually grouped
    with Guardian's audit-trail surface family. CHAIN_ONLY proof weight.

    Validates `agent_canonical_name`, `current_phase`, `last_operator_decision`,
    `visual_state` against frozen sets before compiling. Raises ValueError on
    any unknown value.
    """
    if visual_state not in VISUAL_STATES:
        raise ValueError(
            f"visual_state must be one of {VISUAL_STATES}; got {visual_state!r}"
        )
    if agent_canonical_name not in _VALID_AGENTS:
        raise ValueError(
            f"agent_canonical_name must be one of {_VALID_AGENTS}; "
            f"got {agent_canonical_name!r}"
        )
    if current_phase not in _VALID_PHASES:
        raise ValueError(
            f"current_phase must be one of {_VALID_PHASES}; got {current_phase!r}"
        )
    if last_operator_decision not in _VALID_DECISIONS:
        raise ValueError(
            f"last_operator_decision must be one of {_VALID_DECISIONS}; "
            f"got {last_operator_decision!r}"
        )

    inputs = {
        "agent_canonical_name":    str(agent_canonical_name),
        "agent_id_hex":            str(agent_id_hex),
        "current_phase":           str(current_phase),
        "shadow_log_row_count":    int(shadow_log_row_count),
        "drift_log_row_count":     int(drift_log_row_count),
        "last_operator_decision":  str(last_operator_decision),
        "last_decision_ts_ns":     int(last_decision_ts_ns),
        "disagreement_rate_30d":   float(disagreement_rate_30d),
        "false_positive_rate_30d": float(false_positive_rate_30d),
        "o2_ready":                bool(o2_ready),
        "o3_ready":                bool(o3_ready),
        "visual_state":            str(visual_state),
        "integrity_label":         dict(integrity_label),
        "zkba_manifest_hash_hex":  str(zkba_manifest_hash_hex),
        "ts_ns":                   int(ts_ns),
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
        html_renderer=_render_agent_review_html,
    )


def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an AGENT-REVIEW-v1 VPM artifact "
                    "(Phase O4-VPM-INTEGRATION Stream A.1.b)."
    )
    parser.add_argument("--agent-canonical-name", choices=list(_VALID_AGENTS), required=True)
    parser.add_argument("--agent-id-hex", required=True)
    parser.add_argument("--current-phase", choices=list(_VALID_PHASES), default="O1_SHADOW")
    parser.add_argument("--shadow-log-row-count", type=int, default=0)
    parser.add_argument("--drift-log-row-count", type=int, default=0)
    parser.add_argument("--last-operator-decision", choices=list(_VALID_DECISIONS), default="none")
    parser.add_argument("--last-decision-ts-ns", type=int, default=0)
    parser.add_argument("--disagreement-rate-30d", type=float, default=0.0)
    parser.add_argument("--false-positive-rate-30d", type=float, default=0.0)
    parser.add_argument("--o2-ready", action="store_true")
    parser.add_argument("--o3-ready", action="store_true")
    parser.add_argument("--zkba-manifest-hash-hex", required=True)
    parser.add_argument("--visual-state", default="live", choices=list(VISUAL_STATES))
    parser.add_argument("--capture-mode", default="live")
    parser.add_argument("--ts-ns", type=int, required=True)
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "agent_review",
        )),
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    integrity_label = {
        "proof_type":             "VPM-AGENT-REVIEW",
        "capture_mode":           args.capture_mode,
        "raw_biometrics_exposed": False,
        "consent_active":         True,
        "zk_verified":            False,
        "on_chain_anchor":        True,
        "proof_weight":           "CHAIN_ONLY",
        "revocation_status":      "active",
        "limitations":            ["Operator-decision provenance only; not a humanity proof"],
    }

    manifest = build_agent_review_artifact(
        agent_canonical_name=args.agent_canonical_name,
        agent_id_hex=args.agent_id_hex,
        current_phase=args.current_phase,
        shadow_log_row_count=args.shadow_log_row_count,
        drift_log_row_count=args.drift_log_row_count,
        last_operator_decision=args.last_operator_decision,
        last_decision_ts_ns=args.last_decision_ts_ns,
        disagreement_rate_30d=args.disagreement_rate_30d,
        false_positive_rate_30d=args.false_positive_rate_30d,
        o2_ready=args.o2_ready,
        o3_ready=args.o3_ready,
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=args.zkba_manifest_hash_hex,
        visual_state=args.visual_state,
        capture_mode=args.capture_mode,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"AGENT-REVIEW-v1 compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  visual_state:          {manifest.visual_state}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
