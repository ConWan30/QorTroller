"""HWFL-1 Cycle 3 — Sensor B v0.1 watch tests. All deterministic via fixture
injection — the module is pure-function and no test touches the network."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from bridge.vapi_bridge.sensor_b_supply_watch import (
    FetchKind,
    FetchResult,
    WatchState,
    _CANONICAL_SOURCES,
    assemble_watch_report,
    canonical_source_count,
)


def test_t_sensor_b_1_canonical_source_count_is_7():
    """D-HWFL-11 confirmed 7-source v0.1 list."""
    assert canonical_source_count() == 7


def test_t_sensor_b_2_one_structured_six_manual():
    """S1 IIP-64 PR is the only STRUCTURED source in v0.1; the other 6 are MANUAL_NARRATIVE."""
    structured = [s for s in _CANONICAL_SOURCES if s.fetch_kind == FetchKind.STRUCTURED]
    manual = [s for s in _CANONICAL_SOURCES if s.fetch_kind == FetchKind.MANUAL_NARRATIVE]
    assert len(structured) == 1
    assert structured[0].topic_id == "S1.iip64-pr72"
    assert len(manual) == 6


def test_t_sensor_b_3_no_fetched_data_yields_all_pending():
    """Empty fetched dict => every source lands as PENDING-OPERATOR-NOTE."""
    report = assemble_watch_report(cycle=99)
    assert len(report.lines) == 7
    for line in report.lines:
        assert line.state == WatchState.PENDING_OPERATOR_NOTE


def test_t_sensor_b_4_structured_fresh_stays_fresh():
    """STRUCTURED source with recent timestamp + summary => FRESH (not UNVERIFIED-EXTERNAL)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fetched = {
        "S1.iip64-pr72": FetchResult(
            topic_id="S1.iip64-pr72",
            summary="PR #72 OPEN; last updated 2026-05-23",
            fetched_at=now,
        )
    }
    report = assemble_watch_report(cycle=3, fetched=fetched)
    s1 = next(l for l in report.lines if l.source.topic_id == "S1.iip64-pr72")
    assert s1.state == WatchState.FRESH


def test_t_sensor_b_5_manual_narrative_fresh_demotes_to_unverified_external():
    """MANUAL_NARRATIVE never reaches FRESH — even fresh timestamps go to UNVERIFIED-EXTERNAL.
    The narrative IS external content; that's the discipline."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fetched = {
        "S2.atecc608a-lifecycle": FetchResult(
            topic_id="S2.atecc608a-lifecycle",
            summary="ATECC608A still in production per operator note",
            fetched_at=now,
        )
    }
    report = assemble_watch_report(cycle=3, fetched=fetched)
    s2 = next(l for l in report.lines if l.source.topic_id == "S2.atecc608a-lifecycle")
    assert s2.state == WatchState.UNVERIFIED_EXTERNAL


def test_t_sensor_b_6_stale_when_outside_freshness_window():
    """Fetched timestamp older than freshness_days => STALE."""
    stale_ts = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat(timespec="seconds")
    fetched = {
        "S1.iip64-pr72": FetchResult(
            topic_id="S1.iip64-pr72",
            summary="PR #72 OPEN",
            fetched_at=stale_ts,
        )
    }
    report = assemble_watch_report(cycle=3, fetched=fetched)
    s1 = next(l for l in report.lines if l.source.topic_id == "S1.iip64-pr72")
    assert s1.state == WatchState.STALE


def test_t_sensor_b_7_fetch_error_state():
    """Non-empty error => FETCH-ERROR, regardless of summary content."""
    fetched = {
        "S1.iip64-pr72": FetchResult(
            topic_id="S1.iip64-pr72",
            summary="attempted",
            error="gh exit-1",
        )
    }
    report = assemble_watch_report(cycle=3, fetched=fetched)
    s1 = next(l for l in report.lines if l.source.topic_id == "S1.iip64-pr72")
    assert s1.state == WatchState.FETCH_ERROR
    assert s1.error == "gh exit-1"


def test_t_sensor_b_8_markdown_renders_operator_action_box_and_honesty_rail():
    """OA-1..OA-4 + honesty rail render into every report AND
    (HWFL-1 Cycle 9 / F-CYCLE9-1 sanitization) the rendered markdown MUST
    NOT contain operator-private filename tokens. Positive content
    assertions verify the sanitized OA-1 text shape + Sensor B honesty rail."""
    report = assemble_watch_report(cycle=9)
    md = report.to_markdown()
    # Required structural markers (filename intentionally absent).
    for marker in ("OA-1", "OA-4", "UNVERIFIED-EXTERNAL", "Honesty rail"):
        assert marker in md, f"watch report missing marker {marker!r}"
    # F-CYCLE9-1 sanitization regression — no operator-private filename tokens.
    forbidden_tokens = ("qortroller_foundation_mfg_ca.json", "qortroller_foundation_mfg_ca")
    for tok in forbidden_tokens:
        assert tok not in md, (
            f"Sensor B watch markdown leaked operator-private token {tok!r} into "
            f"public artifact — violates F-CYCLE9-1 sanitization rail."
        )
    # Positive content for sanitized OA-1 (must match Sensor C exactly per cross-artifact consistency).
    assert "MFG Root CA canonical file" in md
    assert "docs/disaster-recovery-runbook.private.md" in md
    assert "F-DECON-3.2" in md


def test_t_sensor_b_9_markdown_escapes_external_pipe_and_html_in_summary():
    """Adversarial input check: external content with pipe-chars + HTML must not break the table or render active markup."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = "Title with | pipe and <script>alert(1)</script> tag"
    fetched = {
        "S1.iip64-pr72": FetchResult(
            topic_id="S1.iip64-pr72", summary=payload, fetched_at=now,
        )
    }
    report = assemble_watch_report(cycle=3, fetched=fetched)
    md = report.to_markdown()
    # Pipe escaped in the table cell (look for the escaped form)
    assert "\\|" in md
    # HTML escaped — never raw script tag in output
    assert "<script>" not in md
    assert "&lt;script&gt;" in md


