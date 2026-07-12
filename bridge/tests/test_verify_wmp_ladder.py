"""Plug-and-play ladder verifier — regression pins.

Confirms the one-command zero-trust verifier runs green offline over the real
bundle, each rung reports the expected PASS/DEFER, and (crucially for a reviewer
on any OS) the verifier's output is ASCII-only so a Windows cp1252 console never
crashes on it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_wmp_ladder as vwl

_SCRIPT = REPO_ROOT / "scripts" / "verify_wmp_ladder.py"


def test_rung_statuses_offline():
    b = vwl._load_bundle()
    assert vwl.rung_bundle(b)[0] == vwl.PASS
    assert vwl.rung_hardening(b)[0] == vwl.PASS
    assert vwl.rung_derived(b)[0] == vwl.PASS
    assert vwl.rung_disclosure(b)[0] == vwl.PASS
    assert vwl.rung_zk(b)[0] == vwl.DEFER          # honest deferral, not pass/fail
    assert vwl.rung_flywheel(b)[0] == vwl.DEFER     # breadth-gated at N=1
    assert vwl.rung_assertion(b)[0] == vwl.PASS     # anti-cheat PoSP (same M17 session)
    assert vwl.rung_fusion(b)[0] == vwl.PASS         # tri-plane federation (one match, three planes)


def test_ladder_runs_exit_zero_from_clone():
    """The single command a reviewer runs must exit 0 offline (no deps, no net)."""
    r = subprocess.run([sys.executable, str(_SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "LADDER VERIFIED" in r.stdout


def test_verifier_source_is_ascii_only():
    """Plug-and-play guard: a Windows cp1252 console crashes on non-ASCII output.
    Pin the verifier source ASCII-clean so it runs on any reviewer's terminal."""
    src = _SCRIPT.read_text(encoding="utf-8")
    non_ascii = sorted(set(c for c in src if ord(c) > 127))
    assert non_ascii == [], f"non-ASCII in verifier: {[hex(ord(c)) for c in non_ascii]}"
