"""Run the committed Composite-B evaluator (l9_presence/realplay_liveness.py) against real capture
data via l9_presence/realplay_feature_adapter.py. Off-rig, first real-data run of this module.

Windowing: slides fixed-width windows (default 30s, matching H_W30 in realplay_liveness.py) across
the capture with 50% overlap.

Approximations documented (not hidden): capture_nominal/host_exclusive_usb_or_unknown are injected
True (the recorder's manifest confirms USB dual-connection; this adapter doesn't re-derive PCC
poll-rate stats from raw HID timestamps, which would need the live CaptureHealthMonitor path).
menu_detected is injected False (GAD live-classification not available offline; the operator
confirmed active play throughout run1). Both are stated assumptions, not measurements.

Time base (F-COMPB-TNS-1): this runner ALWAYS writes relative ``t_ms`` (capture-origin = 0). The
adapter prefers ``t_ms`` over absolute epoch ``t_ns`` for window membership — absolute ns is never
comparable to relative window bounds.
"""
import os, sys, json, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from l9_presence.realplay_feature_adapter import extract_window_features
from l9_presence.realplay_liveness import evaluate_realplay_liveness

WINDOW_MS = 30_000.0
STEP_MS = 15_000.0


def _honest_note(has_accel: bool, has_ticks: bool, verdict_counts: dict) -> str:
    """Dynamic, not a hardcoded description of one specific capture (2026-07-22 finding: the
    original version of this note was frozen text about run1's missing-IMU limitation and stayed
    silently stale/wrong once run3 actually had accel+ticks and produced real PARTIAL_PRESENT
    verdicts -- a stale report claim, caught before commit)."""
    if not has_accel or not has_ticks:
        return (
            "This capture predates the IMU/device-clock recorder fix (scripts/u3_raw_capture.py) "
            "-- G3 (tremor) and/or the anti-replay rail layer-1 (device clock) are structurally "
            "unavailable from its HID rows. Fail-closed UNVERIFIABLE output here confirms the "
            "evaluator's existing design correctly refuses to invent a verdict from incomplete "
            "data; it does NOT validate the evaluator end-to-end."
        )
    n_partial = verdict_counts.get("PARTIAL_PRESENT", 0)
    n_continuous = verdict_counts.get("CONTINUOUS_PRESENT", 0)
    if n_partial == 0 and n_continuous == 0:
        return (
            "IMU/device-clock data is present, but no window reached PARTIAL_PRESENT or better -- "
            "check individual window gate_bitmaps for which gate is failing (commonly G3 tremor: no "
            "clean >=2s/256-sample accel segment in that window, or gameplay-fraction/rhythm gates)."
        )
    note = (
        f"IMU/device-clock data present. {n_partial} window(s) reached PARTIAL_PRESENT "
        f"(human-shape + device-clock lock confirmed on real data, explicitly replayable/advisory -- "
        f"optical_consistent is not wired into this offline path, so CONTINUOUS_PRESENT is "
        f"structurally unreachable here regardless of how strong the other gates are)."
    )
    if n_continuous:
        note += (
            f" {n_continuous} window(s) reported CONTINUOUS_PRESENT -- verify this is NOT a bug: "
            f"the offline runner does not compute real optical co-presence, so this should not "
            f"normally happen; investigate before trusting it."
        )
    return note


def run(capture_dir: str) -> dict:
    rows = [json.loads(l) for l in open(os.path.join(capture_dir, "hid_events.jsonl"))]
    t0 = rows[0]["t_ns"]
    for r in rows:
        # Relative window coordinate (adapter prefers t_ms over absolute t_ns — F-COMPB-TNS-1).
        r["t_ms"] = (r["t_ns"] - t0) / 1e6
    span_ms = rows[-1]["t_ms"]

    has_accel = any("accel_x" in r for r in rows)
    has_ticks = any("sensor_ts_ticks" in r for r in rows)

    windows = []
    t = 0.0
    while t + WINDOW_MS <= span_ms:
        f = extract_window_features(rows, t, t + WINDOW_MS)
        rec = evaluate_realplay_liveness(f)
        windows.append({"window_start_s": round(t / 1000.0, 1), "window_end_s": round((t + WINDOW_MS) / 1000.0, 1),
                        **rec.to_dict(), "reason": rec.reason, "gate_bitmap": rec.gate_bitmap})
        t += STEP_MS

    verdict_counts: dict = {}
    for w in windows:
        verdict_counts[w["verdict"]] = verdict_counts.get(w["verdict"], 0) + 1

    report = {
        "capture_dir": capture_dir, "n_hid_rows": len(rows), "span_s": round(span_ms / 1000.0, 1),
        "has_accel_data": has_accel, "has_sensor_ts_ticks": has_ticks,
        "n_windows": len(windows), "verdict_counts": verdict_counts,
        "windows": windows,
        "honest_note": _honest_note(has_accel, has_ticks, verdict_counts),
    }
    out = os.path.join(capture_dir, "realplay_liveness_report.json")
    json.dump(report, open(out, "w"), indent=2)
    report["_out"] = out
    return report

if __name__ == "__main__":
    r = run(sys.argv[1])
    print(json.dumps({k: v for k, v in r.items() if k != "windows"}, indent=2))
