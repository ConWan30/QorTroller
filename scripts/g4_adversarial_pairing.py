#!/usr/bin/env python3
"""G4 adversarial pairing harness (Increment 2 step 3; read-only, no daemon/live/chain).

PRE-REGISTERED BAR (docs/l4-conjunction-verdict-scope-2026-07-03.md, set BEFORE any run, no post-hoc
tuning): adversarial scenarios must yield **ZERO AUTHORED_SESSION certificates**. Any single adversarial
certificate = G4 FAIL -> diagnose + fix + FULL re-run.

Scenarios:
  A2 `splice`  — drive an adversarial replay-splice crop archive through the REAL wired producer
                 (_session_anchor_fold, same bare-RGC pattern as replay_session_anchor) and issue a KAS
                 record over whatever composites result. Expect: no certificate.
  A3 `spoof`   — synthetic near-collision handle probes through the strict-canon OCR read + template path.
                 Reports which probes the canon DOES collide with (canon is deliberately OCR-confusion-
                 tolerant: o->0, i/l/|->1 — visually-confusable handles collide BY DESIGN; that boundary is
                 surfaced as a finding, never hidden).
  A4 `nowindow`— structural: an AUTHORED-quality kill row present but NO live R2 window -> the monitor
                 refuses to classify -> zero composites -> no certificate. (The R2^B2 rail at KAS level.)
  A1 `session` — issue a KAS record over a REAL daemon session by label (the operator's spectate-spam
                 segment). Expect: INSUFFICIENT_KILLS (own handle never in the killer slot).

Usage:
  python scripts/g4_adversarial_pairing.py splice   [--crops retina_kf_adv_splice]
  python scripts/g4_adversarial_pairing.py spoof
  python scripts/g4_adversarial_pairing.py nowindow
  python scripts/g4_adversarial_pairing.py session --label <daemon_label>
  python scripts/g4_adversarial_pairing.py all      (splice + spoof + nowindow)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(_REPO, "bridge"), _REPO):
    if p not in sys.path:
        sys.path.insert(0, p)

from l9_presence.kill_authorship_session import AUTHORED_SESSION, build_session_record  # noqa: E402

_H_CLEAN = {"frame_errs": 0, "frame_stall_s": 0.0, "ts_source": "timespan"}
_TSNUM = re.compile(r"panel_(\d+)")


def _bare_rgc(y_gate: float = 0.75, ocr: bool = False):
    import cv2  # noqa: F401
    from l9_presence import killfeed_cv as kc
    from l9_presence.killfeed_inline import InlineAuthorshipMonitor
    from l9_presence.killfeed_session_anchor import SessionAnchorGenerator
    from vapi_bridge.qortroller_retina_capture import RetinaGameCapture
    rgc = RetinaGameCapture.__new__(RetinaGameCapture)
    rgc._inline_monitor = InlineAuthorshipMonitor(match_floor=0.66, killer_max_frac=0.28,
                                                  feed_region_max_yfrac=y_gate, anchor_id="feed_v1")
    rgc._session_anchor = SessionAnchorGenerator(session_id="g4adv", killer_max_frac=0.28,
                                                 feed_region_max_yfrac=y_gate, k_consistency=3)
    rgc._anchor = kc.load_anchor(os.path.join(_REPO, "l9_presence/assets/own_handle_anchor_feed.png"))
    rgc._prev_killer_gray = None
    rgc._last_killer_fresh_ms = -1e18
    rgc._session_anchor_dir = os.path.join(_REPO, "retina_kf_anchors_g4adv")   # separate archive dir
    rgc._ocr_bootstrap_enabled = bool(ocr)      # run the LIVE config (OCR on) for the strongest attack
    return rgc


def scenario_splice(crop_dir: str, ocr: bool = False) -> dict:
    """A2: the wired producer over the adversarial splice archive -> KAS record. Composites are collected via
    the monitor's own resolution paths (mark_onset restarts + final flush)."""
    import cv2
    from l9_presence import killfeed_cv as kc
    rgc = _bare_rgc(ocr=ocr)
    gen, mon = rgc._session_anchor, rgc._inline_monitor
    crops = sorted(glob.glob(os.path.join(crop_dir, "*.png")),
                   key=lambda p: int(_TSNUM.search(p).group(1)) if _TSNUM.search(p) else 0)
    composites = []
    mon.mark_onset(0.0)
    for i, p in enumerate(crops):
        bgr = cv2.imread(p)
        if bgr is None:
            continue
        now = float(i * 100)
        res = kc.classify_panel(bgr, rgc._anchor, feed_region_max_yfrac=mon.feed_region_max_yfrac)
        rgc._session_anchor_fold(bgr, res, res.evidence or {}, now)
        r = mon.mark_onset(now)                        # sustained-fire attacker: window kept open/restarted
        if r:
            composites.append(r)
    r = mon.flush_if_expired(1e12)
    if r:
        composites.append(r)
    rec = build_session_record(session_label=f"A2_splice{'_ocr' if ocr else ''}:{os.path.basename(crop_dir)}",
                               handle="QorTrola30", composites=composites,
                               event_trail=[{"generator": gen.status()}], hygiene=dict(_H_CLEAN))
    return rec.to_dict()


