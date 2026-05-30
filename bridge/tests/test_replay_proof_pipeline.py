"""Data Economy Arc 5 Commit 4 — VAPIReplayProofPipeline orchestrator suite.

Covers every branch of package_session: dormant config, missing session, no
consent / consent-says-no, wrong verdict, below-floor humanity, deferred
prover, built-but-no-verifier, full success. Plus the listing-payload shape
and the pending-proofs query surface.

All tests are deterministic and use in-memory stubs — no chain RPC, no
snarkjs, no circomlibjs.
"""

import asyncio
from dataclasses import dataclass

import pytest

from bridge.vapi_bridge.replay_proof_pipeline import (
    DeferredProver,
    ProofResult,
    SanitizedReplayMatrix,
    VAPIReplayProofPipeline,
    VHRProofPackage,
    VHR_OUTCOME_ABORTED_NO_SESSION,
    VHR_OUTCOME_DEFERRED_HUMANITY,
    VHR_OUTCOME_DEFERRED_NO_CONSENT,
    VHR_OUTCOME_DEFERRED_NO_FRAMES,
    VHR_OUTCOME_DEFERRED_VERDICT,
    VHR_OUTCOME_DISABLED,
    VHR_OUTCOME_PROOF_BUILT,
    VHR_OUTCOME_PROOF_BUILT_NO_VERIFIER,
    VHR_OUTCOME_PROOF_DEFERRED,
)


# ── test stubs ──────────────────────────────────────────────────────────────

@dataclass
class _Cfg:
    replay_proof_pipeline_enabled: bool = True
    replay_proof_verifier_address: str = ""


class _ChainStub:
    """Mimics ChainClient.get_consent_manifest — async, dict-returning."""
    def __init__(self, manifest: dict | None):
        self._m = manifest

    async def get_consent_manifest(self, gamer_address: str) -> dict:
        return dict(self._m) if self._m is not None else {}


class _Store:
    def __init__(self, session: dict | None = None):
        self._session = session
        self.audit_writes: list[dict] = []

    def get_curator_session_aggregate(self, sid: str) -> dict | None:
        if self._session is None:
            return None
        return dict(self._session, session_id=sid)

    def record_curator_packaging_action(self, entry: dict) -> None:
        self.audit_writes.append(dict(entry))


class _PreProcessorStub:
    """Returns a fixed SanitizedReplayMatrix regardless of input — the
    pre-processor's correctness is covered by Commit 1's suite."""
    def __init__(self, *, ticks: int = 3):
        self._ticks = ticks

    def process_session(self, session_id, **_kwargs):
        return SanitizedReplayMatrix(
            session_id=session_id,
            ticks=self._ticks,
            stick_L_sector=bytes(self._ticks),
            stick_R_sector=bytes(self._ticks),
            trigger_L_state=bytes(self._ticks),
            trigger_R_state=bytes(self._ticks),
            button_mask=bytes(self._ticks * 2),
            imu_gravity_sector=bytes(self._ticks),
            poac_chain_root=bytes(32),
            vhp_token_id=2,
            humanity_prob_floor=0.92,
            session_verdict="HUMAN",
        )


class _FakeProver:
    """Returns a non-empty proof with stub commitments — covers the success
    path without circomlibjs / snarkjs."""
    def is_available(self) -> bool:
        return True

    def prove(self, **_kwargs) -> ProofResult:
        return ProofResult(
            proof_bytes=b"\x01" * 256,
            replay_proof_token="0x" + "aa" * 32,
            sanitized_trace_root="123456789",
            vhp_commitment="987654321",
            humanity_threshold_scaled=700,
            deferred_reason=None,
        )


_BASE_MANIFEST = {
    "allow_replay_proofs":       True,
    "replay_humanity_threshold": 70,    # 0.70 on the ×100 scale
    "replay_quantization_bits":  4,
    "replay_require_verdict":    True,
    "autonomy_level":            1,
    "manifest_hash":             "0x" + "cc" * 32,
}

