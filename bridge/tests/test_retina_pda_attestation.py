"""Retina Phase 2c — RETINA_PERCEPTION_OBSERVATION PDA attestation."""

from __future__ import annotations

import os
import tempfile
from dataclasses import replace

import pytest

from bridge.vapi_bridge.config import Config
from bridge.vapi_bridge.physical_data_attestation import (
    RETINA_PERCEPTION_OBSERVATION,
    attestation_type_from_string,
    compute_pda_hash,
)
from bridge.vapi_bridge.operator_initiative_auto_supersede import _canonical_agent_id_bytes
from bridge.vapi_bridge.retina_pda_attestation import maybe_record_retina_pda_attestation
from bridge.vapi_bridge.retina_perception import RetinaPerceptionResult, persist_retina_result
from bridge.vapi_bridge.retina_state_commitment import compute_retina_state_commitment
from bridge.vapi_bridge.retina_w3bstream import EXIT_OK
from bridge.vapi_bridge.store import Store


@pytest.fixture()
def tmp_store():
    d = tempfile.mkdtemp()
    db = os.path.join(d, "retina_pda.db")
    yield Store(db)
    try:
        os.remove(db)
    except OSError:
        pass


def test_pda_hash_retina_perception_observation():
    hw = bytes.fromhex("aa" * 32)
    agent = _canonical_agent_id_bytes("bridge_agent")
    at_hash = attestation_type_from_string(RETINA_PERCEPTION_OBSERVATION)
    h1 = compute_pda_hash(hw, agent, at_hash, 9_000)
    h2 = compute_pda_hash(hw, agent, at_hash, 9_000)
    assert h1 == h2
    assert len(h1) == 32


def test_maybe_record_skips_when_disabled(tmp_store):
    cfg = replace(Config(), retina_pda_attestation_enabled=False)
    out = maybe_record_retina_pda_attestation(
        tmp_store,
        cfg,
        device_id="d1",
        state_commitment_hex="bb" * 32,
        ts_ns=1,
        w3bstream_exit_code=EXIT_OK,
    )
    assert out["recorded"] is False
    status = tmp_store.get_physical_data_attestation_status()
    assert int(status.get("total_attestations") or 0) == 0


def test_maybe_record_writes_log_when_enabled(tmp_store):
    commitment = "cc" * 32
    cfg = replace(Config(), retina_pda_attestation_enabled=True)
    out = maybe_record_retina_pda_attestation(
        tmp_store,
        cfg,
        device_id="d2",
        state_commitment_hex=commitment,
        ts_ns=2_000,
        w3bstream_exit_code=EXIT_OK,
    )
    assert out["recorded"] is True
    assert out["pda_commitment"]
    status = tmp_store.get_physical_data_attestation_status()
    assert int(status.get("total_attestations") or 0) >= 1
    assert status.get("latest_attestation_type") == RETINA_PERCEPTION_OBSERVATION


def test_maybe_record_skips_on_w3bstream_failure(tmp_store):
    cfg = replace(Config(), retina_pda_attestation_enabled=True)
    out = maybe_record_retina_pda_attestation(
        tmp_store,
        cfg,
        device_id="d3",
        state_commitment_hex="dd" * 32,
        ts_ns=3,
        w3bstream_exit_code=6,
    )
    assert out["recorded"] is False
    assert out.get("skipped") == "w3bstream_exit_6"


def test_persist_retina_result_chains_pda_attestation(tmp_store):
    events = [{"type": "controller.trigger.onset", "label": "r2"}]
    commitment = compute_retina_state_commitment("dev-pda", 5_000, events)
    result = RetinaPerceptionResult(
        enabled=True,
        source_id="dev-pda",
        event_count=1,
        events=events,
        world_state_json="{}",
        record_hash_hex="11" * 32,
        state_commitment_hex=commitment,
        ts_ns=5_000,
    )
    cfg = replace(
        Config(),
        retina_w3bstream_validation_enabled=True,
        retina_w3bstream_enforce_on_ingest=False,
        retina_da_upload_enabled=False,
        retina_pda_attestation_enabled=True,
    )
    persist_retina_result(tmp_store, "dev-pda", result, source="test", cfg=cfg)
    status = tmp_store.get_physical_data_attestation_status()
    assert status.get("latest_attestation_type") == RETINA_PERCEPTION_OBSERVATION
    hist = tmp_store.get_physical_data_attestation_history(
        attestation_type=RETINA_PERCEPTION_OBSERVATION,
        limit=3,
    )
    assert len(hist) >= 1


def test_duplicate_pda_insert_idempotent(tmp_store):
    commitment = "ee" * 32
    cfg = replace(Config(), retina_pda_attestation_enabled=True)
    kwargs = dict(
        store=tmp_store,
        cfg=cfg,
        device_id="d4",
        state_commitment_hex=commitment,
        ts_ns=4_000,
        w3bstream_exit_code=EXIT_OK,
    )
    first = maybe_record_retina_pda_attestation(**kwargs)
    second = maybe_record_retina_pda_attestation(**kwargs)
    assert first["recorded"] is True
    assert second["recorded"] is True
    assert first["pda_commitment"] == second["pda_commitment"]
    status = tmp_store.get_physical_data_attestation_status()
    assert int(status.get("total_attestations") or 0) == 1
