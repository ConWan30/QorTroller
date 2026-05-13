"""Layer 7 composition lattice exhaustiveness — formal completeness test.

Phase O3-ZKBA-TRACK1's `T-ZKBA-HW-10_layer_7_seven_of_seven_closure` test
verifies NON-COLLISION across the 7 ZKBAClass values for identical
component bytes — proves the domain-tag byte in `compute_zkba_commitment`
is load-bearing. The complementary property — that when one upstream
primitive in a COMPOSING artifact changes, the downstream commitment
changes predictably — was asserted implicitly per-class (T-ZKBA-TOURN-10,
T-ZKBA-MARKET-10, etc.) but not validated at the cross-class CDRR DAG
level.

This test band closes the formal completeness gap. It exhaustively
exercises every composition edge in the CDRR DAG. After Phase O4 close
the DAG has 7 nodes (one per ZKBAClass) and 5 composition edges:

  TOURNAMENT ── composes ──> VHP                (token state)
  TOURNAMENT ── composes ──> GIC                (chain head + length)
  TOURNAMENT ── composes ──> ProtocolLens       (isFullyEligible verdict)
  MARKET     ── composes ──> LISTING            (Phase 238 primitive)
  MARKET     ── composes ──> CONSENT            (Phase 237 v1 hash)

The 5 single-primitive classes (AIT, GIC, VHP, HARDWARE, CONSENT)
trivially satisfy the property — their per-field tamper tests
(T-ZKBA-AIT-7, T-ZKBA-GIC-7, T-ZKBA-VHP-7, T-ZKBA-HW-7, T-ZKBA-CONSENT-7)
already cover it. This test band targets the 2 composing classes.

Empirical assertion per composition edge: building a baseline
TOURNAMENT/MARKET artifact, then mutating one upstream primitive
(holding all other primitives fixed), MUST produce a different
commitment hash. The test runs every edge exhaustively + reports
which edges contribute and which don't.

A failure on any composition edge would indicate one of two architectural
regressions:
  (a) the upstream primitive's bytes are no longer in the preimage
      (compiler regression — silent removal of a field)
  (b) the upstream primitive's contribution is overwritten by a downstream
      field (compiler regression — preimage construction reordered)

Either case fires this test before merge.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
if str(PROJECT_ROOT / "bridge") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "bridge"))


def _load_script(name: str):
    """Load a compile script as a module."""
    path = PROJECT_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)  # type: ignore
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore
    return module


@pytest.fixture(scope="module")
def tournament_compiler():
    return _load_script("zkba_compile_tournament_card")


@pytest.fixture(scope="module")
def market_compiler():
    return _load_script("zkba_compile_marketplace_listing")


def _make_store(tmp_path):
    """Build a fresh on-disk bridge store. ":memory:" path doesn't
    trigger the schema_versions migration; on-disk does."""
    from vapi_bridge.store import Store  # type: ignore

    return Store(str(tmp_path / "composition_test.db"))


def _commitment_of(manifest) -> str:
    """Extract the output commitment (HTML hash) from a manifest."""
    return manifest.output_hash_hex


# Baseline TOURNAMENT inputs — mirrors the Phase 235-A GIC_100 fixture +
# canonical Sony DualShock Edge CFI-ZCP1 binding from Sessions 1+2+3.
_TOURNAMENT_BASELINE = {
    "vhp_token_id": 2,
    "vhp_is_valid": True,
    "gic_chain_head_hex": (
        "0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da"
    ),
    "gic_chain_length": 100,
    "is_fully_eligible": True,
    "device_id_hash_hex": (
        "10e0169446ba33200000000000000000000000000000000000000000000000ab"
    ),
    "tournament_id": 20260601001,
    "ts_ns": 1745539200000000000,
}

# Baseline MARKET inputs — mirrors the Phase 238 LISTING-v1 + CONSENT v1
# composition fixture from the existing MARKET test band.
_MARKET_BASELINE = {
    "listing_commitment_hex": (
        "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"
    ),
    "tier_multiplier_milli": 2000,
    "ipfs_cid": "QmTestCidV0Fixed1234567890123456789012345678",
    "consent_hash_hex": (
        "d45615ff1ffdef9efa7857fc930c43c0dd20ed492076537d85cc96ae537ac97b"
    ),
    "suspended": False,
    "ts_ns": 1745539200000000000,
}


# ---- T-LAYER7-COMP-1: TOURNAMENT × VHP edge -------------------------

def test_t_layer7_comp_1_tournament_vhp_edge(tournament_compiler, tmp_path):
    """Mutating VHP token_id MUST change the TOURNAMENT commitment."""
    store = _make_store(tmp_path)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)

        m_base = tournament_compiler.build_tournament_card_artifact(
            store=store, output_dir=out, **_TOURNAMENT_BASELINE,
        )
        c_base = _commitment_of(m_base)

        # Mutate VHP token_id; hold everything else fixed.
        mutated = dict(_TOURNAMENT_BASELINE)
        mutated["vhp_token_id"] = 3
        m_mut = tournament_compiler.build_tournament_card_artifact(
            store=store, output_dir=out, **mutated,
        )
        c_mut = _commitment_of(m_mut)

        assert c_base != c_mut, (
            "TOURNAMENT commitment MUST change when VHP token_id changes "
            "— VHP primitive is part of the composition lattice"
        )


# ---- T-LAYER7-COMP-2: TOURNAMENT × GIC edge -------------------------

def test_t_layer7_comp_2_tournament_gic_chain_head_edge(tournament_compiler, tmp_path):
    """Mutating GIC chain head MUST change the TOURNAMENT commitment."""
    store = _make_store(tmp_path)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)

        m_base = tournament_compiler.build_tournament_card_artifact(
            store=store, output_dir=out, **_TOURNAMENT_BASELINE,
        )
        c_base = _commitment_of(m_base)

        # Mutate GIC chain head to a different valid 32-byte hex.
        mutated = dict(_TOURNAMENT_BASELINE)
        mutated["gic_chain_head_hex"] = "f" * 64
        m_mut = tournament_compiler.build_tournament_card_artifact(
            store=store, output_dir=out, **mutated,
        )
        c_mut = _commitment_of(m_mut)

        assert c_base != c_mut, (
            "TOURNAMENT commitment MUST change when GIC chain head changes "
            "— GIC primitive is part of the composition lattice"
        )


def test_t_layer7_comp_2b_tournament_gic_chain_length_edge(
    tournament_compiler, tmp_path,
):
    """Mutating GIC chain length MUST change the TOURNAMENT commitment.
    Validates that the chain length field is independently load-bearing
    (not just the head hash)."""
    store = _make_store(tmp_path)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)

        m_base = tournament_compiler.build_tournament_card_artifact(
            store=store, output_dir=out, **_TOURNAMENT_BASELINE,
        )
        c_base = _commitment_of(m_base)

        mutated = dict(_TOURNAMENT_BASELINE)
        mutated["gic_chain_length"] = 101  # GIC_100 → GIC_101 simulation
        m_mut = tournament_compiler.build_tournament_card_artifact(
            store=store, output_dir=out, **mutated,
        )
        c_mut = _commitment_of(m_mut)

        assert c_base != c_mut, (
            "TOURNAMENT commitment MUST change when GIC chain length "
            "changes — chain depth is independently load-bearing"
        )


# ---- T-LAYER7-COMP-3: TOURNAMENT × ProtocolLens edge -----------------

def test_t_layer7_comp_3_tournament_protocollens_edge(tournament_compiler, tmp_path):
    """Mutating isFullyEligible verdict MUST change the TOURNAMENT
    commitment. This is the cryptographically-critical edge: a
    tournament organizer's gate decision flips ineligible→eligible (or
    vice versa), and the artifact's commitment MUST reflect the flip."""
    store = _make_store(tmp_path)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)

        m_base = tournament_compiler.build_tournament_card_artifact(
            store=store, output_dir=out, **_TOURNAMENT_BASELINE,
        )
        c_base = _commitment_of(m_base)

        mutated = dict(_TOURNAMENT_BASELINE)
        mutated["is_fully_eligible"] = False  # flip eligibility
        m_mut = tournament_compiler.build_tournament_card_artifact(
            store=store, output_dir=out, **mutated,
        )
        c_mut = _commitment_of(m_mut)

        assert c_base != c_mut, (
            "TOURNAMENT commitment MUST change when isFullyEligible "
            "flips — ProtocolLens verdict is part of the composition "
            "lattice"
        )


