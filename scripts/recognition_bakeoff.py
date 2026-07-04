#!/usr/bin/env python3
"""Recognition-engine bake-off — paddle_svtr_v1 vs tesseract_row_v1 (Phase 2 scoring; archive-only).

Pre-registration FROZEN in docs/recognition-engine-bakeoff-2026-07-03.md — this script appends results only.

PROCESS ISOLATION (REQUIRED, not just tidy): loading paddlepaddle in-process BREAKS pytesseract (measured:
8/8 False on a crop the shipped reader reads True once paddle's oneDNN/DLL env loads). A co-loaded run would
score Tesseract at ~0 recall — a fraudulent Paddle win. So each engine runs in its OWN process:
  tesseract:  <repo>/python  scripts/recognition_bakeoff.py --engine tesseract   (NO paddle import)
  paddle:     C:/Users/Contr/vbko/Scripts/python  scripts/recognition_bakeoff.py --engine paddle
  report:     <repo>/python  scripts/recognition_bakeoff.py --report

Recognition is the ONLY variable: ONE shared, DETERMINISTIC localization (killer_slot_best loose-locate
>=0.40 — identical crops across processes) + ONE crop + ONE 4x upscale; both recognizers pass the SAME
canon()+killer-slot gate. Same abstain law: below cutoff / no canon match -> UNRESOLVED, never a guess.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, r"C:\Users\Contr\vapi-pebble-prototype")
sys.path.insert(0, r"C:\Users\Contr\vapi-pebble-prototype\bridge")
sys.path.insert(0, r"C:\Users\Contr\vapi-pebble-prototype\scripts")

import cv2  # noqa: E402
from l9_presence import killfeed_cv as kc  # noqa: E402
from l9_presence.killfeed_authorship import canon, default_handle  # noqa: E402

_REPO = r"C:\Users\Contr\vapi-pebble-prototype"
_HANDLE = canon(default_handle())
_YGATE = 0.75
_LOCATE_MIN = 0.40
_PADDLE_CUTOFF = 0.50            # frozen on the held-out slice (recorded by --engine paddle before full pass)
_CTS = re.compile(r"panel_(\d+)")
_AUD = os.path.join(_REPO, "audits")
_TAG = os.environ.get("RBO_TAG", "")           # run suffix (sidesteps a stale file lock on a prior run)
_ANCHOR = kc.load_anchor(os.path.join(_REPO, "l9_presence/assets/own_handle_anchor_feed.png"))


def _crop_ms(p):
    m = _CTS.search(os.path.basename(p))
    return int(m.group(1)) / 1e6 if m else 0.0


def shared_locate_crop(img):
    score, cxf, cyf = kc.killer_slot_best(img, _ANCHOR, feed_region_max_yfrac=_YGATE)
    if cxf is None or cyf is None or score < _LOCATE_MIN:
        return None
    h, w = img.shape[:2]
    px, py = int(cxf * w), int(cyf * h)
    crop = img[max(0, py - 16):min(h, py + 16), max(0, px - 95):min(w, px + 120)]
    if crop.size == 0:
        return None
    return score, cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)


def gate(text):
    return bool(_HANDLE) and _HANDLE in canon(text)


def recog_tesseract(up):
    import pytesseract
    g = cv2.threshold(cv2.cvtColor(up, cv2.COLOR_BGR2GRAY), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    best = ""
    for im in (g, 255 - g):
        try:
            txt = pytesseract.image_to_string(im, config="--psm 7").strip()
        except Exception:
            txt = ""
        if _HANDLE and _HANDLE in canon(txt):
            return txt, 1.0
        if txt and not best:
            best = txt
    return best, 0.0


def recog_paddle(model, up):
    out = model.predict(input=up)
    if not out:
        return "", 0.0, []
    d = out[0] if isinstance(out[0], dict) else getattr(out[0], "res", out[0])
    try:
        keys = list(d.keys())
    except Exception:
        keys = []
    return str(d.get("rec_text", "")), float(d.get("rec_score", 0.0) or 0.0), keys


def ring_in_span(label):
    from issue_kas_records import parse_log
    logs = sorted(glob.glob(os.path.join(_REPO, f"retina_daemon_{label}_*.log")))
    s, _, _, _ = parse_log(logs[-1])
    a, b = s[0] - 5000, s[1] + 120000
    return [p for p in sorted(glob.glob(os.path.join(_REPO, "retina_kf_crops", "panel_*.png")),
                              key=_crop_ms) if a <= _crop_ms(p) <= b]


def _corpora():
    return {"b2trace_pos": ring_in_span("b2trace"), "a1spectate_neg": ring_in_span("a1spectate"),
            "seg3_pos": sorted(glob.glob(os.path.join(_REPO, "retina_kf_archive",
                                                      "seg3_20260701_052921", "*.png"))),
            "splice_neg": sorted(glob.glob(os.path.join(_REPO, "retina_kf_adv_splice", "*.png")))}


def run_engine(engine):
    model = None
    if engine == "tesseract":
        from l9_presence import hud_ocr           # sets pytesseract.tesseract_cmd (bare pytesseract can't
        hud_ocr.ocr_available()                   # find tesseract.exe in the repo env) — else silent 0 reads
        # STARTUP SELF-CHECK: read a known-good crop; abort LOUD if the engine can't (never a silent 0-read
        # garbage run again — this failure mode has bitten twice: paddle-contamination + missing tesseract_cmd).
        _chk = cv2.imread(os.path.join(_REPO, "retina_kf_crops", "panel_1783114494027671900.png"))
        _loc = shared_locate_crop(_chk) if _chk is not None else None
        if _loc is None or not gate(recog_tesseract(_loc[1])[0]):
            print("[tesseract] SELF-CHECK FAILED — engine cannot read the known crop; ABORTING (would be an "
                  "unfair 0-read run). Check tesseract_cmd / install.", file=sys.stderr, flush=True)
            sys.exit(3)
        print("[tesseract] self-check PASSED (read the known crop)", file=sys.stderr, flush=True)
    if engine == "paddle":
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        from paddleocr import TextRecognition
        model = TextRecognition(model_name="PP-OCRv5_mobile_rec")
    out_path = os.path.join(_AUD, f"rbo_{engine}_2026-07-03{_TAG}.jsonl")
    fh = open(out_path, "w", encoding="utf-8")
    corpora = _corpora()
    # held-out cutoff tuning (paddle only): first 60 b2trace crops -> record min handle-read score
    if engine == "paddle":
        hits = []
        for p in corpora["b2trace_pos"][:60]:
            loc = shared_locate_crop(cv2.imread(p))
            if loc is None:
                continue
            txt, sc, _ = recog_paddle(model, loc[1])
            if gate(txt):
                hits.append(sc)
        print(f"[paddle] held-out(60): handle-reads={len(hits)} min_score="
              f"{min(hits) if hits else None} -> frozen cutoff={_PADDLE_CUTOFF}", file=sys.stderr, flush=True)
    for name, paths in corpora.items():
        loc_n = read_n = 0
        for i, p in enumerate(paths):
            img = cv2.imread(p)
            if img is None:
                continue
            loc = shared_locate_crop(img)
            rec = {"corpus": name, "crop": os.path.basename(p), "ts_ms": _crop_ms(p), "located": loc is not None}
            if loc is not None:
                loc_n += 1
                t0 = time.time()
                if engine == "tesseract":
                    txt, sc = recog_tesseract(loc[1])
                    keys = None
                else:
                    txt, sc, keys = recog_paddle(model, loc[1])
                lat = (time.time() - t0) * 1000
                hit = gate(txt) and (engine == "tesseract" or sc >= _PADDLE_CUTOFF)
                read_n += hit
                rec.update({"locate_score": round(loc[0], 3), "text": txt, "score": round(sc, 4),
                            "own_kill": hit, "lat_ms": round(lat, 1)})
                if keys is not None:
                    rec["paddle_keys"] = keys
            fh.write(json.dumps(rec) + "\n")
            if (i + 1) % 50 == 0:
                print(f"[{engine}] {name} {i+1}/{len(paths)} located={loc_n} own_kill={read_n}",
                      file=sys.stderr, flush=True)
        print(f"[{engine}] {name}: n={len(paths)} located={loc_n} own_kill={read_n}", file=sys.stderr, flush=True)
    fh.close()
    print(f"[{engine}] wrote {out_path}")


def _load(engine):
    rows = {}
    with open(os.path.join(_AUD, f"rbo_{engine}_2026-07-03{_TAG}.jsonl"), encoding="utf-8") as fh:
        for l in fh:
            r = json.loads(l)
            rows[(r["corpus"], r["crop"])] = r
    return rows


def _b2trace_windows():
    from issue_kas_records import parse_log
    logs = sorted(glob.glob(os.path.join(_REPO, "retina_daemon_b2trace_*.log")))
    s, _, _, _ = parse_log(logs[-1])
    a, b = s[0] - 5000, s[1] + 120000
    seen, wins = set(), []
    for l in open(os.path.join(_REPO, "retina_kf_composite.jsonl"), encoding="utf-8"):
        c = json.loads(l)
        if c.get("verdict") == "AUTHORED_PRESENT" and isinstance(c.get("ts_ms"), (int, float)) and a <= c["ts_ms"] <= b:
            k = (c.get("window_gate_ms"), c.get("composite_score"))
            if k not in seen:
                seen.add(k)
                wins.append((c["window_gate_ms"], c["window_end_ms"]))
    return wins


def report():
    import statistics as st
    T, P = _load("tesseract"), _load("paddle")
    keys = sorted(set(T) | set(P))
    corpora = sorted({k[0] for k in keys})
    rep = {"engines": ["tesseract_row_v1", "paddle_svtr_v1"], "paddle_cutoff": _PADDLE_CUTOFF, "corpora": {}}

    # B7 capability probe from a paddle row
    sample = next((P[k] for k in P if P[k].get("paddle_keys")), {})
    rep["B7_paddle_keys"] = sample.get("paddle_keys")
    rep["B7_char_confidence"] = any("char" in str(x).lower() for x in (sample.get("paddle_keys") or []))

    for c in corpora:
        ck = [k for k in keys if k[0] == c]
        loc = [k for k in ck if (T.get(k, {}).get("located") or P.get(k, {}).get("located"))]
        t_hit = [k for k in ck if T.get(k, {}).get("own_kill")]
        p_hit = [k for k in ck if P.get(k, {}).get("own_kill")]
        t_lat = [T[k]["lat_ms"] for k in ck if T.get(k, {}).get("located")]
        p_lat = [P[k]["lat_ms"] for k in ck if P.get(k, {}).get("located")]
        d = {"n": len(ck), "located": len(loc), "tesseract_reads": len(t_hit), "paddle_reads": len(p_hit),
             "tesseract_lat_med": round(st.median(t_lat), 0) if t_lat else None,
             "paddle_lat_med": round(st.median(p_lat), 0) if p_lat else None,
             "paddle_lat_p95": round(sorted(p_lat)[int(len(p_lat) * 0.95)], 0) if p_lat else None}
        if c.endswith("_neg"):
            # B1/B8: false own-handle reads on a negative corpus (bar ZERO)
            d["B1_tesseract_false_reads"] = len(t_hit)
            d["B1_paddle_false_reads"] = len(p_hit)
            d["false_read_crops_paddle"] = [k[1] for k in p_hit][:20]
            d["false_read_crops_tesseract"] = [k[1] for k in t_hit][:20]
        else:
            # B2 pooled-union recall (crop level)
            union = set(t_hit) | set(p_hit)
            d["pooled_union_reads"] = len(union)
            d["tesseract_recall_vs_union"] = round(len(t_hit) / len(union), 3) if union else None
            d["paddle_recall_vs_union"] = round(len(p_hit) / len(union), 3) if union else None
        rep["corpora"][c] = d

    # B2 b2trace WINDOW-level catch (event-anchored, R2 present/total)
    wins = _b2trace_windows()
    present = t_caught = p_caught = 0
    for g, e in wins:
        crops = [k for k in keys if k[0] == "b2trace_pos" and g <= (T.get(k) or P.get(k) or {}).get("ts_ms", -1) <= e]
        if not crops:
            continue
        present += 1
        t_caught += any(T.get(k, {}).get("own_kill") for k in crops)
        p_caught += any(P.get(k, {}).get("own_kill") for k in crops)
    rep["B2_b2trace_window_catch"] = {"windows_total": len(wins), "windows_present_in_archive": present,
                                      "present_over_total": f"{present}/{len(wins)}",
                                      "tesseract_caught": t_caught, "paddle_caught": p_caught}
    with open(os.path.join(_AUD, "recognition_bakeoff_2026-07-03.report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    print(json.dumps(rep, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["tesseract", "paddle"])
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        report()
    elif a.engine:
        run_engine(a.engine)
    else:
        ap.error("need --engine or --report")


if __name__ == "__main__":
    main()
