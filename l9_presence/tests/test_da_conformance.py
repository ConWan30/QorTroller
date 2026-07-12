"""TRL-1 I2 - DA sidecar-pointer conformance tests.

The real M17 boundary record is CONFORMANT (events_roots are 32B commitments, no
inline scene payload). Synthetic forgeries that inline a scene payload where a
pointer belongs are caught as VIOLATION.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from l9_presence.da_conformance import (assess_da_conformance, _is_pointer,
                                        CONFORMANT, VIOLATION)

_M17 = REPO_ROOT / "audits" / "posp_record_match17_rp_fixb3_2026-07-08.json"
_SCRIPT = REPO_ROOT / "scripts" / "da_conformance_check.py"


def _base():
    return json.loads(_M17.read_text(encoding="utf-8"))


# -- the pointer predicate -------------------------------------------------

def test_is_pointer():
    assert _is_pointer("ab" * 32) is True                 # 64 hex
    assert _is_pointer("0x" + "cd" * 32) is True           # 0x + 64 hex
    assert _is_pointer(None) is True                       # honestly absent
    assert _is_pointer(["frame1", "frame2"]) is False      # a list is a payload
    assert _is_pointer("x" * 5000) is False                # oversized blob
    assert _is_pointer("nothex" * 11) is False


# -- the real record is conformant -----------------------------------------

def test_real_m17_is_conformant():
    res = assess_da_conformance(_base())
    assert res["status"] == CONFORMANT
    assert res["violations"] == []


def test_record_hashes_list_is_not_a_violation():
    """A list of short hashes is provenance metadata (pointers), not scene payload."""
    b = _base()
    assert isinstance(b["fusion"]["record_hashes"], list) and len(b["fusion"]["record_hashes"]) > 0
    assert assess_da_conformance(b)["status"] == CONFORMANT


# -- forgeries that inline a payload are caught ----------------------------

def test_root_inlined_as_list_is_violation():
    b = _base()
    b["events_roots"]["retina_perception_root"] = ["frame_a", "frame_b"]   # payload, not a pointer
    res = assess_da_conformance(b)
    assert res["status"] == VIOLATION
    assert any("retina_perception_root" in v for v in res["violations"])


def test_oversized_root_is_violation():
    b = _base()
    b["events_roots"]["kas_session_root"] = "d" * 4096      # a blob, not a 32B commitment
    assert assess_da_conformance(b)["status"] == VIOLATION


def test_inline_scene_payload_key_is_violation():
    b = _base()
    b["kas"]["raw_frame"] = "..."                          # a raw frame crossing the boundary
    res = assess_da_conformance(b)
    assert res["status"] == VIOLATION
    assert any("raw_frame" in v for v in res["violations"])


def test_data_uri_image_is_violation():
    b = _base()
    b["notes"] = ["data:image/png;base64,iVBORw0KGgo..."]
    assert assess_da_conformance(b)["status"] == VIOLATION


# -- portability + runner --------------------------------------------------

def test_ascii_only_sources():
    for f in (_SCRIPT, REPO_ROOT / "l9_presence" / "da_conformance.py"):
        src = f.read_text(encoding="utf-8")
        assert [c for c in src if ord(c) > 127] == [], f"non-ASCII in {f.name}"


def test_runner_conformant_on_m17():
    r = subprocess.run([sys.executable, str(_SCRIPT)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0
    assert "CONFORMANT" in r.stdout