# ---- T-LAYER7-COMP-4: MARKET × LISTING edge -------------------------

def test_t_layer7_comp_4_market_listing_edge(market_compiler, tmp_path):
    """Mutating LISTING commitment MUST change the MARKET commitment."""
    store = _make_store(tmp_path)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)

        m_base = market_compiler.build_marketplace_listing_artifact(
            store=store, output_dir=out, **_MARKET_BASELINE,
        )
        c_base = _commitment_of(m_base)

        mutated = dict(_MARKET_BASELINE)
        mutated["listing_commitment_hex"] = "f" * 64
        m_mut = market_compiler.build_marketplace_listing_artifact(
            store=store, output_dir=out, **mutated,
        )
        c_mut = _commitment_of(m_mut)

        assert c_base != c_mut, (
            "MARKET commitment MUST change when LISTING commitment "
            "changes — LISTING primitive is part of the composition lattice"
        )


# ---- T-LAYER7-COMP-5: MARKET × CONSENT edge -------------------------

def test_t_layer7_comp_5_market_consent_edge(market_compiler, tmp_path):
    """Mutating CONSENT hash MUST change the MARKET commitment. This is
    the GDPR-critical edge: a seller's MARKETPLACE consent state changes
    (granted/revoked), and the listing artifact's commitment MUST
    reflect it."""
    store = _make_store(tmp_path)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)

        m_base = market_compiler.build_marketplace_listing_artifact(
            store=store, output_dir=out, **_MARKET_BASELINE,
        )
        c_base = _commitment_of(m_base)

        mutated = dict(_MARKET_BASELINE)
        mutated["consent_hash_hex"] = "e" * 64
        m_mut = market_compiler.build_marketplace_listing_artifact(
            store=store, output_dir=out, **mutated,
        )
        c_mut = _commitment_of(m_mut)

        assert c_base != c_mut, (
            "MARKET commitment MUST change when CONSENT hash changes "
            "— CONSENT v1 primitive is part of the composition lattice"
        )


