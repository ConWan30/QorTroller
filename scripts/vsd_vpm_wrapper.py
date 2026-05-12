"""Phase O3-ZKBA-TRACK1 Lane B G5b — VPM Wrapper Manifest + Integrity Label.

Implements the `vapi-vpm-manifest-v1` wrapper schema specified by
VBDIP-0002 Appendix B (v1.1 amendment) §B.4. The wrapper composes over
the existing FROZEN `vapi-zkba-manifest-v1` ZKBA manifest schema
(scripts/vsd_ui_compiler.py:58) without replacing or modifying it —
wrapper references rather than supersedes.

Module shape mirrors scripts/vsd_ui_compiler.py:
  - same deterministic-compilation discipline (no wall-clock / random /
    network imports; sorted-key canonical JSON; no mutable web fonts)
  - same frozen-dataclass slotted Result types
  - same module-level FROZEN constants

V-check guarantees (statically enforced by G5c visual grammar tests):
  - VPM_WRAPPER_SCHEMA = "vapi-vpm-manifest-v1"             FROZEN at v1.0
  - VPM_WRAPPER_VERSION = "0.1.0"                            FROZEN at v1.0
  - VPMVisualState enum is a 6-element closed set:
      live / dry_run / emulated / frozen_disabled / revoked / unverified
  - VPMCaptureMode enum is a 5-element closed set:
      live / dry-run / emulated / demo / frozen-disabled
  - VPMLifecycleStatus enum is a 5-element closed set:
      Reserved / Draft Manifest / Compiler Target / Test Fixture / Active
  - VPMRevocationStatus enum is a 3-element closed set:
      active / revoked / expired
  - VPMAnchorStatus enum is a 4-element closed set:
      none / pending / anchored / stale
  - VPMProofType: free-form string at v1.0 (e.g. "ZKBA-GIC", "ZKBA-AIT",
    "ZKBA-VHP"); will close into enum at v1.1 once registry stabilizes.

VPM-HONESTY-001 is a METHODOLOGY-DOC identifier (VBDIP-0002 Appendix B
§B.5 + reconciliation plan §4). It is NOT a PV-CI invariant. The
enforcement of visual-honesty rules below is mechanical (validate_vpm_manifest)
but the identifier does NOT enter .github/INVARIANTS_ALLOWLIST.json and
does NOT enter scripts/vapi_invariant_gate.py. A future PV-CI invariant
covering visual-honesty enforcement would ship under existing native
naming (e.g. INV-VPM-VISUAL-001) per VEDIP-0001 documentation-alias
discipline.

This module is import-safe and side-effect-free at import time.

Author: VAPI Architect (bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
Date: 2026-05-12 (Phase O3-ZKBA-TRACK1 Lane B G5b)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

# Re-use the ZKBA primitive surface for cross-reference + import consistency.
_BRIDGE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "bridge"))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402


# ---------------------------------------------------------------------------
# FROZEN constants — pinned at v1.0; bump together with manifest v2
# ---------------------------------------------------------------------------

VPM_WRAPPER_SCHEMA = "vapi-vpm-manifest-v1"   # FROZEN; B.4 + B.5 honesty grammar pin
VPM_WRAPPER_VERSION = "0.1.0"                  # FROZEN at v1.0

# Cross-reference: the wrapper REFERENCES the FROZEN ZKBA manifest schema.
# Wrapper does not replace it.
ZKBA_WRAPPED_SCHEMA = "vapi-zkba-manifest-v1"  # FROZEN; from vsd_ui_compiler.py:58


# ---------------------------------------------------------------------------
# FROZEN enums — B.5 visual grammar + B.4 schema enums
# ---------------------------------------------------------------------------

class VPMVisualState(str, Enum):
    """B.5 visual-state literal set. FROZEN-v1 closed enum.

    Underlying string values match the visible-state vocabulary the
    rendering layer must consume. Renderer-side mapping is implementation
    detail (saturated colors for `live`, striped patterns for `dry_run`,
    etc.); this enum locks ONLY the protocol-side literal set.
    """
    LIVE             = "live"             # saturated colors
    DRY_RUN          = "dry_run"          # striped patterns
    EMULATED         = "emulated"         # desaturated / greyscale
    FROZEN_DISABLED  = "frozen_disabled"  # locked iconography
    REVOKED          = "revoked"          # crossed out / redacted
    UNVERIFIED       = "unverified"       # high-contrast warning bands


class VPMCaptureMode(str, Enum):
    """B.4 capture_mode field. FROZEN-v1 closed enum.

    Five-element set distinct from VPMVisualState — capture_mode answers
    "how was the underlying state produced" while visual_state answers
    "how must the projection display." They are coupled (see
    validate_vpm_manifest) but not equal.
    """
    LIVE             = "live"
    DRY_RUN          = "dry-run"           # note: hyphen, per B.4 schema
    EMULATED         = "emulated"
    DEMO             = "demo"
    FROZEN_DISABLED  = "frozen-disabled"   # note: hyphen, per B.4 schema


class VPMLifecycleStatus(str, Enum):
    """B.10 registry lifecycle ladder. FROZEN-v1 closed enum.

    Transition discipline (K13): Reserved → Draft Manifest → Compiler
    Target → Test Fixture → Active. Skipping a step requires
    governance authorization.
    """
    RESERVED         = "Reserved"
    DRAFT_MANIFEST   = "Draft Manifest"
    COMPILER_TARGET  = "Compiler Target"
    TEST_FIXTURE     = "Test Fixture"
    ACTIVE           = "Active"


class VPMRevocationStatus(str, Enum):
    """B.4 + B.6 revocation_status field. FROZEN-v1 closed enum."""
    ACTIVE   = "active"
    REVOKED  = "revoked"
    EXPIRED  = "expired"


class VPMAnchorStatus(str, Enum):
    """B.4 + B.6 anchor_status field. FROZEN-v1 closed enum.

    Track 1 invariant: `anchored` is forbidden until Track 2 anchoring
    ceremony lands on a real ZKBA artifact. `none` and `pending` are
    the only valid Track 1 values; `stale` applies post-anchor only.
    """
    NONE     = "none"
    PENDING  = "pending"
    ANCHORED = "anchored"
    STALE    = "stale"


# ---------------------------------------------------------------------------
# Integrity Label — B.5 nine-field block
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class VPMIntegrityLabel:
    """B.5 Integrity Nutrition Label. FROZEN-v1 nine-field shape.

    The label is the visible-honesty surface that accompanies every VPM
    artifact. Renderer-side display is implementation detail; this
    dataclass locks the protocol-side field set + types.

    The 9 fields (B.5 enumeration):
        1. proof_type              — e.g. "ZKBA-GIC", "ZKBA-AIT"
        2. capture_mode            — VPMCaptureMode literal
        3. raw_biometrics_exposed  — bool; MUST be False for any
                                      gamer-facing or marketplace VPM
        4. consent_active          — bool; False forces visual_state=REVOKED
                                      per B.6 failure-state rules
        5. zk_verified             — bool; False with on_chain_anchor=True
                                      is a methodology violation (B.6)
        6. on_chain_anchor         — bool; False forces anchor_status
                                      derivation to NONE or PENDING
        7. proof_weight            — ProofWeightClass IntEnum value;
                                      OMISSION → compilation failure (B.6)
        8. revocation_status       — VPMRevocationStatus literal
        9. limitations             — tuple of strings; explicit
                                      caller-side claim limits
    """
    proof_type:              str
    capture_mode:            str   # VPMCaptureMode value string
    raw_biometrics_exposed:  bool
    consent_active:          bool
    zk_verified:             bool
    on_chain_anchor:         bool
    proof_weight:            int   # ProofWeightClass IntEnum value
    revocation_status:       str   # VPMRevocationStatus value string
    limitations:             tuple = ()


# ---------------------------------------------------------------------------
# VPM Wrapper Manifest — B.4 schema
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class VPMWrapperManifest:
    """B.4 vapi-vpm-manifest-v1 wrapper schema. FROZEN-v1 shape.

    The wrapper references but does NOT replace `vapi-zkba-manifest-v1`.
    `zkba_manifest_hash` field carries the SHA-256 of the ZKBA manifest
    canonical-json bytes so verifiers can chain wrapper → ZKBA → primitive
    commitment without re-deriving the ZKBA commitment from scratch.
    """
    schema:                  str   # always VPM_WRAPPER_SCHEMA
    vpm_id:                  str   # registry identifier, e.g. "QR-ELIGIBILITY-v1"
    lifecycle_status:        str   # VPMLifecycleStatus value string
    audience:                str   # free-form at v1.0; e.g. "Tournament Organizers"
    source_commitment:       str   # SHA-256 hex of the canonical state source
    zkba_manifest_schema:    str   # always ZKBA_WRAPPED_SCHEMA (cross-reference)
    zkba_manifest_hash:      str   # SHA-256 hex of wrapped ZKBA manifest bytes
    proof_weight:            int   # ProofWeightClass IntEnum value (mirrors label)
    capture_mode:            str   # VPMCaptureMode value string (mirrors label)
    visual_state:            str   # VPMVisualState value string (derived; see below)
    integrity_label:         VPMIntegrityLabel
    wrapper_version:         str   # VPM_WRAPPER_VERSION
    anchor_status:           str   # VPMAnchorStatus value string
    revocation_status:       str   # VPMRevocationStatus value string (mirrors label)
    limitations:             tuple = ()


# ---------------------------------------------------------------------------
# Helpers — canonical bytes + commitment
# ---------------------------------------------------------------------------

def vpm_canonical_json(obj) -> bytes:
    """Sorted-key UTF-8 JSON for deterministic byte output. Matches
    scripts/vsd_ui_compiler.canonical_json verbatim — same serializer
    discipline so the wrapper hash is computed identically on every
    platform."""
    if hasattr(obj, "__dataclass_fields__"):
        obj = _asdict_recursive(obj)
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _asdict_recursive(obj):
    """Convert nested dataclasses + tuples + Enums to JSON-serialisable
    primitives. Preserves canonical-JSON determinism end-to-end."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _asdict_recursive(v) for k, v in asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_asdict_recursive(v) for v in obj]
    if isinstance(obj, Enum):
        return obj.value
    return obj


