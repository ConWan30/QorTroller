"""WMP UC-8 — Controller-fleet capability telemetry (hardware-partner data product).

Aggregated controller-MODEL capability distributions — trigger/reflex response envelopes and
per-model verification rates — DEVICE data, not gamer data. The audience is hardware vendors /
design houses (the Qorvo outreach precedent) + the HWFL-1 dev-kit lane's own BOM decisions.

HARD RAILS (portfolio ceiling + CROSS-LESSON-001):
  - DEVICE-CLASS statistics ONLY. Never per-gamer, never per-unit: an AGGREGATION FLOOR suppresses
    any model bucket with fewer than `min_devices` distinct devices, so no single controller (or its
    owner) is identifiable. Suppressed buckets report ONLY that they were suppressed + the floor.
  - Per-unit fingerprinting is structurally excluded (CROSS-LESSON-001 same-model separability
    constraint respected): no device_id ever appears in output — only model-level distributions.
  - READ-ONLY over already-captured telemetry (l6b_probe_log CCO rows). No chain, no consent write,
    no biometric export (latency/peak are device-actuation telemetry aggregated at model level).

Pure functions (testable, no DB) + a thin read-only Store adapter.
"""
from __future__ import annotations

SCHEMA = "qortroller-wmp-fleet-telemetry-v0"
DEFAULT_MIN_DEVICES_PER_BUCKET = 3      # aggregation floor: below this, the bucket is suppressed


def _quantiles(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0, "mean": None, "p10": None, "median": None, "p90": None, "min": None, "max": None}
    s = sorted(xs)

    def _pct(p: float) -> float:
        k = (len(s) - 1) * p
        lo = int(k)
        hi = min(lo + 1, len(s) - 1)
        return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 3)

    return {"n": len(s), "mean": round(sum(s) / len(s), 3), "p10": _pct(0.10),
            "median": _pct(0.5), "p90": _pct(0.90), "min": round(s[0], 3), "max": round(s[-1], 3)}


def aggregate_fleet_telemetry(rows: list[dict], *,
                              min_devices: int = DEFAULT_MIN_DEVICES_PER_BUCKET) -> dict:
    """Aggregate per-probe telemetry rows into DEVICE-MODEL buckets with the aggregation floor.

    Each row: {device_id, cco_profile_id, latency_ms, accel_delta_peak, reflex_verdict}. Rows with no
    model tag land in the "untagged" bucket (still floor-protected). Buckets under the floor are
    SUPPRESSED — their stats are withheld entirely (only n_devices<floor is disclosed).
    """
    buckets: dict[str, dict] = {}
    for r in rows:
        model = (r.get("cco_profile_id") or "untagged").strip() or "untagged"
        b = buckets.setdefault(model, {"devices": set(), "latencies": [], "peaks": [],
                                       "verdicts": {}, "n_probes": 0})
        b["n_probes"] += 1
        did = r.get("device_id")
        if did:
            b["devices"].add(str(did))
        lat = r.get("latency_ms")
        if isinstance(lat, (int, float)) and lat > 0:
            b["latencies"].append(float(lat))
        pk = r.get("accel_delta_peak")
        if isinstance(pk, (int, float)) and pk > 0:
            b["peaks"].append(float(pk))
        v = (r.get("reflex_verdict") or "UNKNOWN").strip() or "UNKNOWN"
        b["verdicts"][v] = b["verdicts"].get(v, 0) + 1

    models: dict[str, dict] = {}
    n_suppressed = 0
    for model, b in sorted(buckets.items()):
        n_dev = len(b["devices"])
        if n_dev < min_devices:
            n_suppressed += 1
            models[model] = {"suppressed": True, "reason": f"n_devices<{min_devices} (aggregation floor)",
                             "n_devices_below_floor": True}
            continue
        total = b["n_probes"] or 1
        models[model] = {
            "suppressed": False,
            "n_devices": n_dev,                       # >= floor, safe to disclose
            "n_probes": b["n_probes"],
            "latency_ms": _quantiles(b["latencies"]),
            "peak_lsb": _quantiles(b["peaks"]),
            "verdict_rates": {v: round(c / total, 4) for v, c in sorted(b["verdicts"].items())},
        }

    return {
        "schema": SCHEMA,
        "device_class_only": True,
        "per_unit_fingerprinting": False,
        "min_devices_per_bucket": min_devices,
        "n_models": len(models),
        "n_suppressed_buckets": n_suppressed,
        "models": models,
        "note": "Device-MODEL capability distributions only. Buckets under the aggregation floor are "
                "suppressed so no single controller (or its owner) is identifiable; device_ids never "
                "appear in output. Per-unit fingerprints structurally excluded (CROSS-LESSON-001). "
                "Read-only over captured telemetry; no chain/consent write; not gamer data.",
    }


def fleet_telemetry_from_store(store, *, min_devices: int = DEFAULT_MIN_DEVICES_PER_BUCKET,
                               limit: int = 100_000) -> dict:
    """Read-only Store adapter. Fail-soft: query errors -> empty aggregate, never fabricated."""
    rows: list[dict] = []
    try:
        with store._conn() as conn:  # noqa: SLF001 - read-only SELECT over an existing table
            cur = conn.execute(
                "SELECT device_id, cco_profile_id, latency_ms, accel_delta_peak, reflex_verdict "
                "FROM l6b_probe_log ORDER BY id DESC LIMIT ?", (int(limit),))
            rows = [dict(r) for r in cur.fetchall()]
    except Exception:  # noqa: BLE001 - fail-soft
        rows = []
    return aggregate_fleet_telemetry(rows, min_devices=min_devices)
