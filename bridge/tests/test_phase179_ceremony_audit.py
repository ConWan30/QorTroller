"""Phase 179 bridge tests — ZK Ceremony Audit Gate (WIF-030 W1 closure).

8 tests:
  T179-1  insert_ceremony_audit_entry stores record
  T179-2  get_ceremony_audit_status returns 7 expected keys
  T179-3  count_ceremony_participants returns 0 for unknown circuit
  T179-4  count_ceremony_participants returns correct count after inserts
  T179-5  anti-replay: duplicate (ceremony_id, participant_address, circuit_name) raises IntegrityError
  T179-6  ceremony_audit_enabled config default is False (infrastructure-first)
  T179-7  ceremony_audit_min_participants config default is 3
  T179-8  GET /agent/ceremony-audit-status audit_passed=True when disabled
"""
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store(tmp):
    from vapi_bridge.store import Store
    return Store(str(Path(tmp) / "test179.db"))


# ---------------------------------------------------------------------------
# T179-1  insert stores record
# ---------------------------------------------------------------------------

def test_t179_1_insert_stores_record():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        row_id = s.insert_ceremony_audit_entry(
            ceremony_id="vapi-ceremony-2026-04-09",
            circuit_name="PitlSessionProof",
            participant_address="0xABCD1234",
            contribution_hash="sha256:contrib1",
            ts_ns=int(time.time_ns()),
        )
        assert row_id >= 1


# ---------------------------------------------------------------------------
# T179-2  get_ceremony_audit_status returns 7 expected keys
# ---------------------------------------------------------------------------

def test_t179_2_get_status_returns_7_keys():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        status = s.get_ceremony_audit_status()
        for key in ("ceremony_audit_enabled", "total_entries", "distinct_participants",
                    "circuits_audited", "min_participants", "audit_passed", "timestamp"):
            assert key in status, f"Missing key: {key}"
        assert len(status) == 7


# ---------------------------------------------------------------------------
# T179-3  count_ceremony_participants returns 0 for unknown circuit
# ---------------------------------------------------------------------------

def test_t179_3_count_zero_for_unknown_circuit():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        count = s.count_ceremony_participants("NonExistentCircuit")
        assert count == 0


# ---------------------------------------------------------------------------
# T179-4  count_ceremony_participants returns correct count after inserts
# ---------------------------------------------------------------------------

def test_t179_4_count_correct_after_inserts():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        ceremony = "vapi-ceremony-2026-04-09"
        circuit = "PitlSessionProof"
        s.insert_ceremony_audit_entry(ceremony, circuit, "0xAAA1", "hash1")
        s.insert_ceremony_audit_entry(ceremony, circuit, "0xBBB2", "hash2")
        s.insert_ceremony_audit_entry(ceremony, circuit, "0xCCC3", "hash3")
        count = s.count_ceremony_participants(circuit)
        assert count == 3
        # Different circuit should still be 0
        assert s.count_ceremony_participants("TournamentPassport") == 0


# ---------------------------------------------------------------------------
# T179-5  anti-replay: duplicate raises IntegrityError
# ---------------------------------------------------------------------------

def test_t179_5_anti_replay_duplicate_raises():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_ceremony_audit_entry("ceremony1", "CircuitA", "0xAAA1", "hash1")
        try:
            s.insert_ceremony_audit_entry("ceremony1", "CircuitA", "0xAAA1", "hash1")
            assert False, "Expected IntegrityError on duplicate"
        except sqlite3.IntegrityError:
            pass  # expected


# ---------------------------------------------------------------------------
# T179-6  ceremony_audit_enabled config default is False
# ---------------------------------------------------------------------------

def test_t179_6_ceremony_audit_enabled_default_false():
    from vapi_bridge.config import Config
    cfg = Config(
        verifier_address="0x1234",
        bridge_private_key="0xdeadbeef",
    )
    assert hasattr(cfg, "ceremony_audit_enabled")
    assert cfg.ceremony_audit_enabled is False


# ---------------------------------------------------------------------------
# T179-7  ceremony_audit_min_participants config default is 3
# ---------------------------------------------------------------------------

def test_t179_7_min_participants_default_3():
    from vapi_bridge.config import Config
    cfg = Config(
        verifier_address="0x1234",
        bridge_private_key="0xdeadbeef",
    )
    assert hasattr(cfg, "ceremony_audit_min_participants")
    assert int(cfg.ceremony_audit_min_participants) == 3


# ---------------------------------------------------------------------------
# T179-8  audit_passed=True when ceremony_audit_enabled=False (gate inactive)
# ---------------------------------------------------------------------------

def test_t179_8_audit_passed_true_when_disabled():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        # No participants registered — but gate is disabled by default
        # The operator_api overlays audit_passed=True when disabled
        status = s.get_ceremony_audit_status()
        # In store, audit_passed defaults to True (caller overlays from cfg)
        assert status["audit_passed"] is True
        assert status["ceremony_audit_enabled"] is False
        assert status["total_entries"] == 0