def compute_vpm_commitment(manifest: VPMWrapperManifest) -> str:
    """SHA-256 hex of canonical-json(manifest). Deterministic byte
    identity for the wrapper artifact (parallels compute_zkba_commitment
    discipline at scripts/vsd_ui_compiler.py:97)."""
    return hashlib.sha256(vpm_canonical_json(manifest)).hexdigest()


# ---------------------------------------------------------------------------
# wrap_zkba_manifest — public API for G5b
# ---------------------------------------------------------------------------

def wrap_zkba_manifest(
    *,
    zkba_manifest_dict: dict,
    vpm_id: str,
    audience: str,
    source_commitment: str,
    integrity_label: VPMIntegrityLabel,
    visual_state: VPMVisualState,
    anchor_status: VPMAnchorStatus = VPMAnchorStatus.NONE,
    revocation_status: VPMRevocationStatus = VPMRevocationStatus.ACTIVE,
    lifecycle_status: VPMLifecycleStatus = VPMLifecycleStatus.RESERVED,
    limitations: tuple = (),
) -> VPMWrapperManifest:
    """Wrap an existing ZKBA manifest dict into a VPM wrapper manifest.

    The ZKBA manifest is hashed (canonical-json SHA-256) and the hash
    embedded as `zkba_manifest_hash`. The wrapper does not modify the
    ZKBA manifest itself — the underlying FROZEN `vapi-zkba-manifest-v1`
    contract holds.

    Args:
        zkba_manifest_dict: A dict that conforms to
            `vapi-zkba-manifest-v1` (i.e. an asdict(ZKBAManifest)).
            MUST contain `schema`, `zkba_class`, `proof_weight`,
            `output_hash_hex` for the wrapper to be coherent.
        vpm_id: Registry identifier per VBDIP-0002A §10.
        audience: Free-form audience string (gamers / developers /
            tournament organizers / etc.).
        source_commitment: SHA-256 hex of canonical state source.
        integrity_label: 9-field Integrity Label per B.5.
        visual_state: VPMVisualState enum literal. Caller derives this
            from honesty rules OR uses derive_visual_state() below.
        anchor_status: VPMAnchorStatus literal. Defaults to NONE per
            Track 1 invariant (anchored is forbidden pre-Track-2).
        revocation_status: VPMRevocationStatus literal. Default ACTIVE.
        lifecycle_status: Default Reserved per K13 registry discipline.
        limitations: tuple of caller-supplied limit strings.

    Returns:
        VPMWrapperManifest. Caller may serialize via vpm_canonical_json()
        for SHA-256 commitment.

    Raises:
        ValueError if zkba_manifest_dict lacks required fields OR has
        an unrecognised schema string. Failure-state rules per B.6 are
        enforced separately via validate_vpm_manifest().
    """
    if not isinstance(zkba_manifest_dict, dict):
        raise ValueError("zkba_manifest_dict must be dict")
    schema = zkba_manifest_dict.get("schema")
    if schema != ZKBA_WRAPPED_SCHEMA:
        raise ValueError(
            f"wrap_zkba_manifest expects schema={ZKBA_WRAPPED_SCHEMA!r}, "
            f"got {schema!r}"
        )
    required = ("zkba_class", "proof_weight", "output_hash_hex")
    missing = [k for k in required if k not in zkba_manifest_dict]
    if missing:
        raise ValueError(f"zkba_manifest_dict missing required keys: {missing}")

    zkba_manifest_bytes = vpm_canonical_json(zkba_manifest_dict)
    zkba_hash = hashlib.sha256(zkba_manifest_bytes).hexdigest()

    return VPMWrapperManifest(
        schema=VPM_WRAPPER_SCHEMA,
        vpm_id=str(vpm_id),
        lifecycle_status=lifecycle_status.value,
        audience=str(audience),
        source_commitment=str(source_commitment),
        zkba_manifest_schema=ZKBA_WRAPPED_SCHEMA,
        zkba_manifest_hash=zkba_hash,
        proof_weight=int(zkba_manifest_dict["proof_weight"]),
        capture_mode=integrity_label.capture_mode,
        visual_state=visual_state.value,
        integrity_label=integrity_label,
        wrapper_version=VPM_WRAPPER_VERSION,
        anchor_status=anchor_status.value,
        revocation_status=revocation_status.value,
        limitations=tuple(limitations),
    )


