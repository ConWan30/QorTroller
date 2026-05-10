"""Phase O2-DRAFT-GENERATION (Guardian) -- end-to-end primitive tests.

Mirrors test_phase_o2_draft_generation_sentry.py with Guardian-specific
URI schemes + skill names. Verifies the parallel-fleet drafting symmetry
(Sentry and Guardian both produce drafts under their respective Cedar-
permitted resource paths; both contribute toward the watcher's
PHASE_O3_DRAFT_PAYLOAD_MIN gate per agent).

  T-O2-DRAFT-GUARDIAN-1: kms-sign draft persists (mirrors Sentry T-1)
  T-O2-DRAFT-GUARDIAN-2: audit-drafting on audit_entries/* with sanitized id
  T-O2-DRAFT-GUARDIAN-3: operational-diagnostic on audit_entries/diag-*
                          (URI prefix-disambiguates audit vs diag at-a-glance)
  T-O2-DRAFT-GUARDIAN-4: count_drafts returns N=50 for Guardian after 50 inserts
                          (independent of Sentry's count -- per-agent gate)
  T-O2-DRAFT-GUARDIAN-5: invalid input early-returns with no DB write
                          (bad commit hash; empty audit_id; non-dict payload;
                          bad severity)
  T-O2-DRAFT-GUARDIAN-6: end-to-end watcher gate clears for Guardian
                          (50 audit drafts -> _count_drafts_safe(guardian) == 50)
  T-O2-DRAFT-GUARDIAN-7: Guardian and Sentry counts are INDEPENDENT
                          (parallel-fleet invariant: each agent counts its own
                          drafts; cross-counts MUST NOT pollute either gate)
  T-O2-DRAFT-GUARDIAN-8: idempotent insert -- same audit_id+payload returns
                          same row_id; count remains 1
  T-O2-DRAFT-GUARDIAN-9: severity field validated against
                          {info,warn,error,critical}; other values fail
  T-O2-DRAFT-GUARDIAN-10: Guardian drafts pass through agent-specific
                          disagreement_rate computation (mirrors Sentry T-6)
"""

from __future__ import annotations

import sys
import time
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
    db_path = tmp_path / "guardian_drafts_test.db"
    return Store(str(db_path))


def _make_cfg(**overrides):
    cfg = types.SimpleNamespace()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# --------------------------------------------------------------------------
# T-O2-DRAFT-GUARDIAN-1: kms-sign draft persistence
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_GUARDIAN_1_kms_sign_persists(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import (
        GuardianDraftGenerator,
        GUARDIAN_KMS_SIGN_DRAFT_PREFIX,
    )

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)
    commit = "1" * 40

    result = gen.draft_kms_sign(
        commit_hash=commit,
        signer_pubkey_hex="0xabcdef",
        signature_payload={"repo": "vapi-prototype", "branch": "audits/sweep-N"},
    )
    assert result.error is None
    assert result.draft_id > 0
    assert result.draft_uri == f"{GUARDIAN_KMS_SIGN_DRAFT_PREFIX}{commit}"
    assert result.action_name == "kms-sign"
    assert result.agent_id_used == "guardian"

    rows = store.get_operator_agent_drafts(agent_id="guardian", limit=10)
    assert len(rows) == 1
    assert rows[0]["kms_sig_present"] == 1
    assert rows[0]["operator_decision"] is None


# --------------------------------------------------------------------------
# T-O2-DRAFT-GUARDIAN-2: audit-drafting on audit_entries/*
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_GUARDIAN_2_audit_drafting_persists(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import (
        GuardianDraftGenerator,
        GUARDIAN_AUDIT_DRAFT_PREFIX,
    )

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)

    # audit_id with disallowed chars -> sanitized
    result = gen.draft_audit_entry(
        audit_id="invariant/INV-007/sweep:2026-05-10",
        audit_payload={
            "subject": "INV-007 stable EMA NOMINAL-only enforcement",
            "finding": "compliant across 100 sessions in window",
            "evidence_count": 100,
        },
        audit_kind="invariant_drift",
    )
    assert result.error is None
    assert result.draft_id > 0
    assert result.draft_uri.startswith(GUARDIAN_AUDIT_DRAFT_PREFIX)
    # / and : -> _
    assert "invariant_INV-007_sweep_2026-05-10" in result.draft_uri
    assert result.action_category == "skill"
    assert result.action_name == "audit-drafting"


