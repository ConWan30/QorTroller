"""Tests for scripts/g7_curator_review_readiness_audit.py.

Validates the G7 observability harness ships the right gate semantics:
NO_CURATOR_DRAFTS / BLOCKED / PASS / FAIL / FAIL_ZERO_TOLERANCE all
reachable; section-by-section field shape stable; CLI exit codes line
up with verdict.

Each test builds a fresh in-memory SQLite DB seeded with the minimum
operator_agent_drafts rows needed to exercise the gate path. No bridge
runtime required.
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "g7_curator_review_readiness_audit.py"

# Load the script as a module (it lives in scripts/ not a package).
_spec = importlib.util.spec_from_file_location(
    "g7_audit", SCRIPT_PATH
)
g7_audit = importlib.util.module_from_spec(_spec)  # type: ignore
_spec.loader.exec_module(g7_audit)  # type: ignore


CURATOR_Q9 = (
    "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"
)


def _seed_db_with_schema(db_path: Path) -> sqlite3.Connection:
    """Create a fresh DB with operator_agent_drafts schema (phase 1005)."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS operator_agent_drafts (
            id                              INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id                        TEXT    NOT NULL,
            action_category                 TEXT    NOT NULL,
            action_name                     TEXT    NOT NULL,
            draft_uri                       TEXT    NOT NULL,
            payload_hash                    TEXT    NOT NULL,
            payload_bytes                   INTEGER NOT NULL,
            kms_sig_present                 INTEGER NOT NULL DEFAULT 0,
            operator_decision               TEXT,
            operator_decision_at            REAL,
            operator_disagreement_reason    TEXT,
            created_at                      REAL    NOT NULL
        )
    """)
    conn.commit()
    return conn


def _insert_curator_draft(
    conn: sqlite3.Connection,
    *,
    agent_id: str = CURATOR_Q9,
    decision: str | None = None,
    decision_age_seconds: float = 60.0,
    created_age_seconds: float = 120.0,
    payload_hash: str = "",
) -> None:
    """Insert one Curator draft with optional operator decision."""
    now = time.time()
    if not payload_hash:
        # Use a per-call unique payload_hash to avoid the UNIQUE index.
        payload_hash = f"hash_{now}_{decision_age_seconds}_{id(conn)}_{created_age_seconds}"
    conn.execute(
        "INSERT INTO operator_agent_drafts ("
        "  agent_id, action_category, action_name, draft_uri, "
        "  payload_hash, payload_bytes, kms_sig_present, "
        "  operator_decision, operator_decision_at, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            agent_id,
            "skill",
            "marketplace-listing-review",
            f"draft://listing_reviews/{payload_hash[:16]}/verdict",
            payload_hash,
            128,
            0,
            decision,
            now - decision_age_seconds if decision else None,
            now - created_age_seconds,
        ),
    )
    conn.commit()


# ---- T-G7-1: No curator drafts -> NO_CURATOR_DRAFTS exit 3 -----------

def test_t_g7_1_no_curator_drafts_returns_exit_3():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "vapi_store.db"
        conn = _seed_db_with_schema(db)
        conn.close()

        report, exit_code = g7_audit.run_audit(db)

        assert exit_code == 3
        assert report["verdict"] == "NO_CURATOR_DRAFTS"
        assert report["section_1_curator_presence"]["curator_present"] is False


# ---- T-G7-2: <10 reviewed -> BLOCKED exit 1 --------------------------

def test_t_g7_2_insufficient_reviews_returns_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "vapi_store.db"
        conn = _seed_db_with_schema(db)
        # 5 reviewed drafts (all accept) — insufficient for the 10-row gate.
        for i in range(5):
            _insert_curator_draft(
                conn, decision="accept",
                decision_age_seconds=60 + i,
                payload_hash=f"hash_blocked_{i}",
            )
        conn.close()

        report, exit_code = g7_audit.run_audit(db)

        assert exit_code == 1
        assert report["final_verdict"] == "BLOCKED"
        s4 = report["section_4_gate_evaluation"]
        assert s4["n_reviewed_in_window"] == 5
        assert "insufficient_signal" in s4["reason"]


# ---- T-G7-3: 10 reviewed, 9 accept -> PASS exit 0 --------------------

def test_t_g7_3_nine_of_ten_accept_returns_pass():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "vapi_store.db"
        conn = _seed_db_with_schema(db)
        for i in range(9):
            _insert_curator_draft(
                conn, decision="accept",
                decision_age_seconds=60 + i,
                payload_hash=f"hash_accept_{i}",
            )
        _insert_curator_draft(
            conn, decision="reject",
            decision_age_seconds=70,
            payload_hash="hash_reject_one",
        )
        conn.close()

        report, exit_code = g7_audit.run_audit(db)

        assert exit_code == 0
        assert report["final_verdict"] == "PASS"
        s3 = report["section_3_last_n_breakdown"]
        assert s3["n_accept"] == 9
        assert s3["n_reject"] == 1


# ---- T-G7-4: 10 reviewed, 8 accept -> FAIL exit 2 --------------------

def test_t_g7_4_eight_of_ten_accept_returns_fail():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "vapi_store.db"
        conn = _seed_db_with_schema(db)
        for i in range(8):
            _insert_curator_draft(
                conn, decision="accept",
                decision_age_seconds=60 + i,
                payload_hash=f"hash_a_{i}",
            )
        for i in range(2):
            _insert_curator_draft(
                conn, decision="reject",
                decision_age_seconds=70 + i,
                payload_hash=f"hash_r_{i}",
            )
        conn.close()

        report, exit_code = g7_audit.run_audit(db)

        assert exit_code == 2
        assert report["final_verdict"] == "FAIL"


# ---- T-G7-5: Any overturn_curator -> ZERO TOLERANCE FAIL exit 2 -------

def test_t_g7_5_overturn_curator_triggers_zero_tolerance_fail():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "vapi_store.db"
        conn = _seed_db_with_schema(db)
        # 10 reviewed with 9 accept + 1 overturn_curator. Section 4 alone
        # would NOT see this as PASS (overturn_curator is not 'accept'),
        # but section 5 ZERO TOLERANCE forces final FAIL regardless.
        for i in range(9):
            _insert_curator_draft(
                conn, decision="accept",
                decision_age_seconds=60 + i,
                payload_hash=f"hash_a_{i}",
            )
        _insert_curator_draft(
            conn, decision="overturn_curator",
            decision_age_seconds=70,
            payload_hash="hash_oc_one",
        )
        conn.close()

        report, exit_code = g7_audit.run_audit(db)

        assert exit_code == 2
        assert report["final_verdict"] == "FAIL_ZERO_TOLERANCE_VIOLATION"
        s5 = report["section_5_zero_tolerance_invariant"]
        assert s5["n_overturn_curator_in_window"] == 1
        assert s5["zero_tolerance_ok"] is False


# ---- T-G7-6: Canonical-name agent_id fallback (test-stub mode) -------

def test_t_g7_6_canonical_name_fallback_works():
    """When Curator has rows under 'curator' (test stub) not Q9 hex,
    section 1 resolves correctly and downstream sections still
    evaluate the gate."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "vapi_store.db"
        conn = _seed_db_with_schema(db)
        for i in range(10):
            _insert_curator_draft(
                conn,
                agent_id="curator",  # canonical name, not Q9 hex
                decision="accept",
                decision_age_seconds=60 + i,
                payload_hash=f"hash_canon_{i}",
            )
        conn.close()

        report, exit_code = g7_audit.run_audit(db)

        assert exit_code == 0
        assert report["section_1_curator_presence"]["curator_agent_id"] == "curator"
        assert report["section_1_curator_presence"]["is_q9_hex"] is False
        assert report["final_verdict"] == "PASS"


