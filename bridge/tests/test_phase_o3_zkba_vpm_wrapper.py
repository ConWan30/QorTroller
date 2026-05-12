"""Phase O3-ZKBA-TRACK1 Lane B G5b + G5c — VPM Wrapper + Visual Grammar tests.

Tests for VBDIP-0002 Appendix B (v1.1 amendment):
  - B.4 wrapper manifest schema
  - B.5 visual honesty grammar + Integrity Label
  - B.6 failure-state rules

G5b (wrapper manifest + Integrity Label) — T-VPM-1..10
G5c (Anti-Hype Visual Grammar)         — T-VPM-VG-1..12

The wrapper module sits in scripts/ (not bridge/vapi_bridge/) because it
parallels scripts/vsd_ui_compiler.py — both modules are tooling that
operates on ZKBA + VPM artifact manifests. The bridge codebase imports
neither at runtime; bridge tests import them for verification.

NO PV-CI invariant is registered for VPM-HONESTY-001; per VBDIP-0002
Appendix B B.5 + reconciliation plan §4, VPM-HONESTY-001 is a
methodology-doc identifier only. These tests exercise the wrapper's
mechanical enforcement of the same rules, but do not enter the
.github/INVARIANTS_ALLOWLIST.json or scripts/vapi_invariant_gate.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pytest

# Add bridge/ + scripts/ to sys.path so the wrapper module and ZKBA primitive
# both import cleanly from a fresh test process.
_HERE = os.path.dirname(__file__)
_BRIDGE = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402
from vsd_vpm_wrapper import (  # noqa: E402
    VPM_WRAPPER_SCHEMA,
    VPM_WRAPPER_VERSION,
    ZKBA_WRAPPED_SCHEMA,
    VPMVisualState,
    VPMCaptureMode,
    VPMLifecycleStatus,
    VPMRevocationStatus,
    VPMAnchorStatus,
    VPMIntegrityLabel,
    VPMWrapperManifest,
    vpm_canonical_json,
    compute_vpm_commitment,
    wrap_zkba_manifest,
    derive_visual_state,
    validate_vpm_manifest,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_zkba_manifest_dict(
    *,
    proof_weight: int = ProofWeightClass.CHAIN_ONLY.value,
    output_hash_hex: str = "f" * 64,
    zkba_class: int = ZKBAClass.GIC.value,
) -> dict:
    """Construct an asdict-shaped ZKBA manifest matching
    scripts/vsd_ui_compiler.ZKBAManifest fields."""
    return {
        "schema":               ZKBA_WRAPPED_SCHEMA,
        "zkba_class":           int(zkba_class),
        "proof_weight":         int(proof_weight),
        "output_path":          "gic_continuity_ledger/abc.html",
        "output_hash_hex":      str(output_hash_hex),
        "input_commitment_hex": "a" * 64,
        "compiler_version":     "0.1.0",
        "ts_ns":                1778000000000000000,
    }


def _make_integrity_label(
    *,
    proof_weight: int = ProofWeightClass.CHAIN_ONLY.value,
    capture_mode: str = VPMCaptureMode.DRY_RUN.value,
    consent_active: bool = True,
    zk_verified: bool = False,
    on_chain_anchor: bool = False,
    revocation_status: str = VPMRevocationStatus.ACTIVE.value,
) -> VPMIntegrityLabel:
    return VPMIntegrityLabel(
        proof_type="ZKBA-GIC",
        capture_mode=capture_mode,
        raw_biometrics_exposed=False,
        consent_active=consent_active,
        zk_verified=zk_verified,
        on_chain_anchor=on_chain_anchor,
        proof_weight=int(proof_weight),
        revocation_status=revocation_status,
        limitations=("chain-only projection", "no fresh biometric capture"),
    )


# ===========================================================================
# G5b — VPM Wrapper Manifest + Integrity Label tests (T-VPM-1..10)
# ===========================================================================

def test_t_vpm_1_wrapper_schema_frozen():
    """T-VPM-1: VPM_WRAPPER_SCHEMA is the FROZEN literal `vapi-vpm-manifest-v1`."""
    assert VPM_WRAPPER_SCHEMA == "vapi-vpm-manifest-v1"
    assert VPM_WRAPPER_VERSION == "0.1.0"


def test_t_vpm_2_wrapped_schema_cross_reference():
    """T-VPM-2: ZKBA_WRAPPED_SCHEMA matches the FROZEN ZKBA manifest schema
    string from scripts/vsd_ui_compiler.py. Wrapper REFERENCES, not REPLACES."""
    # Cross-verify against the canonical compiler module
    from vsd_ui_compiler import _MANIFEST_SCHEMA as _ZKBA_SCHEMA
    assert ZKBA_WRAPPED_SCHEMA == _ZKBA_SCHEMA
    assert ZKBA_WRAPPED_SCHEMA == "vapi-zkba-manifest-v1"


def test_t_vpm_3_wrap_zkba_manifest_happy_path():
    """T-VPM-3: wrap_zkba_manifest produces a valid wrapper manifest with
    correct cross-references + 9-field Integrity Label embedded."""
    zkba = _make_zkba_manifest_dict()
    label = _make_integrity_label()
    manifest = wrap_zkba_manifest(
        zkba_manifest_dict=zkba,
        vpm_id="QR-ELIGIBILITY-v1",
        audience="Tournament Organizers",
        source_commitment="b" * 64,
        integrity_label=label,
        visual_state=VPMVisualState.DRY_RUN,
        revocation_status=VPMRevocationStatus.ACTIVE,
        anchor_status=VPMAnchorStatus.NONE,
        lifecycle_status=VPMLifecycleStatus.RESERVED,
    )
    assert isinstance(manifest, VPMWrapperManifest)
    assert manifest.schema == VPM_WRAPPER_SCHEMA
    assert manifest.zkba_manifest_schema == ZKBA_WRAPPED_SCHEMA
    assert manifest.vpm_id == "QR-ELIGIBILITY-v1"
    assert manifest.proof_weight == ProofWeightClass.CHAIN_ONLY.value
    assert manifest.capture_mode == VPMCaptureMode.DRY_RUN.value
    assert manifest.visual_state == VPMVisualState.DRY_RUN.value
    assert manifest.wrapper_version == VPM_WRAPPER_VERSION
    # 9-field Integrity Label embedded
    assert manifest.integrity_label.proof_type == "ZKBA-GIC"
    assert manifest.integrity_label.raw_biometrics_exposed is False
    assert manifest.integrity_label.consent_active is True
    assert len(manifest.integrity_label.limitations) == 2


def test_t_vpm_4_integrity_label_nine_fields():
    """T-VPM-4: Integrity Label has all 9 required fields per B.5."""
    label = _make_integrity_label()
    # Slotted dataclass — introspect __slots__ for field set
    slots = set(VPMIntegrityLabel.__slots__)
    required = {
        "proof_type",
        "capture_mode",
        "raw_biometrics_exposed",
        "consent_active",
        "zk_verified",
        "on_chain_anchor",
        "proof_weight",
        "revocation_status",
        "limitations",
    }
    assert required.issubset(slots), f"missing: {required - slots}"
    assert len(required) == 9


def test_t_vpm_5_deterministic_byte_identity():
    """T-VPM-5: Same inputs → same wrapper commitment hash. Determinism
    discipline matches scripts/vsd_ui_compiler.canonical_json contract."""
    zkba = _make_zkba_manifest_dict()
    label = _make_integrity_label()

    def _build():
        return wrap_zkba_manifest(
            zkba_manifest_dict=zkba,
            vpm_id="DEV-SANDBOX-v1",
            audience="Developers",
            source_commitment="c" * 64,
            integrity_label=label,
            visual_state=VPMVisualState.DRY_RUN,
        )

    m1 = _build()
    m2 = _build()
    h1 = compute_vpm_commitment(m1)
    h2 = compute_vpm_commitment(m2)
    assert h1 == h2
    # And the canonical-json bytes are byte-identical
    assert vpm_canonical_json(m1) == vpm_canonical_json(m2)


def test_t_vpm_6_wrong_zkba_schema_rejected():
    """T-VPM-6: ZKBA manifest with wrong schema string raises ValueError."""
    zkba = _make_zkba_manifest_dict()
    zkba["schema"] = "vapi-zkba-manifest-v999"  # wrong schema
    label = _make_integrity_label()
    with pytest.raises(ValueError, match="vapi-zkba-manifest-v1"):
        wrap_zkba_manifest(
            zkba_manifest_dict=zkba,
            vpm_id="X",
            audience="y",
            source_commitment="d" * 64,
            integrity_label=label,
            visual_state=VPMVisualState.DRY_RUN,
        )


def test_t_vpm_7_missing_zkba_required_field_rejected():
    """T-VPM-7: ZKBA manifest missing required field raises ValueError."""
    zkba = _make_zkba_manifest_dict()
    del zkba["proof_weight"]
    label = _make_integrity_label()
    with pytest.raises(ValueError, match="missing required keys"):
        wrap_zkba_manifest(
            zkba_manifest_dict=zkba,
            vpm_id="X",
            audience="y",
            source_commitment="d" * 64,
            integrity_label=label,
            visual_state=VPMVisualState.DRY_RUN,
        )


def test_t_vpm_8_zkba_manifest_hash_cross_verifies():
    """T-VPM-8: zkba_manifest_hash field is the SHA-256 of canonical-JSON
    bytes of the wrapped ZKBA manifest dict. Verifier can chain
    wrapper → ZKBA without re-deriving."""
    zkba = _make_zkba_manifest_dict()
    label = _make_integrity_label()
    manifest = wrap_zkba_manifest(
        zkba_manifest_dict=zkba,
        vpm_id="HONESTY-BOARD-v1",
        audience="Ecosystem Partners",
        source_commitment="e" * 64,
        integrity_label=label,
        visual_state=VPMVisualState.DRY_RUN,
    )
    expected = hashlib.sha256(vpm_canonical_json(zkba)).hexdigest()
    assert manifest.zkba_manifest_hash == expected
    assert len(manifest.zkba_manifest_hash) == 64


def test_t_vpm_9_validate_happy_path_returns_no_errors():
    """T-VPM-9: A well-formed manifest returns empty error list from validator."""
    zkba = _make_zkba_manifest_dict()
    label = _make_integrity_label()
    manifest = wrap_zkba_manifest(
        zkba_manifest_dict=zkba,
        vpm_id="MARKET-LISTING-v1",
        audience="Buyers / Curator",
        source_commitment="f" * 64,
        integrity_label=label,
        visual_state=VPMVisualState.DRY_RUN,
    )
    errors = validate_vpm_manifest(manifest)
    assert errors == [], f"unexpected errors: {errors}"


def test_t_vpm_10_proof_weight_mismatch_caught_by_validator():
    """T-VPM-10: Wrapper proof_weight vs Integrity Label proof_weight
    mismatch surfaces in validator output (B.6 proof-weight omission
    extended to mirror-coherence)."""
    zkba = _make_zkba_manifest_dict(proof_weight=ProofWeightClass.CHAIN_ONLY.value)
    label = _make_integrity_label(proof_weight=ProofWeightClass.DIRECT_HID.value)
    # Build via wrap_zkba_manifest — proof_weight on wrapper sourced from zkba dict
    manifest = wrap_zkba_manifest(
        zkba_manifest_dict=zkba,
        vpm_id="X",
        audience="y",
        source_commitment="0" * 64,
        integrity_label=label,
        visual_state=VPMVisualState.DRY_RUN,
    )
    # wrapper.proof_weight=CHAIN_ONLY(3) vs label.proof_weight=DIRECT_HID(1)
    errors = validate_vpm_manifest(manifest)
    assert any("integrity_label.proof_weight" in e for e in errors), \
        f"expected proof_weight mismatch error; got {errors!r}"


# ===========================================================================
# G5c — Anti-Hype Visual Grammar tests (T-VPM-VG-1..12)
# ===========================================================================

def test_t_vpm_vg_1_visual_state_enum_is_closed_set():
    """T-VPM-VG-1: VPMVisualState is the FROZEN 6-element literal set per
    B.5. Adding values to the enum requires v2 manifest schema bump."""
    expected = {"live", "dry_run", "emulated", "frozen_disabled", "revoked", "unverified"}
    actual = {v.value for v in VPMVisualState}
    assert actual == expected, f"VPMVisualState drift: {actual - expected} / {expected - actual}"


def test_t_vpm_vg_2_capture_mode_enum_is_closed_set():
    """T-VPM-VG-2: VPMCaptureMode is FROZEN 5-element literal set per B.4."""
    expected = {"live", "dry-run", "emulated", "demo", "frozen-disabled"}
    actual = {v.value for v in VPMCaptureMode}
    assert actual == expected, f"VPMCaptureMode drift: {actual - expected} / {expected - actual}"


def test_t_vpm_vg_3_revocation_anchor_lifecycle_enums_closed():
    """T-VPM-VG-3: Revocation / anchor / lifecycle enums are FROZEN closed sets."""
    assert {v.value for v in VPMRevocationStatus} == {"active", "revoked", "expired"}
    assert {v.value for v in VPMAnchorStatus} == {"none", "pending", "anchored", "stale"}
    assert {v.value for v in VPMLifecycleStatus} == {
        "Reserved", "Draft Manifest", "Compiler Target", "Test Fixture", "Active"
    }


def test_t_vpm_vg_4_derive_revoked_consent_forces_redacted():
    """T-VPM-VG-4: B.6 revoked consent → visual_state=REVOKED regardless of
    capture_mode. Honesty grammar K9: revoked artifact may NOT render LIVE."""
    state = derive_visual_state(
        capture_mode=VPMCaptureMode.LIVE,
        revocation_status=VPMRevocationStatus.REVOKED,
        anchor_status=VPMAnchorStatus.ANCHORED,
    )
    assert state == VPMVisualState.REVOKED, \
        "revoked consent must override LIVE capture_mode"


def test_t_vpm_vg_5_derive_expired_consent_forces_redacted():
    """T-VPM-VG-5: Expired consent treated as REVOKED visual state."""
    state = derive_visual_state(
        capture_mode=VPMCaptureMode.LIVE,
        revocation_status=VPMRevocationStatus.EXPIRED,
        anchor_status=VPMAnchorStatus.ANCHORED,
    )
    assert state == VPMVisualState.REVOKED


def test_t_vpm_vg_6_derive_frozen_disabled_never_live():
    """T-VPM-VG-6: B.6 FROZEN_DISABLED capture_mode → visual_state=FROZEN_DISABLED.
    Never renders as LIVE under any code path."""
    state = derive_visual_state(
        capture_mode=VPMCaptureMode.FROZEN_DISABLED,
        revocation_status=VPMRevocationStatus.ACTIVE,
        anchor_status=VPMAnchorStatus.NONE,
    )
    assert state == VPMVisualState.FROZEN_DISABLED


def test_t_vpm_vg_7_derive_demo_capture_mode_forces_dry_run():
    """T-VPM-VG-7: B.6 DEMO capture_mode → visual_state=DRY_RUN. Demo
    artifacts must visibly indicate non-production state (15% pin per §6.5
    is renderer-side; protocol-side is DRY_RUN visual_state)."""
    state = derive_visual_state(
        capture_mode=VPMCaptureMode.DEMO,
        revocation_status=VPMRevocationStatus.ACTIVE,
        anchor_status=VPMAnchorStatus.NONE,
    )
    assert state == VPMVisualState.DRY_RUN, \
        "DEMO must render as DRY_RUN visual state to prevent overclaim"


def test_t_vpm_vg_8_derive_missing_manifest_unverified():
    """T-VPM-VG-8: B.6 missing manifest → visual_state=UNVERIFIED."""
    state = derive_visual_state(
        capture_mode=VPMCaptureMode.LIVE,
        revocation_status=VPMRevocationStatus.ACTIVE,
        anchor_status=VPMAnchorStatus.ANCHORED,
        zkba_manifest_present=False,
    )
    assert state == VPMVisualState.UNVERIFIED


def test_t_vpm_vg_9_derive_compiler_hash_mismatch_unverified():
    """T-VPM-VG-9: B.6 compiler hash mismatch → visual_state=UNVERIFIED.
    "verification-unavailable" — do not show 'verified' under any
    capture_mode."""
    state = derive_visual_state(
        capture_mode=VPMCaptureMode.LIVE,
        revocation_status=VPMRevocationStatus.ACTIVE,
        anchor_status=VPMAnchorStatus.ANCHORED,
        compiler_hash_mismatch=True,
    )
    assert state == VPMVisualState.UNVERIFIED


def test_t_vpm_vg_10_derive_stale_anchor_unverified():
    """T-VPM-VG-10: B.6 absent / stale anchor → visual_state=UNVERIFIED.
    Do not imply on-chain finality."""
    state = derive_visual_state(
        capture_mode=VPMCaptureMode.LIVE,
        revocation_status=VPMRevocationStatus.ACTIVE,
        anchor_status=VPMAnchorStatus.STALE,
    )
    assert state == VPMVisualState.UNVERIFIED


def test_t_vpm_vg_11_validator_blocks_overclaim_revoked_then_live():
    """T-VPM-VG-11: Validator catches an attempt to manually set
    revocation_status=REVOKED while keeping visual_state=LIVE. Honesty
    grammar K9 is enforced at validate_vpm_manifest, not only at
    derive_visual_state."""
    zkba = _make_zkba_manifest_dict()
    label = _make_integrity_label(revocation_status=VPMRevocationStatus.REVOKED.value)
    # Caller manually picks LIVE visual_state — overclaim attempt
    manifest = wrap_zkba_manifest(
        zkba_manifest_dict=zkba,
        vpm_id="X",
        audience="y",
        source_commitment="0" * 64,
        integrity_label=label,
        visual_state=VPMVisualState.LIVE,
        revocation_status=VPMRevocationStatus.REVOKED,
    )
    errors = validate_vpm_manifest(manifest)
    assert any("revoked consent must render visual_state" in e for e in errors), \
        f"validator must catch revoked-but-LIVE overclaim; got {errors!r}"


def test_t_vpm_vg_12_validator_blocks_zk_verified_false_with_on_chain_anchor():
    """T-VPM-VG-12: B.7 methodology violation — on_chain_anchor=True with
    zk_verified=False is structurally inconsistent. The label cannot claim
    on-chain finality without ZK verification.

    This is a CROSS-AGENT honesty rule, not just a single-field check —
    Integrity Label fields must be internally consistent before display.
    """
    zkba = _make_zkba_manifest_dict()
    label = _make_integrity_label(
        zk_verified=False,
        on_chain_anchor=True,  # inconsistent — claims on-chain without ZK
    )
    manifest = wrap_zkba_manifest(
        zkba_manifest_dict=zkba,
        vpm_id="X",
        audience="y",
        source_commitment="0" * 64,
        integrity_label=label,
        visual_state=VPMVisualState.DRY_RUN,
    )
    errors = validate_vpm_manifest(manifest)
    assert any("on_chain_anchor=True with zk_verified=False" in e for e in errors), \
        f"validator must catch on_chain_anchor+!zk_verified inconsistency; got {errors!r}"


# ---------------------------------------------------------------------------
# Static guards — module-level invariants (no PV-CI entry)
# ---------------------------------------------------------------------------

def test_t_vpm_static_no_forbidden_imports():
    """Track 1 invariant: vsd_vpm_wrapper imports no wall-clock / random /
    network modules. Same discipline as scripts/vsd_ui_compiler.py at G5b
    so the wrapper compiler step is byte-stable across platforms."""
    wrapper_path = Path(_SCRIPTS) / "vsd_vpm_wrapper.py"
    text = wrapper_path.read_text(encoding="utf-8")
    forbidden = [
        r"^\s*import\s+datetime\b",
        r"^\s*from\s+datetime\b",
        r"^\s*import\s+random\b",
        r"^\s*from\s+random\b",
        r"^\s*import\s+urllib\b",
        r"^\s*from\s+urllib\b",
        r"^\s*import\s+requests\b",
        r"^\s*from\s+requests\b",
        r"^\s*import\s+socket\b",
        r"^\s*from\s+socket\b",
        r"^\s*import\s+http\.client\b",
        r"^\s*from\s+http\.client\b",
    ]
    for pattern in forbidden:
        assert not re.search(pattern, text, re.MULTILINE), \
            f"forbidden import detected in vsd_vpm_wrapper.py: {pattern}"
    # `time` module is excluded structurally because the wrapper doesn't need
    # ts_ns — caller supplies via ZKBA manifest dict + Integrity Label
    assert not re.search(r"^\s*import\s+time\b", text, re.MULTILINE), \
        "wrapper must not import time (wall-clock forbidden)"


def test_t_vpm_static_wrapper_schema_string_pinned_in_source():
    """Static guard: the FROZEN literal `vapi-vpm-manifest-v1` is present
    in the source file. Mirrors INV-ZKBA-003 enforcement pattern at
    PV-CI level (but does NOT register as a PV-CI invariant per the
    namespace lock-in decided in reconciliation plan §4)."""
    wrapper_path = Path(_SCRIPTS) / "vsd_vpm_wrapper.py"
    text = wrapper_path.read_text(encoding="utf-8")
    assert '"vapi-vpm-manifest-v1"' in text, \
        "FROZEN VPM_WRAPPER_SCHEMA literal missing from source"
