"""Runner: extract CFB play-transition events from a U3 capture dir -> snap_events.jsonl.
Usage: python scripts/cfb_extract_snaps.py <capture_dir>"""
import os, sys, glob, json
import cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from l9_presence.cfb_snap_extractor import (
    ScoreboardROI, Sample, detect_play_events, downdist_signature, scoreboard_present,
)

def run(capture_dir: str) -> dict:
    frames = sorted(glob.glob(os.path.join(capture_dir, "frames", "f_*.jpg")))
    if not frames:
        raise SystemExit(f"no frames in {capture_dir}")
    roi = ScoreboardROI()
    t0 = int(os.path.basename(frames[0])[2:-4])
    samples, present_ct = [], 0
    for fp in frames:
        img = cv2.imread(fp)
        if img is None:
            continue
        ts = (int(os.path.basename(fp)[2:-4]) - t0) / 1e9
        pres = scoreboard_present(img, roi, cv2)
        if pres:
            present_ct += 1
        sig = downdist_signature(img, roi, cv2) if pres else None
        samples.append(Sample(ts_s=ts, present=pres, signature=sig))
    events = detect_play_events(samples)
    out = os.path.join(capture_dir, "snap_events.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e.to_dict()) + "\n")
    return {"frames": len(samples), "present": present_ct, "events": len(events),
            "event_times_s": [round(e.ts_s, 1) for e in events], "out": out}

if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1]), indent=2))
