"""WMP UC-8 fleet-telemetry tests. Device-MODEL aggregation with the aggregation floor — the
load-bearing rail: no bucket under min_devices ever discloses stats, and no device_id ever appears in
output (CROSS-LESSON-001: per-unit fingerprinting structurally excluded).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.wmp.fleet_telemetry import (
    DEFAULT_MIN_DEVICES_PER_BUCKET,
    SCHEMA,
    aggregate_fleet_telemetry,
)


def _row(dev, model, lat=180.0, peak=1500.0, verdict="REFLEX_OBSERVED"):
    return {"device_id": dev, "cco_profile_id": model, "latency_ms": lat,
            "accel_delta_peak": peak, "reflex_verdict": verdict}


def test_bucket_above_floor_reports_stats():
    rows = [_row(f"d{i}", "sony_dualshock_edge_v1", lat=100.0 + i * 10) for i in range(4)]
    r = aggregate_fleet_telemetry(rows)
    m = r["models"]["sony_dualshock_edge_v1"]
    assert m["suppressed"] is False
    assert m["n_devices"] == 4
    assert m["latency_ms"]["n"] == 4
    assert m["latency_ms"]["median"] == 115.0
    assert m["verdict_rates"]["REFLEX_OBSERVED"] == 1.0


def test_bucket_below_floor_is_suppressed_entirely():
    # 2 devices < floor 3 -> NO stats disclosed, only the suppression marker
    rows = [_row("d1", "rare_pad_v1"), _row("d2", "rare_pad_v1"), _row("d1", "rare_pad_v1")]
    r = aggregate_fleet_telemetry(rows)
    m = r["models"]["rare_pad_v1"]
    assert m["suppressed"] is True
    assert "latency_ms" not in m and "n_probes" not in m and "n_devices" not in m
    assert r["n_suppressed_buckets"] == 1


def test_no_device_id_ever_appears_in_output():
    rows = ([_row(f"edge-{i}", "sony_dualshock_edge_v1") for i in range(5)]
            + [_row("secret-device-abc", "rare_pad_v1")])
    blob = json.dumps(aggregate_fleet_telemetry(rows))
    for did in ("edge-0", "edge-4", "secret-device-abc"):
        assert did not in blob


def test_untagged_rows_bucket_and_floor_protect():
    rows = [_row(f"d{i}", None) for i in range(2)]
    r = aggregate_fleet_telemetry(rows)
    assert r["models"]["untagged"]["suppressed"] is True


def test_min_devices_configurable_and_disclosed():
    rows = [_row(f"d{i}", "m1") for i in range(3)]
    strict = aggregate_fleet_telemetry(rows, min_devices=5)
    assert strict["models"]["m1"]["suppressed"] is True
    assert strict["min_devices_per_bucket"] == 5
    default = aggregate_fleet_telemetry(rows)
    assert default["models"]["m1"]["suppressed"] is False
    assert default["min_devices_per_bucket"] == DEFAULT_MIN_DEVICES_PER_BUCKET


def test_invalid_measurements_excluded_from_quantiles_not_counts():
    rows = [_row(f"d{i}", "m1", lat=(None if i == 0 else 200.0), peak=(0 if i == 1 else 1000.0))
            for i in range(3)]
    m = aggregate_fleet_telemetry(rows)["models"]["m1"]
    assert m["n_probes"] == 3
    assert m["latency_ms"]["n"] == 2          # None excluded
    assert m["peak_lsb"]["n"] == 2            # 0 excluded


def test_schema_and_rails():
    r = aggregate_fleet_telemetry([])
    assert r["schema"] == SCHEMA
    assert r["device_class_only"] is True
    assert r["per_unit_fingerprinting"] is False
    assert r["n_models"] == 0
