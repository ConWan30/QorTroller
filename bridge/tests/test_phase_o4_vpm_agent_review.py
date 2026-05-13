"""Phase O4-VPM-INTEGRATION Stream A.1.b — AGENT-REVIEW-v1 tests.

Test band:
  T-VPM-AR-1:   compiler ID + ZKBA class + proof weight pinning
  T-VPM-AR-2:   end-to-end happy path
  T-VPM-AR-3:   rebuild idempotency
  T-VPM-AR-4:   byte-stable two-build determinism
  T-VPM-AR-5:   agent identity fields surface in HTML body
  T-VPM-AR-6:   per-input tamper detection (parametrized)
  T-VPM-AR-7:   reject unknown agent_canonical_name / current_phase / last_operator_decision
  T-VPM-AR-8:   Curator-only false_positive_rate semantic (rate>0 only meaningful for curator)

Plus T-VPM-GRAMMAR-1..6 parametrized over AGENT-REVIEW.

Author: VAPI Architect (Phase O4 Commit 4)
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_BRIDGE = os.path.normpath(os.path.join(_REPO, "bridge"))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402
from vsd_ui_compiler import VPMArtifactManifest, _VPM_ARTIFACT_SCHEMA  # noqa: E402
from vpm_visual_grammar import (  # noqa: E402
    VISUAL_STATES,
    VISUAL_STATE_SIGNATURES,
    META_TAG_SIGNATURE,
    ARIA_LABEL_SIGNATURE,
)
from vpm_compile_agent_review import (  # noqa: E402
    _VPM_ID,
    build_agent_review_artifact,
)


_INTEGRITY_LABEL = {
    "proof_type":             "VPM-AGENT-REVIEW",
    "capture_mode":           "live",
    "raw_biometrics_exposed": False,
    "consent_active":         True,
    "zk_verified":            False,
    "on_chain_anchor":        True,
    "proof_weight":           "CHAIN_ONLY",
    "revocation_status":      "active",
    "limitations":            ["Operator-decision provenance only"],
}

_FIXTURE_TS_NS = 1779100000000000000
_FIXTURE_ZKBA_HASH = "d" * 64
_FIXTURE_AGENT_ID = "b21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"


def _kwargs(**overrides) -> dict:
    base = dict(
        agent_canonical_name="anchor_sentry",
        agent_id_hex=_FIXTURE_AGENT_ID,
        current_phase="O1_SHADOW",
        shadow_log_row_count=42,
        drift_log_row_count=0,
        last_operator_decision="accept",
        last_decision_ts_ns=1778900000000000000,
        disagreement_rate_30d=0.02,
        false_positive_rate_30d=0.0,
        o2_ready=False,
        o3_ready=False,
        integrity_label=_INTEGRITY_LABEL,
        zkba_manifest_hash_hex=_FIXTURE_ZKBA_HASH,
        visual_state="live",
        capture_mode="live",
        ts_ns=_FIXTURE_TS_NS,
    )
    base.update(overrides)
    return base


def test_t_vpm_ar_1_compiler_identifiers_pinned():
    assert _VPM_ID == "AGENT-REVIEW-v1"
    from vpm_compile_agent_review import build_agent_review_artifact as fn
    assert callable(fn)


def test_t_vpm_ar_2_end_to_end_happy_path(tmp_path):
    manifest = build_agent_review_artifact(**_kwargs(output_dir=tmp_path / "ar_t2"))
    assert isinstance(manifest, VPMArtifactManifest)
    assert manifest.schema == _VPM_ARTIFACT_SCHEMA
    assert manifest.vpm_id == _VPM_ID
    assert manifest.zkba_class == int(ZKBAClass.CONSENT)
    assert manifest.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    assert manifest.visual_state == "live"
    html_path = Path(manifest.output_path)
    assert html_path.exists()
    html_bytes = html_path.read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex


def test_t_vpm_ar_3_rebuild_idempotent(tmp_path):
    out = tmp_path / "ar_t3"
    m1 = build_agent_review_artifact(**_kwargs(output_dir=out))
    m2 = build_agent_review_artifact(**_kwargs(output_dir=out))
    assert m1.output_path == m2.output_path
    assert m1.output_hash_hex == m2.output_hash_hex


def test_t_vpm_ar_4_byte_stable_two_runs(tmp_path):
    m_a = build_agent_review_artifact(**_kwargs(output_dir=tmp_path / "ar_a"))
    m_b = build_agent_review_artifact(**_kwargs(output_dir=tmp_path / "ar_b"))
    assert Path(m_a.output_path).read_bytes() == Path(m_b.output_path).read_bytes()
    assert m_a.input_commitment_hex == m_b.input_commitment_hex


def test_t_vpm_ar_5_agent_identity_fields_visible(tmp_path):
    manifest = build_agent_review_artifact(**_kwargs(output_dir=tmp_path / "ar_t5"))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    assert "anchor_sentry" in html_text
    assert _FIXTURE_AGENT_ID in html_text
    assert "O1_SHADOW" in html_text
    assert "42" in html_text  # shadow_log_row_count
    assert "accept" in html_text  # last_operator_decision
    assert "0.0200" in html_text  # disagreement_rate formatted to 4 decimals


@pytest.mark.parametrize("field,mutated", [
    ("agent_canonical_name",    "guardian"),
    ("agent_id_hex",            "f" * 64),
    ("current_phase",           "O2_SUGGEST"),
    ("shadow_log_row_count",    100),
    ("drift_log_row_count",     5),
    ("last_operator_decision",  "reject"),
    ("disagreement_rate_30d",   0.05),
    ("o2_ready",                True),
])
def test_t_vpm_ar_6_per_input_tamper_detection(field, mutated, tmp_path):
    canonical = build_agent_review_artifact(**_kwargs(output_dir=tmp_path / "ar_canonical"))
    tampered = build_agent_review_artifact(**_kwargs(
        **{field: mutated},
        output_dir=tmp_path / f"ar_{field}",
    ))
    assert canonical.input_commitment_hex != tampered.input_commitment_hex


def test_t_vpm_ar_7_reject_unknown_enum_values(tmp_path):
    """Unknown agent / phase / decision values must raise ValueError."""
    # Unknown agent
    with pytest.raises(ValueError):
        build_agent_review_artifact(**_kwargs(
            agent_canonical_name="alien_agent",
            output_dir=tmp_path / "ar_bad1",
        ))
    # Unknown phase
    with pytest.raises(ValueError):
        build_agent_review_artifact(**_kwargs(
            current_phase="O9_GHOST",
            output_dir=tmp_path / "ar_bad2",
        ))
    # Unknown decision
    with pytest.raises(ValueError):
        build_agent_review_artifact(**_kwargs(
            last_operator_decision="maybe",
            output_dir=tmp_path / "ar_bad3",
        ))


def test_t_vpm_ar_8_curator_false_positive_rate_semantic(tmp_path):
    """false_positive_rate is semantically Curator-only (per Phase O3
    overturn_curator decision wiring); test that the rate surfaces correctly
    for Curator and changes the commitment when set."""
    sentry_zero = build_agent_review_artifact(**_kwargs(
        agent_canonical_name="anchor_sentry",
        false_positive_rate_30d=0.0,
        output_dir=tmp_path / "ar_sentry",
    ))
    curator_zero = build_agent_review_artifact(**_kwargs(
        agent_canonical_name="curator",
        false_positive_rate_30d=0.0,
        output_dir=tmp_path / "ar_curator0",
    ))
    curator_nonzero = build_agent_review_artifact(**_kwargs(
        agent_canonical_name="curator",
        false_positive_rate_30d=0.05,
        output_dir=tmp_path / "ar_curator5",
    ))
    # Distinct commitments due to agent + rate variation
    assert sentry_zero.input_commitment_hex != curator_zero.input_commitment_hex
    assert curator_zero.input_commitment_hex != curator_nonzero.input_commitment_hex
    # Surface check: nonzero rate visible in HTML
    html_text = Path(curator_nonzero.output_path).read_text(encoding="utf-8")
    assert "0.0500" in html_text


@pytest.mark.parametrize("state", VISUAL_STATES, ids=list(VISUAL_STATES))
def test_t_vpm_grammar_agent_review_dom_signature(state, tmp_path):
    """T-VPM-GRAMMAR-N (AGENT-REVIEW): all canonical signature substrings
    for the visual_state must appear in emitted HTML."""
    capture_mode_map = {
        "live": "live", "dry-run": "dry-run", "emulated": "emulated",
        "frozen-disabled": "frozen-disabled", "revoked": "live", "unverified": "demo",
    }
    manifest = build_agent_review_artifact(**_kwargs(
        visual_state=state,
        capture_mode=capture_mode_map[state],
        output_dir=tmp_path / f"ar_grammar_{state}",
    ))
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")
    for required in VISUAL_STATE_SIGNATURES[state]:
        assert required in html_text, (
            f"state={state}: missing DOM signature substring {required!r} "
            f"in AGENT-REVIEW emitted HTML"
        )
    assert META_TAG_SIGNATURE in html_text
    assert ARIA_LABEL_SIGNATURE in html_text
    assert f'content="{state}"' in html_text
