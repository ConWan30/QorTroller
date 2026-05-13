"""VPM Lifecycle regression guard — pins VBDIP-0002A §10 registry state.

Catches silent regression in the VPM registry's lifecycle ladder. Without
this guard, a refactor of `scripts/vpm_audit.py` could:

  - Drop a Compiler Target VPM back to Draft Manifest
  - Re-assign a CFSS lane (e.g. move MARKET-LISTING-v1 from curator to
    sentry, silently undermining the CFSS triangle)
  - Re-class a VPM's ZKBA class (silent overclaim attack)
  - Remove a VPM ID from §10 (silent registry shrinkage)

Each test below locks one architectural property. Failure surfaces at
PR time + lists the specific drift detected. Operator can resolve by
either (a) reverting the unintended change, or (b) updating both the
audit source AND this test in the same commit (explicit governance).

The regression guard is INTENTIONALLY a test-only invariant, NOT a
PV-CI INV-VPM-* entry. PV-CI invariants pin SOURCE-CODE-REGION digests
and require a `--confirm-governance` ceremony to update. Test-only
invariants pin SEMANTIC STATE that may legitimately evolve through
VBDIP-0002A §10 lifecycle promotions (Draft Manifest → Compiler Target
→ Active) without requiring governance ceremony — those promotions are
explicit operator decisions surfaced through the audit endpoint, not
frozen-protocol-invariant changes.

Together, this test band + the existing INV-VPM-* family form the full
defense: source-region digest pins protect against silent edits to
compiler functions; this test protects against silent edits to
lifecycle state.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "vpm_audit.py"

if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("vpm_audit", SCRIPT_PATH)
vpm_audit = importlib.util.module_from_spec(_spec)  # type: ignore
sys.modules["vpm_audit"] = vpm_audit
_spec.loader.exec_module(vpm_audit)  # type: ignore


# FROZEN expected state for VBDIP-0002A §10 registry after Phase O4 close.
# Updating this requires explicitly editing this test alongside the
# audit source — an explicit lifecycle promotion event.
_EXPECTED_SECTION_10 = {
    ("PROOF-TRAILER-v1",      "Esports Viewers",         "Reserved"),
    ("PROOF-WALLET-v1",       "Gamers",                  "Draft Manifest"),
    ("QR-ELIGIBILITY-v1",     "Organizers",              "Draft Manifest"),
    ("HARDWARE-LINEAGE-v1",   "Manufacturers",           "Draft Manifest"),
    ("CONSENT-CAPSULE-v1",    "Gamers / Data Buyers",    "Draft Manifest"),
    ("DISPUTE-PACKET-v1",     "Referees / Ops",          "Compiler Target"),
    ("MARKET-LISTING-v1",     "Buyers / Curator",        "Compiler Target"),
    ("DEV-SANDBOX-v1",        "Developers",              "Reserved"),
    ("HONESTY-BOARD-v1",      "Ecosystem Partners",      "Test Fixture"),
    ("AGENT-REVIEW-v1",       "Governance / Deployer",   "Test Fixture"),
}

# FROZEN per-compiler CFSS lane attribution. Catches silent lane
# re-assignment (the most security-relevant regression).
_EXPECTED_COMPILER_LANES = {
    "scripts/vpm_compile_honesty_board.py":    "sentry",
    "scripts/vpm_compile_agent_review.py":     "guardian",
    "scripts/vpm_compile_cdrr_dag.py":         "sentry",
    "scripts/vpm_compile_gic_ledger_beta.py":  "sentry",
    "scripts/vpm_compile_dispute_packet.py":   "guardian",
    "scripts/vpm_compile_market_listing.py":   "curator",
}

# FROZEN per-compiler ZKBA class binding. Catches silent class
# re-assignment (overclaim attack: changing a VPM's underlying class
# without revising the manifest hash linkage).
_EXPECTED_COMPILER_ZKBA_CLASSES = {
    "scripts/vpm_compile_honesty_board.py":    2,   # GIC
    "scripts/vpm_compile_agent_review.py":     5,   # CONSENT
    "scripts/vpm_compile_cdrr_dag.py":         4,   # HARDWARE
    "scripts/vpm_compile_gic_ledger_beta.py":  2,   # GIC
    "scripts/vpm_compile_dispute_packet.py":   5,   # CONSENT
    "scripts/vpm_compile_market_listing.py":   7,   # MARKET
}


# ---- T-LIFECYCLE-1: §10 registry cardinality + composition pinned -----

def test_t_lifecycle_1_section_10_registry_locked():
    """The §10 registry MUST contain exactly the 10 expected
    (vpm_id, audience, lifecycle) tuples — no additions, no removals,
    no field mutations."""
    actual = set(vpm_audit.SECTION_10_REGISTRY)
    assert actual == _EXPECTED_SECTION_10, (
        f"§10 registry drift detected. "
        f"Added: {actual - _EXPECTED_SECTION_10}. "
        f"Removed: {_EXPECTED_SECTION_10 - actual}. "
        f"Update both vpm_audit.py:SECTION_10_REGISTRY AND this test "
        f"in the same commit for explicit lifecycle promotion."
    )


# ---- T-LIFECYCLE-2: cardinality per lifecycle stage --------------------

def test_t_lifecycle_2_cardinality_per_stage():
    """The current §10 ladder shape after Phase O4 close is FROZEN at:
        Reserved=2 / Draft Manifest=4 / Compiler Target=2 / Test Fixture=2
    = 10 IDs total. Any silent stage-cardinality change is a regression
    or an implicit promotion — both should be explicit."""
    counts = {}
    for _, _, stage in vpm_audit.SECTION_10_REGISTRY:
        counts[stage] = counts.get(stage, 0) + 1

    expected = {
        "Reserved":        2,
        "Draft Manifest":  4,
        "Compiler Target": 2,
        "Test Fixture":    2,
    }
    assert counts == expected, (
        f"§10 lifecycle stage cardinality drift. "
        f"Expected: {expected}. Actual: {counts}."
    )


# ---- T-LIFECYCLE-3: total ID count --------------------------------------

def test_t_lifecycle_3_total_id_count():
    """The §10 registry MUST have exactly 10 IDs. Catch silent
    additions (which would imply an un-reviewed VPM Reservation)."""
    assert len(vpm_audit.SECTION_10_REGISTRY) == 10


# ---- T-LIFECYCLE-4: CFSS lane attribution per compiler ----------------

def test_t_lifecycle_4_cfss_lane_attribution_pinned():
    """Each compiler's CFSS lane is FROZEN. A silent re-assignment
    (e.g. moving MARKET-LISTING-v1 from curator to sentry) would
    structurally undermine the CFSS triangle. Catch at PR time."""
    actual = {
        c["compiler_path"]: c["proposed_cfss_lane"]
        for c in vpm_audit.ACTIVE_COMPILERS
    }
    assert actual == _EXPECTED_COMPILER_LANES, (
        f"CFSS lane attribution drift. Expected: {_EXPECTED_COMPILER_LANES}. "
        f"Actual: {actual}."
    )


# ---- T-LIFECYCLE-5: ZKBA class binding per compiler ------------------

def test_t_lifecycle_5_zkba_class_binding_pinned():
    """Each compiler's ZKBA class is FROZEN. Re-binding would shift
    the artifact's identity. Catch at PR time."""
    actual = {
        c["compiler_path"]: c["proposed_zkba_class"]
        for c in vpm_audit.ACTIVE_COMPILERS
    }
    assert actual == _EXPECTED_COMPILER_ZKBA_CLASSES, (
        f"ZKBA class binding drift. Expected: {_EXPECTED_COMPILER_ZKBA_CLASSES}. "
        f"Actual: {actual}."
    )


