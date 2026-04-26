"""Phase 238 Decision A — FSCA findings wired into autoresearch cycle.

Test runner per design review §A.D5. Three sub-tests cover the wiring:

  T238-FSCA-1: load_fsca_findings() fail-open
  T238-FSCA-2: load_fsca_findings() severity + age filtering
  T238-FSCA-3: format_cycle_prompt() renders FSCA section correctly
              (both with N≥1 finding and with empty list)

These tests are deterministic and don't require a running bridge.  They
seed a temporary SQLite DB matching `fleet_coherence_log` schema (cited
from store.py:2281–2301) and verify the loader's contract.
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# Make the project root importable regardless of test invocation cwd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Schema verbatim from bridge/vapi_bridge/store.py:2281–2301.
_FSCA_SCHEMA = """
CREATE TABLE fleet_coherence_log (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    coherence_id              TEXT    NOT NULL UNIQUE,
    failure_mode              TEXT    NOT NULL,
    rule_name                 TEXT    NOT NULL,
    agents_involved           TEXT    NOT NULL,
    severity                  TEXT    NOT NULL,
    explanation               TEXT    NOT NULL,
    resolution                TEXT    NOT NULL,
    evidence_json             TEXT    NOT NULL DEFAULT '[]',
    promoted_to_wif           INTEGER NOT NULL DEFAULT 0,
    wif_entry_id              TEXT,
    wiki_contradict_written   INTEGER NOT NULL DEFAULT 0,
    alert_published           INTEGER NOT NULL DEFAULT 0,
    resolved                  INTEGER NOT NULL DEFAULT 0,
    resolved_at               TEXT,
    resolved_by               TEXT,
    phase_detected            INTEGER NOT NULL DEFAULT 193,
    ts_ns                     INTEGER NOT NULL DEFAULT 0,
    created_at                TEXT    DEFAULT (datetime('now'))
)
"""


def _make_seeded_db(tmp_path: Path) -> Path:
    """Create a temp SQLite DB seeded with one CRITICAL, one HIGH, one
    MEDIUM, one resolved, and one stale (>24h) finding so filters can be
    exercised."""
    db = tmp_path / "test_fsca.db"
    conn = sqlite3.connect(str(db))
    conn.execute(_FSCA_SCHEMA)
    rows = [
        # (coherence_id, rule_name, severity, resolved, age_hours)
        ("coh_001", "CONSENT_REVOKED_BUT_DATA_FLOWING", "HIGH",     0, 1),
        ("coh_002", "RENEWAL_WITHOUT_ATTESTATION",      "CRITICAL", 0, 6),
        ("coh_003", "RATIO_VELOCITY_NEGATIVE",          "MEDIUM",   0, 2),    # filtered: severity
        ("coh_004", "TTL_COMMITTED_AT_MISMATCH",        "HIGH",     1, 3),    # filtered: resolved
        ("coh_005", "PERSONA_BREAK_ENROLLMENT",         "HIGH",     0, 30),   # filtered: stale
    ]
    for cid, rule, sev, resolved, age_h in rows:
        conn.execute(
            f"""
            INSERT INTO fleet_coherence_log
              (coherence_id, failure_mode, rule_name, agents_involved,
               severity, explanation, resolution, resolved, created_at)
            VALUES (?, 'CONTRADICTION', ?, '["bridge"]', ?, 'test explanation', 'test resolution',
                    ?, datetime('now', '-{age_h} hours'))
            """,
            (cid, rule, sev, resolved),
        )
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def seeded_bridge_db(tmp_path, monkeypatch):
    """Point vapi_autoresearch.BRIDGE_DB_PATH at a freshly seeded temp DB."""
    db = _make_seeded_db(tmp_path)
    import vapi_autoresearch
    monkeypatch.setattr(vapi_autoresearch, "BRIDGE_DB_PATH", db)
    return db


@pytest.fixture
def missing_bridge_db(tmp_path, monkeypatch):
    """Point at a path that does not exist → fail-open path."""
    db = tmp_path / "does_not_exist.db"
    import vapi_autoresearch
    monkeypatch.setattr(vapi_autoresearch, "BRIDGE_DB_PATH", db)
    return db


# ---------------------------------------------------------------------------
# T238-FSCA-1 — fail-open
# ---------------------------------------------------------------------------

def test_t238_fsca_1_load_fail_open_when_db_missing(missing_bridge_db):
    """load_fsca_findings returns [] when bridge DB does not exist."""
    from vapi_autoresearch import load_fsca_findings
    result = load_fsca_findings()
    assert result == [], (
        "Expected fail-open empty list when BRIDGE_DB_PATH does not exist; "
        f"got {result!r}"
    )


def test_t238_fsca_1b_load_fail_open_when_table_missing(tmp_path, monkeypatch):
    """load_fsca_findings returns [] when DB exists but table does not.

    This is the currently-observed live state — bridge/vapi_store.db exists
    in dev but fleet_coherence_log is not yet created until FSCA agent runs.
    """
    db = tmp_path / "empty.db"
    sqlite3.connect(str(db)).close()  # empty DB, no tables
    import vapi_autoresearch
    monkeypatch.setattr(vapi_autoresearch, "BRIDGE_DB_PATH", db)
    from vapi_autoresearch import load_fsca_findings
    result = load_fsca_findings()
    assert result == [], (
        "Expected fail-open empty list when fleet_coherence_log table does "
        f"not exist; got {result!r}"
    )


# ---------------------------------------------------------------------------
# T238-FSCA-2 — severity + age + resolved filtering
# ---------------------------------------------------------------------------

def test_t238_fsca_2_filters_correctly(seeded_bridge_db):
    """Only HIGH+CRITICAL, unresolved, within last 24h findings returned."""
    from vapi_autoresearch import load_fsca_findings
    result = load_fsca_findings()

    # Expected: coh_001 (HIGH/active/1h) + coh_002 (CRITICAL/active/6h)
    # Excluded: coh_003 (MEDIUM), coh_004 (resolved=1), coh_005 (>24h stale)
    rule_names = {r["rule_name"] for r in result}
    assert "CONSENT_REVOKED_BUT_DATA_FLOWING" in rule_names, "HIGH active should be included"
    assert "RENEWAL_WITHOUT_ATTESTATION"      in rule_names, "CRITICAL active should be included"
    assert "RATIO_VELOCITY_NEGATIVE"      not in rule_names, "MEDIUM should be filtered out"
    assert "TTL_COMMITTED_AT_MISMATCH"    not in rule_names, "resolved=1 should be filtered out"
    assert "PERSONA_BREAK_ENROLLMENT"     not in rule_names, "stale (>24h) should be filtered out"
    assert len(result) == 2, f"Expected 2 findings, got {len(result)}: {rule_names}"

    # Verify CRITICAL is sorted ahead of HIGH
    assert result[0]["severity"] == "CRITICAL", (
        f"CRITICAL should sort ahead of HIGH; got {[r['severity'] for r in result]}"
    )


def test_t238_fsca_2b_severity_min_critical_only(seeded_bridge_db):
    """severity_min='CRITICAL' returns only CRITICAL findings."""
    from vapi_autoresearch import load_fsca_findings
    result = load_fsca_findings(severity_min="CRITICAL")
    rule_names = {r["rule_name"] for r in result}
    assert rule_names == {"RENEWAL_WITHOUT_ATTESTATION"}, (
        f"severity_min='CRITICAL' should return only CRITICAL; got {rule_names}"
    )


# ---------------------------------------------------------------------------
# T238-FSCA-3 — format_cycle_prompt renders FSCA section
# ---------------------------------------------------------------------------

def test_t238_fsca_3_renders_with_findings():
    """format_cycle_prompt embeds the FSCA section with each finding."""
    from vapi_autoresearch import format_cycle_prompt
    findings = [
        {
            "rule_name":      "CONSENT_REVOKED_BUT_DATA_FLOWING",
            "severity":       "HIGH",
            "agents_involved": '["bridge", "BiometricPrivacyComplianceAgent"]',
            "explanation":    "Device has revoked consent but PoAC records appear post-revocation.",
            "created_at":     "2026-04-26 12:00:00",
        }
    ]
    prompt = format_cycle_prompt(
        current_skill="(skill stub)",
        program="(program stub)",
        log=[],
        priority="fleet_coherence_critical",
        cycle_num=1,
        fsca_findings=findings,
    )
    assert "ACTIVE FSCA CONTRADICTIONS" in prompt, "Section header missing"
    assert "[HIGH] CONSENT_REVOKED_BUT_DATA_FLOWING" in prompt, "Finding bullet missing"
    assert "Device has revoked consent" in prompt, "Explanation truncation should preserve start"


def test_t238_fsca_3b_renders_empty_state():
    """format_cycle_prompt renders '(none active)' when fsca_findings is empty."""
    from vapi_autoresearch import format_cycle_prompt
    prompt = format_cycle_prompt(
        current_skill="(skill stub)",
        program="(program stub)",
        log=[],
        priority="separation_ratio_pathways",
        cycle_num=1,
        fsca_findings=[],
    )
    assert "ACTIVE FSCA CONTRADICTIONS" in prompt
    assert "(none active in last 24h at severity ≥ HIGH)" in prompt, (
        "Empty-state placeholder must appear so prompt structure is uniform across cycles"
    )


def test_t238_fsca_3c_renders_with_default_none():
    """format_cycle_prompt accepts None (backward-compat) as fsca_findings."""
    from vapi_autoresearch import format_cycle_prompt
    prompt = format_cycle_prompt(
        current_skill="(skill stub)",
        program="(program stub)",
        log=[],
        priority="separation_ratio_pathways",
        cycle_num=1,
        fsca_findings=None,
    )
    # Default None should render as empty section, not crash
    assert "ACTIVE FSCA CONTRADICTIONS" in prompt
    assert "(none active in last 24h at severity ≥ HIGH)" in prompt
