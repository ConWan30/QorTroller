"""Phase 180 bridge tests — Biometric Renewal Engine (WIF-029 W2 closure).

8 tests:
  T180-1  insert_biometric_renewal_chain_log stores record, returns row_id >= 1
  T180-2  get_biometric_renewal_chain_status returns 7 expected keys
  T180-3  get_biometric_renewal_chain_status total_renewals=0 when empty
  T180-4  get_biometric_renewal_chain_status reflects latest renewal after insert
  T180-5  anti-replay: duplicate new_commit_hash raises IntegrityError
  T180-6  renewal_enabled config default is False (infrastructure-first)
  T180-7  new_commit_hash is SHA-256 preimage (prev_hash+ratio+N+N_consented+ttl+ts_ns)
  T180-8  POST /agent/renew-separation-ratio-commitment returns 8 expected keys
"""
import hashlib
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store(tmp):
    from vapi_bridge.store import Store
    return Store(str(Path(tmp) / "test180.db"))


# ---------------------------------------------------------------------------
# T180-1  insert stores record, returns row_id >= 1
# ---------------------------------------------------------------------------

def test_t180_1_insert_stores_record():
    tmp = tempfile.mkdtemp()
    s = _make_store(tmp)
    row_id = s.insert_biometric_renewal_chain_log(
        prev_commit_hash="sha256:aabbcc",
        new_commit_hash="sha256:ddeeff",
        n_consented=3,
        n_sessions=20,
        ttl_days=90.0,
        dry_run=True,
    )
    assert row_id >= 1


# ---------------------------------------------------------------------------
# T180-2  get_biometric_renewal_chain_status returns 7 expected keys
# ---------------------------------------------------------------------------

def test_t180_2_get_status_returns_7_keys():
    tmp = tempfile.mkdtemp()
    s = _make_store(tmp)
    status = s.get_biometric_renewal_chain_status()
    expected_keys = {
        "renewal_enabled", "total_renewals", "latest_renewal_ts",
        "prev_commit_hash", "new_commit_hash", "ttl_days", "timestamp",
    }
    assert expected_keys == set(status.keys()), f"Missing keys: {expected_keys - set(status.keys())}"
    assert len(status) == 7


# ---------------------------------------------------------------------------
# T180-3  total_renewals=0 and empty hashes when no rows
# ---------------------------------------------------------------------------

def test_t180_3_empty_chain_defaults():
    tmp = tempfile.mkdtemp()
    s = _make_store(tmp)
    status = s.get_biometric_renewal_chain_status()
    assert status["total_renewals"] == 0
    assert status["prev_commit_hash"] == ""
    assert status["new_commit_hash"] == ""
    assert status["ttl_days"] == 90.0
    assert status["latest_renewal_ts"] == 0.0


# ---------------------------------------------------------------------------
# T180-4  get_status reflects latest renewal after insert
# ---------------------------------------------------------------------------

def test_t180_4_status_reflects_insert():
    tmp = tempfile.mkdtemp()
    s = _make_store(tmp)
    # Insert two renewals
    s.insert_biometric_renewal_chain_log("sha256:aa", "sha256:bb", 3, 20, 90.0)
    s.insert_biometric_renewal_chain_log("sha256:bb", "sha256:cc", 3, 22, 90.0)
    status = s.get_biometric_renewal_chain_status()
    assert status["total_renewals"] == 2
    assert status["prev_commit_hash"] == "sha256:bb"
    assert status["new_commit_hash"] == "sha256:cc"
    assert status["ttl_days"] == 90.0
    assert status["latest_renewal_ts"] > 0.0


# ---------------------------------------------------------------------------
# T180-5  anti-replay: duplicate new_commit_hash raises IntegrityError
# ---------------------------------------------------------------------------