# ---------------------------------------------------------------------------
# derive_visual_state — B.6 failure-state rule engine (compile-time precedence)
# ---------------------------------------------------------------------------

def derive_visual_state(
    *,
    capture_mode: VPMCaptureMode,
    revocation_status: VPMRevocationStatus,
    anchor_status: VPMAnchorStatus,
    zkba_manifest_present: bool = True,
    verification_key_stale: bool = False,
    compiler_hash_mismatch: bool = False,
) -> VPMVisualState:
    """B.6 failure-state precedence resolver.

    Precedence order (highest → lowest; first match wins):

      1. compiler_hash_mismatch     → UNVERIFIED ("verification-unavailable")
      2. zkba_manifest_present=False → UNVERIFIED ("missing manifest")
      3. revocation_status=REVOKED  → REVOKED
      4. revocation_status=EXPIRED  → REVOKED
      5. capture_mode=FROZEN_DISABLED → FROZEN_DISABLED
      6. capture_mode=DEMO           → DRY_RUN (visible demo watermark
                                        handled at render layer via demo
                                        watermark; protocol-side state
                                        is DRY_RUN to prevent overclaim)
      7. capture_mode=EMULATED       → EMULATED
      8. capture_mode=DRY_RUN        → DRY_RUN
      9. verification_key_stale=True → UNVERIFIED ("warning")
     10. anchor_status=STALE         → UNVERIFIED
     11. capture_mode=LIVE           → LIVE

    The precedence order encodes K9 (Anti-Hype Visual Grammar): a
    revoked or unverified artifact MAY NOT render as LIVE even if
    capture_mode says LIVE. Caller cannot bypass by setting capture_mode
    independently.
    """
    if compiler_hash_mismatch:
        return VPMVisualState.UNVERIFIED
    if not zkba_manifest_present:
        return VPMVisualState.UNVERIFIED
    if revocation_status == VPMRevocationStatus.REVOKED:
        return VPMVisualState.REVOKED
    if revocation_status == VPMRevocationStatus.EXPIRED:
        return VPMVisualState.REVOKED
    if capture_mode == VPMCaptureMode.FROZEN_DISABLED:
        return VPMVisualState.FROZEN_DISABLED
    if capture_mode == VPMCaptureMode.DEMO:
        return VPMVisualState.DRY_RUN
    if capture_mode == VPMCaptureMode.EMULATED:
        return VPMVisualState.EMULATED
    if capture_mode == VPMCaptureMode.DRY_RUN:
        return VPMVisualState.DRY_RUN
    if verification_key_stale:
        return VPMVisualState.UNVERIFIED
    if anchor_status == VPMAnchorStatus.STALE:
        return VPMVisualState.UNVERIFIED
    # capture_mode=LIVE + no failure conditions
    return VPMVisualState.LIVE


