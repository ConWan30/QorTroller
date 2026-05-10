"""Phase O2-DRAFT-AUTOLOOP (Sentry) -- polling-loop scaffold tests.

Verifies the SentryPollingLoop dispatch matrix, rate-limiting, lifecycle,
opt-in default, fail-open error handling, and draft counter accuracy.

  T-O2-POLL-SENTRY-1: dispatch matrix routes each trigger kind to the right
                      draft methods (commit -> kms-sign + provenance;
                      poac_chain_head -> provenance; poad_hash -> pda-anchor)
  T-O2-POLL-SENTRY-2: rate limiting -- ONE trigger per cycle (queue head);
                      remaining triggers wait. Unit is "trigger" not "draft row"
                      (commit produces 2 rows but counts as 1 trigger).
  T-O2-POLL-SENTRY-3: start()/stop() lifecycle -- async, no zombie task,
                      no exceptions.
  T-O2-POLL-SENTRY-4: opt-in default -- run_sentry_polling_loop returns
                      immediately when flag=False (no blocking).
  T-O2-POLL-SENTRY-5: trigger handler errors don't crash loop -- a generator
                      whose method raises is caught + logged + skipped; the
                      next trigger still dispatches normally.
  T-O2-POLL-SENTRY-6: _drafts_this_session() accurate count -- N triggers
                      pushed across N cycles -> counter equals N.
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub web3 + eth_account modules so any indirect import doesn't trip.
for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _make_store(tmp_path):
    from vapi_bridge.store import Store
    db_path = tmp_path / "polling_test.db"
    return Store(str(db_path))


def _make_cfg(**overrides):
    """Minimal cfg -- canonical agent_id ('anchor_sentry') used; no Q9 hex."""
    cfg = types.SimpleNamespace()
    # Default: short interval so tests run fast.
    cfg.operator_agent_sentry_polling_enabled = False
    cfg.operator_agent_sentry_polling_interval_s = 1
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# --------------------------------------------------------------------------
# T-O2-POLL-SENTRY-1: dispatch matrix
# --------------------------------------------------------------------------
def test_T_O2_POLL_SENTRY_1_dispatch_matrix(tmp_path):
    """Each trigger kind routes to the documented draft method(s)."""
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_agent_sentry_polling import SentryPollingLoop

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    # --- commit trigger -> kms-sign + provenance-recording (2 rows) ---
    triggers_commit = [{
        "kind": "commit",
        "payload": {
            "commit_hash": "a" * 40,
            "repo": "ConWan30/vapi-prototype",
            "branch": "main",
        },
    }]
    loop_commit = SentryPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: triggers_commit,
    )
    asyncio.run(loop_commit._dispatch_one_cycle())

    rows = store.get_operator_agent_drafts(agent_id="anchor_sentry", limit=10)
    actions = sorted(r["action_name"] for r in rows)
    assert actions == ["kms-sign", "provenance-recording"]
    assert store.count_operator_agent_drafts(
        agent_id="anchor_sentry", since_seconds=86400,
    ) == 2

    # --- poac_chain_head trigger -> provenance-recording only ---
    store2 = _make_store(tmp_path / "poac")
    gen2 = SentryDraftGenerator(cfg=_make_cfg(), store=store2)
    triggers_poac = [{
        "kind": "poac_chain_head",
        "payload": {"chain_head_hex": "f" * 64, "ts_ns": 1234567890},
    }]
    loop_poac = SentryPollingLoop(
        cfg=_make_cfg(), store=store2, draft_generator=gen2,
        get_pending_triggers=lambda: triggers_poac,
    )
    asyncio.run(loop_poac._dispatch_one_cycle())
    rows = store2.get_operator_agent_drafts(agent_id="anchor_sentry", limit=10)
    assert len(rows) == 1
    assert rows[0]["action_name"] == "provenance-recording"

    # --- poad_hash trigger -> pda-attestation-anchor only ---
    store3 = _make_store(tmp_path / "poad")
    gen3 = SentryDraftGenerator(cfg=_make_cfg(), store=store3)
    triggers_poad = [{
        "kind": "poad_hash",
        "payload": {
            "device_id_hash_hex": "8" * 64,
            "poad_hash_hex": "9" * 64,
        },
    }]
    loop_poad = SentryPollingLoop(
        cfg=_make_cfg(), store=store3, draft_generator=gen3,
        get_pending_triggers=lambda: triggers_poad,
    )
    asyncio.run(loop_poad._dispatch_one_cycle())
    rows = store3.get_operator_agent_drafts(agent_id="anchor_sentry", limit=10)
    assert len(rows) == 1
    assert rows[0]["action_name"] == "pda-attestation-anchor"


# --------------------------------------------------------------------------
# T-O2-POLL-SENTRY-2: rate limiting (one trigger per cycle)
# --------------------------------------------------------------------------
def test_T_O2_POLL_SENTRY_2_rate_limit_one_trigger_per_cycle(tmp_path):
    """get_pending_triggers returns 5 distinct triggers; ONE cycle dispatches
    only the head. Document the unit: a 'commit' trigger produces 2 rows
    but counts as 1 trigger toward the per-cycle ceiling."""
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_agent_sentry_polling import SentryPollingLoop

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    # 5 commit triggers with distinct commit_hashes -> distinct payloads.
    triggers = [
        {
            "kind": "commit",
            "payload": {
                "commit_hash": f"{i:040x}",
                "repo": "x",
                "branch": "main",
            },
        }
        for i in range(5)
    ]
    loop = SentryPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: triggers,
    )
    asyncio.run(loop._dispatch_one_cycle())

    # Only the FIRST commit-trigger dispatched. That trigger produces 2 rows
    # (kms-sign + provenance), so total rows == 2 and trigger count == 1.
    n = store.count_operator_agent_drafts(
        agent_id="anchor_sentry", since_seconds=86400,
    )
    assert n == 2  # 2 rows from one commit trigger
    assert loop._drafts_this_session() == 1  # 1 trigger dispatched

    # Verify head-of-queue selection: commit_hash 0000...0000 was dispatched
    rows = store.get_operator_agent_drafts(agent_id="anchor_sentry", limit=10)
    kms_rows = [r for r in rows if r["action_name"] == "kms-sign"]
    assert len(kms_rows) == 1
    assert kms_rows[0]["draft_uri"].endswith("0" * 40)


# --------------------------------------------------------------------------
# T-O2-POLL-SENTRY-3: start()/stop() lifecycle
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_T_O2_POLL_SENTRY_3_start_stop_lifecycle(tmp_path):
    """start() -> short sleep -> stop() with no exceptions, no zombie task."""
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_agent_sentry_polling import SentryPollingLoop

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)
    loop = SentryPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: [],  # no-op stub
    )
    await loop.start()
    # Give the loop time to enter its sleep.
    await asyncio.sleep(0.05)
    assert loop._task is not None
    assert not loop._task.done()
    await loop.stop()
    assert loop._task is None  # cleaned up


# --------------------------------------------------------------------------
# T-O2-POLL-SENTRY-4: opt-in default -- short-circuit when flag=False
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_T_O2_POLL_SENTRY_4_opt_in_default(tmp_path):
    """run_sentry_polling_loop returns immediately when
    operator_agent_sentry_polling_enabled is False (default)."""
    from vapi_bridge.operator_agent_sentry_polling import run_sentry_polling_loop

    store = _make_store(tmp_path)
    cfg = _make_cfg(operator_agent_sentry_polling_enabled=False)

    # Must NOT block. wait_for(...) raises TimeoutError if it does.
    await asyncio.wait_for(
        run_sentry_polling_loop(cfg=cfg, store=store),
        timeout=1.0,
    )


# --------------------------------------------------------------------------
# T-O2-POLL-SENTRY-5: trigger handler errors don't crash loop
# --------------------------------------------------------------------------
def test_T_O2_POLL_SENTRY_5_handler_errors_do_not_crash_loop(tmp_path):
    """A generator whose method raises is caught + logged + skipped; the
    next trigger still dispatches normally."""
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_agent_sentry_polling import SentryPollingLoop

    store = _make_store(tmp_path)
    real_gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    # Wrap real generator: first call raises, subsequent calls forward.
    class _FlakyGen:
        def __init__(self, real):
            self._real = real
            self._n = 0

        def draft_kms_sign(self, **kw):
            self._n += 1
            if self._n == 1:
                raise RuntimeError("simulated kms-sign failure")
            return self._real.draft_kms_sign(**kw)

        def draft_provenance_record(self, **kw):
            return self._real.draft_provenance_record(**kw)

        def draft_pda_anchor(self, **kw):
            return self._real.draft_pda_anchor(**kw)

    flaky = _FlakyGen(real_gen)

    # Use a mutable trigger queue so we can drain head-by-head across cycles.
    queue: list[dict] = [
        {"kind": "commit", "payload": {"commit_hash": "a" * 40,
                                         "repo": "x", "branch": "y"}},
        {"kind": "commit", "payload": {"commit_hash": "b" * 40,
                                         "repo": "x", "branch": "y"}},
    ]

    def take_head():
        # Return ONLY the head; once it's been dispatched-or-tried, drop it.
        return queue[:1] if queue else []

    loop = SentryPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=flaky,
        get_pending_triggers=take_head,
    )

    # Cycle 1: head = commit a; flaky kms-sign raises; loop swallows.
    asyncio.run(loop._dispatch_one_cycle())
    queue.pop(0)  # operator drained head after the dispatch attempt

    # Cycle 2: head = commit b; flaky kms-sign succeeds.
    asyncio.run(loop._dispatch_one_cycle())
    queue.pop(0)

    # The first commit trigger raised mid-flight -> kms-sign failed,
    # provenance-recording NEVER ran (sequential dispatch breaks on raise).
    # The second commit trigger fully succeeds -> 2 rows.
    rows = store.get_operator_agent_drafts(agent_id="anchor_sentry", limit=10)
    actions = sorted(r["action_name"] for r in rows)
    assert actions == ["kms-sign", "provenance-recording"]
    # Both cycles incremented _drafts_count? No -- the failed cycle is NOT
    # counted (exception path). Only the successful cycle increments.
    assert loop._drafts_this_session() == 1


# --------------------------------------------------------------------------
# T-O2-POLL-SENTRY-6: _drafts_this_session() accurate count
# --------------------------------------------------------------------------
def test_T_O2_POLL_SENTRY_6_drafts_this_session_count(tmp_path):
    """Push N triggers, run N cycles; counter equals N (unit = trigger,
    not draft row)."""
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_agent_sentry_polling import SentryPollingLoop

    store = _make_store(tmp_path)
    gen = SentryDraftGenerator(cfg=_make_cfg(), store=store)

    # Mix of 2 commits + 2 poad_hashes + 1 poac_chain_head = 5 triggers.
    queue: list[dict] = [
        {"kind": "commit", "payload": {
            "commit_hash": "a" * 40, "repo": "x", "branch": "y"}},
        {"kind": "poad_hash", "payload": {
            "device_id_hash_hex": "1" * 64, "poad_hash_hex": "2" * 64}},
        {"kind": "poac_chain_head", "payload": {
            "chain_head_hex": "c" * 64, "ts_ns": 100}},
        {"kind": "commit", "payload": {
            "commit_hash": "b" * 40, "repo": "x", "branch": "y"}},
        {"kind": "poad_hash", "payload": {
            "device_id_hash_hex": "3" * 64, "poad_hash_hex": "4" * 64}},
    ]
    n_triggers = len(queue)

    def take_head():
        return queue[:1] if queue else []

    loop = SentryPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=take_head,
    )

    for _ in range(n_triggers):
        asyncio.run(loop._dispatch_one_cycle())
        if queue:
            queue.pop(0)

    # Counter equals number of triggers dispatched (5).
    assert loop._drafts_this_session() == n_triggers

    # Total draft rows in store: commits produce 2 rows each (2 commits ->
    # 4 rows), poad_hash produces 1 (2 -> 2 rows), poac_chain_head produces 1.
    # Expected total: 4 + 2 + 1 = 7.
    n_rows = store.count_operator_agent_drafts(
        agent_id="anchor_sentry", since_seconds=86400,
    )
    assert n_rows == 7
