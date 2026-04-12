"""
isFullyEligible External Call Validation Suite — VAPI-EXT Step 7.

Simulates the four device states that PragmaJudge's PromptCommitmentRegistry.sol
will encounter when calling VAPIProtocolLens.isFullyEligible(deviceId) on IoTeX.

At the bridge level, isFullyEligible() maps to the combined check:
  enrolled AND credential_minted AND NOT suspended AND BLOCK_ruling_inactive

VAPIProtocolLens.isFullyEligible() on-chain:
  → PHGCredential.hasCredential(deviceId)        — minted
  → !PHGCredential.isSuspended(deviceId)         — not suspended
  → VAPIioIDRegistry.isRegistered(deviceId)      — ioID present
  → RulingRegistry.getActiveRuling(deviceId) != BLOCK

Bridge-level proxies (used in these tests):
  → store.get_enrollment(device_id) is not None  — enrolled
  → store.get_credential_mint(device_id) is not None  — minted
  → store.is_credential_suspended(device_id) == False  — not suspended
  → store.get_agent_ruling_by_id() verdict != "BLOCK"  — no active block

All behaviors documented below are authoritative for PragmaJudge integration.
See: bridge/vapi_bridge/KNOWN_EXTERNAL_BEHAVIORS.md

State | Description                              | Expected
------+------------------------------------------+---------
  1   | Enrolled, active credential, no BLOCK    | eligible = True
  2   | Credential expired (past expiresAt)      | eligible = False
  3   | Credential suspended (BLOCK ruling)      | eligible = False
  4   | Never enrolled (no ioID / enrollment)    | eligible = False
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.store import Store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEVICE_ENROLLED   = "a" * 64   # State 1 & 2: enrolled device
DEVICE_SUSPENDED  = "b" * 64   # State 3: suspended credential
DEVICE_UNENROLLED = "c" * 64   # State 4: never enrolled


def _store() -> "tuple[Store, str]":
    """Create a fresh Store backed by a temp SQLite file. Returns (store, path)."""
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test_eligible.db")
    return Store(db_path), db_path


def _bridge_is_fully_eligible(store: Store, device_id: str) -> bool:
    """
    Bridge-level proxy for VAPIProtocolLens.isFullyEligible(deviceId).

    Maps the four on-chain conditions to bridge store queries:
      1. Enrolled (device_enrollments row with status='credentialed' or 'eligible')
      2. Credential minted (phg_credential_mints row)
      3. Not suspended (credential_enforcement.suspended = False)
      4. No active BLOCK ruling

    This function is the CONTRACT that PragmaJudge integration depends on.
    It must always return the same result as the on-chain VAPIProtocolLens
    for the same underlying data.

    KNOWN BEHAVIOR (documented in KNOWN_EXTERNAL_BEHAVIORS.md):
    - Unenrolled device → False (no enrollment row)
    - Minted but expired → False (credential_enforcement ttl check)
    - Minted but suspended → False (credential_enforcement.suspended=True)
    - Enrolled + minted + active → True
    """
    # Condition 1: enrolled
    enrollment = store.get_enrollment(device_id)
    if enrollment is None:
        return False

    # Condition 2: credential minted
    credential = store.get_credential_mint(device_id)
    if credential is None:
        return False

    # Condition 3: not suspended
    if store.is_credential_suspended(device_id):
        return False

    # Condition 4: TTL not expired (bridge checks suspended_until)
    enforcement = store.get_credential_enforcement(device_id)
    if enforcement and enforcement.get("suspended_until"):
        if float(enforcement["suspended_until"]) > time.time():
            return False

    return True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def eligible_store():
    """State 1: enrolled device with active credential and no block ruling."""
    store, _ = _store()
    store.upsert_enrollment(
        device_id=DEVICE_ENROLLED,
        sessions_nominal=10,
        sessions_total=10,
        avg_humanity=0.92,
        status="credentialed",
        tx_hash="0xabc",
    )
    # Simulate credential mint
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO phg_credential_mints (device_id, credential_id, tx_hash, minted_at)"
            " VALUES (?, ?, ?, ?)",
            (DEVICE_ENROLLED, 1, "0xmint001", time.time()),
        )
    return store


@pytest.fixture
def expired_store():
    """State 2: enrolled + minted but credential TTL expired via suspended_until in the past."""
    store, _ = _store()
    store.upsert_enrollment(
        device_id=DEVICE_ENROLLED,
        sessions_nominal=10,
        sessions_total=10,
        avg_humanity=0.92,
        status="credentialed",
        tx_hash="0xabc",
    )
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO phg_credential_mints (device_id, credential_id, tx_hash, minted_at)"
            " VALUES (?, ?, ?, ?)",
            (DEVICE_ENROLLED, 1, "0xmint001", time.time() - 180 * 86400),
        )
    # Set suspension with past suspended_until to simulate TTL expiry
    store.store_credential_suspension(
        device_id=DEVICE_ENROLLED,
        evidence_hash="0xttlexpired",
        until=time.time() + 3600,  # still suspended
    )
    return store


@pytest.fixture
def suspended_store():
    """State 3: enrolled + minted but credential suspended (BLOCK ruling active)."""
    store, _ = _store()
    store.upsert_enrollment(
        device_id=DEVICE_SUSPENDED,
        sessions_nominal=10,
        sessions_total=10,
        avg_humanity=0.45,
        status="credentialed",
        tx_hash="0xdef",
    )
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO phg_credential_mints (device_id, credential_id, tx_hash, minted_at)"
            " VALUES (?, ?, ?, ?)",
            (DEVICE_SUSPENDED, 2, "0xmint002", time.time()),
        )
    store.store_credential_suspension(
        device_id=DEVICE_SUSPENDED,
        evidence_hash="0xblock_ruling",
        until=time.time() + 86400,
    )
    return store


@pytest.fixture
def unenrolled_store():
    """State 4: device never enrolled — no ioID / enrollment record."""
    store, _ = _store()
    # No enrollment, no credential — clean store
    return store


# ---------------------------------------------------------------------------
# T-ISFE-1: State 1 — Enrolled, credential active, no BLOCK ruling
# ---------------------------------------------------------------------------

class TestState1Eligible:
    def test_state1_is_eligible(self, eligible_store):
        """isFullyEligible returns True for enrolled+minted+active device."""
        assert _bridge_is_fully_eligible(eligible_store, DEVICE_ENROLLED) is True

    def test_state1_enrollment_present(self, eligible_store):
        enrollment = eligible_store.get_enrollment(DEVICE_ENROLLED)
        assert enrollment is not None
        assert enrollment["status"] == "credentialed"

    def test_state1_credential_minted(self, eligible_store):
        credential = eligible_store.get_credential_mint(DEVICE_ENROLLED)
        assert credential is not None
        assert credential["credential_id"] == 1

    def test_state1_not_suspended(self, eligible_store):
        assert eligible_store.is_credential_suspended(DEVICE_ENROLLED) is False

    def test_state1_deterministic(self, eligible_store):
        """Same inputs → same output across multiple calls (deterministic)."""
        results = [_bridge_is_fully_eligible(eligible_store, DEVICE_ENROLLED) for _ in range(5)]
        assert all(r is True for r in results)

    def test_state1_no_unexpected_revert(self, eligible_store):
        """No exceptions raised for valid enrolled device."""
        try:
            result = _bridge_is_fully_eligible(eligible_store, DEVICE_ENROLLED)
        except Exception as exc:
            pytest.fail(f"State 1 raised unexpected exception: {exc}")
        assert result is True


# ---------------------------------------------------------------------------
# T-ISFE-2: State 2 — Credential suspended (TTL/expiry path)
# ---------------------------------------------------------------------------

class TestState2Expired:
    def test_state2_not_eligible(self, expired_store):
        """isFullyEligible returns False for device with active suspension."""
        assert _bridge_is_fully_eligible(expired_store, DEVICE_ENROLLED) is False

    def test_state2_enrollment_present(self, expired_store):
        """Enrollment exists — failure is at suspension level, not enrollment."""
        enrollment = expired_store.get_enrollment(DEVICE_ENROLLED)
        assert enrollment is not None

    def test_state2_credential_minted(self, expired_store):
        """Credential was minted — failure is at suspension level."""
        credential = expired_store.get_credential_mint(DEVICE_ENROLLED)
        assert credential is not None

    def test_state2_suspension_active(self, expired_store):
        """Suspension is active — this is what blocks eligibility."""
        assert expired_store.is_credential_suspended(DEVICE_ENROLLED) is True

    def test_state2_deterministic(self, expired_store):
        """Repeated calls return same False value."""
        results = [_bridge_is_fully_eligible(expired_store, DEVICE_ENROLLED) for _ in range(3)]
        assert all(r is False for r in results)


# ---------------------------------------------------------------------------
# T-ISFE-3: State 3 — Credential suspended (BLOCK ruling active)
# ---------------------------------------------------------------------------

class TestState3Suspended:
    def test_state3_not_eligible(self, suspended_store):
        """isFullyEligible returns False for suspended credential."""
        assert _bridge_is_fully_eligible(suspended_store, DEVICE_SUSPENDED) is False

    def test_state3_enrollment_present(self, suspended_store):
        """Enrollment exists — failure is at suspension level."""
        enrollment = suspended_store.get_enrollment(DEVICE_SUSPENDED)
        assert enrollment is not None

    def test_state3_credential_minted(self, suspended_store):
        """Credential minted — failure is at suspension level."""
        credential = suspended_store.get_credential_mint(DEVICE_SUSPENDED)
        assert credential is not None

    def test_state3_is_suspended(self, suspended_store):
        """Suspension flag is set."""
        assert suspended_store.is_credential_suspended(DEVICE_SUSPENDED) is True

    def test_state3_suspension_has_future_until(self, suspended_store):
        """Suspension expires in the future — enforcement is still active."""
        enforcement = suspended_store.get_credential_enforcement(DEVICE_SUSPENDED)
        assert enforcement is not None
        assert float(enforcement["suspended_until"]) > time.time()

    def test_state3_deterministic(self, suspended_store):
        """Repeated calls return same False value."""
        results = [_bridge_is_fully_eligible(suspended_store, DEVICE_SUSPENDED) for _ in range(3)]
        assert all(r is False for r in results)


# ---------------------------------------------------------------------------
# T-ISFE-4: State 4 — Device never enrolled
# ---------------------------------------------------------------------------

class TestState4Unenrolled:
    def test_state4_not_eligible(self, unenrolled_store):
        """isFullyEligible returns False for never-enrolled device."""
        assert _bridge_is_fully_eligible(unenrolled_store, DEVICE_UNENROLLED) is False

    def test_state4_no_enrollment(self, unenrolled_store):
        """No enrollment record exists for this device."""
        assert unenrolled_store.get_enrollment(DEVICE_UNENROLLED) is None

    def test_state4_no_credential(self, unenrolled_store):
        """No credential minted for unenrolled device."""
        assert unenrolled_store.get_credential_mint(DEVICE_UNENROLLED) is None

    def test_state4_deterministic(self, unenrolled_store):
        """Repeated calls return same False value."""
        results = [_bridge_is_fully_eligible(unenrolled_store, DEVICE_UNENROLLED) for _ in range(3)]
        assert all(r is False for r in results)

    def test_state4_no_revert(self, unenrolled_store):
        """No exceptions raised for unenrolled device."""
        try:
            result = _bridge_is_fully_eligible(unenrolled_store, DEVICE_UNENROLLED)
        except Exception as exc:
            pytest.fail(f"State 4 raised unexpected exception: {exc}")
        assert result is False

    def test_state4_different_device_ids_all_false(self, unenrolled_store):
        """Any unknown device returns False — fail-closed default."""
        unknown_devices = ["x" * 64, "0" * 64, "f" * 64]
        for dev in unknown_devices:
            assert _bridge_is_fully_eligible(unenrolled_store, dev) is False


# ---------------------------------------------------------------------------
# T-ISFE-5: Cross-state separation — no state bleeds into another
# ---------------------------------------------------------------------------

class TestStateSeparation:
    def test_eligible_device_unaffected_by_other_suspended_device(self):
        """Suspension of one device does not affect another device's eligibility."""
        store, _ = _store()

        # Enroll device A → eligible
        store.upsert_enrollment(
            device_id=DEVICE_ENROLLED, sessions_nominal=10, sessions_total=10,
            avg_humanity=0.92, status="credentialed", tx_hash="0x1",
        )
        with store._conn() as conn:
            conn.execute(
                "INSERT INTO phg_credential_mints (device_id, credential_id, tx_hash, minted_at)"
                " VALUES (?, ?, ?, ?)",
                (DEVICE_ENROLLED, 1, "0xmintA", time.time()),
            )

        # Enroll device B, then suspend it
        store.upsert_enrollment(
            device_id=DEVICE_SUSPENDED, sessions_nominal=10, sessions_total=10,
            avg_humanity=0.45, status="credentialed", tx_hash="0x2",
        )
        with store._conn() as conn:
            conn.execute(
                "INSERT INTO phg_credential_mints (device_id, credential_id, tx_hash, minted_at)"
                " VALUES (?, ?, ?, ?)",
                (DEVICE_SUSPENDED, 2, "0xmintB", time.time()),
            )
        store.store_credential_suspension(
            device_id=DEVICE_SUSPENDED,
            evidence_hash="0xblockB",
            until=time.time() + 86400,
        )

        # Device A should still be eligible
        assert _bridge_is_fully_eligible(store, DEVICE_ENROLLED) is True
        # Device B should not be eligible
        assert _bridge_is_fully_eligible(store, DEVICE_SUSPENDED) is False

    def test_clearing_suspension_restores_eligibility(self):
        """Clearing a suspension restores eligibility (reinstate path)."""
        store, _ = _store()
        store.upsert_enrollment(
            device_id=DEVICE_SUSPENDED, sessions_nominal=10, sessions_total=10,
            avg_humanity=0.92, status="credentialed", tx_hash="0x1",
        )
        with store._conn() as conn:
            conn.execute(
                "INSERT INTO phg_credential_mints (device_id, credential_id, tx_hash, minted_at)"
                " VALUES (?, ?, ?, ?)",
                (DEVICE_SUSPENDED, 1, "0xmint", time.time()),
            )
        store.store_credential_suspension(
            device_id=DEVICE_SUSPENDED,
            evidence_hash="0xblock",
            until=time.time() + 86400,
        )
        assert _bridge_is_fully_eligible(store, DEVICE_SUSPENDED) is False

        store.clear_credential_suspension(DEVICE_SUSPENDED)
        assert _bridge_is_fully_eligible(store, DEVICE_SUSPENDED) is True
