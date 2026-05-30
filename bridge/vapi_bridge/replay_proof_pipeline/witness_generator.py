"""Data Economy Arc 5 — VAPIReplayProofVerifier WitnessGenerator.

Deterministic, pure-Python half of the VHR proof witness:

  • Scaling of float humanity probabilities to BN254-field ×1000 integers.
  • Off-circuit gap subtraction (compute_h_gap) — the division/subtraction
    offload called out in spec §3.3 Optimization 1.
  • Assembly of the snarkjs circuit input dict (public + private partition
    exactly matching the compiled circuit at
    contracts/circuits/VAPIReplayProofVerifier.circom).

What this module deliberately does NOT do:

  • Compute Poseidon (vhpCommitment, sanitizedTraceRoot). Those public-input
    commitments are computed at orchestration time by a circomlibjs node
    helper that guarantees byte-identical output to the circuit's in-wasm
    Poseidon. Doing it in Python would risk a constant-mismatch divergence
    that silently produces invalid proofs. The honesty rail mirrors
    zk_sepproof_prover.py: callers supply the Poseidon-derived commitments
    as decimal-string field elements; the WitnessGenerator validates shape
    and assembles the input.json.
  • Run snarkjs fullprove. That subprocess composition lands in Commit 4
    alongside the orchestrator, gated on the ceremony populating
    bridge/vapi_bridge/replay_proof_pipeline/zk_artifacts/.

Spec anchor: docs/VAPI_REPLAY_PROOF_PIPELINE_SPEC (1).md §3.3 + §10 Commit 2.
Off-circuit-root resolution (drift D-9): the matrix root is a PUBLIC input
computed by the pre-processor / orchestrator, not re-hashed in-circuit. See
the circuit file's header comment for the full reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ── FROZEN scaling constants ────────────────────────────────────────────────

# Humanity probabilities are scaled to integers in [0, 1000] to stay safely in
# the BN254 field and to keep h_gap inside a 10-bit Num2Bits range check.
# Changing this scale silently breaks the circuit's range check assumption
# (a higher scale would overflow 10 bits; a lower scale would lose precision
# below the AIT 0.70 floor's two-decimal granularity).
HUMANITY_SCALE: Final[int] = 1000

# Range-check ceiling enforced in-circuit by Num2Bits(10). h_gap > 1023 cannot
# be represented in 10 bits → proof generation fails. Both witness and
# threshold are bounded by HUMANITY_SCALE = 1000 so the gap is at most 1000,
# which fits comfortably inside the 10-bit window.
H_GAP_BITS: Final[int] = 10
H_GAP_MAX: Final[int] = (1 << H_GAP_BITS) - 1   # 1023


# ── Errors ──────────────────────────────────────────────────────────────────

class HumanityFloorNotClearedError(ValueError):
    """Raised when humanity_probability_witness < humanity_threshold.

    The off-chain check matches the in-circuit Num2Bits(10) constraint: if a
    prover tries to generate a proof for a session that did not clear the
    floor, the circuit will reject it. Raising here fails fast with a clear
    message rather than letting the prover discover the failure inside
    snarkjs fullprove.
    """


class InvalidCommitmentError(ValueError):
    """Raised when a supplied Poseidon commitment is not a valid BN254 field
    element decimal string.

    The WitnessGenerator does NOT compute Poseidon — callers pass precomputed
    commitments. This sanity check catches the easy mistakes (empty string,
    hex string, negative, exceeds the BN254 modulus) before snarkjs gets a
    chance to fail with a less actionable error.
    """


# BN254 scalar field prime (snarkjs / circomlib BN254 default curve).
# A commitment must be a decimal integer in [0, BN254_PRIME).
BN254_PRIME: Final[int] = (
    21888242871839275222246405745257275088548364400416034343698204186575808495617
)


# ── Scaling + gap computation ──────────────────────────────────────────────

def scale_probability(probability: float) -> int:
    """Scale a float probability in [0, 1] to an integer in [0, HUMANITY_SCALE].

    Bankers' / IEEE rounding via round() — matches the spec's compute_h_gap
    reference (`int(gap * 1000)` is truncation-equivalent for the gap, but for
    the inputs we round-to-nearest so a 0.7001 humanity prob doesn't silently
    drop to 700 = threshold and produce a borderline-zero gap that's an
    artifact of float→int truncation rather than the real margin).
    """
    if not isinstance(probability, (int, float)):
        raise TypeError(
            f"probability must be int or float, got {type(probability).__name__}"
        )
    if not (0.0 <= float(probability) <= 1.0):
        raise ValueError(
            f"probability must be in [0, 1], got {probability}"
        )
    return int(round(float(probability) * HUMANITY_SCALE))


def compute_h_gap(humanity_probability: float, humanity_threshold: float) -> int:
    """Compute the scaled humanity-floor gap, offloaded off-chain per spec §3.3.

    Returns the scaled integer h_gap = scale(prob) − scale(threshold), and
    asserts gap >= 0. This is the exact contract the circuit's
    Num2Bits(10) constraint enforces on the witness side; computing it here
    avoids in-circuit subtraction-then-comparison logic and keeps the
    constraint count down.

    Raises HumanityFloorNotClearedError if the session's probability is below
    the threshold.
    """
    scaled_prob = scale_probability(humanity_probability)
    scaled_threshold = scale_probability(humanity_threshold)
    gap = scaled_prob - scaled_threshold
    if gap < 0:
        raise HumanityFloorNotClearedError(
            f"humanity_probability {humanity_probability} < threshold "
            f"{humanity_threshold} — session did not clear the consent-manifest "
            f"floor; no VHR proof is producible for this session"
        )
    if gap > H_GAP_MAX:
        # Defensive: with HUMANITY_SCALE=1000 and both inputs in [0,1] this
        # is mathematically unreachable (gap ≤ 1000 ≤ 1023). Guarding anyway
        # so a future scale change can't silently break the in-circuit range
        # check without this raising first.
        raise ValueError(
            f"h_gap {gap} exceeds {H_GAP_MAX} — Num2Bits({H_GAP_BITS}) would "
            f"reject; revisit HUMANITY_SCALE / H_GAP_BITS pairing"
        )
    return gap


# ── Commitment validation ──────────────────────────────────────────────────

def _validate_field_decimal(value, name: str) -> str:
    """Validate that `value` is a decimal-string BN254 field element.

    Returns the normalized decimal string snarkjs expects. Raises
    InvalidCommitmentError on any malformed input.
    """
    if isinstance(value, int):
        n = value
    elif isinstance(value, str):
        s = value.strip()
        if not s or not (s.isdigit() or (s.startswith("-") and s[1:].isdigit())):
            raise InvalidCommitmentError(
                f"{name} must be a decimal integer string, got {value!r}"
            )
        n = int(s)
    else:
        raise InvalidCommitmentError(
            f"{name} must be int or decimal str, got {type(value).__name__}"
        )
    if n < 0 or n >= BN254_PRIME:
        raise InvalidCommitmentError(
            f"{name} = {n} is outside [0, BN254_PRIME) — not a valid field element"
        )
    return str(n)


# ── Input dict assembly ────────────────────────────────────────────────────

@dataclass(frozen=True)
class VHRCircuitInputs:
    """The snarkjs input.json contents for one VAPIReplayProofVerifier proof.

    All values are decimal strings as required by snarkjs. The public/private
    partition matches the compiled circuit's `component main {public [...]}`
    declaration exactly.
    """

    # Public inputs (verifier sees these; order matches circuit declaration).
    sanitized_trace_root: str
    poac_chain_root: str
    consent_policy_hash: str
    humanity_threshold: str
    vhp_commitment: str

    # Private inputs (witness only; never leave the prover).
    humanity_probability_witness: str
    vhp_token_id: str
    session_nonce: str

    def to_input_dict(self) -> dict[str, str]:
        """Render the input dict snarkjs fullprove expects.

        Field names exactly match the circuit's `signal input` declarations.
        Any rename here without a matching circuit edit silently breaks proof
        generation — INV-VHR-005 pins the public-input order across surfaces.
        """
        return {
            "sanitizedTraceRoot":          self.sanitized_trace_root,
            "poacChainRoot":               self.poac_chain_root,
            "consentPolicyHash":           self.consent_policy_hash,
            "humanityThreshold":           self.humanity_threshold,
            "vhpCommitment":               self.vhp_commitment,
            "humanityProbabilityWitness":  self.humanity_probability_witness,
            "vhpTokenId":                  self.vhp_token_id,
            "sessionNonce":                self.session_nonce,
        }


@dataclass(frozen=True)
class VHRCircuitInputsV2:
    """The snarkjs input.json contents for one VAPIReplayProofVerifier_v2
    proof (Arc 6 PoSR). Extends Arc 5's 8-field shape with the 4 beacon
    public inputs + 2 beacon-hash private witnesses.

    Public/private partition matches VAPIReplayProofVerifier_v2.circom
    `component main {public [...]}` declaration order EXACTLY. Pinned by
    PV-CI INV-POSR-CIRCUIT-001.

    All values are decimal strings as required by snarkjs.
    """
    # Public (in declaration order — snarkjs public.json output order):
    sanitized_trace_root:    str
    poac_chain_root:         str
    consent_policy_hash:     str
    humanity_threshold:      str
    vhp_commitment:          str
    open_beacon_block:       str
    close_beacon_block:      str
    open_beacon_commitment:  str
    close_beacon_commitment: str

    # Private witnesses:
    humanity_probability_witness: str
    vhp_token_id:                 str
    session_nonce:                str
    open_beacon_hash:             str
    close_beacon_hash:            str

    def to_input_dict(self) -> dict[str, str]:
        """Render the input dict snarkjs fullprove expects for v2. Field
        names MUST match the circuit's `signal input` declarations exactly."""
        return {
            "sanitizedTraceRoot":          self.sanitized_trace_root,
            "poacChainRoot":               self.poac_chain_root,
            "consentPolicyHash":           self.consent_policy_hash,
            "humanityThreshold":           self.humanity_threshold,
            "vhpCommitment":               self.vhp_commitment,
            "openBeaconBlock":             self.open_beacon_block,
            "closeBeaconBlock":            self.close_beacon_block,
            "openBeaconCommitment":        self.open_beacon_commitment,
            "closeBeaconCommitment":       self.close_beacon_commitment,
            "humanityProbabilityWitness":  self.humanity_probability_witness,
            "vhpTokenId":                  self.vhp_token_id,
            "sessionNonce":                self.session_nonce,
            "openBeaconHash":              self.open_beacon_hash,
            "closeBeaconHash":             self.close_beacon_hash,
        }


