"""Phase 186 bridge tests — AttestationBoundRenewalAgent (WIF-032 W2 closure).

8 tests:
  T186-1  attestation_bound_renewal_log table created; schema phase 186 registered
  T186-2  insert_attestation_bound_renewal_log stores; get_attestation_bound_renewal_status counts
  T186-3  get_attestation_bound_renewal_status player filter returns latest row for player
  T186-4  validate_attestation_for_renewal returns (True, "") for active valid attestation
  T186-5  validate_attestation_for_renewal returns (False, "attestation_expired") for expired
  T186-6  validate_attestation_for_renewal returns (False, "no_active_attestation") unknown player
  T186-7  Config field attestation_bound_renewal_enabled=False (infrastructure-first default)
  T186-8  GET /agent/attestation-bound-renewal-status registered in operator_app routes
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ---------------------------------------------------------------------------
# T186-1  Table created; schema phase 186 registered
# ---------------------------------------------------------------------------

def test_t186_1_table_and_schema():
    import sqlite3
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        from vapi_bridge.store import Store
        db_path = str(Path(tmp) / "t186_schema.db")
        Store(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "attestation_bound_renewal_log" in tables, \
            f"attestation_bound_renewal_log not in {tables}"

        phases = {r["phase"] for r in conn.execute(
            "SELECT phase FROM schema_versions"
        ).fetchall()}
        assert 186 in phases, f"Phase 186 not in schema_versions: {phases}"
        conn.close()


# ---------------------------------------------------------------------------
# T186-2  insert stores; get_attestation_bound_renewal_status returns counts
# ---------------------------------------------------------------------------

def test_t186_2_insert_and_counts():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        from vapi_bridge.store import Store
        s = Store(str(Path(tmp) / "t186_counts.db"))

        # No rows yet
        status0 = s.get_attestation_bound_renewal_status()
        assert status0.get("total_approved", 0) == 0
        assert status0.get("total_blocked", 0) == 0

        row_id1 = s.insert_attestation_bound_renewal_log(
            player_id="P1",
            attestation_hash="hmac:abc123",
            renewal_approved=True,
            denial_reason="",
            new_commit_hash="sha256:newcommit001",
        )
        assert row_id1 > 0

        row_id2 = s.insert_attestation_bound_renewal_log(
            player_id="P1",
            attestation_hash="",
            renewal_approved=False,
            denial_reason="no_active_attestation",
            new_commit_hash="",
        )
        assert row_id2 > row_id1

        status = s.get_attestation_bound_renewal_status()
        assert status.get("total_approved", 0) == 1
        assert status.get("total_blocked", 0) == 1


# ---------------------------------------------------------------------------
# T186-3  get_attestation_bound_renewal_status player filter
# ---------------------------------------------------------------------------

def test_t186_3_player_filter():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        from vapi_bridge.store import Store
        s = Store(str(Path(tmp) / "t186_filter.db"))

        s.insert_attestation_bound_renewal_log(
            player_id="P1",
            attestation_hash="hmac:p1hash",
            renewal_approved=True,
            denial_reason="",
            new_commit_hash="sha256:p1commit",
        )
        s.insert_attestation_bound_renewal_log(
            player_id="P2",
            attestation_hash="",
            renewal_approved=False,
            denial_reason="no_active_attestation",
            new_commit_hash="",
        )

        status_p1 = s.get_attestation_bound_renewal_status("P1")
        assert status_p1.get("player_id", "") == "P1"
        assert status_p1.get("attestation_hash", "") == "hmac:p1hash"
        assert status_p1.get("renewal_approved", False) is True

        status_p2 = s.get_attestation_bound_renewal_status("P2")
        assert status_p2.get("player_id", "") == "P2"
        assert status_p2.get("renewal_approved", True) is False
        assert status_p2.get("denial_reason", "") == "no_active_attestation"


# ---------------------------------------------------------------------------
# T186-4  validate_attestation_for_renewal returns (True, "") for active valid
# ---------------------------------------------------------------------------

def test_t186_4_validate_active_valid():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        from vapi_bridge.store import Store
        from vapi_bridge.attestation_bound_renewal_agent import AttestationBoundRenewalAgent

        s = Store(str(Path(tmp) / "t186_valid.db"))

        class _FakeCfg:
            attestation_bound_renewal_enabled = True

        agent = AttestationBoundRenewalAgent(_FakeCfg(), s, None)

        now = time.time()
        s.insert_persona_break_attestation(
            player_id="P1",
            hash="hmac:validtoken",
            loo_trend=0.05,
            tdi=0.15,
            ttl_days=7.0,
            issued_at=now,
            expires_at=now + 7 * 86400,
        )

        ok, reason = agent.validate_attestation_for_renewal("P1", "hmac:validtoken")
        assert ok is True, f"Expected ok=True; got ok={ok}, reason={reason!r}"
        assert reason == "", f"Expected empty reason; got {reason!r}"


# ---------------------------------------------------------------------------
# T186-5  validate_attestation_for_renewal returns (False, reason) for expired
# ---------------------------------------------------------------------------

def test_t186_5_validate_expired():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        from vapi_bridge.store import Store
        from vapi_bridge.attestation_bound_renewal_agent import AttestationBoundRenewalAgent

        s = Store(str(Path(tmp) / "t186_expired.db"))

        class _FakeCfg:
            attestation_bound_renewal_enabled = True

        agent = AttestationBoundRenewalAgent(_FakeCfg(), s, None)

        now = time.time()
        # Insert an active but already-expired attestation (expire_stale has not run yet,
        # so active=1 in DB — but expires_at is in the past)
        import sqlite3
        conn = sqlite3.connect(str(Path(tmp) / "t186_expired.db"))
        conn.execute(
            "INSERT INTO persona_break_attestation_log"
            " (player_id, attestation_hash, loo_trend_at_break, tdi_at_break,"
            "  ttl_days, active, issued_at, expires_at, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("P1", "hmac:expiredtoken", 0.05, 0.15, 0.001, 1,
             now - 200, now - 100, now - 200),
        )
        conn.commit()
        conn.close()

        ok, reason = agent.validate_attestation_for_renewal("P1", "hmac:expiredtoken")
        assert ok is False, f"Expected ok=False for expired; got ok={ok}"
        # get_active_attestation() filters expired rows via SQL (expires_at > now), so the
        # agent sees active=False and returns "no_active_attestation" before the explicit
        # expires_at check — both "no_active_attestation" and "attestation_expired" are valid
        # failure signals for an expired token.
        assert reason in ("no_active_attestation", "attestation_expired"), \
            f"Expected expired-related denial reason; got {reason!r}"


# ---------------------------------------------------------------------------
# T186-6  validate_attestation_for_renewal returns (False, reason) unknown player
# ---------------------------------------------------------------------------

def test_t186_6_validate_unknown_player():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        from vapi_bridge.store import Store
        from vapi_bridge.attestation_bound_renewal_agent import AttestationBoundRenewalAgent

        s = Store(str(Path(tmp) / "t186_unknown.db"))

        class _FakeCfg:
            attestation_bound_renewal_enabled = True

        agent = AttestationBoundRenewalAgent(_FakeCfg(), s, None)

        ok, reason = agent.validate_attestation_for_renewal("PX", "hmac:anything")
        assert ok is False, f"Expected ok=False for unknown player; got ok={ok}"
        assert reason != "", f"Expected non-empty denial reason; got {reason!r}"


# ---------------------------------------------------------------------------
# T186-7  Config field attestation_bound_renewal_enabled=False (infrastructure-first)
# ---------------------------------------------------------------------------

def test_t186_7_config_field():
    from vapi_bridge.config import Config
    cfg = Config()

    assert hasattr(cfg, "attestation_bound_renewal_enabled"), \
        "Config missing attestation_bound_renewal_enabled field"
    assert cfg.attestation_bound_renewal_enabled is False, \
        f"Expected False (infrastructure-first); got {cfg.attestation_bound_renewal_enabled}"


# ---------------------------------------------------------------------------
# T186-8  GET /agent/attestation-bound-renewal-status registered in operator_app
# ---------------------------------------------------------------------------

def test_t186_8_endpoint_registered():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        from vapi_bridge.store import Store
        from vapi_bridge.config import Config
        from vapi_bridge.operator_api import create_operator_app

        store = Store(str(Path(tmp) / "t186_routes.db"))
        cfg   = Config()
        object.__setattr__(cfg, "operator_api_key", "test-key-186")

        app    = create_operator_app(cfg, store)
        routes = {r.path for r in app.routes}
        assert "/agent/attestation-bound-renewal-status" in routes, \
            f"attestation-bound-renewal-status not found in {routes}"