_BASE_SESSION = {
    "device_id":            "dev-abc",
    "gamer_address":        "0x" + "1" * 40,
    "verdict":              "HUMAN",
    "humanity_probability": 0.92,
    "vhp_token_id":         2,
    "session_nonce":        424242,
}


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_pipeline(
    *, manifest=None, session=None, prover=None,
    cfg_enabled=True, verifier_addr="",
):
    chain = _ChainStub(manifest if manifest is not None else _BASE_MANIFEST)
    store = _Store(session if session is not None else _BASE_SESSION)
    cfg = _Cfg(
        replay_proof_pipeline_enabled=cfg_enabled,
        replay_proof_verifier_address=verifier_addr,
    )
    return VAPIReplayProofPipeline(
        chain=chain, cfg=cfg, store=store,
        pre_processor=_PreProcessorStub(),
        prover=prover or DeferredProver(),
    )


# ── disabled / no-session ───────────────────────────────────────────────────

def test_disabled_returns_dormant_outcome():
    p = _make_pipeline(cfg_enabled=False)
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_DISABLED


def test_missing_session_aborts():
    chain = _ChainStub(_BASE_MANIFEST)
    store = _Store(session=None)   # explicit None — store returns no aggregate
    p = VAPIReplayProofPipeline(
        chain=chain, cfg=_Cfg(), store=store,
        pre_processor=_PreProcessorStub(), prover=DeferredProver(),
    )
    out = _run(p.package_session("nope"))
    assert out["outcome"] == VHR_OUTCOME_ABORTED_NO_SESSION


# ── consent gate ────────────────────────────────────────────────────────────

def test_no_manifest_defers_no_consent():
    p = _make_pipeline(manifest={})
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_DEFERRED_NO_CONSENT


def test_manifest_disallows_replay_proofs_defers():
    m = {**_BASE_MANIFEST, "allow_replay_proofs": False}
    p = _make_pipeline(manifest=m)
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_DEFERRED_NO_CONSENT


# ── verdict gate ────────────────────────────────────────────────────────────

def test_unclear_verdict_defers_when_required():
    s = {**_BASE_SESSION, "verdict": "UNCLEAR"}
    p = _make_pipeline(session=s)
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_DEFERRED_VERDICT


def test_unclear_verdict_proceeds_when_not_required():
    s = {**_BASE_SESSION, "verdict": "UNCLEAR"}
    m = {**_BASE_MANIFEST, "replay_require_verdict": False}
    p = _make_pipeline(session=s, manifest=m, prover=_FakeProver(),
                       verifier_addr="0x" + "f" * 40)
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_PROOF_BUILT


def test_certify_verdict_accepted():
    s = {**_BASE_SESSION, "verdict": "CERTIFY"}
    p = _make_pipeline(session=s, prover=_FakeProver(),
                       verifier_addr="0x" + "f" * 40)
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_PROOF_BUILT


# ── humanity floor ─────────────────────────────────────────────────────────

def test_below_floor_humanity_defers():
    s = {**_BASE_SESSION, "humanity_probability": 0.65}
    p = _make_pipeline(session=s)
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_DEFERRED_HUMANITY


def test_at_floor_humanity_proceeds():
    s = {**_BASE_SESSION, "humanity_probability": 0.70}
    p = _make_pipeline(session=s, prover=_FakeProver(),
                       verifier_addr="0x" + "f" * 40)
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_PROOF_BUILT


# ── pre-processor / prover stages ───────────────────────────────────────────

def test_zero_ticks_defers_no_frames():
    p = _make_pipeline()
    p._pre_processor = _PreProcessorStub(ticks=0)
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_DEFERRED_NO_FRAMES


def test_deferred_prover_returns_proof_deferred():
    p = _make_pipeline(prover=DeferredProver("ceremony pending"))
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_PROOF_DEFERRED
    assert out["extra"]["reason"] == "ceremony pending"
    # Honesty rail: package surfaces empty proof_bytes + deferred_reason.
    pkg = out["package"]
    assert pkg["is_deferred"] is True
    assert pkg["deferred_reason"] == "ceremony pending"
    assert pkg["proof_type"] == "VAPI-REPLAY-PROOF-v1"
    assert pkg["listing_type"] == "REPLAY_PROOF"