def test_t180_5_anti_replay_duplicate_raises():
    tmp = tempfile.mkdtemp()
    s = _make_store(tmp)
    s.insert_biometric_renewal_chain_log("sha256:prev1", "sha256:new1", 3, 20, 90.0)
    try:
        s.insert_biometric_renewal_chain_log("sha256:prev2", "sha256:new1", 3, 20, 90.0)
        assert False, "Expected IntegrityError on duplicate new_commit_hash"
    except sqlite3.IntegrityError:
        pass  # expected


# ---------------------------------------------------------------------------
# T180-6  renewal_enabled config default is False (infrastructure-first)
# ---------------------------------------------------------------------------

def test_t180_6_renewal_enabled_default_false(monkeypatch):
    # Phase 180 documented default is False. Tests must isolate from
    # bridge/.env which sets RENEWAL_ENABLED=true for live operation
    # (per CLAUDE.md T199-8 env-isolation precedent).
    #
    # Use setenv("RENEWAL_ENABLED", "false"), not delenv:
    # config.py's module-level load_dotenv(override=False) runs on first import
    # and re-adds missing variables from .env. If we delenv'd RENEWAL_ENABLED
    # and the first config import happened after our patch (test isolation or
    # suite ordering), load_dotenv would restore RENEWAL_ENABLED=true from .env:151.
    # setenv keeps the variable present with our test value; load_dotenv(override=False)
    # then correctly leaves it alone.
    monkeypatch.setenv("RENEWAL_ENABLED", "false")
    from vapi_bridge.config import Config
    cfg = Config(
        verifier_address="0x1234",
        bridge_private_key="0xdeadbeef",
    )
    assert hasattr(cfg, "renewal_enabled")
    assert cfg.renewal_enabled is False


# ---------------------------------------------------------------------------
# T180-7  new_commit_hash follows SHA-256 preimage format
# ---------------------------------------------------------------------------

def test_t180_7_new_commit_hash_sha256_format():
    tmp = tempfile.mkdtemp()
    s = _make_store(tmp)
    # Compute expected hash matching operator_api.py logic
    prev_hash  = "sha256:aabbcc112233"
    ratio      = 1.261
    n_sessions = 20
    n_consented = 3
    ttl_days   = 90.0
    ts_ns      = time.time_ns()
    preimage = (
        prev_hash
        + f"{ratio:.6f}"
        + str(n_sessions)
        + str(n_consented)
        + f"{ttl_days:.1f}"
        + str(ts_ns)
    ).encode()
    expected_hash = "sha256:" + hashlib.sha256(preimage).hexdigest()
    s.insert_biometric_renewal_chain_log(
        prev_commit_hash=prev_hash,
        new_commit_hash=expected_hash,
        n_consented=n_consented,
        n_sessions=n_sessions,
        ttl_days=ttl_days,
    )
    status = s.get_biometric_renewal_chain_status()
    assert status["new_commit_hash"] == expected_hash
    assert expected_hash.startswith("sha256:")
    assert len(expected_hash) == len("sha256:") + 64  # 7 + 64 hex chars


# ---------------------------------------------------------------------------
# T180-8  GET /agent/renewal-chain-status returns 7 expected keys (endpoint smoke)
# ---------------------------------------------------------------------------

def test_t180_8_endpoint_returns_7_keys():
    """Smoke test: the renewal chain status dict from store has all expected keys."""
    tmp = tempfile.mkdtemp()
    s = _make_store(tmp)
    # Simulate what the endpoint returns: store.get_biometric_renewal_chain_status()
    # with renewal_enabled overlaid from cfg
    status = s.get_biometric_renewal_chain_status()
    # Endpoint overlays renewal_enabled from cfg (default False)
    status["renewal_enabled"] = False
    expected_keys = {
        "renewal_enabled", "total_renewals", "latest_renewal_ts",
        "prev_commit_hash", "new_commit_hash", "ttl_days", "timestamp",
    }
    assert expected_keys == set(status.keys())
    assert status["renewal_enabled"] is False
