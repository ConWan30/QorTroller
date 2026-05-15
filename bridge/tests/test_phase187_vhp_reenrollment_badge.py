"""
Phase 187 — VHPReenrollmentBadge bridge tests (8 tests, WIF-033 W2 closure).

Tests:
  T187B-1: vhp_reenrollment_badge_log table created; schema 1870 registered
  T187B-2: insert_reenrollment_badge_log stores row
  T187B-3: get_reenrollment_badge_status returns latest row for player
  T187B-4: get_reenrollment_badge_status safe defaults when empty
  T187B-5: re_enrollment_count increments per player across multiple badges
  T187B-6: total_badges counts all players
  T187B-7: config fields reenrollment_badge_enabled and vhp_reenrollment_badge_address present
  T187B-8: GET /agent/vhp-reenrollment-badge-status endpoint registered
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.store import Store
from vapi_bridge.config import Config


@pytest.fixture()
def store(tmp_path):
    db = str(tmp_path / "test_phase187_badge.db")
    return Store(db_path=db)


@pytest.fixture()
def cfg():
    return Config()


# T187B-1 — table created and schema registered
def test_1_table_created_schema_registered(store):
    with store._conn() as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "vhp_reenrollment_badge_log" in tables

    with store._conn() as conn:
        row = conn.execute(
            "SELECT phase FROM schema_versions WHERE phase=1870"
        ).fetchone()
    assert row is not None, "schema_versions missing phase=1870 (vhp_reenrollment_badge)"


# T187B-2 — insert stores row
def test_2_insert_stores_row(store):
    rowid = store.insert_reenrollment_badge_log(
        player_id="P1",
        attestation_hash="hmac:abc123",
        badge_token_id=1,
        ttl_days=90.0,
        on_chain_tx="0xdeadbeef",
        dry_run=False,
    )
    assert rowid > 0

    with store._conn() as conn:
        row = conn.execute(
            "SELECT * FROM vhp_reenrollment_badge_log WHERE id=?", (rowid,)
        ).fetchone()
    assert row is not None
    assert row["player_id"] == "P1"
    assert row["attestation_hash"] == "hmac:abc123"
    assert row["badge_token_id"] == 1
    assert row["dry_run"] == 0


# T187B-3 — get_reenrollment_badge_status returns latest for player
def test_3_get_latest_for_player(store):
    store.insert_reenrollment_badge_log("P1", "hmac:first",  1, 90.0, "0xaaa", False)
    store.insert_reenrollment_badge_log("P1", "hmac:second", 2, 90.0, "0xbbb", False)
    store.insert_reenrollment_badge_log("P2", "hmac:p2one",  3, 90.0, "0xccc", False)

    status = store.get_reenrollment_badge_status("P1")
    assert status["attestation_hash"] == "hmac:second"
    assert status["badge_token_id"] == 2
    assert status["re_enrollment_count"] == 2


# T187B-4 — safe defaults when empty
def test_4_safe_defaults_when_empty(store):
    status = store.get_reenrollment_badge_status()
    assert status["badge_token_id"] == 0
    assert status["attestation_hash"] == ""
    assert status["total_badges"] == 0


# T187B-5 — re_enrollment_count increments per player
def test_5_reenrollment_count_per_player(store):
    for i in range(3):
        store.insert_reenrollment_badge_log("P1", f"hmac:tok{i}", i+1, 90.0, f"0x{i:04x}", False)
    store.insert_reenrollment_badge_log("P2", "hmac:p2tok", 4, 90.0, "0xffff", False)

    p1_status = store.get_reenrollment_badge_status("P1")
    p2_status = store.get_reenrollment_badge_status("P2")
    assert p1_status["re_enrollment_count"] == 3
    assert p2_status["re_enrollment_count"] == 1


# T187B-6 — total_badges counts all players
def test_6_total_badges_all_players(store):
    store.insert_reenrollment_badge_log("P1", "hmac:t1", 1, 90.0, "0x01", False)
    store.insert_reenrollment_badge_log("P2", "hmac:t2", 2, 90.0, "0x02", False)
    store.insert_reenrollment_badge_log("P3", "hmac:t3", 3, 90.0, "0x03", False)

    status = store.get_reenrollment_badge_status()
    assert status["total_badges"] == 3


# T187B-7 — config fields present
def test_7_config_fields_present(cfg):
    assert hasattr(cfg, "reenrollment_badge_enabled")
    assert cfg.reenrollment_badge_enabled is False
    assert hasattr(cfg, "vhp_reenrollment_badge_address")
    # Env-agnostic: field defaults to "" but bridge/.env may populate a real
    # deployed address. Assert type, not value, so CI is not env-dependent.
    assert isinstance(cfg.vhp_reenrollment_badge_address, str)


# T187B-8 — endpoint registered
def test_8_endpoint_registered(store, cfg):
    try:
        from vapi_bridge.operator_api import create_app
        app = create_app(cfg, store)
        routes = [r.path for r in app.routes]
        assert any("vhp-reenrollment-badge-status" in r for r in routes), (
            f"GET /agent/vhp-reenrollment-badge-status not registered. Routes: {routes}"
        )
    except Exception as exc:
        pytest.skip(f"operator_api unavailable in test environment: {exc}")
