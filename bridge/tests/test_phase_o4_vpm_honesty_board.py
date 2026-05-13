"""Phase O4-VPM-INTEGRATION Stream A.1.a — HONESTY-BOARD-v1 tests.

Test band:
  T-VPM-HB-1:   compiler ID + ZKBA class + proof weight pinning
  T-VPM-HB-2:   end-to-end happy path (state=live; manifest + HTML + DB)
  T-VPM-HB-3:   rebuild idempotency (same inputs -> same output_path)
  T-VPM-HB-4:   byte-stable determinism across two builds
  T-VPM-HB-5:   protocol-state fields surface in HTML body (visible to operator)
  T-VPM-HB-6:   per-input tamper detection (each field changes input_commitment)
  T-VPM-HB-7:   zkba_manifest_hash_hex binding (different hash -> different VPM)
  T-VPM-HB-8:   reject visual_state outside FROZEN 6-element set

Plus Layer 1 Anti-Hype Visual Grammar tests per Phase O4 plan §5.2:
  T-VPM-GRAMMAR-1..6: parametrized over all 6 VPMVisualState values; for
                     each state, the emitted HONESTY-BOARD HTML must contain
                     ALL substrings in vpm_visual_grammar.VISUAL_STATE_SIGNATURES[state].
                     Plus §5.4 meta-tag + aria-label markers.

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
from vpm_compile_honesty_board import (  # noqa: E402
    _VPM_ID,
    build_honesty_board_artifact,
)


# ---------------------------------------------------------------------------
# Canonical fixture
# ---------------------------------------------------------------------------

_INTEGRITY_LABEL = {
    "proof_type":             "VPM-HONESTY-BOARD",
    "capture_mode":           "live",
    "raw_biometrics_exposed": False,
    "consent_active":         True,
    "zk_verified":            False,
    "on_chain_anchor":        True,
    "proof_weight":           "CHAIN_ONLY",
    "revocation_status":      "active",
    "limitations":            ["Internal protocol-state projection"],
}

_FIXTURE_TS_NS = 1779000000000000000
_FIXTURE_ZKBA_HASH = "b" * 64


def _kwargs(**overrides) -> dict:
    """Default fixture kwargs; overrides merge in."""
    base = dict(
        fleet_phase_aligned=True,
        fleet_phase_target="O1_SHADOW",
        zkba_class_coverage_count=7,
        chain_submission_paused=True,
        cedar_v2_bundles_anchored=True,
        pv_ci_invariants_count=67,
        wallet_balance_iotx="15.03",
        last_anchor_tx_hash="0xe807347eb837a2ac9db0da51de7ddba5952a3e0e2509e197d9cac3375d23aa23",
        last_anchor_block=43348052,
        integrity_label=_INTEGRITY_LABEL,
        zkba_manifest_hash_hex=_FIXTURE_ZKBA_HASH,
        visual_state="live",
        capture_mode="live",
        ts_ns=_FIXTURE_TS_NS,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# T-VPM-HB-1 — compiler identifiers pinned
# ---------------------------------------------------------------------------

def test_t_vpm_hb_1_compiler_identifiers_pinned():
    """Registered VPM ID + ZKBA class + proof weight match the plan §2.3
    placement table (HONESTY-BOARD-v1 / GIC / CHAIN_ONLY)."""
    assert _VPM_ID == "HONESTY-BOARD-v1"
    # Verified via build, not asserting internals
    from vpm_compile_honesty_board import build_honesty_board_artifact as fn
    assert callable(fn)


# ---------------------------------------------------------------------------
# T-VPM-HB-2 — end-to-end happy path
# ---------------------------------------------------------------------------

def test_t_vpm_hb_2_end_to_end_happy_path(tmp_path):
    """build_honesty_board_artifact produces a well-formed VPMArtifactManifest;
    emitted HTML on disk; output_hash matches SHA-256 of bytes."""
    manifest = build_honesty_board_artifact(
        **_kwargs(output_dir=tmp_path / "hb_t2"),
    )
    assert isinstance(manifest, VPMArtifactManifest)
    assert manifest.schema == _VPM_ARTIFACT_SCHEMA
    assert manifest.vpm_id == _VPM_ID
    assert manifest.zkba_class == int(ZKBAClass.GIC)
    assert manifest.proof_weight == int(ProofWeightClass.CHAIN_ONLY)
    assert manifest.visual_state == "live"
    assert manifest.capture_mode == "live"
    assert manifest.zkba_manifest_hash_hex == _FIXTURE_ZKBA_HASH
    assert manifest.ts_ns == _FIXTURE_TS_NS

    html_path = Path(manifest.output_path)
    assert html_path.exists()
    html_bytes = html_path.read_bytes()
    assert hashlib.sha256(html_bytes).hexdigest() == manifest.output_hash_hex

    sidecar = html_path.with_name(html_path.stem + ".vpm.manifest.json")
    assert sidecar.exists()


# ---------------------------------------------------------------------------
# T-VPM-HB-3 — rebuild idempotency
# ---------------------------------------------------------------------------

def test_t_vpm_hb_3_rebuild_idempotent(tmp_path):
    """Same inputs across two builds in the same dir produce the same
    output_path (deterministic naming) and the file is overwritten with
    byte-identical content."""
    out = tmp_path / "hb_t3"
    m1 = build_honesty_board_artifact(**_kwargs(output_dir=out))
    m2 = build_honesty_board_artifact(**_kwargs(output_dir=out))
    assert m1.output_path == m2.output_path
    assert m1.input_commitment_hex == m2.input_commitment_hex
    assert m1.output_hash_hex == m2.output_hash_hex


# ---------------------------------------------------------------------------
# T-VPM-HB-4 — byte-stable determinism across two builds in different dirs
# ---------------------------------------------------------------------------

def test_t_vpm_hb_4_byte_stable_two_runs(tmp_path):
    """Two independent builds in different output dirs produce
    byte-identical HTML output."""
    out_a = tmp_path / "hb_a"
    out_b = tmp_path / "hb_b"
    m_a = build_honesty_board_artifact(**_kwargs(output_dir=out_a))
    m_b = build_honesty_board_artifact(**_kwargs(output_dir=out_b))
    bytes_a = Path(m_a.output_path).read_bytes()
    bytes_b = Path(m_b.output_path).read_bytes()
    assert bytes_a == bytes_b
    assert m_a.input_commitment_hex == m_b.input_commitment_hex
    assert m_a.output_hash_hex == m_b.output_hash_hex


# ---------------------------------------------------------------------------
# T-VPM-HB-5 — protocol-state fields surface in HTML body
# ---------------------------------------------------------------------------

def test_t_vpm_hb_5_protocol_state_fields_visible(tmp_path):
    """Operator-facing fields must appear in emitted HTML for actual audit
    value. Each canonical field is verified present."""
    manifest = build_honesty_board_artifact(
        **_kwargs(output_dir=tmp_path / "hb_t5"),
    )
    html = Path(manifest.output_path).read_text(encoding="utf-8")
    assert "ALIGNED" in html  # fleet_phase_aligned=True
    assert "O1_SHADOW" in html
    assert "7 / 7" in html  # 7 ZKBA classes
    assert "PAUSED" in html  # chain_submission_paused=True
    assert "ANCHORED" in html  # cedar_v2_bundles_anchored=True
    assert "67" in html  # PV-CI invariant count
    assert "15.03" in html  # wallet balance
    assert "0xe807347e" in html  # last anchor tx hash (partial)
    assert "43348052" in html  # last anchor block


# ---------------------------------------------------------------------------
# T-VPM-HB-6 — per-input tamper detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("field,mutated", [
    ("fleet_phase_aligned",        False),
    ("fleet_phase_target",         "O3_ACT"),
    ("zkba_class_coverage_count",  6),
    ("chain_submission_paused",    False),
    ("cedar_v2_bundles_anchored",  False),
    ("pv_ci_invariants_count",     77),
    ("wallet_balance_iotx",        "0.5"),
    ("last_anchor_tx_hash",        "0xdead"),
    ("last_anchor_block",          0),
])
def test_t_vpm_hb_6_per_input_tamper_detection(field, mutated, tmp_path):
    """Mutating any input field changes the input_commitment_hex (and
    therefore the output_path and content)."""
    canonical = build_honesty_board_artifact(
        **_kwargs(output_dir=tmp_path / "hb_t6_canonical"),
    )
    tampered = build_honesty_board_artifact(
        **_kwargs(**{field: mutated}, output_dir=tmp_path / f"hb_t6_{field}"),
    )
    assert canonical.input_commitment_hex != tampered.input_commitment_hex, (
        f"field {field}: tamper not detected"
    )


# ---------------------------------------------------------------------------
# T-VPM-HB-7 — zkba_manifest_hash_hex binding
# ---------------------------------------------------------------------------

def test_t_vpm_hb_7_zkba_manifest_hash_binding(tmp_path):
    """Different zkba_manifest_hash_hex with otherwise-identical inputs
    produces a different input_commitment_hex — proves the binding link
    to the underlying ZKBA projection is in the preimage."""
    base = build_honesty_board_artifact(
        **_kwargs(output_dir=tmp_path / "hb_t7_base"),
    )
    different_hash = "c" * 64
    rebound = build_honesty_board_artifact(
        **_kwargs(
            zkba_manifest_hash_hex=different_hash,
            output_dir=tmp_path / "hb_t7_rebound",
        ),
    )
    assert base.input_commitment_hex != rebound.input_commitment_hex
    assert base.zkba_manifest_hash_hex == _FIXTURE_ZKBA_HASH
    assert rebound.zkba_manifest_hash_hex == different_hash


# ---------------------------------------------------------------------------
# T-VPM-HB-8 — reject visual_state outside FROZEN 6-element set
# ---------------------------------------------------------------------------

def test_t_vpm_hb_8_reject_unknown_visual_state(tmp_path):
    """An unknown visual_state (not in VISUAL_STATES) must raise ValueError
    before any output is written."""
    with pytest.raises(ValueError) as excinfo:
        build_honesty_board_artifact(
            **_kwargs(
                visual_state="suspicious",
                output_dir=tmp_path / "hb_t8",
            ),
        )
    assert "visual_state" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# T-VPM-GRAMMAR-1..6 — Anti-Hype Visual Grammar parametrized over 6 states
#
# For each of the 6 FROZEN visual states, build a HONESTY-BOARD VPM in that
# state and assert that ALL canonical DOM-signature substrings for the state
# (per vpm_visual_grammar.VISUAL_STATE_SIGNATURES) appear in the emitted
# HTML. Plus §5.4 meta-tag + aria-label markers.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", VISUAL_STATES, ids=list(VISUAL_STATES))
def test_t_vpm_grammar_honesty_board_dom_signature(state, tmp_path):
    """T-VPM-GRAMMAR-N (HONESTY-BOARD): every emitted HTML for visual_state=N
    must contain every required substring in VISUAL_STATE_SIGNATURES[N]."""
    # Adjust capture_mode to match visual_state where the wrapper enums
    # admit it; compile_vpm_artifact validates the capture_mode against
    # _VPM_CAPTURE_MODES (which includes 'demo' too — we map any non-
    # matching state to a known-good capture mode for the test fixture).
    capture_mode_map = {
        "live": "live",
        "dry-run": "dry-run",
        "emulated": "emulated",
        "frozen-disabled": "frozen-disabled",
        "revoked": "live",       # revoked is a wrapper state, not capture
        "unverified": "demo",    # unverified ~ demo capture provenance
    }
    manifest = build_honesty_board_artifact(
        **_kwargs(
            visual_state=state,
            capture_mode=capture_mode_map[state],
            output_dir=tmp_path / f"hb_grammar_{state}",
        ),
    )
    html_text = Path(manifest.output_path).read_text(encoding="utf-8")

    # Per-state required signature substrings
    for required in VISUAL_STATE_SIGNATURES[state]:
        assert required in html_text, (
            f"state={state}: missing DOM signature substring "
            f"{required!r} in HONESTY-BOARD emitted HTML"
        )

    # §5.4 meta-tag + aria-label
    assert META_TAG_SIGNATURE in html_text, (
        f"state={state}: missing <meta name=\"vpm-visual-state\" tag"
    )
    assert ARIA_LABEL_SIGNATURE in html_text, (
        f"state={state}: missing role=\"status\" aria-label block"
    )
    assert f'content="{state}"' in html_text, (
        f"state={state}: meta tag does not carry content=\"{state}\""
    )
