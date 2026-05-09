"""Phase 238 Session 1 — Canary anchor smoke-test gate verification.

T-CANARY-1..6 — verifies the triple-gate authorization in
scripts/canary_corpus_snapshot_anchor.py refuses to fire chain calls
unless ALL three gates align.  Static-source checks supplement live
gate-logic tests.
"""
from __future__ import annotations

import os
import sys
import types as _types
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Stub heavy-import modules
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

# Reload the canary module fresh per-test so env vars are read freshly
import importlib

CANARY_PATH = PROJECT_ROOT / "scripts" / "canary_corpus_snapshot_anchor.py"


def _import_canary():
    """Load scripts/canary_corpus_snapshot_anchor.py as a module."""
    spec = importlib.util.spec_from_file_location("canary_anchor", CANARY_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# T-CANARY-1 ─────────────────────────────────────────────────────────────────
def test_t_canary_1_script_exists_with_required_constants():
    """Canary script exists + has the expected gate function + cost budget."""
    assert CANARY_PATH.exists()
    src = CANARY_PATH.read_text(encoding="utf-8")
    assert "COST_BUDGET_IOTX = 0.50" in src
    assert "def _check_gates()" in src
    assert "CHAIN_SUBMISSION_PAUSED" in src
    assert "CORPUS_SNAPSHOT_CANARY_AUTHORIZED" in src
    assert "--confirm" in src
    # Must NOT have any obvious bypass
    assert "force=True" not in src
    assert "skip_gates" not in src


# T-CANARY-2 ─────────────────────────────────────────────────────────────────
def test_t_canary_2_default_env_blocks_gate_1():
    """With no env override, Gate 1 (CHAIN_SUBMISSION_PAUSED) blocks."""
    mod = _import_canary()
    # Clear both env vars
    with patch.dict(os.environ, {}, clear=False):
        for k in ("CHAIN_SUBMISSION_PAUSED", "CORPUS_SNAPSHOT_CANARY_AUTHORIZED"):
            os.environ.pop(k, None)
        ok, reason = mod._check_gates()
        assert ok is False
        assert "Gate 1 FAILED" in reason
        assert "CHAIN_SUBMISSION_PAUSED" in reason


# T-CANARY-3 ─────────────────────────────────────────────────────────────────
def test_t_canary_3_pause_off_alone_blocks_gate_2():
    """CHAIN_SUBMISSION_PAUSED=false alone → Gate 2 blocks (intent flag missing)."""
    mod = _import_canary()
    with patch.dict(os.environ, {
        "CHAIN_SUBMISSION_PAUSED": "false",
    }, clear=False):
        os.environ.pop("CORPUS_SNAPSHOT_CANARY_AUTHORIZED", None)
        ok, reason = mod._check_gates()
        assert ok is False
        assert "Gate 2 FAILED" in reason


# T-CANARY-4 ─────────────────────────────────────────────────────────────────
def test_t_canary_4_pause_true_blocks_even_with_intent():
    """Gate 1 must trump Gate 2 — pause=true blocks regardless of intent flag."""
    mod = _import_canary()
    with patch.dict(os.environ, {
        "CHAIN_SUBMISSION_PAUSED": "true",
        "CORPUS_SNAPSHOT_CANARY_AUTHORIZED": "true",
    }, clear=False):
        ok, reason = mod._check_gates()
        assert ok is False
        assert "Gate 1 FAILED" in reason


# T-CANARY-5 ─────────────────────────────────────────────────────────────────
def test_t_canary_5_both_gates_aligned_passes():
    """Only when both env gates align does _check_gates return ok=True."""
    mod = _import_canary()
    with patch.dict(os.environ, {
        "CHAIN_SUBMISSION_PAUSED": "false",
        "CORPUS_SNAPSHOT_CANARY_AUTHORIZED": "true",
    }, clear=False):
        ok, reason = mod._check_gates()
        assert ok is True
        assert "all 3 gates aligned" in reason


# T-CANARY-6 ─────────────────────────────────────────────────────────────────
def test_t_canary_6_dry_run_without_confirm_does_no_chain_io():
    """Without --confirm, the CLI exits 0 without running async _run."""
    mod = _import_canary()
    # Simulate CLI without --confirm
    with patch.object(sys, "argv", ["canary_corpus_snapshot_anchor.py"]):
        rc = mod._main_cli()
    # Returns 0 (dry-run) without invoking _run() — no chain calls happened
    assert rc == 0
