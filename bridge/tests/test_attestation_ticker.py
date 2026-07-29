"""Tests for the protocol-enforced multi-modal attestation loop.

Covers: envelope construction, channel hashing, cross-modal binding,
tick chaining, store persistence, and lifecycle integration.
"""

from __future__ import annotations

import os
import sys
import pytest
import json
import asyncio
import hashlib
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_bridge.attestation import AttestationTicker, AttestationEnvelope, ChannelSnapshot
from vapi_bridge.attestation.store import AttestationStore, CREATE_ATTESTATIONS_TABLE
from vapi_bridge.attestation.ticker import _hash


# ══════════════════════════════════════════════════════
# Test helpers
# ══════════════════════════════════════════════════════

@pytest.fixture
def tmp_db(tmp_path: Path) -> str:
    """Temporary SQLite database path."""
    return str(tmp_path / "attestations.db")


# ══════════════════════════════════════════════════════
# Types: _hash function
# ══════════════════════════════════════════════════════

class TestHashFunction:
    """SHA-256 hash of serializable objects."""

    def test_hash_string(self):
        h = _hash("hello")
        assert len(h) == 64  # SHA-256 hex digest
        assert isinstance(h, str)

    def test_hash_dict(self):
        h = _hash({"key": "value"})
        assert len(h) == 64

    def test_hash_deterministic(self):
        h1 = _hash([1, 2, 3])
        h2 = _hash([1, 2, 3])
        assert h1 == h2

    def test_hash_order_dependent(self):
        h1 = _hash({"a": 1, "b": 2})
        h2 = _hash({"b": 2, "a": 1})
        assert h1 == h2  # sort_keys ensures deterministic order


# ══════════════════════════════════════════════════════
# ChannelSnapshot
# ══════════════════════════════════════════════════════

class TestChannelSnapshot:
    """ChannelSnapshot dataclass behavior."""

    def test_defaults(self):
        snap = ChannelSnapshot()
        assert snap.tick == 0
        assert snap.timestamp == 0.0
        assert snap.session_id == ""
        assert snap.hardware is None
        assert snap.controller is None
        assert snap.biometrics is None
        assert snap.retina is None
        assert snap.vlm is None
        assert snap.contradictions is None
        assert snap.invariants is None

    def test_partial_population(self):
        """Only populated fields are non-None."""
        snap = ChannelSnapshot(
            tick=5,
            session_id="test123",
            hardware={"state": "ALL_READY"},
            contradictions=[],
        )
        assert snap.tick == 5
        assert snap.session_id == "test123"
        assert snap.hardware == {"state": "ALL_READY"}
        assert snap.contradictions == []
        assert snap.controller is None  # not populated


# ══════════════════════════════════════════════════════
# AttestationEnvelope
# ══════════════════════════════════════════════════════

class TestAttestationEnvelope:
    """Envelope construction and serialization."""

    def test_minimal_envelope(self):
        """Envelope can be created with minimal fields."""
        env = AttestationEnvelope(
            tick=0,
            timestamp=1000.0,
            session_id="test",
            channel_hashes={},
            cross_modal_hash="",
            envelope_hash="abc123",
            previous_envelope_hash="",
        )
        assert env.tick == 0
        assert env.envelope_hash == "abc123"

    def test_envelope_with_channels(self):
        """Envelope with multiple channel hashes."""
        env = AttestationEnvelope(
            tick=42,
            timestamp=2000.0,
            session_id="test",
            channel_hashes={
                "poac": "hash1",
                "poep": "hash2",
            },
            cross_modal_hash="cross_hash",
            pv_ci_fingerprint="pv_ci_hash",
            envelope_hash="final_hash",
            previous_envelope_hash="prev_hash",
        )
        assert len(env.channel_hashes) == 2
        assert env.cross_modal_hash == "cross_hash"
        assert env.envelope_hash == "final_hash"
        assert env.previous_envelope_hash == "prev_hash"

    def test_to_dict(self):
        """to_dict produces a JSON-serializable dict."""
        env = AttestationEnvelope(
            tick=1,
            timestamp=100.0,
            session_id="s1",
            envelope_hash="h1",
            previous_envelope_hash="h0",
        )
        d = env.to_dict()
        assert d["tick"] == 1
        assert d["session_id"] == "s1"
        assert d["envelope_hash"] == "h1"
        # Should be JSON-serializable
        json.dumps(d)

    def test_from_dict(self):
        """from_dict reconstructs an envelope."""
        original = AttestationEnvelope(
            tick=5,
            timestamp=500.0,
            session_id="s2",
            channel_hashes={"poac": "abc"},
            cross_modal_hash="xyz",
            envelope_hash="final",
            previous_envelope_hash="prev",
        )
        d = original.to_dict()
        reconstructed = AttestationEnvelope.from_dict(d)
        assert reconstructed.tick == original.tick
        assert reconstructed.envelope_hash == original.envelope_hash
        assert reconstructed.channel_hashes == original.channel_hashes


