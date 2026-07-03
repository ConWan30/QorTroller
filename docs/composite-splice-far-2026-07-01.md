# Composite Authorship — Replay-Splice FAR (2026-07-01)

**Question.** The composite `AUTHORED_PRESENT` path (`97b86b3c` + `f6e7061f`) is validated genuine-only
(3/3 kills, 2/2 deaths, 0 false positives vs background). It had never faced an adversary. This is its
first paired forgery attempt, per the standing discipline (no genuine claim stands without its paired
forgery — the same posture as the `NO_SAFE_THRESHOLD` correlation result).

**Attack — replay-splice.** A forger replays the operator's own archived gameplay (real own-handle kill
rows) on screen while pressing R2 live on the certified controller. The killfeed rows are genuine, so the
authorship signal alone cannot distinguish this from live play. The only structural defense is the
conjunction already built in: classification runs *only inside live R2 windows*, and the composite takes
*max-over-window*. The attack succeeds when a replayed kill row falls inside a live R2 window and clears
`match_floor = 0.66`.

**Finding that reframes the arithmetic.** The deployed R2 window is `R2_WINDOW_MS = (50, 5000)ms`, **not**
the (50, 900) it was originally. It was widened in `15e2b487` to fix a live detection bug (windows closing
between ~1.5s loop iterations). Window width is the dominant FAR driver, so a detection fix directly raised
splice exposure. Both widths are reported below.

---

## Phase 0 — Monte Carlo (SIMULATED grade)

`scripts/splice_far_montecarlo.py`. 3 genuine kills (killer-position hot crops at 0.702 / 0.736 / 0.843)
in a 640s replay loop; the exact deployed composite rule; N=8000 trials; two attacker timing models
(Poisson/uniform + clustered/burst); dwell width swept (the archive samples each kill once at ~4s cadence,
so the ≥floor on-screen duration is unknown and swept 0.5 / 2 / 4s).

**Base-rate arithmetic (the interpretable core):** per-session `FAR ≈ 1 − (1−ρ)^K`, `K=3` kills,
`ρ` = R2 coverage fraction. `ρ` is driven by the window tail: **one press "listens" for 4950ms**, so even
modest firing gives high coverage. The genuine session itself ran at ~1 classification / 4.3s during
gameplay (near-continuous R2 coverage), so a splicer firing *merely play-like* sits at `ρ ≥ 0.5`.

**DEPLOYED (50, 5000ms) window** — per-session FAR:

| firing (Poisson) | ρ | dwell 0.5s | 2s | 4s |
|---|---|---|---|---|
| 5/min | 0.34 | 0.75 | 0.82 | 0.89 |
| 10/min | 0.56 | 0.94 | 0.97 | 0.99 |
| 20/min | 0.81 | ≈1.0 | ≈1.0 | ≈1.0 |
| 40/min | 0.96 | ≈1.0 | ≈1.0 | ≈1.0 |

per-window FAR 2.5–4.2%. Clustered/burst model: 0.58 (2 bursts/min) → 0.99 (10 bursts/min) — same
magnitude; the 5000ms tail dominates either way.

**ORIGINAL (50, 900ms) window (contrast):** per-session FAR 0.28–0.70 at 5/min, rising to 0.93–1.0 at
40/min. The narrower window helps at low firing but does not rescue authorship-alone against an
active-firing splicer.

**Limitation (why Phase 1 exists):** simulates *timing coincidence only*. It assumes the replayed video's
kill rows score the same as live capture — reasonable (same pipeline) but unverified, because a replay adds
a second encode generation that could soften scores below floor (which would *lower* the real FAR).

---

## Phase 1 — physical session (MEASURED grade)

Reconstructed the genuine kill rows into full frames (panel crop back at its ROI position) and played them
fullscreen (`scripts/adv_splice_replay.py`, 131-frame kill-dense loop, 2 loops ≈ 19 min); certified
controller USB'd to the laptop; both loops live; operator pressing R2 play-like. **No PS5.** Corpus
separation: all output routed to `adv_splice_*` / `retina_kf_adv_splice/`; the genuine `retina_kf_archive/
seg3_*` was read-only-displayed, never written (verified by construction and on disk).

**Raw measurement:** 6 kill appearances + 4 death appearances; composite resolved 22 windows.
- **Kill side: 0 AUTHORED / 6.**
- **Death side: 1 real own-death spliced through** — the genuine 0.796 death, re-captured at **0.6952
  (still ≥ 0.66)**, fell inside a sustained R2 window (gate→end = 304s, 201 members, `ρ≈1`) and fired
  `OWN_DEATH`. Anchor `1782947860544` aligns to the shown death at `1782947856235`.

