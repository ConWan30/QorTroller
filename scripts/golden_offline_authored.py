#!/usr/bin/env python3
"""Golden offline authored pack (P0 #2) -- the card-free "run this -> authored>0" proof.

Rebuilds a deferred-attestation record from FIXED, known-good, BOUNDED-LAG Remote-Play archives
with the RP window-latency pad (4000 ms), asserts DEFERRED_AUTHORED_SESSION + verifier OK +
authored >= floor, and exits 0 (PASS) / 1 (FAIL -- a present golden regressed) / 2 (no golden
archive on disk). No rig, no new match, no chain, no FROZEN-v1, no IOTX.

WHY THIS EXISTS: live authored>0 is still fragile under capture lag; the deferred path is the
card-free reliability proof that works TODAY. This pack makes reproducing it a single command so
the operator never needs to play another match to demonstrate authored>0. On both goldens the
LIVE KAS verdict is INSUFFICIENT_KILLS (RP thinned the live crops) yet the deferred path recovers
authored=3 -- that recovery IS the proof.

HONEST SCOPE (do not soften): authored>0 is guaranteed only for BOUNDED-LAG archives -- ones whose
RP fire->kill gap fits inside the 4000 ms pad. The >4 s-lag tail (e.g. M18) is an HONEST 0 that a
looser pad must NOT paper over; it needs a deferred-FAR study, not a bigger number. M18 is
deliberately EXCLUDED from the golden set below; pad=4000 recovered only 3/8 of M18's kills -- a
limit, not a target. (This exclusion is pinned by test_golden_offline_pack.)

GOLDEN ARCHIVES ARE LOCAL: retina_kf_archive/ is gitignored (biometric-capture policy), so the
crops live on the operator's disk, not in the repo. THIS SCRIPT + docs/golden-offline-authored-pack.md
are the committed part; the archive is the operator's reliability asset. A missing golden exits 2
and names the archive to restore -- never a silent pass.

Run:
    python scripts/golden_offline_authored.py
"""
from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from l9_presence.kas_deferred import build_deferred_record, verify_deferred_record
from build_deferred_attestation import _load_windows          # reuse the tested window loader (no drift)

PAD_MS = 4000.0                    # Remote-Play fire->kill window-latency pad (arc A)
_MIN_AUTHORED = 2                  # DEFAULT_MIN_KILLS floor for a *_SESSION verdict

# Bounded-lag golden archives (LOCAL). M18 (>4 s lag) is intentionally NOT here -- see HONEST SCOPE.
# Checklist bar E3: every golden MUST carry a lag_note documenting the measured fire->kill lag and
# why it fits the 4000 ms pad budget (test-pinned non-empty; content quality is review, not code).
GOLDEN = [
    {"label": "densecand_validate",
     "archive": "retina_kf_archive/densecand_validate_1783711025",
     "scan": "audits/rp_ocr_scan_densecand.json",
     "kas": "audits/kas_record_densecand_validate_2026-07-10.json",
     "lag_note": "RP match 2026-07-10; pad=4000 flipped OBSERVED_ONLY(1)->AUTHORED_SESSION(3), so "
                 "recovered kills' fire->kill gap <= 4s (arc A study); live KAS INSUFFICIENT_KILLS"},
    {"label": "match14_rp_option_b",
     "archive": "retina_kf_archive/match14_rp_option_b_1783475385",
     "scan": "audits/rp_ocr_precision_scan_v2_m14_m13.json",
     "kas": "audits/kas_record_match14_rp_option_b_2026-07-07.json",
     "lag_note": "RP match 2026-07-07 (M14); deferred stable 3->3 at pad=0 AND pad=4000 (arc A "
                 "regression anchor), so within-window kills need no pad; bounded by construction"},
]