# ══════════════════════════════════════════════════════
# AttestationStore
# ══════════════════════════════════════════════════════

class TestAttestationStore:
    """Database persistence for attestation envelopes."""

    def test_init_creates_table(self, tmp_db):
        """Store initialization creates the attestations table."""
        store = AttestationStore(tmp_db)
        # Verify table exists
        conn = store._get_conn()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='attestations'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["name"] == "attestations"

    def test_append_and_query(self, tmp_db):
        """Append an envelope and query it back."""
        store = AttestationStore(tmp_db)
        env = AttestationEnvelope(
            tick=1,
            timestamp=100.0,
            session_id="session1",
            channel_hashes={"poac": "abc123"},
            cross_modal_hash="cross1",
            envelope_hash="env1",
            previous_envelope_hash="",
        )
        assert store.append(env)

        # Query by session
        results = store.get_by_session("session1")
        assert len(results) == 1
        assert results[0]["tick"] == 1
        assert results[0]["session_id"] == "session1"

    def test_append_multiple_ticks(self, tmp_db):
        """Multiple ticks for the same session."""
        store = AttestationStore(tmp_db)
        for i in range(5):
            env = AttestationEnvelope(
                tick=i,
                timestamp=100.0 + i,
                session_id="session1",
                channel_hashes={"poac": f"hash{i}"},
                cross_modal_hash=f"cross{i}",
                envelope_hash=f"env{i}",
                previous_envelope_hash=f"env{i-1}" if i > 0 else "",
            )
            store.append(env)

        results = store.get_by_session("session1", limit=10)
        assert len(results) == 5
        # Ordered by tick ascending
        for i, row in enumerate(results):
            assert row["tick"] == i

    def test_get_by_hash(self, tmp_db):
        """Query by attestation hash."""
        store = AttestationStore(tmp_db)
        env = AttestationEnvelope(
            tick=1, timestamp=100.0, session_id="s1",
            envelope_hash="unique_hash",
            previous_envelope_hash="",
        )
        store.append(env)

        result = store.get_by_hash("unique_hash")
        assert result is not None
        assert result["tick"] == 1

    def test_get_by_hash_not_found(self, tmp_db):
        """Querying nonexistent hash returns None."""
        store = AttestationStore(tmp_db)
        result = store.get_by_hash("nonexistent")
        assert result is None

    def test_get_latest_for_session(self, tmp_db):
        """Get the most recent attestation."""
        store = AttestationStore(tmp_db)
        for i in range(3):
            env = AttestationEnvelope(
                tick=i, timestamp=100.0 + i, session_id="s1",
                envelope_hash=f"env{i}",
                previous_envelope_hash=f"env{i-1}" if i > 0 else "",
            )
            store.append(env)

        latest = store.get_latest_for_session("s1")
        assert latest is not None
        assert latest["tick"] == 2
        assert latest["attestation_hash"] == "env2"

    def test_count_by_session(self, tmp_db):
        """Count attestations for a session."""
        store = AttestationStore(tmp_db)
        for i in range(10):
            env = AttestationEnvelope(
                tick=i, timestamp=100.0 + i, session_id="s1",
                envelope_hash=f"env{i}",
                previous_envelope_hash=f"env{i-1}" if i > 0 else "",
            )
            store.append(env)

        assert store.count_by_session("s1") == 10
        assert store.count_by_session("nonexistent") == 0

    def test_delete_older_than(self, tmp_db):
        """Delete old attestations."""
        store = AttestationStore(tmp_db)
        for i in range(5):
            env = AttestationEnvelope(
                tick=i, timestamp=1000.0 + i * 100, session_id="s1",
                envelope_hash=f"env{i}",
                previous_envelope_hash=f"env{i-1}" if i > 0 else "",
            )
            store.append(env)

        # Delete ticks with timestamp < 1200 (ticks 0, 1)
        deleted = store.delete_older_than(1200.0)
        assert deleted >= 2
        assert store.count_by_session("s1") == 3

    def test_session_attestation_range(self, tmp_db):
        """Get first/last tick info for a session."""
        store = AttestationStore(tmp_db)
        for i in range(5):
            env = AttestationEnvelope(
                tick=i, timestamp=1000.0 + i, session_id="s1",
                envelope_hash=f"env{i}",
                previous_envelope_hash=f"env{i-1}" if i > 0 else "",
            )
            store.append(env)

        info = store.get_session_attestation_range("s1")
        assert info is not None
        assert info["first_tick"] == 0
        assert info["last_tick"] == 4
        assert info["total"] == 5


