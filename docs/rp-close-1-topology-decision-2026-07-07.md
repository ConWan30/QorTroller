# RP-CLOSE-1 Gate RP-1 — Remote Play Capture-Topology Decision (D-RP-1)

**Status: DECIDED — B-then-A (operator, 2026-07-07).**
**Date opened: 2026-07-07.**

## The question

For QorTroller to make the "novel anti-cheat *when playing Remote Play*" claim, the
authorship/PoSP stack (KAS + killfeed + PoSP SYNCHRONIZED) must run against a live RP
stream. It has run successfully only on direct HDMI (Match 13). The one full RP attempt
(Match 12) failed for measured, structural reasons. The topology for Match 14 must be
decided before the match is scheduled.

## Measured evidence (all live, not assumed)

| # | Finding | Source |
|---|---------|--------|
| E1 | WGC screen capture competes with RP's GPU **decoder** cross-process — capturing lags the game regardless of rate; a separate capture process is throttled to ~13fps under load. **Process isolation REFUTED.** | 2026-06-27 live A/B (cycle-46 premise refuted) |
| E2 | Match 12 under RP: bridge at **94.9% CPU**, ema_fps **3.76**, only 35 crops archived — RP streaming codec overhead named as root cause. | M12 close-out (`5b607a0d` arc) |
| E3 | Match 13 direct HDMI (PS5→laptop): **524 crops**, AUTHORED_SESSION authored=8, PoSP SYNCHRONIZED. HDMI path eliminated the codec contention entirely. | M13 (`5b607a0d`) |
| E4 | Presence oracle DOES work same-machine over RP at reduced density: COUPLED_CLEAN **0.348 @ 13.6fps** (lean mode + on-demand bursts). | 2026-06-27 (`2758c74d`) |
| E5 | Operator sidecar analysis: a sidecar **process** cannot give capture its own GPU (one laptop GPU, shared, measured); the valid evolution is a sidecar **device** (own silicon). | cycle-48 |
| E6 | Bridge DB at 5.3GB again as of 2026-07-07 (preflight live run) — cycle-49 lag source regrown; fresh `DB_PATH` override needed regardless of topology. | RP-5 preflight first live run |

## The two honest options

### Option A — Sidecar DEVICE (recommended for the full-strength claim)

Capture hardware with its own silicon witnesses the RP client's rendered output:
HDMI capture card on the client laptop's display output, a mini-PC, or a second machine.
The game stays on Remote Play untouched; only the witness moves off the shared GPU.

- **Pros:** Full capture density (M13-class, ~520+ crops/match) while the game runs RP.
  Both lobes at full strength: HID is USB-direct to the client (RP's native topology),
  screen is contention-free. This is the *tournament-deployable* shape — a witness box
  next to the player is exactly what a LAN-tower BT witness already looks like in the L8
  design. M13's HDMI-direct run is effectively the prototype of this topology.
- **Cons:** Requires hardware the rig may not have today (capture card ≈ $20–150, or a
  second machine). One more device to provision/trust — the witness device becomes part
  of the verifier-independence story (arguably a PRO long-term).
- **Cost to first result:** hardware acquisition + one match.

### Option B — Same-machine reduced-density (available today, weaker numbers)

Accept the measured ~13fps WGC ceiling under RP; run Match 14 on the current laptop with
lean mode + on-demand/dense bursts, and publish whatever recall floor survives.

- **Pros:** Zero new hardware; Match 14 can run as soon as the operator is at the rig.
  Whatever number comes out is an honest, publishable RP floor — even a low floor with
  the zero-false-read precision bar held is a real claim ("high-precision,
  conservative-recall under RP").
- **Cons:** Archive density will be a fraction of M13's (M12 managed 35 crops vs 524);
  the K=3 promotion gate may rarely complete inside kill windows → risk of an honest but
  weak AUTHORED result (or INSUFFICIENT_KILLS) that under-represents the mechanism.
  Contention remains a per-match variance source even with lean mode.
- **Cost to first result:** one match, today's hardware.

### Non-options (measured out)

- **Sidecar process on the same machine** — refuted live (E1, E5). Not revisited.
- **HDMI-direct as "the RP answer"** — M13's topology bypasses RP entirely (PS5 renders
  natively next to the laptop). It proves the mechanism, not the remote deployment.

## Recommendation

**B first, then A.** Run Match 14 as Option B — it needs no hardware, and even a weak
AUTHORED/recall result under RP converts the claim from extrapolated to demonstrated
while measuring exactly how much Option A's hardware would buy. Then acquire the capture
card and re-run as Option A to publish the full-density RP figure. The two matches
together give the honest floor AND the deployable ceiling, and the delta is itself
publishable evidence for the sidecar-witness architecture.

Regardless of option: fresh `DB_PATH` override (E6), RP-5 preflight must pass, VPN off,
and the launch stack per the C-3.2 runbook.

## Decision record

- **D-RP-1: B-then-A** (operator, 2026-07-07) — Match 14 runs Option B (same-machine
  reduced-density, today's hardware); Match 15 reruns as Option A (sidecar device)
  after capture-card acquisition. The B/A delta is itself publishable evidence for
  the sidecar-witness architecture.
- Match 14 runbook: `docs/rp-close-1-match14-runbook.md`.
- Option A hardware prerequisite: HDMI/USB capture card for the RP client's display
  output (≈$20–150) — OPERATOR-ACTION, no deadline.
