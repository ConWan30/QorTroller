# F2.x — Residual Capture Contention (Post-Offload Failure Class)

**Status:** DESIGN / DECISION (2026-07-10). Loop: design → Claude audit → operator GO.  
**Predecessor:** D1 / D1.1 / F2 (`store_frame_checkpoint` + `get_detection_policy` → `to_thread`).  
**Does not:** retune authorship K/pad, prune DB, touch PoAC/FROZEN/chain.  
**Rails:** reversible experiments · default-OFF · no data drop · PV-CI 182 · 0 IOTX design.

---

## 1. Claim / scope

**F2 verifiably removed the two named loop-thread SQLite offenders from starvation dumps, but loop starvation and sub-30 fps capture persisted (and worsened under load). The residual failure class is no longer “wrappable sync call on the asyncio thread”; it is systemic contention (GIL/CPU, worker-thread pile-up, executor/OS scheduling under RP encode). F2.x chooses the cheapest honest path among (a) capture-priority deferral, (b) vision process isolation, or (c) institutionalizing offline authored as the reliability path — without pretending P0 “live path no longer self-starving” is met.**

---

## 2. Validation evidence (F2 closed as offload; open as fps)

| Observation | Meaning |
|-------------|---------|
| **0 mentions** of the two F2 sites in **184** starvation dumps | Offload **worked** — those labels are gone |
| **184** starvation events; worst excess **~7.34 s** | Loop still blocked/delayed; **worse** than prior 18-event / ~4.7 s class under attribution |
| All instrumented loop-thread sites **≤ 0.035 s** in dump windows | Residual is **not** a remaining wrappable timed_block site |
| fps med **~13.5** (min ~12.9, max ~25.8 class from prior) | Capture still governor-floored |
| Lean mode ON | Fleet instrumented agents already ruled out |
| Dense-candidate / classify-burst / HID already off-loop | Still share **one CPython process** (GIL) with WGC callbacks |

**P0 exit criterion “live path no longer self-starving”:** **NOT met.**

