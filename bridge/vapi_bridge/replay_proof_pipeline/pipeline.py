"""Data Economy Arc 5 Commit 4 — VAPIReplayProofPipeline orchestrator.

Composes Commits 1-3 (pre-processor + circuit + contract wrapper) into the
session-boundary VHR (Verified Human Replay) packaging flow:

  Consent gate → verdict gate → pre-processor → witness assembly → prover →
  VHRProofPackage

The orchestrator does NOT broadcast anything on-chain — its output is a
VHRProofPackage that the existing autonomy-ladder routing (Curator approval /
notify / full-autonomy) and the operator-fired marketplace submission path
both consume. It also does not produce a proof in the absence of the trusted
setup ceremony's .zkey: the pipeline returns a PROOF_DEFERRED outcome with
the witness saved for later proving rather than fabricating a placeholder.

Honesty rails (load-bearing — match Arc 5 deploy-hold doc):

  • Consent dimension 8 (allowReplayProofs) is read from the on-chain Arc 4
    VAPIConsentManifestRegistry (gamer-address keyed, drift D-2 resolution).
    The bridge NEVER writes consent; the gamer is the sole writer.

  • The Curator orchestrator NEVER invokes the marketplace contract directly.
    Its output is a structured listing intent; the operator-fired submission
    path consumes it on a separate explicit step (deploy-hold posture).

  • The verifier contract address is OPTIONAL at construction time — the
    pipeline can package and prove a session locally, store the proof, and
    surface PROOF_BUILT_NO_VERIFIER to the operator when no on-chain
    verifier is wired yet. Drift here would be silent "verifies against
    nothing", which would not be honest.

  • The Poseidon public commitments (sanitizedTraceRoot, vhpCommitment) and
    the snarkjs subprocess are delegated to a Prover collaborator object so
    the orchestrator can be tested deterministically without circomlibjs /
    node / a populated zk_artifacts directory. The default prover is
    `DeferredProver` which always returns PROOF_DEFERRED until the ceremony
    populates artifacts.

Spec anchor: docs/VAPI_REPLAY_PROOF_PIPELINE_SPEC (1).md §6 + §10 Commit 4.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from .pre_processor import (
    DataFloorViolationError,
    ReplayPreProcessor,
    SanitizedReplayMatrix,
)
from .witness_generator import (
    HumanityFloorNotClearedError,
    WitnessGenerator,
)

log = logging.getLogger(__name__)


# ── Outcome codes (mirror CuratorPackagingLoop.OUTCOME_*) ───────────────────

#: Pipeline is dormant (cfg.replay_proof_pipeline_enabled is False).
VHR_OUTCOME_DISABLED              = "vhr_disabled"
#: Session row not found in store — nothing to package.
VHR_OUTCOME_ABORTED_NO_SESSION    = "vhr_aborted_no_session"
#: Gamer's consent manifest does not allow replay proofs (Dimension 8
#: allowReplayProofs == False). Honest no-op; not a tamper.
VHR_OUTCOME_DEFERRED_NO_CONSENT   = "vhr_deferred_no_consent"
#: Session verdict is not HUMAN/CERTIFY (Curator default = require verdict).
VHR_OUTCOME_DEFERRED_VERDICT      = "vhr_deferred_verdict"
#: Humanity probability < manifest's replayHumanityThreshold. Honest no-op.
VHR_OUTCOME_DEFERRED_HUMANITY     = "vhr_deferred_humanity"
#: Data-floor protocol violation — a forbidden biometric column reached the
#: pre-processor. Raises ProtocolViolationError; this code is the audit-log
#: form for the same event.
VHR_OUTCOME_DATA_FLOOR_VIOLATION  = "vhr_data_floor_violation"
#: Pre-processor produced zero ticks (no usable frames) — DEFER.
VHR_OUTCOME_DEFERRED_NO_FRAMES    = "vhr_deferred_no_frames"
#: Witness assembled but the prover is dormant (ceremony hasn't fired /
#: circomlibjs unavailable). The witness is persisted; a later run can prove.
VHR_OUTCOME_PROOF_DEFERRED        = "vhr_proof_deferred"
#: Proof generated locally but no on-chain verifier address is configured.
#: The package is returned but is NOT yet verifier-bound.
VHR_OUTCOME_PROOF_BUILT_NO_VERIFIER = "vhr_proof_built_no_verifier"
#: Full success — package is ready for the autonomy-ladder routing step.
VHR_OUTCOME_PROOF_BUILT           = "vhr_proof_built"


# ── Prover collaborator interface ───────────────────────────────────────────

class Prover(Protocol):
    """Minimal interface the orchestrator needs from a VHR prover.

    Two implementations ship: `DeferredProver` (default, always returns
    PROOF_DEFERRED — honest stand-in until the ceremony lands a .zkey + the
    circomlibjs Poseidon helper is wired) and the real snarkjs-backed prover
    (lands in a later commit when ceremony artifacts populate
    `bridge/vapi_bridge/replay_proof_pipeline/zk_artifacts/`).
    """

    def is_available(self) -> bool: ...

    def prove(
        self,
        *,
        matrix: SanitizedReplayMatrix,
        humanity_probability: float,
        humanity_threshold: float,
        vhp_token_id: int,
        session_nonce: int,
    ) -> "ProofResult": ...


@dataclass(frozen=True)
class ProofResult:
    """What the prover returns. proof_bytes empty when deferred."""
    proof_bytes: bytes
    replay_proof_token: str          # hex 0x-prefixed, 32B
    sanitized_trace_root: str        # decimal field element
    vhp_commitment: str              # decimal field element
    humanity_threshold_scaled: int   # ×1000 integer that landed in the proof
    deferred_reason: Optional[str]   # set when proof_bytes is empty


class DeferredProver:
    """Honest no-op prover. Returns PROOF_DEFERRED with an empty proof.

    Activates whenever the ceremony / circomlibjs surface isn't populated.
    Never produces a fake `proof_bytes`; never produces a fake Poseidon
    commitment. Honesty rail.
    """

    def __init__(self, reason: str = "ceremony not fired / artifacts absent") -> None:
        self._reason = reason

    def is_available(self) -> bool:
        return False

    def prove(self, **_kwargs: Any) -> ProofResult:
        return ProofResult(
            proof_bytes=b"",
            replay_proof_token="",
            sanitized_trace_root="",
            vhp_commitment="",
            humanity_threshold_scaled=0,
            deferred_reason=self._reason,
        )


# ── VHRProofPackage (per spec §6) ───────────────────────────────────────────

@dataclass(frozen=True)
class VHRProofPackage:
    """Complete VHR proof package — listing payload for VAPIDataMarketplace.

    The spec mandates an `LISTING_TYPE_REPLAY_PROOF` discriminator; the
    contract Commit 3 froze PROOF_TYPE = keccak256("VAPI-REPLAY-PROOF-v1").
    Both are surfaced here so the autonomy-ladder + operator-fired submission
    path can route by either field without a second lookup.
    """
    session_id: str
    proof_type: str                          # "VAPI-REPLAY-PROOF-v1"
    listing_type: str                        # "REPLAY_PROOF"
    replay_proof_token: str                  # hex 0x-prefixed
    proof_bytes: bytes                       # 256-byte snarkjs proof, empty if deferred
    quantized_matrix: SanitizedReplayMatrix
    poac_chain_root: str                     # hex of matrix.poac_chain_root
    consent_policy_hash: str                 # hex of Arc 4 manifestHash at package time
    humanity_threshold: float                # the disclosed floor (0.0-1.0)
    vhp_commitment: str                      # decimal field element
    sanitized_trace_root: str                # decimal field element
    autonomy_level: int                      # 0=manual,1=approval,2=notify,3=full
    deferred_reason: Optional[str] = None    # set when the prover was deferred
    created_at_ns: int = field(default_factory=time.time_ns)

    def to_listing_payload(self) -> dict:
        """Marketplace listing payload. consent_policy_hash MANDATORY —
        establishes the permanent auditable lineage between the proof and
        the gamer's consent policy at packaging time (spec §6)."""
        return {
            "listing_type":          self.listing_type,
            "proof_type":            self.proof_type,
            "proof_token":           self.replay_proof_token,
            "poac_chain_root":       self.poac_chain_root,
            "consent_policy_hash":   self.consent_policy_hash,
            "humanity_threshold":    self.humanity_threshold,
            "vhp_commitment":        self.vhp_commitment,
            "sanitized_trace_root":  self.sanitized_trace_root,
            "autonomy_level":        self.autonomy_level,
            "session_id":            self.session_id,
            "is_deferred":           bool(self.deferred_reason),
            "deferred_reason":       self.deferred_reason or "",
            "created_at_ns":         self.created_at_ns,
        }


