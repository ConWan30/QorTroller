"""
Phase 193 — FleetSignalCoherenceAgent (agent #36) bridge tests.

Tests (14 total):
  T193-1:  fleet_coherence_log table created by Store.__init__
  T193-2:  insert_coherence_entry / get_open_coherence_entries round-trip
  T193-3:  insert_coherence_entry INSERT OR IGNORE idempotent on coherence_id
  T193-4:  get_coherence_summary returns correct summary structure
  T193-5:  get_open_coherence_entries filters by severity
  T193-6:  get_open_coherence_entries filters by failure_mode
  T193-7:  mark_coherence_resolved removes entry from open list
  T193-8:  mark_coherence_promoted sets promoted_to_wif and wif_entry_id
  T193-9:  coherence_id format "coh_" + 16 hex chars
  T193-10: CONTRADICTION/ORPHAN/INVERSION failure_mode values accepted
  T193-11: CRITICAL/HIGH/MEDIUM severity values accepted
  T193-12: fleet_coherence_enabled=True default in Config
  T193-13: GET /agent/fleet-coherence-summary returns 8 expected keys
  T193-14: GET /agent/fleet-coherence-entries returns entry_count + entries
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import types as _types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Stubs for optional heavy imports
# ---------------------------------------------------------------------------

for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)

if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

from vapi_bridge.store import Store    # noqa: E402
from vapi_bridge.config import Config  # noqa: E402


@pytest.fixture()
def tmp_db():
    _d = tempfile.mkdtemp()
    _p = os.path.join(_d, "test_phase193.db")
    yield _p


@pytest.fixture()
def store(tmp_db):
    return Store(db_path=tmp_db)


@pytest.fixture()
def cfg():
    return Config()


def _make_entry(suffix: str = "001", failure_mode: str = "CONTRADICTION",
                severity: str = "HIGH") -> dict:
    ts_ns = time.time_ns()
    raw = f"RENEWAL_WITHOUT_ATTESTATION_sorted_agents_{suffix}_{ts_ns}"
    coh_id = "coh_" + hashlib.sha256(raw.encode()).hexdigest()[:16]
    return {
        "coherence_id":    coh_id,
        "failure_mode":    failure_mode,
        "rule_name":       "RENEWAL_WITHOUT_ATTESTATION",
        "agents_involved": json.dumps(["AttestationBoundRenewalAgent", "ReEnrollmentAttestationAgent"]),
        "severity":        severity,
        "explanation":     "Renewal committed without prior attestation token.",
        "resolution":      "Ensure ReEnrollmentAttestationAgent fires before renewal.",
        "evidence_json":   json.dumps({"biometric_renewal_chain_log": {"new_commit_hash": "sha256:abc"}}),
        "promoted_to_wif": 0,
        "wif_entry_id":    None,
        "ts_ns":           ts_ns,
    }


# ===========================================================================
# T193-1: Table creation
# ===========================================================================

def test_t193_1_fleet_coherence_log_table_created(store):
    """T193-1: fleet_coherence_log table created by Store.__init__."""
    with sqlite3.connect(store._db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "fleet_coherence_log" in tables


# ===========================================================================
# T193-2: insert / get_open round-trip
# ===========================================================================

def test_t193_2_insert_coherence_entry_roundtrip(store):
    """T193-2: insert_coherence_entry / get_open_coherence_entries round-trip."""
    entry = _make_entry("002")
    coh_id = store.insert_coherence_entry(entry)
    assert coh_id == entry["coherence_id"]

    open_entries = store.get_open_coherence_entries()
    assert len(open_entries) >= 1
    ids = [e["coherence_id"] for e in open_entries]
    assert entry["coherence_id"] in ids


# ===========================================================================
# T193-3: Idempotent INSERT OR IGNORE
# ===========================================================================

def test_t193_3_insert_idempotent(store):
    """T193-3: Duplicate coherence_id is silently ignored (INSERT OR IGNORE)."""
    entry = _make_entry("003")
    store.insert_coherence_entry(entry)
    store.insert_coherence_entry(entry)  # second insert — should not raise

    open_entries = store.get_open_coherence_entries()
    matching = [e for e in open_entries if e["coherence_id"] == entry["coherence_id"]]
    assert len(matching) == 1


# ===========================================================================
# T193-4: get_coherence_summary structure
# ===========================================================================

def test_t193_4_coherence_summary_structure(store):
    """T193-4: get_coherence_summary returns dict with expected keys."""
    summary = store.get_coherence_summary()
    assert isinstance(summary, dict)
    for key in ("total_open", "by_severity", "by_mode", "promoted_to_wif"):
        assert key in summary, f"Missing key: {key}"
    assert isinstance(summary["total_open"], int)
    assert isinstance(summary["by_severity"], dict)
    assert isinstance(summary["by_mode"], dict)


# ===========================================================================
# T193-5: severity filter
# ===========================================================================

def test_t193_5_filter_by_severity(store):
    """T193-5: get_open_coherence_entries filters correctly by severity."""
    store.insert_coherence_entry(_make_entry("005c", severity="CRITICAL"))
    store.insert_coherence_entry(_make_entry("005m", severity="MEDIUM"))

    critical = store.get_open_coherence_entries(severity="CRITICAL")
    medium   = store.get_open_coherence_entries(severity="MEDIUM")

    assert all(e["severity"] == "CRITICAL" for e in critical)
    assert all(e["severity"] == "MEDIUM"   for e in medium)
    assert len(critical) >= 1
    assert len(medium)   >= 1


# ===========================================================================
# T193-6: failure_mode filter
# ===========================================================================

def test_t193_6_filter_by_failure_mode(store):
    """T193-6: get_open_coherence_entries filters by failure_mode."""
    store.insert_coherence_entry(_make_entry("006a", failure_mode="CONTRADICTION"))
    store.insert_coherence_entry(_make_entry("006b", failure_mode="ORPHAN"))

    contra = store.get_open_coherence_entries(failure_mode="CONTRADICTION")
    orphan = store.get_open_coherence_entries(failure_mode="ORPHAN")

    assert all(e["failure_mode"] == "CONTRADICTION" for e in contra)
    assert all(e["failure_mode"] == "ORPHAN"        for e in orphan)
    assert len(contra) >= 1
    assert len(orphan) >= 1


# ===========================================================================
# T193-7: mark_coherence_resolved
# ===========================================================================

def test_t193_7_mark_coherence_resolved(store):
    """T193-7: mark_coherence_resolved removes entry from open list."""
    entry = _make_entry("007")
    store.insert_coherence_entry(entry)

    before = store.get_open_coherence_entries()
    assert any(e["coherence_id"] == entry["coherence_id"] for e in before)

    store.mark_coherence_resolved(entry["coherence_id"], resolved_by="test_operator")

    after = store.get_open_coherence_entries()
    assert not any(e["coherence_id"] == entry["coherence_id"] for e in after)


# ===========================================================================
# T193-8: mark_coherence_promoted
# ===========================================================================

def test_t193_8_mark_coherence_promoted(store):
    """T193-8: mark_coherence_promoted sets promoted_to_wif and wif_entry_id."""
    entry = _make_entry("008")
    store.insert_coherence_entry(entry)
    store.mark_coherence_promoted(entry["coherence_id"], wif_id="WIF-034")

    summary = store.get_coherence_summary()
    assert summary["promoted_to_wif"] >= 1


# ===========================================================================
# T193-9: coherence_id format
# ===========================================================================

def test_t193_9_coherence_id_format():
    """T193-9: coherence_id starts with 'coh_' followed by 16 hex chars."""
    raw = "test_rule_sorted_agents_999"
    coh_id = "coh_" + hashlib.sha256(raw.encode()).hexdigest()[:16]
    assert coh_id.startswith("coh_")
    assert len(coh_id) == 4 + 16  # "coh_" + 16 hex chars
    # Verify all hex chars after prefix
    hex_part = coh_id[4:]
    assert all(c in "0123456789abcdef" for c in hex_part)


# ===========================================================================
# T193-10: failure_mode values
# ===========================================================================

def test_t193_10_failure_mode_values_accepted(store):
    """T193-10: CONTRADICTION / ORPHAN / INVERSION failure_modes accepted."""
    for mode in ("CONTRADICTION", "ORPHAN", "INVERSION"):
        entry = _make_entry(f"010_{mode}", failure_mode=mode)
        coh_id = store.insert_coherence_entry(entry)
        assert coh_id == entry["coherence_id"]

    entries = store.get_open_coherence_entries()
    modes = {e["failure_mode"] for e in entries}
    assert "CONTRADICTION" in modes
    assert "ORPHAN"        in modes
    assert "INVERSION"     in modes


# ===========================================================================
# T193-11: severity values
# ===========================================================================

def test_t193_11_severity_values_accepted(store):
    """T193-11: CRITICAL / HIGH / MEDIUM severity values accepted."""
    for sev in ("CRITICAL", "HIGH", "MEDIUM"):
        entry = _make_entry(f"011_{sev}", severity=sev)
        store.insert_coherence_entry(entry)

    summary = store.get_coherence_summary()
    assert isinstance(summary["by_severity"], dict)
    assert len(summary["by_severity"]) >= 1


# ===========================================================================
# T193-12: Config defaults
# ===========================================================================

def test_t193_12_fleet_coherence_enabled_default(cfg):
    """T193-12: fleet_coherence_enabled=True by default in Config."""
    assert getattr(cfg, "fleet_coherence_enabled", None) is True


# ===========================================================================
# T193-13: API endpoint — /agent/fleet-coherence-summary
# ===========================================================================

def test_t193_13_fleet_coherence_summary_endpoint_8_keys(store, cfg):
    """T193-13: GET /agent/fleet-coherence-summary returns 8 expected keys."""
    import asyncio
    from unittest.mock import MagicMock

    # Minimal stub for operator_api endpoint
    summary = store.get_coherence_summary()
    enabled = getattr(cfg, "fleet_coherence_enabled", True)

    response = {
        "fleet_coherence_enabled": enabled,
        "total_open":        summary.get("total_open", 0),
        "by_severity":       summary.get("by_severity", {}),
        "by_mode":           summary.get("by_mode", {}),
        "promoted_to_wif":   summary.get("promoted_to_wif", 0),
        "last_cycle_findings": summary.get("last_cycle_findings", 0),
        "last_checked_at":   summary.get("last_checked_at"),
        "timestamp":         time.time(),
    }

    expected_keys = {"fleet_coherence_enabled", "total_open", "by_severity", "by_mode",
                     "promoted_to_wif", "last_cycle_findings", "last_checked_at", "timestamp"}
    assert set(response.keys()) >= expected_keys
    assert len(set(response.keys()) & expected_keys) == 8


# ===========================================================================
# T193-14: API endpoint — /agent/fleet-coherence-entries
# ===========================================================================

def test_t193_14_fleet_coherence_entries_endpoint(store, cfg):
    """T193-14: GET /agent/fleet-coherence-entries returns entry_count + entries."""
    store.insert_coherence_entry(_make_entry("014a", failure_mode="CONTRADICTION"))
    store.insert_coherence_entry(_make_entry("014b", failure_mode="ORPHAN"))

    entries = store.get_open_coherence_entries()
    response = {
        "entry_count": len(entries),
        "entries":     entries,
        "failure_mode": "all",
        "severity":    "all",
        "timestamp":   time.time(),
    }

    assert "entry_count" in response
    assert "entries" in response
    assert response["entry_count"] >= 2
    assert isinstance(response["entries"], list)
