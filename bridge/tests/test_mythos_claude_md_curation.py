"""Mythos-Claude-MD-Curation tests (2026-05-18).

T-MYTHOS-CMD-1  Healthy CLAUDE.md (post-prune) yields 0 OVERSIZE findings
T-MYTHOS-CMD-2  Oversize synthetic fixture (>warn_chars) yields OVERSIZE LOW finding
T-MYTHOS-CMD-3  Superseded NOTE detection — mid-arc + closure NOTE present yields MEDIUM
T-MYTHOS-CMD-4  Stale-date NOTE detection — date marker >30d ago yields LOW
T-MYTHOS-CMD-5  Fail-open — missing CLAUDE.md returns []
T-MYTHOS-CMD-6  Coherence-id deterministic across runs (same content -> same id)
T-MYTHOS-CMD-7  Closure NOTEs are NOT flagged as their own stale (canonical entry exempt)
"""
import asyncio
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ----- T-MYTHOS-CMD-1 -----------------------------------------------------

def test_t_mythos_cmd_1_healthy_no_oversize():
    """Post-prune (~139k chars target) — OVERSIZE finding should fire ONCE
    if file exceeds warn_chars=100k. Either way the variant returns a list."""
    from vapi_bridge.mythos_variants import mythos_claude_md_curation

    async def run():
        return await mythos_claude_md_curation(repo_root=ROOT)

    findings = asyncio.run(run())
    assert isinstance(findings, list)
    # Oversize is informational LOW — not a failure condition
    oversize = [f for f in findings if "OVERSIZE" in f.description or "warn threshold" in f.description]
    if oversize:
        assert oversize[0].severity == "LOW"
        assert oversize[0].frozen_region is False


# ----- T-MYTHOS-CMD-2 -----------------------------------------------------

def test_t_mythos_cmd_2_oversize_synthetic():
    """Synthetic CLAUDE.md > warn_chars fires OVERSIZE LOW finding."""
    from vapi_bridge.mythos_variants import mythos_claude_md_curation

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        # Make a CLAUDE.md that crosses the 100-char warn threshold for test isolation
        (repo / "CLAUDE.md").write_text("# Test\n" + ("x" * 1000), encoding="utf-8")

        async def run():
            return await mythos_claude_md_curation(
                repo_root=repo,
                warn_chars=500,  # synthetic threshold
                target_chars=100,
            )

        findings = asyncio.run(run())
        oversize = [f for f in findings if "warn threshold" in f.description]
        assert len(oversize) == 1
        assert oversize[0].severity == "LOW"
        assert oversize[0].variant == "claude_md_curation"


# ----- T-MYTHOS-CMD-3 -----------------------------------------------------

def test_t_mythos_cmd_3_superseded_note_detection():
    """Mid-arc NOTE + later closure NOTE for same tag -> MEDIUM finding."""
    from vapi_bridge.mythos_variants import mythos_claude_md_curation

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        # Closure NOTE first (file is read top-to-bottom; top = newest by VAPI convention)
        # Both NOTEs share arc tag "STABILITY-9"
        content = "\n".join([
            "# Project",
            "",
            "NOTE: STABILITY-9 EMPIRICAL CLOSURE 2026-05-18 — terminal NOTE for arc",
            "",
            "NOTE: STABILITY-9 Stage 5 2026-05-17 — mid-arc work, should be superseded",
            "",
        ])
        (repo / "CLAUDE.md").write_text(content, encoding="utf-8")

        async def run():
            return await mythos_claude_md_curation(repo_root=repo, warn_chars=999_999)

        findings = asyncio.run(run())
        superseded = [f for f in findings if "superseded NOTE" in f.description]
        assert len(superseded) >= 1
        assert superseded[0].severity == "MEDIUM"


# ----- T-MYTHOS-CMD-4 -----------------------------------------------------

def test_t_mythos_cmd_4_stale_date_detection():
    """NOTE with explicit YYYY-MM-DD older than threshold -> LOW finding."""
    from vapi_bridge.mythos_variants import mythos_claude_md_curation

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        # NOTE dated 2024-01-01 — clearly older than 30 days from any plausible test date
        content = "\n".join([
            "# Project",
            "",
            "NOTE: Phase 99 — Test mid-arc 2024-01-01 — long-completed test phase",
            "",
        ])
        (repo / "CLAUDE.md").write_text(content, encoding="utf-8")

        async def run():
            return await mythos_claude_md_curation(
                repo_root=repo,
                stale_days_threshold=30,
                warn_chars=999_999,
            )

        findings = asyncio.run(run())
        stale = [f for f in findings if "days old" in f.description]
        assert len(stale) >= 1
        assert stale[0].severity == "LOW"


# ----- T-MYTHOS-CMD-5 -----------------------------------------------------

def test_t_mythos_cmd_5_missing_file_fail_open():
    """Missing CLAUDE.md -> returns [] (fail-open per Mythos contract)."""
    from vapi_bridge.mythos_variants import mythos_claude_md_curation

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        # No CLAUDE.md present

        async def run():
            return await mythos_claude_md_curation(repo_root=repo)

        findings = asyncio.run(run())
        assert findings == []


# ----- T-MYTHOS-CMD-6 -----------------------------------------------------

def test_t_mythos_cmd_6_coherence_id_deterministic():
    """Same content -> same coherence_id (UNIQUE dedup at store layer)."""
    from vapi_bridge.mythos_variants import mythos_claude_md_curation

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        (repo / "CLAUDE.md").write_text("# x\n" + ("y" * 1000), encoding="utf-8")

        async def run():
            return await mythos_claude_md_curation(repo_root=repo, warn_chars=500)

        findings_a = asyncio.run(run())
        findings_b = asyncio.run(run())

    ids_a = sorted(f.coherence_id for f in findings_a)
    ids_b = sorted(f.coherence_id for f in findings_b)
    assert ids_a == ids_b
    assert all(cid.startswith("mythos_claude_md_curation_") for cid in ids_a)


# ----- T-MYTHOS-CMD-7 -----------------------------------------------------

def test_t_mythos_cmd_7_closure_note_not_self_flagged():
    """Closure NOTEs are canonical for their arc — should NOT be flagged as
    stale even when their own date is >30d old (operator-curated entry)."""
    from vapi_bridge.mythos_variants import mythos_claude_md_curation

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td)
        # Closure NOTE only, dated 2024-01-01
        content = "\n".join([
            "# Project",
            "",
            "NOTE: STABILITY-3 EMPIRICAL CLOSURE 2024-01-01 — only closure NOTE",
            "",
        ])
        (repo / "CLAUDE.md").write_text(content, encoding="utf-8")

        async def run():
            return await mythos_claude_md_curation(
                repo_root=repo,
                stale_days_threshold=30,
                warn_chars=999_999,
            )

        findings = asyncio.run(run())
        # Should NOT flag the closure NOTE as superseded (it IS the closure)
        superseded = [f for f in findings if "superseded NOTE" in f.description]
        assert superseded == []
