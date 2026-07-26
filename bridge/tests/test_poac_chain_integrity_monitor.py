"""
Phase 176 — PoACChainIntegrityMonitor tests.

Covers the counter-contiguity audit, the fail-open behaviours (DB errors,
disabled config, store write failure), the pir_chain_broken bus event, and the
W1 (WIF-026) property that only aggregate counts leave the monitor.
"""
import asyncio
import os
import sqlite3
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge import poac_chain_integrity_monitor as monitor_mod
from vapi_bridge.poac_chain_integrity_monitor import PoACChainIntegrityMonitor


class _FakeStore:
    """Minimal store double backed by an in-memory SQLite records table."""

    def __init__(self, rows=(), fail_connect=False):
        self.fail_connect = fail_connect
        self.audit_logs = []
        self._conn = sqlite3.connect(":memory:")
        self._conn.execute(
            "CREATE TABLE records (device_id TEXT, counter INTEGER, "
            "record_hash TEXT, created_at REAL)"
        )
        self._conn.executemany(
            "INSERT INTO records VALUES (?, ?, ?, ?)",
            [(d, c, f"hash{c}", ts) for d, c, ts in rows],
        )
        self._conn.commit()

    def _connect(self):
        if self.fail_connect:
            raise sqlite3.OperationalError("database is locked")

        class _Ctx:
            def __init__(self, conn):
                self._conn = conn

            def __enter__(self):
                return self._conn

            def __exit__(self, *exc):
                return False

        return _Ctx(self._conn)

    def insert_poac_chain_audit_log(self, **kwargs):
        self.audit_logs.append(kwargs)


def _cfg(enabled=True):
    cfg = MagicMock()
    cfg.chain_integrity_enabled = enabled
    return cfg


class TestChainAudit(unittest.TestCase):

    def test_contiguous_chain_passes(self):
        store = _FakeStore([("d1", i, float(i)) for i in range(1, 6)])
        result = PoACChainIntegrityMonitor(_cfg(), store)._audit_device("d1")
        self.assertEqual(result["total_records"], 5)
        self.assertEqual(result["valid_links"], 4)
        self.assertEqual(result["broken_links"], 0)
        self.assertEqual(result["integrity_score"], 1.0)
        self.assertTrue(result["audit_passed"])

    def test_gap_in_counters_breaks_chain(self):
        # counters 1,2,4,5 → the 2→4 pair is a break
        store = _FakeStore([("d1", c, float(c)) for c in (1, 2, 4, 5)])
        result = PoACChainIntegrityMonitor(_cfg(), store)._audit_device("d1")
        self.assertEqual(result["total_records"], 4)
        self.assertEqual(result["valid_links"], 2)
        self.assertEqual(result["broken_links"], 1)
        self.assertEqual(result["integrity_score"], round(2 / 3, 6))
        self.assertFalse(result["audit_passed"])

    def test_vacuous_cases_report_full_integrity(self):
        monitor = PoACChainIntegrityMonitor(_cfg(), _FakeStore())
        empty = monitor._audit_device("nobody")
        self.assertEqual(empty["total_records"], 0)
        self.assertEqual(empty["valid_links"], 0)
        self.assertTrue(empty["audit_passed"])

        single = PoACChainIntegrityMonitor(
            _cfg(), _FakeStore([("d1", 1, 1.0)])
        )._audit_device("d1")
        self.assertEqual(single["total_records"], 1)
        self.assertEqual(single["integrity_score"], 1.0)
        self.assertTrue(single["audit_passed"])

    def test_device_filter_ignores_other_devices(self):
        rows = [("d1", 1, 1.0), ("d2", 50, 2.0), ("d1", 2, 3.0)]
        monitor = PoACChainIntegrityMonitor(_cfg(), _FakeStore(rows))
        self.assertEqual(monitor._audit_device("d1")["total_records"], 2)
        # device_id=None audits every device's counters as one sequence
        self.assertEqual(monitor._audit_device(None)["total_records"], 3)

    def test_db_error_fails_open(self):
        monitor = PoACChainIntegrityMonitor(_cfg(), _FakeStore(fail_connect=True))
        result = monitor._audit_device("d1")
        self.assertTrue(result["audit_passed"])
        self.assertEqual(result["integrity_score"], 1.0)
        self.assertEqual(result["total_records"], 0)


