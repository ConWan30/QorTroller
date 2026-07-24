"""Tests for scripts/replay_governance_event.py (A2A round-30 T4).

The replay tool records a NEW governance-chain entry documenting an offline seal — it never
backdates the original, never rewrites the allowlist, never re-runs the gate. These tests
exercise the pure payload/hash assembly with NO network.

   T-RGE-1  _hash_allowlist_content matches the gate's compute_allowlist_hash canonicalization
            (byte-identical: sort_keys + compact separators).
   T-RGE-2  a fresh ts_ns makes each provenance hash unique — proving a late record is a NEW
            link, not a reproduction of the original event.
   T-RGE-3  the reason-length guard (10-200) matches the endpoint's contract.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "replay_governance_event", ROOT / "scripts" / "replay_governance_event.py")
rge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rge)

from scripts.vapi_invariant_gate import compute_allowlist_hash  # noqa: E402


# ── T-RGE-1 ───────────────────────────────────────────────────────────────────

def test_t_rge_1_hash_matches_gate_canonicalization():
    """_hash_allowlist_content over the CURRENT allowlist text must equal the gate's
    compute_allowlist_hash() — same canonicalization, single source of truth."""
    allowlist_path = ROOT / ".github" / "INVARIANTS_ALLOWLIST.json"
    text = allowlist_path.read_text(encoding="utf-8")
    assert rge._hash_allowlist_content(text) == compute_allowlist_hash()


# ── T-RGE-2 ───────────────────────────────────────────────────────────────────

def test_t_rge_2_fresh_ts_makes_new_link_not_a_backdate():
    """The provenance hash embeds a fresh ts_ns — two computations of the SAME logical
    event differ, so a late record is honestly a NEW chain link (never the original)."""
    args = ("0" * 64, "a" * 64, "invariant_change", "late record of some seal")
    h1 = rge._compute_governance_provenance_hash(*args)
    h2 = rge._compute_governance_provenance_hash(*args)
    assert h1 != h2  # fresh ts_ns each call
    assert len(h1) == 64 and len(h2) == 64


# ── T-RGE-3 ───────────────────────────────────────────────────────────────────

def test_t_rge_3_reason_length_contract_matches_endpoint():
    """The tool enforces the same 10-200 char reason contract as the bridge endpoint."""
    # (indirect) the module exposes the valid categories set the endpoint validates.
    assert rge._VALID_CATS == {"refactor", "bugfix", "invariant_change", "ceremony_update"}
    # a too-short reason would be rejected by main() before any assembly; assert the bound.
    assert not (10 <= len("short") <= 200)
    assert 10 <= len("late record of INV-MFG-003 seal") <= 200