**The kill-side 0 is CONFOUNDED — it is not a defense.** Daemon diag: the rig ran fullscreen replay + WGC
capture + bridge on one machine, driving capture to **13–17 fps** (target 60), **43 reacquires**, forcing
the governor to **downscale 8× / region 0.5**. Re-captured content capped at **0.7583 (roster) / 0.6952
(death)** vs genuine **0.70–0.84 (kills) / 0.775–0.796 (deaths)** — a systematic **~0.08–0.15 drop** from
the rig's observer-effect. That drop pushed the marginal kill rows (0.70–0.84) below the 0.66 floor.

**Phase 1 CORROBORATES Phase 0 — it does not refute it.** The one event whose re-captured score stayed
≥ floor (the 0.796 death) **spliced through** against sustained R2 coverage — exactly Phase 0's mechanism
made physical. The kill side read 0 only because the rig degraded the marginal kills below floor (a
measurement artifact). The 0.66 floor gives *incidental* protection against a *degraded* replay, not a
robust defense; a clean/strong replay splices. A cleaner Phase 1 (replay on a separate machine to remove
the FPS confound) would raise the measured kill FAR, not lower it.

---

## Conclusion

**Authorship-alone is NOT cert-grade against replay-splice.** Simulated per-session FAR 0.75–1.0 at the
deployed window; the physical session demonstrated a live splice hit on the one event that survived
re-capture. The R2-window conjunction provides weak adversarial protection because R2 coverage during
active play is near-total (the 5000ms tail).

**For D-CERT-5:** authorship needs a **second channel** to be cert-grade. The registered candidate is
`l2_ads` (the ADS / aim-down-sights coupling channel, currently `enabled=False`) — the **motivated next
build**.

### Mitigation space is two-dimensional — and one axis was purchased by a cadence workaround

The dominant term in the FAR≥0.9 result is **the window duration itself**. "One press listens for 4950ms"
is the whole story: the deployed window is ~5000ms because `15e2b487` widened it from 900ms to survive the
~1.5s consumption-loop cadence (windows were closing between iterations and missing classifications). That
same widening is what makes a single R2 press cover most of a replayed kill row's dwell. So a meaningful
fraction of the splice exposure was not structural to authorship-alone — it was **purchased by the cadence
workaround**.

This gives the design-table session two complementary levers, not one:
1. **`l2_ads` (structural):** an independent second channel — makes AUTHORED require corroboration the
   splice can't supply.
2. **Window tightening (parametric):** narrowing the window back toward the original 900ms multiplies `ρ`
   down directly (see the (50,900) table — FAR drops to 0.28–0.70 at low firing). This is enabled by a
   *faster classification cadence*, which the off-thread `_inline_classify_worker` could plausibly support
   (the 900ms window failed only because the single-flight loop tick was ~1.5s, not because classification
   itself is slow). The two levers are complementary, not competing.

**Load-bearing note for whoever revisits this:** *window duration is a splice-exposure parameter, currently
set by a cadence constraint, not a security decision.* It was widened for detection with no adversarial
model in view. When it is revisited, it must be revisited as a security parameter — the cadence fix and the
splice exposure are the same 4100ms.

**Evidence grade, stated honestly:** Phase 0 is simulation. Phase 1 is *one* adversarial session, *one*
operator, *one* game, confounded on the kill side by the rig's observer-effect. This is a first pairing
that establishes the finding — not a certification. Thresholds were not touched
(`match_floor` / killer-boundary / y-gate frozen throughout).

## Window-width note — 2026-07-02 (anchor-swap session): considered, already covered, unchanged

The live 0/19 authorship match prompted a fix for the R2-window: the diagnosis suggested the kill row
rendered *after* the captured frame, implying the window should extend past the fire. On the evidence it did
NOT: the deployed window is already `(50, 5000)ms` and 5000ms already spans the ~1.5s kill-cam lag — the row
is inside the window. The real cause was every classification inside the window locking onto the persistent
squad-roster rendering that the *roster* anchor matched (0.87–0.91), masking the transient feed kill row.
**Fix = anchor swap (roster→feed), NOT window widening.** The window stays 5000ms → **splice exposure
unchanged; no new ρ**. Extending would have paid the exact ρ-widening this doc guards for zero recall gain.
The window-duration security parameter is untouched by this session.
