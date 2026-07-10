#!/usr/bin/env python3
"""RP-4 cross-lobe latency recovery + M13-vs-rp4_rp comparison (offline, read-only).

Recovers per-kill cross-lobe latency (R2 onset [HID lobe] -> kill-row OCR [screen lobe])
for two sessions, computed identically so they are directly comparable:

  * M13 (match13_hdmi_direct)  — the direct-HDMI candidate BASELINE
  * rp4_rp                     — a fresh Remote-Play arm (live authorship=0; recovered here)

Both draw R2 onsets from the SAME global retina_hid_events.jsonl, window-filtered per
session, so the ONLY difference is the transport. Method mirrors Phase C C-1.3 (nearest-
preceding onset; Kill-1 excluded as post-promotion structural). UNCALIBRATED by construction.

Handles two data hazards discovered 2026-07-10:
  (1) the rp4_rp ring archive contains STALE crops from prior sessions -> window-filter by ts.
  (2) retina_hid_events.jsonl is a global appended log -> window-filter onsets per session.

Read-only. No daemon, no chain, no bridge. Output: audits/rp4-latency-recovery-2026-07-10.json
"""
from __future__ import annotations

import json
import os
import statistics
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from rp_ocr_precision_scan import scan_archive  # noqa: E402

_CLUSTER_MS = 5000.0
_LAT_CAP_S = 10.0            # plausibility cap (Phase C max was 6.91s); drops nearest-preceding misses
_ONSET_LOG = os.path.join(_REPO, "retina_hid_events.jsonl")

# Per-session windows (wall-clock ms). M13 from its KAS span_ms; rp4_rp from daemon start stamp.
SESSIONS = [
    {"label": "M13_hdmi_direct", "transport": "direct-HDMI (baseline candidate)",
     "archive": "retina_kf_archive/match13_hdmi_direct_1783385280",
     "lo_ms": 1783385360000.0, "hi_ms": 1783386060000.0},
    {"label": "rp4_rp", "transport": "Remote Play",
     "archive": "retina_kf_archive/rp4_rp_1783700459",
     "lo_ms": 1783700459000.0, "hi_ms": 1783701200000.0},
]


def _load_onsets(lo_ms: float, hi_ms: float) -> tuple[list[float], int, int]:
    """R2-onset wall_ms in [lo,hi], sorted. Returns (onsets, n_total_in_window, n_input_caused)."""
    onsets, n_caused = [], 0
    with open(_ONSET_LOG, encoding="utf-8") as fh:
        for ln in fh:
            try:
                d = json.loads(ln)
            except Exception:  # noqa: BLE001
                continue
            if d.get("type") != "r2_onset":
                continue
            w = d.get("wall_ms")
            if w is None or not (lo_ms <= w <= hi_ms):
                continue
            onsets.append(float(w))
            if d.get("input_caused"):
                n_caused += 1
    onsets.sort()
    return onsets, len(onsets), n_caused


def _recluster(reads: list[dict], lo_ms: float, hi_ms: float) -> list[dict]:
    """Window-filter matched reads by crop ts, re-cluster (5s). Kill = first read ts (row appears)."""
    win = sorted((r for r in reads if lo_ms <= r["ts_ns"] / 1e6 <= hi_ms), key=lambda x: x["ts_ns"])
    kills: list[dict] = []
    for r in win:
        t = r["ts_ns"]
        if kills and (t - kills[-1]["last_ts"]) / 1e6 <= _CLUSTER_MS:
            kills[-1]["last_ts"] = t
            kills[-1]["size"] += 1
        else:
            kills.append({"first_ts": t, "last_ts": t, "size": 1})
    return kills