class WitnessGenerator:
    """Assembles the snarkjs input.json for VAPIReplayProofVerifier proofs.

    Usage (orchestrator at Commit 4):

        gen = WitnessGenerator()
        inputs = gen.build_inputs(
            humanity_probability         = 0.92,    # session min p(human)
            humanity_threshold           = 0.70,    # consent manifest floor
            vhp_token_id                 = 2,
            session_nonce                = 0x1f3e...,
            # Poseidon commitments — caller computes via circomlibjs at
            # Commit 4 orchestration time. Decimal-string field elements.
            sanitized_trace_root         = "143...",
            poac_chain_root              = "284...",
            consent_policy_hash          = "971...",
            vhp_commitment               = "455...",
        )
        json.dump(inputs.to_input_dict(), open("input.json", "w"))
        # then: snarkjs groth16 fullprove input.json wasm zkey proof.json public.json
    """

    HUMANITY_SCALE = HUMANITY_SCALE
    H_GAP_MAX = H_GAP_MAX

    def build_inputs_v2(
        self,
        *,
        humanity_probability: float,
        humanity_threshold: float,
        vhp_token_id: int,
        session_nonce: int,
        sanitized_trace_root,
        poac_chain_root,
        consent_policy_hash,
        vhp_commitment,
        open_beacon_block: int,
        close_beacon_block: int,
        open_beacon_hash: int,
        close_beacon_hash: int,
        open_beacon_commitment,
        close_beacon_commitment,
    ) -> VHRCircuitInputsV2:
        """Build Arc 6 v2 (PoSR) circuit inputs. The two beacon Poseidon
        commitments (open_beacon_commitment, close_beacon_commitment) must
        be precomputed via circomlibjs by the node helper — passed in as
        decimal-string field elements. Block hashes are precomputed BN254
        field-element representations (Python doesn't reimplement Poseidon)."""
        _ = compute_h_gap(humanity_probability, humanity_threshold)
        scaled_witness = scale_probability(humanity_probability)
        scaled_threshold = scale_probability(humanity_threshold)
        if not isinstance(vhp_token_id, int) or vhp_token_id < 0:
            raise ValueError(f"vhp_token_id must be a non-negative int")
        if not isinstance(session_nonce, int) or session_nonce < 0:
            raise ValueError(f"session_nonce must be a non-negative int")
        if not isinstance(open_beacon_block, int) or open_beacon_block < 0:
            raise ValueError("open_beacon_block must be a non-negative int")
        if not isinstance(close_beacon_block, int) or close_beacon_block < 0:
            raise ValueError("close_beacon_block must be a non-negative int")
        if close_beacon_block <= open_beacon_block:
            raise ValueError("close_beacon_block must be > open_beacon_block")
        return VHRCircuitInputsV2(
            sanitized_trace_root=_validate_field_decimal(sanitized_trace_root, "sanitized_trace_root"),
            poac_chain_root=_validate_field_decimal(poac_chain_root, "poac_chain_root"),
            consent_policy_hash=_validate_field_decimal(consent_policy_hash, "consent_policy_hash"),
            humanity_threshold=str(scaled_threshold),
            vhp_commitment=_validate_field_decimal(vhp_commitment, "vhp_commitment"),
            open_beacon_block=str(open_beacon_block),
            close_beacon_block=str(close_beacon_block),
            open_beacon_commitment=_validate_field_decimal(open_beacon_commitment, "open_beacon_commitment"),
            close_beacon_commitment=_validate_field_decimal(close_beacon_commitment, "close_beacon_commitment"),
            humanity_probability_witness=str(scaled_witness),
            vhp_token_id=str(vhp_token_id),
            session_nonce=str(session_nonce),
            open_beacon_hash=str(int(open_beacon_hash)),
            close_beacon_hash=str(int(close_beacon_hash)),
        )

    def build_inputs(
        self,
        *,
        humanity_probability: float,
        humanity_threshold: float,
        vhp_token_id: int,
        session_nonce: int,
        sanitized_trace_root,
        poac_chain_root,
        consent_policy_hash,
        vhp_commitment,
    ) -> VHRCircuitInputs:
        # Off-chain h_gap check (matches the in-circuit Num2Bits constraint).
        # Raises HumanityFloorNotClearedError fast if the floor is not cleared.
        _ = compute_h_gap(humanity_probability, humanity_threshold)

        scaled_witness = scale_probability(humanity_probability)
        scaled_threshold = scale_probability(humanity_threshold)

        if not isinstance(vhp_token_id, int) or vhp_token_id < 0:
            raise ValueError(
                f"vhp_token_id must be a non-negative int, got {vhp_token_id!r}"
            )
        if not isinstance(session_nonce, int) or session_nonce < 0:
            raise ValueError(
                f"session_nonce must be a non-negative int, got {session_nonce!r}"
            )
        if vhp_token_id >= BN254_PRIME:
            raise ValueError("vhp_token_id exceeds BN254 field modulus")
        if session_nonce >= BN254_PRIME:
            raise ValueError("session_nonce exceeds BN254 field modulus")

        return VHRCircuitInputs(
            sanitized_trace_root         = _validate_field_decimal(
                sanitized_trace_root, "sanitized_trace_root"),
            poac_chain_root              = _validate_field_decimal(
                poac_chain_root, "poac_chain_root"),
            consent_policy_hash          = _validate_field_decimal(
                consent_policy_hash, "consent_policy_hash"),
            humanity_threshold           = str(scaled_threshold),
            vhp_commitment               = _validate_field_decimal(
                vhp_commitment, "vhp_commitment"),
            humanity_probability_witness = str(scaled_witness),
            vhp_token_id                 = str(vhp_token_id),
            session_nonce                = str(session_nonce),
        )
