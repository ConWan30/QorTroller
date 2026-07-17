"""HWFL-1 Cycle 2 — Sensor C v0.1 ledger tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bridge.vapi_bridge.sensor_c_rung_ledger import (
    GateState,
    assemble_ledger,
    canonical_gate_count,
    _CANONICAL_GATES,
    _VERIFIERS,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_t_sensor_c_1_canonical_gate_count_is_22():
    """D-HWFL-8 confirmed 22-gate v0.1 canonical list."""
    assert canonical_gate_count() == 22


def test_t_sensor_c_2_six_active_verifiers():
    """G1.4-G1.7 + G2.1 + G2.7 are the verifier-backed gates in v0.1.2
    (G2.7 promoted from intrinsic-BLOCKED-ON-SENSOR-B in HWFL-1 Cycle 7)."""
    assert len(_VERIFIERS) == 6
    verifier_names = {g.verifier_name for g in _CANONICAL_GATES if g.verifier_name}
    assert verifier_names == set(_VERIFIERS.keys())


def test_t_sensor_c_3_intrinsic_states_distribution():
    """Static state distribution after Cycle 7 G2.7 promotion (v0.1.2):
    3 HARDWARE-GATED, 12 DORMANT, 0 BLOCKED-ON-SENSOR-B, 1 BLOCKED-ON-EXTERNAL
    among intrinsic gates; 6 have None (verifier-backed: G1.4-G1.7 + G2.1 + G2.7)."""
    intrinsic = [g.intrinsic_state for g in _CANONICAL_GATES if g.intrinsic_state is not None]
    none_count = sum(1 for g in _CANONICAL_GATES if g.intrinsic_state is None)
    assert none_count == 6  # G1.4-G1.7 + G2.1 + G2.7
    assert intrinsic.count(GateState.HARDWARE_GATED) == 3
    assert intrinsic.count(GateState.DORMANT) == 12
    assert intrinsic.count(GateState.BLOCKED_ON_SENSOR_B) == 0  # was 1; G2.7 promoted out
    assert intrinsic.count(GateState.BLOCKED_ON_EXTERNAL) == 1


def test_t_sensor_c_4_live_repo_assemble_succeeds():
    """Real-repo run: 22 gate results, never raises, every result has evidence."""
    ledger = assemble_ledger(REPO_ROOT, cycle=2)
    assert len(ledger.results) == 22
    for r in ledger.results:
        assert r.evidence, f"gate {r.gate.gate_id} has empty evidence"
        assert r.verified_at


def test_t_sensor_c_5_live_repo_verifier_gates_are_live():
    """The 5 fully-LIVE verifier-backed gates (G1.4, G1.5, G1.6, G1.7, G2.1)
    pass on the real repo. G1.6 re-joined the LIVE set at Sensor C v0.1.4
    (2026-07-17): the F-DECON-3.2 root fix landed — override registry
    deployed + INV-MFG-003 sealed — demote detail asserted by T12.
    G2.7 is verifier-backed but resolves to LIVE-PARTIAL — asserted by T11."""
    ledger = assemble_ledger(REPO_ROOT, cycle=8)
    by_id = {r.gate.gate_id: r for r in ledger.results}
    for gid in ("G1.4", "G1.5", "G1.6", "G1.7", "G2.1"):
        assert by_id[gid].state == GateState.LIVE, (
            f"{gid} expected LIVE on real repo, got {by_id[gid].state.value} "
            f"(evidence: {by_id[gid].evidence})"
        )


def test_t_sensor_c_6_tmp_path_demotes_verifier_gates_to_unverifiable(tmp_path: Path):
    """Fail-open: missing files demote LIVE-candidate gates to UNVERIFIABLE, NEVER LIVE."""
    ledger = assemble_ledger(tmp_path, cycle=99)
    by_id = {r.gate.gate_id: r for r in ledger.results}
    # G1.4, G1.5, G1.7, G2.1, G2.7 verify against repo files that don't exist
    # in tmp_path -> UNVERIFIABLE. G1.6 verifies against ~/.vapi/... which DOES
    # exist on the operator's real home dir regardless of repo_root, so it's
    # intentionally not asserted here (test stays robust across operator machines).
    for gid in ("G1.4", "G1.5", "G1.7", "G2.1", "G2.7"):
        assert by_id[gid].state == GateState.UNVERIFIABLE, (
            f"{gid} should be UNVERIFIABLE on empty tmp repo, got {by_id[gid].state.value}"
        )


def test_t_sensor_c_7_intrinsic_states_preserved_in_results():
    """HARDWARE-GATED / DORMANT / BLOCKED-* states pass through unchanged."""
    ledger = assemble_ledger(REPO_ROOT, cycle=2)
    by_id = {r.gate.gate_id: r for r in ledger.results}
    assert by_id["G1.1"].state == GateState.HARDWARE_GATED
    # G2.1 was DORMANT in v0.1; Cycle 4 promoted it to LIVE via verifier
    # backed by docs/qortroller-devkit-bom-v0_1.md. Test now asserts LIVE
    # (which exercises the same intrinsic-pass-through contract for the
    # other intrinsic states sampled here).
    assert by_id["G2.1"].state == GateState.LIVE
    assert by_id["G2.2"].state == GateState.DORMANT  # representative DORMANT
    # G2.7 was BLOCKED_ON_SENSOR_B in v0.1.1; Cycle 7 (v0.1.2) promoted it
    # to LIVE-PARTIAL via two-part verifier (S6 narrative + BOM C1 absorption).
    assert by_id["G2.7"].state == GateState.LIVE_PARTIAL
    assert by_id["G4.1"].state == GateState.BLOCKED_ON_EXTERNAL


def test_t_sensor_c_8_json_serializes_and_validates_schema():
    """to_json() produces valid JSON; required schema fields present."""
    ledger = assemble_ledger(REPO_ROOT, cycle=2)
    blob = json.loads(ledger.to_json())
    assert blob["schema_version"] == "vapi-rung-gate-ledger-v1"
    assert blob["gate_count"] == 22
    assert isinstance(blob["state_counts"], dict)
    assert len(blob["gates"]) == 22
    for g in blob["gates"]:
        assert {"rung", "gate_id", "name", "state", "evidence", "verified_at", "spec_ref"} <= g.keys()


def test_t_sensor_c_9_markdown_operator_action_box_present_and_sanitized():
    """OA-1..OA-4 box renders into every ledger doc AND (HWFL-1 Cycle 9 /
    F-CYCLE9-1) the markdown stays sanitized. Since HWFL-1 2026-07-17 the box is
    rendered from the shared operator-attested source (single source of truth);
    this test asserts STRUCTURE + sanitization + the shared-render substring,
    NOT specific attestation prose (which the operator is free to change)."""
    from bridge.vapi_bridge.operator_actions import render_operator_actions
    ledger = assemble_ledger(REPO_ROOT, cycle=9)
    md = ledger.to_markdown()
    # Box presence — required markers (filename intentionally absent).
    for marker in ("OA-1", "OA-2", "OA-3", "OA-4"):
        assert marker in md, f"OPERATOR-ACTION box missing marker {marker!r}"
    # F-CYCLE9-1 sanitization regression — no operator-private filename tokens.
    forbidden_tokens = ("qortroller_foundation_mfg_ca.json", "qortroller_foundation_mfg_ca")
    for tok in forbidden_tokens:
        assert tok not in md, (
            f"Sensor C ledger markdown leaked operator-private token {tok!r} into "
            f"public artifact — violates F-CYCLE9-1 sanitization rail."
        )
    # Single-source proof: the ledger's box IS the shared renderer output.
    assert render_operator_actions(REPO_ROOT).strip() in md


def test_t_sensor_c_12_g1_6_live_post_root_fix_plus_evidence_sanitization():
    """G1.6 returns LIVE on the real repo (Sensor C v0.1.4, 2026-07-17): the
    F-DECON-3.2 ROOT FIX landed — HSM-backed CA + birth-cert override
    registry in deployed-addresses.json + INV-MFG-003 sealed in the PV-CI
    allowlist (both repo-committed artifacts checked by the two-part
    verifier). Regression assertion (F-CYCLE8-1 sanitization rider) is
    RETAINED: evidence string MUST NOT contain the CA filename."""
    ledger = assemble_ledger(REPO_ROOT, cycle=8)
    by_id = {r.gate.gate_id: r for r in ledger.results}
    g1_6 = by_id["G1.6"]
    assert g1_6.state == GateState.LIVE, (
        f"G1.6 expected LIVE on real repo (v0.1.4 root-fix evidence present), "
        f"got {g1_6.state.value} (evidence: {g1_6.evidence})"
    )
    # F-CYCLE8-1 sanitization rider — evidence MUST NOT echo the CA filename
    # or other operator-private path tokens into public-repo artifacts.
    forbidden_tokens = ("qortroller_foundation_mfg_ca.json", "qortroller_foundation_mfg_ca")
    for tok in forbidden_tokens:
        assert tok not in g1_6.evidence, (
            f"G1.6 evidence leaked operator-private token {tok!r} into public "
            f"ledger artifact — violates F-CYCLE8-1 sanitization rider. "
            f"Full evidence: {g1_6.evidence!r}"
        )
    # Positive content checks — root-fix evidence names the finding, the HSM
    # root, and both machine-checkable artifacts.
    assert "F-DECON-3.2" in g1_6.evidence
    assert "HSM" in g1_6.evidence
    assert "INV-MFG-003" in g1_6.evidence
    assert "deployed-addresses.json" in g1_6.evidence


def test_t_sensor_c_13_g1_6_fallback_re_demotes_without_root_fix_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """v0.1.4 honesty rail: absent EITHER root-fix artifact, G1.6 falls back
    to the pre-v0.1.4 behavior byte-identically — LIVE-FRAGILE while the
    software CA file exists, UNVERIFIABLE when it does not. Reverting the
    seal or the deploy record re-demotes the ledger; never spurious LIVE.
    Hermetic: Path.home is monkeypatched so the operator machine's real
    ~/.vapi never leaks into the test."""
    fake_home = tmp_path / "home"
    (fake_home / ".vapi").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    # (1) Empty repo (no allowlist, no deploy record) + CA file present
    #     -> LIVE-FRAGILE (the pre-root-fix state).
    (fake_home / ".vapi" / "qortroller_foundation_mfg_ca.json").write_text(
        "{}", encoding="utf-8"
    )
    ledger = assemble_ledger(tmp_path, cycle=99)
    g1_6 = next(r for r in ledger.results if r.gate.gate_id == "G1.6")
    assert g1_6.state == GateState.LIVE_FRAGILE
    assert "F-DECON-3.2" in g1_6.evidence
    assert "disaster-recovery-runbook.private.md" in g1_6.evidence

    # (2) Allowlist present but INV-MFG-003 removed (seal reverted) + deploy
    #     record present -> STILL falls back (two-part rule: BOTH required).
    gh = tmp_path / ".github"
    contracts = tmp_path / "contracts"
    gh.mkdir()
    contracts.mkdir()
    (gh / "INVARIANTS_ALLOWLIST.json").write_text(
        '{"INV-MFG-001": {"digest": "aa"}}', encoding="utf-8"
    )
    (contracts / "deployed-addresses.json").write_text(
        '{"VAPIDeviceBirthCertUpdateRegistry": "0x31030C8F4d805bC73e2c49D935eD0FB6a12987a5"}',
        encoding="utf-8",
    )
    ledger2 = assemble_ledger(tmp_path, cycle=99)
    g1_6_b = next(r for r in ledger2.results if r.gate.gate_id == "G1.6")
    assert g1_6_b.state == GateState.LIVE_FRAGILE  # seal absent -> no LIVE

    # (2b) Symmetric (round-29 F2): seal PRESENT but deploy record ABSENT
    #      -> STILL falls back. Both artifacts required, in both directions.
    (gh / "INVARIANTS_ALLOWLIST.json").write_text(
        '{"INV-MFG-003": {"digest": "bb"}}', encoding="utf-8"
    )
    (contracts / "deployed-addresses.json").unlink()
    ledger2b = assemble_ledger(tmp_path, cycle=99)
    g1_6_b2 = next(r for r in ledger2b.results if r.gate.gate_id == "G1.6")
    assert g1_6_b2.state == GateState.LIVE_FRAGILE  # deploy record absent -> no LIVE

    # (3) Both artifacts present and well-formed -> LIVE (the v0.1.4 demote).
    (contracts / "deployed-addresses.json").write_text(
        '{"VAPIDeviceBirthCertUpdateRegistry": "0x31030C8F4d805bC73e2c49D935eD0FB6a12987a5"}',
        encoding="utf-8",
    )
    ledger3 = assemble_ledger(tmp_path, cycle=99)
    g1_6_c = next(r for r in ledger3.results if r.gate.gate_id == "G1.6")
    assert g1_6_c.state == GateState.LIVE
    assert "INV-MFG-003" in g1_6_c.evidence

    # (4) Malformed deploy-record JSON -> UNVERIFIABLE (exception rail),
    #     never LIVE, never a silent fallback that hides the corruption.
    (contracts / "deployed-addresses.json").write_text("{not json", encoding="utf-8")
    ledger4 = assemble_ledger(tmp_path, cycle=99)
    g1_6_d = next(r for r in ledger4.results if r.gate.gate_id == "G1.6")
    assert g1_6_d.state == GateState.UNVERIFIABLE

    # (5) No root-fix evidence + CA file ABSENT -> UNVERIFIABLE (pre-fix rule).
    (gh / "INVARIANTS_ALLOWLIST.json").unlink()
    (contracts / "deployed-addresses.json").unlink()
    (fake_home / ".vapi" / "qortroller_foundation_mfg_ca.json").unlink()
    ledger5 = assemble_ledger(tmp_path, cycle=99)
    g1_6_e = next(r for r in ledger5.results if r.gate.gate_id == "G1.6")
    assert g1_6_e.state == GateState.UNVERIFIABLE


def test_t_sensor_c_11_g2_7_two_part_verifier_honesty_rail(tmp_path: Path):
    """G2.7's verifier requires BOTH the Sensor B narrative AND the BOM
    absorption marker. Either alone => UNVERIFIABLE (never spurious
    LIVE-PARTIAL). Validates D-HWFL-22 two-part rule."""
    # Fixture: build a minimal repo with both files present + markers correct.
    audits = tmp_path / "audits"
    docs = tmp_path / "docs"
    audits.mkdir()
    docs.mkdir()
    (audits / "ops_notes_cycle5.json").write_text(
        '{"S6.esp32-cert-status": {"summary": "ESP32 cert intel"}}', encoding="utf-8"
    )
    (docs / "qortroller-devkit-bom-v0_1.md").write_text(
        "BOM stub. C1 row notes: secure-element pairing required.\n",
        encoding="utf-8",
    )
    ledger = assemble_ledger(tmp_path, cycle=99)
    g2_7 = next(r for r in ledger.results if r.gate.gate_id == "G2.7")
    assert g2_7.state == GateState.LIVE_PARTIAL

    # Remove BOM marker => UNVERIFIABLE (planning artifact desync).
    (docs / "qortroller-devkit-bom-v0_1.md").write_text(
        "BOM stub. C1 row notes: cert status pending.\n",  # no "secure-element pairing required"
        encoding="utf-8",
    )
    ledger2 = assemble_ledger(tmp_path, cycle=99)
    g2_7_b = next(r for r in ledger2.results if r.gate.gate_id == "G2.7")
    assert g2_7_b.state == GateState.UNVERIFIABLE
    assert "planning artifact desynced" in g2_7_b.evidence

    # Empty S6 summary => UNVERIFIABLE (narrative absent).
    (docs / "qortroller-devkit-bom-v0_1.md").write_text(
        "BOM stub. C1 row notes: secure-element pairing required.\n",
        encoding="utf-8",
    )
    (audits / "ops_notes_cycle5.json").write_text(
        '{"S6.esp32-cert-status": {"summary": ""}}', encoding="utf-8"
    )
    ledger3 = assemble_ledger(tmp_path, cycle=99)
    g2_7_c = next(r for r in ledger3.results if r.gate.gate_id == "G2.7")
    assert g2_7_c.state == GateState.UNVERIFIABLE
    assert "empty" in g2_7_c.evidence.lower() or "missing" in g2_7_c.evidence.lower()


def test_t_sensor_c_10_verifier_exception_yields_unverifiable_not_crash():
    """Honesty rail: a buggy verifier MUST NOT crash assemble; result demotes to UNVERIFIABLE."""
    from bridge.vapi_bridge import sensor_c_rung_ledger as mod
    original = mod._VERIFIERS["verify_g1_7_secure_element_honesty"]
    try:
        def _boom(_repo_root):
            raise RuntimeError("synthetic test failure")
        mod._VERIFIERS["verify_g1_7_secure_element_honesty"] = _boom
        ledger = assemble_ledger(REPO_ROOT, cycle=2)
        by_id = {r.gate.gate_id: r for r in ledger.results}
        assert by_id["G1.7"].state == GateState.UNVERIFIABLE
        assert "synthetic test failure" in by_id["G1.7"].evidence
    finally:
        mod._VERIFIERS["verify_g1_7_secure_element_honesty"] = original