**Authorship reliability today:** rests on **golden offline authored pack** (P0 #2, checklist frozen, exit 0) — card-free, re-runnable. Live authored is a **density/UX** goal, not the only legitimacy proof.

---

## 3. Failure-class model (candidates, not convictions)

| Class | Hypothesis | Why it fits empty dumps + low fps |
|-------|------------|----------------------------------|
| **GIL/CPU** | WGC frame path + dense-candidate scorer + classify-burst + 1 kHz HID reader contend for one interpreter | Worker time never enters `timed_block` on the loop tid; loop still starves waiting for GIL / run loop slots |
| **Executor saturation** | `to_thread` / default executor queue backs up; sleep wakeups delay | Loop “starves” without a single long sync label |
| **OS / RP encode** | Host GPU/CPU under Remote Play encode + capture | Explains variability (M14 ~38 fps vs ~13 fps same stack, different ambient) |
| **Remaining loop micro-work** | Many sub-5ms loop turns aggregate | Unlikely alone to produce multi-second excess if dumps show ≤35ms sites |

F2.x does **not** start another wrap-all-the-things pass. That class is exhausted for known lean residual SQLite.

---

## 4. Three options — cheapest kill-check first

### (a) F1 capture-priority deferral — **cheapest code experiment**

| | |
|--|--|
| **What** | While RGC/capture active, defer residual non-essential asyncio tasks (any still-scheduled background, HTTP-heavy, optional pollers); resume on stop. Already sketched in lag-fix §4.2. |
| **Kill-check cost** | One flag + small main/dualshock arm/disarm; one lean capture |
| **What it can prove** | If residual asyncio work still competes, fps/starvation **moves**. If **no** move under lean+priority, residual is **not** “more fleet deferral” |
| **Risk** | Low if defer≠drop (same rail as lag-fix) |
| **Verdict** | **Run first** if any non-lean or residual asyncio tasks remain on the capture host process. Under pure lean, expected **null or small** effect — still a cheap negative that closes F1 as the answer |

### (b) Process isolation for the vision stack — **high leverage, high cost**

| | |
|--|--|
| **What** | Run WGC + dense-candidate + classify (vision) in a **child process** (own GIL); bridge process keeps HID/PoAC/store via IPC (queues/shared memory). |
| **Kill-check cost** | Large design + IPC + failure modes; multi-sprint |
| **What it can prove** | If GIL/CPU from vision workers is the wall, fps and loop health **should** improve in the bridge process |
| **Risk** | High: latency, crash isolation, dual-process lifecycle, testing surface |
| **Verdict** | **Only if** (a) fails **and** operator still prioritizes live ≥30 fps for the wedge. Not the first build |

### (c) Accept + institutionalize offline — **already mostly done**

| | |
|--|--|
| **What** | Declare **offline deferred authored** (golden pack, pad=4000, verify) the **reliability path** for RP authorship claims; live authored = best-effort / density demo when fps allows |
| **Kill-check cost** | **Zero code** — docs + operator habit (golden exit 0 before external claims). Already: `docs/golden-offline-authored-pack.md` acceptance checklist |
| **What it can prove** | Legitimacy does **not** require live fps bar for card-free proof |
| **Risk** | Live demo narrative must stay honest (“mechanism works; capture health is best-effort on this host”) |
| **Verdict** | **Default posture now** for P0 reliability. Not a cop-out: offline is the same evidence, later |

---

## 5. Recommended decision sequence

```text
1. ADOPT (c) as current reliability truth for external/pilot claims
   - Golden pack exit 0 is mandatory before demo (checklist §G)
   - Do not claim “live path no longer self-starving”

2. OPTIONAL cheap kill-check (a) — one PR if any residual asyncio work exists under lean
   - CAPTURE_PRIORITY_MODE default OFF
   - One capture: starvation count + ema_fps vs F2 baseline
   - If null result → document F1 insufficient; do not build more deferral theater

3. DEFER (b) unless operator prioritizes live ≥30 fps as a product requirement
   - If GO: separate design (IPC contract, process model, crash rails) — not F2.x phase-1 code

4. Do NOT open another D1.x wrap pass without a new named loop-tid offender ≤ multi-second
```

### Recommended default for operator (D-F2X-1)

| Priority | Choice |
|----------|--------|
| **Reliability / legitimacy story** | **(c) offline institutionalized** — already green |
| **Next experiment (optional)** | **(a) F1** only as a one-shot kill-check |
| **Structural live fps** | **(b) process isolation** — parked until product GO |

---

## 6. Updated P0 exit criteria (honest)

| Criterion | Status |
|-----------|--------|
| Offline authored card-free proof (golden pack) | **Met** when exit 0 + checklist A–G |
| Live path no longer self-starving (ema_fps ≥ ~30, excess ≤ 1.0s) | **Not met** — open product goal, not current claim |
| F2 removed named SQLite offenders from loop dumps | **Met** |
| Dense-candidate promotion mechanism | **Met** (progress/stall under flag) |

Wedge reliability narrative (external):

> RP authorship is proven **offline** on sealed archives (deferred + pad + verify). Live capture health on this host remains **best-effort**; lag work removed known SQLite blockers and is pursuing residual contention only if live fps is prioritized.

---

## 7. If operator chooses (a) — minimal F1 build bar

| Item | Spec |
|------|------|
| Flag | `CAPTURE_PRIORITY_MODE` default **OFF** |
| Arm | RGC/capture active |
| Disarm | stop |
| Effect | Defer residual **asyncio** background only (not kill dense/HID workers mid-flight) |
| Success kill-check | Starvation rate or ema_fps **materially** better than F2 baseline, or honest null |
| Fail | No change → close F1; do not expand defer list without new evidence |

## 8. If operator chooses (b) — design gate only (no build in this PR)

Separate design must specify: process split boundary, IPC for panel crops / HID onsets / session_id, failure modes, flag default-OFF, test plan. **Out of scope for F2.x phase-1 implementation.**

## 9. CODE-TRUTH

| Item | Path |
|------|------|
| Attribution / empty dump behavior | `loop_timing.py`, `loop_health_monitor.py` |
| Lean residual path | `main.py` PRESENCE_LEAN_MODE |
| F2 offloads | `dualshock_integration.py` `store_frame_checkpoint`, `get_detection_policy` |
| Off-loop vision workers | dense-candidate worker, classify-burst thread, WGC callback |
| F1 sketch | `docs/bridge-capture-lag-fix-2026-07-10.md` §4.2 |
| Offline reliability | `docs/golden-offline-authored-pack.md` acceptance checklist |
| Dense mechanism | `docs/live-authorship-dense-candidate-fix-2026-07-10.md` |

---

## 10. Test plan (only if (a) is built)

| ID | Assert |
|----|--------|
| T1 | Flag OFF: no behavioral change |
| T2 | Flag ON: arm/disarm without dropping store writes |
| T3 | Never-gates: no PoAC/consent change |
| T4 | Doc/ledger: null result is a valid kill-check outcome |

No new tests required to **adopt (c)** beyond existing golden pack.

---

## 11. Operator-decisions table

| ID | Decision | Default recommendation | Operator |
|----|----------|------------------------|----------|
| **D-F2X-1** | Reliability posture = **(c) offline primary** for external claims | **Yes** | ☑ **ACCEPTED 2026-07-10** |
| **D-F2X-2** | Run optional **(a) F1** kill-check PR | **Optional / low priority** | ☑ **SKIPPED 2026-07-10** (audit note N3: a real defer-list exists under lean — uvicorn/MQTT/revocation-listener/calibration-agent/per-record create_tasks — so the option stays honest and re-openable, just not taken now) |
| **D-F2X-3** | Park **(b) process isolation** until explicit live-fps product GO | **Yes** | ☑ **ACCEPTED 2026-07-10** |
| **D-F2X-4** | No further D1.x wrap pass without multi-second named loop-tid offender | **Yes** | ☑ **ACCEPTED 2026-07-10** |
| **D-F2X-5** | Update P0 narrative: live self-starving criterion **open**; offline pack **closed** | **Yes** | ☑ **ACCEPTED 2026-07-10** |
| **D-F2X-6** | Proceed Claude audit of this decision doc only (no build unless D-F2X-2 GO) | Hold | ☑ **DONE 2026-07-10** — audit PASS (claim ⊆ reality; notes N1 ledger-pairing fix, N2 M14-fps color non-load-bearing, N3 F1 defer-list real) |

**F2.x DECISION ARC: CLOSED 2026-07-10** per §12 — D-F2X-1 + D-F2X-5 accepted; F1 skipped with recorded rationale;
(b) not started; external/pilot language holds the honest narrative (§6). No code shipped or required.

---

## 12. Success criterion for F2.x (decision arc)

F2.x is **done** when:

1. Operator accepts D-F2X-1 (offline primary) and D-F2X-5 (honest P0 status).  
2. External/pilot language never claims live path is healthy until a future measured bar.  
3. Optional (a) either skipped or run once with recorded null/positive result.  
4. (b) not started without separate product GO.

**No code is required** to close F2.x as a decision. Code is only required if D-F2X-2 GO.

---

*End F2.x residual capture contention design v0 — 2026-07-10.*
