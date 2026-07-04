#!/usr/bin/env python3
"""D-PKG-1(b') parity re-check: rapidocr-onnxruntime (bundled ch_PP-OCRv3_rec) vs the D-ENGINE-1-validated
PP-OCRv5_mobile. RUN UNDER vbko (rapidocr installed there). Reuses the bake-off's SHARED localization + gate
so recognition is the only variable. Scores the SAME 4 corpora; compares to the FROZEN v5_mobile numbers.
Pre-registration (parity threshold) frozen in docs/recognition-engine-bakeoff-2026-07-03.md before this ran.
"""
from __future__ import annotations
import glob
import importlib.util
import json
import os
import statistics as st
import sys
import time

_REPO = r"C:\Users\Contr\vapi-pebble-prototype"
for p in (_REPO, os.path.join(_REPO, "bridge"), os.path.join(_REPO, "scripts")):
    sys.path.insert(0, p)
import cv2  # noqa: E402
_spec = importlib.util.spec_from_file_location("rbo", os.path.join(_REPO, "scripts", "recognition_bakeoff.py"))
rbo = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(rbo)  # noqa: E402
from rapidocr import RapidOCR  # noqa: E402  (newer package: bundles PP-OCRv6_rec_small.onnx, onnxruntime)

# frozen v5_mobile numbers from the bake-off (the parity target). Challenger = PP-OCRv6_rec_small (NEWER).
V5 = {"b2trace_pos": 18, "seg3_pos": 8, "a1spectate_neg": 0, "splice_neg": 80}
V5_WINDOWS = (4, 5)   # v5 caught 4/5 present b2trace kill-event windows


def recog_rapidocr(eng, up):
    res = eng(up, use_det=False, use_cls=False, use_rec=True)
    txts = getattr(res, "txts", None)
    scores = getattr(res, "scores", None)
    if txts:
        return str(txts[0]), (float(scores[0]) if scores else 0.0)
    return "", 0.0


def main():
    eng = RapidOCR()
    out_jsonl = os.path.join(_REPO, "audits", "rbo_rapidocr_2026-07-03_r2.jsonl")
    fh = open(out_jsonl, "w", encoding="utf-8")
    corpora = rbo._corpora()
    summary = {}
    for name, paths in corpora.items():
        loc = read = 0
        lat = []
        rows = []
        for i, p in enumerate(paths):
            img = cv2.imread(p)
            if img is None:
                continue
            l = rbo.shared_locate_crop(img)
            rec = {"corpus": name, "crop": os.path.basename(p), "ts_ms": rbo._crop_ms(p), "located": l is not None}
            if l is not None:
                loc += 1
                t0 = time.time()
                txt, sc = recog_rapidocr(eng, l[1])
                lat.append((time.time() - t0) * 1000)
                hit = rbo.gate(txt)
                read += hit
                rec.update({"locate_score": round(l[0], 3), "text": txt, "score": round(sc, 4),
                            "own_kill": hit, "lat_ms": round(lat[-1], 1)})
            fh.write(json.dumps(rec) + "\n")
            rows.append(rec)
            if (i + 1) % 100 == 0:
                print(f"[rapidocr] {name} {i+1}/{len(paths)} located={loc} read={read}", file=sys.stderr, flush=True)
        summary[name] = {"n": len(paths), "located": loc, "reads": read,
                         "lat_med": round(st.median(lat), 0) if lat else None,
                         "v5_reads": V5[name], "parity_recall": read >= V5[name] if name.endswith("_pos") else None}
        print(f"[rapidocr] {name}: located={loc} reads={read} (v5={V5[name]}) lat_med="
              f"{summary[name]['lat_med']}ms", file=sys.stderr, flush=True)
    fh.close()

    # b2trace window-level catch
    from issue_kas_records import parse_log
    s, _, _, _ = parse_log(sorted(glob.glob(os.path.join(_REPO, "retina_daemon_b2trace_*.log")))[-1])
    a, b = s[0] - 5000, s[1] + 120000
    seen, wins = set(), []
    for line in open(os.path.join(_REPO, "retina_kf_composite.jsonl"), encoding="utf-8"):
        c = json.loads(line)
        if c.get("verdict") == "AUTHORED_PRESENT" and isinstance(c.get("ts_ms"), (int, float)) and a <= c["ts_ms"] <= b:
            k = (c.get("window_gate_ms"), c.get("composite_score"))
            if k not in seen:
                seen.add(k); wins.append((c["window_gate_ms"], c["window_end_ms"]))
    R = {}
    for line in open(out_jsonl, encoding="utf-8"):
        r = json.loads(line)
        if r["corpus"] == "b2trace_pos":
            R[r["crop"]] = r
    present = caught = 0
    for g, e in wins:
        cr = [r for r in R.values() if g <= r.get("ts_ms", -1) <= e]
        if not cr:
            continue
        present += 1
        caught += any(r.get("own_kill") for r in cr)
    summary["b2trace_windows"] = {"present": present, "caught": caught, "v5_caught": V5_WINDOWS[0]}

    # PARITY VERDICT (pre-registered): B2 no-regression every rendering + B1 zero-false both negs + B5<=250
    b2_ok = (summary["b2trace_pos"]["reads"] >= V5["b2trace_pos"] and caught >= V5_WINDOWS[0]
             and summary["seg3_pos"]["reads"] >= V5["seg3_pos"])
    # B1: hallucinated reads on negatives — reported raw; adjudication (genuine own-kill vs hallucination) is eyeball
    b1_note = f"a1spectate reads={summary['a1spectate_neg']['reads']} splice reads(=B8)={summary['splice_neg']['reads']}"
    all_lat = summary["b2trace_pos"]["lat_med"]
    verdict = {"B2_no_regression": b2_ok, "B1_neg_reads": b1_note,
               "B5_ok": bool(all_lat and all_lat <= 250), "B8_rapidocr_splice": summary["splice_neg"]["reads"],
               "PARITY": "needs-adjudication (B2 " + ("PASS" if b2_ok else "FAIL") + ")"}
    summary["_verdict"] = verdict
    with open(os.path.join(_REPO, "audits", "rapidocr_parity_2026-07-03.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
