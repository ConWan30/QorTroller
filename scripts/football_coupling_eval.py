"""B1-B4: run field-motion + multi-input coupling against a real U3 capture, report a real number.

Held-out threshold discipline (grok r02): energy_threshold is NOT the full-session percentile of
the scored series. We compute it from the FIRST THIRD of the capture only (train) and evaluate
onset detection on the FULL series (the train segment's samples are still scored, which is a mild
leak vs a true holdout, but avoids the worse look-ahead of a whole-file percentile — documented,
not hidden).
"""
import os, sys, glob, json
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from l9_presence.football_event_coupling import (
    MotionSample, HidSample, detect_field_motion_onsets, extract_multi_input_onsets,
    extract_r2_onsets, football_fixed_window_coupling, football_adaptive_lag_coupling,
    events_from_ts_s, suggest_energy_threshold,
)
from l9_presence.optical_copresence import TimedEvent

def field_crop(img):
    h, w = img.shape[:2]
    return img[int(h*0.12):int(h*0.82), int(w*0.08):int(w*0.92)]  # grok's expand-round ROI

def run(capture_dir: str) -> dict:
    frames = sorted(glob.glob(os.path.join(capture_dir, "frames", "f_*.jpg")))
    t0 = int(os.path.basename(frames[0])[2:-4])
    motion = []
    prev = None
    for fp in frames:
        img = cv2.imread(fp)
        if img is None:
            continue
        t = (int(os.path.basename(fp)[2:-4]) - t0) / 1e9
        g = cv2.resize(cv2.cvtColor(field_crop(img), cv2.COLOR_BGR2GRAY), (160, 90))
        if prev is not None:
            motion.append(MotionSample(t, float(np.mean(np.abs(g.astype(int) - prev.astype(int))))))
        prev = g

    # HELD-OUT thr: percentile-90 computed from the first third only (train segment)
    span = motion[-1].ts_s
    train = [m for m in motion if m.ts_s < span / 3.0]
    thr = suggest_energy_threshold(train, percentile=90.0)
    field_events = detect_field_motion_onsets(motion, energy_threshold=thr, debounce_s=2.0)

    hid_rows = [json.loads(l) for l in open(os.path.join(capture_dir, "hid_events.jsonl"))]
    ht0 = hid_rows[0]["t_ns"]
    samples = [HidSample(t_ms=(r["t_ns"] - ht0) / 1e6, l2=r["l2"], r2=r["r2"],
                         lx=r["lx"], ly=r["ly"], rx=r["rx"], ry=r["ry"]) for r in hid_rows]
    r2_only = extract_r2_onsets(samples)
    multi = extract_multi_input_onsets(samples)

    gt_rows = [json.loads(l) for l in open(os.path.join(capture_dir, "ground_truth_transitions.jsonl"))]
    gt_events = events_from_ts_s([r["ts_s"] for r in gt_rows if r["kind"] == "downdist_text_change"], "gt_downdist")
    snap_rows = [json.loads(l) for l in open(os.path.join(capture_dir, "snap_events.jsonl"))]
    snap_events = events_from_ts_s([r["ts_s"] for r in snap_rows], "detector_downdist")

    windows = [(0.0, 8000.0), (500.0, 8000.0), (100.0, 1500.0), (150.0, 600.0), (200.0, 2000.0)]
    baselines = {
        "A_GT_downdist + R2only": (gt_events, r2_only),
        "B_detector_downdist + R2only": (snap_events, r2_only),
        "C_field_motion + R2only": (field_events, r2_only),
        "D_field_motion + multi_input": (field_events, multi),
    }
    report = {"n_motion_samples": len(motion), "held_out_thr": round(thr, 2),
             "n_field_events": len(field_events), "n_gt_events": len(gt_events),
             "n_detector_events": len(snap_events), "n_r2_onsets": len(r2_only),
             "n_multi_onsets": len(multi), "fixed_window_table": {}}
    for name, (ev, rp) in baselines.items():
        row = {}
        for lo, hi in windows:
            res = football_fixed_window_coupling(ev, rp, reaction_window_ms=(lo, hi))
            row[f"{lo:.0f}-{hi:.0f}ms"] = {"hit": res.hit_rate, "null_q": res.null_q,
                                            "coupled": res.event_coupled}
        report["fixed_window_table"][name] = row

    # B5: if D (field+multi) stayed at-null everywhere, try matched-adaptive
    d_all_null = all(not v["coupled"] for v in report["fixed_window_table"]["D_field_motion + multi_input"].values())
    if d_all_null:
        adapt = football_adaptive_lag_coupling(field_events, multi, lag_search_ms=(0.0, 8000.0), bin_width_ms=500.0)
        report["adaptive_D2_on_field_multi"] = adapt.to_dict()

    out = os.path.join(capture_dir, "football_coupling_report.json")
    json.dump(report, open(out, "w"), indent=2)
    report["_out"] = out
    return report

if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1]), indent=2))
