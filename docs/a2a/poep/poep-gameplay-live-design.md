# Design: Live dual-connect PoEP challenge path (challenge-live)

**Status:** DESIGN OPEN · 2026-07-17 · A2A arc `poep-gameplay-live`  
**Prior:** dry skeleton PASS (round-05) · round-04 honesty model is **load-bearing**  
**Not:** desk probe campaigns · `poep_enabled` flip · FLIP-B / SE · chain spend  

---

## 1. Problem

Dry gameplay session can mint **`dry_plumbing_ok` only**.  
**`presence_session_candidate_ok`** structurally requires:

| Requirement | Today |
|-------------|--------|
| `mode == "live"` | CLI `start` forces `dry` |
| All GO events `live_hardware=True` | dry always False |
| `activity_source == "bridge"` | CLI forces `cli_inject` |
| Real HID challenge + IMU | `challenge-live` exits 3 (LIVE_TODO) |

**Gap closed by this increment:** wire the dual-connect live path so a real play session can become a **candidate** (still not a flip).

---

## 2. Claim (unchanged, locked)

> During an active play session on the registered Edge, under a **trusted capture host**, sparse unpredictable low-amplitude adaptive-trigger challenges produce live-bound responses under catch rules. **Session liveness** (FLIP-A host-trusted) — not identity, not anti-compromised-PC (FLIP-B).  
> `poep_enabled` stays **False**. `is_presence_verdict` stays **False**.

---

## 3. Topology (normative)

```text
  PS5 / console  <---BT---  DualSense Edge  ---USB--->  PC (bridge + challenge driver)
       |                         |                         |
     game inputs              pad physics              force write + IMU read
     (BT HID)                 (single body)            (USB exclusive poll ~1 kHz)
```

| Rule | Detail |
|------|--------|
| **Bridge** | **UP** for live (opposite of desk HID-exclusive path) |
| **USB** | PC owns adaptive trigger challenge + IMU capture |
| **BT** | Console owns gameplay (operator dual-connect standard) |
| **PCC** | Prefer `capture_state=NOMINAL` + `host_state` in `{EXCLUSIVE_USB, UNKNOWN}` before arming |
| **Device** | Registered Edge `581a836c…` (or current birth-cert device_id) |

If USB poll collapses (CONTESTED / DEGRADED), **refuse** new challenges (fail-closed).

---

## 4. Round-04 honesty model (must not regress)

| Axis | Live path must |
|------|----------------|
| **dry_plumbing_ok** | Still reachable offline for harness |
| **presence_session_candidate_ok** | Only if `mode=live` AND effective all-GO-live AND `activity_source=bridge` AND floors (MIN_GO_*=2, activity ≥0.5, catch FA) |
| **cli_inject** | Must **never** mint candidate (unchanged) |
| **State file spoof** | Dry-mode cannot claim live; live mode needs a **live seal** stronger than hand-edit (see §7) |
| **Amplitude** | Default **60**, hard max **80** — never desk 255 mid-game |
| **MENU/UNKNOWN** | No challenge issue |

---

## 5. Components

### 5.1 Activity source: bridge (not CLI JSON)

**Input (v1):** poll bridge HTTP (read-key) for fields already used in GAD / capture health, e.g.:

- `GET /bridge/capture-health` (or existing equivalent): `capture_state`, `host_state`, `poll_rate_hz`, optional `latest_gameplay_context`  
- Session loop also samples **live HID** on USB: `trigger_active` / recent press events for `trigger_active_fraction` over a short window  

**Map to `classify_activity`:** same pure function; **provenance** `activity_source="bridge"` only when samples come from this path (never from free `--activity-json` on a live session).

**Rate:** e.g. 1–2 Hz activity ticks while session open (tunable named constant).

### 5.2 Live challenge driver

**Reuse (do not fork crypto):**

- Nonce: `secrets` / existing `fresh_nonce` pattern  
- Schedule: `next_challenge_delay_s` (90–300 s default)  
- Fire: same family as desk `_fire_probe_silent` but **coexist with bridge ownership of HID** — prefer calling through bridge/controller stack if dual-writer is unsafe; if process-local HID, **document exclusive USB ownership during fire window**  
- Verify: `verify_live_response` unchanged  
- Catch: optional `plan_catch_kind` / `score_trial` on NO_GO (no force write)  
- Amplitude: `LOW_AMPLITUDE_FORCE_DEFAULT` (60), clamp ≤80  

