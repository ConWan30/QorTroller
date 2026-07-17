"""Shared OPERATOR-ACTION renderer tests (HWFL-1, 2026-07-17).

The OA box was byte-identical hardcoded in TWO sensor files (the Cycle-9
dual-site drift disease). It now renders from one operator-attested source
(audits/operator_actions.json) via bridge/vapi_bridge/operator_actions.py.

   T-OA-1  Real-repo render: all 4 markers present; statuses reflect the JSON
           (OA-1/OA-2/OA-4 checked, OA-3 unchecked); sanitization tokens absent.
   T-OA-2  DEDUP PROOF: Sensor C ledger and Sensor B watch emit the IDENTICAL
           OA block == render_operator_actions() — single source of truth.
   T-OA-3  Missing file -> honest MISSING banner, no crash, and NONE of the
           stale legacy hardcoded text ("Highest-leverage 5-min action").
   T-OA-4  Malformed JSON / wrong schema -> MISSING banner (fail-open).
   T-OA-5  Sanitization: a synthetic item carrying a forbidden token renders
           REDACTED; the token never reaches the output.
   T-OA-6  Loop-never-attests: an unknown status renders as OPEN ([ ]), never
           silently [x]; and rendering does NOT mutate the source file.
   T-OA-7  machine_hint is advisory only — a bogus hint kind never crashes and
           never flips the checkbox.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bridge.vapi_bridge.operator_actions import render_operator_actions

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FORBIDDEN = ("qortroller_foundation_mfg_ca.json", "qortroller_foundation_mfg_ca",
              "arn:aws:", "~/.vapi")


def _seed(tmp_path: Path, items: list[dict], *, schema: str = "vapi-operator-actions-v1",
          note: str = "test note") -> Path:
    audits = tmp_path / "audits"
    audits.mkdir(exist_ok=True)
    (audits / "operator_actions.json").write_text(
        json.dumps({"schema": schema, "note": note, "items": items}, indent=2),
        encoding="utf-8",
    )
    return tmp_path


# ── T-OA-1 ────────────────────────────────────────────────────────────────────

def test_t_oa_1_real_repo_render_reflects_attested_statuses():
    md = render_operator_actions(REPO_ROOT)
    for marker in ("OA-1", "OA-2", "OA-3", "OA-4"):
        assert marker in md, f"OA box missing marker {marker!r}"
    # OA-3 is the one open item -> unchecked; the done/moot items are checked.
    assert "[ ] **OA-3** (open)" in md
    assert "[x] **OA-4** (done)" in md
    assert "[x] **OA-1** (moot)" in md
    # Sanitization — no operator-private tokens in the public box.
    low = md.lower()
    for tok in _FORBIDDEN:
        assert tok.lower() not in low, f"OA box leaked forbidden token {tok!r}"


# ── T-OA-2 (dedup proof) ──────────────────────────────────────────────────────

def test_t_oa_2_both_sensors_emit_identical_block():
    from bridge.vapi_bridge.sensor_c_rung_ledger import assemble_ledger
    from bridge.vapi_bridge.sensor_b_supply_watch import assemble_watch_report

    shared = render_operator_actions(REPO_ROOT)
    c_md = assemble_ledger(REPO_ROOT, cycle=18).to_markdown()
    b_md = assemble_watch_report(cycle=18, repo_root=REPO_ROOT).to_markdown()

    # The exact shared block appears verbatim in BOTH cycle artifacts.
    assert shared.strip() in c_md, "Sensor C did not render the shared OA block"
    assert shared.strip() in b_md, "Sensor B did not render the shared OA block"


# ── T-OA-3 ────────────────────────────────────────────────────────────────────

def test_t_oa_3_missing_file_honest_banner_no_legacy(tmp_path: Path):
    # tmp_path has no audits/operator_actions.json
    md = render_operator_actions(tmp_path)
    assert "missing, malformed, or wrong-schema" in md
    # The stale legacy hardcoded strings must NOT be revived by the fallback.
    assert "Highest-leverage 5-min action" not in md
    assert "[ ] **OA-1**" not in md  # no fabricated items


# ── T-OA-4 ────────────────────────────────────────────────────────────────────

def test_t_oa_4_malformed_and_wrong_schema_fail_open(tmp_path: Path):
    audits = tmp_path / "audits"
    audits.mkdir()
    # malformed JSON
    (audits / "operator_actions.json").write_text("{not json", encoding="utf-8")
    assert "missing, malformed, or wrong-schema" in render_operator_actions(tmp_path)
    # wrong schema
    (audits / "operator_actions.json").write_text(
        json.dumps({"schema": "something-else", "items": [{"id": "X"}]}), encoding="utf-8")
    assert "missing, malformed, or wrong-schema" in render_operator_actions(tmp_path)


# ── T-OA-5 (sanitization active defense) ──────────────────────────────────────

def test_t_oa_5_forbidden_token_item_is_redacted(tmp_path: Path):
    root = _seed(tmp_path, [
        {"id": "OA-9", "text": "leak ~/.vapi/qortroller_foundation_mfg_ca.json here",
         "status": "open"},
        {"id": "OA-10", "text": "clean item", "status": "done"},
    ])
    md = render_operator_actions(root)
    assert "REDACTED" in md
    assert "qortroller_foundation_mfg_ca" not in md.lower()
    assert "~/.vapi" not in md
    # the clean sibling still renders normally
    assert "[x] **OA-10** (done) clean item" in md


# ── T-OA-6 (loop never attests) ───────────────────────────────────────────────

def test_t_oa_6_unknown_status_renders_open_and_no_file_mutation(tmp_path: Path):
    root = _seed(tmp_path, [
        {"id": "OA-11", "text": "bogus status item", "status": "TOTALLY_DONE_TRUST_ME"},
    ])
    src = root / "audits" / "operator_actions.json"
    before = src.read_text(encoding="utf-8")
    md = render_operator_actions(root)
    # Unknown status must NOT silently become done/[x].
    assert "[ ] **OA-11** (open)" in md
    assert "[x] **OA-11**" not in md
    # The renderer has no write path — the source file is untouched.
    assert src.read_text(encoding="utf-8") == before


# ── T-OA-7 (machine_hint advisory) ────────────────────────────────────────────

def test_t_oa_7_bogus_hint_never_crashes_or_flips_checkbox(tmp_path: Path):
    root = _seed(tmp_path, [
        {"id": "OA-12", "text": "item", "status": "open",
         "machine_hint": {"kind": "not_a_real_kind", "ref": "x"}},
        {"id": "OA-13", "text": "item2", "status": "done",
         "machine_hint": "not-even-a-dict"},
    ])
    md = render_operator_actions(root)  # must not raise
    assert "[ ] **OA-12** (open)" in md   # bogus hint kind rendered nothing extra
    assert "[x] **OA-13** (done)" in md   # non-dict hint tolerated
    assert "not_a_real_kind" not in md    # unknown kind not echoed as a hint
