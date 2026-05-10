"""Phase O1-FRR — Fleet Readiness Root primitive tests.

Six tests cover the FROZEN-v1 contract:

  T-O1-FRR-1: compute_fleet_readiness_root is deterministic across
              invocations with the same input.
  T-O1-FRR-2: Sort canonicalization — agents passed in ANY input order
              yield the same FRR (sort by agent_id bytes ascending).
  T-O1-FRR-3: Phase code change flips FRR — single bit-flip in any
              phase_code emits a different digest.
  T-O1-FRR-4: Domain tag is part of the pre-image — changing the tag
              would emit a different digest (verified by manual recompute).
  T-O1-FRR-5: evaluate_frr_sync fail-open returns
              FleetReadinessRootResult(error=...) on injected exception.
  T-O1-FRR-6: insert_operator_initiative_advancement_log +
              get_latest_operator_initiative_advancement round-trip
              preserves frr_hex.

These tests use stub Config + Store classes that match production
interfaces — kept self-contained per Phase O1 D test pattern.
"""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
import time
import types
from pathlib import Path

# Mirror Phase O1 C2 test pattern — add bridge/ to sys.path so
# `from vapi_bridge.X` resolves regardless of pytest invocation cwd.
_BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

import pytest

from vapi_bridge.operator_initiative_advancement import (
    AgentAdvancementReadiness,
    FleetAdvancementSummary,
    FleetReadinessRootResult,
    FRR_DOMAIN_TAG,
    INITIATIVE_AGENTS,
    PHASE_CODE_O1_SHADOW,
    PHASE_CODE_O2_SUGGEST,
    PHASE_CODE_UNKNOWN,
    compute_fleet_readiness_root,
    evaluate_frr_sync,
)


# Q9-frozen agentIds (from CLAUDE.md / Sessions 1+2+3)
SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"
GUARDIAN_ID = "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1"
CURATOR_ID = "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"


def _make_cfg(
    sentry: str = SENTRY_ID,
    guardian: str = GUARDIAN_ID,
    curator: str = CURATOR_ID,
):
    cfg = types.SimpleNamespace()
    cfg.operator_agent_anchor_sentry_id = sentry
    cfg.operator_agent_guardian_id = guardian
    cfg.operator_agent_curator_id = curator
    return cfg


def _make_per_agent(phase_per_agent: dict[str, str]) -> tuple:
    """Build per_agent tuple with given phase string per canonical name."""
    return tuple(
        AgentAdvancementReadiness(
            agent_id=agent_id,
            current_phase=phase_per_agent.get(agent_id, "O1_SHADOW"),
            shadow_age_hours=0.0,
            cedar_eval_count=0,
            bundle_hash_drift_count_30d=0,
            scope_hash_governance_drift_count_30d=0,
            o2_ready=False,
            o2_blockers=tuple(),
            o3_ready=False,
            o3_blockers=tuple(),
        )
        for agent_id in INITIATIVE_AGENTS
    )


def _make_summary(per_agent: tuple) -> FleetAdvancementSummary:
    return FleetAdvancementSummary(
        timestamp=time.time(),
        fleet_size=len(per_agent),
        per_agent=per_agent,
    )


# ───────────────────────────────────────────────────────────────────────
# T-O1-FRR-1: determinism
# ───────────────────────────────────────────────────────────────────────


def test_T_O1_FRR_1_compute_is_deterministic():
    """Same per_agent + same ts_ns → same FRR hex across invocations."""
    cfg = _make_cfg()
    per_agent = _make_per_agent({a: "O1_SHADOW" for a in INITIATIVE_AGENTS})
    summary = _make_summary(per_agent)
    ts = 1_777_777_777_000_000_000

    r1 = compute_fleet_readiness_root(summary, cfg=cfg, ts_ns=ts)
    r2 = compute_fleet_readiness_root(summary, cfg=cfg, ts_ns=ts)
    r3 = compute_fleet_readiness_root(summary, cfg=cfg, ts_ns=ts)

    assert r1.error is None
    assert r1.frr_hex == r2.frr_hex == r3.frr_hex
    assert len(r1.frr_hex) == 64  # SHA-256 → 32B → 64 hex chars
    assert r1.ts_ns == ts


