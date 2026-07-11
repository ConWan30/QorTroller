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
GOLDEN = [
    {"label": "densecand_validate",
     "archive": "retina_kf_archive/densecand_validate_1783711025",
     "scan": "audits/rp_ocr_scan_densecand.json",
     "kas": "audits/kas_record_densecand_validate_2026-07-10.json"},
    {"label": "match14_rp_option_b",
     "archive": "retina_kf_archive/match14_rp_option_b_1783475385",
     "scan": "audits/rp_ocr_precision_scan_v2_m14_m13.json",
     "kas": "audits/kas_record_match14_rp_option_b_2026-07-07.json"},
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
    ok = (rec.verdict == "DEFERRED_AUTHORED_SESSION"
          and rec.deferred_authored >= _MIN_AUTHORED and v["ok"])
    detail = (f"verdict={rec.verdict} authored={rec.deferred_authored} "
              f"observed={rec.deferred_observed} verify={'OK' if v['ok'] else 'FAIL'} pad={PAD_MS:.0f}")
    return ("PASS" if ok else "FAIL"), detail


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
    print(f"  PASS={n_pass}  FAIL={n_fail}  MISSING={n_missing}")
    if n_fail:
        print("  RESULT: FAIL -- a present golden archive did not reproduce DEFERRED_AUTHORED_SESSION "
              "(deferred-logic regression). Investigate before trusting the offline proof.")
        return 1
    if n_pass == 0:
        print("  RESULT: NO GOLDEN ARCHIVE ON DISK -- restore one of the archives above "
              "(retina_kf_archive/ is local + gitignored). Not a pass.")
        return 2
    print(f"  RESULT: PASS -- {n_pass} golden archive(s) reproduce authored>0 + verifier OK. "
          "Card-free authorship proven, no new match. (Scope: bounded-lag archives only; see header.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
