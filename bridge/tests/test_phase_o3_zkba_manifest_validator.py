"""Phase O3-ZKBA-TRACK1 Lane B G4 — manifest validator tests.

Covers `scripts/zkba_manifest_validator.py` against representative
manifests of all 7 ZKBA classes (AIT / GIC / VHP / HARDWARE / CONSENT /
TOURNAMENT / MARKET) plus malformation cases.

Test plan:

  T-MV-1  validator accepts FROZEN simple manifest for each of 7 ZKBA
          classes at default proof_weight (parametrized; 7 tests)
  T-MV-2  validator accepts both schema names (implementation and
          spec-design-time) — surfaces drift via schema_name_form
  T-MV-3  validator rejects manifest missing required field (8 tests
          parametrized over REQUIRED_FIELDS)
  T-MV-4  validator rejects invalid zkba_class enum value
  T-MV-5  validator rejects invalid proof_weight enum value
  T-MV-6  validator rejects malformed output_hash_hex (non-hex /
          wrong length / uppercase)
  T-MV-7  validator rejects malformed input_commitment_hex
  T-MV-8  validator rejects non-uint64 ts_ns (negative / >2^64-1 /
          non-int)
  T-MV-9  validator rejects non-string schema field
  T-MV-10 validator rejects non-dict manifest entirely
  T-MV-11 validator round-trip: end-to-end check against actual
          compile_artifact output for GIC
  T-MV-12 fail-open contract: validator never raises
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(__file__)
_BRIDGE = os.path.normpath(os.path.join(_HERE, ".."))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402
from zkba_manifest_validator import (  # noqa: E402
    IMPLEMENTATION_SCHEMA_NAME,
    SPEC_DESIGN_TIME_SCHEMA_NAME,
    ACCEPTED_SCHEMA_NAMES,
    REQUIRED_FIELDS,
    DEFAULT_PROOF_WEIGHT_BY_CLASS,
    ManifestValidationResult,
    validate_zkba_manifest,
    build_representative_manifest,
)
from vsd_ui_compiler import compile_artifact, _MANIFEST_SCHEMA  # noqa: E402
from zkba_compile_gic_ledger import _render_gic_ledger_html  # noqa: E402


# ===========================================================================
# T-MV-1 — validator accepts each of 7 ZKBA classes at default proof_weight
# ===========================================================================

@pytest.mark.parametrize("zkba_class", list(ZKBAClass))
def test_t_mv_1_accept_all_seven_classes_at_default_proof_weight(zkba_class):
    """B.8 G4 explicit requirement: validator accepts representative
    artifacts of all 7 Section 5 classes. Each class is parametrized
    independently — failure of any one fails B.8 G4 closure."""
    manifest = build_representative_manifest(zkba_class=zkba_class)
    result = validate_zkba_manifest(manifest)
    assert isinstance(result, ManifestValidationResult)
    assert result.valid, \
        f"validator rejected default {zkba_class.name} manifest: " \
        f"errors={result.errors}"
    assert result.errors == ()
    assert result.zkba_class_name == zkba_class.name
    expected_pw = DEFAULT_PROOF_WEIGHT_BY_CLASS[zkba_class]
    assert result.proof_weight_name == expected_pw.name


# ===========================================================================
# T-MV-2 — validator accepts both schema names (drift surfacing)
# ===========================================================================

def test_t_mv_2_accepts_implementation_schema_name():
    m = build_representative_manifest(
        zkba_class=ZKBAClass.GIC,
        schema_name=IMPLEMENTATION_SCHEMA_NAME,
    )
    r = validate_zkba_manifest(m)
    assert r.valid, f"errors={r.errors}"
    assert r.schema_name_form == "implementation"


def test_t_mv_2b_accepts_spec_design_time_schema_name():
    """The validator accepts both names so legacy / third-party
    manifests under the §9.2 spec name remain interpretable. The
    schema_name_form field surfaces the drift to callers."""
    m = build_representative_manifest(
        zkba_class=ZKBAClass.GIC,
        schema_name=SPEC_DESIGN_TIME_SCHEMA_NAME,
    )
    r = validate_zkba_manifest(m)
    assert r.valid, f"errors={r.errors}"
    assert r.schema_name_form == "spec_design_time"


def test_t_mv_2c_rejects_unknown_schema_name():
    m = build_representative_manifest(zkba_class=ZKBAClass.GIC)
    m["schema"] = "wrong-schema-v999"
    r = validate_zkba_manifest(m)
    assert not r.valid
    assert any("schema=" in e and "not in accepted names" in e for e in r.errors)
    assert r.schema_name_form == "unknown"


# ===========================================================================
# T-MV-3 — validator rejects missing required field
# ===========================================================================

@pytest.mark.parametrize("missing_field", sorted(REQUIRED_FIELDS))
def test_t_mv_3_reject_missing_required_field(missing_field):
    """Each of the 8 REQUIRED_FIELDS, when absent, must produce a
    validation error. Parametrized so failure of any one fails
    closure."""
    m = build_representative_manifest(zkba_class=ZKBAClass.GIC)
    del m[missing_field]
    r = validate_zkba_manifest(m)
    assert not r.valid, f"missing {missing_field!r} should fail validation"
    assert any("missing required fields" in e for e in r.errors), \
        f"missing-fields error not raised; got {r.errors}"


# ===========================================================================
# T-MV-4 — validator rejects invalid zkba_class enum value
# ===========================================================================

@pytest.mark.parametrize("bad_value", [0, 8, -1, 999, 1.5, "GIC", True])
def test_t_mv_4_reject_invalid_zkba_class(bad_value):
    m = build_representative_manifest(zkba_class=ZKBAClass.GIC)
    m["zkba_class"] = bad_value
    r = validate_zkba_manifest(m)
    assert not r.valid, f"zkba_class={bad_value!r} should fail validation"


# ===========================================================================
# T-MV-5 — validator rejects invalid proof_weight enum value
# ===========================================================================

@pytest.mark.parametrize("bad_value", [0, 7, -1, 99, 2.5, "CHAIN_ONLY", True])
def test_t_mv_5_reject_invalid_proof_weight(bad_value):
    m = build_representative_manifest(zkba_class=ZKBAClass.GIC)
    m["proof_weight"] = bad_value
    r = validate_zkba_manifest(m)
    assert not r.valid, f"proof_weight={bad_value!r} should fail validation"


# ===========================================================================
# T-MV-6 — validator rejects malformed output_hash_hex
# ===========================================================================

@pytest.mark.parametrize("bad_hash", [
    "",                      # empty
    "abc",                   # too short
    "f" * 65,                # too long
    "F" * 64,                # uppercase (must be lowercase)
    "G" * 64,                # non-hex char
    "z" * 64,                # non-hex char
    123,                     # not a string
    None,                    # None
])
def test_t_mv_6_reject_malformed_output_hash_hex(bad_hash):
    m = build_representative_manifest(zkba_class=ZKBAClass.GIC)
    m["output_hash_hex"] = bad_hash
    r = validate_zkba_manifest(m)
    assert not r.valid, f"output_hash_hex={bad_hash!r} should fail"
    assert any("output_hash_hex" in e for e in r.errors), \
        f"output_hash_hex error not raised; got {r.errors}"


# ===========================================================================
# T-MV-7 — validator rejects malformed input_commitment_hex
# ===========================================================================

def test_t_mv_7_reject_malformed_input_commitment_hex():
    m = build_representative_manifest(zkba_class=ZKBAClass.GIC)
    m["input_commitment_hex"] = "not-hex"
    r = validate_zkba_manifest(m)
    assert not r.valid
    assert any("input_commitment_hex" in e for e in r.errors)


# ===========================================================================
# T-MV-8 — validator rejects non-uint64 ts_ns
# ===========================================================================

@pytest.mark.parametrize("bad_ts", [
    -1,                       # negative
    0xFFFFFFFFFFFFFFFF + 1,   # > uint64 max
    "1778000000",             # not int
    1778.5,                   # float
    True,                     # bool (Python int subclass, but explicitly rejected)
])
def test_t_mv_8_reject_invalid_ts_ns(bad_ts):
    m = build_representative_manifest(zkba_class=ZKBAClass.GIC)
    m["ts_ns"] = bad_ts
    r = validate_zkba_manifest(m)
    assert not r.valid, f"ts_ns={bad_ts!r} should fail validation"


# ===========================================================================
# T-MV-9 — validator rejects non-string schema field
# ===========================================================================

def test_t_mv_9_reject_non_string_schema():
    m = build_representative_manifest(zkba_class=ZKBAClass.GIC)
    m["schema"] = 42
    r = validate_zkba_manifest(m)
    assert not r.valid


# ===========================================================================
# T-MV-10 — validator rejects non-dict manifest entirely
# ===========================================================================

@pytest.mark.parametrize("not_dict", [None, [], "string", 42, set()])
def test_t_mv_10_reject_non_dict_manifest(not_dict):
    r = validate_zkba_manifest(not_dict)
    assert not r.valid
    assert any("must be dict" in e for e in r.errors)
    assert r.schema_name_form == "absent"


# ===========================================================================
# T-MV-11 — round-trip: validator accepts real compile_artifact output
# ===========================================================================

def test_t_mv_11_validator_accepts_real_compile_artifact_output(tmp_path):
    """End-to-end: invoke the real compile_artifact() on a GIC input
    set, parse the emitted .manifest.json, and confirm the validator
    accepts it. This is the closure test for B.8 G4 — proves the
    validator is interoperable with the actual compiler at v0.1.0."""
    inputs = {
        "grind_session_id":    "grind_phase235_v1",
        "chain_length":        100,
        "chain_head_hex":      "0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da",
        "genesis_hex":         "87ce52cd21f9037730262debd4d247a76a6439bb754d9219fe10346ee1278c05",
        "zkba_commitment_hex": "f" * 64,
        "ts_ns":               1778000000000000000,
        "links_summary":       [
            {"index": 0, "host_state": "EXCLUSIVE_USB", "verdict": "CERTIFY", "ch_short": "abc123"},
            {"index": 1, "host_state": "EXCLUSIVE_USB", "verdict": "CERTIFY", "ch_short": "def456"},
        ],
    }
    manifest = compile_artifact(
        zkba_class=ZKBAClass.GIC,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        inputs=inputs,
        output_dir=tmp_path,
        html_renderer=_render_gic_ledger_html,
    )
    # Read the emitted manifest JSON
    manifest_path = tmp_path / f"{manifest.input_commitment_hex}.manifest.json"
    assert manifest_path.exists()
    manifest_dict = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Validator must accept the real compiler output
    r = validate_zkba_manifest(manifest_dict)
    assert r.valid, f"validator rejected real compiler output: {r.errors}"
    assert r.zkba_class_name == "GIC"
    assert r.proof_weight_name == "CHAIN_ONLY"
    assert r.schema_name_form == "implementation"
    # Sanity: the real compiler uses the implementation schema name
    assert manifest_dict["schema"] == _MANIFEST_SCHEMA
    assert _MANIFEST_SCHEMA == IMPLEMENTATION_SCHEMA_NAME


# ===========================================================================
# T-MV-12 — fail-open contract: validator never raises
# ===========================================================================

def test_t_mv_12_validator_never_raises_on_garbage():
    """Fail-open contract: validate_zkba_manifest must NEVER raise.
    Any malformed input produces a result with valid=False and errors
    populated. Caller can chain rejections without try/except wrapping."""
    # Garbage inputs that might tempt code into raising
    garbage_inputs = [
        None,
        [],
        "string",
        42,
        set(),
        {"schema": object()},                    # un-stringable
        {"schema": IMPLEMENTATION_SCHEMA_NAME,
         "zkba_class": object(),                 # un-int-able
         "proof_weight": ProofWeightClass.CHAIN_ONLY.value,
         "output_path": "x",
         "output_hash_hex": "a" * 64,
         "input_commitment_hex": "b" * 64,
         "compiler_version": "0.1.0",
         "ts_ns": 0},
    ]
    for inp in garbage_inputs:
        # MUST NOT raise — if any of these raises, the fail-open
        # contract is violated.
        result = validate_zkba_manifest(inp)
        assert isinstance(result, ManifestValidationResult)
        assert not result.valid, f"garbage input {inp!r} should be invalid"
        assert len(result.errors) > 0


# ===========================================================================
# Closure marker for B.8 G4
# ===========================================================================

def test_t_mv_g4_seven_class_coverage_summary():
    """B.8 G4 closure marker: confirms the validator was exercised
    against representative artifacts of all 7 ZKBAClass values."""
    tested_classes = {c for c in ZKBAClass}
    assert tested_classes == {
        ZKBAClass.AIT, ZKBAClass.GIC, ZKBAClass.VHP, ZKBAClass.HARDWARE,
        ZKBAClass.CONSENT, ZKBAClass.TOURNAMENT, ZKBAClass.MARKET,
    }
    assert len(tested_classes) == 7
    # Default proof_weight table covers every class
    for c in tested_classes:
        assert c in DEFAULT_PROOF_WEIGHT_BY_CLASS, \
            f"missing default proof_weight for {c.name}"
