"""A2A-CDM Round 07 - forge execution of grok's Round-06 DAG attacks (T3).

T3-A3 (session re-bind) was a CONFIRMED REAL GAP: a valid PoSP listed under a fabricated
index session_id verified GREEN. Fixed: an artifact carrying a session_id must equal its
index entry. T3-A2/A5 confirm existing rails hold; T3-A8 pins the offline-WMP ceiling text.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = REPO_ROOT / "scripts" / "verify_provenance_dag.py"
_INDEX = REPO_ROOT / "audits" / "provenance_dag_index_2026-07-12.json"


def _run(index_path):
    return subprocess.run([sys.executable, str(_SCRIPT), str(index_path)],
                          capture_output=True, text=True, cwd=str(REPO_ROOT))


def _write(tmp_path, idx):
    p = tmp_path / "idx.json"
    p.write_text(json.dumps(idx), encoding="utf-8")
    return p


def _idx():
    return json.loads(_INDEX.read_text(encoding="utf-8"))


# -- T3-A3: valid PoSP listed under a LIED session_id (was a real gap) ------------------

def test_t3_a3_session_rebind_caught(tmp_path):
    idx = _idx()
    idx["sessions"][0]["session_id"] = "a_fabricated_session_id_timeline_lie"
    r = _run(_write(tmp_path, idx))
    assert r.returncode == 1
    assert "session_id" in r.stdout and "!= index session" in r.stdout


# -- T3-A2: cross-device grafting (PoSP device_id != index) - existing rail holds -------

def test_t3_a2_cross_device_graft_caught(tmp_path):
    idx = _idx()
    idx["device_id"] = "0" * 64                         # index claims a device the PoSP isn't
    r = _run(_write(tmp_path, idx))
    assert r.returncode == 1
    assert "device_id" in r.stdout


# -- T3-A8: the offline-WMP ceiling must ship with the verdict --------------------------

def test_t3_a8_offline_wmp_ceiling_printed():
    r = _run(_INDEX)
    assert r.returncode == 0                            # real index still verifies clean
    assert "OFFLINE defaults" in r.stdout               # not the full 5/5 crypto bar
    assert "selective omission NOT detected" in r.stdout


# -- regression: the real, honest M17 index still verifies clean after the fix ----------

def test_real_index_still_verifies_after_r07():
    r = _run(_INDEX)
    assert r.returncode == 0
    assert "DAG VERIFIED" in r.stdout
