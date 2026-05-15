"""Phase O5-MYTHOS-MINIMAL M.1 tests — mythos_cadence_engine + store helpers.

T-MYTHOS-M1-1  Both store tables (mythos_finding_log + mythos_cadence_log) exist after Store init
T-MYTHOS-M1-2  insert_mythos_finding writes row; idempotent on duplicate coherence_id
T-MYTHOS-M1-3  INV-MYTHOS-FROZEN-PROTECTION: frozen_region=True forces fix_authority_tier=3
T-MYTHOS-M1-4  insert_mythos_cadence_run writes row
T-MYTHOS-M1-5  get_mythos_findings filters by variant / severity / unresolved
T-MYTHOS-M1-6  get_mythos_cadence_status aggregates per-variant
T-MYTHOS-M1-7  run_mythos_cadence_loop returns immediately when mythos_cadence_enabled=False
T-MYTHOS-M1-8  cadence loop catches variant exceptions and continues; findings persist
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store(tmpdir):
    from vapi_bridge.store import Store
    return Store(db_path=os.path.join(tmpdir, "test_mythos_m1.db"))


def _make_cfg(enabled: bool, interval_s: int = 86400):
    cfg = MagicMock()
    cfg.mythos_cadence_enabled = enabled
    cfg.mythos_cadence_interval_s = interval_s
    return cfg


def _finding(variant="frozen", coherence_id="mythos_frozen_test001", severity="HIGH", **kw):
    from vapi_bridge.mythos_cadence_engine import MythosFindingResult
    defaults = dict(
        variant=variant,
        severity=severity,
        description="test finding",
        recommended_fix="test fix",
        coherence_id=coherence_id,
        evidence_sources=["test/corpus.md"],
    )
    defaults.update(kw)
    return MythosFindingResult(**defaults)


# ----- T-MYTHOS-M1-1 ------------------------------------------------------

def test_t_mythos_m1_1_tables_created_after_store_init():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        import sqlite3
        conn = sqlite3.connect(store._db_path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "mythos_finding_log" in tables, "mythos_finding_log table not created"
        assert "mythos_cadence_log" in tables, "mythos_cadence_log table not created"


# ----- T-MYTHOS-M1-2 ------------------------------------------------------

def test_t_mythos_m1_2_insert_mythos_finding_idempotent_on_coherence_id():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        # First insert returns a positive row id.
        rid_1 = store.insert_mythos_finding(
            variant="frozen",
            severity="HIGH",
            coherence_id="mythos_frozen_abc123",
            description="OFF_INF_CODE drift",
            recommended_fix="set OFF_INF_CODE = 128",
            file_path="scripts/w3bstream/validate_poac_record.ts",
            line_number=109,
            frozen_region=False,
            fix_authority_tier=2,
            evidence_sources=["bridge/vapi_bridge/codec.py", "contracts/circuits/PitlSessionProof.circom"],
        )
        assert rid_1 > 0
        # Second insert with same coherence_id returns 0 (UNIQUE collision; INSERT OR IGNORE).
        rid_2 = store.insert_mythos_finding(
            variant="frozen",
            severity="HIGH",
            coherence_id="mythos_frozen_abc123",
            description="different description but same coherence_id",
            recommended_fix="different fix",
        )
        assert rid_2 == 0, "idempotent insert MUST return 0 on duplicate coherence_id"
        # Only one row exists in the table.
        rows = store.get_mythos_findings(variant="frozen", limit=10)
        assert len(rows) == 1
        assert rows[0]["coherence_id"] == "mythos_frozen_abc123"
        # The evidence_sources_json was stored as canonical sorted JSON.
        ev = json.loads(rows[0]["evidence_sources_json"])
        assert "bridge/vapi_bridge/codec.py" in ev


# ----- T-MYTHOS-M1-3  INV-MYTHOS-FROZEN-PROTECTION-001 --------------------

def test_t_mythos_m1_3_frozen_region_forces_tier_3():
    """A variant CAN suggest tier-1 autofix on a frozen-region finding;
    the store layer MUST override it to tier-3 (read-only) so Mythos
    can NEVER auto-fix FROZEN material. INV-MYTHOS-FROZEN-PROTECTION-001."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        # Variant claims tier=1 (autofix-safe) but frozen_region=True.
        rid = store.insert_mythos_finding(
            variant="frozen",
            severity="CRITICAL",
            coherence_id="mythos_frozen_protection_test",
            description="hypothetical drift in PoAC wire format",
            recommended_fix="DO NOT auto-apply — see governance ceremony",
            frozen_region=True,
            fix_authority_tier=1,  # variant requests autofix authority
        )
        assert rid > 0
        rows = store.get_mythos_findings(variant="frozen", limit=1)
        assert len(rows) == 1
        # Store MUST have forced tier to 3 (read-only) regardless of input.
        assert int(rows[0]["fix_authority_tier"]) == 3, (
            "INV-MYTHOS-FROZEN-PROTECTION-001 violated: frozen_region=True "
            "finding stored with fix_authority_tier != 3"
        )
        assert int(rows[0]["frozen_region"]) == 1


# ----- T-MYTHOS-M1-4 ------------------------------------------------------

