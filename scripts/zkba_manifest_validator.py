"""Phase O3-ZKBA-TRACK1 Lane B G4 — ZKBA manifest schema validator.

VBDIP-0002 §16 G4 gate text:

    ZKBA Manifest Schema Validated - Schema `zkba.projection_manifest.v1`
    validates all required artifact layers and proof-weight fields against
    representative artifacts of all seven Section 5 classes.

This module ships the validator. It targets the manifest shape emitted by
`scripts/vsd_ui_compiler.py:compile_artifact` (the 8-field FROZEN
ZKBAManifest dataclass at v1.0).

V-CHECK FINDING DOCUMENTED:

  §9.2 spec design-time schema name:    `zkba.projection_manifest.v1`
  Implementation FROZEN schema name:    `vapi-zkba-manifest-v1`
                                        (PV-CI INV-ZKBA-003 pin in
                                         scripts/vapi_invariant_gate.py)

  These two names diverged at C3 (commit `3b3081d3`) when the
  vsd_ui_compiler.py implementation chose `vapi-zkba-manifest-v1` for
  the schema literal. INV-ZKBA-003 then froze the implementation name
  at allowlist regeneration time (commit `0791c935` C5).

  The validator below accepts BOTH names. PV-CI takes precedence in
  practice — any future re-emission MUST use `vapi-zkba-manifest-v1`
  to satisfy INV-ZKBA-003 — but legacy or third-party manifests
  emitted under the spec name `zkba.projection_manifest.v1` are also
  recognized so cross-document references remain interpretable.

  Reconciliation of the schema-name drift is operator-decision work,
  scoped as a future VBDIP-0002 v1.x amendment. This validator does
  NOT force the resolution; it surfaces the drift via the
  `schema_name_form` field of the result.

VALIDATOR SCOPE (B.8 G4):
  - Accepts a dict (typically from json.loads of a .manifest.json file)
  - Verifies required field set
  - Verifies field types
  - Verifies schema string matches one of the two known names
  - Verifies zkba_class is a valid ZKBAClass enum value (1..7)
  - Verifies proof_weight is a valid ProofWeightClass enum value (1..6)
  - Verifies hashes are 64-char lowercase hex
  - Verifies ts_ns is a uint64
  - Returns ManifestValidationResult; never raises

This validator is import-safe + side-effect-free. It is wallet-free and
authority-neutral; it reads dicts and returns error lists. No chain
access, no Cedar evaluation, no operator-agent draft emission.

Author: VAPI Architect (bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
Date: 2026-05-12 (Phase O3-ZKBA-TRACK1 Lane B G4)
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Optional

# Add bridge/ to sys.path so we can import the ZKBA primitive's enums.
_BRIDGE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "bridge"))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402


# ---------------------------------------------------------------------------
# FROZEN schema names — two recognized forms (drift documented in module doc)
# ---------------------------------------------------------------------------

IMPLEMENTATION_SCHEMA_NAME = "vapi-zkba-manifest-v1"        # INV-ZKBA-003 pin
SPEC_DESIGN_TIME_SCHEMA_NAME = "zkba.projection_manifest.v1"  # §9.2 text

ACCEPTED_SCHEMA_NAMES = frozenset({
    IMPLEMENTATION_SCHEMA_NAME,
    SPEC_DESIGN_TIME_SCHEMA_NAME,
})


# ---------------------------------------------------------------------------
# Required field set for the simple (implementation) manifest form
# ---------------------------------------------------------------------------

# The FROZEN ZKBAManifest dataclass at scripts/vsd_ui_compiler.py:62-76 has
# exactly these 8 fields. The validator pins this set as the minimum-required
# field set; richer manifests (per §9.2 design-time intent) MAY include
# additional fields, but MUST include these 8 at minimum.
REQUIRED_FIELDS = frozenset({
    "schema",
    "zkba_class",
    "proof_weight",
    "output_path",
    "output_hash_hex",
    "input_commitment_hex",
    "compiler_version",
    "ts_ns",
})


# ---------------------------------------------------------------------------
# Result dataclass — fail-open contract; never raises
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ManifestValidationResult:
    """Result of validate_zkba_manifest. Slotted + frozen for determinism.

    Attributes:
        valid:             True iff `errors` is empty.
        errors:            List of human-readable error strings.
        zkba_class_name:   String form of zkba_class enum value when present,
                           else "". Useful for log lines.
        proof_weight_name: Same for proof_weight.
        schema_name_form:  One of "implementation" / "spec_design_time" /
                           "unknown" / "absent". Surfaces the schema-name
                           drift documented in module doc.
    """
    valid:             bool
    errors:            tuple
    zkba_class_name:   str = ""
    proof_weight_name: str = ""
    schema_name_form:  str = "unknown"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_lowercase_hex(s, length: Optional[int] = None) -> bool:
    """True iff s is a string of lowercase hex digits; optional exact length."""
    if not isinstance(s, str):
        return False
    if length is not None and len(s) != length:
        return False
    return all(c in "0123456789abcdef" for c in s)


def _classify_schema_name(name) -> str:
    """Returns one of: 'implementation' / 'spec_design_time' / 'unknown' /
    'absent'."""
    if name is None:
        return "absent"
    if not isinstance(name, str):
        return "unknown"
    if name == IMPLEMENTATION_SCHEMA_NAME:
        return "implementation"
    if name == SPEC_DESIGN_TIME_SCHEMA_NAME:
        return "spec_design_time"
    return "unknown"


def _validate_enum_int(
    value, enum_cls, errors: list, field_name: str,
) -> Optional[int]:
    """Verify value is an integer in the enum_cls range. Returns the int on
    success or None on failure (errors list mutated)."""
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(
            f"{field_name} must be int; got {type(value).__name__}"
        )
        return None
    valid_values = {m.value for m in enum_cls}
    if value not in valid_values:
        errors.append(
            f"{field_name}={value!r} not in {enum_cls.__name__} "
            f"valid values {sorted(valid_values)}"
        )
        return None
    return value


# ---------------------------------------------------------------------------
# Main entry — validate_zkba_manifest
# ---------------------------------------------------------------------------

def validate_zkba_manifest(manifest: dict) -> ManifestValidationResult:
    """Validate a ZKBA projection manifest dict against B.8 G4 rules.

    Args:
        manifest: dict parsed from the .manifest.json file emitted by
            scripts/vsd_ui_compiler.compile_artifact (the 8-field FROZEN
            ZKBAManifest). May contain additional fields for the §9.2
            design-time richer shape; they are not validated by this v1
            validator (forward-compat handling lives at the v1.x
            amendment that resolves the schema-name drift).

    Returns:
        ManifestValidationResult with valid=True (empty errors) on
        coherent manifests, valid=False (populated errors) on
        malformed manifests. Never raises.
    """
    errors: list = []

    if not isinstance(manifest, dict):
        return ManifestValidationResult(
            valid=False,
            errors=(f"manifest must be dict; got {type(manifest).__name__}",),
            schema_name_form="absent",
        )

    # Required field presence
    missing = REQUIRED_FIELDS - set(manifest.keys())
    if missing:
        errors.append(f"missing required fields: {sorted(missing)}")

    # Schema name validation
    schema_form = _classify_schema_name(manifest.get("schema"))
    if schema_form == "unknown":
        errors.append(
            f"schema={manifest.get('schema')!r} not in accepted names "
            f"{sorted(ACCEPTED_SCHEMA_NAMES)}"
        )
    elif schema_form == "absent":
        # already caught by missing-fields check above; only add if not
        # already present
        if "schema" in REQUIRED_FIELDS and "schema" in manifest.keys():
            errors.append("schema field is None / not a string")
        # else: missing-fields error already added

    # zkba_class — int in ZKBAClass enum
    zkba_class_int = _validate_enum_int(
        manifest.get("zkba_class"), ZKBAClass, errors, "zkba_class",
    )
    zkba_class_name = ZKBAClass(zkba_class_int).name if zkba_class_int is not None else ""

    # proof_weight — int in ProofWeightClass enum
    proof_weight_int = _validate_enum_int(
        manifest.get("proof_weight"), ProofWeightClass, errors, "proof_weight",
    )
    proof_weight_name = ProofWeightClass(proof_weight_int).name if proof_weight_int is not None else ""

    # output_path — non-empty string
    output_path = manifest.get("output_path")
    if output_path is not None:
        if not isinstance(output_path, str) or not output_path:
            errors.append(
                f"output_path must be non-empty string; got {output_path!r}"
            )

    # output_hash_hex — 64-char lowercase hex
    if not _is_lowercase_hex(manifest.get("output_hash_hex"), length=64):
        errors.append(
            f"output_hash_hex must be 64-char lowercase hex; "
            f"got {manifest.get('output_hash_hex')!r}"
        )

    # input_commitment_hex — 64-char lowercase hex
    if not _is_lowercase_hex(manifest.get("input_commitment_hex"), length=64):
        errors.append(
            f"input_commitment_hex must be 64-char lowercase hex; "
            f"got {manifest.get('input_commitment_hex')!r}"
        )

    # compiler_version — non-empty string
    cv = manifest.get("compiler_version")
    if cv is not None and (not isinstance(cv, str) or not cv):
        errors.append(
            f"compiler_version must be non-empty string; got {cv!r}"
        )

    # ts_ns — uint64
    ts_ns = manifest.get("ts_ns")
    if ts_ns is not None:
        if not isinstance(ts_ns, int) or isinstance(ts_ns, bool):
            errors.append(
                f"ts_ns must be int; got {type(ts_ns).__name__}"
            )
        elif ts_ns < 0 or ts_ns > 0xFFFFFFFFFFFFFFFF:
            errors.append(
                f"ts_ns must be uint64 (0..2^64-1); got {ts_ns!r}"
            )

    return ManifestValidationResult(
        valid=len(errors) == 0,
        errors=tuple(errors),
        zkba_class_name=zkba_class_name,
        proof_weight_name=proof_weight_name,
        schema_name_form=schema_form,
    )


# ---------------------------------------------------------------------------
# build_representative_manifest — test-fixture helper for B.8 G4 7-class
# coverage requirement
# ---------------------------------------------------------------------------

# Per VBDIP-0002 §5 + §6, each ZKBA class has a recommended default
# proof_weight at v1.0. The validator MUST accept all 7 classes at their
# default proof weights. The mapping below pins those defaults for
# representative manifest construction.
#
# DEFAULTS:
#   AIT        → CALIBRATION_PLUS_CONTEXT (AIT separation snapshot;
#                                          chain-anchored via BIOMETRIC-SNAPSHOT-v1)
#   GIC        → CHAIN_ONLY               (chain head; no fresh capture)
#   VHP        → CHAIN_ONLY               (VHP token state is on-chain)
#   HARDWARE   → CHAIN_ONLY               (hardware cert is on-chain)
#   CONSENT    → CHAIN_ONLY               (consent state via on-chain registry)
#   TOURNAMENT → CHAIN_ONLY               (composite: VHP + isFullyEligible)
#   MARKET     → MARKETPLACE_DERIVED      (listing-derived attestation)

DEFAULT_PROOF_WEIGHT_BY_CLASS = {
    ZKBAClass.AIT:        ProofWeightClass.CALIBRATION_PLUS_CONTEXT,
    ZKBAClass.GIC:        ProofWeightClass.CHAIN_ONLY,
    ZKBAClass.VHP:        ProofWeightClass.CHAIN_ONLY,
    ZKBAClass.HARDWARE:   ProofWeightClass.CHAIN_ONLY,
    ZKBAClass.CONSENT:    ProofWeightClass.CHAIN_ONLY,
    ZKBAClass.TOURNAMENT: ProofWeightClass.CHAIN_ONLY,
    ZKBAClass.MARKET:     ProofWeightClass.MARKETPLACE_DERIVED,
}


def build_representative_manifest(
    *,
    zkba_class: ZKBAClass,
    proof_weight: Optional[ProofWeightClass] = None,
    output_hash_hex: Optional[str] = None,
    input_commitment_hex: Optional[str] = None,
    ts_ns: int = 1778000000000000000,
    schema_name: str = IMPLEMENTATION_SCHEMA_NAME,
) -> dict:
    """Construct a synthetic representative manifest for a given ZKBA class.

    Useful as a test fixture: produces a manifest dict that
    validate_zkba_manifest() accepts. Caller may then mutate one field
    to verify the validator catches the specific malformation.

    Default proof_weight comes from DEFAULT_PROOF_WEIGHT_BY_CLASS table.
    Hash defaults are deterministic per zkba_class (so the same class
    always produces the same fixture)."""
    pw = proof_weight if proof_weight is not None else DEFAULT_PROOF_WEIGHT_BY_CLASS[zkba_class]
    # Deterministic fixture hashes per class — different classes produce
    # different hashes so tests can't accidentally pass on hash-equality
    class_seed = int(zkba_class)
    output_hash = output_hash_hex if output_hash_hex is not None else f"{class_seed:064x}"
    input_commit = input_commitment_hex if input_commitment_hex is not None else f"{class_seed + 100:064x}"
    return {
        "schema":               schema_name,
        "zkba_class":           int(zkba_class),
        "proof_weight":         int(pw),
        "output_path":          f"frontend/src/artifacts/zkba_class_{class_seed}/{input_commit}.html",
        "output_hash_hex":      output_hash,
        "input_commitment_hex": input_commit,
        "compiler_version":     "0.1.0",
        "ts_ns":                int(ts_ns),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "IMPLEMENTATION_SCHEMA_NAME",
    "SPEC_DESIGN_TIME_SCHEMA_NAME",
    "ACCEPTED_SCHEMA_NAMES",
    "REQUIRED_FIELDS",
    "DEFAULT_PROOF_WEIGHT_BY_CLASS",
    "ManifestValidationResult",
    "validate_zkba_manifest",
    "build_representative_manifest",
]