def test_t_sensor_b_11_verified_external_happy_path_plus_stale_unified_window():
    """D-HWFL-18/19: all 3 verification preconditions present + fresh => VERIFIED-EXTERNAL.
    Same fields with aged-out verified_date => STALE, but verified_by/sources/verified_date
    are RETAINED on the WatchLine for detail rendering (D-HWFL-19 unified window)."""
    today = datetime.now(timezone.utc).date().isoformat()
    fetched_fresh = {
        "S2.atecc608a-lifecycle": FetchResult(
            topic_id="S2.atecc608a-lifecycle",
            summary="ATECC608A NRND since 2021-03",
            verified_by="operator",
            sources=["https://example.com/microchip", "DS40002239A"],
            verified_date=today,
        )
    }
    report = assemble_watch_report(cycle=99, fetched=fetched_fresh)
    s2 = next(l for l in report.lines if l.source.topic_id == "S2.atecc608a-lifecycle")
    assert s2.state == WatchState.VERIFIED_EXTERNAL
    assert s2.verified_by == "operator"
    assert s2.sources == ["https://example.com/microchip", "DS40002239A"]
    assert s2.verified_date == today
    assert s2.verification_warning == ""

    # Aged-out verified_date => STALE, fields retained (S2 freshness_days=30).
    stale_date = (datetime.now(timezone.utc).date() - timedelta(days=120)).isoformat()
    fetched_stale = {
        "S2.atecc608a-lifecycle": FetchResult(
            topic_id="S2.atecc608a-lifecycle",
            summary="ATECC608A NRND (stale verification)",
            verified_by="operator",
            sources=["https://example.com/microchip"],
            verified_date=stale_date,
        )
    }
    report2 = assemble_watch_report(cycle=99, fetched=fetched_stale)
    s2_stale = next(l for l in report2.lines if l.source.topic_id == "S2.atecc608a-lifecycle")
    assert s2_stale.state == WatchState.STALE
    assert s2_stale.verified_by == "operator"  # retained
    assert s2_stale.verified_date == stale_date  # retained
    assert s2_stale.sources == ["https://example.com/microchip"]  # retained


def test_t_sensor_b_12_missing_verified_by_downgrades_with_warning():
    """D-HWFL-20: 2/3 fields present => UNVERIFIED-EXTERNAL + warning."""
    today = datetime.now(timezone.utc).date().isoformat()
    fetched = {
        "S2.atecc608a-lifecycle": FetchResult(
            topic_id="S2.atecc608a-lifecycle",
            summary="some narrative",
            verified_by="",  # missing
            sources=["url"],
            verified_date=today,
        )
    }
    report = assemble_watch_report(cycle=99, fetched=fetched)
    s2 = next(l for l in report.lines if l.source.topic_id == "S2.atecc608a-lifecycle")
    assert s2.state == WatchState.UNVERIFIED_EXTERNAL
    assert "verified_by" in s2.verification_warning
    assert "PARTIAL VERIFICATION" in s2.verification_warning


