"""Phase 235.x-STABILITY-9 stage 13 (2026-05-18) — ProactiveMonitor
surveillance asyncio.to_thread wrap tests.

Validates the LOAD-BEARING fix that closes the 12-stage + 9-BISECT-cycle
STABILITY-9 arc: ProactiveMonitor's 3 surveillance checks now wrap their
synchronous hotpaths in asyncio.to_thread to prevent the event loop
from blocking on O(N²) NCD pairwise distance compute.

The smoking gun: `network_detector.detect_clusters()` calls
`build_distance_matrix(device_ids)` which is a doubly-nested loop
computing `prover.compute_distance(...)` for every device pair —
~4,950 compression-based compute calls at N=100 devices. Then DBSCAN
on top. Completely synchronous on event loop before Stage 13 fix.

BISECT empirical evidence (B5_PMONITOR cycle):
- Boot 11:07:38 + ProactiveMonitor sole spawn
- First STARVATION at boot+1:54 (=11:09:32) = 54s into first 60s poll cycle
- Peak excess 49.67s — matches Stage 12 baseline 48.96s within ±3%
- 11 STARVATION events over 13 min uptime (vs 65 in B5_ALL with full agent set)
- Other 40 agents (B1+B2+B3+B4+B5A+B5B+B5C+B5D) tested CLEAN in isolation

Stage 13 expected post-fix outcome: STARVATION peak drops from 49.67s → <1s
(below loop_health heartbeat threshold). STABILITY-9 closes.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest


_BRIDGE_DIR = Path(__file__).resolve().parents[1] / "vapi_bridge"


# ─── Source-pattern presence tests ─────────────────────────────────────────


def test_t_235_stab9_13_1_detect_clusters_wrapped_in_to_thread() -> None:
    """_check_anomaly_clusters wraps detect_clusters via asyncio.to_thread."""
    src = (_BRIDGE_DIR / "proactive_monitor.py").read_text(encoding="utf-8")
    assert (
        "await asyncio.to_thread(\n                self._network_detector.detect_clusters\n            )"
        in src
    ), "detect_clusters must be wrapped in asyncio.to_thread (multi-line form)"
    # Stage 13 marker comment present
    assert "stage 13" in src
    assert "LOAD-BEARING 50s event-loop block" in src
    assert "build_distance_matrix" in src


def test_t_235_stab9_13_2_get_high_risk_devices_wrapped() -> None:
    """_check_high_risk_trajectories wraps get_high_risk_devices via to_thread."""
    src = (_BRIDGE_DIR / "proactive_monitor.py").read_text(encoding="utf-8")
    assert (
        "await asyncio.to_thread(\n                self._behavioral_arch.get_high_risk_devices, 0.7\n            )"
        in src
    ), "get_high_risk_devices must be wrapped in asyncio.to_thread"


def test_t_235_stab9_13_3_analyze_device_wrapped_in_loop() -> None:
    """_check_high_risk_trajectories wraps per-device analyze_device via to_thread."""
    src = (_BRIDGE_DIR / "proactive_monitor.py").read_text(encoding="utf-8")
    assert (
        "await asyncio.to_thread(\n                    self._behavioral_arch.analyze_device, device_id\n                )"
        in src
    ), "analyze_device(device_id) inside risky loop must be wrapped in asyncio.to_thread"


def test_t_235_stab9_13_4_get_leaderboard_wrapped() -> None:
    """_check_eligibility_horizons wraps get_leaderboard via to_thread."""
    src = (_BRIDGE_DIR / "proactive_monitor.py").read_text(encoding="utf-8")
    assert (
        "await asyncio.to_thread(self._store.get_leaderboard, 100)"
        in src
    ), "get_leaderboard(100) must be wrapped in asyncio.to_thread"


def test_t_235_stab9_13_5_no_unwrapped_sync_call_remains() -> None:
    """No bare sync call (without `await asyncio.to_thread`) survives in
    the 3 surveillance check methods."""
    src = (_BRIDGE_DIR / "proactive_monitor.py").read_text(encoding="utf-8")
    # Find each surveillance method body
    forbidden_patterns = [
        "clusters = self._network_detector.detect_clusters()",
        "risky = self._behavioral_arch.get_high_risk_devices(threshold=0.7)",
        "report = self._behavioral_arch.analyze_device(device_id)",
        "leaderboard = self._store.get_leaderboard(100)",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in src, (
            f"Pre-stage-13 unwrapped sync call survived: {pattern!r}"
        )


# ─── Behavioral tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t_235_stab9_13_6_check_anomaly_clusters_does_not_block_loop(tmp_path) -> None:
    """When detect_clusters blocks for 500ms, the event loop must NOT block —
    a concurrent 50ms tick completes well before the blocking sync work
    finishes.
    """
    from bridge.vapi_bridge.proactive_monitor import ProactiveMonitor
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    class _SlowNetDetector:
        def detect_clusters(self):
            time.sleep(0.5)
            return []

    monitor = ProactiveMonitor(
        store=MagicMock(),
        behavioral_arch=MagicMock(),
        network_detector=_SlowNetDetector(),
        agent=None,
        cfg=SimpleNamespace(),
        poll_interval=60.0,
        calibration_agent=None,
    )

    tick_completed_at: list[float] = []

    async def event_loop_tick():
        await asyncio.sleep(0.05)
        tick_completed_at.append(time.monotonic())

    t0 = time.monotonic()
    await asyncio.gather(
        monitor._check_anomaly_clusters(),
        event_loop_tick(),
    )
    check_completed_at = time.monotonic() - t0
    tick_elapsed = tick_completed_at[0] - t0

    assert tick_elapsed < 0.30, (
        f"Event loop was blocked: tick took {tick_elapsed:.3f}s "
        f"(expected <0.30s if to_thread is offloading detect_clusters)"
    )
    assert check_completed_at >= 0.45, (
        f"Check returned in {check_completed_at:.3f}s — expected >=0.45s "
        f"because detect_clusters sleeps 500ms"
    )


@pytest.mark.asyncio
async def test_t_235_stab9_13_7_check_high_risk_trajectories_offloaded(tmp_path) -> None:
    """get_high_risk_devices + analyze_device sync calls run via to_thread —
    a 300ms blocking trajectory check does not block the event loop."""
    from bridge.vapi_bridge.proactive_monitor import ProactiveMonitor
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    class _SlowBehavArch:
        def get_high_risk_devices(self, threshold):
            time.sleep(0.3)
            return []  # empty → no per-device analyze_device calls

    monitor = ProactiveMonitor(
        store=MagicMock(),
        behavioral_arch=_SlowBehavArch(),
        network_detector=MagicMock(),
        agent=None,
        cfg=SimpleNamespace(),
        poll_interval=60.0,
        calibration_agent=None,
    )

    tick_completed_at: list[float] = []

    async def event_loop_tick():
        await asyncio.sleep(0.05)
        tick_completed_at.append(time.monotonic())

    t0 = time.monotonic()
    await asyncio.gather(
        monitor._check_high_risk_trajectories(),
        event_loop_tick(),
    )
    tick_elapsed = tick_completed_at[0] - t0
    assert tick_elapsed < 0.20, (
        f"Event loop blocked during get_high_risk_devices: tick {tick_elapsed:.3f}s"
    )


@pytest.mark.asyncio
async def test_t_235_stab9_13_8_check_eligibility_horizons_offloaded(tmp_path) -> None:
    """get_leaderboard sync call runs via to_thread."""
    from bridge.vapi_bridge.proactive_monitor import ProactiveMonitor
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    class _SlowStore:
        def get_leaderboard(self, n):
            time.sleep(0.3)
            return []

    monitor = ProactiveMonitor(
        store=_SlowStore(),
        behavioral_arch=MagicMock(),
        network_detector=MagicMock(),
        agent=None,
        cfg=SimpleNamespace(),
        poll_interval=60.0,
        calibration_agent=None,
    )

    tick_completed_at: list[float] = []

    async def event_loop_tick():
        await asyncio.sleep(0.05)
        tick_completed_at.append(time.monotonic())

    t0 = time.monotonic()
    await asyncio.gather(
        monitor._check_eligibility_horizons(),
        event_loop_tick(),
    )
    tick_elapsed = tick_completed_at[0] - t0
    assert tick_elapsed < 0.20, (
        f"Event loop blocked during get_leaderboard: tick {tick_elapsed:.3f}s"
    )


# ─── Regression guards ─────────────────────────────────────────────────────


def test_t_235_stab9_13_9_stage12_sync_w3_preserved() -> None:
    """Stage 12 chain.py sync Web3 companion construction MUST remain."""
    src = (_BRIDGE_DIR / "chain.py").read_text(encoding="utf-8")
    assert "self._sync_w3 = Web3(_SyncHTTPProvider(cfg.iotex_rpc_url))" in src


def test_t_235_stab9_13_10_stage11_trigger_source_to_thread_preserved() -> None:
    """Stage 11 trigger-source asyncio.to_thread wrap MUST remain in all 3
    polling stewards."""
    for name in (
        "operator_agent_sentry_polling.py",
        "operator_agent_guardian_polling.py",
        "operator_agent_curator_polling.py",
    ):
        src = (_BRIDGE_DIR / name).read_text(encoding="utf-8")
        assert "asyncio.to_thread" in src, f"{name} Stage 11 wrap regressed"
