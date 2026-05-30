"""Data Economy Arc 5 — VAPIReplayProofPipeline.

Verified Human Replay (VHR) proof system. Turns a session's structural HID
replay into a non-invertible Sanitized Replay Matrix that proves a verified
human produced the gameplay trace while information-theoretically erasing the
L4/L5/E4/AIT biometric fingerprint.

Commit 1 ships the pre-processor (φ = φ_spatial ∘ φ_temporal) + data floor.
Circuit, contract, and orchestrator land in later commits of the arc; all
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
]
