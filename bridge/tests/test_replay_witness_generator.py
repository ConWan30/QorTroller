"""Data Economy Arc 5 — VHR WitnessGenerator verification suite.

Pins the spec §3.3 Optimization 1 contract (off-chain compute_h_gap, in-circuit
Num2Bits(10) range check) and the circuit's public/private input partition.
Pure-Python deterministic checks only; Poseidon-via-circomlibjs lands at Commit
4 with its own gated tests.
"""

import json
from pathlib import Path

import pytest

from bridge.vapi_bridge.replay_proof_pipeline import (
    BN254_PRIME,
    H_GAP_BITS,
    H_GAP_MAX,
    HUMANITY_SCALE,
    HumanityFloorNotClearedError,
    InvalidCommitmentError,
    VHRCircuitInputs,
    WitnessGenerator,
    compute_h_gap,
    scale_probability,
)


# Fixture: a plausible commitment value — a decimal string strictly inside the
# BN254 field. Reused across input-assembly tests where the actual Poseidon
# computation is out of scope (lands at Commit 4).
_OK_COMMIT = "123456789012345678901234567890123456789012345678901234567890"
assert 0 < int(_OK_COMMIT) < BN254_PRIME


# --- §3.3 frozen-constant pinning ------------------------------------------

def test_humanity_scale_frozen():
    """HUMANITY_SCALE=1000 is the spec's compute_h_gap reference scale."""
    assert HUMANITY_SCALE == 1000


def test_h_gap_range_pins_circuit_num2bits():
    """Num2Bits(10) in the circuit accepts h_gap in [0, 1023] only.

    The Python H_GAP_MAX must equal that ceiling; otherwise compute_h_gap can
    accept values the circuit will reject (silent proof failure) or reject
    values the circuit would accept (loss of legitimate sessions).
    """
    assert H_GAP_BITS == 10
    assert H_GAP_MAX == 1023


def test_humanity_scale_fits_in_h_gap_window():
    """The scale and the bit window must be paired: max gap ≤ H_GAP_MAX.

    With HUMANITY_SCALE=1000 the maximum possible gap is 1000 (witness=1.0,
    threshold=0.0). 1000 ≤ 1023, so the pairing is valid. Catches future drift
    if either constant moves independently.
    """
    assert HUMANITY_SCALE <= H_GAP_MAX


# --- scale_probability ------------------------------------------------------

@pytest.mark.parametrize("p,expected", [
    (0.0, 0), (1.0, 1000),
    (0.70, 700),      # AIT default floor
    (0.92, 920),
    (0.7001, 700),    # rounds to nearest, not floors
    (0.7005, 700),    # banker's rounding (round-half-to-even) → 700
    (0.7006, 701),
])
def test_scale_probability_canonical_points(p, expected):
    assert scale_probability(p) == expected


@pytest.mark.parametrize("bad", [-0.01, 1.01, 1.5, -1.0])
def test_scale_probability_rejects_out_of_range(bad):
    with pytest.raises(ValueError):
        scale_probability(bad)


def test_scale_probability_rejects_non_numeric():
    with pytest.raises(TypeError):
        scale_probability("0.7")  # type: ignore[arg-type]


# --- compute_h_gap (spec §3.3 Optimization 1) ------------------------------

def test_compute_h_gap_clears_floor():
    """A session at 0.92 humanity against the 0.70 floor yields gap = 220."""
    assert compute_h_gap(0.92, 0.70) == 220


def test_compute_h_gap_equal_is_zero():
    """Exactly at the floor — gap is zero, NOT a violation.

    Num2Bits(10) accepts 0; the consent manifest says "minimum X" not
    "strictly above X" (matches the spec §4 Dimension 8 default of 0.70).
    """
    assert compute_h_gap(0.70, 0.70) == 0


def test_compute_h_gap_full_human():
    """Witness=1.0, threshold=0.0 → gap = 1000 (the max allowed by the pair)."""
    assert compute_h_gap(1.0, 0.0) == 1000


