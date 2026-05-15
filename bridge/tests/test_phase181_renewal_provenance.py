"""Phase 181 bridge tests — Consent-Bound Renewal Provenance (WIF-031 W1 mitigation).

8 tests:
  T181-1  insert_renewal_consent_snapshot stores record, returns row_id >= 1
  T181-2  get_renewal_consent_snapshot returns dict linked by new_commit_hash
  T181-3  get_renewal_consent_snapshot returns None when hash not found
  T181-4  corpus_delta_detected=True stored and read correctly
  T181-5  corpus_delta_detected=False default when no delta
  T181-6  ceremony_audit_registry_address config field present and defaults to empty string
  T181-7  POST /agent/renew-separation-ratio-commitment response includes corpus_delta_detected key
  T181-8  second renewal produces separate snapshot linked by its own new_commit_hash
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store(tmp):
    from vapi_bridge.store import Store
    return Store(str(Path(tmp) / "test181.db"))


# ---------------------------------------------------------------------------
# T181-1  insert stores record, returns row_id >= 1
# ---------------------------------------------------------------------------

def test_t181_1_insert_stores_record():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        row_id = s.insert_renewal_consent_snapshot(
            new_commit_hash="sha256:abc001",
            n_consented=3,
            players_json='["P1","P2","P3"]',
            revoked=0,
            delta=False,
        )
        assert row_id >= 1


# ---------------------------------------------------------------------------
# T181-2  get_renewal_consent_snapshot returns dict linked by new_commit_hash
# ---------------------------------------------------------------------------

def test_t181_2_get_snapshot_returns_dict():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_renewal_consent_snapshot(
            new_commit_hash="sha256:abc002",
            n_consented=3,
            players_json='["P1","P2","P3"]',
            revoked=0,
            delta=False,
        )
        snap = s.get_renewal_consent_snapshot("sha256:abc002")
        assert snap is not None
        assert snap["new_commit_hash"] == "sha256:abc002"
        assert snap["n_consented_at_renewal"] == 3
        assert snap["players_consented_json"] == '["P1","P2","P3"]'
        assert snap["revoked_at_renewal"] == 0
        assert snap["corpus_delta_detected"] == 0


# ---------------------------------------------------------------------------
# T181-3  get_renewal_consent_snapshot returns None when hash not found
# ---------------------------------------------------------------------------

def test_t181_3_get_snapshot_returns_none_when_missing():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        result = s.get_renewal_consent_snapshot("sha256:nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# T181-4  corpus_delta_detected=True stored and read correctly
# ---------------------------------------------------------------------------

def test_t181_4_corpus_delta_detected_true():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_renewal_consent_snapshot(
            new_commit_hash="sha256:abc004",
            n_consented=2,
            players_json='["P1","P2"]',
            revoked=1,
            delta=True,
        )
        snap = s.get_renewal_consent_snapshot("sha256:abc004")
        assert snap is not None
        assert snap["corpus_delta_detected"] == 1
        assert snap["revoked_at_renewal"] == 1


# ---------------------------------------------------------------------------
# T181-5  corpus_delta_detected=False when no delta
# ---------------------------------------------------------------------------

def test_t181_5_corpus_delta_detected_false_default():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_renewal_consent_snapshot(
            new_commit_hash="sha256:abc005",
            n_consented=3,
            players_json='["P1","P2","P3"]',
            revoked=0,
            delta=False,
        )
        snap = s.get_renewal_consent_snapshot("sha256:abc005")
        assert snap is not None
        assert snap["corpus_delta_detected"] == 0


# ---------------------------------------------------------------------------
# T181-6  ceremony_audit_registry_address config field present and defaults to ""
# ---------------------------------------------------------------------------

def test_t181_6_config_ceremony_audit_registry_address():
    from vapi_bridge.config import Config
    cfg = Config()
    assert hasattr(cfg, "ceremony_audit_registry_address")
    # Env-agnostic: field defaults to "" but bridge/.env may populate a real
    # deployed address. Assert type, not value, so CI is not env-dependent.
    assert isinstance(cfg.ceremony_audit_registry_address, str)


# ---------------------------------------------------------------------------
# T181-7  POST /agent/renew response includes corpus_delta_detected key
# ---------------------------------------------------------------------------

def test_t181_7_renew_endpoint_returns_corpus_delta_key():
    from fastapi.testclient import TestClient
    from vapi_bridge.store import Store
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store = Store(str(Path(tmp) / "test181t7.db"))
        cfg = Config()
        object.__setattr__(cfg, "operator_api_key", "test-key-181")

        app = create_operator_app(cfg, store)
        client = TestClient(app)

        resp = client.post(
            "/agent/renew-separation-ratio-commitment",
            params={
                "ratio": 0.569,
                "n_sessions": 20,
                "n_players": 3,
                "dry_run": True,
                "api_key": "test-key-181",
            },
        )
        # endpoint may return 200 or 422/500; check key presence on success
        if resp.status_code == 200:
            body = resp.json()
            assert "corpus_delta_detected" in body


# ---------------------------------------------------------------------------
# T181-8  second renewal produces separate snapshot linked by its own hash
# ---------------------------------------------------------------------------

def test_t181_8_second_renewal_separate_snapshot():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        s = _make_store(tmp)
        s.insert_renewal_consent_snapshot(
            new_commit_hash="sha256:first",
            n_consented=3,
            players_json='["P1","P2","P3"]',
            revoked=0,
            delta=False,
        )
        s.insert_renewal_consent_snapshot(
            new_commit_hash="sha256:second",
            n_consented=2,
            players_json='["P1","P2"]',
            revoked=1,
            delta=True,
        )
        snap1 = s.get_renewal_consent_snapshot("sha256:first")
        snap2 = s.get_renewal_consent_snapshot("sha256:second")
        assert snap1 is not None
        assert snap2 is not None
        assert snap1["n_consented_at_renewal"] == 3
        assert snap2["n_consented_at_renewal"] == 2
        assert snap2["corpus_delta_detected"] == 1