def test_t_sensor_b_13_empty_sources_downgrades_with_warning():
    """D-HWFL-20: sources=[] is empty => UNVERIFIED-EXTERNAL + warning."""
    today = datetime.now(timezone.utc).date().isoformat()
    fetched = {
        "S2.atecc608a-lifecycle": FetchResult(
            topic_id="S2.atecc608a-lifecycle",
            summary="some narrative",
            verified_by="operator",
            sources=[],  # empty
            verified_date=today,
        )
    }
    report = assemble_watch_report(cycle=99, fetched=fetched)
    s2 = next(l for l in report.lines if l.source.topic_id == "S2.atecc608a-lifecycle")
    assert s2.state == WatchState.UNVERIFIED_EXTERNAL
    assert "sources" in s2.verification_warning


def test_t_sensor_b_14_missing_verified_date_downgrades_with_warning():
    """D-HWFL-20: verified_date='' => UNVERIFIED-EXTERNAL + warning."""
    fetched = {
        "S2.atecc608a-lifecycle": FetchResult(
            topic_id="S2.atecc608a-lifecycle",
            summary="some narrative",
            verified_by="operator",
            sources=["url"],
            verified_date="",  # missing
        )
    }
    report = assemble_watch_report(cycle=99, fetched=fetched)
    s2 = next(l for l in report.lines if l.source.topic_id == "S2.atecc608a-lifecycle")
    assert s2.state == WatchState.UNVERIFIED_EXTERNAL
    assert "verified_date" in s2.verification_warning


def test_t_sensor_b_15_malformed_verified_date_downgrades_with_warning():
    """D-HWFL-20 amendment: 3/3 fields present BUT verified_date not ISO-8601 =>
    UNVERIFIED-EXTERNAL + warning (catches operator typo)."""
    fetched = {
        "S2.atecc608a-lifecycle": FetchResult(
            topic_id="S2.atecc608a-lifecycle",
            summary="some narrative",
            verified_by="operator",
            sources=["url"],
            verified_date="not-a-date",  # malformed
        )
    }
    report = assemble_watch_report(cycle=99, fetched=fetched)
    s2 = next(l for l in report.lines if l.source.topic_id == "S2.atecc608a-lifecycle")
    assert s2.state == WatchState.UNVERIFIED_EXTERNAL
    assert "MALFORMED" in s2.verification_warning
    # Field still retained on the WatchLine so reviewer can see what was attempted.
    assert s2.verified_date == "not-a-date"


def test_t_sensor_b_16_zero_verified_fields_silent_backward_compat():
    """D-HWFL-20 amendment: 0/3 fields = Cycle 3-style JSON => silent downgrade
    to UNVERIFIED-EXTERNAL, NO warning rendered (backward compat for narratives
    shipped before Sensor B v0.1.1)."""
    today = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fetched = {
        "S2.atecc608a-lifecycle": FetchResult(
            topic_id="S2.atecc608a-lifecycle",
            summary="Cycle-3-shape narrative without any verified_* fields",
            fetched_at=today,
            # No verified_by / sources / verified_date.
        )
    }
    report = assemble_watch_report(cycle=99, fetched=fetched)
    s2 = next(l for l in report.lines if l.source.topic_id == "S2.atecc608a-lifecycle")
    assert s2.state == WatchState.UNVERIFIED_EXTERNAL
    assert s2.verification_warning == ""  # SILENT — backward compat
    # Confirm no warning bleed into rendered markdown either.
    md = report.to_markdown()
    assert "VERIFICATION WARNING" not in md


def test_t_sensor_b_10_never_raises_on_malformed_fetched_at(monkeypatch):
    """Bad ISO string in fetched_at => assembler doesn't crash; cell renders the literal."""
    fetched = {
        "S1.iip64-pr72": FetchResult(
            topic_id="S1.iip64-pr72",
            summary="some summary",
            fetched_at="not-a-timestamp",
        )
    }
    # Must not raise.
    report = assemble_watch_report(cycle=3, fetched=fetched)
    s1 = next(l for l in report.lines if l.source.topic_id == "S1.iip64-pr72")
    # Malformed timestamp => kept FRESH (we don't punish operator typos here)
    assert s1.state == WatchState.FRESH
    assert s1.fetched_at == "not-a-timestamp"