# ---- T-LIFECYCLE-6: active compiler count -----------------------------

def test_t_lifecycle_6_active_compiler_count():
    """ACTIVE_COMPILERS MUST have exactly 6 entries after Phase O4.
    The 6: HONESTY-BOARD, AGENT-REVIEW, CDRR-DAG, GIC-LEDGER-BETA,
    DISPUTE-PACKET, MARKET-LISTING."""
    assert len(vpm_audit.ACTIVE_COMPILERS) == 6


# ---- T-LIFECYCLE-7: draft manifest count ------------------------------

def test_t_lifecycle_7_draft_manifest_count():
    """DRAFT_MANIFESTS MUST have exactly 4 entries after Phase O4.
    The 4: PROOF-WALLET, QR-ELIGIBILITY, HARDWARE-LINEAGE, CONSENT-CAPSULE."""
    assert len(vpm_audit.DRAFT_MANIFESTS) == 4


# ---- T-LIFECYCLE-8: every Draft Manifest has a corresponding §10 entry ---

def test_t_lifecycle_8_draft_to_section_10_consistency():
    """Every entry in DRAFT_MANIFESTS MUST appear in SECTION_10_REGISTRY
    at lifecycle stage 'Draft Manifest'. Catches silent inconsistency
    between the two registries."""
    section_10_drafts = {
        vpm_id for vpm_id, _, stage in vpm_audit.SECTION_10_REGISTRY
        if stage == "Draft Manifest"
    }
    declared_drafts = {d["vpm_id"] for d in vpm_audit.DRAFT_MANIFESTS}
    assert declared_drafts == section_10_drafts, (
        f"Draft Manifest registry inconsistency. "
        f"DRAFT_MANIFESTS declares: {declared_drafts}. "
        f"§10 registry stage 'Draft Manifest': {section_10_drafts}. "
        f"Difference: {declared_drafts ^ section_10_drafts}."
    )


