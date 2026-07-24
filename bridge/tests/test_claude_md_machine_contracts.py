"""CLAUDE.md is machine-read. This pins the contracts so an edit can't silently break them.

Born 2026-07-24: the progressive-disclosure restructure (225k -> 74k chars) archived the
Path A Arc 1 NOTE, which carried the first-device-registration tx hash that
sensor_c_rung_ledger.py greps for. G1.5 silently flipped LIVE -> UNVERIFIABLE and it took
a full CI matrix run to surface. The SENSOR-A-LIVE anchors were checked before that edit
and survived; the Sensor C literal was not, because nothing said it existed.

The general hazard: CLAUDE.md doubles as a human context file AND a machine-read state
surface, so any content-level edit is a potential silent breakage of a verifier that
greps it. These tests make each such dependency explicit and fail loudly instead.

Adding a NEW machine dependency on CLAUDE.md? Add it here in the same commit.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "bridge"))

CLAUDE_MD = _REPO / "CLAUDE.md"


@pytest.fixture(scope="module")
def md() -> str:
    return CLAUDE_MD.read_text(encoding="utf-8")


# --- Sensor A v0.2: HTML-comment anchors, regex-parsed ---------------------------------

def test_sensor_a_anchors_parse(md):
    """parse_anchors() must find all three. These are the canonical claim, not the prose
    around them (D-HWFL-33)."""
    from vapi_bridge.sensor_a_live_drift import parse_anchors
    anchors = parse_anchors(md)
    assert set(anchors) == {"WALLET", "CONTRACTS", "TESTS"}, f"got {sorted(anchors)}"
    assert "balance_iotx" in anchors["WALLET"] and "as_of" in anchors["WALLET"]
    assert "count" in anchors["CONTRACTS"]
    for suite in ("bridge", "sdk", "hardhat_regex_scan"):
        assert suite in anchors["TESTS"], f"TESTS anchor missing {suite}"


# --- Sensor C: literal substring greps -------------------------------------------------

def test_sensor_c_g1_5_reference_device_tx_present(md):
    """G1.5 greps for this exact tx hash. Removing it flips the gate to UNVERIFIABLE.
    This is the one the 2026-07-24 restructure actually broke."""
    assert "0x68f6cf49564ed2b193d00e881e5cc9488111a8bc05951c2f2af55e25050ac9c0" in md, (
        "first-reference-device registration tx missing from CLAUDE.md -- "
        "sensor_c_rung_ledger.py::_verify_g1_5_reference_device_registered will report "
        "UNVERIFIABLE. Keep it in the canonical chain-facts block, not inside a NOTE "
        "(NOTEs get archived)."
    )


def test_sensor_c_live_gates_still_live():
    """End-to-end: the verifier-backed gates that depend on repo+CLAUDE.md state resolve
    LIVE. Catches the breakage at the level that actually matters."""
    from vapi_bridge.sensor_c_rung_ledger import GateState, assemble_ledger
    by_id = {r.gate.gate_id: r for r in assemble_ledger(_REPO, cycle=8).results}
    for gid in ("G1.4", "G1.5", "G1.6", "G1.7", "G2.1"):
        assert by_id[gid].state == GateState.LIVE, (
            f"{gid} = {by_id[gid].state.value} (evidence: {by_id[gid].evidence})"
        )


# --- Curation guardrail ---------------------------------------------------------------

def test_claude_md_within_its_own_size_budget(md):
    """The repo's own mythos_claude_md_curation enforces target 60k / warn 100k. It was
    firing 17 findings at 225k before the restructure. Keep it under the warn line."""
    assert len(md) < 100_000, (
        f"CLAUDE.md is {len(md):,} chars, over the 100k warn threshold "
        f"mythos_claude_md_curation enforces. Archive completed arcs to wiki/phases/ "
        f"and move detail into .claude/skills/."
    )


def test_note_discipline_holds(md):
    """'only the 5-7 most-recent NOTEs live here' -- the file's own stated rule, and the
    thing that regrows the file when it slips."""
    notes = [l for l in md.split("\n") if l.startswith("NOTE:")]
    assert len(notes) <= 8, (
        f"{len(notes)} NOTE lines; discipline is 5-7 recent + archive pointers. "
        f"Archive older arcs to wiki/phases/."
    )


# --- Progressive-disclosure layer ------------------------------------------------------

def test_skills_exist_and_are_indexed(md):
    """Skills carry the detail the restructure moved out. If one is deleted or renamed,
    CLAUDE.md's index silently points at nothing."""
    skills_dir = _REPO / ".claude" / "skills"
    on_disk = {p.parent.name for p in skills_dir.glob("*/SKILL.md")}
    assert on_disk, "no skills found -- progressive-disclosure layer is missing"
    for name in on_disk:
        assert f"`{name}`" in md, f"skill '{name}' exists but CLAUDE.md doesn't index it"


def test_skills_have_frontmatter():
    """A skill without name+description won't be discoverable at the right moment."""
    for skill in (_REPO / ".claude" / "skills").glob("*/SKILL.md"):
        head = skill.read_text(encoding="utf-8")[:400]
        assert head.startswith("---"), f"{skill.parent.name}: missing frontmatter"
        assert "name:" in head and "description:" in head, (
            f"{skill.parent.name}: frontmatter needs both name and description"
        )


# --- Archive integrity -----------------------------------------------------------------

def test_archived_notes_are_recoverable():
    """The 2026-07-24 archive claimed lossless. Verify the file still holds real NOTE
    bodies rather than a summary that quietly replaced them."""
    archive = _REPO / "wiki" / "phases" / "claude_md_note_archive_2026_07_24.md"
    if not archive.exists():
        pytest.skip("archive not present in this checkout")
    text = archive.read_text(encoding="utf-8")
    assert text.count("NOTE:") >= 40, (
        f"archive holds {text.count('NOTE:')} NOTE bodies; expected >=40 (lossless claim)"
    )
