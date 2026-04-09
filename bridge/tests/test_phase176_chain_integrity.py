"""Phase 176 bridge tests — PoACChainIntegrityMonitor (agent #25).

8 tests:
  T176-1  insert_poac_chain_audit_log stores record
  T176-2  get_poac_chain_audit_status returns latest
  T176-3  integrity_score = valid_links / total_records
  T176-4  audit_passed True when broken_links == 0
  T176-5  audit_passed False when broken_links > 0
  T176-6  integrity_score = 1.0 when total_records = 0 (vacuously intact)
  T176-7  device_id filter returns device-specific results
  T176-8  broken_links count-only (W1): no record IDs in response
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store(tmp):
    from vapi_bridge.store import Store
    return Store(str(Path(tmp) / "test176.db"))


# ---------------------------------------------------------------------------
# T176-1  insert stores record
# ---------------------------------------------------------------------------

def test_t176_1_insert_stores_record():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        row_id = s.insert_poac_chain_audit_log(
            device_id="dev_abc",
            total_records=50,
            valid_links=50,
            broken_links=0,
        )
        assert row_id >= 1


# ---------------------------------------------------------------------------
# T176-2  get_poac_chain_audit_status returns latest
# ---------------------------------------------------------------------------

def test_t176_2_get_returns_latest():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        s.insert_poac_chain_audit_log("dev_abc", 50, 50, 0)
        time.sleep(0.01)
        s.insert_poac_chain_audit_log("dev_abc", 60, 59, 1)
        rows = s.get_poac_chain_audit_status(limit=1)
        assert len(rows) == 1
        assert rows[0]["total_records"] == 60


# ---------------------------------------------------------------------------
# T176-3  integrity_score = valid_links / total_records
# ---------------------------------------------------------------------------

def test_t176_3_integrity_score_computed():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        s.insert_poac_chain_audit_log("dev_abc", 100, 90, 10)
        rows = s.get_poac_chain_audit_status(limit=1)
        assert abs(rows[0]["integrity_score"] - 0.9) < 1e-5


# ---------------------------------------------------------------------------
# T176-4  audit_passed True when broken_links == 0
# ---------------------------------------------------------------------------

def test_t176_4_audit_passed_on_zero_broken():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        s.insert_poac_chain_audit_log("dev_abc", 50, 50, 0)
        rows = s.get_poac_chain_audit_status(limit=1)
        assert rows[0]["audit_passed"] is True


# ---------------------------------------------------------------------------
# T176-5  audit_passed False when broken_links > 0
# ---------------------------------------------------------------------------

def test_t176_5_audit_failed_on_broken():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        s.insert_poac_chain_audit_log("dev_abc", 50, 47, 3)
        rows = s.get_poac_chain_audit_status(limit=1)
        assert rows[0]["audit_passed"] is False


# ---------------------------------------------------------------------------
# T176-6  integrity_score = 1.0 when total_records = 0 (vacuously intact)
# ---------------------------------------------------------------------------

def test_t176_6_vacuous_integrity_on_zero_records():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        s.insert_poac_chain_audit_log("dev_new", 0, 0, 0)
        rows = s.get_poac_chain_audit_status(limit=1)
        assert abs(rows[0]["integrity_score"] - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# T176-7  device_id filter returns device-specific results
# ---------------------------------------------------------------------------

def test_t176_7_device_id_filter():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        s.insert_poac_chain_audit_log("dev_a", 10, 10, 0)
        s.insert_poac_chain_audit_log("dev_b", 20, 19, 1)
        rows_a = s.get_poac_chain_audit_status(device_id="dev_a", limit=1)
        assert len(rows_a) == 1
        assert rows_a[0]["total_records"] == 10
        rows_b = s.get_poac_chain_audit_status(device_id="dev_b", limit=1)
        assert rows_b[0]["broken_links"] == 1


# ---------------------------------------------------------------------------
# T176-8  W1 — response has no broken record ID fields
# ---------------------------------------------------------------------------

def test_t176_8_no_broken_record_ids_in_response():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        s.insert_poac_chain_audit_log("dev_abc", 50, 47, 3)
        rows = s.get_poac_chain_audit_status(limit=1)
        row = rows[0]
        # Only aggregate counts — no field that could identify specific broken records
        forbidden_keys = {"broken_record_ids", "broken_hashes", "broken_record_list", "failed_ids"}
        assert not forbidden_keys.intersection(set(row.keys()))
        # Sanity: broken_links count is present
        assert row["broken_links"] == 3