def test_compute_h_gap_below_floor_raises():
    """Floor not cleared — fail fast off-chain rather than letting snarkjs."""
    with pytest.raises(HumanityFloorNotClearedError):
        compute_h_gap(0.65, 0.70)


def test_compute_h_gap_just_below_floor_raises():
    """A 0.5 LSB float wobble at the floor must still be a clean failure."""
    with pytest.raises(HumanityFloorNotClearedError):
        compute_h_gap(0.6994, 0.70)


# --- commitment validation -------------------------------------------------

def test_commitment_field_modulus_pinned():
    """BN254 scalar field prime is curve-defined; pinning it catches drift
    if a future contributor accidentally swaps to a different curve."""
    assert BN254_PRIME == (
        21888242871839275222246405745257275088548364400416034343698204186575808495617
    )


@pytest.mark.parametrize("bad", [
    "",                # empty
    "0x1234",          # hex not allowed
    "1.5",             # not integer
    "abc",             # not numeric
    str(BN254_PRIME),  # exactly the modulus is out of field
])
def test_build_inputs_rejects_malformed_commitment(bad):
    gen = WitnessGenerator()
    with pytest.raises(InvalidCommitmentError):
        gen.build_inputs(
            humanity_probability=0.92, humanity_threshold=0.70,
            vhp_token_id=2, session_nonce=1,
            sanitized_trace_root=bad, poac_chain_root=_OK_COMMIT,
            consent_policy_hash=_OK_COMMIT, vhp_commitment=_OK_COMMIT,
        )


def test_build_inputs_accepts_int_commitment():
    """Decimal int form is accepted (no need to pre-stringify at call sites)."""
    gen = WitnessGenerator()
    inputs = gen.build_inputs(
        humanity_probability=0.92, humanity_threshold=0.70,
        vhp_token_id=2, session_nonce=1,
        sanitized_trace_root=int(_OK_COMMIT), poac_chain_root=_OK_COMMIT,
        consent_policy_hash=_OK_COMMIT, vhp_commitment=_OK_COMMIT,
    )
    assert inputs.sanitized_trace_root == _OK_COMMIT


# --- circuit-input partition (matches component main public list) -----------

CIRCUIT_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts" / "circuits" / "VAPIReplayProofVerifier.circom"
)


def _public_keys_from_circuit_source():
    """Extract the `component main {public [...]}` order from the circuit file.

    Tests assert the Python input dict's first 5 keys are exactly the circuit's
    public list in declaration order — INV-VHR-005's tooth on the Python side.
    """
    text = CIRCUIT_PATH.read_text(encoding="utf-8")
    head = text.split("component main {public [", 1)[1]
    body = head.split("]", 1)[0]
    return [tok.strip() for tok in body.split(",") if tok.strip()]


def test_build_inputs_dict_matches_circuit_public_order():
    gen = WitnessGenerator()
    inputs = gen.build_inputs(
        humanity_probability=0.92, humanity_threshold=0.70,
        vhp_token_id=2, session_nonce=1,
        sanitized_trace_root=_OK_COMMIT, poac_chain_root=_OK_COMMIT,
        consent_policy_hash=_OK_COMMIT, vhp_commitment=_OK_COMMIT,
    )
    d = inputs.to_input_dict()
    circuit_public = _public_keys_from_circuit_source()
    assert circuit_public == [
        "sanitizedTraceRoot", "poacChainRoot", "consentPolicyHash",
        "humanityThreshold", "vhpCommitment",
    ], f"Circuit public list drifted: {circuit_public}"
    # First five keys of the input dict must be the public partition, in order.
    keys = list(d.keys())
    assert keys[:5] == circuit_public
    # Remaining three keys are the private witness.
    assert sorted(keys[5:]) == sorted([
        "humanityProbabilityWitness", "vhpTokenId", "sessionNonce",
    ])


