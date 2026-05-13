"""Tests for scripts/parallel_vpm_anchor.py.

Validates the triple-gate authorization + manifest-parse logic. Does
not exercise chain.anchor_vpm itself (covered by test_phase_o4_anchor_vpm).

T-PARALLEL-VPM-1: gates pass when env+confirm aligned
T-PARALLEL-VPM-2: missing CHAIN_SUBMISSION_PAUSED=false -> gate 1 FAIL
T-PARALLEL-VPM-3: missing OPERATOR_VPM_ANCHOR_AUTHORIZED -> gate 2 FAIL
T-PARALLEL-VPM-4: missing --confirm -> gate 3 FAIL
T-PARALLEL-VPM-5: missing manifest file -> exit 3
T-PARALLEL-VPM-6: malformed JSON manifest -> exit 3
T-PARALLEL-VPM-7: unknown schema -> exit 3
T-PARALLEL-VPM-8: zkba-schema manifest rejected (use parallel_zkba_anchor)
T-PARALLEL-VPM-9: vpm-schema without zkba_manifest_hash_hex -> exit 3
T-PARALLEL-VPM-10: full happy path parse returns valid manifest
T-PARALLEL-VPM-11: O2 / O3 env var carry-over CANNOT satisfy gate 2
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "parallel_vpm_anchor.py"

if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("vpm_anchor_cer", SCRIPT_PATH)
vpm_anchor_cer = importlib.util.module_from_spec(_spec)  # type: ignore
sys.modules["vpm_anchor_cer"] = vpm_anchor_cer
_spec.loader.exec_module(vpm_anchor_cer)  # type: ignore


@pytest.fixture
def _clear_env(monkeypatch):
    """Clear the three env vars that this script + parallel_o2/o3
    scripts read. Prevents cross-test contamination."""
    monkeypatch.delenv("CHAIN_SUBMISSION_PAUSED", raising=False)
    monkeypatch.delenv("OPERATOR_VPM_ANCHOR_AUTHORIZED", raising=False)
    monkeypatch.delenv("OPERATOR_INITIATIVE_O2_AUTHORIZED", raising=False)
    monkeypatch.delenv("OPERATOR_INITIATIVE_O3_AUTHORIZED", raising=False)


def _make_args(confirm: bool = True):
    class _A:
        pass
    a = _A()
    a.confirm = confirm
    return a


def _vpm_manifest(tmp_path: Path) -> Path:
    """Write a minimal vapi-vpm-artifact-v1 manifest."""
    manifest = {
        "schema": "vapi-vpm-artifact-v1",
        "vpm_id": "MARKET-LISTING-v1",
        "zkba_class": 7,
        "proof_weight": 6,
        "visual_state": "live",
        "capture_mode": "live",
        "integrity_label_hash_hex": "ab" * 32,
        "wrapper_schema": "vapi-vpm-manifest-v1",
        "zkba_manifest_hash_hex": "1649f2803e0e3207f93fb1daac25d71d579ba3150d9d15317b97fe0e65a70d5f",
        "output_path": "test.html",
        "output_hash_hex": "5b09a65e64f13026461ef5ea7aff701f8840f1c1e5202f60bb8f88a7474da5cb",
        "input_commitment_hex": "cd" * 32,
        "compiler_version": "0.1.0",
        "ts_ns": 1778900000000000000,
    }
    p = tmp_path / "test_vpm.manifest.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


# ---- T-PARALLEL-VPM-1: all gates aligned -> pass --------------------

def test_t_parallel_vpm_1_all_gates_pass(_clear_env, monkeypatch):
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "false")
    monkeypatch.setenv("OPERATOR_VPM_ANCHOR_AUTHORIZED", "true")
    ok, reason = vpm_anchor_cer.check_gates(_make_args(confirm=True))
    assert ok, reason
    assert "all three gates aligned" in reason


# ---- T-PARALLEL-VPM-2: gate 1 FAIL when kill-switch held -----------

def test_t_parallel_vpm_2_kill_switch_held(_clear_env, monkeypatch):
    # CHAIN_SUBMISSION_PAUSED unset (defaults to 'true' guarded read)
    monkeypatch.setenv("OPERATOR_VPM_ANCHOR_AUTHORIZED", "true")
    ok, reason = vpm_anchor_cer.check_gates(_make_args(confirm=True))
    assert not ok
    assert "Gate 1 FAIL" in reason


# ---- T-PARALLEL-VPM-3: gate 2 FAIL without intent ------------------

def test_t_parallel_vpm_3_intent_missing(_clear_env, monkeypatch):
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "false")
    ok, reason = vpm_anchor_cer.check_gates(_make_args(confirm=True))
    assert not ok
    assert "Gate 2 FAIL" in reason


# ---- T-PARALLEL-VPM-4: gate 3 FAIL without --confirm ---------------

def test_t_parallel_vpm_4_no_confirm_flag(_clear_env, monkeypatch):
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "false")
    monkeypatch.setenv("OPERATOR_VPM_ANCHOR_AUTHORIZED", "true")
    ok, reason = vpm_anchor_cer.check_gates(_make_args(confirm=False))
    assert not ok
    assert "Gate 3 FAIL" in reason


# ---- T-PARALLEL-VPM-5: missing manifest file -> exit 3 -------------

def test_t_parallel_vpm_5_missing_manifest():
    nonexistent = Path("/nonexistent/path.manifest.json")
    manifest, err = vpm_anchor_cer.parse_manifest(nonexistent)
    assert manifest is None
    assert "does not exist" in err


# ---- T-PARALLEL-VPM-6: malformed JSON -> exit 3 --------------------

def test_t_parallel_vpm_6_malformed_json(tmp_path):
    p = tmp_path / "bad.manifest.json"
    p.write_text("{not json", encoding="utf-8")
    manifest, err = vpm_anchor_cer.parse_manifest(p)
    assert manifest is None
    assert "parse failed" in err


# ---- T-PARALLEL-VPM-7: unknown schema -> exit 3 --------------------

def test_t_parallel_vpm_7_unknown_schema(tmp_path):
    p = tmp_path / "weird.manifest.json"
    p.write_text(
        json.dumps({"schema": "vapi-imposter-v1", "ts_ns": 1, "output_hash_hex": "a" * 64}),
        encoding="utf-8",
    )
    manifest, err = vpm_anchor_cer.parse_manifest(p)
    assert manifest is None
    assert "not vapi-vpm-artifact-v1" in err


# ---- T-PARALLEL-VPM-8: zkba-schema manifest rejected ----------------

def test_t_parallel_vpm_8_zkba_manifest_rejected(tmp_path):
    """A vapi-zkba-manifest-v1 manifest should be rejected with a clear
    redirect to parallel_zkba_anchor.py. This script handles VPM
    wrappers only."""
    p = tmp_path / "zkba.manifest.json"
    p.write_text(json.dumps({
        "schema": "vapi-zkba-manifest-v1",
        "ts_ns": 1778900000000000000,
        "output_hash_hex": "a" * 64,
    }), encoding="utf-8")
    manifest, err = vpm_anchor_cer.parse_manifest(p)
    assert manifest is None
    assert "parallel_zkba_anchor.py" in err


# ---- T-PARALLEL-VPM-9: vpm-schema missing zkba_manifest_hash_hex ---

def test_t_parallel_vpm_9_vpm_missing_zkba_hash(tmp_path):
    p = tmp_path / "incomplete.manifest.json"
    # vpm-form manifest missing the upstream zkba hash field.
    p.write_text(json.dumps({
        "schema": "vapi-vpm-artifact-v1",
        "ts_ns": 1778900000000000000,
        "output_hash_hex": "a" * 64,
        # zkba_manifest_hash_hex absent
    }), encoding="utf-8")
    manifest, err = vpm_anchor_cer.parse_manifest(p)
    assert manifest is None
    assert "zkba_manifest_hash_hex" in err


# ---- T-PARALLEL-VPM-10: happy path parse ---------------------------

def test_t_parallel_vpm_10_happy_path_parse(tmp_path):
    p = _vpm_manifest(tmp_path)
    manifest, err = vpm_anchor_cer.parse_manifest(p)
    assert manifest is not None
    assert err == ""
    assert manifest["schema"] == "vapi-vpm-artifact-v1"
    assert manifest["zkba_manifest_hash_hex"].startswith("1649f")


# ---- T-PARALLEL-VPM-11: O2/O3 env carry-over CANNOT satisfy gate 2 -

def test_t_parallel_vpm_11_o2_o3_env_carryover_blocked(
    _clear_env, monkeypatch,
):
    """If operator has residual O2 or O3 authorization env vars in
    their shell from a prior ceremony, those MUST NOT satisfy the VPM
    gate 2 — the script reads OPERATOR_VPM_ANCHOR_AUTHORIZED specifically."""
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "false")
    monkeypatch.setenv("OPERATOR_INITIATIVE_O2_AUTHORIZED", "true")
    monkeypatch.setenv("OPERATOR_INITIATIVE_O3_AUTHORIZED", "true")
    # OPERATOR_VPM_ANCHOR_AUTHORIZED NOT set
    ok, reason = vpm_anchor_cer.check_gates(_make_args(confirm=True))
    assert not ok
    assert "Gate 2 FAIL" in reason
    assert "OPERATOR_VPM_ANCHOR_AUTHORIZED" in reason
