"""Phase 185 bridge tests — ReEnrollmentAttestationAgent (WIF-032 W1 closure).

8 tests:
  T185-1  persona_break_attestation_log table created; schema phase 185 registered
  T185-2  insert_persona_break_attestation stores row; get_active_attestation retrieves it
  T185-3  get_active_attestation returns latest active row for a player
  T185-4  expire_stale_attestations sets active=0 for expired rows; active rows untouched
  T185-5  _compute_attestation_hash returns HMAC prefix when secret set
  T185-6  _compute_attestation_hash returns SHA-256 prefix when secret empty (test mode)
  T185-7  Config fields reauth_attestation_enabled/ttl_days/secret present with correct defaults
  T185-8  GET /agent/reenrollment-attestation-status registered in operator_app routes
"""
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ---------------------------------------------------------------------------
# T185-1  Table created; schema phase 185 registered
# ---------------------------------------------------------------------------

def test_t185_1_table_and_schema():
    import sqlite3
    with tempfile.TemporaryDirectory() as tmp:
        from vapi_bridge.store import Store
        db_path = str(Path(tmp) / "t185_schema.db")
        Store(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Table exists
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert "persona_break_attestation_log" in tables, \
            f"persona_break_attestation_log not in {tables}"

        # Schema version 185 registered
        phases = {r["phase"] for r in conn.execute(
            "SELECT phase FROM schema_versions"
        ).fetchall()}
        assert 185 in phases, f"Phase 185 not in schema_versions: {phases}"
        conn.close()


# ---------------------------------------------------------------------------
# T185-2  insert_persona_break_attestation stores; get_active_attestation retrieves
# ---------------------------------------------------------------------------

def test_t185_2_insert_and_retrieve():
    with tempfile.TemporaryDirectory() as tmp:
        from vapi_bridge.store import Store
        s = Store(str(Path(tmp) / "t185_insert.db"))

        now = time.time()
        row_id = s.insert_persona_break_attestation(
            player_id="P1",
            hash="hmac:abcdef1234567890",
            loo_trend=0.10,
            tdi=0.25,
            ttl_days=7.0,
            issued_at=now,
            expires_at=now + 7 * 86400,
        )
        assert row_id > 0

        result = s.get_active_attestation("P1")
        assert result["player_id"] == "P1"
        assert result["attestation_hash"] == "hmac:abcdef1234567890"
        assert result["active"] is True
        assert result["loo_trend_at_break"] == pytest.approx(0.10, abs=1e-6)


# ---------------------------------------------------------------------------
# T185-3  get_active_attestation returns latest active row; skips player_id filter
# ---------------------------------------------------------------------------

def test_t185_3_active_attestation_player_filter():
    import pytest
    with tempfile.TemporaryDirectory() as tmp:
        from vapi_bridge.store import Store
        s = Store(str(Path(tmp) / "t185_filter.db"))

        now = time.time()
        s.insert_persona_break_attestation(
            player_id="P1", hash="hmac:p1hash",
            loo_trend=0.05, tdi=0.3, ttl_days=7.0,
            issued_at=now, expires_at=now + 7 * 86400,
        )
        s.insert_persona_break_attestation(
            player_id="P2", hash="hmac:p2hash",
            loo_trend=0.08, tdi=0.2, ttl_days=7.0,
            issued_at=now, expires_at=now + 7 * 86400,
        )

        result_p1 = s.get_active_attestation("P1")
        assert result_p1["attestation_hash"] == "hmac:p1hash"

        result_p2 = s.get_active_attestation("P2")
        assert result_p2["attestation_hash"] == "hmac:p2hash"

        # Unknown player → active=False
        result_px = s.get_active_attestation("PX")
        assert result_px["active"] is False
        assert result_px["attestation_hash"] == ""


# ---------------------------------------------------------------------------
# T185-4  expire_stale_attestations sets active=0 for expired; active rows untouched
# ---------------------------------------------------------------------------

def test_t185_4_expire_stale_attestations():
    with tempfile.TemporaryDirectory() as tmp:
        from vapi_bridge.store import Store
        s = Store(str(Path(tmp) / "t185_expire.db"))

        now = time.time()
        # Insert one already-expired row (expires in the past)
        s.insert_persona_break_attestation(
            player_id="P1", hash="sha256:stale",
            loo_trend=0.10, tdi=0.2, ttl_days=0.0,
            issued_at=now - 200, expires_at=now - 100,  # already expired
        )
        # Insert one still-active row (expires in the future)
        s.insert_persona_break_attestation(
            player_id="P2", hash="hmac:fresh",
            loo_trend=0.15, tdi=0.3, ttl_days=7.0,
            issued_at=now, expires_at=now + 7 * 86400,
        )

        expired_count = s.expire_stale_attestations()
        assert expired_count == 1, f"Expected 1 expired; got {expired_count}"

        # Stale row now inactive
        stale = s.get_active_attestation("P1")
        assert stale["active"] is False

        # Fresh row still active
        fresh = s.get_active_attestation("P2")
        assert fresh["active"] is True


# ---------------------------------------------------------------------------
# T185-5  HMAC mode when secret set
# ---------------------------------------------------------------------------

def test_t185_5_hmac_mode_with_secret():
    from vapi_bridge.reenrollment_attestation_agent import ReEnrollmentAttestationAgent

    class _FakeCfg:
        reauth_attestation_enabled  = True
        reauth_attestation_ttl_days = 7.0
        reauth_attestation_secret   = "test-operator-secret-key"

    agent = ReEnrollmentAttestationAgent(_FakeCfg(), None, None)
    h, hmac_mode = agent._compute_attestation_hash("P1", 1234567890, 0.10, 0.25, 7.0)

    assert hmac_mode is True, "Expected hmac_mode=True when secret set"
    assert h.startswith("hmac:"), f"Expected 'hmac:' prefix; got: {h}"
    assert len(h) == len("hmac:") + 64  # 32 bytes = 64 hex chars


# ---------------------------------------------------------------------------
# T185-6  SHA-256 fallback when secret empty (test mode)
# ---------------------------------------------------------------------------

def test_t185_6_sha256_fallback_no_secret():
    from vapi_bridge.reenrollment_attestation_agent import ReEnrollmentAttestationAgent

    class _FakeCfg:
        reauth_attestation_enabled  = True
        reauth_attestation_ttl_days = 7.0
        reauth_attestation_secret   = ""

    agent = ReEnrollmentAttestationAgent(_FakeCfg(), None, None)
    h, hmac_mode = agent._compute_attestation_hash("P1", 1234567890, 0.10, 0.25, 7.0)

    assert hmac_mode is False, "Expected hmac_mode=False when secret empty"
    assert h.startswith("sha256:"), f"Expected 'sha256:' prefix; got: {h}"
    assert len(h) == len("sha256:") + 64  # 32 bytes = 64 hex chars

    # Deterministic: same inputs → same hash
    h2, _ = agent._compute_attestation_hash("P1", 1234567890, 0.10, 0.25, 7.0)
    assert h == h2

    # Different player → different hash
    h3, _ = agent._compute_attestation_hash("P2", 1234567890, 0.10, 0.25, 7.0)
    assert h != h3


# ---------------------------------------------------------------------------
# T185-7  Config fields present with correct defaults
# ---------------------------------------------------------------------------

def test_t185_7_config_fields():
    from vapi_bridge.config import Config
    cfg = Config()

    assert hasattr(cfg, "reauth_attestation_enabled")
    assert cfg.reauth_attestation_enabled is True

    assert hasattr(cfg, "reauth_attestation_ttl_days")
    assert cfg.reauth_attestation_ttl_days == 7.0

    assert hasattr(cfg, "reauth_attestation_secret")
    assert cfg.reauth_attestation_secret == ""  # empty by default (no env set)


# ---------------------------------------------------------------------------
# T185-8  GET /agent/reenrollment-attestation-status registered in operator_app
# ---------------------------------------------------------------------------

def test_t185_8_endpoint_registered():
    import tempfile
    from vapi_bridge.store import Store
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    with tempfile.TemporaryDirectory() as tmp:
        store = Store(str(Path(tmp) / "t185_routes.db"))
        cfg   = Config()
        object.__setattr__(cfg, "operator_api_key", "test-key-185")

        app    = create_operator_app(cfg, store)
        routes = {r.path for r in app.routes}
        assert "/agent/reenrollment-attestation-status" in routes, \
            f"reenrollment-attestation-status not found in {routes}"


import pytest
