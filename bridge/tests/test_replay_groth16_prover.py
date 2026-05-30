"""Data Economy Arc 5 — Groth16Prover end-to-end test.

Covers:
  • artifacts_available() + missing_artifacts() reflect disk truth.
  • auto_prover() returns DeferredProver when artifacts absent and
    Groth16Prover when all present — no fabrication on either side.
  • Below-floor humanity returns ProofResult with deferred_reason BEFORE
    spawning any subprocess (fast-fail rail).

A FULL end-to-end real-proof test is gated on circomlibjs being installed
at the canonical artifact path. CI without those artifacts skips the heavy
test cleanly (it's a ceremony+circomlibjs gate, not a code gate); local
dev runs the full e2e path when the gate is open.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from bridge.vapi_bridge.replay_proof_pipeline import (
    DeferredProver,
    Groth16Prover,
    SanitizedReplayMatrix,
    artifacts_available,
    auto_prover,
    missing_artifacts,
)


# ── auto_prover routing ────────────────────────────────────────────────────

def test_auto_prover_returns_deferred_when_artifacts_missing(tmp_path, monkeypatch):
    """Point ZK_ARTIFACTS_DIR at an empty tempdir → all 5 prerequisites are
    missing → DeferredProver carries a clear reason."""
    from bridge.vapi_bridge.replay_proof_pipeline import groth16_prover as gp
    monkeypatch.setattr(gp, "_COMPUTE_INPUTS_JS",  tmp_path / "compute.js")
    monkeypatch.setattr(gp, "_WASM_PATH",          tmp_path / "x.wasm")
    monkeypatch.setattr(gp, "_ZKEY_PATH",          tmp_path / "x.zkey")
    monkeypatch.setattr(gp, "_VKEY_PATH",          tmp_path / "vk.json")
    monkeypatch.setattr(gp, "_CIRCOMLIBJS_PATH",   tmp_path / "circomlibjs")

    assert gp.artifacts_available() is False
    miss = gp.missing_artifacts()
    assert "compute_inputs_replay_proof.js" in miss
    assert "node_modules/circomlibjs" in miss

    prover = gp.auto_prover()
    assert isinstance(prover, DeferredProver)
    # Reason names a missing artifact so operators can act.
    assert "ceremony / helper artifacts absent" in prover._reason


def test_auto_prover_returns_groth16_when_all_artifacts_present(tmp_path, monkeypatch):
    """All five prereqs touched → auto_prover constructs Groth16Prover."""
    from bridge.vapi_bridge.replay_proof_pipeline import groth16_prover as gp
    for p, name in (
        (tmp_path / "compute.js",    "_COMPUTE_INPUTS_JS"),
        (tmp_path / "x.wasm",        "_WASM_PATH"),
        (tmp_path / "x.zkey",        "_ZKEY_PATH"),
        (tmp_path / "vk.json",       "_VKEY_PATH"),
    ):
        p.write_bytes(b"")
        monkeypatch.setattr(gp, name, p)
    (tmp_path / "circomlibjs").mkdir()
    monkeypatch.setattr(gp, "_CIRCOMLIBJS_PATH", tmp_path / "circomlibjs")
    assert gp.artifacts_available() is True
    prover = gp.auto_prover()
    assert isinstance(prover, Groth16Prover)


# ── Pre-flight (fast-fail before subprocess) ────────────────────────────────

def _stub_matrix(ticks: int = 3) -> SanitizedReplayMatrix:
    return SanitizedReplayMatrix(
        session_id="S1",
        ticks=ticks,
        stick_L_sector=bytes(range(ticks)),
        stick_R_sector=bytes(range(ticks)),
        trigger_L_state=bytes(range(ticks)),
        trigger_R_state=bytes(range(ticks)),
        button_mask=bytes(ticks * 2),
        imu_gravity_sector=bytes(ticks),
        poac_chain_root=bytes(32),
        vhp_token_id=2,
        humanity_prob_floor=0.92,
        session_verdict="HUMAN",
    )


def test_below_floor_humanity_fast_fails_no_subprocess(monkeypatch):
    """A below-floor humanity prob returns deferred_reason BEFORE any
    subprocess spawn. Guards against accidental refactor that pushes the
    floor check past the node + snarkjs work."""
    # Sentinel to detect if subprocess spawn happened.
    from bridge.vapi_bridge.replay_proof_pipeline import groth16_prover as gp
    spawned = {"node": False, "snarkjs": False}

    def _no_node(*a, **k):
        spawned["node"] = True
        raise AssertionError("node subprocess must not spawn below-floor")

    def _no_snarkjs(*a, **k):
        spawned["snarkjs"] = True
        raise AssertionError("snarkjs subprocess must not spawn below-floor")

    monkeypatch.setattr(gp, "_run_node", _no_node)
    monkeypatch.setattr(gp, "_run_snarkjs", _no_snarkjs)

    prover = Groth16Prover()
    result = prover.prove(
        matrix=_stub_matrix(),
        humanity_probability=0.65, humanity_threshold=0.70,
        vhp_token_id=2, session_nonce=1,
    )
    assert result.proof_bytes == b""
    assert "humanity floor not cleared" in (result.deferred_reason or "")
    assert spawned == {"node": False, "snarkjs": False}


# ── End-to-end (gated on real artifacts) ───────────────────────────────────

@pytest.mark.skipif(
    not artifacts_available(),
    reason="Arc 5 ceremony zkey / wasm / circomlibjs not on disk — skip e2e",
)
def test_end_to_end_real_proof_against_ceremony_zkey(tmp_path):
    """Generate a REAL Groth16 proof against the 2026-05-30 ceremony zkey +
    wasm, parse the public.json, confirm shape matches snarkjs convention.

    Heavy test (~few seconds) — only runs when the operator has both the
    ceremony zkey AND `npm install` was done in zk_artifacts/.
    """
    prover = Groth16Prover()
    assert prover.is_available()

    result = prover.prove(
        matrix=_stub_matrix(ticks=3),
        humanity_probability=0.92,
        humanity_threshold=0.70,
        vhp_token_id=2,
        session_nonce=42,
    )
    assert result.deferred_reason is None, f"prove failed: {result.deferred_reason}"
    assert len(result.proof_bytes) == 256  # snarkjs Groth16 wire format
    assert result.replay_proof_token.startswith("0x")
    assert len(result.replay_proof_token) == 2 + 64  # 32B hex
    # Field-element decimals — must be non-empty digit strings.
    assert result.sanitized_trace_root.isdigit()
    assert int(result.sanitized_trace_root) > 0
    assert result.vhp_commitment.isdigit()
    assert int(result.vhp_commitment) > 0
    # Threshold pinned to ×1000 scaling.
    assert result.humanity_threshold_scaled == 700
