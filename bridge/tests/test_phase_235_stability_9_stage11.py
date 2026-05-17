"""Phase 235.x-STABILITY-9 stage 11 (2026-05-17) — Trigger-source
asyncio.to_thread wrap tests.

Validates the surgical fix that moves all 3 stewards' trigger-source
fetch calls off the event loop thread. The trigger sources internally
run subprocess.run(["git", ...], timeout=5.0) (Sentry+Guardian) and
sqlite3.connect + SELECT on hot tables (Guardian FSCA + Curator
marketplace/freshness/compliance), all of which were blocking the
event loop and producing the residual ~50s STARVATION peak that
survived stages 5-10.

Stage 11 wraps the call sites in asyncio.to_thread — three lines
across three files. This test asserts the wrap is present + the
event loop is not blocked when the underlying source sleeps.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest


_BRIDGE_DIR = Path(__file__).resolve().parents[1] / "vapi_bridge"


# ─── Source-pattern presence tests ─────────────────────────────────────────


def test_t_235_stab9_11_1_sentry_to_thread_wrap_present() -> None:
    """Sentry polling loop wraps trigger source in asyncio.to_thread."""
    src = (_BRIDGE_DIR / "operator_agent_sentry_polling.py").read_text(encoding="utf-8")
    assert "await asyncio.to_thread(self._get_triggers)" in src, (
        "SentryPollingLoop._dispatch_one_cycle must invoke "
        "self._get_triggers via asyncio.to_thread"
    )
    # Stage 11 rationale comment present
    assert "stage 11" in src
    assert "GitTriggerSource" in src


def test_t_235_stab9_11_2_guardian_to_thread_wrap_present() -> None:
    """Guardian polling loop wraps trigger source in asyncio.to_thread."""
    src = (_BRIDGE_DIR / "operator_agent_guardian_polling.py").read_text(encoding="utf-8")
    assert "await asyncio.to_thread(self._safe_get_triggers)" in src, (
        "GuardianPollingLoop._run must invoke _safe_get_triggers via "
        "asyncio.to_thread"
    )
    assert "stage 11" in src
    assert "fleet_coherence_log" in src


def test_t_235_stab9_11_3_curator_to_thread_wrap_present() -> None:
    """Curator polling loop wraps trigger source in asyncio.to_thread."""
    src = (_BRIDGE_DIR / "operator_agent_curator_polling.py").read_text(encoding="utf-8")
    assert "await asyncio.to_thread(self._safe_get_triggers)" in src, (
        "CuratorPollingLoop._run must invoke _safe_get_triggers via "
        "asyncio.to_thread"
    )
    assert "stage 11" in src
    assert "marketplace" in src.lower()


def test_t_235_stab9_11_4_no_unwrapped_sync_call_remains() -> None:
    """No bare `triggers = self._get_triggers()` or `_safe_get_triggers()`
    call survives in any steward polling loop."""
    for name in (
        "operator_agent_sentry_polling.py",
        "operator_agent_guardian_polling.py",
        "operator_agent_curator_polling.py",
    ):
        src = (_BRIDGE_DIR / name).read_text(encoding="utf-8")
        # The synchronous call site MUST NOT appear unwrapped in any line.
        # Filter out comment lines that intentionally reference the prior pattern.
        for ln_no, ln in enumerate(src.splitlines(), 1):
            stripped = ln.lstrip()
            if stripped.startswith("#"):
                continue
            if "triggers = self._get_triggers()" in ln:
                pytest.fail(
                    f"{name}:{ln_no} contains unwrapped self._get_triggers()"
                )
            if "triggers = self._safe_get_triggers()" in ln:
                pytest.fail(
                    f"{name}:{ln_no} contains unwrapped self._safe_get_triggers()"
                )


# ─── Behavioral tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_t_235_stab9_11_5_sentry_dispatch_does_not_block_loop(tmp_path) -> None:
    """When the trigger source sleeps for 0.5s, the Sentry polling loop's
    dispatch coroutine must NOT block the event loop — a concurrent
    coroutine should still get scheduled within ~50ms.
    """
    from bridge.vapi_bridge.operator_agent_sentry_polling import SentryPollingLoop
    from bridge.vapi_bridge.store import Store
    from types import SimpleNamespace

    store = Store(str(tmp_path / "stage11.db"))

    def slow_trigger_fetch() -> list[dict]:
        # Simulate subprocess.run / sqlite3.connect blocking for 500ms
        time.sleep(0.5)
        return []  # empty list → no dispatch needed

    cfg = SimpleNamespace(
        operator_agent_sentry_id="0x" + "a" * 64,
        agent_dry_run_mode=True,
        kms_hsm_production_ready=False,
        operator_dual_key_present=False,
        operator_agent_sentry_polling_interval_s=30,
    )
    loop = SentryPollingLoop(
        store=store,
        cfg=cfg,
        draft_generator=None,
        get_pending_triggers=slow_trigger_fetch,
    )

    # Concurrent tick task — should complete in ~50ms even while the
    # dispatch is busy with the 500ms sleep, because the sleep runs
    # on a worker thread.
    tick_done_at: list[float] = []

    async def event_loop_tick():
        await asyncio.sleep(0.05)
        tick_done_at.append(time.monotonic())

    t0 = time.monotonic()
    await asyncio.gather(
        loop._dispatch_one_cycle(),
        event_loop_tick(),
    )
    dispatch_completed_at = time.monotonic() - t0
    tick_elapsed = tick_done_at[0] - t0

    # Tick must complete well before the 500ms sleep ends
    assert tick_elapsed < 0.30, (
        f"Event loop was blocked: concurrent tick took {tick_elapsed:.3f}s "
        f"(expected <0.30s if to_thread is wrapping the slow call)"
    )
    # Dispatch should still wait for the worker — total ~500ms
    assert dispatch_completed_at >= 0.45, (
        f"Dispatch returned in {dispatch_completed_at:.3f}s — expected "
        f">=0.45s because slow_trigger_fetch sleeps 500ms"
    )


@pytest.mark.asyncio
async def test_t_235_stab9_11_6_guardian_safe_get_triggers_offloaded(tmp_path) -> None:
    """Guardian's _safe_get_triggers wrapper is invoked via to_thread —
    raising in the wrapper must not crash the loop (fail-open preserved).
    """
    from bridge.vapi_bridge.operator_agent_guardian_polling import GuardianPollingLoop
    from bridge.vapi_bridge.store import Store
    from types import SimpleNamespace

    store = Store(str(tmp_path / "stage11_guard.db"))

    def raising_trigger_fetch() -> list[dict]:
        time.sleep(0.2)
        raise RuntimeError("synthetic trigger-source crash")

    cfg = SimpleNamespace(
        operator_agent_guardian_id="0x" + "b" * 64,
        agent_dry_run_mode=True,
        kms_hsm_production_ready=False,
        operator_dual_key_present=False,
        github_app_oauth_tokens_valid=False,
        operator_agent_guardian_polling_interval_s=30,
    )
    loop = GuardianPollingLoop(
        store=store,
        cfg=cfg,
        draft_generator=None,
        get_pending_triggers=raising_trigger_fetch,
    )
    # _safe_get_triggers catches and returns []; to_thread must not
    # propagate any exception either way.
    result = await asyncio.to_thread(loop._safe_get_triggers)
    assert result == []


@pytest.mark.asyncio
async def test_t_235_stab9_11_7_curator_safe_get_triggers_offloaded(tmp_path) -> None:
    """Curator's _safe_get_triggers wrapper is invoked via to_thread —
    contract preserved."""
    from bridge.vapi_bridge.operator_agent_curator_polling import CuratorPollingLoop
    from bridge.vapi_bridge.store import Store
    from types import SimpleNamespace

    store = Store(str(tmp_path / "stage11_curator.db"))

    def quick_trigger_fetch() -> list[dict]:
        return [{"kind": "listing_event", "payload": {}}]

    cfg = SimpleNamespace(
        operator_agent_curator_id="0x" + "c" * 64,
        agent_dry_run_mode=True,
        kms_hsm_production_ready=False,
        operator_dual_key_present=False,
        marketplace_curator_role_assigned=False,
        operator_agent_curator_polling_interval_s=30,
    )
    loop = CuratorPollingLoop(
        store=store,
        cfg=cfg,
        draft_generator=None,
        get_pending_triggers=quick_trigger_fetch,
    )
    result = await asyncio.to_thread(loop._safe_get_triggers)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["kind"] == "listing_event"


# ─── Regression guards ─────────────────────────────────────────────────────


def test_t_235_stab9_11_8_stage8_sqlite_wrap_pattern_preserved() -> None:
    """Stage 8 chain_reconciler asyncio.to_thread wrap MUST remain — the
    Stage 11 fix is the same SHAPE pattern in a different layer; we
    must not have inadvertently regressed Stage 8."""
    src = (_BRIDGE_DIR / "chain_reconciler.py").read_text(encoding="utf-8")
    assert "asyncio.to_thread" in src, (
        "Stage 8 chain_reconciler to_thread wrap regressed"
    )


def test_t_235_stab9_11_9_stage4_fsca_to_thread_preserved() -> None:
    """Stage 1+4 FSCA _promote_to_wif asyncio.to_thread wrap MUST remain."""
    src = (_BRIDGE_DIR / "fleet_signal_coherence_agent.py").read_text(encoding="utf-8")
    assert "asyncio.to_thread(self._promote_to_wif" in src, (
        "Stage 1/4 FSCA _promote_to_wif to_thread wrap regressed"
    )


def test_t_235_stab9_11_10_all_three_stewards_have_stage11_marker() -> None:
    """All three stewards' source files carry the stage 11 rationale
    comment so future archaeologists can grep `stage 11` to find every
    site touched by this fix."""
    for name in (
        "operator_agent_sentry_polling.py",
        "operator_agent_guardian_polling.py",
        "operator_agent_curator_polling.py",
    ):
        src = (_BRIDGE_DIR / name).read_text(encoding="utf-8")
        assert "stage 11" in src, f"{name} missing stage 11 marker comment"