# ---- T-G7-7: 7-day window cutoff excludes stale rows ------------------

def test_t_g7_7_window_cutoff_excludes_stale_rows():
    """Drafts older than 7 days don't count against the window total
    but DO still exist in total_drafts_ever (section 1)."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "vapi_store.db"
        conn = _seed_db_with_schema(db)
        # 15 stale drafts (10 days old) — should NOT count in section 2.
        for i in range(15):
            _insert_curator_draft(
                conn, decision="accept",
                decision_age_seconds=10 * 86400 + i,
                created_age_seconds=10 * 86400 + i,
                payload_hash=f"hash_stale_{i}",
            )
        # 3 fresh drafts — should count in section 2 but BLOCKED in 4.
        for i in range(3):
            _insert_curator_draft(
                conn, decision="accept",
                decision_age_seconds=60 + i,
                created_age_seconds=120 + i,
                payload_hash=f"hash_fresh_{i}",
            )
        conn.close()

        report, exit_code = g7_audit.run_audit(db)

        # Section 1 should see all 18 drafts.
        s1 = report["section_1_curator_presence"]
        assert s1["total_drafts_ever"] == 18

        # Section 2 should see only the 3 fresh ones.
        s2 = report["section_2_window_counts"]
        assert s2["total_in_window"] == 3
        assert s2["reviewed_in_window"] == 3

        # Section 4 -> BLOCKED (3 < 10).
        assert report["final_verdict"] == "BLOCKED"
        assert exit_code == 1


# ---- T-G7-8: JSON-mode output is valid JSON ---------------------------

def test_t_g7_8_json_mode_produces_valid_json(capsys):
    """--json flag should emit machine-readable JSON, not human report."""
    import json
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "vapi_store.db"
        conn = _seed_db_with_schema(db)
        for i in range(10):
            _insert_curator_draft(
                conn, decision="accept",
                decision_age_seconds=60 + i,
                payload_hash=f"hash_jm_{i}",
            )
        conn.close()

        exit_code = g7_audit.main([
            "--db", str(db),
            "--json",
        ])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)

        assert exit_code == 0
        assert parsed["final_verdict"] == "PASS"
        assert "section_4_gate_evaluation" in parsed


# ---- T-G7-9: Missing DB returns exit 4 (config error) -----------------

def test_t_g7_9_missing_db_returns_exit_4():
    nonexistent = Path("/this/path/should/never/exist/vapi_store.db")
    report, exit_code = g7_audit.run_audit(nonexistent)

    assert exit_code == 4
    assert "error" in report


# ---- T-G7-10: FROZEN gate constants pinned ----------------------------

def test_t_g7_10_gate_constants_frozen():
    """The G7 gate constants are FROZEN per VBDIP-0002 §B.8.
    Catch accidental relaxation at PR time."""
    assert g7_audit.G7_WINDOW_DAYS == 7
    assert g7_audit.G7_LAST_N == 10
    assert g7_audit.G7_MIN_ACCEPT == 9
    assert g7_audit.G7_FALSE_POSITIVE_RATE_MAX == 0.0
