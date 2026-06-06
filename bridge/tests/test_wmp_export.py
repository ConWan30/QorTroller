"""WMP-2 exporter tests.

T-WMP2-1  default invocation REFUSES real export (deferred-export guard)
          and exits 2 with a clear DEFERRED message
T-WMP2-2  --allow-fixtures without --fixture-corpus fails clean
T-WMP2-3  fixture path writes a JSONL + corpus_manifest.json index
T-WMP2-4  idempotent: re-running the same fixture corpus skips duplicates
T-WMP2-5  --dry-run does NOT write the JSONL but reports written count
T-WMP2-6  corpus_manifest.json index entries carry NO PII (no wallet,
          no device_id, no session_id beyond the bundle hash)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
WMP_EXPORT = REPO_ROOT / "scripts" / "wmp_export.py"
VENV_PY    = REPO_ROOT / "bridge" / ".venv" / "Scripts" / "python.exe"


def _venv() -> str:
    return str(VENV_PY) if VENV_PY.exists() else sys.executable


def _fixture_corpus(tmp_path: Path) -> Path:
    """Build a tiny fixture corpus with two distinct bundles."""
    sys.path.insert(0, str(REPO_ROOT / "bridge"))
    from vapi_bridge.wmp import BundleAssembler
    from vapi_bridge.replay_proof_pipeline.pre_processor import SanitizedReplayMatrix
    asm = BundleAssembler(); asm.__post_init__()

    def m(sid: str, ticks: int):
        return SanitizedReplayMatrix(
            session_id=sid, ticks=ticks,
            stick_L_sector=bytes(ticks), stick_R_sector=bytes(ticks),
            trigger_L_state=bytes(ticks), trigger_R_state=bytes(ticks),
            button_mask=bytes(ticks * 2), imu_gravity_sector=bytes(ticks),
            poac_chain_root=bytes(32), vhp_token_id=2,
            humanity_prob_floor=0.71, session_verdict="HUMAN",
        )

    hp = {
        "proof_type":          "VAPI-REPLAY-PROOF-v1",
        "proof_bytes_hex":     "0xaa" * 64,
        "public_inputs":       {"sanitizedTraceRoot": "143000"},
        "verifier_address":    "0x5182372d1D033db0c9230843DFDE606733D5F91B",
        "sanitized_trace_root": "143000",
    }
    rec = {
        "open_block": 1, "open_block_hash": "0x" + "11" * 32,
        "close_block": 2, "close_block_hash": "0x" + "22" * 32,
        "registry_address": "",
    }
    cons = {
        "registry_address": "0x5F7c8068D0e61818FCD613D47e68a9Ea906a2743",
        "gamer_address":    "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692",
        "manifest_hash":    "0x" + "ab" * 32,
    }

    b1 = asm.assemble(sanitized_matrix=m("sid-1", 4),
                      humanity_proof=hp, recency=rec, consent=cons,
                      synthetic=True)
    b2 = asm.assemble(sanitized_matrix=m("sid-2", 8),
                      humanity_proof=hp, recency=rec, consent=cons,
                      synthetic=True)

    corpus_dir = tmp_path / "fixtures"
    corpus_dir.mkdir(parents=True)
    jsonl = corpus_dir / "wmp_corpus.jsonl"
    with jsonl.open("w", encoding="utf-8") as f:
        f.write(json.dumps(b1.to_dict(), separators=(",", ":")) + "\n")
        f.write(json.dumps(b2.to_dict(), separators=(",", ":")) + "\n")
    return corpus_dir


def test_wmp2_1_default_refuses_real_export(tmp_path):
    out = tmp_path / "out"
    r = subprocess.run(
        [_venv(), str(WMP_EXPORT), "--out", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "DEFERRED" in r.stderr
    assert "world-model consent" in r.stderr
    assert not (out / "wmp_corpus.jsonl").exists()


def test_wmp2_2_allow_fixtures_without_path_fails(tmp_path):
    out = tmp_path / "out"
    r = subprocess.run(
        [_venv(), str(WMP_EXPORT), "--out", str(out), "--allow-fixtures"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2
    assert "fixture-corpus" in r.stderr


def test_wmp2_3_fixture_path_writes_jsonl_and_index(tmp_path):
    corpus = _fixture_corpus(tmp_path)
    out = tmp_path / "out"
    r = subprocess.run(
        [_venv(), str(WMP_EXPORT),
         "--out", str(out),
         "--allow-fixtures",
         "--fixture-corpus", str(corpus)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    summary = json.loads(r.stdout)
    assert summary["written"] == 2
    assert summary["skipped"] == 0
    # JSONL + index land
    assert (out / "wmp_corpus.jsonl").exists()
    assert (out / "corpus_manifest.json").exists()
    # JSONL has 2 lines
    assert len((out / "wmp_corpus.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_wmp2_4_idempotent_skips_duplicates(tmp_path):
    corpus = _fixture_corpus(tmp_path)
    out = tmp_path / "out"
    # First run writes 2
    subprocess.run(
        [_venv(), str(WMP_EXPORT),
         "--out", str(out),
         "--allow-fixtures",
         "--fixture-corpus", str(corpus)],
        capture_output=True, text=True,
    )
    # Second run skips both
    r2 = subprocess.run(
        [_venv(), str(WMP_EXPORT),
         "--out", str(out),
         "--allow-fixtures",
         "--fixture-corpus", str(corpus)],
        capture_output=True, text=True,
    )
    s2 = json.loads(r2.stdout)
    assert s2["written"] == 0
    assert s2["skipped"] == 2


def test_wmp2_5_dry_run_does_not_write(tmp_path):
    corpus = _fixture_corpus(tmp_path)
    out = tmp_path / "out"
    r = subprocess.run(
        [_venv(), str(WMP_EXPORT),
         "--out", str(out),
         "--allow-fixtures",
         "--fixture-corpus", str(corpus),
         "--dry-run"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0
    s = json.loads(r.stdout)
    assert s["dry_run"] is True
    assert s["written"] == 2
    # No JSONL on disk
    assert not (out / "wmp_corpus.jsonl").exists()


def test_wmp2_6_index_carries_no_pii(tmp_path):
    corpus = _fixture_corpus(tmp_path)
    out = tmp_path / "out"
    subprocess.run(
        [_venv(), str(WMP_EXPORT),
         "--out", str(out),
         "--allow-fixtures",
         "--fixture-corpus", str(corpus)],
        capture_output=True, text=True,
    )
    idx = json.loads((out / "corpus_manifest.json").read_text(encoding="utf-8"))
    for entry in idx["entries"]:
        # PII-redaction invariant: no gamer wallet, no device_id, no
        # session_id (the bundle_hash is the only opaque identifier).
        assert "gamer_address" not in entry
        assert "device_id" not in entry
        assert "session_id" not in entry
        assert "consent_gamer_address" not in entry
        assert "wallet" not in str(entry).lower()