def run_one(g: dict, composites: str = "retina_kf_composite.jsonl") -> tuple:
    """Rebuild + verify one golden. Returns (status, detail) with status PASS / FAIL / MISSING.
    MISSING (archive/scan/kas absent on disk) is never a pass -- the local archive is required."""
    arch = os.path.join(_REPO, g["archive"])
    scan_p = os.path.join(_REPO, g["scan"])
    kas_p = os.path.join(_REPO, g["kas"])
    manifest_p = os.path.join(arch, "manifest.json")
    for p in (manifest_p, scan_p, kas_p):
        if not os.path.isfile(p):
            return "MISSING", f"absent: {os.path.relpath(p, _REPO)}"
    try:
        scan_doc = json.load(open(scan_p, encoding="utf-8"))
        manifest = json.load(open(manifest_p, encoding="utf-8"))
        kas = json.load(open(kas_p, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return "FAIL", f"load error: {exc}"
    # pick THIS archive's result out of a (possibly multi-archive) scan file -- runner logic
    results = scan_doc.get("results") or [scan_doc]
    arch_norm = g["archive"].replace("\\", "/").rstrip("/")
    scan = next((r for r in results
                 if str(r.get("archive", "")).replace("\\", "/").rstrip("/") == arch_norm), None)
    if scan is None:
        return "FAIL", f"no scan result for {g['archive']!r} in {g['scan']!r}"
    windows = _load_windows(os.path.join(_REPO, composites), kas.get("span_ms"))
    rec = build_deferred_record(scan=scan, manifest=manifest, windows=windows, kas_record=kas,
                                window_latency_pad_ms=PAD_MS)
    v = verify_deferred_record(rec.to_dict(), manifest, arch)
    # Checklist bar D (three-artifact join), pack-hardened: the builder tolerates a KAS record
    # WITHOUT session_id (pre-U1 records); goldens are all post-U1, so require it present + equal
    # across manifest / KAS / deferred record. Anti-splice rail, not optional metadata.
    sid_m, sid_k, sid_r = manifest.get("session_id"), kas.get("session_id"), rec.session_id
    joined = bool(sid_m) and sid_m == sid_k == sid_r
    ok = (rec.verdict == "DEFERRED_AUTHORED_SESSION"                       # bar A1
          and rec.deferred_authored >= _MIN_AUTHORED                       # bar A2
          and v["ok"]                                                      # bar B1/B2 (G-VERIFY)
          and joined)                                                      # bar D
    detail = (f"verdict={rec.verdict} authored={rec.deferred_authored} "
              f"observed={rec.deferred_observed} verify={'OK' if v['ok'] else 'FAIL'} "
              f"session_id={'joined' if joined else 'MISMATCH'} pad_ms={PAD_MS:.0f}")
    return ("PASS" if ok else "FAIL"), detail


def pack_exit(n_pass: int, n_fail: int, n_missing: int) -> int:
    """Checklist bar C, pure + test-pinned. FAIL of a PRESENT golden dominates (exit 1 -- never
    hide regression behind missing); any MISSING golden makes the environment incomplete (exit 2 --
    bar F rejects exit 0 with missing>0); only all-present all-pass is exit 0."""
    if n_fail:
        return 1
    if n_missing or n_pass == 0:
        return 2
    return 0


def main() -> int:
    print("=" * 74)
    print("  GOLDEN OFFLINE AUTHORED PACK -- card-free 'run this -> authored>0' (pad=%.0fms)" % PAD_MS)
    print("=" * 74)
    n_pass = n_fail = n_missing = 0
    for g in GOLDEN:
        status, detail = run_one(g)
        print(f"  [{status:7}] {g['label']:22} {detail}")
        n_pass += status == "PASS"
        n_fail += status == "FAIL"
        n_missing += status == "MISSING"
    print("-" * 74)
    code = pack_exit(n_pass, n_fail, n_missing)
    if code == 1:
        print(f"  GOLDEN OFFLINE AUTHORED PACK: FAIL  (present golden regressed)")
        print(f"    goldens={len(GOLDEN)} pass={n_pass} fail={n_fail} missing={n_missing}  exit=1")
        print("    deferred logic or inputs broke -- investigate before trusting the offline proof.")
    elif code == 2:
        print(f"  GOLDEN OFFLINE AUTHORED PACK: INCOMPLETE  (missing golden archive -- never a pass)")
        print(f"    goldens={len(GOLDEN)} pass={n_pass} fail={n_fail} missing={n_missing}  exit=2")
        print("    restore the named archive(s); retina_kf_archive/ is local + gitignored.")
    else:
        # Checklist bar F: the reviewer-facing PASS line -- semantic fields are mandatory.
        print("  GOLDEN OFFLINE AUTHORED PACK: PASS")
        print(f"    goldens={len(GOLDEN)} present={n_pass} missing=0")
        print(f"    each: verdict=DEFERRED_AUTHORED_SESSION authored>={_MIN_AUTHORED} verify=OK "
              f"session_id=joined pad_ms={PAD_MS:.0f}")
        print("    scope=developer_self bounded_lag=true m18_excluded=true")
        print("    exit=0")
    return code


if __name__ == "__main__":
    sys.exit(main())
