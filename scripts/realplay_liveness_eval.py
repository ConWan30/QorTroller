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
        "honest_note": (
            "run1_cfb27 predates the IMU/device-clock recorder fix (u3_raw_capture.py, 2026-07-22) -- "
            "G3 (tremor) and the anti-replay rail layer-1 (device clock) are structurally unavailable "
            "from this capture's HID rows. UNVERIFIABLE-heavy output here confirms the evaluator's "
            "existing fail-closed design correctly refuses to invent a verdict from incomplete data; "
            "it does NOT validate the evaluator end-to-end (that needs a capture from the fixed "
            "recorder with real accel/gyro/sensor_ts_ticks present)."
        ),
    }
    out = os.path.join(capture_dir, "realplay_liveness_report.json")
    json.dump(report, open(out, "w"), indent=2)
    report["_out"] = out
    return report

if __name__ == "__main__":
    r = run(sys.argv[1])
    print(json.dumps({k: v for k, v in r.items() if k != "windows"}, indent=2))