# ---------------------------------------------------------------------------
# validate_vpm_manifest — B.6 failure-state enforcement at compile time
# ---------------------------------------------------------------------------

def validate_vpm_manifest(manifest: VPMWrapperManifest) -> list[str]:
    """B.6 failure-state rules + B.4 schema coherence enforcement.

    Returns a list of human-readable error strings. Empty list means the
    manifest is coherent and may be emitted. Non-empty list means the
    compiler MUST refuse emission (proof-weight omission case in B.6:
    "fail compilation; no VPM artifact is emitted").

    This function does not raise — it returns the error list so callers
    can decide whether to refuse, downgrade, or surface.
    """
    errors: list[str] = []

    # B.4 schema field — must be FROZEN literal
    if manifest.schema != VPM_WRAPPER_SCHEMA:
        errors.append(
            f"schema must be {VPM_WRAPPER_SCHEMA!r}; got {manifest.schema!r}"
        )

    # B.4 wrapped-schema cross-reference must be FROZEN ZKBA literal
    if manifest.zkba_manifest_schema != ZKBA_WRAPPED_SCHEMA:
        errors.append(
            f"zkba_manifest_schema must be {ZKBA_WRAPPED_SCHEMA!r}; "
            f"got {manifest.zkba_manifest_schema!r}"
        )

    # B.6 proof-weight omission — wrapper-level
    valid_pw = {pw.value for pw in ProofWeightClass}
    if manifest.proof_weight not in valid_pw:
        errors.append(
            f"proof_weight omitted or invalid; got {manifest.proof_weight!r}; "
            f"valid values: {sorted(valid_pw)}"
        )

    # B.6 proof-weight omission — Integrity Label mirror must match wrapper
    if manifest.integrity_label.proof_weight != manifest.proof_weight:
        errors.append(
            f"integrity_label.proof_weight {manifest.integrity_label.proof_weight!r} "
            f"!= wrapper.proof_weight {manifest.proof_weight!r}"
        )

    # B.4 capture_mode literal must be in FROZEN enum
    valid_capture = {cm.value for cm in VPMCaptureMode}
    if manifest.capture_mode not in valid_capture:
        errors.append(
            f"capture_mode {manifest.capture_mode!r} not in {sorted(valid_capture)}"
        )
    if manifest.integrity_label.capture_mode != manifest.capture_mode:
        errors.append(
            f"integrity_label.capture_mode {manifest.integrity_label.capture_mode!r} "
            f"!= wrapper.capture_mode {manifest.capture_mode!r}"
        )

    # B.5 visual_state literal must be in FROZEN enum
    valid_visual = {vs.value for vs in VPMVisualState}
    if manifest.visual_state not in valid_visual:
        errors.append(
            f"visual_state {manifest.visual_state!r} not in {sorted(valid_visual)}"
        )

    # B.5 revocation_status literal must be in FROZEN enum
    valid_revoc = {rs.value for rs in VPMRevocationStatus}
    if manifest.revocation_status not in valid_revoc:
        errors.append(
            f"revocation_status {manifest.revocation_status!r} not in {sorted(valid_revoc)}"
        )
    if manifest.integrity_label.revocation_status != manifest.revocation_status:
        errors.append(
            f"integrity_label.revocation_status {manifest.integrity_label.revocation_status!r} "
            f"!= wrapper.revocation_status {manifest.revocation_status!r}"
        )

    # B.5 anchor_status literal must be in FROZEN enum
    valid_anchor = {ans.value for ans in VPMAnchorStatus}
    if manifest.anchor_status not in valid_anchor:
        errors.append(
            f"anchor_status {manifest.anchor_status!r} not in {sorted(valid_anchor)}"
        )

    # B.5 lifecycle_status literal must be in FROZEN enum
    valid_lifecycle = {ls.value for ls in VPMLifecycleStatus}
    if manifest.lifecycle_status not in valid_lifecycle:
        errors.append(
            f"lifecycle_status {manifest.lifecycle_status!r} not in {sorted(valid_lifecycle)}"
        )

    # B.6 revoked consent → forces REVOKED visual state (no LIVE override)
    if manifest.revocation_status == VPMRevocationStatus.REVOKED.value:
        if manifest.visual_state != VPMVisualState.REVOKED.value:
            errors.append(
                f"revoked consent must render visual_state="
                f"{VPMVisualState.REVOKED.value!r}; got {manifest.visual_state!r}"
            )

    # B.6 FROZEN_DISABLED never renders as LIVE
    if manifest.capture_mode == VPMCaptureMode.FROZEN_DISABLED.value:
        if manifest.visual_state == VPMVisualState.LIVE.value:
            errors.append(
                "FROZEN_DISABLED capture_mode may not render as LIVE visual_state"
            )

    # B.6 DEMO capture_mode never renders as LIVE
    if manifest.capture_mode == VPMCaptureMode.DEMO.value:
        if manifest.visual_state == VPMVisualState.LIVE.value:
            errors.append(
                "DEMO capture_mode may not render as LIVE visual_state "
                "(must include demo watermark / DRY_RUN visual state)"
            )

    # Cross-reference: zk_verified=False + on_chain_anchor=True is a
    # methodology violation (B.7 AI Role Constraint: "alter proof weight"
    # equivalent at honesty layer). The label cannot claim on-chain finality
    # without ZK verification.
    if (
        not manifest.integrity_label.zk_verified
        and manifest.integrity_label.on_chain_anchor
    ):
        errors.append(
            "integrity_label inconsistent: on_chain_anchor=True with "
            "zk_verified=False is a methodology violation (B.7)"
        )

    # Track 1 invariant: anchor_status=ANCHORED is forbidden until Track 2
    # ceremony lands. This is a soft-rule warning (NOT a compile error) at
    # the protocol-side layer; the bridge endpoints surface
    # track1_invariant_holds separately for the same gate.
    # We intentionally do NOT add an error here — the surface check is
    # bridge-side; the wrapper validator is artifact-layer.

    # zkba_manifest_hash must be 64-char lowercase hex
    h = manifest.zkba_manifest_hash
    if not (isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h)):
        errors.append(
            f"zkba_manifest_hash must be 64-char lowercase hex; got {h!r}"
        )

    return errors


# ---------------------------------------------------------------------------
# Module exit barrier — re-export the FROZEN constants for test introspection
# ---------------------------------------------------------------------------

__all__ = [
    "VPM_WRAPPER_SCHEMA",
    "VPM_WRAPPER_VERSION",
    "ZKBA_WRAPPED_SCHEMA",
    "VPMVisualState",
    "VPMCaptureMode",
    "VPMLifecycleStatus",
    "VPMRevocationStatus",
    "VPMAnchorStatus",
    "VPMIntegrityLabel",
    "VPMWrapperManifest",
    "vpm_canonical_json",
    "compute_vpm_commitment",
    "wrap_zkba_manifest",
    "derive_visual_state",
    "validate_vpm_manifest",
]