# --------------------------------------------------------------------------
# T-O2-DRAFT-GUARDIAN-3: operational-diagnostic uses diag- prefix
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_GUARDIAN_3_operational_diagnostic_diag_prefix(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import (
        GuardianDraftGenerator,
        GUARDIAN_AUDIT_DRAFT_PREFIX,
    )

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)

    result = gen.draft_operational_diagnostic(
        diagnostic_id="watchdog-restart-2026-05-10-T22:00",
        diagnostic_payload={
            "subject": "bridge process restart",
            "trigger": "BRIDGE_UNRESPONSIVE",
            "shadow_age_at_restart_hours": 152.0,
        },
        severity="warn",
    )
    assert result.error is None
    assert result.draft_id > 0
    # diag- prefix distinguishes from audit-drafting URIs at-a-glance
    assert result.draft_uri.startswith(f"{GUARDIAN_AUDIT_DRAFT_PREFIX}diag-")
    assert result.action_name == "operational-diagnostic"


# --------------------------------------------------------------------------
# T-O2-DRAFT-GUARDIAN-4: count_drafts(guardian) returns N=50 after 50 inserts
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_GUARDIAN_4_count_returns_true_count(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)

    for i in range(50):
        result = gen.draft_audit_entry(
            audit_id=f"audit-{i:04d}",
            audit_payload={"finding": f"sweep finding {i}", "n": i},
        )
        assert result.error is None
        assert result.draft_id > 0

    n = store.count_operator_agent_drafts(
        agent_id="guardian", since_seconds=86400,
    )
    assert n == 50


# --------------------------------------------------------------------------
# T-O2-DRAFT-GUARDIAN-5: invalid input early-returns
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_GUARDIAN_5_invalid_input(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)

    # Bad commit hash
    r1 = gen.draft_kms_sign(commit_hash="abc")
    assert r1.error is not None
    assert r1.draft_id == 0

    # Empty audit_id
    r2 = gen.draft_audit_entry(audit_id="", audit_payload={"k": "v"})
    assert r2.error is not None
    assert r2.draft_id == 0

    # Non-dict audit_payload
    r3 = gen.draft_audit_entry(
        audit_id="ok", audit_payload="not a dict",  # type: ignore[arg-type]
    )
    assert r3.error is not None
    assert r3.draft_id == 0

    # Bad severity
    r4 = gen.draft_operational_diagnostic(
        diagnostic_id="x", diagnostic_payload={"k": "v"}, severity="extreme",
    )
    assert r4.error is not None
    assert r4.draft_id == 0
    assert "severity" in r4.error

    # Empty diagnostic_id
    r5 = gen.draft_operational_diagnostic(
        diagnostic_id="", diagnostic_payload={"k": "v"},
    )
    assert r5.error is not None
    assert r5.draft_id == 0

    # No rows persisted
    assert store.count_operator_agent_drafts(
        agent_id="guardian", since_seconds=86400,
    ) == 0


# --------------------------------------------------------------------------
# T-O2-DRAFT-GUARDIAN-6: end-to-end watcher gate clears for Guardian
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_GUARDIAN_6_watcher_gate_clears(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator
    from vapi_bridge.operator_initiative_advancement import (
        PHASE_O3_DRAFT_PAYLOAD_MIN,
        _count_drafts_safe,
    )

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)

    # Below threshold
    for i in range(10):
        gen.draft_audit_entry(
            audit_id=f"audit-{i:04d}",
            audit_payload={"finding": f"f{i}"},
        )
    assert _count_drafts_safe(store, "guardian") == 10
    assert _count_drafts_safe(store, "guardian") < PHASE_O3_DRAFT_PAYLOAD_MIN

    # At threshold
    for i in range(10, PHASE_O3_DRAFT_PAYLOAD_MIN):
        gen.draft_audit_entry(
            audit_id=f"audit-{i:04d}",
            audit_payload={"finding": f"f{i}"},
        )
    assert _count_drafts_safe(store, "guardian") == PHASE_O3_DRAFT_PAYLOAD_MIN


