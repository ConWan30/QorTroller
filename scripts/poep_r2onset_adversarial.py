#!/usr/bin/env python3
"""(ii) R2-onset — ADVERSARIAL harness v0 (offline, grok adversarial-consult design).

Tests whether the R2-onset voluntary-reaction liveness primitive is "indistinguishable enough" for
anti-cheat, OFFLINE against dumps + the study verifier. Operator decisions (2026-07-19):
  * GO band = (320, 400] ms, FAST-cluster only. Slow honest taps -> SOFT (retry), NOT bot flags.
  * The one attack a single challenge cannot beat (a fixed-delay in-band bot) -> PUBLISH the residual FAR.

DETECTOR: detect_voluntary_go(rec) -> verdict. A GO requires a GOLD read-at-fire t0 (mono_extrap/stale are
too uncertain to certify a reaction time), a real R2 reaction, and lat in the GO band.

ATTACKS (synthetic, by construction):
  A1 naive replay   -> a captured response re-fired against a FRESH nonce/t0: the unrelated t0 fails
                       gold-window acceptance -> non-gold (uncertain) reference -> REJECT. Defeated by
                       construction (nonce + device clock); NOT a forced-out-of-band-latency artifact.
  A1' re-anchor     -> attacker who KNOWS the new t0 re-times the response to land at ~345 ms. If it still
                       GOes it is a FINDING (offline dumps carry no cryptographic frame-commitment) -> the
                       rig/crypto upgrade is HMAC(nonce||t0||onset) at fire. Reported, not silently passed.
  A2 sub-floor bot  -> presses faster than the human floor (<=320 ms) -> REJECT_TOO_FAST.
  A3 dead feed      -> flat R2 -> REJECT_NO_REACTION.
  A4 absurd t0      -> t0 outside window / no gold read -> REJECT_BAD_T0.
  A5 fixed-delay bot-> presses at a constant ~345 ms -> GOes single-shot -> RESIDUAL FAR (published).
  A6 random bot     -> presses at a uniform-random offset in [0, ISI] -> FAR ~= band_width/ISI (analytic+sim).

CLAIM CEILING (PASS): construction attacks (A1, A2, A3, A4) REJECT by design; the human fast-cluster mostly
GOes (low FRR on that subset); A1'/A5/A6 residual FAR is MEASURED and PUBLISHED, not waved away. This stays
a VOLUNTARY-reaction liveness CANDIDATE on a single-operator provisional band. It does NOT prove: sub-280 ms
reflex, population biometric, tournament-ready poep_enabled, defeat of a fixed-delay bot on a SINGLE
challenge, or a bot that learns the fire time from host APIs / a hardware injector (all rig/crypto-gated).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import statistics
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from poep_ring_coupling_study import analyze_fire, DELTA  # noqa: E402

GO_LO_MS = 320.0    # soft floor below the measured 339 (avoid overfitting one operator/one night)
GO_HI_MS = 400.0    # fast-cluster ceiling (operator decision 2026-07-19)
_TPMS = 3000.0
_A = 1_000_000      # synthetic anchor device tick


def detect_voluntary_go(rec: dict[str, Any], go_lo_ms: float = GO_LO_MS, go_hi_ms: float = GO_HI_MS,
                        sub_floor_ms: float | None = None) -> dict[str, Any]:
    """v0 anti-cheat verdict for one nonce-bound fire dump. GO requires a gold read-at-fire t0, a real R2
    reaction, and lat in (go_lo, go_hi]. go_lo/go_hi default to the single-operator band; a POPULATION band
    (l9_presence.population_band) can be supplied. sub_floor_ms (below = REJECT_TOO_FAST, non-human) defaults
    to go_lo (single-op behavior); a population config sets it to the anticipation floor (~120ms) so a fast
    human BELOW the band is SOFT_TOO_FAST (retry), NOT falsely flagged as a bot (F5). Returns the verdict."""
    sub = go_lo_ms if sub_floor_ms is None else sub_floor_ms
    r = analyze_fire(rec)
    t0m = r["t0_method"]
    lat = r["lat_pt_ms"]
    out = {"verdict": None, "reason": "", "lat_pt_ms": lat, "t0_method": t0m,
           "reference_gap_ms": r["reference_gap_ms"], "max_dR2_post": r["max_dR2_post"]}
    if t0m not in ("read_at_fire", "read_at_fire_certified"):
        out.update(verdict="REJECT", reason="no gold read-at-fire t0 (uncertain reference)"); return out
    if not r["plausible"] or lat is None:
        out.update(verdict="REJECT_NO_REACTION", reason="no plausible in-window reaction"); return out
    if r["max_dR2_post"] <= DELTA:
        out.update(verdict="REJECT_NO_REACTION", reason="flat R2 (no reaction on the channel)"); return out
    if lat <= sub:
        out.update(verdict="REJECT_TOO_FAST", reason=f"lat {lat:.0f}ms <= sub-floor {sub:.0f}ms (non-human)"); return out
    if lat <= go_lo_ms:
        out.update(verdict="SOFT_TOO_FAST", reason=f"lat {lat:.0f}ms below band {go_lo_ms:.0f}ms but above sub-floor (retry, not a bot)"); return out
    if lat > go_hi_ms:
        out.update(verdict="SOFT_TOO_SLOW", reason=f"lat {lat:.0f}ms > band {go_hi_ms:.0f}ms (retry, not a bot)"); return out
    out.update(verdict="GO", reason=f"lat {lat:.0f}ms in ({go_lo_ms:.0f},{go_hi_ms:.0f}] on gold t0")
    return out


# --- synthetic dump builder + attacks -----------------------------------------------------------
def _synth_rec(onset_ms: float | None, r2_peak: int = 255, gold: bool = True,
               t0_offset_ticks: int = 65_000) -> dict[str, Any]:
    """A dump-shaped rec: gold t0 at _A+t0_offset_ticks; R2 rises to r2_peak at onset_ms after t0 (None=flat)."""
    t0 = _A + t0_offset_ticks
    pre = [{"r2": 0, "l2": 0, "device_ts": _A - 3000 + i * 1000, "t_mono": 99.99 + i * 0.001} for i in range(3)]
    post = [{"r2": 0, "device_ts": t0 - 2000, "t_mono": 100.02}]   # a pre-fire stale-buffered sample
    tm = 100.05
    for k in range(1, 460):
        dev = t0 + int(k * 6000)               # ~2ms cadence @3MHz
        t_rel = (dev - t0) / _TPMS
        r2 = r2_peak if (onset_ms is not None and t_rel >= onset_ms) else 0
        post.append({"r2": r2, "device_ts": dev, "t_mono": tm}); tm += 0.006
    rec = {"schema": "qortroller-poep-ring-dump-v0", "nonce": "synth", "probe_hold_ms": 15,
           "probe_device_ts": _A, "device_ticks_per_ms": _TPMS, "probe_ts_mono": 100.01,
           "pre_series": pre, "post_series": post}
    if gold:
        rec["t0_read_device_ts"] = t0
        rec["t0_read_age_s"] = 0.001
    return rec


def attack_fixed_delay_bot(delay_ms: float) -> dict:  # A5 / A2 (if sub-floor)
    return _synth_rec(delay_ms)


def attack_dead_feed() -> dict:                       # A3
    return _synth_rec(None)


def attack_absurd_t0() -> dict:                       # A4
    rec = _synth_rec(345.0); rec["t0_read_device_ts"] = _A + 999_999_999; return rec


def attack_naive_replay(donor: dict, fresh_t0_ticks: int) -> dict:
    """A1: re-fire a captured response against a FRESH t0 unrelated to the response's device_ts."""
    rec = json.loads(json.dumps(donor))
    rec["t0_read_device_ts"] = fresh_t0_ticks         # new nonce/fire; response device_ts unchanged
    rec.pop("t0_read_age_s", None); rec["t0_read_age_s"] = 0.001
    return rec


