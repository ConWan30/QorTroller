"""WMP Phase-2 real-export path tests (INC-3).

Pins: env-unset consent gate stays hard-False (v1 byte-identical) · --real REFUSES when the
consent view-call is not True · a mocked-granted consent + real-shaped inputs assembles ONE
non-synthetic bundle whose strata extra_metadata rode through the DataFloorViolationError
guard · a forbidden extra key still raises · missing-anchored-recency ships the honest empty
registry (deferred), never fabricated. No network: consent gate mocked at module level.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "bridge"))

import wmp_export  # noqa: E402


def test_consent_gate_env_unset_is_hard_false(monkeypatch):
    monkeypatch.delenv("WORLD_MODEL_CONSENT_REGISTRY_ADDRESS", raising=False)
    assert wmp_export.world_model_consent_present("0x" + "0c" * 20) is False
    assert wmp_export.world_model_consent_present("") is False


def test_real_refused_without_consent(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WORLD_MODEL_CONSENT_REGISTRY_ADDRESS", raising=False)
    rc = wmp_export.main(["--out", str(tmp_path), "--real", "--gamer", "0x" + "0c" * 20])
    assert rc == 2
    assert "NOT granted" in capsys.readouterr().err


def _write_real_inputs(tmp_path):
    ticks = 4
    priv = {"poacChainRoot": "0x" + "11" * 32,
            "matrix": {"ticks": ticks,
                       "stick_L_sector": "00" * ticks, "stick_R_sector": "01" * ticks,
                       "trigger_L_state": "02" * ticks, "trigger_R_state": "03" * ticks,
                       "button_mask": "00" * (2 * ticks), "imu_gravity_sector": "04" * ticks}}
    proof = {"pi_a": ["1", "2", "1"], "pi_b": [["3", "4"], ["5", "6"], ["1", "0"]],
             "pi_c": ["7", "8", "1"], "protocol": "groth16", "curve": "bn128"}
    public = ["9", "10", "11", "0", "700", "12"]
    mp, pp, up = tmp_path / "priv.json", tmp_path / "proof.json", tmp_path / "public.json"
    mp.write_text(json.dumps(priv)); pp.write_text(json.dumps(proof)); up.write_text(json.dumps(public))
    return mp, pp, up


def _real_args(tmp_path, mp, pp, up, **extra):
    args = ["--out", str(tmp_path / "out"), "--real", "--gamer", "0x" + "0c" * 20,
            "--matrix", str(mp), "--vhr-proof", str(pp), "--vhr-public", str(up),
            "--session-id", "m17_test"]
    for k, v in extra.items():
        args += [f"--{k.replace('_', '-')}", str(v)]
    return args


def test_real_exports_one_bundle_with_strata_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(wmp_export, "world_model_consent_present", lambda g: True)
    mp, pp, up = _write_real_inputs(tmp_path)
    rc = wmp_export.main(_real_args(tmp_path, mp, pp, up, strata_band="AUTHORED_HIGH_DENSITY"))
    assert rc == 0
    lines = (tmp_path / "out" / "wmp_corpus.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    b = json.loads(lines[0])
    assert b["scope_synthetic"] is False                       # REAL bundle
    assert b["world_model_consent_dimension"] == "GRANTED"
    assert b["humanity_proof_public_inputs"]["sanitizedTraceRoot"] == "10"
    assert len(b["humanity_proof_bytes_hex"]) == 512           # 256-byte ABI wire
    assert b["extra_metadata"]["skill_strata_band"] == "AUTHORED_HIGH_DENSITY"   # UC-2 hook rode
    assert b["recency_registry_address"] == ""                 # honest deferral (no anchored pair)


def test_real_forbidden_extra_key_still_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(wmp_export, "world_model_consent_present", lambda g: True)
    mp, pp, up = _write_real_inputs(tmp_path)
    from l9_presence import skill_strata
    monkeypatch.setattr(skill_strata, "wmp_metadata",
                        lambda band: {"l4_mahalanobis_distance": 1.0})   # forbidden column
    from vapi_bridge.wmp.bundle_assembler import DataFloorViolationError
    with pytest.raises(DataFloorViolationError):
        wmp_export.main(_real_args(tmp_path, mp, pp, up, strata_band="AUTHORED_STANDARD"))


def test_real_with_anchored_recency_carries_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(wmp_export, "world_model_consent_present", lambda g: True)
    mp, pp, up = _write_real_inputs(tmp_path)
    rc = wmp_export.main(_real_args(
        tmp_path, mp, pp, up,
        recency_open=45026880, recency_open_hash="0x" + "a8" * 32,
        recency_close=45027008, recency_close_hash="0x" + "b9" * 32))
    assert rc == 0
    b = json.loads((tmp_path / "out" / "wmp_corpus.jsonl").read_text().strip())
    assert b["recency_open_block"] == 45026880
    assert b["recency_registry_address"].startswith("0x9624")  # the LIVE Arc 6 registry