**GO path:** force write at `t_challenge` → capture post-window IMU → build real `ChallengeResponse` → verify → `SessionChallengeEvent(live_hardware=True)`.  

**NO_GO path:** same arm/delay, **no** force → score catch on peak → `live_hardware=False` on event is OK for NO_GO (no stimulus); candidate rule uses **GO** live flags.

### 5.3 Session lifecycle CLI / service

```text
start-live   --player Pn --device-id …   # mode=live, activity_source=bridge, live_seal
tick-loop    (background or external): bridge+HID activity samples
scheduler    when ACTIVE + delay elapsed + PCC ok → challenge-live
stop-live    → summarize_session → audits/poep_gameplay_live_{player}_{utc}.json
```

**Operator “ready?”** before first challenge: print topology + PCC snapshot; require `--i-am-playing` or interactive confirm (fail-closed if not).

### 5.4 Live seal (anti state-file spoof)

v0.1 dry-first allowed hand-edited `mode=live`. Live increment **must**:

- `start-live` writes `mode=live` + `live_seal = H(session_id || device_id || t_start || process_nonce)`  
- `summarize` / candidate_ok requires seal recomputes OR seal only present when started via start-live in this process  
- Refuse loading foreign state as live without seal match  

(Exact seal is local bookkeeping, **not** FROZEN-v1.)

---

## 6. Candidate score (v0.1, unchanged floors)

```text
presence_session_candidate_ok iff
  dry_plumbing_ok-style gates hold:
    n_go_issued >= 2 AND n_go_verify_pass >= 2
    AND (n_nogo==0 OR human_fa_rate <= 0.05)
    AND gameplay_active_fraction >= 0.5
  AND mode == "live"
  AND effective_live (all GO live_hardware)
  AND activity_source == "bridge"
  AND live_seal valid
  AND poep_enabled remains False in output
```

A **single** play session that issues ≥2 GO and gets ≥2 verify-pass while mostly ACTIVE is enough for a **candidate artifact** — not a protocol flip.

---

## 7. Phased delivery

| Phase | Deliverable | Rig? |
|-------|-------------|------|
| **L0** | This design + A2A round-01 open | No |
| **L1** | Live seal + `start-live` / refuse path; bridge activity poll pure+mocked tests | No |
| **L2** | Challenge driver integration (mock HID in tests; real fire behind flag) | Partial |
| **L3** | Operator dogfood: dual-connect + game + ≥1 candidate session | **Yes** |
| **L4** | Optional: wire into node receipt / StreamView as advisory only | Later |

---

## 8. Adversary / honesty bars (grok verify after build)

1. CLI dry path still **cannot** mint `presence_session_candidate_ok`.  
2. Forged `mode=live` without seal → no candidate.  
3. MENU-only bridge samples → no challenges / no candidate.  
4. Amplitude never defaults to 255; clamp ≤80.  
5. PCC CONTESTED → no new challenges.  
6. Desk scripts not required for this path; no desk N campaign.  
7. Claim string still FLIP-A only.  
8. `poep_enabled=False` on every summary.

---

## 9. Explicit non-goals

- Enabling product flags  
- Path A re-anchor / F-PATHA-1  
- Waveform hard gate  
- Tournament BLOCK  
- More desk `--catch` volume as mainline  

---

## 10. Operator dogfood checklist (when L3 opens)

1. Bridge up; Edge USB to PC; BT to console; game running.  
2. Confirm capture-health healthy.  
3. `start-live` → hear/feel rare low force only when playing (not menu).  
4. Play until ≥2 GO pass (or stop and read honest fail reasons).  
5. `stop-live` → inspect summary: `presence_session_candidate_ok` only if gates true.  
6. Still not a flip.

---

## 11. One-liner

**Live dual-connect = bridge-attested activity + sealed live mode + sparse low-amp HID challenges during real play, reusing P-LIVE-0 verify — first way `presence_session_candidate_ok` can be true without lying.**