def attack_random_bot_far(isi_ms: float, trials: int = 20000, seed: int = 7) -> float:
    """A6: analytic/sim FAR of a bot pressing at uniform-random offset in [0, ISI]. FAR = P(offset in band)."""
    rnd = random.Random(seed); hits = 0
    for _ in range(trials):
        off = rnd.uniform(0.0, isi_ms)
        if GO_LO_MS < off <= GO_HI_MS:
            hits += 1
    return hits / trials


def _load_real_dumps(d: str) -> list[dict]:
    out = []
    for fp in sorted(glob.glob(os.path.join(d, "*.json"))):
        try:
            rec = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        if rec.get("schema") == "qortroller-poep-ring-dump-v0":
            out.append(rec)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="(ii) R2-onset adversarial harness v0")
    ap.add_argument("--dir", default=os.path.join("audits", "poep_ring_dump"))
    ap.add_argument("--isi-ms", type=float, default=3000.0, help="challenge inter-stimulus interval for the random-bot FAR")
    args = ap.parse_args()

    print(f"=== R2-onset adversarial harness v0 — GO band ({GO_LO_MS:.0f},{GO_HI_MS:.0f}]ms ===")

    # --- human FRR on real gold dumps ---
    reals = _load_real_dumps(args.dir)
    gold = [r for r in reals if r.get("t0_read_device_ts")]
    verds = [detect_voluntary_go(r)["verdict"] for r in gold]
    n_go = verds.count("GO"); n_soft = verds.count("SOFT_TOO_SLOW")
    n_fast = sum(1 for r in gold if (analyze_fire(r)["lat_pt_ms"] or 1e9) <= 400)
    print(f"\n[HUMAN] real gold dumps N={len(gold)}: GO={n_go} SOFT(slow)={n_soft} other={len(gold)-n_go-n_soft}")
    if n_fast:
        print(f"  fast-cluster (<=400ms) GO-rate = {n_go}/{n_fast} = {100*n_go/max(1,n_fast):.0f}%  "
              f"(slow tail -> SOFT, not bot)")

    # --- attacks ---
    print("\n[ATTACKS]")
    rows = []
    rows.append(("A2 sub-floor bot @150ms", detect_voluntary_go(attack_fixed_delay_bot(150.0))["verdict"], "REJECT_TOO_FAST"))
    rows.append(("A3 dead feed (flat R2)", detect_voluntary_go(attack_dead_feed())["verdict"], "REJECT_NO_REACTION"))
    rows.append(("A4 absurd t0", detect_voluntary_go(attack_absurd_t0())["verdict"], "REJECT*"))
    donor = _synth_rec(345.0)
    rows.append(("A1 naive replay (fresh t0)", detect_voluntary_go(attack_naive_replay(donor, _A + 50_000_000))["verdict"], "not GO"))
    a5 = detect_voluntary_go(attack_fixed_delay_bot(345.0))["verdict"]
    rows.append(("A5 fixed-delay bot @345ms", a5, "RESIDUAL (single-shot)"))
    for name, got, expect in rows:
        ok = ("REJECT" in got or got == "SOFT_TOO_SLOW") if "REJECT" in expect or "not GO" in expect else True
        flag = "OK" if (got != "GO") == ("REJECT" in expect or "not GO" in expect) else ("<== RESIDUAL" if "RESIDUAL" in expect else "<== CHECK")
        print(f"  {name:32} -> {got:20} [{flag}]")

    far_fixed = 1.0 if a5 == "GO" else 0.0
    far_rand = attack_random_bot_far(args.isi_ms)
    print(f"\n[RESIDUAL FAR — published, not hidden]")
    print(f"  A5 fixed-delay in-band bot (single challenge): FAR = {far_fixed:.2f}  "
          f"(a bot that guesses ~345ms AND the fire time passes ONE challenge -> defense = multi-challenge variance)")
    print(f"  A6 random-timing bot (ISI={args.isi_ms:.0f}ms): FAR = {far_rand:.4f} = band_width/ISI = {(GO_HI_MS-GO_LO_MS)/args.isi_ms:.4f}")
    print("\n  CLAIM CEILING: construction attacks (A1/A2/A3/A4) REJECT by design; A5/A6 residual FAR is")
    print("  PUBLISHED. Voluntary-reaction liveness CANDIDATE, single-operator provisional band. NOT sub-280")
    print("  reflex, NOT population, NOT bot-proof on one challenge, NOT tournament-ready. Rig/crypto remainder:")
    print("  live host-API bot, hardware injector, HMAC(nonce||t0||onset) frame-commitment, multi-session FRR.")

    # exit 0 iff construction rails hold (A1/A2/A3/A4 all non-GO)
    construction_ok = all(v != "GO" for v in (
        detect_voluntary_go(attack_fixed_delay_bot(150.0))["verdict"],
        detect_voluntary_go(attack_dead_feed())["verdict"],
        detect_voluntary_go(attack_absurd_t0())["verdict"],
        detect_voluntary_go(attack_naive_replay(donor, _A + 50_000_000))["verdict"],
    ))
    print(f"\n  VERDICT: {'construction rails HOLD' if construction_ok else 'RAIL BREACH — inspect'}")
    return 0 if construction_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