# ───────────────────────────────────────────────────────────────────────
# T-O1-FRR-2: sort canonicalization
# ───────────────────────────────────────────────────────────────────────


def test_T_O1_FRR_2_sort_canonicalization():
    """FRR is invariant to per_agent input order — sort by agent_id bytes."""
    cfg = _make_cfg()
    ts = 1_777_777_777_000_000_000

    # Build two summaries with the SAME per_agent content but DIFFERENT
    # input orders.  FRR must match.
    base = _make_per_agent({a: "O2_SUGGEST" for a in INITIATIVE_AGENTS})
    forward = base
    backward = tuple(reversed(base))
    middle_first = (base[1], base[2], base[0])

    s_fwd = _make_summary(forward)
    s_bwd = _make_summary(backward)
    s_mid = _make_summary(middle_first)

    r_fwd = compute_fleet_readiness_root(s_fwd, cfg=cfg, ts_ns=ts)
    r_bwd = compute_fleet_readiness_root(s_bwd, cfg=cfg, ts_ns=ts)
    r_mid = compute_fleet_readiness_root(s_mid, cfg=cfg, ts_ns=ts)

    assert r_fwd.frr_hex == r_bwd.frr_hex == r_mid.frr_hex


# ───────────────────────────────────────────────────────────────────────
# T-O1-FRR-3: phase code sensitivity
# ───────────────────────────────────────────────────────────────────────


def test_T_O1_FRR_3_phase_code_change_flips_frr():
    """Changing one agent's phase code produces a different FRR."""
    cfg = _make_cfg()
    ts = 1_777_777_777_000_000_000

    all_o1 = _make_per_agent({a: "O1_SHADOW" for a in INITIATIVE_AGENTS})
    one_o2 = _make_per_agent(
        {"anchor_sentry": "O2_SUGGEST", "guardian": "O1_SHADOW", "curator": "O1_SHADOW"}
    )
    all_o2 = _make_per_agent({a: "O2_SUGGEST" for a in INITIATIVE_AGENTS})

    r_all_o1 = compute_fleet_readiness_root(_make_summary(all_o1), cfg=cfg, ts_ns=ts)
    r_one_o2 = compute_fleet_readiness_root(_make_summary(one_o2), cfg=cfg, ts_ns=ts)
    r_all_o2 = compute_fleet_readiness_root(_make_summary(all_o2), cfg=cfg, ts_ns=ts)

    assert r_all_o1.frr_hex != r_one_o2.frr_hex
    assert r_one_o2.frr_hex != r_all_o2.frr_hex
    assert r_all_o1.frr_hex != r_all_o2.frr_hex


# ───────────────────────────────────────────────────────────────────────
# T-O1-FRR-4: domain tag in pre-image (manual recompute proof)
# ───────────────────────────────────────────────────────────────────────


def test_T_O1_FRR_4_domain_tag_in_preimage():
    """Manually reconstruct the pre-image and verify FRR matches.

    This locks the byte-order invariant INV-FRR-003.  If a future
    refactor changes byte order without bumping to FRR v2, this test
    fails loudly.
    """
    cfg = _make_cfg()
    ts = 1_777_777_777_000_000_000
    per_agent = _make_per_agent({a: "O2_SUGGEST" for a in INITIATIVE_AGENTS})
    summary = _make_summary(per_agent)

    r = compute_fleet_readiness_root(summary, cfg=cfg, ts_ns=ts)
    assert r.error is None

    # Manual pre-image recompute
    sentry_b = bytes.fromhex(SENTRY_ID[2:])
    guardian_b = bytes.fromhex(GUARDIAN_ID[2:])
    curator_b = bytes.fromhex(CURATOR_ID[2:])
    sorted_ids = sorted([sentry_b, guardian_b, curator_b])

    pre = bytearray(FRR_DOMAIN_TAG)
    for id_b in sorted_ids:
        pre.extend(id_b)
        pre.append(PHASE_CODE_O2_SUGGEST)
    pre.extend(int(ts).to_bytes(8, "big"))

    expected = hashlib.sha256(bytes(pre)).hexdigest()
    assert r.frr_hex == expected, (
        f"FRR pre-image byte-order broken!\n"
        f"  computed: {r.frr_hex}\n"
        f"  expected: {expected}"
    )

    # Verify domain tag is exactly 11 bytes (b"VAPI-FRR-v1")
    assert FRR_DOMAIN_TAG == b"VAPI-FRR-v1"
    assert len(FRR_DOMAIN_TAG) == 11