class TestPrimaryDeviceId(unittest.TestCase):

    def test_returns_most_recent_device(self):
        rows = [("old", 1, 1.0), ("newest", 2, 99.0), ("mid", 3, 50.0)]
        monitor = PoACChainIntegrityMonitor(_cfg(), _FakeStore(rows))
        self.assertEqual(monitor._get_primary_device_id(), "newest")

    def test_returns_none_when_empty_or_erroring(self):
        self.assertIsNone(
            PoACChainIntegrityMonitor(_cfg(), _FakeStore())._get_primary_device_id()
        )
        self.assertIsNone(
            PoACChainIntegrityMonitor(
                _cfg(), _FakeStore(fail_connect=True)
            )._get_primary_device_id()
        )


class TestRunAudit(unittest.TestCase):

    def test_disabled_short_circuits(self):
        store = _FakeStore([("d1", 1, 1.0)])
        result = PoACChainIntegrityMonitor(_cfg(enabled=False), store)._run_audit()
        self.assertEqual(result, {"chain_integrity_enabled": False, "audit_passed": True})
        self.assertEqual(store.audit_logs, [])

    def test_intact_chain_logs_audit_and_publishes_nothing(self):
        store = _FakeStore([("d1", i, float(i)) for i in range(1, 4)])
        bus = MagicMock()
        result = PoACChainIntegrityMonitor(_cfg(), store, bus)._run_audit()
        self.assertTrue(result["audit_passed"])
        self.assertEqual(result["device_id"], "d1")
        self.assertEqual(len(store.audit_logs), 1)
        self.assertEqual(store.audit_logs[0]["broken_links"], 0)
        bus.publish.assert_not_called()

    def test_broken_chain_publishes_pir_chain_broken(self):
        store = _FakeStore([("d1", c, float(c)) for c in (1, 5)])
        bus = MagicMock()
        result = PoACChainIntegrityMonitor(_cfg(), store, bus)._run_audit()
        self.assertFalse(result["audit_passed"])
        bus.publish.assert_called_once()
        topic, payload = bus.publish.call_args[0]
        self.assertEqual(topic, "pir_chain_broken")
        self.assertEqual(payload["source"], "PoACChainIntegrityMonitor")
        self.assertEqual(payload["broken_links"], 1)
        # W1 (WIF-026): only aggregates are exposed — never per-record identifiers.
        self.assertNotIn("record_hash", payload)
        self.assertNotIn("counters", payload)

    def test_bus_publish_error_is_swallowed(self):
        store = _FakeStore([("d1", c, float(c)) for c in (1, 5)])
        bus = MagicMock()
        bus.publish.side_effect = RuntimeError("bus down")
        result = PoACChainIntegrityMonitor(_cfg(), store, bus)._run_audit()
        self.assertFalse(result["audit_passed"])

    def test_store_write_error_falls_back_to_full_integrity(self):
        store = _FakeStore([("d1", c, float(c)) for c in (1, 5)])
        store.insert_poac_chain_audit_log = MagicMock(side_effect=RuntimeError("no table"))
        result = PoACChainIntegrityMonitor(_cfg(), store)._run_audit()
        self.assertTrue(result["chain_integrity_enabled"])
        self.assertTrue(result["audit_passed"])
        self.assertEqual(result["integrity_score"], 1.0)


class TestPollLoop(unittest.TestCase):

    def test_audit_exception_does_not_break_the_loop(self):
        monitor = PoACChainIntegrityMonitor(_cfg(), _FakeStore())
        monitor._run_audit = MagicMock(side_effect=[RuntimeError("boom"), {}])

        sleeps = []

        async def _fake_sleep(delay):
            sleeps.append(delay)
            if len(sleeps) == 2:
                raise asyncio.CancelledError

        with patch.object(monitor_mod.asyncio, "sleep", _fake_sleep), \
                self.assertRaises(asyncio.CancelledError):
            asyncio.run(monitor.run_poll_loop())

        self.assertEqual(monitor._run_audit.call_count, 2)
        self.assertEqual(sleeps, [PoACChainIntegrityMonitor._POLL_INTERVAL_S] * 2)


if __name__ == "__main__":
    unittest.main()