def _latencies(kills: list[dict], onsets: list[float]) -> tuple[list[float], int]:
    """Nearest-preceding onset per kill; latency_s = kill_wall_ms - onset_wall_ms. Returns (lat, n_capped)."""
    import bisect
    lat, capped = [], 0
    for k in kills:
        kt_ms = k["first_ts"] / 1e6
        i = bisect.bisect_right(onsets, kt_ms)
        if i == 0:
            continue                        # no preceding onset
        dt = (kt_ms - onsets[i - 1]) / 1000.0
        if 0 < dt <= _LAT_CAP_S:
            lat.append(round(dt, 4))
        else:
            capped += 1
    return lat, capped


def _dist(lat: list[float]) -> dict:
    if not lat:
        return {"n": 0}
    s = sorted(lat)
    q = statistics.quantiles(s, n=4) if len(s) >= 2 else [s[0], s[0], s[0]]
    return {
        "n": len(s), "min": round(s[0], 3), "q1": round(q[0], 3),
        "median": round(statistics.median(s), 3), "q3": round(q[2], 3),
        "max": round(s[-1], 3), "mean": round(statistics.fmean(s), 3),
        "std": round(statistics.pstdev(s), 3) if len(s) > 1 else 0.0,
    }


def main() -> int:
    out = {"schema": "rp4-latency-recovery-v0", "cap_s": _LAT_CAP_S,
           "method": "nearest-preceding onset; screen ts = first kill-row crop; Kill-1 excluded (Phase C)",
           "sessions": []}
    for s in SESSIONS:
        arch = os.path.join(_REPO, s["archive"])
        if not os.path.isdir(arch):
            print(f"SKIP {s['label']}: no archive {arch}")
            continue
        print(f"\n=== {s['label']} ({s['transport']}) — scanning {s['archive']} ===", flush=True)
        res = scan_archive(arch)
        reads = [r for c in res["clusters"] for r in c["reads"]]
        kills = _recluster(reads, s["lo_ms"], s["hi_ms"])
        onsets, n_on, n_caused = _load_onsets(s["lo_ms"], s["hi_ms"])
        lat_all, capped = _latencies(kills, onsets)
        lat_excl1 = lat_all[1:] if len(lat_all) >= 1 else []
        rec = {
            "label": s["label"], "transport": s["transport"],
            "total_crops_scanned": res["total_crops"], "matched_crops_all": res["matched_crops"],
            "kills_in_window": len(kills), "onsets_in_window": n_on, "onsets_input_caused": n_caused,
            "latency_capped_out": capped,
            "dist_all": _dist(lat_all), "dist_excl_kill1": _dist(lat_excl1),
            "latencies_s": lat_all,
        }
        out["sessions"].append(rec)
        d = rec["dist_excl_kill1"]
        print(f"  kills={len(kills)} onsets={n_on} lat_n={d.get('n')} "
              f"median={d.get('median')}s q1={d.get('q1')} q3={d.get('q3')} (Kill-1 excl)")

    # comparison
    by = {r["label"]: r for r in out["sessions"]}
    if "M13_hdmi_direct" in by and "rp4_rp" in by:
        m13 = by["M13_hdmi_direct"]["dist_excl_kill1"]
        rp = by["rp4_rp"]["dist_excl_kill1"]
        if m13.get("n") and rp.get("n"):
            delta = round(rp["median"] - m13["median"], 3)
            out["comparison"] = {
                "m13_median_s": m13["median"], "rp4_rp_median_s": rp["median"],
                "delta_median_s": delta,
                "interpretation": (
                    "M13 clearly lower -> genuine low-latency baseline; delta approximates RP contribution"
                    if delta >= 0.15 else
                    "M13 ~ rp4_rp -> M13 was effectively RP too; NO valid baseline on this rig (blocked on capture card)"
                    if abs(delta) < 0.15 else
                    "rp4_rp LOWER than M13 -> baseline assumption inverted; investigate (play-mix / OCR-lag confound)"),
            }
            print(f"\n=== COMPARISON ===\n  M13 median {m13['median']}s vs rp4_rp median {rp['median']}s "
                  f"-> delta {delta:+.3f}s\n  {out['comparison']['interpretation']}")

    outp = os.path.join(_REPO, "audits", "rp4-latency-recovery-2026-07-10.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nwrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
