"""Phase O1 C4 — Drift Auto-Sweep Scheduler tests.

Validates the long-lived asyncio loop that drives detect_*_drift on the
INV-OPERATOR-AGENT-008 dual-cadence pattern (bundle 60s, scope 600s default).
Covers: enabled gate, monotonic interval gating, dual-cadence independence,
fail-open on sweep error, graceful cancellation.
"""

import asyncio
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _make_cfg(enabled=True, bundle_s=1, scope_s=2):
    """Minimal cfg object — short intervals to keep tests fast."""
    cfg = MagicMock()
    cfg.cedar_drift_sweep_enabled = enabled
    cfg.cedar_drift_sweep_interval_bundle_s = bundle_s
    cfg.cedar_drift_sweep_interval_scope_s = scope_s
    return cfg


def _make_drift_result(sweep_id="sweep_x", findings=None, error=None,
                      agents_checked=2):
    """Build a synthetic DriftSweepResult."""
    from vapi_bridge.cedar_shadow_runtime import DriftSweepResult
    return DriftSweepResult(
        sweep_id=sweep_id,
        agents_checked=agents_checked,
        findings=findings or [],
        error=error,
    )


# ---------------------------------------------------------------------------
# T-O1-C4-DS-1: cedar_drift_sweep_enabled=False short-circuits immediately
# ---------------------------------------------------------------------------

class TestDisabledShortCircuit(unittest.IsolatedAsyncioTestCase):

    async def test_t_o1_c4_ds_1_disabled_returns_immediately(self):
        from vapi_bridge.cedar_drift_sweeper import run_drift_sweep_loop

        cfg = _make_cfg(enabled=False)
        store = MagicMock()
        chain = MagicMock()

        # Should return within ms — never enter the sweep loop
        await asyncio.wait_for(
            run_drift_sweep_loop(cfg=cfg, store=store, chain=chain),
            timeout=1.0,
        )
        # No sweep should have been attempted on store
        store.assert_not_called()


# ---------------------------------------------------------------------------
# T-O1-C4-DS-2: bundle sweep fires at configured interval
# ---------------------------------------------------------------------------

