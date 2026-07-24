"""Retina Phase 3c — DA witness bundle keyed by events_root."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace

import pytest

from bridge.vapi_bridge.config import Config
from bridge.vapi_bridge.replay_proof_pipeline.da_layer import da_router
from bridge.vapi_bridge.retina_da_upload import (
    download_retina_bulk_from_da,
    maybe_upload_retina_to_da,
)
from bridge.vapi_bridge.retina_da_witness import (
    DA_WITNESS_SCHEMA,
    build_retina_witness_bytes,
    download_retina_witness_from_da,
    maybe_upload_retina_witness_to_da,
    upload_retina_witness_to_da,
)
from bridge.vapi_bridge.retina_events_root import (
    EVENTS_ROOT_SCHEME_POSEIDON_V1,
    EVENTS_ROOT_SCHEME_SHA256_V1,
)
from bridge.vapi_bridge.retina_perception import RetinaPerceptionResult, persist_retina_result
from bridge.vapi_bridge.retina_state_commitment import (
    compute_events_root_for_scheme,
    compute_retina_state_commitment,
)
from bridge.vapi_bridge.retina_w3bstream import EXIT_OK
from bridge.vapi_bridge.store import Store


@pytest.fixture()
def tmp_store():
    d = tempfile.mkdtemp()
    db = os.path.join(d, "retina_da_witness.db")
    yield Store(db)
    try:
        os.remove(db)
    except OSError:
        pass


def test_witness_round_trip_by_events_root():
    events = [{"type": "controller.trigger.onset", "label": "r2"}]
    root_hex = compute_events_root_for_scheme(
        events, EVENTS_ROOT_SCHEME_SHA256_V1
    ).hex()
    witness = build_retina_witness_bytes(
        device_id="dev1",
        ts_ns=1_000,
        events=events,
        events_root_hex=root_hex,
        events_root_scheme=EVENTS_ROOT_SCHEME_SHA256_V1,
        record_hash_hex="aa" * 32,
        state_commitment_hex="bb" * 32,
    )
    parsed = json.loads(witness.decode())
    assert parsed["schema"] == DA_WITNESS_SCHEMA
    da_router.clear()
    assert upload_retina_witness_to_da(root_hex, witness) is True
    assert download_retina_witness_from_da(root_hex) == witness


def test_maybe_upload_witness_skips_when_disabled(tmp_store):
    da_router.clear()
    cfg = replace(Config(), retina_da_witness_enabled=False)
    out = maybe_upload_retina_witness_to_da(
        tmp_store,
        cfg,
        device_id="d",
        record_hash_hex="bb" * 32,
        state_commitment_hex="cc" * 32,
        events=[{"type": "x"}],
        ts_ns=1,
        w3bstream_exit_code=EXIT_OK,
    )
    assert out["uploaded"] is False
    assert out["da_witness_enabled"] is False
    status = tmp_store.get_retina_da_witness_status()
    assert status["total_log_rows"] == 0


def test_maybe_upload_witness_skips_on_w3bstream_failure(tmp_store):
    da_router.clear()
    cfg = replace(Config(), retina_da_witness_enabled=True)
    out = maybe_upload_retina_witness_to_da(
        tmp_store,
        cfg,
        device_id="dev3",
        record_hash_hex="ee" * 32,
        state_commitment_hex="ff" * 32,
        events=[{"type": "x"}],
        ts_ns=3,
        w3bstream_exit_code=6,
    )
    assert out["uploaded"] is False
    assert out.get("skipped") == "w3bstream_exit_6"


def test_maybe_upload_witness_writes_log_when_enabled(tmp_store):
    da_router.clear()
    events = [{"type": "controller.stick.radial_jump", "magnitude": 0.3}]
    root_hex = compute_events_root_for_scheme(
        events, EVENTS_ROOT_SCHEME_SHA256_V1
    ).hex()
    cfg = replace(Config(), retina_da_witness_enabled=True)
    out = maybe_upload_retina_witness_to_da(
        tmp_store,
        cfg,
        device_id="dev2",
        record_hash_hex="dd" * 32,
        state_commitment_hex=compute_retina_state_commitment("dev2", 2_000, events),
        events=events,
        ts_ns=2_000,
        w3bstream_exit_code=EXIT_OK,
        events_root_scheme=EVENTS_ROOT_SCHEME_SHA256_V1,
    )
    assert out["uploaded"] is True
    assert out["payload_bytes"] > 0
    assert out["events_root_hex"] == root_hex
    status = tmp_store.get_retina_da_witness_status()
    assert status["latest_uploaded"] is True
    assert status["latest_events_root"] == root_hex
    assert download_retina_witness_from_da(root_hex) is not None


@pytest.mark.skip(reason="circomlibjs not installed (npm ci not run against bridge/vapi_bridge/retina_zk_artifacts in this environment)")
def test_sha256_vs_poseidon_distinct_roots_and_keys(tmp_store):
    events = [{"type": "controller.trigger.onset", "label": "l2"}]
    sha_root = compute_events_root_for_scheme(
        events, EVENTS_ROOT_SCHEME_SHA256_V1
    ).hex()
    poseidon_root = compute_events_root_for_scheme(
        events, EVENTS_ROOT_SCHEME_POSEIDON_V1
    ).hex()
    assert sha_root != poseidon_root
    da_router.clear()
    cfg = replace(Config(), retina_da_witness_enabled=True)
    maybe_upload_retina_witness_to_da(
        tmp_store,
        cfg,
        device_id="dev5",
        record_hash_hex="22" * 32,
        state_commitment_hex="33" * 32,
        events=events,
        ts_ns=5,
        w3bstream_exit_code=EXIT_OK,
        events_root_scheme=EVENTS_ROOT_SCHEME_SHA256_V1,
    )
    maybe_upload_retina_witness_to_da(
        tmp_store,
        cfg,
        device_id="dev5",
        record_hash_hex="22" * 32,
        state_commitment_hex="44" * 32,
        events=events,
        ts_ns=5,
        w3bstream_exit_code=EXIT_OK,
        events_root_scheme=EVENTS_ROOT_SCHEME_POSEIDON_V1,
    )
    assert download_retina_witness_from_da(sha_root) is not None
    assert download_retina_witness_from_da(poseidon_root) is not None
    assert download_retina_witness_from_da(sha_root) != download_retina_witness_from_da(
        poseidon_root
    )


def test_bulk_and_witness_coexist_different_da_keys(tmp_store):
    da_router.clear()
    events = [{"type": "controller.trigger.onset", "label": "cross"}]
    commitment = compute_retina_state_commitment("dev6", 6, events)
    root_hex = compute_events_root_for_scheme(
        events, EVENTS_ROOT_SCHEME_SHA256_V1
    ).hex()
    cfg = replace(
        Config(),
        retina_da_upload_enabled=True,
        retina_da_witness_enabled=True,
    )
    maybe_upload_retina_to_da(
        tmp_store,
        cfg,
        device_id="dev6",
        record_hash_hex="55" * 32,
        state_commitment_hex=commitment,
        events=events,
        world_state_json="{}",
        ts_ns=6,
        w3bstream_exit_code=EXIT_OK,
    )
    maybe_upload_retina_witness_to_da(
        tmp_store,
        cfg,
        device_id="dev6",
        record_hash_hex="55" * 32,
        state_commitment_hex=commitment,
        events=events,
        ts_ns=6,
        w3bstream_exit_code=EXIT_OK,
        events_root_scheme=EVENTS_ROOT_SCHEME_SHA256_V1,
    )
    assert download_retina_bulk_from_da(commitment) is not None
    assert download_retina_witness_from_da(root_hex) is not None
    assert commitment != root_hex


def test_persist_retina_result_chains_witness_upload(tmp_store):
    da_router.clear()
    events = [{"type": "controller.trigger.onset", "label": "l2"}]
    result = RetinaPerceptionResult(
        enabled=True,
        source_id="dev7",
        event_count=1,
        events=events,
        world_state_json='{"ok":true}',
        record_hash_hex="66" * 32,
        state_commitment_hex=compute_retina_state_commitment("dev7", 7, events),
        ts_ns=7,
    )
    cfg = replace(
        Config(),
        retina_w3bstream_validation_enabled=True,
        retina_w3bstream_enforce_on_ingest=False,
        retina_da_witness_enabled=True,
    )
    persist_retina_result(tmp_store, "dev7", result, source="hid", cfg=cfg)
    witness_status = tmp_store.get_retina_da_witness_status()
    assert witness_status["latest_uploaded"] is True
    root_hex = compute_events_root_for_scheme(
        events, EVENTS_ROOT_SCHEME_SHA256_V1
    ).hex()
    assert witness_status["latest_events_root"] == root_hex
    assert download_retina_witness_from_da(root_hex) is not None
