"""WMP-1 bundle assembler tests.

T-WMP1-1  fixture bundle assembles with expected channel order + ticks
T-WMP1-2  scope_disclosure FROZEN values always present + correct
T-WMP1-3  extra_metadata with a FORBIDDEN_COLUMNS key raises
          DataFloorViolationError BEFORE any bundle is built
T-WMP1-4  assembler reuses ReplayPreProcessor.FORBIDDEN_COLUMNS verbatim
          (no fork; same frozenset object)
T-WMP1-5  matrix bytes are encoded hex-per-channel; bundle references
          the sanitized matrix (does NOT copy raw HID)
T-WMP1-6  recency dict with empty registry_address surfaces verbatim
          (Arc 6 dormant → consumer verifier handles as
          BEACON_REGISTRY_NOT_DEPLOYED later)
T-WMP1-7  deferred humanity_proof preserves deferred=True +
          deferred_reason; bundle.humanity_deferred bool exposes it
T-WMP1-8  consent_ref defaults: world_model_consent_dimension =
          "DEFERRED" (the W1-D operator decision) when caller omits it
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.wmp import (
    BundleAssembler,
    DataFloorViolationError,
    ProvenanceBundle,
    SCHEMA_VERSION,
)
from vapi_bridge.replay_proof_pipeline.pre_processor import (
    ReplayPreProcessor,
    SanitizedReplayMatrix,
)


def _fixture_matrix(ticks: int = 8) -> SanitizedReplayMatrix:
    """Build a deterministic post-φ matrix for tests. Bytes are zero-
    filled per channel — assembly is structural (sanity), not
    cryptographic."""
    return SanitizedReplayMatrix(
        session_id="fixture-session-0001",
        ticks=ticks,
        stick_L_sector=bytes(ticks),
        stick_R_sector=bytes(ticks),
        trigger_L_state=bytes(ticks),
        trigger_R_state=bytes(ticks),
        button_mask=bytes(ticks * 2),
        imu_gravity_sector=bytes(ticks),
        poac_chain_root=bytes(32),
        vhp_token_id=2,
        humanity_prob_floor=0.71,
        session_verdict="HUMAN",
    )


def _fixture_humanity_proof(deferred: bool = False) -> dict:
    return {
        "proof_type": "VAPI-REPLAY-PROOF-v1",
        "proof_bytes_hex": "0xaa" * 64,
        "public_inputs": {
            "sanitizedTraceRoot": "143000",
            "poacChainRoot":      "0",
        },
        "verifier_address": "0x5182372d1D033db0c9230843DFDE606733D5F91B",
        "deferred": deferred,
        "deferred_reason": "ceremony_pending" if deferred else "",
        "sanitized_trace_root": "143000",
    }


def _fixture_recency(registry_address: str = "") -> dict:
    return {
        "open_block":       44354500,
        "open_block_hash":  "0x" + "11" * 32,
        "close_block":      44354700,
        "close_block_hash": "0x" + "22" * 32,
        "registry_address": registry_address,
    }


def _fixture_consent() -> dict:
    return {
        "registry_address": "0x5F7c8068D0e61818FCD613D47e68a9Ea906a2743",
        "gamer_address":    "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692",
        "manifest_hash":    "0x00d2be8fbd80b9475724f38c858ea6e7d1f690ff893de52d790424bc762ba358",
        # world_model_dimension intentionally omitted — test T-WMP1-8
        # asserts the default DEFERRED W1-D path.
    }


def test_wmp1_1_fixture_assembles():
    asm = BundleAssembler()
    asm.__post_init__()
    bundle = asm.assemble(
        sanitized_matrix=_fixture_matrix(ticks=8),
        humanity_proof=_fixture_humanity_proof(),
        recency=_fixture_recency(),
        consent=_fixture_consent(),
    )
    assert isinstance(bundle, ProvenanceBundle)
    assert bundle.schema == SCHEMA_VERSION
    assert bundle.action_trace_ticks == 8
    assert bundle.action_trace_channels == (
        "stick_L_sector", "stick_R_sector",
        "trigger_L_state", "trigger_R_state",
        "button_mask", "imu_gravity_sector",
    )


def test_wmp1_2_scope_disclosure_frozen_values():
    asm = BundleAssembler(); asm.__post_init__()
    bundle = asm.assemble(
        sanitized_matrix=_fixture_matrix(),
        humanity_proof=_fixture_humanity_proof(),
        recency=_fixture_recency(),
        consent=_fixture_consent(),
    )
    assert bundle.scope_channel == "ACTION_ONLY"
    assert bundle.scope_observation_channel == "ABSENT_BY_DESIGN_DATA_FLOOR"
    assert bundle.scope_fidelity == "MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL"
    assert bundle.scope_synthetic is False
    assert bundle.scope_is_full_pomdp_tuple is False


def test_wmp1_3_forbidden_extra_metadata_raises():
    asm = BundleAssembler(); asm.__post_init__()
    # `l4_mahalanobis_distance` is in FORBIDDEN_COLUMNS — the assembler
    # must refuse it BEFORE the bundle is built.
    bad = {"l4_mahalanobis_distance": 7.009, "innocuous": "ok"}
    with pytest.raises(DataFloorViolationError) as exc_info:
        asm.assemble(
            sanitized_matrix=_fixture_matrix(),
            humanity_proof=_fixture_humanity_proof(),
            recency=_fixture_recency(),
            consent=_fixture_consent(),
            extra_metadata=bad,
        )
    msg = str(exc_info.value)
    assert "l4_mahalanobis_distance" in msg
    assert "FORBIDDEN_COLUMNS" in msg


def test_wmp1_4_assembler_reuses_arc5_frozenset_no_fork():
    asm = BundleAssembler(); asm.__post_init__()
    # SAME frozenset object — identity, not equality. Confirms no fork.
    assert asm.forbidden_columns is ReplayPreProcessor.FORBIDDEN_COLUMNS
    # And carries the canonical members.
    assert "l4_mahalanobis_distance" in asm.forbidden_columns
    assert "ait_rms" in asm.forbidden_columns
    assert "micro_tremor_variance" in asm.forbidden_columns


def test_wmp1_5_matrix_hex_encoded_per_channel():
    asm = BundleAssembler(); asm.__post_init__()
    bundle = asm.assemble(
        sanitized_matrix=_fixture_matrix(ticks=4),
        humanity_proof=_fixture_humanity_proof(),
        recency=_fixture_recency(),
        consent=_fixture_consent(),
    )
    # 4 ticks × 1 byte each → 8 hex chars per single-byte channel
    assert bundle.action_trace_matrix_hex["stick_L_sector"] == "00" * 4
    assert bundle.action_trace_matrix_hex["stick_R_sector"] == "00" * 4
    # button_mask is 2 bytes per tick → 16 hex chars for 4 ticks
    assert bundle.action_trace_matrix_hex["button_mask"] == "00" * 8
    # Hex round-trip: bundle bytes → matrix bytes
    assert bytes.fromhex(bundle.action_trace_matrix_hex["stick_L_sector"]) == bytes(4)


def test_wmp1_6_recency_empty_registry_surfaces_verbatim():
    """Arc 6 dormant — empty registry_address. Bundle must record it as-is
    so the consumer verifier can return BEACON_REGISTRY_NOT_DEPLOYED."""
    asm = BundleAssembler(); asm.__post_init__()
    bundle = asm.assemble(
        sanitized_matrix=_fixture_matrix(),
        humanity_proof=_fixture_humanity_proof(),
        recency=_fixture_recency(registry_address=""),
        consent=_fixture_consent(),
    )
    assert bundle.recency_registry_address == ""
    # Block fields are still populated (the session HAD a recency claim;
    # what's missing is the on-chain registry to verify it against).
    assert bundle.recency_open_block == 44354500
    assert bundle.recency_close_block == 44354700


def test_wmp1_7_deferred_humanity_proof_preserved():
    asm = BundleAssembler(); asm.__post_init__()
    bundle = asm.assemble(
        sanitized_matrix=_fixture_matrix(),
        humanity_proof=_fixture_humanity_proof(deferred=True),
        recency=_fixture_recency(),
        consent=_fixture_consent(),
    )
    assert bundle.humanity_deferred is True
    assert bundle.humanity_deferred_reason == "ceremony_pending"


def test_wmp1_8_world_model_consent_dimension_defaults_to_deferred():
    """W1-D operator decision: in v1 the WMP consent dimension is
    DEFERRED. The assembler's default when consent dict omits the field
    must be exactly 'DEFERRED' so the exporter's deferred-export guard
    has a known string to gate on."""
    asm = BundleAssembler(); asm.__post_init__()
    bundle = asm.assemble(
        sanitized_matrix=_fixture_matrix(),
        humanity_proof=_fixture_humanity_proof(),
        recency=_fixture_recency(),
        consent=_fixture_consent(),
    )
    assert bundle.world_model_consent_dimension == "DEFERRED"
    assert bundle.world_model_consent_registry == ""
