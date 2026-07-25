# QorTroller next forks A–D — decision brief (2026-07-25)

**Status:** analysis only · exclusive decision set A/B/C/D · **one recommendation**  
**HEAD context:** after RWM ladder L0→NOV-1.1 dogfood and `live_10` gate note  
`docs/a2a/retina-witness-mark-ladder/l0-live-session-live10-2026-07-25.md`.

This brief ranks four mutually exclusive *next* forks. Choosing **D** means not
executing A–C. Choosing A, B, or C means not pausing for grant/packaging alone.

**Claim separation (load-bearing):** `live_10` is a **RWM diversity win** (N=367,
unique=100%, locator PASS). It is **not** an L9 continuum win (~6.5% LIVE_COUPLED,
~92% REPLAY_OR_RELAY). Do not conflate those claims.

---

## Ranking table

| Fork | Work | Readiness | Main evidence | Risk if chosen next |
|------|------|-----------|---------------|---------------------|
| **A** | L9 continuum engineering (center ROI, device ts, lag measure) | **Partial** — RGC path exists; measured continuum weak | live_10: 6/92 LIVE_COUPLED, 85/92 REPLAY_OR_RELAY, coupling mean ~0.07, `wall_fallback` only; left-panel ROI `0.0,0.28,0.32,0.67` is RWM-strong / continuum-weak (`l0-live-session-live10-2026-07-25.md`) | Scope creep into full PoEP or tournament gates; overclaim LIVE after one ROI tweak without lag proof |
| **B** | PoEP / single-HID SYNCHRONIZED under real play | **Partial / blocked** — adapters + HID ring built; **L6B already ON** | CLAUDE hard rules (2026-07-24 reconcile): `L6B_ENABLED=true` operator seal 2026-07-18 after usable N met (220 usable / 197 independent on Edge); **`poep_enabled` stays False** independently; SYNCHRONIZED under real play still topology-blocked (single-HID bridge fire path / dual-connect seam); campaign mode is process-scoped only | Claiming SYNCHRONIZED_CONTROLLER without `real_hardware` + topology; conflating L6B-ON with poep_enabled; dual-connect HID regressions |
| **C** | Tournament preflight / TGE sequencing on AIT + gates | **Partial** — AIT defensibility path advanced; multi-gate preflight exists | CLAUDE/Agents: AIT all_pairs>1 + per-player N≥10 defensibility; staged graduation; many P0 conditions; still testnet + `CHAIN_SUBMISSION_PAUSED` posture | Premature TGE narrative while L9 continuum and AUTHORED seams still open; spend/activation mistakes |
| **D** | Pause product-ops; grant / docs / packaging | **Ready anytime** — no code dependency | Product + DePIN node + RWM ladder already dogfoodable; public-repo hygiene in place | Stalling measured continuum/TGE gaps; docs drift if ops continue offline without brief |

---

## Per-fork detail

### A — L9 continuum engineering

- **Readiness:** Partial. RetinaGameCapture + RGC diag already emit L9/NQPV verdicts and lag; live_10 proves the *measurement surface* works and the *result* is mostly REPLAY.
- **Evidence:** live_10 gate note RGC table; empty latency calib jsonl for that harvest; wall_fallback ts source.
- **Risk:** Treating “ROI change landed” as continuum closed without in-play stick periods + lag budget.

### B — PoEP / single-HID SYNCHRONIZED under real play

- **Readiness:** Partial/blocked. Bridge fire+IMU ring and adapters exist as mechanism. **Split flags:** `L6B_ENABLED=true` already sealed (2026-07-18; corpus gate met); **`poep_enabled=False`** still independent — presence protocol not auto-on. SYNCHRONIZED under real play remains topology-blocked, not “waiting for L6B seal.”
- **Evidence:** CLAUDE hard rule (L6B ON after usable 220/197; poep_enabled stays False); `bridge/.env` `L6B_ENABLED=true`; HID-ring / dual-connect notes; presence fusion CANDIDATE compose-not-conflate.
- **Risk:** Claiming SYNCHRONIZED_CONTROLLER without real pad fire topology; treating L6B-ON as if PoEP live protocol were on.

