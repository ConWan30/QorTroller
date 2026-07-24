# POEP population reaction-time band — 2-operator rig runbook

**Goal:** promote the population band from **PROVISIONAL** to **measured** by capturing R2-onset reaction
latencies from **≥2 genuinely-different people** (`MIN_OPERATORS_FOR_POPULATION=2`), each with **≥20 clean
fires** (`MIN_SAMPLES_PER_OPERATOR=20`). Candidate/advisory only — this **gates nothing**; `poep_enabled` /
`L6B` / `L6_CHALLENGES` stay **False**; zero spend; no chain; no flag flip.

This is the **standalone desk reflex** capture (bridge OFF) — NOT a gameplay/Remote-Play session. It is the
clean path; do **not** use the Remote-Play gameplay ring dumps for the band (their device latency is inflated
per finding **F-RIG27-8**).

---

## Honesty rails (read before you start)
- **"Operator" = a distinct LABEL, and the tool cannot verify a label is a distinct PERSON.** The band is a
  real population claim **only if the labels are genuinely different humans.** One person under two labels is
  NOT a population — the pooling script prints this warning every run.
- The **~120 ms anticipation sub-floor** is a conservative **uncited** general-psychophysics prior, not our
  measurement. N=2 is a **minimal** population sample, not a robust one.
- Capture dumps are **gitignored** (biometric-adjacent, public repo). **Never commit** `audits/poep_live_capture_*.json`.
- Interactive: the person's reflex IS the input. The fire is **silent** (no on-screen cue) — you react to the
  felt R2 buzz. Run it in your own terminal.

---

## Prerequisites
- The **registered** DualShock Edge (`581a836c…`, VID `054C` / PID `0DF2`), **USB-C to the laptop**.
- **Stop the bridge first** (dual-writer contention — the runner takes the pad exclusively).
- Python env active; repo root `C:\Users\Contr\vapi-pebble-prototype`.

---

## Step 0 — Preflight (once)
1. Plug the Edge into the laptop by **USB-C**. If it's also BT-paired to a PS5, that's fine — the desk capture
   ignores BT; it reads the USB HID directly.
2. **Stop the bridge** if it's running (close its terminal / Ctrl-C). Confirm nothing else holds the pad.
3. Sanity-check the runner is reachable:
   ```
   python scripts/poep_live_capture.py --help
   ```

> **⚠ MODE + TECHNIQUE (learned the hard way 2026-07-19 — cost an hour):**
> - **Use `--mode pulse`** (the default). Pulse *vibrates* and is felt at rest, like rumble. Do **NOT** use
>   `--mode rigid` — rigid is a *resistance* only felt on a hard R2 pull, so it reads as "the buzz is dead"
>   even though the actuator is fine.
> - **Keep light pressure on R2** (finger resting *with slight engagement*, not feather-light) so the pulse
>   transmits through the trigger. A feather-rest may not feel it.
> - Sanity: a clean capture shows `class=HUMAN` / `LIVE-VERIFY PASS` with latencies ~230–400 ms and peaks in
>   the thousands of LSB. If everything is `NO_RESPONSE` / peak ~7 LSB, the buzz isn't being felt (check mode,
>   R2 pressure, and that `--mode pulse`). To isolate a truly-dead actuator: lightbar+rumble use the *same*
>   output report — if those work but the trigger doesn't, it's mode/perception, not hardware.

## Step 1 — Person A capture (≥20 fires)
Person A holds the pad. Run (pick a **real** label — use the person's name, not P1/P2):
```
python scripts/poep_live_capture.py --player alice --count 25 --mode pulse --no-store
```
Per fire: the runner arms silently, then after an unpredictable delay fires an **R2 adaptive-trigger PULSE
buzz** — Person A **presses R2 as soon as they feel it**. Repeat ×25 (~a few minutes). It writes one labelled
session file: `audits/poep_live_capture_alice_<date>_<time>.json`. (`--no-store` skips the bridge DB; the JSON
artifact — which the band reads — is still written.)

> Aim for ≥20 *clean* reactions. No-reaction fires (you missed the buzz) are recorded with `latency_ms=null`
> and are dropped automatically at pooling — so capture a few extra (25) to clear 20 clean.

## Step 2 — Person B capture (≥20 fires)
**A different person** holds the same pad. Run with a different real label:
```
python scripts/poep_live_capture.py --player bob --count 25 --mode pulse --no-store
```

## Step 3 — Pool + score the population band
```
python scripts/poep_population_band.py --players alice,bob --min-ms 120 --max-ms 800
```
- `--players alice,bob` scopes to your two real operators (so old/ambiguous labels in `audits/` don't pollute the band).
- `--min-ms 120 --max-ms 800` drops no-reaction / slow-outlier fires (disclosed in the output). 120 ms = the
  anticipation floor; 800 ms is a generous voluntary-reaction ceiling.

**What good looks like** — the real N=5 run (Con+Fari+Khamari+Roy+Pookie, 2026-07-20, window [120,450]; see
`audits/poep-population-band-con-fari-2026-07-19.md`): per-operator medians **254–295 ms**, band
**(195, 416] ms** (now the detector default), `degenerate_band: False`, **`PROVISIONAL: False`**, per-op FRR
~0 (Roy 0.043). 4 held-out exercises across 4 people (ConHeldout/Khamari/Pookie/Roy, NOT Fari); Roy the moderate reactor stretched the ceiling. A wide band gives
a high single-shot `worst_case_far_population_band` (e.g. ~0.18) — that is expected and honest: the anti-cheat
strength comes from **multi-challenge compounding (K=5)**, not one shot. Tighten the band (more/cleaner data)
or raise K to lower it.

## Step 4 (optional) — score a live session under the population band
Score a directory of gold ring dumps under the measured population sub-floor (a fast human below the band reads
`SOFT`/retry, not `SUSPECTED_BOT`):
```
python scripts/qortroller_anticheat_report.py --dir audits/poep_ring_dump --population
```

---

## After the session
- The band result is **candidate evidence** — record it (screenshot / paste into an audit note). Do **not**
  flip `poep_enabled` or `L6B`; those stay operator decisions gated on the full waveform + Stage-A work.
- **Do not commit** the `audits/poep_live_capture_*.json` capture files (gitignored).
- If the two labels turned out to be the same person, the band is **not** a population band — recapture with a
  genuinely different second person.

## Known limits (unchanged)
- A **reactive bot** watching the HID force-output command and reacting in-band (A-REACTIVE) is uncloseable for
  any host-timed proof — out of scope until controller-firmware force-timestamps + Stage-A land.
- N=5 (small sample), **scoped to competitive players** (fast-to-moderate reactors, by operator decision;
  slow reactors out of scope, handled gracefully as `SOFT_TOO_SLOW`/retry); the 120 ms floor is an uncited
  prior; the band widens the FAR (it fixes a false-*reject*, not a false-*accept*). All advisory; gates nothing.