# ---- T-LAYER7-COMP-6: cross-composition uniqueness ------------------

def test_t_layer7_comp_6_cross_composition_uniqueness(
    tournament_compiler, market_compiler, tmp_path,
):
    """All 5 composition mutations MUST produce 5 DISTINCT commitments
    (no two edges collapse to the same byte sequence). This is the
    formal exhaustiveness claim: the composition lattice has 5
    independent edges, and every edge produces a structurally distinct
    artifact."""
    store = _make_store(tmp_path)

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)

        # Build the 5 mutated artifacts (one per composition edge).
        mutations = []

        # Edge 1: TOURNAMENT × VHP
        m = dict(_TOURNAMENT_BASELINE)
        m["vhp_token_id"] = 999  # specific mutation
        mutations.append(("tournament_vhp", tournament_compiler, m))

        # Edge 2: TOURNAMENT × GIC head
        m = dict(_TOURNAMENT_BASELINE)
        m["gic_chain_head_hex"] = "a" * 64
        mutations.append(("tournament_gic_head", tournament_compiler, m))

        # Edge 3: TOURNAMENT × ProtocolLens
        m = dict(_TOURNAMENT_BASELINE)
        m["is_fully_eligible"] = False
        mutations.append(("tournament_protocollens", tournament_compiler, m))

        # Edge 4: MARKET × LISTING
        m = dict(_MARKET_BASELINE)
        m["listing_commitment_hex"] = "b" * 64
        mutations.append(("market_listing", market_compiler, m))

        # Edge 5: MARKET × CONSENT
        m = dict(_MARKET_BASELINE)
        m["consent_hash_hex"] = "c" * 64
        mutations.append(("market_consent", market_compiler, m))

        commitments = {}
        for label, compiler_module, inputs in mutations:
            if compiler_module is tournament_compiler:
                manifest = compiler_module.build_tournament_card_artifact(
                    store=store, output_dir=out, **inputs,
                )
            else:
                manifest = compiler_module.build_marketplace_listing_artifact(
                    store=store, output_dir=out, **inputs,
                )
            commitments[label] = _commitment_of(manifest)

        # Assert all 5 are distinct.
        unique = set(commitments.values())
        assert len(unique) == 5, (
            f"Expected 5 distinct commitments across all composition "
            f"edges; got {len(unique)}. Collisions in: {commitments}"
        )


# ---- T-LAYER7-COMP-7: same upstream values reproduce identical commitments

def test_t_layer7_comp_7_reproducibility_under_same_upstream(
    tournament_compiler, market_compiler, tmp_path,
):
    """The complementary determinism property: re-running the compiler
    with identical inputs MUST produce identical commitments. Failure
    here would indicate non-deterministic byte ordering or hidden
    wall-clock dependency."""
    store = _make_store(tmp_path)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)

        # TOURNAMENT twice with same inputs.
        m_t1 = tournament_compiler.build_tournament_card_artifact(
            store=store, output_dir=out, **_TOURNAMENT_BASELINE,
        )
        m_t2 = tournament_compiler.build_tournament_card_artifact(
            store=store, output_dir=out, **_TOURNAMENT_BASELINE,
        )
        assert _commitment_of(m_t1) == _commitment_of(m_t2), (
            "TOURNAMENT compile is non-deterministic — same inputs "
            "produced different commitments"
        )

        # MARKET twice with same inputs.
        m_m1 = market_compiler.build_marketplace_listing_artifact(
            store=store, output_dir=out, **_MARKET_BASELINE,
        )
        m_m2 = market_compiler.build_marketplace_listing_artifact(
            store=store, output_dir=out, **_MARKET_BASELINE,
        )
        assert _commitment_of(m_m1) == _commitment_of(m_m2), (
            "MARKET compile is non-deterministic — same inputs "
            "produced different commitments"
        )