### C — Tournament preflight / TGE sequencing

- **Readiness:** Partial. AIT separation + preflight APIs/gates exist; not a single “green = mainnet launch” button.
- **Evidence:** AIT all_pairs / defensibility / staged graduation in CLAUDE phase history; chain pause default.
- **Risk:** Marketing ahead of continuum + AUTHORED + multi-P0 honesty.

### D — Pause product-ops; grant / docs / packaging

- **Readiness:** Ready. Forensic RWM + DePIN node + CLI product are enough for external packaging if continuum is explicitly *not* overclaimed.
- **Evidence:** RWM ladder README (L0–NOV-1 built+dogfood); live_10 RWM win; public repo + assessments.
- **Risk:** Freezing engineering while the one measured “almost product claim” gap (continuum) stays REPLAY-dominant.

---

## Recommendation (exactly one)

### **Recommended next fork: A — L9 continuum engineering**

**Why A over B/C/D**

1. **Measured gap after a forensic win.** live_10 closed diverse RWM; continuum is the adjacent claim customers will confuse with “live proof,” and the data already shows REPLAY dominance.
2. **Unblocks honest product language.** Separating RWM vs L9 in docs is done; engineering A makes a *future* continuum cite possible without touching PoEP flags or TGE.
3. **B is higher risk / topology-bound.** L6B is already sealed ON; remaining work is `poep_enabled` / campaign / single-HID SYNCHRONIZED under real play — not another L6B enablement decision.
4. **C depends on multi-gate honesty.** TGE sequencing is premature as *the* next build while continuum is unexplained and chain pause is correct default.
5. **D is valid but freezes the wrong moment.** Packaging can run *in parallel later*; the ranking pick for *next engineering* is A.

### Bounded next build slice (A only) — definition of done

**Slice name:** `L9-continuum-instrument-v0` (CANDIDATE; no FROZEN ceremony)

**In scope (when executed as a later build — not this brief’s commit):**

1. **Dual optical path config:** keep left-panel ROI for RWM dense crops; add optional **center-field ROI** (env/config) feeding *coupling only* — RWM crop path unchanged by default.
2. **Lag honesty:** report and persist whether lag uses device clock vs `wall_fallback`; never silently upgrade REPLAY→LIVE without source tag.
3. **Offline lag/ROI report:** script or RGC export over an existing session log/archive that tabulates LIVE vs REPLAY rates + lag histogram + ts_source (drive real shipped functions in tests).
4. **Ops gate for analysis:** document “only score continuum on in-play stick motion windows,” not play-call UI (ops criterion in the report, not a new biometric flag).

**Out of slice:** `poep_enabled` flips / SYNCHRONIZED under-play topology work (fork B), tournament commit-activation, mainnet, FROZEN-v1 pins, claiming continuum win on live_10. (L6B is already ON — not an A-slice or B-unblock item.)

**Slice “done” means:** dual-ROI/config + lag source tagging + offline continuum report + tests on real functions; **not** “LIVE_COUPLED majority on a new capture” (that is a later validation session).

---

## Explicit non-claims

- This brief does **not** implement A, B, or C.
- live_10 is **not** L9 continuum success.
- No TGE / mainnet launch readiness asserted.
- `CHAIN_SUBMISSION_PAUSED` remains the correct default ops posture.

---

## Sources checked

| Path | Use |
|------|-----|
| `docs/a2a/retina-witness-mark-ladder/l0-live-session-live10-2026-07-25.md` | RWM win vs RGC continuum numbers |
| `docs/a2a/retina-witness-mark-ladder/README.md` | Ladder L0–NOV-1 status; live_10 preferred for RWM diversity |
| `CLAUDE.md` | AIT; L6B sealed ON (2026-07-18) vs `poep_enabled` False; chain pause; product/DePIN standing |
| `bridge/.env` (local, not committed) | Confirmed `L6B_ENABLED=true` |
| `retina_kf_archive/cfb_rwm_live_10_1784953588` (local) | panel count 367 re-check |

---

*Decision brief 2026-07-25. Recommended fork: **A**. Next engineering goal should open only the bounded `L9-continuum-instrument-v0` slice above.*
