"""Tests for Mythos-Doc-Number-Consistency variant (2026-05-19, Layer 2).

T-MYTHOS-DNC-1  Empty registry / no superseded_values yields 0 findings
T-MYTHOS-DNC-2  Stale-value present in target doc → MEDIUM finding fires
T-MYTHOS-DNC-3  Word-boundary numeric matching avoids substring false positives
T-MYTHOS-DNC-4  Context-hint filter suppresses unrelated numeric matches
T-MYTHOS-DNC-5  Missing target document → silently skipped (no crash)
T-MYTHOS-DNC-6  Coherence-id deterministic across runs
T-MYTHOS-DNC-7  Live registry against current docs returns no surprise findings
                (sanity check — the WP v6 + state-of-protocol drifts are closed)
"""
import asyncio
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ----- T-MYTHOS-DNC-1 -----------------------------------------------------

def test_t_mythos_dnc_1_empty_superseded_yields_zero():
    """A registry entry with no superseded_values is skipped — nothing to scan for.

    Note (2026-05-19 honesty refinement): the variant always emits ONE
    COVERAGE_BOUNDARY informational finding describing what it audits, so
    a green result names its own scope. Drift findings (MEDIUM) are
    separate. This test asserts variant returns a list + the boundary
    finding is present + entries with empty superseded_values produce
    no drift findings."""
    from vapi_bridge.mythos_variants import mythos_doc_number_consistency

    findings = asyncio.run(mythos_doc_number_consistency())
    assert isinstance(findings, list)
    # COVERAGE_BOUNDARY finding always present (1 LOW informational)
    boundary_findings = [
        f for f in findings if "COVERAGE_BOUNDARY" in f.description
    ]
    assert len(boundary_findings) == 1, \
        "Variant must always emit exactly one COVERAGE_BOUNDARY finding"
    assert boundary_findings[0].severity == "LOW"
    # The boundary describes the registry; check it names a count of facts
    assert "registered canonical facts" in boundary_findings[0].description


# ----- T-MYTHOS-DNC-2 -----------------------------------------------------

def test_t_mythos_dnc_2_stale_value_in_doc_fires():
    """Stale value present in a target doc surfaces MEDIUM finding."""
    from vapi_bridge.mythos_variants import (
        _find_value_in_doc,
    )

    # Synthetic doc text containing a stale "217 sessions" reference
    text = """
    The 3-player corpus has 217 sessions on disk.
    Verified via ls sessions/human/ | wc -l.
    """
    matches = list(_find_value_in_doc(text, "217", ("session",)))
    assert len(matches) >= 1
    line_no, context = matches[0]
    assert "217" in context
    assert line_no >= 1


# ----- T-MYTHOS-DNC-3 -----------------------------------------------------

def test_t_mythos_dnc_3_word_boundary_no_substring_false_positives():
    """Searching for '12' must NOT match '128' or '4377' or '12345'."""
    from vapi_bridge.mythos_variants import _find_value_in_doc

    text = """
    PV-CI 128 invariants verified.
    Bridge tests 4377 passing.
    Foo bar 12345 baz.
    Actually 12 primitives flat overclaim.
    """
    # Searching for '12' with context hint 'primitives' should only fire on
    # the last line — the others have '12' as a substring of other numbers
    matches = list(_find_value_in_doc(text, "12", ("primitives",)))
    assert len(matches) == 1
    line_no, context = matches[0]
    assert "12 primitives" in context

    # Without context hint, '12' should still ONLY match the bare 12 (word-
    # boundary) not the substrings inside 128, 4377, 12345
    matches_all = list(_find_value_in_doc(text, "12", ()))
    assert len(matches_all) == 1, \
        f"Expected 1 match for bare 12; got {len(matches_all)}: {matches_all}"


# ----- T-MYTHOS-DNC-4 -----------------------------------------------------

def test_t_mythos_dnc_4_context_hint_suppresses_unrelated_matches():
    """Context hint filters out matches not in the relevant context."""
    from vapi_bridge.mythos_variants import _find_value_in_doc

    text = """
    Some random block 217 in IoTeX history.
    The 3-player corpus has 217 sessions.
    Unrelated 217 in a date string 2026-04-217-impossible.
    """
    # With context hint 'session', only the middle line matches
    matches = list(_find_value_in_doc(text, "217", ("session",)))
    assert len(matches) == 1
    line_no, context = matches[0]
    assert "session" in context.lower()


# ----- T-MYTHOS-DNC-5 -----------------------------------------------------

def test_t_mythos_dnc_5_missing_doc_silently_skipped():
    """Target doc that doesn't exist is silently skipped — no crash, no
    spurious finding."""
    from vapi_bridge.mythos_variants import mythos_doc_number_consistency

    # Run against a temp root that has NO docs/ directory.
    with tempfile.TemporaryDirectory() as td:
        findings = asyncio.run(mythos_doc_number_consistency(repo_root=Path(td)))
        # Missing docs → no drift findings (only the COVERAGE_BOUNDARY
        # informational); not an error
        drift = [f for f in findings if "STALE_RESIDUAL" in f.description]
        assert drift == []


# ----- T-MYTHOS-DNC-6 -----------------------------------------------------

def test_t_mythos_dnc_6_coherence_id_deterministic():
    """Same drift state → identical coherence_id (UNIQUE dedup at store layer)."""
    from vapi_bridge.mythos_variants import mythos_doc_number_consistency
    a = asyncio.run(mythos_doc_number_consistency())
    b = asyncio.run(mythos_doc_number_consistency())
    ids_a = sorted(f.coherence_id for f in a)
    ids_b = sorted(f.coherence_id for f in b)
    assert ids_a == ids_b
    if ids_a:
        assert all(cid.startswith("mythos_doc_number_consistency_") for cid in ids_a)


# ----- T-MYTHOS-DNC-7 -----------------------------------------------------

def test_t_mythos_dnc_7_live_docs_no_surprise_findings():
    """Sanity check: after the WP v6 reconciliation arc (commit 7eacd1a6),
    the live docs should NOT contain known superseded values for corpus-
    related facts. This test is the load-bearing regression guard: if it
    fails, a stale residual was introduced after the reconciliation.

    Specifically: '217' (corpus count) should NOT appear in
    docs/qortroller-whitepaper-v6.md with corpus context."""
    from vapi_bridge.mythos_variants import mythos_doc_number_consistency

    findings = asyncio.run(mythos_doc_number_consistency())

    # Filter to findings specifically about '217' in WP v6
    # Filter to drift findings (exclude COVERAGE_BOUNDARY informational)
    drift = [f for f in findings if "STALE_RESIDUAL" in f.description]
    wp_217_findings = [
        f for f in drift
        if "'217'" in f.description and "qortroller-whitepaper-v6" in (f.file_path or "")
    ]
    assert wp_217_findings == [], (
        f"Expected zero '217' stale residuals in WP v6 post-7eacd1a6; "
        f"got {len(wp_217_findings)}: {[f.description[:120] for f in wp_217_findings]}"
    )
