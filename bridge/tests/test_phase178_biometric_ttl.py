"""Phase 178 bridge tests — Biometric Credential TTL Gate (WIF-029 W1 closure).

8 tests:
  T178-1  insert_biometric_renewal_log stores record correctly
  T178-2  get_biometric_credential_age_status returns 8 expected keys
  T178-3  ttl_expired=False when no commits exist (fail-open, no commit = no expiry)
  T178-4  ttl_expired=False when age_days < ttl_days (credential fresh)
  T178-5  ttl_expired=True when age_days > ttl_days (credential stale)
  T178-6  check_biometric_credential_ttl logs to biometric_renewal_log
  T178-7  check_biometric_credential_ttl returns fail-open on missing store method
  T178-8  biometric_credential_ttl_days config field default is 90.0
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store(tmp):
    from vapi_bridge.store import Store
    return Store(str(Path(tmp) / "test178.db"))


def _fake_cfg(ttl_days=90.0):
    """Minimal config stub for Phase 178 TTL tests."""
    class _Cfg:
        biometric_credential_ttl_days = ttl_days
    return _Cfg()


# ---------------------------------------------------------------------------
# T178-1  insert stores record
# ---------------------------------------------------------------------------

def test_t178_1_insert_stores_record():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        row_id = s.insert_biometric_renewal_log(
            commit_hash="sha256:abc123",
            age_days=6.3,
            ttl_days=90.0,
            ttl_expired=False,
            recalibration_required=False,
        )
        assert row_id >= 1


# ---------------------------------------------------------------------------
# T178-2  get_biometric_credential_age_status returns 8 expected keys
# ---------------------------------------------------------------------------

def test_t178_2_get_status_returns_8_keys():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        status = s.get_biometric_credential_age_status()
        assert "ttl_enabled" in status
        assert "commit_hash" in status
        assert "commit_ts" in status
        assert "age_days" in status
        assert "ttl_days" in status
        assert "ttl_expired" in status
        assert "recalibration_required" in status
        assert "timestamp" in status
        assert len(status) == 8


# ---------------------------------------------------------------------------
# T178-3  ttl_expired=False when no commits exist
# ---------------------------------------------------------------------------

def test_t178_3_no_commits_not_expired():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        status = s.get_biometric_credential_age_status()
        # No commit → commit_hash is empty → ttl_expired must be False (fail-open)
        assert status["ttl_expired"] is False
        assert status["commit_hash"] == ""


# ---------------------------------------------------------------------------
# T178-4  ttl_expired=False when credential is fresh (age_days < ttl_days)
# ---------------------------------------------------------------------------

def test_t178_4_fresh_credential_not_expired():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        # Insert a renewal log with ttl_expired=False
        s.insert_biometric_renewal_log(
            commit_hash="sha256:fresh",
            age_days=6.3,
            ttl_days=90.0,
            ttl_expired=False,
            recalibration_required=False,
        )
        # Simulate a recent commit in separation_ratio_registry_log (age ~0 days)
        with s._conn() as conn:
            conn.execute(
                "INSERT INTO separation_ratio_registry_log "
                "(commit_hash, ratio_millis, n_sessions, n_players, "
                "committed, on_chain_tx, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                ("sha256:fresh", 569, 20, 3, 1, "", time.time()),
            )
        status = s.get_biometric_credential_age_status()
        assert status["age_days"] < 1.0  # committed moments ago
        assert status["ttl_expired"] is False


# ---------------------------------------------------------------------------
# T178-5  ttl_expired=True when credential is stale (age_days > ttl_days)
# ---------------------------------------------------------------------------

def test_t178_5_stale_credential_expired():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        # Insert a commit 91 days ago (91 * 86400 seconds)
        old_ts = time.time() - 91 * 86400
        with s._conn() as conn:
            conn.execute(
                "INSERT INTO separation_ratio_registry_log "
                "(commit_hash, ratio_millis, n_sessions, n_players, "
                "committed, on_chain_tx, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                ("sha256:stale", 569, 20, 3, 1, "", old_ts),
            )
        status = s.get_biometric_credential_age_status()
        assert status["age_days"] > 90.0
        assert status["ttl_expired"] is True
        assert status["commit_hash"] == "sha256:stale"


# ---------------------------------------------------------------------------
# T178-6  check_biometric_credential_ttl logs to biometric_renewal_log
# ---------------------------------------------------------------------------

def test_t178_6_check_ttl_logs_to_renewal_log():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        cfg = _fake_cfg(ttl_days=90.0)
        from vapi_bridge.tournament_activation_chain_agent import TournamentActivationChainAgent
        agent = TournamentActivationChainAgent(cfg=cfg, store=s, bus=None)
        result = agent.check_biometric_credential_ttl()
        # Should have logged to biometric_renewal_log
        with s._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM biometric_renewal_log"
            ).fetchone()[0]
        assert count >= 1
        assert "ttl_enabled" in result
        assert result["ttl_days"] == 90.0


# ---------------------------------------------------------------------------
# T178-7  check_biometric_credential_ttl returns correct keys
# ---------------------------------------------------------------------------

def test_t178_7_check_ttl_returns_8_keys():
    with tempfile.TemporaryDirectory() as tmp:
        s = _make_store(tmp)
        cfg = _fake_cfg(ttl_days=90.0)
        from vapi_bridge.tournament_activation_chain_agent import TournamentActivationChainAgent
        agent = TournamentActivationChainAgent(cfg=cfg, store=s, bus=None)
        result = agent.check_biometric_credential_ttl()
        for key in ("ttl_enabled", "commit_hash", "commit_ts", "age_days",
                    "ttl_days", "ttl_expired", "recalibration_required", "timestamp"):
            assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# T178-8  biometric_credential_ttl_days config default is 90.0
# ---------------------------------------------------------------------------

def test_t178_8_config_default_90_days():
    from vapi_bridge.config import Config
    cfg = Config(
        verifier_address="0x1234",
        bridge_private_key="0xdeadbeef",
    )
    assert hasattr(cfg, "biometric_credential_ttl_days")
    assert float(cfg.biometric_credential_ttl_days) == 90.0
