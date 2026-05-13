"""Phase O4-VPM-INTEGRATION Stream A.3 — Draft Manifest schema tests.

Test band:
  T-VPM-DRAFT-1:  PROOF-WALLET-v1 draft manifest schema validates
  T-VPM-DRAFT-2:  QR-ELIGIBILITY-v1 draft manifest schema validates
  T-VPM-DRAFT-3:  HARDWARE-LINEAGE-v1 draft manifest schema validates
  T-VPM-DRAFT-4:  CONSENT-CAPSULE-v1 draft manifest schema validates

Plus consolidated tests:
  T-VPM-DRAFT-5:  registry alignment — every Draft Manifest references a
                  registered VBDIP-0002A section 10 ID; no compiler body
                  exists for any of the 4 Draft IDs (lifecycle invariant)
  T-VPM-DRAFT-6:  cross-draft uniqueness — each Draft ID is distinct;
                  no two drafts collide on (vpm_id, proposed_cfss_lane)
                  in an unintended way

Each draft manifest is purely documentation-only per VBDIP-0002A section 10
("VPM ID becomes active only after wrapper manifest, compiler target, test
fixture, and governance approval exist"). These tests assert that the JSON
shape is well-formed and the lifecycle status is locked at "Draft Manifest".

Author: VAPI Architect (Phase O4 Commit 6)
Date: 2026-05-13
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_BRIDGE = os.path.normpath(os.path.join(_REPO, "bridge"))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vpm_visual_grammar import VISUAL_STATES, INTEGRITY_LABEL_FIELDS  # noqa: E402


_DRAFTS_DIR = Path(_REPO) / "scripts" / "vpm_drafts"


_VALID_ZKBA_CLASSES = {1, 2, 3, 4, 5, 6, 7}
_VALID_PROOF_WEIGHTS = {1, 2, 3, 4, 5, 6}  # 6-element FROZEN enum per Phase O3
_VALID_CFSS_LANES = {"sentry", "guardian", "curator"}

# Expected per-draft top-level invariants
_EXPECTED_DRAFTS = {
    "PROOF-WALLET-v1": {
        "audience": "Gamers",
        "proposed_zkba_class": 3,
        "proposed_zkba_class_name": "VHP",
        "proposed_cfss_lane": "sentry",
    },
    "QR-ELIGIBILITY-v1": {
        "audience": "Tournament Organizers",
        "proposed_zkba_class": 6,
        "proposed_zkba_class_name": "TOURNAMENT",
        "proposed_cfss_lane": "sentry",
    },
    "HARDWARE-LINEAGE-v1": {
        "audience": "Manufacturers",
        "proposed_zkba_class": 4,
        "proposed_zkba_class_name": "HARDWARE",
        "proposed_cfss_lane": "sentry",
    },
    "CONSENT-CAPSULE-v1": {
        "audience": "Gamers / Data Buyers",
        "proposed_zkba_class": 5,
        "proposed_zkba_class_name": "CONSENT",
        "proposed_cfss_lane": "guardian",
    },
}


# Common schema validator — used by each per-draft test
def _validate_draft_schema(vpm_id: str, expected: dict) -> dict:
    """Load + validate the per-draft JSON. Returns the parsed dict for
    additional per-draft assertions. Raises AssertionError on any drift."""
    path = _DRAFTS_DIR / f"{vpm_id}.draft.json"
    assert path.exists(), f"Draft manifest missing: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))

    # Top-level invariants
    assert data["vpm_id"] == vpm_id, (
        f"vpm_id drift: file claims {data['vpm_id']!r} but filename pins {vpm_id!r}"
    )
    assert data["lifecycle_status"] == "Draft Manifest", (
        f"lifecycle_status MUST be 'Draft Manifest'; got {data['lifecycle_status']!r}"
    )
    assert data["wrapper_schema_ref"] == "vapi-vpm-manifest-v1", (
        f"wrapper_schema_ref MUST reference vapi-vpm-manifest-v1; "
        f"got {data['wrapper_schema_ref']!r}"
    )
    assert data["audience"] == expected["audience"], (
        f"audience drift: expected {expected['audience']!r}; got {data['audience']!r}"
    )
    assert data["proposed_zkba_class"] == expected["proposed_zkba_class"]
    assert data["proposed_zkba_class_name"] == expected["proposed_zkba_class_name"]
    assert data["proposed_zkba_class"] in _VALID_ZKBA_CLASSES
    assert data["proposed_proof_weight"] in _VALID_PROOF_WEIGHTS
    assert data["proposed_cfss_lane"] == expected["proposed_cfss_lane"]
    assert data["proposed_cfss_lane"] in _VALID_CFSS_LANES

    # Visual states must be a subset of VISUAL_STATES (with all 6 covered
    # in the canonical case)
    proposed_states = data["proposed_visual_states"]
    assert isinstance(proposed_states, list)
    assert set(proposed_states).issubset(set(VISUAL_STATES)), (
        f"proposed_visual_states contains unknown state: "
        f"{set(proposed_states) - set(VISUAL_STATES)}"
    )
    assert set(proposed_states) == set(VISUAL_STATES), (
        "Phase O4 drafts MUST propose support for all 6 visual states"
    )

    # Proposed inputs schema must be a dict with at least 5 fields
    inputs_schema = data["proposed_inputs_schema"]
    assert isinstance(inputs_schema, dict)
    assert len(inputs_schema) >= 5, (
        f"proposed_inputs_schema has only {len(inputs_schema)} fields; "
        "drafts should specify >=5 substantive fields"
    )
    for field_name, field_spec in inputs_schema.items():
        assert isinstance(field_spec, dict), (
            f"field {field_name} spec must be dict; got {type(field_spec).__name__}"
        )
        assert "type" in field_spec
        assert "description" in field_spec

    # Integrity label template must contain all 9 FROZEN fields
    label_template = data["proposed_integrity_label_template"]
    assert isinstance(label_template, dict)
    for field in INTEGRITY_LABEL_FIELDS:
        assert field in label_template, (
            f"proposed_integrity_label_template missing FROZEN field {field!r}"
        )

    # References block must point at the future compiler path
    refs = data["references"]
    assert isinstance(refs, dict)
    assert "future_compiler_path" in refs
    assert "registry" in refs
    assert refs["future_compiler_path"].startswith("scripts/vpm_compile_")
    assert refs["future_compiler_path"].endswith(".py")

    # Promotion rules block must specify all 3 ladder steps
    promo = data["promotion_rules"]
    assert isinstance(promo, dict)
    assert "to_compiler_target" in promo
    assert "to_test_fixture" in promo
    assert "to_active" in promo

    # Non-authoritative-clause must be present
    assert "non_authoritative_notes" in data
    assert "documentation-only" in data["non_authoritative_notes"].lower()

    return data


# ---------------------------------------------------------------------------
# T-VPM-DRAFT-1..4 — one per Reserved -> Draft Manifest promotion
# ---------------------------------------------------------------------------

def test_t_vpm_draft_1_proof_wallet_v1_schema():
    data = _validate_draft_schema("PROOF-WALLET-v1", _EXPECTED_DRAFTS["PROOF-WALLET-v1"])
    # PROOF-WALLET specific: must reference VHP token + GIC chain length
    inputs = data["proposed_inputs_schema"]
    assert "vhp_token_id" in inputs
    assert "vhp_cert_level" in inputs
    assert "gic_chain_length" in inputs
    assert "consecutive_clean_streak" in inputs


def test_t_vpm_draft_2_qr_eligibility_v1_schema():
    data = _validate_draft_schema("QR-ELIGIBILITY-v1", _EXPECTED_DRAFTS["QR-ELIGIBILITY-v1"])
    # QR-ELIGIBILITY specific: must reference tournament + is_fully_eligible
    inputs = data["proposed_inputs_schema"]
    assert "tournament_id" in inputs
    assert "is_fully_eligible" in inputs
    assert "qr_payload_hash_hex" in inputs
    assert "check_in_window_start_ts_ns" in inputs
    assert "check_in_window_end_ts_ns" in inputs


def test_t_vpm_draft_3_hardware_lineage_v1_schema():
    data = _validate_draft_schema("HARDWARE-LINEAGE-v1", _EXPECTED_DRAFTS["HARDWARE-LINEAGE-v1"])
    # HARDWARE-LINEAGE specific: must reference profile_hash + manufacturer
    inputs = data["proposed_inputs_schema"]
    assert "profile_hash" in inputs
    assert "manufacturer_address" in inputs
    assert "cert_level" in inputs
    # Inherits Phase O3 HARDWARE Participation Card privacy posture:
    # manufacturer_address is publicly attributable, NOT hashed.
    assert inputs["manufacturer_address"].get("privacy") == "publicly-attributable-not-hashed"


def test_t_vpm_draft_4_consent_capsule_v1_schema():
    data = _validate_draft_schema("CONSENT-CAPSULE-v1", _EXPECTED_DRAFTS["CONSENT-CAPSULE-v1"])
    # CONSENT-CAPSULE specific: must reference consent_hash + category_bitmask
    # + revoked_at (GDPR Art. 17 primitive)
    inputs = data["proposed_inputs_schema"]
    assert "consent_hash" in inputs
    assert "category_bitmask" in inputs
    assert "revoked_at" in inputs
    # gamer_address must be hashed (privacy posture matches CONSENT Receipt
    # Card commit 9bfa981e — inverse of HARDWARE manufacturer posture)
    assert inputs["gamer_address_hash"].get("privacy") == "already-hashed-input"


# ---------------------------------------------------------------------------
# T-VPM-DRAFT-5..6 — Cross-draft consolidated invariants
# ---------------------------------------------------------------------------

def test_t_vpm_draft_5_no_compiler_body_yet_for_drafts():
    """Lifecycle invariant: NO compiler script exists for any of the 4
    Reserved/Draft Manifest IDs in this commit. If a compiler script for
    a Draft ID later appears, this test fails — the lifecycle has
    advanced and the draft JSON should accompany the promotion to a
    new lifecycle status (Compiler Target)."""
    for draft_id in _EXPECTED_DRAFTS:
        # Convert draft_id -> expected compiler script name
        # e.g. PROOF-WALLET-v1 -> vpm_compile_proof_wallet.py
        snake = draft_id.lower().replace("-v1", "").replace("-", "_")
        compiler_path = Path(_REPO) / "scripts" / f"vpm_compile_{snake}.py"
        assert not compiler_path.exists(), (
            f"Lifecycle drift: Draft Manifest {draft_id} has a compiler "
            f"script at {compiler_path}. Either the lifecycle should be "
            "promoted to 'Compiler Target' in the draft JSON or the "
            "compiler script should not exist yet."
        )


def test_t_vpm_draft_6_distinct_ids_and_no_lane_conflicts():
    """Cross-draft uniqueness: each Draft ID is distinct (4 of 4); no two
    draft IDs collide on (vpm_id, proposed_cfss_lane). Drafts may share a
    lane (e.g. 3 of 4 drafts live in Sentry's zk_artifacts/) but each
    vpm_id is globally unique."""
    seen_ids = set()
    lane_counts = {"sentry": 0, "guardian": 0, "curator": 0}
    for draft_id in _EXPECTED_DRAFTS:
        path = _DRAFTS_DIR / f"{draft_id}.draft.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["vpm_id"] not in seen_ids, (
            f"Duplicate vpm_id: {data['vpm_id']}"
        )
        seen_ids.add(data["vpm_id"])
        lane_counts[data["proposed_cfss_lane"]] += 1
    assert len(seen_ids) == 4
    # All 4 drafts must propose existing CFSS lanes — no new lanes
    assert all(count >= 0 for count in lane_counts.values())
    # Expected distribution per the per-draft assignments:
    #   Sentry: 3 (PROOF-WALLET, QR-ELIGIBILITY, HARDWARE-LINEAGE)
    #   Guardian: 1 (CONSENT-CAPSULE)
    #   Curator: 0 (no Curator-lane drafts in A.3; MARKET-LISTING already a
    #              Compiler Target from A.2.b)
    assert lane_counts["sentry"] == 3
    assert lane_counts["guardian"] == 1
    assert lane_counts["curator"] == 0