def scenario_spoof() -> dict:
    """A3: near-collision handle probes vs the strict canon. Two classes: (a) DIFFERENT names that must NOT
    collide; (b) visually-confusable names that DO collide BY DESIGN (canon o->0, i/l/|->1) — surfaced as the
    honest boundary, not hidden."""
    from l9_presence.killfeed_authorship import canon, default_handle
    own = canon(default_handle())
    must_reject = ["QorTrola31", "QorTrola3", "XorTrola30", "QorTrolla30", "orTrola30"]
    # DOCUMENTED COLLISION BOUNDARY (two mechanisms, both deliberate OCR tolerances, both adjudicated at the
    # G4 HOLD rather than hidden): (a) glyph-confusion canon (o->0, i/l/|->1, case) collides visually-
    # confusable names; (b) SUBSTRING matching (needed because OCR row text carries junk around the handle)
    # collides names that EXTEND the handle — the harness's own probe caught 'QorTro1a300' here 2026-07-03.
    boundary_collide = ["Q0rTrola30", "QorTro1a30", "QORTROLA30", "QorTrolA30", "Q0rTr01a30", "QorTro1a300"]
    leaks = [n for n in must_reject if own in canon(n)]
    collided = [n for n in boundary_collide if own in canon(n)]
    return {"scenario": "A3_spoof", "own_canon": own,
            "must_reject": {"total": len(must_reject), "rejected": len(must_reject) - len(leaks),
                            "leaks": leaks},
            "documented_collision_boundary": collided,
            "pass": not leaks,
            "finding": "canon collides (a) visually-confusable names (o/0, i/l/1, case) and (b) handle-"
                       "EXTENDING names via substring matching. Certificate-level consequence: a hostile "
                       "lobby name inside this boundary could credit the attacker's kills to the handle — "
                       "requires the handle to be a canon-substring of the attacker's name, visible in the "
                       "same lobby. Recorded for HOLD adjudication; disambiguation beyond glyph shape is out "
                       "of the CV layer's scope."}


def scenario_nowindow() -> dict:
    """A4 structural: a perfect kill row on screen but NO live R2 window -> should_classify False -> zero
    composites -> the KAS record cannot certify. Proves the rail composes to the certificate level."""
    from l9_presence.killfeed_inline import InlineAuthorshipMonitor
    mon = InlineAuthorshipMonitor(match_floor=0.66, killer_max_frac=0.28,
                                  feed_region_max_yfrac=0.75, anchor_id="feed_v1")
    attempts = [mon.should_classify(float(t)) for t in (0, 1_000, 60_000, 3_600_000)]  # no onset ever
    rec = build_session_record(session_label="A4_nowindow", handle="QorTrola30",
                               composites=[], hygiene=dict(_H_CLEAN))
    return {"scenario": "A4_nowindow", "classify_attempts_granted": sum(attempts),
            "kas_verdict": rec.verdict, "pass": sum(attempts) == 0 and rec.verdict != AUTHORED_SESSION}


def scenario_session(label: str) -> dict:
    """A1: KAS record over a real daemon session (the operator's spectate segment)."""
    from scripts.issue_kas_records import parse_log  # reuse the retro-issuer's parser
    logs = sorted(glob.glob(os.path.join(_REPO, f"retina_daemon_{label}_*.log")))
    if not logs:
        return {"scenario": f"A1_session:{label}", "error": "no daemon log found"}
    span, events, hygiene, coupling = parse_log(logs[-1])
    comps = []
    if span:
        a, b = span[0] - 10_000, span[1] + 120_000
        for l in open(os.path.join(_REPO, "retina_kf_composite.jsonl"), encoding="utf-8"):
            c = json.loads(l)
            if isinstance(c.get("ts_ms"), (int, float)) and a <= c["ts_ms"] <= b:
                comps.append(c)
    rec = build_session_record(session_label=f"A1_session:{label}", handle="QorTrola30",
                               composites=comps, event_trail=events, hygiene=hygiene, coupling=coupling)
    return rec.to_dict()


def _verdict_line(name: str, d: dict) -> str:
    v = d.get("verdict") or ("PASS" if d.get("pass") else "FAIL")
    cert = (d.get("verdict") == AUTHORED_SESSION)
    bar = "*** ADVERSARIAL CERTIFICATE — G4 FAIL ***" if cert else "no certificate (bar held)"
    return f"{name:22s} {v:20s} {bar}"


def main():
    ap = argparse.ArgumentParser(description="G4 adversarial pairing (read-only).")
    ap.add_argument("scenario", choices=["splice", "spoof", "nowindow", "session", "all"])
    ap.add_argument("--crops", default="retina_kf_adv_splice")
    ap.add_argument("--label", default="")
    ap.add_argument("--ocr", action="store_true", help="splice with OCR bootstrap ON (the live config)")
    ap.add_argument("--out", default="audits/g4_adversarial_2026-07-03.json")
    a = ap.parse_args()
    results = {}
    if a.scenario in ("splice", "all"):
        crop_dir = a.crops if os.path.isabs(a.crops) else os.path.join(_REPO, a.crops)
        results["A2_splice" + ("_ocr" if a.ocr else "")] = scenario_splice(crop_dir, ocr=a.ocr)
    if a.scenario in ("spoof", "all"):
        results["A3_spoof"] = scenario_spoof()
    if a.scenario in ("nowindow", "all"):
        results["A4_nowindow"] = scenario_nowindow()
    if a.scenario == "session":
        if not a.label:
            ap.error("--label required for session")
        results[f"A1_session:{a.label}"] = scenario_session(a.label)
    out = a.out if os.path.isabs(a.out) else os.path.join(_REPO, a.out)
    existing = {}
    if os.path.exists(out):
        with open(out, encoding="utf-8") as fh:
            existing = json.load(fh)
    existing.update(results)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2)
    print("\n=== G4 pairing (bar: ZERO adversarial certificates) ===")
    any_cert = False
    for name, d in results.items():
        print(_verdict_line(name, d))
        any_cert = any_cert or (d.get("verdict") == AUTHORED_SESSION)
    print("\nG4 " + ("FAIL — adversarial certificate issued" if any_cert else
                     "bar HELD on the scenarios run") + f"; results appended to {out}")


if __name__ == "__main__":
    main()
