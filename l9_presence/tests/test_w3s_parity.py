"""TRL-1 I3 - W3bstream applet parity tests.

The real w3bstream surfaces are CONFORMANT (frame_grabbing/optical_capture pinned
false, applet validates never captures, W3S invariants pinned in gate + allowlist).
Synthetic regressions (a capture marker, a flipped flag, an unpinned invariant) are
caught as VIOLATION.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from l9_presence.w3s_parity import (assess_w3s_parity, check_sandbox_mechanisms,
                                    check_applet_validation_only, check_invariants_pinned,
                                    CONFORMANT, VIOLATION)

_SCRIPT = REPO_ROOT / "scripts" / "w3s_parity_check.py"
_GOOD_CONFIG = {"mechanisms": {"frame_grabbing": False, "optical_capture": False}}
_GOOD_APPLET = "const ANCHOR_CADENCE: u64 = 64;\npub extern \"C\" fn handle_poac_payload(...)"
_GOOD_GATE = "INV-W3S-001 INV-W3S-002 ... gate"
_GOOD_ALLOWLIST = '{"INV-W3S-001": "...", "INV-W3S-002": "..."}'


# -- per-surface checks ----------------------------------------------------

def test_mechanisms_conformant():
    assert check_sandbox_mechanisms(_GOOD_CONFIG) == []


def test_frame_grabbing_true_is_violation():
    bad = {"mechanisms": {"frame_grabbing": True, "optical_capture": False}}
    assert check_sandbox_mechanisms(bad)


def test_applet_capture_marker_is_violation():
    v = check_applet_validation_only(_GOOD_APPLET + "\nlet c = VideoCapture::new();")
    assert any("VideoCapture" in x for x in v)


def test_applet_without_validation_marker_is_violation():
    assert check_applet_validation_only("fn nothing() {}")


def test_invariant_unpinned_in_allowlist_is_violation():
    v = check_invariants_pinned(_GOOD_GATE, '{"INV-W3S-001": "..."}')   # 002 missing
    assert any("INV-W3S-002" in x and "allowlist" in x for x in v)


def test_combined_good_is_conformant():
    res = assess_w3s_parity(_GOOD_CONFIG, _GOOD_APPLET, _GOOD_GATE, _GOOD_ALLOWLIST)
    assert res["status"] == CONFORMANT and res["violations"] == []


def test_combined_bad_is_violation():
    bad = {"mechanisms": {"frame_grabbing": True, "optical_capture": False}}
    res = assess_w3s_parity(bad, "fn x(){}", "", "")
    assert res["status"] == VIOLATION


# -- portability + the real repo -------------------------------------------

def test_ascii_only_sources():
    for f in (_SCRIPT, REPO_ROOT / "l9_presence" / "w3s_parity.py"):
        assert [c for c in f.read_text(encoding="utf-8") if ord(c) > 127] == [], f"non-ASCII in {f.name}"


def test_real_repo_is_conformant():
    """The actual w3bstream surfaces pass parity (the discipline genuinely holds)."""
    r = subprocess.run([sys.executable, str(_SCRIPT)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "CONFORMANT" in r.stdout