def test_build_inputs_decimal_strings_only():
    """snarkjs fullprove parses input.json with string-or-number; we standardise
    on decimal strings (matches the zk_sepproof_prover precedent)."""
    gen = WitnessGenerator()
    inputs = gen.build_inputs(
        humanity_probability=0.92, humanity_threshold=0.70,
        vhp_token_id=2, session_nonce=1,
        sanitized_trace_root=_OK_COMMIT, poac_chain_root=_OK_COMMIT,
        consent_policy_hash=_OK_COMMIT, vhp_commitment=_OK_COMMIT,
    )
    d = inputs.to_input_dict()
    for k, v in d.items():
        assert isinstance(v, str), f"{k} is {type(v).__name__}, want str"
        assert v.isdigit(), f"{k}={v!r} is not a decimal-digit string"


def test_build_inputs_scales_humanity_to_thresholded_integers():
    """Witness + threshold must be the ×1000-scaled integers, not raw floats."""
    gen = WitnessGenerator()
    inputs = gen.build_inputs(
        humanity_probability=0.92, humanity_threshold=0.70,
        vhp_token_id=2, session_nonce=1,
        sanitized_trace_root=_OK_COMMIT, poac_chain_root=_OK_COMMIT,
        consent_policy_hash=_OK_COMMIT, vhp_commitment=_OK_COMMIT,
    )
    assert inputs.humanity_threshold == "700"
    assert inputs.humanity_probability_witness == "920"


def test_build_inputs_below_floor_fails_fast():
    """Pre-flight: builder refuses to assemble a doomed witness."""
    gen = WitnessGenerator()
    with pytest.raises(HumanityFloorNotClearedError):
        gen.build_inputs(
            humanity_probability=0.65, humanity_threshold=0.70,
            vhp_token_id=2, session_nonce=1,
            sanitized_trace_root=_OK_COMMIT, poac_chain_root=_OK_COMMIT,
            consent_policy_hash=_OK_COMMIT, vhp_commitment=_OK_COMMIT,
        )


@pytest.mark.parametrize("bad_field", ["vhp_token_id", "session_nonce"])
def test_build_inputs_rejects_negative_witness_ids(bad_field):
    gen = WitnessGenerator()
    kwargs = dict(
        humanity_probability=0.92, humanity_threshold=0.70,
        vhp_token_id=2, session_nonce=1,
        sanitized_trace_root=_OK_COMMIT, poac_chain_root=_OK_COMMIT,
        consent_policy_hash=_OK_COMMIT, vhp_commitment=_OK_COMMIT,
    )
    kwargs[bad_field] = -1
    with pytest.raises(ValueError):
        gen.build_inputs(**kwargs)


def test_input_dict_is_json_serializable():
    """snarkjs reads input.json — the dict must round-trip through json."""
    gen = WitnessGenerator()
    inputs = gen.build_inputs(
        humanity_probability=0.92, humanity_threshold=0.70,
        vhp_token_id=2, session_nonce=42,
        sanitized_trace_root=_OK_COMMIT, poac_chain_root=_OK_COMMIT,
        consent_policy_hash=_OK_COMMIT, vhp_commitment=_OK_COMMIT,
    )
    blob = json.dumps(inputs.to_input_dict())
    parsed = json.loads(blob)
    assert parsed["humanityThreshold"] == "700"
    assert parsed["humanityProbabilityWitness"] == "920"
    assert parsed["sessionNonce"] == "42"


# --- compiled-circuit cross-check ------------------------------------------

def test_circuit_file_present_and_off_circuit_root_design():
    """The compiled circuit ships sanitizedTraceRoot as PUBLIC, not private —
    pins drift D-9's resolution (off-circuit matrix commitment, see circuit
    header)."""
    src = CIRCUIT_PATH.read_text(encoding="utf-8")
    assert "signal input sanitizedTraceRoot" in src, (
        "sanitizedTraceRoot must be a public signal (drift D-9 resolution)"
    )
    # D-8: no circom-1.x `signal private input` survives.
    assert "signal private input" not in src, (
        "circom 2.0.0: privacy is declared via component main, not 'signal "
        "private input' (drift D-8 resolution)"
    )
