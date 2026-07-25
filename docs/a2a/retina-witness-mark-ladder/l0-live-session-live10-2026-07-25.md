# L0 live session — `cfb_rwm_live_10` (2026-07-25)

**Verdict: RWM diversity win · L9 continuum non-win.**

OBS freeze from live_07/08 was fixed before this session. Content-hash de-dup
(F-RWM-FROZEN-CONTENT) was already on `main`. This session is the first
**pure-session, diverse-panel, N≥146** L0 cite after that fix.

**Do not cite this session as L9 stick↔screen continuum success.**

---

## Capture ops

| Field | Value |
|-------|--------|
| Label | `cfb_rwm_live_10` |
| Start | ring cleared → `--capture --uvc-index 2` (post-OBS-fix) |
| Source | UVC #2 @ 1920×1080 |
| Log span | 2026-07-24 23:26:30 → 23:41:42 (~15 min) |
| Stop ring / archive | **367** crops (pure session) |
| Archive | `retina_kf_archive/cfb_rwm_live_10_1784953588` (gitignored) |
| RWM at stop | **auto** — 367 frames marked + chained |
| Post-check | **EXIT 0** |

---

## Claims separated (load-bearing)

### A. RWM / panel-archive (WIN)

| Goal | Target | Result |
|------|--------|--------|
| Frame count | N ≥ 146 | **367 — PASS** |
| Content diversity | unique ≫ 1 | **367/367 (100%) — PASS** (not FROZEN_RING) |
| Auto-RWM at stop | yes | **PASS** |
| Pure ring | cleared before start | **PASS** |
| Locator full cycle | N ≥ 146 + decode | **PASS** (decoded on all 367) |
| Chain / originals | re-verify + byte-identical | **PASS** |

Measured: `scripts/rwm_post_session_check.py --label cfb_rwm_live_10` EXIT 0;
manifest `count=367`; `rwm_manifest_chain.json` present.

**Cite live_10 for:** pure-session auto-RWM + diversity + locator after OBS fix.

### B. L9 / NQPV continuum — stick↔screen coupling (NOT a win)

RGC diag ticks from `retina_daemon_cfb_rwm_live_10_1784953588.log` (92 ticks):

| Metric | Value |
|--------|--------|
| L9 `LIVE_COUPLED` | **6 / 92 (~6.5%)** |
| L9 `REPLAY_OR_RELAY` | **85 / 92 (~92%)** |
| NQPV `COUPLED_CLEAN` | **6** |
| NQPV `IMPLAUSIBLE` | **85** |
| Coupling score (n=91) | mean **~0.073** (min 0.01, max 0.354) |
| Coupling when LIVE | mean ~0.24 |
| Coupling when REPLAY | mean ~0.03 |
| Timestamp source | **`wall_fallback` only** (92 mentions) |

Timeline: brief LIVE islands early and mid-session; **rest of session REPLAY_OR_RELAY**.

Controller/PoAC path was healthy (**368** DualShock `Record verified` lines) — pad was
live. Continuum FAIL here means **optical motion was not locked to stick under RGC
gates**, not “player was offline.”

**Do not cite live_10 for:** L9 continuum SYNCHRONIZED / stable LIVE_COUPLED session,
NQPV COUPLED_CLEAN session, or “screen proves this stick now” for the full match.

### C. Other surfaces (context, not L9 win)

| Surface | Result |
|---------|--------|
| Cross-channel latency corpus jsonl | **empty (0 bytes)** — no τ_lag session scorecard from this harvest |
| DA uploads | many SUCCESS (~60KB) local path |
| On-chain | `CHAIN_SUBMISSION_PAUSED` — no spend |
| PoSP / CONTINUOUS_PRESENT | not issued by this daemon stop |

---

## Why both can be true

| Layer | Needs | live_10 |
|-------|--------|---------|
| RWM panel diversity | Changing pixels in panel ROI | Strong |
| L9 continuum | Stick-driven optical coupling + lag in band | Weak (~7% LIVE) |

Left-panel ROI (`0.0,0.28,0.32,0.67`) can vary frame-to-frame (RWM win) while still
failing stick↔screen continuum (L9 non-win). Keep claims separate in any external write-up.

---

## Follow-ups / continuum (ops + engineering — **not shipped in this note**)

Priority order (objective; open work, not completed here):

1. **Confirm in-play stick motion** when reading RGC (not play-call UI / pause).
2. **Center-field ROI (or dual crop)** for coupling vs left-panel for RWM.
3. **Prefer device timestamps** over `wall_fallback` for lag when available on this path.
4. **Measure end-to-end video lag** (OBS + card); REPLAY often means delayed/decoupled video, not “you weren’t playing.”
5. **Keep RWM and L9 claims separate in docs** — live_10 is a **RWM diversity win**, not an L9 continuum win (this document).

---

## Cite guidance

| Claim | Preferred evidence |
|-------|-------------------|
| Diverse pure-session auto-RWM + locator N≥146 | **live_10** (this note) |
| FROZEN_RING / OBS freeze failure modes | live_07 / live_08 notes |
| L9 continuum success | **not this session** — need REPLAY minority + sustained LIVE_COUPLED |
| Ladder dogfood (escrow / stranger) | live_07 dogfood still valid; live_10 optional re-dogfood |

---

*Gate note only. No ROI/lag/timestamp code changes in the commit that introduces this file.*
