#!/usr/bin/env python3
"""QorTroller L5 kill-feed AUDIT LANE — dual-instrument, read-only offline audit over a session's dense
crop archive. NO daemon, NO live-path footprint: it walks a directory of panel crops and labels each with
TWO INDEPENDENT instruments, then reports where they agree, where they diverge, and what neither can resolve.

It IS the G1' precision tooling (run over the historical archive) AND the standing per-session audit that
replaces the manual offline reworks — every future match self-audits by pointing this at its crop archive.

TWO INSTRUMENTS (the independence that keeps G1' from self-grading):
  A  ocr_row_v1          — killfeed_ocr_bootstrap.tight_row_ocr: locate a killer-slot row (loose feed_v1
                           template >= 0.40, below B's verdict floor) then READ the literal handle glyphs
                           (upscale+Otsu+psm-7, strict canon). Verdict by READING.
  B  template_ensemble_v1 — max-over-anchors killer_slot_best (feed_v1 + roster_v1 + the R4 session-anchor
                           library) at the FROZEN 0.66 floor; refined to OWN_DEATH/OTHER via classify_panel.
                           Verdict by SCORING template correlation.
A resolves rows in the 0.40-0.66 band B's floor rejects — that disagreement is the independence payoff, an
INDEPENDENT corroboration of A's zero-false-read claim. Independence is at the VERDICT MECHANISM (glyph read
vs template score), not location (both use feed_v1 to locate) — see killfeed_ocr_bootstrap docstring.

INSTRUMENT B COVERAGE IS UNEVEN BY CONSTRUCTION and annotated: B can only OWN_KILL a rendering it has an
anchor for. Where B's killer signal is won only by the static feed_v1/roster_v1 (no R4 session anchor for
that rendering), `A=OWN_KILL / B=UNRESOLVED` is an EXPECTED B-gap (structural blindness), NOT evidence against
A. The report states per session which anchors carried B's OWN_KILLs so a B-gap never reads as suspicion.

UNRESOLVED is a first-class output (below-confidence OCR / sub-floor template) — never a forced verdict. The
UNRESOLVED contact sheet is ALSO the human_oracle bootstrap's input artifact (Phase W.1 consumes it).

READ-ONLY: no writes outside the chosen --out prefix; no bridge/session/chain/IOTX. l2_ads untouched.

--workers N parallelizes ACROSS crops with a process pool (spawn-safe: each worker loads the ensemble once
in its initializer). The instruments are byte-identical per crop — parallelism changes scheduling only, never
the measurement; results are emitted in path order (imap) so the JSONL is deterministic.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from collections import Counter

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import cv2  # noqa: E402

from l9_presence import killfeed_ocr_bootstrap as ob  # noqa: E402
from l9_presence import killfeed_cv as kc  # noqa: E402

INSTR_A = "ocr_row_v1"
INSTR_B = "template_ensemble_v1"
_R4_PREFIX = "session_anchor"          # a winning anchor whose name starts with this is R4 (rendering-specific)

# Feed row pitch (F-G1P-2, operator-approved 2026-07-04): one feed row = ~24px text (the calibrated feed
# anchor's height) + ~8-10px inter-row gap on the calibrated 724px panel -> ~33px = 0.045 y-frac; confirmed
# by horizontal-projection band measurement on real multi-row crops (c4 adjacent rows: dy=0.033). Derived
# from the feed's ACTUAL geometry, not a generic tolerance — a double-kill's two genuinely distinct rows sit
# >= one pitch apart and must NOT be bucketed as "same row".
ROW_PITCH_YFRAC = 0.045
SAME_ROW_MAX_DY = ROW_PITCH_YFRAC / 2.0    # same-row test: |A.y - B.y| within half a pitch


# ------------------------------------------------------------------ ensemble ----------------------------
def load_ensemble(r4_dir: str = "retina_kf_anchors"):
    """{name: anchor_bw} for Instrument B: static feed_v1 + roster_v1 + every R4 session anchor found."""
    ens = {}
    for name, path in (("feed_v1", "l9_presence/assets/own_handle_anchor_feed.png"),
                       ("roster_v1", "l9_presence/assets/own_handle_anchor.png")):
        a = kc.load_anchor(os.path.join(_REPO, path))
        if a is not None:
            ens[name] = a
    for p in sorted(glob.glob(os.path.join(_REPO, r4_dir, "*.png"))):
        a = kc.load_anchor(p)
        if a is not None:
            ens[f"{_R4_PREFIX}:{os.path.basename(p)}"] = a
    return ens


# ------------------------------------------------------------------ instruments -------------------------
def instrument_a(img) -> dict:
    """A — tight-row OCR (killer-slot READER). taxonomy in {OWN_KILL, UNRESOLVED} by construction.
    `engine` records the ACTUAL recognizer that produced this read (C3 discipline): with an engine chain
    (RETINA_OCR_ENGINE=rapidocr_v6 -> tesseract fallback) per-record attribution is what keeps a parity
    comparison honest — aggregate numbers must never mix engines invisibly."""
    r = ob.tight_row_ocr(img)
    return {"labeler": INSTR_A, "taxonomy": r.taxonomy(), "engine": r.engine,
            "matched": r.matched, "text": r.text, "x_frac": r.x_frac, "y_frac": r.y_frac, "slot": r.slot}


def instrument_b(img, ensemble) -> dict:
    """B — template ensemble. OWN_KILL iff max-over-anchors killer_slot_best >= 0.66 (record the winning
    anchor + whether it is R4); else refine to OWN_DEATH (victim) / OTHER_ROW (roster) / UNRESOLVED via the
    best-scoring classify_panel over the ensemble."""
    best_k = (0.0, None, None, None)                       # (score, anchor, x_frac, y_frac)
    for name, anchor in ensemble.items():
        sc, cxf, cyf = kc.killer_slot_best(img, anchor)
        if sc > best_k[0]:
            best_k = (sc, name, cxf, cyf)
    if best_k[0] >= kc.DEFAULT_MATCH_FLOOR:
        win = best_k[1]
        return {"labeler": INSTR_B, "taxonomy": ob.OWN_KILL, "killer_score": round(best_k[0], 3),
                "winning_anchor": win, "is_r4": bool(win and win.startswith(_R4_PREFIX)),
                "x_frac": best_k[2], "y_frac": best_k[3]}
    # no confident killer signal — refine the non-kill class from the strongest classify_panel
    best = None                                # (priority, score, taxonomy, anchor, region, x_frac, y_frac)
    _pri = {ob.OWN_DEATH: 2, ob.OTHER_ROW: 1, ob.UNRESOLVED: 0}
    for name, anchor in ensemble.items():
        res = kc.classify_panel(img, anchor, match_floor=kc.DEFAULT_MATCH_FLOOR)
        v = res.verdict.value
        region = (res.evidence or {}).get("region")
        if v == "OWN_KILL_UNBOUND":
            tax = ob.OWN_DEATH
        elif region == "roster" and res.score >= kc.DEFAULT_MATCH_FLOOR:
            tax = ob.OTHER_ROW
        else:
            tax = ob.UNRESOLVED
        cand = (_pri[tax], res.score, tax, name, region, res.x_frac, (res.evidence or {}).get("y_frac"))
        if best is None or cand[:2] > best[:2]:
            best = cand
    return {"labeler": INSTR_B, "taxonomy": best[2], "killer_score": round(best_k[0], 3),
            "winning_anchor": best[3], "is_r4": False, "region": best[4], "x_frac": best[5],
            "y_frac": best[6]}


# ------------------------------------------------------------------ disagreement adjudication -----------
def _same_row(a: dict, b: dict):
    """True/False when both instruments carry y_frac (|dy| within half a row pitch), None when either is
    missing — the caller FAILS TOWARD REVIEW on None (a potential contradiction is never silently
    downgraded for lack of geometry)."""
    ay, by = a.get("y_frac"), b.get("y_frac")
    if ay is None or by is None:
        return None
    return abs(float(ay) - float(by)) <= SAME_ROW_MAX_DY


def adjudicate(a: dict, b: dict) -> str:
    """Category for the disagreement report. The zero-false-read control is CONFLICT_A_KILL_B_DEATH: A read
    an own-kill where B scored the handle in the VICTIM slot OF THE SAME ROW — a candidate A false read,
    operator-adjudicated.

    F-G1P-2 location gate (operator-approved 2026-07-04, empirically supported — all 7 archive conflicts
    were different-row): B disagreeing from a DIFFERENT row (|dy| > half a row pitch; the roster at y~0.97
    is always different-row from a feed read) is B-blindness/mis-slot, NOT a read contradiction ->
    A_KILL_B_ELSEWHERE. Only a same-row disagreement is a CONFLICT. Missing y on either side keeps the
    CONFLICT label (fail-toward-review)."""
    ta, tb = a["taxonomy"], b["taxonomy"]
    if ta == tb:
        return "AGREE"
    if ta == ob.OWN_KILL and tb in (ob.OWN_DEATH, ob.OTHER_ROW):
        if _same_row(a, b) is False:
            return "A_KILL_B_ELSEWHERE"           # different row: expected B-blindness, not suspicion
        return ("CONFLICT_A_KILL_B_DEATH" if tb == ob.OWN_DEATH
                else "CONFLICT_A_KILL_B_ROSTER")  # same row (or unknown geometry): candidate A false read
    if ta == ob.OWN_KILL and tb == ob.UNRESOLVED:
        return "A_KILL_B_GAP" if not b.get("is_r4") else "A_KILL_B_MISS"  # B-coverage gap vs real B miss
    if ta == ob.UNRESOLVED and tb == ob.OWN_KILL:
        return "B_KILL_A_MISS"                    # A OCR miss (recall gap) — B had the anchor, A didn't read
    if ta == ob.UNRESOLVED and tb in (ob.OWN_DEATH, ob.OTHER_ROW):
        return "BENIGN_A_ABSTAIN"                 # A is a killer-slot reader; abstaining on a death/roster is
                                                  # CORRECT behaviour, not a missed kill — kept out of the
                                                  # OWN_KILL disagreement signal.
    return f"DIVERGE_{ta}_vs_{tb}"


# ------------------------------------------------------------------ parallel workers ---------------------
_W_ENS = None                                          # per-process ensemble (loaded once in the initializer)


def _worker_init(r4_dir: str):
    global _W_ENS
    _W_ENS = load_ensemble(r4_dir)


def _label_one(path: str):
    """One crop -> (basename, a, b) with BOTH instruments, or None on unreadable image. Runs in a worker
    process; identical per-crop computation to the sequential path (scheduling-only parallelism)."""
    img = cv2.imread(path)
    if img is None:
        return None
    return os.path.basename(path), instrument_a(img), instrument_b(img, _W_ENS)


def _iter_labels(paths, ens, workers: int):
    """Yield (basename, a, b) in path order — sequential (workers<=1) or via a spawn-safe process pool."""
    if workers <= 1:
        for p in paths:
            img = cv2.imread(p)
            if img is None:
                continue
            yield os.path.basename(p), instrument_a(img), instrument_b(img, ens)
        return
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers, initializer=_worker_init, initargs=(_R4_DIR_FOR_WORKERS,)) as pool:
        for out in pool.imap(_label_one, paths, chunksize=4):
            if out is not None:
                yield out


_R4_DIR_FOR_WORKERS = "retina_kf_anchors"              # set by run_lane before pool spawn (picklable str)


# ------------------------------------------------------------------ run ----------------------------------
def _load_resume_rows(jsonl_path: str) -> list:
    """Parse an interrupted run's JSONL (tolerant of a truncated trailing line from a killed buffer)."""
    rows = []
    try:
        with open(jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    if "crop" in r and INSTR_A in r and INSTR_B in r:
                        rows.append(r)
                except Exception:  # noqa: BLE001 — truncated flush boundary; the crop just re-runs
                    pass
    except OSError:
        pass
    return rows


def run_lane(crop_dir: str, out_prefix: str, limit: int, r4_dir: str, workers: int = 1,
             resume: bool = False) -> dict:
    global _R4_DIR_FOR_WORKERS
    _R4_DIR_FOR_WORKERS = r4_dir
    ens = load_ensemble(r4_dir)
    r4_anchors = [n for n in ens if n.startswith(_R4_PREFIX)]
    paths = sorted(glob.glob(os.path.join(crop_dir, "*.png")))
    if limit > 0:
        paths = paths[:limit]
    if not ob.ocr_ready():
        print("WARNING: OCR engine unavailable (tesseract) — Instrument A will UNRESOLVED every crop.",
              file=sys.stderr)

    jsonl_path = out_prefix + ".taxonomy.jsonl"
    rows = _load_resume_rows(jsonl_path) if resume else []
    if rows:
        done = {r["crop"] for r in rows}
        paths = [p for p in paths if os.path.basename(p) not in done]
        with open(jsonl_path, "w", encoding="utf-8") as fh:      # rewrite clean (drops any truncated tail)
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        print(f"  resume: {len(rows)} crops already labeled, {len(paths)} remaining", file=sys.stderr)
    a_cnt, b_cnt, disagree_cnt = Counter(), Counter(), Counter()
    b_kill_anchor = Counter()                      # which anchors carry B's OWN_KILLs (coverage annotation)
    for r in rows:                                 # prime counters from resumed rows (summary covers ALL)
        a_cnt[r[INSTR_A]["taxonomy"]] += 1
        b_cnt[r[INSTR_B]["taxonomy"]] += 1
        if r["category"] not in ("AGREE", "BENIGN_A_ABSTAIN"):
            disagree_cnt[r["category"]] += 1
        if r[INSTR_B]["taxonomy"] == ob.OWN_KILL:
            b_kill_anchor[r[INSTR_B].get("winning_anchor")] += 1
    t0 = time.time()
    with open(jsonl_path, "a" if rows else "w", encoding="utf-8") as fh:
        for i, (base, a, b) in enumerate(_iter_labels(paths, ens, workers)):
            cat = adjudicate(a, b)
            rec = {"crop": base, INSTR_A: a, INSTR_B: b, "category": cat}
            fh.write(json.dumps(rec) + "\n")
            rows.append(rec)
            a_cnt[a["taxonomy"]] += 1
            b_cnt[b["taxonomy"]] += 1
            if cat not in ("AGREE", "BENIGN_A_ABSTAIN"):     # BENIGN = A correctly abstaining on a non-kill
                disagree_cnt[cat] += 1
            if b["taxonomy"] == ob.OWN_KILL:
                b_kill_anchor[b.get("winning_anchor")] += 1
            if (i + 1) % 100 == 0:
                print(f"  ...{i + 1}/{len(paths)} ({(time.time() - t0) / (i + 1) * 1000:.0f}ms/crop)",
                      file=sys.stderr, flush=True)
    dt = time.time() - t0
    n = len(rows)

    # candidate false reads = A OWN_KILL contradicted by B seeing the handle in a non-killer slot
    false_read_candidates = [r for r in rows if r["category"] in ("CONFLICT_A_KILL_B_DEATH",
                                                                  "CONFLICT_A_KILL_B_ROSTER")]
    unresolved_both = [r for r in rows
                       if r[INSTR_A]["taxonomy"] == ob.UNRESOLVED and r[INSTR_B]["taxonomy"] == ob.UNRESOLVED]

    summary = {
        "crop_dir": crop_dir, "n_crops": n, "ms_per_crop": round(dt / max(1, n) * 1000, 1),
        "ensemble": list(ens.keys()), "r4_anchor_count": len(r4_anchors),
        "instrument_a_counts": dict(a_cnt), "instrument_b_counts": dict(b_cnt),
        "a_unresolved_rate": round(a_cnt[ob.UNRESOLVED] / max(1, n), 4),
        "b_unresolved_rate": round(b_cnt[ob.UNRESOLVED] / max(1, n), 4),
        "disagreements": dict(disagree_cnt),
        "b_own_kill_by_anchor": dict(b_kill_anchor),
        "false_read_candidates": len(false_read_candidates),
        "unresolved_both": len(unresolved_both),
        "a_own_kill": a_cnt[ob.OWN_KILL], "b_own_kill": b_cnt[ob.OWN_KILL],
    }
    _write_report(out_prefix + ".report.md", summary, false_read_candidates, r4_anchors)
    _write_contact_sheet(out_prefix + ".contact_sheet.md", false_read_candidates, unresolved_both)
    _write_evidence(out_prefix, crop_dir, false_read_candidates)
    summary["jsonl"] = jsonl_path
    return summary


def _write_evidence(out_prefix: str, crop_dir: str, false_reads) -> None:
    """F-G1P-1 (operator-required): conflict evidence must survive rolling-buffer eviction — copy every
    conflict crop into `<out>.evidence/` at report time, PLUS a FULL-Y-GATE-RANGE zoom (y<0.55, i.e. the
    whole feed gate + margin, 2.5x). The zoom range is a hard requirement, not a convenience: the c7
    adjudication (2026-07-04) initially missed a REAL kill row because a shallow y<0.35 zoom cropped it out
    — a partial zoom can flip an adjudication. Fail-open: evidence copying never breaks the report."""
    if not false_reads:
        return
    ev_dir = out_prefix + ".evidence"
    try:
        os.makedirs(ev_dir, exist_ok=True)
        import shutil
        for r in false_reads:
            src = os.path.join(crop_dir, r["crop"])
            img = cv2.imread(src)
            if img is None:
                continue
            shutil.copy2(src, os.path.join(ev_dir, r["crop"]))
            h, w = img.shape[:2]
            zoom = cv2.resize(img[0:max(1, int(h * 0.55)), 0:w], None, fx=2.5, fy=2.5,
                              interpolation=cv2.INTER_CUBIC)
            cv2.imwrite(os.path.join(ev_dir, r["crop"].rsplit(".", 1)[0] + "_fullgate2.5x.png"), zoom)
    except Exception as e:  # noqa: BLE001 — evidence is additive; the report itself must still land
        print(f"  evidence-copy WARNING: {e!r}", file=sys.stderr)


def _write_report(path, s, false_reads, r4_anchors):
    L = []
    L.append("# Kill-feed audit lane — dual-instrument precision report\n")
    L.append(f"Crops: **{s['n_crops']}** from `{s['crop_dir']}`  ·  {s['ms_per_crop']} ms/crop\n")
    L.append(f"Ensemble (Instrument B): {', '.join(s['ensemble'])}  ·  R4 session anchors: "
             f"**{s['r4_anchor_count']}**\n")
    L.append("\n## Zero-false-read bar (the hard gate)\n")
    L.append(f"- Instrument A OWN_KILL reads: **{s['a_own_kill']}**\n")
    L.append(f"- **Candidate false reads** (A=OWN_KILL contradicted by B seeing the handle in a non-killer "
             f"slot): **{s['false_read_candidates']}** — bar is ZERO after adjudication; see contact sheet.\n")
    L.append("\n## Per-instrument taxonomy\n")
    L.append(f"- A `ocr_row_v1` (killer-slot READER): {s['instrument_a_counts']}\n")
    L.append(f"- B `template_ensemble_v1` (template SCORER): {s['instrument_b_counts']}\n")
    L.append(f"- UNRESOLVED rate — A **{s['a_unresolved_rate']:.1%}** / B **{s['b_unresolved_rate']:.1%}** "
             f"(pre-registered DRIFT ALARM: a rendering change spikes this before recall silently collapses)\n")
    L.append("\n## Disagreement report (the independence measurement)\n")
    L.append(f"{s['disagreements'] or '{} (perfect agreement)'}\n\n")
    L.append("Categories: `CONFLICT_A_KILL_B_DEATH`/`_B_ROSTER` = candidate A false read (contact sheet); "
             "`A_KILL_B_GAP` = EXPECTED B-coverage gap (B had no R4 anchor for the rendering — NOT suspicion); "
             "`A_KILL_B_MISS` = B had an R4 anchor but missed (real B miss); `B_KILL_A_MISS` = A OCR recall "
             "gap.\n")
    L.append("\n## Instrument B coverage annotation (uneven by construction)\n")
    L.append(f"B's OWN_KILLs by winning anchor: {s['b_own_kill_by_anchor']}\n\n")
    only_static = all(not k.startswith(_R4_PREFIX) for k in s['b_own_kill_by_anchor']) \
        if s['b_own_kill_by_anchor'] else True
    if only_static:
        L.append("> **B-coverage: STATIC ONLY.** Every B OWN_KILL was carried by feed_v1/roster_v1 — B holds "
                 "no R4 session anchor matching this archive's rendering. Therefore `A_KILL_B_GAP` "
                 "disagreements are EXPECTED structural B-blindness, not evidence against A. A-vs-B "
                 "corroboration of the zero-false-read bar holds only where B actually scored (its OWN_KILL "
                 "set), not over the B-gap tail.\n")
    else:
        L.append("> **B-coverage: includes R4.** At least one B OWN_KILL was carried by an R4 session anchor "
                 f"({', '.join(a for a in r4_anchors)}) — A-B agreement corroborates independence over that "
                 "covered subset.\n")
    L.append("\n## Correlated blind spot (honest limit)\n")
    L.append(f"- Crops neither instrument resolved (UNRESOLVED by BOTH): **{s['unresolved_both']}** — the "
             "deep tail where feed_v1 < 0.40 (A cannot locate) AND template < 0.66 (B sub-floor). This is the "
             "human_oracle contact-sheet input.\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(L))


def _write_contact_sheet(path, false_reads, unresolved_both):
    L = ["# Contact sheet — operator adjudication\n\n",
         "## Candidate A false reads (MUST resolve to zero — A read own-kill, B saw a non-killer slot)\n\n"]
    if not false_reads:
        L.append("_None — zero-false-read bar held mechanically._\n")
    for r in false_reads:
        a, b = r[INSTR_A], r[INSTR_B]
        L.append(f"- `{r['crop']}`  A={a['taxonomy']} text={a['text']!r} xf={a.get('x_frac')}  |  "
                 f"B={b['taxonomy']} score={b.get('killer_score')} anchor={b.get('winning_anchor')}\n")
    L.append("\n## UNRESOLVED-by-both (human_oracle bootstrap input)\n\n")
    if not unresolved_both:
        L.append("_None._\n")
    for r in unresolved_both[:200]:                # cap the sheet
        L.append(f"- `{r['crop']}`\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(L))


def main():
    ap = argparse.ArgumentParser(description="Dual-instrument kill-feed audit lane (read-only).")
    ap.add_argument("--crops", default="retina_kf_crops", help="directory of panel_*.png crops")
    ap.add_argument("--out", default="audits/killfeed_audit_lane", help="output path prefix")
    ap.add_argument("--limit", type=int, default=0, help="cap crops (0 = all)")
    ap.add_argument("--r4-dir", default="retina_kf_anchors", help="R4 session-anchor library dir")
    ap.add_argument("--workers", type=int, default=1,
                    help="process-pool size (1 = sequential; parallelism is scheduling-only)")
    ap.add_argument("--resume", action="store_true",
                    help="skip crops already in the output JSONL (rewrites it clean, then appends)")
    a = ap.parse_args()
    crop_dir = a.crops if os.path.isabs(a.crops) else os.path.join(_REPO, a.crops)
    out = a.out if os.path.isabs(a.out) else os.path.join(_REPO, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    s = run_lane(crop_dir, out, a.limit, a.r4_dir, workers=a.workers, resume=a.resume)
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
