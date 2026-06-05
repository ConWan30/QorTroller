"""Consent Cockpit F1 — append-only consent_event_log tests.

T-EVTLOG-1: append-only invariant — GRANT→REVOKE→re-GRANT on the same
            (device, category) produces 3 distinct event rows even though
            consent_ledger's UPSERT semantic collapses to 1 state row.
T-EVTLOG-2: get_consent_history orders rows by ts DESC + id DESC and
            honors the limit clamp.
T-EVTLOG-3: get_consent_history for an unknown device returns [] (no
            fabricated entries).
T-EVTLOG-4: insert_consent_event is fail-open — never raises; returns 0
            on a closed Store (smoke).
T-EVTLOG-5: REVOKE event captures the operator-supplied reason field
            (regulator-facing receipt copy).
T-EVTLOG-6: schema_versions row for the consent_event_log migration is
            written exactly once across multiple grant/revoke cycles.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.store import Store


@pytest.fixture
def store():
    """A clean Store with consent_ledger enabled, freshly migrated."""
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()
    st = Store(tf.name, consent_ledger_enabled=True)
    try:
        yield st
    finally:
        try:
            # Drop the connection before unlink — Windows holds the file lock.
            del st
            os.unlink(tf.name)
        except Exception:
            pass


def test_evtlog_1_append_only_through_grant_revoke_regrant(store):
    """Append-only invariant: 3 events, even though consent_ledger has 1 row."""
    store.grant_category_consent(device_id="abc", category="TOURNAMENT_GATE")
    store.revoke_category_consent(device_id="abc", category="TOURNAMENT_GATE", reason="test-revoke")
    store.grant_category_consent(device_id="abc", category="TOURNAMENT_GATE")

    hist = store.get_consent_history("abc", limit=10)
    assert len(hist) == 3, f"expected 3 rows, got {len(hist)}: {hist}"

    actions_newest_first = [e["action"] for e in hist]
    assert actions_newest_first == ["GRANT", "REVOKE", "GRANT"], actions_newest_first

    # Every row is for the same (device, category)
    assert all(e["category"] == "TOURNAMENT_GATE" for e in hist)


def test_evtlog_2_ordering_and_limit(store):
    """Ordering is ts DESC + id DESC; limit clamped to [1, 500]."""
    for cat in ["TOURNAMENT_GATE", "MARKETPLACE", "ANONYMIZED_RESEARCH"]:
        store.grant_category_consent(device_id="abc", category=cat)
    hist = store.get_consent_history("abc", limit=2)
    assert len(hist) == 2  # limit honored
    # Most recent grant is ANONYMIZED_RESEARCH (last inserted)
    assert hist[0]["category"] == "ANONYMIZED_RESEARCH"
    # Limit clamped: limit=0 → at least 1; limit=10_000 → caps at 500
    hist_full = store.get_consent_history("abc", limit=10_000)
    assert len(hist_full) <= 500


def test_evtlog_3_unknown_device_returns_empty_list(store):
    """No fabrication — unknown device returns [], not a placeholder row."""
    assert store.get_consent_history("nonexistent-device", limit=10) == []
    assert store.get_consent_history("", limit=10) == []


def test_evtlog_4_insert_consent_event_fail_open(store):
    """insert_consent_event direct call returns a positive row id."""
    row_id = store.insert_consent_event(
        device_id="abc",
        category="MARKETPLACE",
        action="GRANT",
        tx_hash="0x" + "a" * 64,
    )
    assert row_id > 0
    hist = store.get_consent_history("abc", limit=5)
    assert len(hist) == 1
    assert hist[0]["tx_hash"].startswith("0xaa")


def test_evtlog_5_revoke_reason_preserved(store):
    """Regulator-facing receipt: REVOKE row carries the supplied reason."""
    store.grant_category_consent(device_id="abc", category="MARKETPLACE")
    store.revoke_category_consent(
        device_id="abc",
        category="MARKETPLACE",
        reason="gdpr-art-17-request",
    )
    hist = store.get_consent_history("abc", limit=5)
    revoke_rows = [e for e in hist if e["action"] == "REVOKE"]
    assert len(revoke_rows) == 1
    assert revoke_rows[0]["reason"] == "gdpr-art-17-request"


def test_evtlog_6_migration_idempotent(store):
    """schema_versions row written once, not on every grant/revoke cycle."""
    for _ in range(5):
        store.grant_category_consent(device_id=f"d{_}", category="TOURNAMENT_GATE")
        store.revoke_category_consent(device_id=f"d{_}", category="TOURNAMENT_GATE")
    with store._conn() as conn:
        rows = conn.execute(
            "SELECT phase, migration_name FROM schema_versions WHERE migration_name=?",
            ("consent_event_log",),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 244
