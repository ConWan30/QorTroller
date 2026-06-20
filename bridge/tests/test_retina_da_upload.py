"""Retina Phase 2b — DA bulk upload for retina_event_log sidecar."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace

import pytest

from bridge.vapi_bridge.config import Config
from bridge.vapi_bridge.replay_proof_pipeline.da_layer import da_router
from bridge.vapi_bridge.retina_da_upload import (
    DA_BULK_SCHEMA,
    build_retina_da_bulk_bytes,
    download_retina_bulk_from_da,
    maybe_upload_retina_to_da,
    upload_retina_bulk_to_da,
)
from bridge.vapi_bridge.retina_perception import RetinaPerceptionResult, persist_retina_result
from bridge.vapi_bridge.retina_state_commitment import compute_retina_state_commitment
from bridge.vapi_bridge.retina_w3bstream import EXIT_OK
from bridge.vapi_bridge.store import Store


@pytest.fixture()
def tmp_store():
    d = tempfile.mkdtemp()
    db = os.path.join(d, "retina_da.db")
    yield Store(db)
    try:
        os.remove(db)
    except OSError:
        pass


def test_build_bulk_schema_and_round_trip():
    events = [{"type": "controller.trigger.onset", "label": "r2"}]
    bulk = build_retina_da_bulk_bytes(
        device_id="dev1",
        ts_ns=1_000,
        events=events,
        world_state_json='{"vec":[0.1]}',
        record_hash_hex="aa" * 32,
    )
    parsed = json.loads(bulk.decode())
    assert parsed["schema"] == DA_BULK_SCHEMA
    commitment = compute_retina_state_commitment("dev1", 1_000, events)
    da_router.clear()
    assert upload_retina_bulk_to_da(commitment, bulk) is True
    got = download_retina_bulk_from_da(commitment)
    assert got == bulk


def test_maybe_upload_skips_when_disabled(tmp_store):
    da_router.clear()
    cfg = replace(Config(), retina_da_upload_enabled=False)
    out = maybe_upload_retina_to_da(
        tmp_store,
        cfg,
        device_id="d",
        record_hash_hex="bb" * 32,
        state_commitment_hex="cc" * 32,
        events=[{"type": "x"}],
        world_state_json="{}",
        ts_ns=1,
        w3bstream_exit_code=EXIT_OK,
    )
    assert out["uploaded"] is False
    assert out["da_upload_enabled"] is False


def test_maybe_upload_writes_log_when_enabled(tmp_store):
    da_router.clear()
    events = [{"type": "controller.stick.radial_jump", "magnitude": 0.3}]
    commitment = compute_retina_state_commitment("dev2", 2_000, events)
    cfg = replace(Config(), retina_da_upload_enabled=True)
    out = maybe_upload_retina_to_da(
        tmp_store,
        cfg,
        device_id="dev2",
        record_hash_hex="dd" * 32,
        state_commitment_hex=commitment,
        events=events,
        world_state_json='{"n":1}',
        ts_ns=2_000,
        w3bstream_exit_code=EXIT_OK,
    )
    assert out["uploaded"] is True
    assert out["payload_bytes"] > 0
    status = tmp_store.get_retina_da_upload_status()
    assert status["latest_uploaded"] is True
    assert download_retina_bulk_from_da(commitment) is not None


def test_maybe_upload_skips_on_w3bstream_failure(tmp_store):
    da_router.clear()
    cfg = replace(Config(), retina_da_upload_enabled=True)
    out = maybe_upload_retina_to_da(
        tmp_store,
        cfg,
        device_id="dev3",
        record_hash_hex="ee" * 32,
        state_commitment_hex="ff" * 32,
        events=[{"type": "x"}],
        world_state_json="{}",
        ts_ns=3,
        w3bstream_exit_code=6,
    )
    assert out["uploaded"] is False
    assert out.get("skipped") == "w3bstream_exit_6"


def test_persist_retina_result_chains_da_upload(tmp_store):
    da_router.clear()
    events = [{"type": "controller.trigger.onset", "label": "l2"}]
    result = RetinaPerceptionResult(
        enabled=True,
        source_id="dev4",
        event_count=1,
        events=events,
        world_state_json='{"ok":true}',
        record_hash_hex="11" * 32,
        state_commitment_hex=compute_retina_state_commitment("dev4", 4, events),
        ts_ns=4,
    )
    cfg = replace(
        Config(),
        retina_w3bstream_validation_enabled=True,
        retina_w3bstream_enforce_on_ingest=False,
        retina_da_upload_enabled=True,
    )
    persist_retina_result(tmp_store, "dev4", result, source="hid", cfg=cfg)
    da_status = tmp_store.get_retina_da_upload_status()
    assert da_status["latest_uploaded"] is True
    w3s = tmp_store.get_retina_w3bstream_status()
    assert int(w3s.get("latest_exit_code") or 0) == EXIT_OK
