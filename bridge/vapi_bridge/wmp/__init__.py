"""World Model Provenance Lane (WMP) — Verified Human Action Provenance
for World-Model Consumers (Phase WMP-1, 2026-06-06).

QorTroller is a provenance source for the demonstration-data bottleneck Li
named in *A Functional Taxonomy of World Models* (June 2026). WMP packages
Arc 5 (VHR) + Arc 6 (PoSR) + Arc 4 (Consent) into a `ProvenanceBundle v1`
that a world-model researcher can verify cryptographically WITHOUT
trusting QorTroller's infrastructure.

QorTroller is NOT a world model. WMP does not output pixels (renderer),
state (simulator), or actions (planner). It instruments the agent→action
edge of a real human in the loop and stamps that edge with cryptographic
provenance. The lane is action-channel-only, post-φ sanitized data only,
real sessions only.

See docs/world-model-provenance.md for the honest POMDP placement and
the W1-D operator decision (fixtures-first v1, deferred-export guard,
greenfield VAPIWorldModelConsentRegistry as flagged Phase-2 promote).
"""

from .bundle_assembler import (
    ProvenanceBundle,
    BundleAssembler,
    DataFloorViolationError,
    SCHEMA_VERSION,
)

__all__ = [
    "ProvenanceBundle",
    "BundleAssembler",
    "DataFloorViolationError",
    "SCHEMA_VERSION",
]