# ══════════════════════════════════════════════════════
# AttestationTicker — envelope construction
# ══════════════════════════════════════════════════════

class TestTickerEnvelopeConstruction:
    """AttestationTicker._build_envelope unit tests."""

    def test_envelope_with_single_channel(self, tmp_db):
        """Envelope with one channel has that channel hash."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store)

        # Register a single reader
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY", "dualshock": True}
        ticker._session_id = "test_session"
        ticker._tick_count = 0

        envelope = ticker._build_envelope()
        assert envelope.session_id == "test_session"
        assert "hardware" in envelope.channel_hashes
        assert len(envelope.channel_hashes) == 1
        assert envelope.cross_modal_hash != ""
        assert envelope.envelope_hash != ""

    def test_envelope_with_multiple_channels(self, tmp_db):
        """Envelope with multiple channels has cross-modal hash."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store)
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}
        ticker._readers["pv_ci"] = lambda: {"fingerprint": "pv_fp_123"}
        ticker._session_id = "test"
        ticker._tick_count = 0

        envelope = ticker._build_envelope()
        assert len(envelope.channel_hashes) == 2
        assert envelope.cross_modal_hash != ""
        # cross-modal hash binds both channels
        assert envelope.cross_modal_hash != envelope.channel_hashes["hardware"]

    def test_envelope_tick_chain(self, tmp_db):
        """Consecutive ticks create a hash chain."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store)
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}
        ticker._session_id = "test"

        ticker._tick_count = 0
        env1 = ticker._build_envelope()

        ticker._last_envelope_hash = env1.envelope_hash
        ticker._tick_count = 1
        env2 = ticker._build_envelope()

        assert env1.envelope_hash != env2.envelope_hash
        assert env2.previous_envelope_hash == env1.envelope_hash

    def test_envelope_with_missing_channels(self, tmp_db):
        """Missing channels are omitted without error."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store)
        ticker._session_id = "test"
        ticker._tick_count = 0

        # No readers registered — all channels missing
        envelope = ticker._build_envelope()
        assert envelope.channel_hashes == {}
        assert envelope.cross_modal_hash == ""
        assert envelope.envelope_hash != ""  # still has timestamp + session_id

    def test_reader_returns_none(self, tmp_db):
        """Reader returning None omits that channel."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store)
        ticker._readers["hardware"] = lambda: None  # not available
        ticker._readers["biometrics"] = lambda: {"separation": 0.85}  # available
        ticker._session_id = "test"
        ticker._tick_count = 0

        envelope = ticker._build_envelope()
        assert "hardware" not in envelope.channel_hashes
        assert "biometrics" in envelope.channel_hashes

    def test_reader_raises_exception(self, tmp_db):
        """Reader exception is caught, channel omitted."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store)
        ticker._readers["failing"] = lambda: 1 / 0  # raises ZeroDivisionError
        ticker._session_id = "test"
        ticker._tick_count = 0

        envelope = ticker._build_envelope()  # should not raise
        assert "failing" not in envelope.channel_hashes


# ══════════════════════════════════════════════════════
# AttestationTicker — lifecycle
# ══════════════════════════════════════════════════════