# ---- T-LIFECYCLE-9: CFSS lane vocabulary is canonical -----------------

def test_t_lifecycle_9_cfss_lane_vocabulary_canonical():
    """Every CFSS lane attribution MUST be one of {sentry, guardian,
    curator}. Catches typos + accidental new-lane introduction."""
    canonical_lanes = {"sentry", "guardian", "curator"}
    for compiler in vpm_audit.ACTIVE_COMPILERS:
        lane = compiler["proposed_cfss_lane"]
        assert lane in canonical_lanes, (
            f"Compiler {compiler['compiler_path']} has non-canonical "
            f"CFSS lane: {lane!r}. Must be one of {canonical_lanes}."
        )
    for draft in vpm_audit.DRAFT_MANIFESTS:
        lane = draft["proposed_cfss_lane"]
        assert lane in canonical_lanes, (
            f"Draft {draft['vpm_id']} has non-canonical CFSS lane: "
            f"{lane!r}. Must be one of {canonical_lanes}."
        )


# ---- T-LIFECYCLE-10: ZKBA class values are in valid range -------------

def test_t_lifecycle_10_zkba_class_in_valid_range():
    """Every ZKBA class binding MUST be in 1..7 (the FROZEN ZKBAClass
    enum range). Catches accidental class-8 introduction or class-0
    typo."""
    for compiler in vpm_audit.ACTIVE_COMPILERS:
        zc = compiler["proposed_zkba_class"]
        assert isinstance(zc, int) and 1 <= zc <= 7, (
            f"Compiler {compiler['compiler_path']} has invalid "
            f"ZKBA class: {zc}. Must be int in 1..7."
        )
    for draft in vpm_audit.DRAFT_MANIFESTS:
        zc = draft["proposed_zkba_class"]
        assert isinstance(zc, int) and 1 <= zc <= 7, (
            f"Draft {draft['vpm_id']} has invalid ZKBA class: {zc}. "
            f"Must be int in 1..7."
        )