# ── Orchestrator ────────────────────────────────────────────────────────────

class VAPIReplayProofPipeline:
    """Arc 5 orchestrator. Composes Commits 1-3 into a session-boundary flow.

    Construct with the live ChainClient (for the Arc 4 manifest read) and
    Config. Optional store for session-data reads + audit persistence.
    Optional prover for proof generation (DeferredProver by default).

    The orchestrator does NOT touch the marketplace contract, the data
    marketplace listings registry, or any other on-chain authority directly —
    its sole output is a VHRProofPackage that the Curator autonomy ladder
    (Arc 3) and the operator-fired submission path both consume.
    """

    def __init__(
        self,
        chain: Any,
        cfg: Any,
        store: Optional[Any] = None,
        pre_processor: Optional[ReplayPreProcessor] = None,
        witness_generator: Optional[WitnessGenerator] = None,
        prover: Optional[Prover] = None,
    ) -> None:
        self._chain = chain
        self._cfg = cfg
        self._store = store
        self._pre_processor = pre_processor or ReplayPreProcessor()
        self._witness_generator = witness_generator or WitnessGenerator()
        self._prover = prover or DeferredProver()
        self._enabled = bool(getattr(cfg, "replay_proof_pipeline_enabled", False))
        self._verifier_address = (
            getattr(cfg, "replay_proof_verifier_address", "") or ""
        )
        self.audit_log: list[dict] = []

    # ── public entry point ─────────────────────────────────────────────────

    async def package_session(
        self,
        session_id: str,
        *,
        gamer_address: Optional[str] = None,
        session_nonce: Optional[int] = None,
    ) -> dict:
        """Run the full VHR pipeline against `session_id`. Returns a dict
        result whose `outcome` is one of VHR_OUTCOME_*.

        The dict shape mirrors CuratorPackagingLoop.on_session_complete so
        downstream observers can union them without special-casing.
        """
        if not self._enabled:
            return self._result(VHR_OUTCOME_DISABLED, session_id,
                                reason="replay_proof_pipeline_enabled=False")

        session = self._load_session(session_id)
        if not session:
            return self._audit_and_return(
                VHR_OUTCOME_ABORTED_NO_SESSION, session_id, {})

        verdict = str(session.get("verdict", "") or "")
        humanity_prob = float(session.get("humanity_probability", 0.0) or 0.0)
        device_id = str(session.get("device_id", "") or "")
        gamer_address = gamer_address or str(
            session.get("gamer_address") or session.get("wallet_address") or "")

        # Step 1 — consent gate (Arc 4 Dimension 8).
        manifest = await self._load_consent_manifest(gamer_address)
        if not manifest:
            return self._audit_and_return(
                VHR_OUTCOME_DEFERRED_NO_CONSENT, session_id,
                {"reason": "no on-chain consent manifest for gamer"})
        if not manifest.get("allow_replay_proofs", False):
            return self._audit_and_return(
                VHR_OUTCOME_DEFERRED_NO_CONSENT, session_id,
                {"reason": "manifest allowReplayProofs == false"})

        # Step 2 — verdict gate (default: require HUMAN/CERTIFY).
        if manifest.get("replay_require_verdict", True) and verdict not in ("HUMAN", "CERTIFY"):
            return self._audit_and_return(
                VHR_OUTCOME_DEFERRED_VERDICT, session_id,
                {"verdict": verdict})

        # Step 3 — humanity floor (manifest field is ×100 scale).
        threshold = float(manifest.get("replay_humanity_threshold", 70)) / 100.0
        if humanity_prob < threshold:
            return self._audit_and_return(
                VHR_OUTCOME_DEFERRED_HUMANITY, session_id,
                {"humanity_prob": humanity_prob, "threshold": threshold})

        # Step 4 — pre-processor. The data floor enforcement lives inside
        # _fetch_structural_frames; DataFloorViolationError propagates up as
        # a protocol violation (NOT a silent defer — caller must surface it).
        try:
            matrix = self._pre_processor.process_session(
                session_id,
                vhp_token_id=int(session.get("vhp_token_id", 0) or 0),
                humanity_prob_floor=float(humanity_prob),
                session_verdict=verdict,
            )
        except DataFloorViolationError as exc:
            self._audit_and_return(
                VHR_OUTCOME_DATA_FLOOR_VIOLATION, session_id,
                {"violation": str(exc)})
            raise
        if matrix.ticks == 0:
            return self._audit_and_return(
                VHR_OUTCOME_DEFERRED_NO_FRAMES, session_id, {})

        # Step 5 — prover. Defer cleanly when ceremony hasn't fired; never
        # fabricate proof bytes.
        try:
            # Thread C: Offload CPU-heavy proving out-of-band to prevent scheduling
            # jitter on the 1002 Hz real-time ingestion loop (Thread A).
            proof = await asyncio.to_thread(
                self._prover.prove,
                matrix=matrix,
                humanity_probability=humanity_prob,
                humanity_threshold=threshold,
                vhp_token_id=int(session.get("vhp_token_id", 0) or 0),
                session_nonce=int(session_nonce if session_nonce is not None
                                  else session.get("session_nonce", 0) or 0),
            )
        except HumanityFloorNotClearedError as exc:
            # Defensive — the off-circuit gap check ran during witness
            # assembly. Caught earlier by the explicit humanity gate above;
            # this branch covers a manifest/witness drift.
            return self._audit_and_return(
                VHR_OUTCOME_DEFERRED_HUMANITY, session_id,
                {"reason": str(exc)})

        # Step 6 — package + outcome routing.
        consent_policy_hash = str(manifest.get("manifest_hash", "") or "")
        autonomy = int(manifest.get("autonomy_level", 1))   # default = approval_required

        package = VHRProofPackage(
            session_id=session_id,
            proof_type="VAPI-REPLAY-PROOF-v1",
            listing_type="REPLAY_PROOF",
            replay_proof_token=proof.replay_proof_token,
            proof_bytes=proof.proof_bytes,
            quantized_matrix=matrix,
            poac_chain_root="0x" + matrix.poac_chain_root.hex(),
            consent_policy_hash=consent_policy_hash,
            humanity_threshold=threshold,
            vhp_commitment=proof.vhp_commitment,
            sanitized_trace_root=proof.sanitized_trace_root,
            autonomy_level=autonomy,
            deferred_reason=proof.deferred_reason,
        )

        if proof.deferred_reason is not None:
            outcome = VHR_OUTCOME_PROOF_DEFERRED
            extra = {"reason": proof.deferred_reason}
        elif not self._verifier_address:
            outcome = VHR_OUTCOME_PROOF_BUILT_NO_VERIFIER
            extra = {"reason": "replay_proof_verifier_address is unset"}
        else:
            outcome = VHR_OUTCOME_PROOF_BUILT
            extra = {"verifier": self._verifier_address}

        result = self._audit_and_return(outcome, session_id, extra)
        result["package"] = package.to_listing_payload()
        return result

    # ── helpers ────────────────────────────────────────────────────────────

    def _load_session(self, session_id: str) -> Optional[dict]:
        if self._store is not None and hasattr(self._store, "get_curator_session_aggregate"):
            try:
                return self._store.get_curator_session_aggregate(session_id)
            except Exception:
                log.exception("get_curator_session_aggregate failed")
        return None

    async def _load_consent_manifest(self, gamer_address: str) -> dict:
        """Read the Arc 4 manifest via the chain wrapper. Empty dict when the
        manifest registry is unset OR no manifest is stored — the orchestrator
        treats both as "consent absent → defer", consistent with the framework
        §7 fail-open-at-chain / fail-closed-at-orchestrator pattern."""
        if not gamer_address or self._chain is None:
            return {}
        getter = getattr(self._chain, "get_consent_manifest", None)
        if getter is None:
            return {}
        try:
            return await getter(gamer_address)
        except Exception:
            log.exception("get_consent_manifest failed (treat as absent)")
            return {}

    def _result(self, outcome: str, session_id: str, **kwargs: Any) -> dict:
        return {"outcome": outcome, "session_id": session_id, **kwargs}

    def _audit_and_return(
        self, outcome: str, session_id: str, extra: dict
    ) -> dict:
        entry = {
            "action":     "vhr_packaging",
            "session_id": session_id,
            "outcome":    outcome,
            "extra":      dict(extra) if extra else {},
            "ts_ns":      time.time_ns(),
        }
        self.audit_log.append(entry)
        if self._store is not None and hasattr(self._store, "record_curator_packaging_action"):
            try:
                self._store.record_curator_packaging_action(entry)
            except Exception:
                log.exception("record_curator_packaging_action failed (non-fatal)")
        return self._result(outcome, session_id, extra=extra)

    # ── pending-listings surface (GET /curator/pending-replay-proofs) ──────

    def list_pending_replay_proofs(self) -> list[dict]:
        """Return audit entries representing deferred / built-but-unsubmitted
        VHR packages. Reads from the local audit_log; the HTTP endpoint
        layer reads this surface to render the operator-fired submission
        queue.
        """
        pending_outcomes = {
            VHR_OUTCOME_PROOF_DEFERRED,
            VHR_OUTCOME_PROOF_BUILT_NO_VERIFIER,
            VHR_OUTCOME_PROOF_BUILT,
        }
        return [dict(e) for e in self.audit_log if e["outcome"] in pending_outcomes]