def test_built_but_no_verifier_surfaces_distinct_outcome():
    """Honesty: a proof built with no on-chain verifier wired is NOT the
    same as a fully verifier-bound proof. The package is returned but
    callers must know the verifier address gap exists."""
    p = _make_pipeline(prover=_FakeProver(), verifier_addr="")
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_PROOF_BUILT_NO_VERIFIER
    assert "replay_proof_verifier_address" in out["extra"]["reason"]


def test_built_with_verifier_full_success_and_package_shape():
    addr = "0x" + "f" * 40
    p = _make_pipeline(prover=_FakeProver(), verifier_addr=addr)
    out = _run(p.package_session("S1"))
    assert out["outcome"] == VHR_OUTCOME_PROOF_BUILT
    pkg = out["package"]
    # Required listing-payload fields (spec §6 + §7).
    for key in ("listing_type", "proof_type", "proof_token", "poac_chain_root",
                "consent_policy_hash", "humanity_threshold", "vhp_commitment",
                "sanitized_trace_root", "autonomy_level", "session_id",
                "created_at_ns"):
        assert key in pkg, f"package missing {key}"
    assert pkg["consent_policy_hash"] == _BASE_MANIFEST["manifest_hash"]
    assert pkg["proof_type"] == "VAPI-REPLAY-PROOF-v1"
    assert pkg["listing_type"] == "REPLAY_PROOF"
    assert pkg["humanity_threshold"] == 0.70
    assert pkg["is_deferred"] is False


# ── pending-proofs query surface ────────────────────────────────────────────

def test_list_pending_replay_proofs_filters_audit_log():
    p = _make_pipeline(prover=DeferredProver("pending"))
    _run(p.package_session("S1"))
    # Also run one that hits NO_CONSENT — that outcome is NOT pending.
    p2 = _make_pipeline(manifest={})
    out_nc = _run(p2.package_session("S2"))
    assert out_nc["outcome"] == VHR_OUTCOME_DEFERRED_NO_CONSENT

    pending_p = p.list_pending_replay_proofs()
    pending_nc = p2.list_pending_replay_proofs()
    assert len(pending_p) == 1
    assert pending_p[0]["session_id"] == "S1"
    assert pending_p[0]["outcome"] == VHR_OUTCOME_PROOF_DEFERRED
    assert pending_nc == []   # DEFERRED_NO_CONSENT not in the pending set


# ── audit-log write-through ─────────────────────────────────────────────────

def test_audit_log_persists_through_store():
    p = _make_pipeline(prover=DeferredProver("x"))
    _run(p.package_session("S1"))
    assert len(p.audit_log) == 1
    # Store mirror catches the same entry.
    assert len(p._store.audit_writes) == 1
    assert p._store.audit_writes[0]["session_id"] == "S1"


# ── listing payload pins the FROZEN proof-type discriminator ───────────────

def test_proof_type_pins_keccak_preimage():
    """The package's proof_type string is the SHA preimage of the contract's
    PROOF_TYPE constant — the off-chain string must stay byte-identical to
    what the contract pins (INV-VHR-003)."""
    pkg = VHRProofPackage(
        session_id="S1", proof_type="VAPI-REPLAY-PROOF-v1",
        listing_type="REPLAY_PROOF",
        replay_proof_token="0x" + "00" * 32,
        proof_bytes=b"", quantized_matrix=_PreProcessorStub().process_session("S1"),
        poac_chain_root="0x" + "00" * 32,
        consent_policy_hash="0x" + "00" * 32,
        humanity_threshold=0.70, vhp_commitment="0", sanitized_trace_root="0",
        autonomy_level=1,
    )
    assert pkg.to_listing_payload()["proof_type"] == "VAPI-REPLAY-PROOF-v1"