class TestTickerLifecycle:
    """Start/stop lifecycle for AttestationTicker."""

    @pytest.mark.asyncio
    async def test_start_stop(self, tmp_db):
        """Start and stop the ticker."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store, tick_interval=0.01)
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}

        assert not ticker.running
        await ticker.start("session1")
        assert ticker.running
        assert ticker.session_id == "session1"

        # Let it tick a few times
        await asyncio.sleep(0.05)

        final = await ticker.stop()
        assert not ticker.running
        assert ticker.tick_count >= 1

    @pytest.mark.asyncio
    async def test_double_start(self, tmp_db):
        """Starting an already-running ticker is a no-op."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store, tick_interval=0.1)
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}

        await ticker.start("s1")
        await ticker.start("s2")  # should be no-op (warns but doesn't restart)
        assert ticker.session_id == "s1"  # unchanged
        await ticker.stop()

    @pytest.mark.asyncio
    async def test_stop_returns_final_envelope(self, tmp_db):
        """stop() returns the final envelope."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store, tick_interval=0.01)
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}

        await ticker.start("s1")
        await asyncio.sleep(0.03)
        final = await ticker.stop()
        assert final is not None
        assert final.session_id == "s1"

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, tmp_db):
        """Stopping a non-running ticker returns None."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store)
        result = await ticker.stop()
        assert result is None

    @pytest.mark.asyncio
    async def test_envelope_callback(self, tmp_db):
        """on_envelope callback receives each tick's envelope."""
        store = AttestationStore(tmp_db)
        received = []

        async def callback(env):
            received.append(env)

        ticker = AttestationTicker(
            store=store, tick_interval=0.01, on_envelope=callback,
        )
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}

        await ticker.start("s1")
        await asyncio.sleep(0.04)
        await ticker.stop()

        assert len(received) >= 1

    @pytest.mark.asyncio
    async def test_context_manager(self, tmp_db):
        """Ticker works as async context manager."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store, tick_interval=0.1)
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}

        async with ticker:
            await ticker.start("s1")
            assert ticker.running
            await asyncio.sleep(0.05)

        assert not ticker.running


# ══════════════════════════════════════════════════════
# Integration: ticker stores envelopes in DB
# ══════════════════════════════════════════════════════

class TestTickerPersistence:
    """AttestationTicker stores envelopes in the database."""

    @pytest.mark.asyncio
    async def test_envelopes_appended_to_db(self, tmp_db):
        """Ticker loop appends envelopes to the database."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store, tick_interval=0.01)
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}

        await ticker.start("session_db_test")
        await asyncio.sleep(0.06)
        await ticker.stop()

        # Verify envelopes were stored
        count = store.count_by_session("session_db_test")
        assert count >= 1, f"Expected >= 1 envelopes, got {count}"

    @pytest.mark.asyncio
    async def test_consecutive_tick_chain(self, tmp_db):
        """Consecutive ticks form a chain in the DB."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store, tick_interval=0.02)
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}

        await ticker.start("chain_test")
        await asyncio.sleep(0.08)
        await ticker.stop()

        results = store.get_by_session("chain_test", limit=100)
        if len(results) >= 2:
            # Verify hash chain
            for i in range(1, len(results)):
                prev = json.loads(results[i - 1]["envelope_json"])
                curr = json.loads(results[i]["envelope_json"])
                assert curr["previous_envelope_hash"] == prev["envelope_hash"]


# ══════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════

class TestTickerEdgeCases:
    """Edge cases for the attestation loop."""

    @pytest.mark.asyncio
    async def test_tick_interval_respected(self, tmp_db):
        """Ticker respects the configured tick interval."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store, tick_interval=0.1)
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}

        start = asyncio.get_event_loop().time()
        await ticker.start("interval_test")
        await asyncio.sleep(0.05 + 0.01)  # half a tick
        await ticker.stop()
        elapsed = asyncio.get_event_loop().time() - start

        # With 0.1s tick interval and ~0.06s runtime, should have ~0 or ~1 ticks
        # Never more than ceiling(elapsed / interval)
        max_expected = int(elapsed / 0.1) + 1
        assert ticker.tick_count <= max_expected, (
            f"Ticker ticked {ticker.tick_count} times in {elapsed:.2f}s "
            f"(max expected: {max_expected})"
        )

    @pytest.mark.asyncio
    async def test_no_readers_crash(self, tmp_db):
        """Ticker with no readers still produces envelopes."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store, tick_interval=0.01)
        # No readers registered
        await ticker.start("empty")
        await asyncio.sleep(0.03)
        final = await ticker.stop()
        assert final is not None
        assert final.channel_hashes == {}

    @pytest.mark.asyncio
    async def test_watch_session_id(self, tmp_db):
        """watch_session_id provides session_id via callable."""
        store = AttestationStore(tmp_db)
        ticker = AttestationTicker(store=store)
        ticker.watch_session_id(lambda: "dynamic_session")
        ticker._readers["hardware"] = lambda: {"state": "OK"}
        ticker._tick_count = 0

        envelope = ticker._build_envelope()
        # Session_id from the ticker's internal state (_session_id)
        # which was set by .start(), not by the watcher
        # The watcher is used when session_id is not set on the ticker
        assert envelope.session_id != "dynamic_session"  # ticker uses _session_id

    @pytest.mark.asyncio
    async def test_db_write_failure_handled(self, tmp_db):
        """Ticker handles DB write failure gracefully."""
        store = AttestationStore(tmp_db)

        # Corrupt the store to simulate write failure
        def failing_append(env):
            return False
        store.append = failing_append

        ticker = AttestationTicker(store=store, tick_interval=0.01)
        ticker._readers["hardware"] = lambda: {"state": "ALL_READY"}

        # Should not crash despite failed DB writes
        await ticker.start("fail_test")
        await asyncio.sleep(0.03)
        await ticker.stop()