class TestBundleSweepCadence(unittest.IsolatedAsyncioTestCase):

    async def test_t_o1_c4_ds_2_bundle_sweep_fires(self):
        from vapi_bridge import cedar_drift_sweeper

        cfg = _make_cfg(enabled=True, bundle_s=1, scope_s=999)  # scope effectively disabled
        store = MagicMock()
        chain = MagicMock()

        bundle_calls = []

        def fake_bundle(*, cfg, store, sweep_id=None):
            bundle_calls.append(1)
            return _make_drift_result(sweep_id="bundle_sweep")

        async def fake_scope(*, cfg, store, chain, sweep_id=None):
            return _make_drift_result(sweep_id="scope_sweep")

        with patch.object(cedar_drift_sweeper, "detect_bundle_hash_drift", fake_bundle), \
             patch.object(cedar_drift_sweeper, "detect_scope_hash_governance_drift", fake_scope):
            task = asyncio.create_task(
                cedar_drift_sweeper.run_drift_sweep_loop(
                    cfg=cfg, store=store, chain=chain,
                )
            )
            # Bundle interval=1s + heartbeat=1s → 1st fire t=0; 2nd fire t=1s+heartbeat
            await asyncio.sleep(2.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.assertGreaterEqual(
            len(bundle_calls), 2,
            f"bundle sweep should have fired ≥2 times in ~2.5s window (got {len(bundle_calls)})",
        )


# ---------------------------------------------------------------------------
# T-O1-C4-DS-3: scope sweep at independent cadence (different from bundle)
# ---------------------------------------------------------------------------

class TestScopeSweepCadence(unittest.IsolatedAsyncioTestCase):

    async def test_t_o1_c4_ds_3_scope_sweep_independent_cadence(self):
        from vapi_bridge import cedar_drift_sweeper

        # bundle every 1s, scope every 3s — verify they fire at different rates
        cfg = _make_cfg(enabled=True, bundle_s=1, scope_s=3)
        store = MagicMock()
        chain = MagicMock()

        bundle_calls = []
        scope_calls = []

        def fake_bundle(*, cfg, store, sweep_id=None):
            bundle_calls.append(1)
            return _make_drift_result()

        async def fake_scope(*, cfg, store, chain, sweep_id=None):
            scope_calls.append(1)
            return _make_drift_result()

        with patch.object(cedar_drift_sweeper, "detect_bundle_hash_drift", fake_bundle), \
             patch.object(cedar_drift_sweeper, "detect_scope_hash_governance_drift", fake_scope):
            task = asyncio.create_task(
                cedar_drift_sweeper.run_drift_sweep_loop(
                    cfg=cfg, store=store, chain=chain,
                )
            )
            await asyncio.sleep(4.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Bundle should fire more frequently than scope (1s vs 3s cadence)
        self.assertGreater(
            len(bundle_calls), len(scope_calls),
            f"bundle ({len(bundle_calls)}) should fire more than scope ({len(scope_calls)})",
        )
        self.assertGreaterEqual(len(scope_calls), 1, "scope must fire at least once in 4.5s")


# ---------------------------------------------------------------------------
# T-O1-C4-DS-4: bundle sweep error is caught; loop continues
# ---------------------------------------------------------------------------

class TestBundleSweepErrorRecovery(unittest.IsolatedAsyncioTestCase):

    async def test_t_o1_c4_ds_4_bundle_error_does_not_crash_loop(self):
        from vapi_bridge import cedar_drift_sweeper

        cfg = _make_cfg(enabled=True, bundle_s=1, scope_s=999)
        store = MagicMock()
        chain = MagicMock()

        bundle_calls = []

        def fake_bundle_raises(*, cfg, store, sweep_id=None):
            bundle_calls.append(1)
            raise RuntimeError("simulated bundle sweep failure")

        async def fake_scope(*, cfg, store, chain, sweep_id=None):
            return _make_drift_result()

        with patch.object(cedar_drift_sweeper, "detect_bundle_hash_drift", fake_bundle_raises), \
             patch.object(cedar_drift_sweeper, "detect_scope_hash_governance_drift", fake_scope):
            task = asyncio.create_task(
                cedar_drift_sweeper.run_drift_sweep_loop(
                    cfg=cfg, store=store, chain=chain,
                )
            )
            await asyncio.sleep(2.5)
            # If the loop crashed on first error, bundle_calls would be 1
            # Loop must continue → bundle_calls >= 2
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.assertGreaterEqual(
            len(bundle_calls), 2,
            f"loop must survive bundle sweep error and re-fire (got {len(bundle_calls)} attempts)",
        )


# ---------------------------------------------------------------------------
# T-O1-C4-DS-5: scope sweep error is caught; loop continues
# ---------------------------------------------------------------------------

class TestScopeSweepErrorRecovery(unittest.IsolatedAsyncioTestCase):

    async def test_t_o1_c4_ds_5_scope_error_does_not_crash_loop(self):
        from vapi_bridge import cedar_drift_sweeper

        cfg = _make_cfg(enabled=True, bundle_s=999, scope_s=1)
        store = MagicMock()
        chain = MagicMock()

        scope_calls = []

        def fake_bundle(*, cfg, store, sweep_id=None):
            return _make_drift_result()

        async def fake_scope_raises(*, cfg, store, chain, sweep_id=None):
            scope_calls.append(1)
            raise ConnectionError("simulated chain RPC failure")

        with patch.object(cedar_drift_sweeper, "detect_bundle_hash_drift", fake_bundle), \
             patch.object(cedar_drift_sweeper, "detect_scope_hash_governance_drift", fake_scope_raises):
            task = asyncio.create_task(
                cedar_drift_sweeper.run_drift_sweep_loop(
                    cfg=cfg, store=store, chain=chain,
                )
            )
            await asyncio.sleep(2.5)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.assertGreaterEqual(
            len(scope_calls), 2,
            f"loop must survive scope sweep error and re-fire (got {len(scope_calls)} attempts)",
        )


# ---------------------------------------------------------------------------
# T-O1-C4-DS-6: cancellation propagates cleanly (graceful shutdown)
# ---------------------------------------------------------------------------

class TestGracefulCancellation(unittest.IsolatedAsyncioTestCase):

    async def test_t_o1_c4_ds_6_cancellation_exits_cleanly(self):
        from vapi_bridge import cedar_drift_sweeper

        cfg = _make_cfg(enabled=True, bundle_s=1, scope_s=1)
        store = MagicMock()
        chain = MagicMock()

        with patch.object(
            cedar_drift_sweeper, "detect_bundle_hash_drift",
            lambda *, cfg, store, sweep_id=None: _make_drift_result(),
        ), patch.object(
            cedar_drift_sweeper, "detect_scope_hash_governance_drift",
            lambda *, cfg, store, chain, sweep_id=None: _async_drift_result(),
        ):
            task = asyncio.create_task(
                cedar_drift_sweeper.run_drift_sweep_loop(
                    cfg=cfg, store=store, chain=chain,
                )
            )
            await asyncio.sleep(0.5)  # let it run briefly
            task.cancel()

            # Cancellation must propagate as CancelledError (not swallowed)
            with self.assertRaises(asyncio.CancelledError):
                await task


async def _async_drift_result():
    """Async wrapper for the lambda patch (needed because real fn is async)."""
    from vapi_bridge.cedar_shadow_runtime import DriftSweepResult
    return DriftSweepResult(sweep_id="x", agents_checked=0, findings=[], error=None)


if __name__ == "__main__":
    unittest.main()
