"""CCO Phase F — on-chain composability preparation tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from vapi_bridge.cco_composability import (
    InMemoryPoEPComposabilityReader,
    apply_composability_to_grid,
    assemble_composability_status,
    compute_composable_claim_hash,
    resolve_poep_commitment,
)


class TestComputeComposableClaimHash:
    def test_deterministic_with_fixed_ts(self):
        h1 = compute_composable_claim_hash(
            device_id="dev123",
            identity_class="PATH_B_HOST_KEY",
            presence_tier="P-T2",
            poep_commitment=b"\xab" * 32,
            is_fully_eligible=False,
            ts_ns=1700000000000000000,
        )
        h2 = compute_composable_claim_hash(
            device_id="dev123",
            identity_class="PATH_B_HOST_KEY",
            presence_tier="P-T2",
            poep_commitment=b"\xab" * 32,
            is_fully_eligible=False,
            ts_ns=1700000000000000000,
        )
        assert h1 == h2
        assert len(h1) == 32

    def test_eligible_bit_changes_hash(self):
        base = dict(
            device_id="dev123",
            identity_class="I1_SILICON",
            presence_tier="P-T3",
            ts_ns=1700000000000000000,
        )
        h0 = compute_composable_claim_hash(**base, is_fully_eligible=False)
        h1 = compute_composable_claim_hash(**base, is_fully_eligible=True)
        assert h0 != h1

    def test_missing_poep_commitment_zero_pads(self):
        h_none = compute_composable_claim_hash(
            device_id="dev123",
            identity_class="I0_SOFTWARE",
            presence_tier="P-T0",
            poep_commitment=None,
            ts_ns=1,
        )
        h_zero = compute_composable_claim_hash(
            device_id="dev123",
            identity_class="I0_SOFTWARE",
            presence_tier="P-T0",
            poep_commitment=b"\x00" * 32,
            ts_ns=1,
        )
        assert h_none == h_zero


class TestResolvePoepCommitment:
    def test_happy_path(self):
        reader = InMemoryPoEPComposabilityReader()
        cmt = b"\xcd" * 32
        reader.register("devX", cmt)
        got, recorded = resolve_poep_commitment(reader, "devX")
        assert got == cmt
        assert recorded is True

    def test_missing_registration_fail_closed(self):
        reader = InMemoryPoEPComposabilityReader()
        got, recorded = resolve_poep_commitment(reader, "missing")
        assert got is None
        assert recorded is None


class TestAssembleComposabilityStatus:
    def test_disabled_default(self):
        status = assemble_composability_status(
            enabled=False,
            registry_deployed=False,
        )
        assert status["enabled"] is False
        assert status["readiness"] == "disabled"
        assert status["composable_on_chain"] is False
        assert status["option"] == "F1"

    def test_prep_only_when_registry_undeployed(self):
        status = assemble_composability_status(
            enabled=True,
            registry_deployed=False,
            device_id="devX",
            identity_class="I1_SILICON",
            presence_tier="P-T3",
        )
        assert status["readiness"] == "registry_undeployed"
        assert status["composable_claim_hash"].startswith("0x")

    def test_off_chain_verifiable_with_registry(self):
        cmt = b"\x01" * 32
        status = assemble_composability_status(
            enabled=True,
            registry_deployed=True,
            device_id="devX",
            identity_class="I1_SILICON",
            presence_tier="P-T2",
            poep_commitment=cmt,
            poep_commitment_recorded=True,
            ts_ns=42,
        )
        assert status["readiness"] == "off_chain_verifiable"
        assert status["poep_commitment_hex"] == "0x" + cmt.hex()

    def test_path_b_pt3_tournament_blocked(self):
        status = assemble_composability_status(
            enabled=True,
            registry_deployed=True,
            device_id="devX",
            identity_class="PATH_B_HOST_KEY",
            presence_tier="P-T3",
            poep_commitment=b"\x02" * 32,
            poep_commitment_recorded=True,
        )
        assert status["readiness"] == "tournament_blocked_path_b"


class TestApplyComposabilityToGrid:
    def test_merges_phase_f_fields(self):
        grid = {
            "schema": "qortroller-identity-grid-v1",
            "identity_class": "I1_SILICON",
            "composable_on_chain": False,
        }
        comp = assemble_composability_status(
            enabled=True,
            registry_deployed=True,
            device_id="devX",
            identity_class="I1_SILICON",
            presence_tier="P-T2",
            poep_commitment=b"\x03" * 32,
            poep_commitment_recorded=True,
            ts_ns=99,
        )
        merged = apply_composability_to_grid(grid, comp)
        assert merged["composability_readiness"] == "off_chain_verifiable"
        assert merged["composable_claim_hash"].startswith("0x")
        assert merged["composability"]["schema"] == "qortroller-composability-v1"
        assert merged["composable_on_chain"] is False