# ───────────────────────────────────────────────────────────────────────
# T-O1-FRR-5: evaluate_frr_sync fail-open
# ───────────────────────────────────────────────────────────────────────


def test_T_O1_FRR_5_evaluate_frr_sync_fail_open():
    """If the underlying evaluator raises, evaluate_frr_sync returns
    a (summary, frr) pair with error fields populated — never raises."""

    class _BrokenStore:
        """Store stub that raises on every call."""

        def get_latest_operator_agent_activation(self, agent_id):
            raise RuntimeError(f"injected_failure for {agent_id}")

        def get_first_operator_agent_activation(self, agent_id):
            raise RuntimeError(f"injected_failure for {agent_id}")

        def count_cedar_shadow_evaluations(self, agent_id):
            raise RuntimeError("injected_failure")

        def count_operator_agent_drift_findings(self, **kw):
            raise RuntimeError("injected_failure")

    cfg = _make_cfg()
    store = _BrokenStore()

    # Must not raise; must return tuple
    summary, frr = evaluate_frr_sync(cfg=cfg, store=store)
    assert isinstance(summary, FleetAdvancementSummary)
    assert isinstance(frr, FleetReadinessRootResult)

    # Per-agent rows have error fields populated (per
    # INV-INITIATIVE-ADVANCEMENT-002 — partial-result rows for failed agents).
    for a in summary.per_agent:
        assert a.error is not None
        assert "injected_failure" in a.error

    # FRR computation itself succeeds (fail-open) but the per_agent
    # phase strings are "UNKNOWN" → phase_code=PHASE_CODE_UNKNOWN.
    # FRR digest is still deterministic.
    assert len(frr.frr_hex) == 64
    assert frr.error is None  # FRR compute didn't fail; only the summary did


# ───────────────────────────────────────────────────────────────────────
# T-O1-FRR-6: advancement_log round-trip preserves frr_hex
# ───────────────────────────────────────────────────────────────────────


def test_T_O1_FRR_6_advancement_log_roundtrip():
    """insert_operator_initiative_advancement_log →
    get_latest_operator_initiative_advancement preserves frr_hex.

    Uses tempfile.mkdtemp (NOT TemporaryDirectory) per CLAUDE.md
    Windows gotcha: WAL files hold file locks past Store.__del__,
    so context-manager cleanup hits PermissionError on Windows.
    """
    import shutil
    from vapi_bridge.store import Store

    td = tempfile.mkdtemp()
    try:
        db_path = str(Path(td) / "test_phase_o1_frr.db")
        store = Store(db_path)

        # Insert a row with a known frr_hex
        sample_frr_hex = "a" * 64
        sample_ts = time.time()
        sample_frr_ts_ns = 1_777_777_777_000_000_000
        per_agent_json = '[{"agent_id":"anchor_sentry","current_phase":"O2_SUGGEST"}]'

        row_id = store.insert_operator_initiative_advancement_log(
            timestamp=sample_ts,
            fleet_phase_aligned=True,
            fleet_at_o1_count=0,
            fleet_at_o2_ready_count=3,
            fleet_at_o3_ready_count=0,
            next_alignment_target="O3_ACT",
            per_agent_json=per_agent_json,
            frr_hex=sample_frr_hex,
            frr_ts_ns=sample_frr_ts_ns,
            error=None,
        )
        assert row_id > 0

        # Read it back
        latest = store.get_latest_operator_initiative_advancement()
        assert latest is not None
        assert latest["frr_hex"] == sample_frr_hex
        assert int(latest["frr_ts_ns"]) == sample_frr_ts_ns
        assert int(latest["fleet_phase_aligned"]) == 1
        assert latest["next_alignment_target"] == "O3_ACT"
        assert latest["per_agent_json"] == per_agent_json

        # History helper returns rows in DESC order
        history = store.get_operator_initiative_advancement_history(limit=10)
        assert len(history) == 1
        assert history[0]["frr_hex"] == sample_frr_hex
    finally:
        # Best-effort cleanup; Windows WAL locks may persist briefly
        try:
            shutil.rmtree(td, ignore_errors=True)
        except Exception:
            pass