# --------------------------------------------------------------------------
# T-O2-DRAFT-GUARDIAN-7: Sentry + Guardian counts are INDEPENDENT
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_GUARDIAN_7_per_agent_isolation(tmp_path):
    """Parallel-fleet invariant: each agent's draft count is per-agent.
    Sentry's drafts MUST NOT inflate Guardian's count and vice versa."""
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator

    store = _make_store(tmp_path)
    sentry = SentryDraftGenerator(cfg=_make_cfg(), store=store)
    guardian = GuardianDraftGenerator(cfg=_make_cfg(), store=store)

    # 10 Sentry drafts
    for i in range(10):
        sentry.draft_kms_sign(commit_hash=f"{i:040x}")
    # 5 Guardian drafts
    for i in range(5):
        guardian.draft_audit_entry(
            audit_id=f"a-{i}", audit_payload={"i": i},
        )

    n_sentry = store.count_operator_agent_drafts(
        agent_id="anchor_sentry", since_seconds=86400,
    )
    n_guardian = store.count_operator_agent_drafts(
        agent_id="guardian", since_seconds=86400,
    )
    assert n_sentry == 10
    assert n_guardian == 5
    # Total stored is 15; per-agent counts must each be < 15
    assert n_sentry + n_guardian == 15


# --------------------------------------------------------------------------
# T-O2-DRAFT-GUARDIAN-8: idempotent insert
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_GUARDIAN_8_idempotent_insert(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)

    # Same audit_id + same payload (locked ts_ns) -> same hash -> same row
    payload = {"finding": "stable", "ts_ns": 1234567890}
    r1 = gen.draft_audit_entry(audit_id="audit-stable", audit_payload=payload)
    r2 = gen.draft_audit_entry(audit_id="audit-stable", audit_payload=payload)

    assert r1.payload_hash == r2.payload_hash
    assert r1.draft_id == r2.draft_id
    assert store.count_operator_agent_drafts(
        agent_id="guardian", since_seconds=86400,
    ) == 1


# --------------------------------------------------------------------------
# T-O2-DRAFT-GUARDIAN-9: severity validation
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_GUARDIAN_9_severity_validation(tmp_path):
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator

    store = _make_store(tmp_path)
    gen = GuardianDraftGenerator(cfg=_make_cfg(), store=store)

    # All four valid severities accepted
    for sev in ("info", "warn", "error", "critical"):
        result = gen.draft_operational_diagnostic(
            diagnostic_id=f"diag-{sev}",
            diagnostic_payload={"x": 1},
            severity=sev,
        )
        assert result.error is None, f"{sev} must be accepted"
        assert result.draft_id > 0

    # Invalid severities rejected
    for sev in ("urgent", "INFO", "panic", ""):
        result = gen.draft_operational_diagnostic(
            diagnostic_id=f"diag-bad-{sev}",
            diagnostic_payload={"x": 1},
            severity=sev,
        )
        assert result.error is not None
        assert result.draft_id == 0


# --------------------------------------------------------------------------
# T-O2-DRAFT-GUARDIAN-10: agent-specific disagreement_rate
# --------------------------------------------------------------------------
def test_T_O2_DRAFT_GUARDIAN_10_disagreement_rate(tmp_path):
    """Guardian's disagreement_rate is computed from operator decisions on
    Guardian drafts only -- Sentry decisions do not pollute Guardian's
    rate (parallel-fleet per-agent gate semantic)."""
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator

    store = _make_store(tmp_path)
    sentry = SentryDraftGenerator(cfg=_make_cfg(), store=store)
    guardian = GuardianDraftGenerator(cfg=_make_cfg(), store=store)

    # 20 Guardian drafts; review 10 (8 accept + 2 reject) -> 20% disagreement
    g_drafts = []
    for i in range(20):
        g_drafts.append(
            guardian.draft_audit_entry(
                audit_id=f"audit-{i:04d}", audit_payload={"i": i},
            )
        )
    for i in range(8):
        store.record_operator_decision(draft_id=g_drafts[i].draft_id, decision="accept")
    for i in range(8, 10):
        store.record_operator_decision(draft_id=g_drafts[i].draft_id, decision="reject")

    # 10 Sentry drafts; review 10 (all reject) -> Sentry has 100% disagreement
    s_drafts = []
    for i in range(10):
        s_drafts.append(sentry.draft_kms_sign(commit_hash=f"{i:040x}"))
    for r in s_drafts:
        store.record_operator_decision(draft_id=r.draft_id, decision="reject")

    # Each agent's disagreement rate is computed against its OWN reviewed
    # drafts only -- per-agent isolation invariant.
    g_rate = store.compute_operator_agent_disagreement_rate(
        agent_id="guardian", since_seconds=86400,
    )
    s_rate = store.compute_operator_agent_disagreement_rate(
        agent_id="anchor_sentry", since_seconds=86400,
    )
    assert g_rate == pytest.approx(2 / 10)
    assert s_rate == pytest.approx(1.0)
    assert g_rate < s_rate
