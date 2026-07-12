"""A2A-CDM build (2) - provenance-DAG index + verifier regression pins.

The real M17 index must verify cold (exit 0); tampered artifact bytes must FAIL; a
session whose PoSP carries a different device_id must FAIL stability; and the verifier's
output stays ASCII-only (cp1252-safe for any reviewer console). The v0 ceiling (producer-
declared index; selective omission undetected) is pinned as printed text so it can never
silently vanish from the product surface.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = REPO_ROOT / "scripts" / "verify_provenance_dag.py"
_INDEX = REPO_ROOT / "audits" / "provenance_dag_index_2026-07-12.json"


def _run(*args):
    return subprocess.run([sys.executable, str(_SCRIPT), *args],
                          capture_output=True, text=True, cwd=str(REPO_ROOT))


def test_real_m17_index_verifies_cold():
    r = _run(str(_INDEX))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DAG VERIFIED" in r.stdout
    assert "selective omission NOT detected" in r.stdout   # the ceiling ships with the verdict


def test_tampered_artifact_bytes_fail(tmp_path):
    idx = json.loads(_INDEX.read_text(encoding="utf-8"))
    posp_rel = idx["sessions"][0]["artifacts"][0]["path"]
    doc = json.loads((REPO_ROOT / posp_rel).read_text(encoding="utf-8"))
    doc["verdict"] = "SYNCHRONIZED_FORGED"
    # re-point the index at a tampered copy WITHOUT updating its sha256
    # (absolute path: os.path.join(_REPO, abs) resolves to abs on all platforms)
    forged = tmp_path / "posp_forged.json"
    forged.write_text(json.dumps(doc), encoding="utf-8")
    idx["sessions"][0]["artifacts"][0]["path"] = str(forged)
    bad = tmp_path / "idx.json"
    bad.write_text(json.dumps(idx), encoding="utf-8")
    r = _run(str(bad))
    assert r.returncode == 1
    assert "FAIL" in r.stdout


def test_device_id_instability_fails(tmp_path):
    idx = json.loads(_INDEX.read_text(encoding="utf-8"))
    idx["device_id"] = "deadbeef" * 8            # index claims a DIFFERENT agency
    bad = tmp_path / "idx.json"
    bad.write_text(json.dumps(idx), encoding="utf-8")
    r = _run(str(bad))
    assert r.returncode == 1
    assert "device_id" in r.stdout


def test_dag_verifier_source_is_ascii_only():
    src = _SCRIPT.read_text(encoding="utf-8")
    non_ascii = sorted(set(c for c in src if ord(c) > 127))
    assert non_ascii == [], f"non-ASCII in dag verifier: {[hex(ord(c)) for c in non_ascii]}"