def test_t_mythos_m1_4_insert_mythos_cadence_run():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        rid = store.insert_mythos_cadence_run(
            variant="frozen",
            cadence="daily",
            findings_count=3,
            duration_ms=1542,
            triggered_by="schedule",
            error=None,
        )
        assert rid > 0
        status = store.get_mythos_cadence_status()
        assert "frozen" in status["variants"]
        assert status["variants"]["frozen"]["n_runs"] == 1
        assert status["variants"]["frozen"]["total_findings"] == 3
        assert status["total_runs"] == 1
        assert status["total_findings"] == 3


# ----- T-MYTHOS-M1-5 ------------------------------------------------------

def test_t_mythos_m1_5_get_mythos_findings_filters():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        # Insert a mix.
        store.insert_mythos_finding(
            variant="frozen", severity="CRITICAL", coherence_id="m_f_001",
            description="d1", recommended_fix="f1",
        )
        store.insert_mythos_finding(
            variant="frozen", severity="LOW", coherence_id="m_f_002",
            description="d2", recommended_fix="f2",
        )
        store.insert_mythos_finding(
            variant="stability", severity="MEDIUM", coherence_id="m_s_001",
            description="d3", recommended_fix="f3",
        )
        # Filter by variant
        rows = store.get_mythos_findings(variant="frozen")
        assert len(rows) == 2
        assert {r["coherence_id"] for r in rows} == {"m_f_001", "m_f_002"}
        # Filter by severity
        rows = store.get_mythos_findings(severity="CRITICAL")
        assert len(rows) == 1
        assert rows[0]["coherence_id"] == "m_f_001"
        # Filter unresolved_only — all 3 unresolved
        rows = store.get_mythos_findings(unresolved_only=True)
        assert len(rows) == 3


# ----- T-MYTHOS-M1-6 ------------------------------------------------------

def test_t_mythos_m1_6_get_mythos_cadence_status_aggregates_per_variant():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        # frozen runs twice with 2 + 3 findings
        store.insert_mythos_cadence_run(variant="frozen", cadence="daily", findings_count=2, duration_ms=100)
        store.insert_mythos_cadence_run(variant="frozen", cadence="daily", findings_count=3, duration_ms=120)
        # stability runs once with 1 finding
        store.insert_mythos_cadence_run(variant="stability", cadence="daily", findings_count=1, duration_ms=200)
        status = store.get_mythos_cadence_status()
        assert status["variants"]["frozen"]["n_runs"] == 2
        assert status["variants"]["frozen"]["total_findings"] == 5
        assert status["variants"]["stability"]["n_runs"] == 1
        assert status["variants"]["stability"]["total_findings"] == 1
        assert status["total_runs"] == 3
        assert status["total_findings"] == 6


# ----- T-MYTHOS-M1-7 ------------------------------------------------------

def test_t_mythos_m1_7_cadence_loop_optout_returns_immediately():
    """When mythos_cadence_enabled=False, run_mythos_cadence_loop returns
    silently without doing anything (does NOT block, does NOT raise)."""
    from vapi_bridge.mythos_cadence_engine import run_mythos_cadence_loop
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        cfg = _make_cfg(enabled=False)

        async def _smoke():
            # Should return well under the cadence interval (no sleep on opt-out).
            await asyncio.wait_for(
                run_mythos_cadence_loop(cfg=cfg, store=store, get_pending_variants=None),
                timeout=1.0,
            )

        asyncio.run(_smoke())
        # No cadence rows recorded.
        status = store.get_mythos_cadence_status()
        assert status["total_runs"] == 0


# ----- T-MYTHOS-M1-8 ------------------------------------------------------

def test_t_mythos_m1_8_cadence_loop_catches_variant_exceptions():
    """When a variant raises, the loop records the cadence run with
    error=... and continues. Other variants in the same cycle still run.
    Their findings persist."""
    from vapi_bridge.mythos_cadence_engine import run_mythos_cadence_loop, MythosFindingResult
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        # interval_s = 0.05 so the loop wakes fast; we cancel after one cycle
        cfg = _make_cfg(enabled=True, interval_s=0.05)

        async def bad_variant():
            raise RuntimeError("simulated variant failure")

        async def good_variant():
            return [MythosFindingResult(
                variant="stability",
                severity="MEDIUM",
                description="urlopen timeout missing",
                recommended_fix="add timeout=cfg.X",
                coherence_id="mythos_stability_good_001",
            )]

        def _pending():
            return [("frozen", bad_variant), ("stability", good_variant)]

        async def _run_one_cycle():
            task = asyncio.create_task(
                run_mythos_cadence_loop(cfg=cfg, store=store, get_pending_variants=_pending)
            )
            # Give the loop time to run one cycle (~50ms) then cancel.
            await asyncio.sleep(0.2)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(_run_one_cycle())
        # Two cadence rows should have been recorded — one per variant.
        status = store.get_mythos_cadence_status()
        assert "frozen" in status["variants"], "bad variant cadence row missing"
        assert "stability" in status["variants"], "good variant cadence row missing"
        # bad variant: error column populated, findings_count=0
        # good variant: findings_count=1
        good_rows = store.get_mythos_findings(variant="stability")
        assert len(good_rows) >= 1, "good variant finding did not persist"
        assert good_rows[0]["coherence_id"] == "mythos_stability_good_001"
