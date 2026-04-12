"""Phase 177 bridge tests — ProtocolMaturityScoringAgent (agent #26).

8 tests:
  T177-1  insert_protocol_maturity_log stores record
  T177-2  get_protocol_maturity_status returns latest
  T177-3  maturity_score formula is correct (6 weighted components)
  T177-4  maturity_tier ALPHA when score < 0.50
  T177-5  maturity_tier BETA when 0.50 <= score < 0.85
  T177-6  maturity_tier PRODUCTION_CANDIDATE when score >= 0.85
  T177-7  all zeros yields ALPHA
  T177-8  all ones yields PRODUCTION_CANDIDATE (score = 1.0)
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store(tmp):
    from vapi_bridge.store import Store
    return Store(str(Path(tmp) / "test177.db"))


# ---------------------------------------------------------------------------
# T177-1  insert stores record
# ---------------------------------------------------------------------------

def test_t177_1_insert_stores_record():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        row_id = s.insert_protocol_maturity_log(
            separation_component=0.5,
            chain_integrity_component=1.0,
            consent_component=1.0,
            biometric_freshness_component=0.8,
            agent_calibration_component=0.9,
            enrollment_component=0.0,
        )
        assert row_id >= 1


# ---------------------------------------------------------------------------
# T177-2  get returns latest
# ---------------------------------------------------------------------------

def test_t177_2_get_returns_latest():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        s.insert_protocol_maturity_log(0.5, 1.0, 1.0, 0.8, 0.9, 0.0)
        time.sleep(0.01)
        s.insert_protocol_maturity_log(0.7, 1.0, 1.0, 0.9, 1.0, 1.0)
        rows = s.get_protocol_maturity_status(limit=1)
        assert len(rows) == 1
        assert abs(rows[0]["separation_component"] - 0.7) < 1e-6


# ---------------------------------------------------------------------------
# T177-3  maturity_score formula v3 (Phase 195):
#   0.18*sep + 0.20*chain + 0.15*consent + 0.11*fresh + 0.12*cal
#   + 0.10*enroll + 0.07*tfa + 0.04*bso + 0.03*pmi
# ---------------------------------------------------------------------------

def test_t177_3_score_formula():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        sep, chain, consent, fresh, cal, enroll = 0.5, 0.8, 0.6, 0.7, 0.9, 0.3
        tfa, bso, pmi = 0.8, 0.7, 1.0
        expected = round(
            0.18 * sep + 0.20 * chain + 0.15 * consent
            + 0.11 * fresh + 0.12 * cal + 0.10 * enroll
            + 0.07 * tfa + 0.04 * bso + 0.03 * pmi,
            6,
        )
        s.insert_protocol_maturity_log(
            sep, chain, consent, fresh, cal, enroll,
            threat_forecast_accuracy_component=tfa,
            biometric_stationarity_component=bso,
            pmi_component=pmi,
        )
        rows = s.get_protocol_maturity_status(limit=1)
        assert abs(rows[0]["maturity_score"] - expected) < 1e-5


# ---------------------------------------------------------------------------
# T177-4  ALPHA when score < 0.50
# ---------------------------------------------------------------------------

def test_t177_4_tier_alpha():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        # All low values -> score well below 0.50
        s.insert_protocol_maturity_log(0.1, 0.1, 0.1, 0.1, 0.1, 0.1)
        rows = s.get_protocol_maturity_status(limit=1)
        assert rows[0]["maturity_tier"] == "ALPHA"
        assert rows[0]["maturity_score"] < 0.50


# ---------------------------------------------------------------------------
# T177-5  BETA when 0.50 <= score < 0.85
# ---------------------------------------------------------------------------

def test_t177_5_tier_beta():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        # Target ~0.65: sep=0.6, chain=0.7, consent=0.7, fresh=0.6, cal=0.7, enroll=0.5
        # score = 0.25*0.6 + 0.20*0.7 + 0.15*0.7 + 0.15*0.6 + 0.15*0.7 + 0.10*0.5
        # = 0.150 + 0.140 + 0.105 + 0.090 + 0.105 + 0.050 = 0.640
        s.insert_protocol_maturity_log(0.6, 0.7, 0.7, 0.6, 0.7, 0.5)
        rows = s.get_protocol_maturity_status(limit=1)
        assert rows[0]["maturity_tier"] == "BETA"
        assert 0.50 <= rows[0]["maturity_score"] < 0.85


# ---------------------------------------------------------------------------
# T177-6  PRODUCTION_CANDIDATE when score >= 0.85
# ---------------------------------------------------------------------------

def test_t177_6_tier_production_candidate():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        # All 1.0 gives score = 1.0
        s.insert_protocol_maturity_log(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        rows = s.get_protocol_maturity_status(limit=1)
        assert rows[0]["maturity_tier"] == "PRODUCTION_CANDIDATE"
        assert rows[0]["maturity_score"] >= 0.85


# ---------------------------------------------------------------------------
# T177-7  All zeros yields ALPHA
# ---------------------------------------------------------------------------

def test_t177_7_all_zeros_alpha():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        s.insert_protocol_maturity_log(
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            threat_forecast_accuracy_component=0.0,
            biometric_stationarity_component=0.0,
            pmi_component=0.0,
        )
        rows = s.get_protocol_maturity_status(limit=1)
        assert rows[0]["maturity_tier"] == "ALPHA"
        assert rows[0]["maturity_score"] == 0.0


# ---------------------------------------------------------------------------
# T177-8  All ones yields PRODUCTION_CANDIDATE (score = 1.0)
# ---------------------------------------------------------------------------

def test_t177_8_all_ones_production_candidate():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        s.insert_protocol_maturity_log(
            1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
            threat_forecast_accuracy_component=1.0,
            biometric_stationarity_component=1.0,
            pmi_component=1.0,
        )
        rows = s.get_protocol_maturity_status(limit=1)
        assert rows[0]["maturity_tier"] == "PRODUCTION_CANDIDATE"
        assert abs(rows[0]["maturity_score"] - 1.0) < 1e-6
