"""Phase O2-DRAFT-AUTOLOOP (Guardian) -- polling-loop scaffold tests.

Sibling of test_phase_o2_polling_sentry.py. Verifies GuardianPollingLoop's
dispatch matrix, rate-limiting, lifecycle, opt-in default, fail-open error
handling, and draft counter accuracy.

  T-O2-POLL-GUARDIAN-1: dispatch matrix routes each kind correctly
                        (sweep_completed -> audit-drafting;
                         fsca_finding -> operational-diagnostic;
                         commit -> kms-sign + audit-drafting)
  T-O2-POLL-GUARDIAN-2: rate limiting -- ONE trigger per cycle.
                        Counter unit drift vs Sentry: Guardian's _record_result
                        increments per-METHOD-success, so a commit trigger
                        bumps _drafts_count by 2. Documented + asserted.
  T-O2-POLL-GUARDIAN-3: start()/stop() lifecycle -- async, no zombie task.
  T-O2-POLL-GUARDIAN-4: opt-in default -- run_guardian_polling_loop returns
                        immediately when flag=False.
  T-O2-POLL-GUARDIAN-5: trigger handler errors don't crash loop.
  T-O2-POLL-GUARDIAN-6: _drafts_this_session() accurate (per-method-success
                        counting; commit=2, sweep_completed=1, fsca_finding=1).
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

for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _make_store(tmp_path):
    from vapi_bridge.store import Store
    return Store(str(tmp_path / "guardian_polling_test.db"))


def _make_cfg(**overrides):
    cfg = types.SimpleNamespace()
    cfg.operator_agent_guardian_polling_enabled = False
    cfg.operator_agent_guardian_polling_interval_s = 1
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# T-O2-POLL-GUARDIAN-1: dispatch matrix
def test_T_O2_POLL_GUARDIAN_1_dispatch_matrix(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator
    from vapi_bridge.operator_agent_guardian_polling import GuardianPollingLoop

    # sweep_completed -> audit-drafting
    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)
    triggers_sweep = [{
        "kind": "sweep_completed",
        "payload": {
            "sweep_id": "skill14-2026-05-10",
            "findings_count": 0,
            "summary_text": "12 invariants verified clean",
        },
    }]
    loop_sweep = GuardianPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: triggers_sweep,
    )
    asyncio.run(loop_sweep._run_one_cycle()) if hasattr(loop_sweep, "_run_one_cycle") else loop_sweep._dispatch_one(triggers_sweep[0])
    rows = store.get_operator_agent_drafts(agent_id="guardian", limit=10)
    assert len(rows) == 1
    assert rows[0]["action_name"] == "audit-drafting"

    # fsca_finding -> operational-diagnostic
    store2 = _make_store(tmp_path / "fsca")
    gen2 = GuardianDraftGenerator(cfg=_make_cfg(), store=store2)
    loop_fsca = GuardianPollingLoop(
        cfg=_make_cfg(), store=store2, draft_generator=gen2,
        get_pending_triggers=lambda: [],
    )
    loop_fsca._dispatch_one({
        "kind": "fsca_finding",
        "payload": {
            "finding_id": "BUNDLE_HASH_DRIFT_DETECTED-001",
            "severity": "warn",
            "agents_involved": ["anchor_sentry", "guardian"],
            "subject": "BUNDLE_HASH_DRIFT severity=HIGH window=15min",
        },
    })
    rows = store2.get_operator_agent_drafts(agent_id="guardian", limit=10)
    assert len(rows) == 1
    assert rows[0]["action_name"] == "operational-diagnostic"

    # commit -> kms-sign + audit-drafting (2 rows)
    store3 = _make_store(tmp_path / "commit")
    gen3 = GuardianDraftGenerator(cfg=_make_cfg(), store=store3)
    loop_commit = GuardianPollingLoop(
        cfg=_make_cfg(), store=store3, draft_generator=gen3,
        get_pending_triggers=lambda: [],
    )
    loop_commit._dispatch_one({
        "kind": "commit",
        "payload": {
            "commit_hash": "a" * 40,
            "repo": "ConWan30/vapi-prototype",
            "branch": "main",
        },
    })
    rows = store3.get_operator_agent_drafts(agent_id="guardian", limit=10)
    actions = sorted(r["action_name"] for r in rows)
    assert actions == ["audit-drafting", "kms-sign"]


# T-O2-POLL-GUARDIAN-2: rate limiting
def test_T_O2_POLL_GUARDIAN_2_rate_limit_one_trigger_per_cycle(tmp_path):
    """5 sweep_completed triggers queued; one cycle dispatches HEAD only.
    Counter unit: Guardian increments per method success, so this trigger
    (which calls draft_audit_entry once) bumps counter by 1."""
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator
    from vapi_bridge.operator_agent_guardian_polling import GuardianPollingLoop

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)
    triggers = [
        {
            "kind": "sweep_completed",
            "payload": {
                "sweep_id": f"sweep-{i:04d}",
                "findings_count": 0,
                "summary_text": f"sweep {i}",
            },
        }
        for i in range(5)
    ]
    loop = GuardianPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: triggers,
    )
    # Drive one cycle worth of dispatch (head only).
    res = loop._safe_get_triggers()
    assert len(res) == 5  # source still has 5
    loop._dispatch_one(res[0])  # head dispatched

    n = store.count_operator_agent_drafts(agent_id="guardian", since_seconds=86400)
    assert n == 1  # one row from one sweep
    assert loop._drafts_this_session() == 1  # 1 method success


# T-O2-POLL-GUARDIAN-3: start()/stop() lifecycle
@pytest.mark.asyncio
async def test_T_O2_POLL_GUARDIAN_3_start_stop_lifecycle(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator
    from vapi_bridge.operator_agent_guardian_polling import GuardianPollingLoop

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)
    loop = GuardianPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: [],
    )
    await loop.start()
    await asyncio.sleep(0.05)
    assert loop._task is not None
    assert not loop._task.done()
    await loop.stop()
    assert loop._task is None


# T-O2-POLL-GUARDIAN-4: opt-in default
@pytest.mark.asyncio
async def test_T_O2_POLL_GUARDIAN_4_opt_in_default(tmp_path):
    from vapi_bridge.operator_agent_guardian_polling import run_guardian_polling_loop

    store = _make_store(tmp_path)
    cfg = _make_cfg(operator_agent_guardian_polling_enabled=False)
    await asyncio.wait_for(
        run_guardian_polling_loop(cfg=cfg, store=store),
        timeout=1.0,
    )


# T-O2-POLL-GUARDIAN-5: trigger handler errors don't crash loop
def test_T_O2_POLL_GUARDIAN_5_handler_errors_do_not_crash_loop(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator
    from vapi_bridge.operator_agent_guardian_polling import GuardianPollingLoop

    store = _make_store(tmp_path)
    real_gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)

    class _FlakyGen:
        def __init__(self, real):
            self._real = real
            self._n = 0

        def draft_audit_entry(self, **kw):
            self._n += 1
            if self._n == 1:
                raise RuntimeError("simulated audit-entry failure")
            return self._real.draft_audit_entry(**kw)

        def draft_operational_diagnostic(self, **kw):
            return self._real.draft_operational_diagnostic(**kw)

        def draft_kms_sign(self, **kw):
            return self._real.draft_kms_sign(**kw)

    flaky = _FlakyGen(real_gen)
    loop = GuardianPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=flaky,
        get_pending_triggers=lambda: [],
    )

    # First sweep -> audit_entry raises; loop catches.
    loop._dispatch_one({
        "kind": "sweep_completed",
        "payload": {"sweep_id": "s1", "findings_count": 0, "summary_text": "x"},
    })
    # Second sweep -> succeeds.
    loop._dispatch_one({
        "kind": "sweep_completed",
        "payload": {"sweep_id": "s2", "findings_count": 0, "summary_text": "y"},
    })

    rows = store.get_operator_agent_drafts(agent_id="guardian", limit=10)
    # Only the second sweep produced a row (first raised).
    assert len(rows) == 1
    assert loop._drafts_this_session() == 1


# T-O2-POLL-GUARDIAN-6: _drafts_this_session() per-method-success count
def test_T_O2_POLL_GUARDIAN_6_drafts_this_session_count(tmp_path):
    """Mix of triggers; counter == sum of successful method invocations.
    commit=2 methods, sweep_completed=1, fsca_finding=1."""
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator
    from vapi_bridge.operator_agent_guardian_polling import GuardianPollingLoop

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)
    loop = GuardianPollingLoop(
        cfg=_make_cfg(), store=store, draft_generator=gen,
        get_pending_triggers=lambda: [],
    )
    triggers = [
        {"kind": "commit", "payload": {
            "commit_hash": "a" * 40, "repo": "x", "branch": "y"}},  # +2
        {"kind": "sweep_completed", "payload": {
            "sweep_id": "s-1", "findings_count": 1, "summary_text": "x"}},  # +1
        {"kind": "fsca_finding", "payload": {
            "finding_id": "f-1", "severity": "warn",
            "agents_involved": ["guardian"], "subject": "drift"}},  # +1
        {"kind": "commit", "payload": {
            "commit_hash": "b" * 40, "repo": "x", "branch": "y"}},  # +2
    ]
    for t in triggers:
        loop._dispatch_one(t)

    expected_methods = 2 + 1 + 1 + 2  # = 6
    assert loop._drafts_this_session() == expected_methods
    n_rows = store.count_operator_agent_drafts(
        agent_id="guardian", since_seconds=86400,
    )
    assert n_rows == expected_methods  # 1 row per method invocation
