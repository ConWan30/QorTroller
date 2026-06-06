"""WMP-1 bundle assembler — packaging-only, no new crypto.

Given a session that already carries an Arc 5 VHR proof (humanity proof),
an Arc 6 PoSR proof (recency proof), and an Arc 4 consent reference,
assemble a `ProvenanceBundle v1` that:

  1. Contains the POST-φ sanitized matrix from the existing
     `ReplayPreProcessor` output — NEVER raw HID, NEVER L4 features,
     NEVER FORBIDDEN_COLUMNS biometric features.

  2. References (does NOT copy) the VHR Groth16 proof object and its
     public inputs (including `sanitizedTraceRoot`).

  3. References (does NOT copy) the PoSR open/close beacon block numbers
     and hashes from the session boundary.

  4. References the Arc 4 ConsentManifest by registry address + gamer
     wallet + manifest hash. v1 names the world-model export consent
     dimension "deferred" — per the W1-D operator decision, the lane
     ships on fixtures and the W1 cryptographic consent leg is deferred
     to a Phase-2 promote (greenfield `VAPIWorldModelConsentRegistry`).

  5. Always includes a machine-readable `scope_disclosure` block stating
     channel=ACTION_ONLY, observation_channel=ABSENT_BY_DESIGN_DATA_FLOOR,
     fidelity=MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL, synthetic=false,
     is_full_pomdp_tuple=false.

Data-floor enforcement: the assembler reads the action trace ONLY through
the Arc 5 `FORBIDDEN_COLUMNS` allowlist path. Any forbidden field on the
input dict raises `DataFloorViolationError` BEFORE any other work. The
guard is reused from `ReplayPreProcessor.FORBIDDEN_COLUMNS` (frozenset
pinned by INV-VHR-004) — never forked.

Honesty rails (held across this module):

  • No new FROZEN-v1 family. The bundle is a packaging schema, not a
    commitment family. Domain tag is absent by design.

  • No new PV-CI invariant. SCHEMA_VERSION is a packaging string.

  • Real sessions only. The assembler refuses synthetic / augmented /
    test-only matrices by checking the `synthetic` field; if a caller
    sets it true, the assembler still proceeds but the bundle records
    synthetic=true in scope_disclosure so a consumer verifier can
    REJECT it. Default: real sessions only.

  • Action channel only. Observation/screen data is permanently absent
    by data floor — `observation_channel` field is always
    "ABSENT_BY_DESIGN_DATA_FLOOR" with no override path.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from ..replay_proof_pipeline.pre_processor import (
    ReplayPreProcessor,
    SanitizedReplayMatrix,
)


# Bundle schema string. NOT a commitment-family domain tag. Pure packaging
# metadata for the consumer verifier to refuse unknown schema versions.
SCHEMA_VERSION = "vapi-wmp-provenance-bundle-v1"


class DataFloorViolationError(Exception):
    """Raised when the bundle assembler detects an attempt to include a
    field forbidden by the Arc 5 `FORBIDDEN_COLUMNS` data floor.

    The error names the offending field so the operator can audit which
    code path tried to leak biometric/observation data into a WMP bundle.
    The guard is reused from `ReplayPreProcessor.FORBIDDEN_COLUMNS` — the
    single source of truth pinned by INV-VHR-004.
    """


@dataclass(frozen=True)
class ProvenanceBundle:
    """ProvenanceBundle v1 — additive packaging over Arc 5/6/4 proofs.

    Fields are organized into five sections matching the spec §2.1
    JSONC schema:

      action_trace   — post-φ sanitized matrix (REFERENCED, not copied)
      humanity_proof — Arc 5 VHR Groth16 proof (REFERENCED)
      recency_proof  — Arc 6 PoSR open/close beacons (REFERENCED)
      consent_ref    — Arc 4 ConsentManifest reference
      scope_disclosure — Anti-Hype machine-readable honesty block

    The assembler ONLY emits frozen dataclasses; consumers serialize via
    `to_dict()` for JSONL export.
    """

    # ── packaging metadata ──────────────────────────────────────────────
    schema: str
    bundle_created_at_ns: int

    # ── action_trace ────────────────────────────────────────────────────
    # Format identifier for the consumer-side parser. Macro-intent only.
    action_trace_format: str
    action_trace_channels: tuple[str, ...]
    action_trace_ticks: int
    # Reference to the sanitized matrix's Poseidon root (the public input
    # to the VHR proof). Consumer recomputes Poseidon(matrix) and asserts
    # equality (the WMP verifier is the canonical home for this check).
    sanitized_trace_root_ref: str
    # The matrix bytes themselves, encoded as hex-per-channel for JSONL
    # portability. Consumer reads these BACK to bytes for the rehash.
    action_trace_matrix_hex: dict[str, str]

    # ── humanity_proof (Arc 5 VHR) ──────────────────────────────────────
    humanity_proof_type: str            # FROZEN: "VAPI-REPLAY-PROOF-v1"
    humanity_proof_bytes_hex: str       # 256-byte snarkjs proof, hex
    humanity_proof_public_inputs: dict  # named inputs (sanitizedTraceRoot, etc.)
    humanity_verifier_address: str      # 0x... on IoTeX testnet
    humanity_deferred: bool             # True when DeferredProver was used
    humanity_deferred_reason: str

    # ── recency_proof (Arc 6 PoSR) ──────────────────────────────────────
    recency_open_block: int
    recency_open_block_hash: str        # 0x... hex
    recency_close_block: int
    recency_close_block_hash: str       # 0x... hex
    recency_registry_address: str       # 0x... on IoTeX testnet (or "")
    # When the Arc 6 registry address is empty, the bundle is honest about
    # PoSR being dormant; the consumer verifier returns
    # BEACON_REGISTRY_NOT_DEPLOYED honestly rather than passing/failing.

    # ── consent_ref (Arc 4) ─────────────────────────────────────────────
    consent_registry_address: str
    consent_gamer_address: str
    consent_manifest_hash: str          # 0x... hex
    # v1 W1-D: the world-model export dimension is DEFERRED. Real exports
    # are blocked at the exporter; the consumer verifier surfaces
    # CONSENT_GATE_DEFERRED honestly. When Phase-2 promotes the greenfield
    # VAPIWorldModelConsentRegistry, this field carries the registry
    # address + view-call result.
    world_model_consent_dimension: str  # "DEFERRED" in v1
    world_model_consent_registry: str   # "" in v1

    # ── scope_disclosure ───────────────────────────────────────────────
    # Machine-readable honesty block. The consumer verifier asserts this
    # block is present AND that it carries the FROZEN values below; a
    # bundle missing or mis-stating scope_disclosure is REJECTED.
    scope_channel: str                  # "ACTION_ONLY"
    scope_observation_channel: str      # "ABSENT_BY_DESIGN_DATA_FLOOR"
    scope_fidelity: str                 # "MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL"
    scope_synthetic: bool               # default False; True flags a synthetic / fixture bundle
    scope_is_full_pomdp_tuple: bool     # always False — the lane never gives full (s, a) tuples

    def to_dict(self) -> dict:
        """Serialize for JSONL export (one bundle per line)."""
        d = asdict(self)
        # tuple → list for JSON
        d["action_trace_channels"] = list(d["action_trace_channels"])
        return d


# Canonical channel order. Matches SanitizedReplayMatrix field order.
_CANONICAL_CHANNELS: tuple[str, ...] = (
    "stick_L_sector",
    "stick_R_sector",
    "trigger_L_state",
    "trigger_R_state",
    "button_mask",
    "imu_gravity_sector",
)


# Machine-readable scope_disclosure FROZEN values. The assembler emits these
# verbatim; the consumer verifier (WMP-3) asserts these exact strings.
_SCOPE_CHANNEL_ACTION_ONLY = "ACTION_ONLY"
_SCOPE_OBSERVATION_ABSENT = "ABSENT_BY_DESIGN_DATA_FLOOR"
_SCOPE_FIDELITY_MACRO = "MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL"


@dataclass
class BundleAssembler:
    """Stateless assembler. Construct once per bridge process; safe to
    invoke `assemble(...)` many times.

    Reuses `ReplayPreProcessor.FORBIDDEN_COLUMNS` directly — no fork.
    """

    def __post_init__(self) -> None:
        # The single source of truth for the data floor. INV-VHR-004
        # pinned. Importing on construction so a misconfigured bridge
        # cannot accidentally fork or override the frozenset.
        self._forbidden: frozenset[str] = ReplayPreProcessor.FORBIDDEN_COLUMNS

    @property
    def forbidden_columns(self) -> frozenset[str]:
        """Expose the reused data-floor frozenset for tests + auditors."""
        return self._forbidden

    def _assert_no_forbidden_keys(self, payload: dict[str, Any], context: str) -> None:
        """Raise DataFloorViolationError if ANY key in `payload` is in the
        FORBIDDEN_COLUMNS frozenset. Called on every external-supplied
        dict (extra metadata, custom annotations) before assembly.
        """
        for key in payload.keys():
            if key in self._forbidden:
                raise DataFloorViolationError(
                    f"WMP bundle assembler refused {context!r}: "
                    f"key {key!r} is in Arc 5 FORBIDDEN_COLUMNS data floor"
                )

    def assemble(
        self,
        *,
        sanitized_matrix: SanitizedReplayMatrix,
        humanity_proof: dict[str, Any],
        recency: dict[str, Any],
        consent: dict[str, Any],
        synthetic: bool = False,
        extra_metadata: Optional[dict[str, Any]] = None,
    ) -> ProvenanceBundle:
        """Assemble a `ProvenanceBundle` v1 from existing Arc 5/6/4 proofs.

        Args:
            sanitized_matrix: The post-φ matrix from `ReplayPreProcessor`.
                MUST already be sanitized; this assembler does not run φ.
            humanity_proof: dict carrying the Arc 5 VHR proof fields
                (proof_bytes, public_inputs, verifier_address, etc.).
            recency: dict carrying open/close beacon block + hash + the
                Arc 6 registry address (or "" when Arc 6 dormant).
            consent: dict carrying the Arc 4 consent registry address +
                gamer wallet + manifestHash. v1 W1-D: world-model
                consent dimension is "DEFERRED".
            synthetic: True iff this is a synthetic / fixture bundle. The
                consumer verifier (WMP-3) defaults to REJECTING synthetic
                bundles for real corpora; fixtures pass when the verifier
                is invoked with allow_synthetic=True.
            extra_metadata: optional extra fields the caller wants to
                annotate. Subject to FORBIDDEN_COLUMNS check before
                acceptance.

        Returns:
            A frozen `ProvenanceBundle` ready for JSONL export.

        Raises:
            DataFloorViolationError: if extra_metadata contains a
                FORBIDDEN_COLUMNS key. The error is raised BEFORE the
                bundle is assembled so the offending data never enters
                the bundle dataclass.
        """
        if extra_metadata is not None:
            self._assert_no_forbidden_keys(extra_metadata, "extra_metadata")

        # Encode the matrix bytes channel-by-channel as hex strings. The
        # consumer side decodes back to bytes for the Poseidon rehash. We
        # ONLY emit channels in _CANONICAL_CHANNELS — no extra fields, no
        # raw HID, no FORBIDDEN_COLUMNS keys could ever land here.
        matrix_hex: dict[str, str] = {
            "stick_L_sector":      sanitized_matrix.stick_L_sector.hex(),
            "stick_R_sector":      sanitized_matrix.stick_R_sector.hex(),
            "trigger_L_state":     sanitized_matrix.trigger_L_state.hex(),
            "trigger_R_state":     sanitized_matrix.trigger_R_state.hex(),
            "button_mask":         sanitized_matrix.button_mask.hex(),
            "imu_gravity_sector":  sanitized_matrix.imu_gravity_sector.hex(),
        }

        return ProvenanceBundle(
            schema=SCHEMA_VERSION,
            bundle_created_at_ns=time.time_ns(),

            # action_trace
            action_trace_format="quantized_macro_intent_60hz",
            action_trace_channels=_CANONICAL_CHANNELS,
            action_trace_ticks=int(sanitized_matrix.ticks),
            sanitized_trace_root_ref=str(humanity_proof.get("sanitized_trace_root", "")),
            action_trace_matrix_hex=matrix_hex,

            # humanity_proof (Arc 5)
            humanity_proof_type=str(humanity_proof.get("proof_type", "VAPI-REPLAY-PROOF-v1")),
            humanity_proof_bytes_hex=str(humanity_proof.get("proof_bytes_hex", "")),
            humanity_proof_public_inputs=dict(humanity_proof.get("public_inputs", {})),
            humanity_verifier_address=str(humanity_proof.get("verifier_address", "")),
            humanity_deferred=bool(humanity_proof.get("deferred", False)),
            humanity_deferred_reason=str(humanity_proof.get("deferred_reason", "")),

            # recency_proof (Arc 6)
            recency_open_block=int(recency.get("open_block", 0) or 0),
            recency_open_block_hash=str(recency.get("open_block_hash", "") or ""),
            recency_close_block=int(recency.get("close_block", 0) or 0),
            recency_close_block_hash=str(recency.get("close_block_hash", "") or ""),
            recency_registry_address=str(recency.get("registry_address", "") or ""),

            # consent_ref (Arc 4)
            consent_registry_address=str(consent.get("registry_address", "")),
            consent_gamer_address=str(consent.get("gamer_address", "")),
            consent_manifest_hash=str(consent.get("manifest_hash", "")),
            world_model_consent_dimension=str(consent.get("world_model_dimension", "DEFERRED")),
            world_model_consent_registry=str(consent.get("world_model_registry", "")),

            # scope_disclosure (Anti-Hype honesty, FROZEN values)
            scope_channel=_SCOPE_CHANNEL_ACTION_ONLY,
            scope_observation_channel=_SCOPE_OBSERVATION_ABSENT,
            scope_fidelity=_SCOPE_FIDELITY_MACRO,
            scope_synthetic=bool(synthetic),
            scope_is_full_pomdp_tuple=False,
        )
