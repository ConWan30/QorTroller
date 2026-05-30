"""Data Economy Arc 5 — VAPIReplayProofPipeline.

Verified Human Replay (VHR) proof system. Turns a session's structural HID
replay into a non-invertible Sanitized Replay Matrix that proves a verified
human produced the gameplay trace while information-theoretically erasing the
L4/L5/E4/AIT biometric fingerprint.

Commit 1 ships the pre-processor (φ = φ_spatial ∘ φ_temporal) + data floor.
Commit 2 ships the circuit (contracts/circuits/VAPIReplayProofVerifier.circom)
+ the Python WitnessGenerator that assembles its input.json.
Contract, deploy, and orchestrator land in later commits of the arc; all
on-chain deploys are HELD until the full Data Economy ladder is verified
end-to-end under explicit operator GO (see
docs/data-economy-deploy-hold-and-arc5-readiness.md).
"""

from .pre_processor import (
    DataFloorViolationError,
    ReplayPreProcessor,
    SanitizedReplayMatrix,
    IMU_BITS,
    OUTPUT_HZ,
    RADIAL_BITS,
    SOURCE_HZ,
    TRIGGER_BITS,
    WINDOW_FRAMES,
)
from .witness_generator import (
    HumanityFloorNotClearedError,
    InvalidCommitmentError,
    VHRCircuitInputs,
    WitnessGenerator,
    compute_h_gap,
    scale_probability,
    BN254_PRIME,
    HUMANITY_SCALE,
    H_GAP_BITS,
    H_GAP_MAX,
)
from .pipeline import (
    DeferredProver,
    ProofResult,
    Prover,
    VAPIReplayProofPipeline,
    VHRProofPackage,
    VHR_OUTCOME_ABORTED_NO_SESSION,
    VHR_OUTCOME_DATA_FLOOR_VIOLATION,
    VHR_OUTCOME_DEFERRED_HUMANITY,
    VHR_OUTCOME_DEFERRED_NO_CONSENT,
    VHR_OUTCOME_DEFERRED_NO_FRAMES,
    VHR_OUTCOME_DEFERRED_VERDICT,
    VHR_OUTCOME_DISABLED,
    VHR_OUTCOME_PROOF_BUILT,
    VHR_OUTCOME_PROOF_BUILT_NO_VERIFIER,
    VHR_OUTCOME_PROOF_DEFERRED,
)

__all__ = [
    "DataFloorViolationError",
    "ReplayPreProcessor",
    "SanitizedReplayMatrix",
    "IMU_BITS",
    "OUTPUT_HZ",
    "RADIAL_BITS",
    "SOURCE_HZ",
    "TRIGGER_BITS",
    "WINDOW_FRAMES",
    "HumanityFloorNotClearedError",
    "InvalidCommitmentError",
    "VHRCircuitInputs",
    "WitnessGenerator",
    "compute_h_gap",
    "scale_probability",
    "BN254_PRIME",
    "HUMANITY_SCALE",
    "H_GAP_BITS",
    "H_GAP_MAX",
    "DeferredProver",
    "ProofResult",
    "Prover",
    "VAPIReplayProofPipeline",
    "VHRProofPackage",
    "VHR_OUTCOME_ABORTED_NO_SESSION",
    "VHR_OUTCOME_DATA_FLOOR_VIOLATION",
    "VHR_OUTCOME_DEFERRED_HUMANITY",
    "VHR_OUTCOME_DEFERRED_NO_CONSENT",
    "VHR_OUTCOME_DEFERRED_NO_FRAMES",
    "VHR_OUTCOME_DEFERRED_VERDICT",
    "VHR_OUTCOME_DISABLED",
    "VHR_OUTCOME_PROOF_BUILT",
    "VHR_OUTCOME_PROOF_BUILT_NO_VERIFIER",
    "VHR_OUTCOME_PROOF_DEFERRED",
]
