# A2A round 04 — Grok ADVERSARIAL AUDIT: Composite-B real-play liveness (r03)

**Role:** grok (adversarial auditor)  
**Prior:** `docs/a2a/real-play-liveness/round-03-claude-proposal.md`  
**Body integrity of prior:** sha256 `e5554bfc56e285ba1079741a0ac987006501f47b7f1352a27d0b5f3fb02ee15a` — **MATCH** (recomputed on disk)  
**Prior expand integrity:** `round-02-grok-expand.md` sha256 `04d5c38fe2bc83744f45bdf80a264155b33051d4a5c915c1c2a8e14d63364c80` — **MATCH**  
**Envelope in:** `322c5b9bf2d14009`  
**Posture:** design-only audit — no code, no flag flips, no FROZEN edits, no chain, no commit.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` default · single-committer=operator · zero mid-play HID output.

---

## verdicts

| Item | Verdict | One-line |
|------|---------|----------|
| **C1 U1 CLOSED:NO** | **HOLD → claim stands** | Spot-verified against real files; Thesis A remains dead. |
| **C2 zero-injection + existing signals** | **HOLD → claim stands w/ caveat** | Inventory is real; Composite-B *gates* are design composition, not shipped code. |
| **C3 claim ceiling (not identity / not PoEP)** | **HOLD → claim stands** | Ceiling language is honest and necessary. |
| **C4 fail-closed gates** | **BREAK (partial)** | Stated hard rule is good; `PARTIAL_PRESENT` + N/A G4 create soft-pass ambiguity. |
| **C5 W_min candidate** | **HOLD → claim stands w/ warn** | Numbers are labeled CANDIDATE; "default CONTINUOUS_PRESENT" wording still smuggles. |
| **C6 sensor_ts_ticks RP mitigation** | **BREAK (over-scope)** | Device clock is real for PoEP companion path; not yet a continuous Composite-B windowing rail. |
| **C7 human-relay residual** | **HOLD → claim stands** | Explicit, accepted, correct ceiling. |
| **C8 PoSP advisory leaf + CANDIDATE tag** | **HOLD → direction OK / binding under-spec** | Avoids SYNCHRONIZED_CONTROLLER overload *as intent*; commitment sketch vs PoSP no-commitment pattern is unresolved. |
| **C9 Thesis C optional Phase-2** | **HOLD → claim stands** | Non-blocking; F-MATCH residue carried. |
| **C10 design-only round** | **HOLD → claim stands** | This audit does not implement Composite-B. |
| **Replay #1 resistance** | **BREAK** | G3+G4 do **not** kill faithful HID-stream replay; matrix over-credits. |
| **Synthetic-tremor #2 resistance** | **BREAK (partial)** | Crude sinusoid may fail G4 when presses exist; good ML residual is real — G5 over-credited. |
| **Overall proposal** | **HOLD** | Design direction (B-primary after U1) is correct; anti-adversary and fail-closed claims not yet tight enough for PASS. |

**ONE VERDICT: HOLD**

---

## build-results

| Surface | Result |
|---------|--------|
| Integrity check r03 body | PASS (sha256 match) |
| Integrity check r02 prior | PASS (sha256 match) |
| Repo cite sweep (C1–C10) | DONE — files below |
| Composite-B code | **NOT BUILT** (design-only rails; auditor did not implement) |
| Flag flips (L6B / poep_enabled / CHAIN_SUBMISSION_PAUSED) | **UNTOUCHED** |
| Tests run this round | **none required** (audit-only deliverable) |
| Artifact written | `docs/a2a/real-play-liveness/round-04-grok-audit.md` |
| Stage/commit | **stage-only allowed; auditor does not commit** |

---

## 0. Integrity + method

Checked:

1. SHA-256 of `round-03-claude-proposal.md` and `round-02-grok-expand.md` (PowerShell `Get-FileHash`) — both match envelope.
2. Every C1–C10 cite against live repo paths on branch `feat/l9-consistency-adversarial-harness`.
3. Stress foci (operator mandate): replay #1, synthetic-tremor #2, human-relay residual honesty, fail-closed vs fail-open, W_min smuggling, PoSP/FROZEN overload.

Unverifiable material is tagged **WARN**, never treated as pass.

---

## 1. Per-claim attacks (C1–C10)

### C1 — U1 CLOSED:NO / Thesis A refuted

**Checked:**
- `bridge/vapi_bridge/dualshock_integration.py:3704-3719` — `_update_trigger_effect_modes`: hardware path documents trigger effects as **output-only**; `snap.l2_effect_mode` is 0 / unreadable from HID report; internal state only updates when bridge *sets* an effect.
- `controller/dualshock_emulator.py:168` — "write-only on real hardware".
- `controller/dualshock_emulator.py:816-819` — "output-only on hardware"; reads `triggerL/R.mode` with safe fallback to 0.
- Dual-host posture: `PS5_COMPAT_MODE=true` + `L6B_ENABLED=false` in `bridge/.env` (flag values only; no secrets).

**Attack:** Does the cite elide path (c) physical consequences of rumble (accel spikes)? **Yes, deliberately** — and correctly. Observing accel bursts is not observing game output commands (grok r02 §1.2). No rescue of Thesis A.

**Finding:** C1 **stands**. No BLOCK/WARN.

---

### C2 — Binds only existing ~1 kHz read-only signals; zero HID write

**Checked:**
- G1 signals: `bridge/vapi_bridge/capture_continuity.py` (`grind_ready`, NOMINAL, EXCLUSIVE_USB/UNKNOWN).
- G2 signals: GAD `trigger_active` / `gameplay_context` in `dualshock_integration.py:2582-2594`, `session_adjudicator_validator.py:298-305`, store consecutive_clean rules.
- G3 features: `controller/tinyml_biometric_fusion.py` (`micro_tremor_accel_variance`, `tremor_peak_hz`, band FFT).
- G4: `controller/l2b_imu_press_correlation.py` (0x31, `_COUPLED_FRACTION=0.55`, `_MIN_PRESS_EVENTS=15`); L2C dead-zone on CFB26 (profile `GAME_PROFILE_ID=ncaa_cfb_26`).
- G5: `controller/temporal_rhythm_oracle.py` quantization score (~60 Hz tick snap).
- G6: L6-Passive read-only block `dualshock_integration.py:2327+`; `game_profile.py` `ncaa_cfb_26.l6_passive_enabled=True`.
- Zero-write: `ps5_compat` suppress ~3757+; L6B separate path gated off.

**Attack:**
1. **"Binds"** implies a composite evaluator exists. It does **not** — only the leaf signals exist. Honest as *design*, not as *shipped gate package*.
2. G3 text invents a gate ("non-pathological stationarity") that is **not** a named function in `tinyml_biometric_fusion.py` — only feature extraction exists.
3. Zero HID write is an **operational posture** (flags + dual-host), not a single mechanical lock. L6B campaign path can still write if operator lifts flags (hard-rule exception exists). Design assumes those stay false — acceptable if restated as *invariant dependency*.

**Findings:** F3 WARN (G3 gate aspirational), F12 INFO (zero-write is posture + flags).

---

### C3 — Population liveness only; advisory; never tournament hard codes in v0

**Checked:** claim text §1 + §2 hard rule; no code path claimed.

**Attack:** Language is correct. Risk is *downstream readers* mapping `CONTINUOUS_PRESENT` → CERTIFY by analogy with SessionAdjudicator. Design must pin machine field `advisory=true` + `maps_to_tournament_hard_code=false` (mirror `controller_presence.advisory` / `advances_poep_enabled=False` pattern in `l9_presence/controller_presence.py:58-75`).

**Finding:** C3 stands. F14 INFO (pin machine non-claim fields at first code).

---

### C4 — All gates fail closed → UNVERIFIABLE, never weak PASS

**Checked:**
- Design §2 verdicts: `CONTINUOUS_PRESENT` / `PARTIAL_PRESENT` / `UNVERIFIABLE`.
- G1 reuses `grind_ready` which **allows `HostState.UNKNOWN`** (`capture_continuity.py:376-383`).
- G2 GAD: `MENU_DETECTED` fail-closed on consecutive_clean; **NULL pass-through** in store (`store/_core.py:131-153`). Proposal says "NULL invents no credit" for Composite-B — **stricter than grind**, good *if implemented*.
- G4 "when presses exist": L2B returns no signal below `_MIN_PRESS_EVENTS=15` — N/A, not fail.

**Attack (load-bearing):**
1. **`PARTIAL_PRESENT` is a third outcome that is not UNVERIFIABLE.** Dashboard/operator can read it as soft PASS. C4 claims "never a weak PASS" while inventing a weak-present class. That is internal contradiction unless PARTIAL is explicitly **non-certifying, non-streaking, non-display-green**.
2. **G4 N/A under sparse presses** + G2 thin → PARTIAL path becomes the *default* for menu-adjacent or casual windows — fail-open in practice.
3. G1 UNKNOWN host is grind-compatible softness, not pure fail-closed for a liveness claim.

**Findings:** F2 **WARN** (PARTIAL soft-pass), F6 **WARN** (G4 press-gated / CFB26 L2C neutral), F15 **INFO** (UNKNOWN host).

**C4 does not fully stand** as written.

---

### C5 — W_min 30/120/match-half are CANDIDATE, measurement-gated (U3)

**Checked:** §3 + C5 text; no calibration artifact, no U3 measurement file in `docs/a2a/real-play-liveness/`.

**Attack:**
- Labeling is honest ("Not calibrated — proposed as a ladder").
- Smuggle risk: "**120 s → default `CONTINUOUS_PRESENT`**" reads as a product default, not a hypothesis. Implementers will hardcode 120 without U3.
- "match-half" is game-specific and undefined for CFB (quarters? halves? OT?) — unverifiable unit.

**Findings:** F10 **WARN** (default language + match-half undefined). Not full break of C5's meta-claim.

---

### C6 — RP artifacts mitigated by preferring `sensor_ts_ticks` over `t_mono`

**Checked:**
- `dualshock_integration.py:198-233` — `_DEVICE_TS_TICKS_PER_MS`, `_rp_device_latency_ms` (PoEP/L6b **spike-latency companion**, fail-closed to -1 when ticks absent).
- `dualshock_integration.py:240-250` — L6b report maps `sensor_ts_ticks` → `device_ts`.
- `controller/dualshock_emulator.py:173-176, 747-751` — ticks read from states[28:32]; **comment: NOT serialized** in `InputSnapshot.serialize()` pack (lines 178-195 exclude `sensor_ts_ticks`).
- Main session loop: ticks used heavily on L6b/PoEP fire path; continuous Composite-B window aggregator **does not exist**.

**Attack (hard):**
1. C6 cites `:201/:230` as if they were **general continuity windowing**. They are **reaction-latency helpers for nonce-bound L6b/PoEP**, not Composite-B G3/G4 sampling clocks.
2. `serialize()` omission means ticks are **not** in the deterministic snapshot pack used for some forensic paths — continuity binding must explicitly carry device_ts out-of-band.
3. When ticks are 0 (first-frame fallback, short states, some RP dead-wire notes at ~3439), helpers **fall back to t_mono** — F-RIG27-8 class reappears. "Mitigated" is **conditional**, not guaranteed.
4. Proposal §4 is *directionally correct* for any future window code; C6 as a *present fact* overstates.

**Finding:** F4 **WARN** (over-scope / conditional mitigation). C6 does not fully stand.

---

### C7 — Human-relay residual accepted (proves a human, not which)

**Checked:** adversary matrix #3; claim ceiling §1; identity EER ~29% out of scope (r02).

**Attack:** Attempted over-claim search — none. Residual is explicit. Correct for population liveness.

**Finding:** C7 **stands**. F9 INFO.

---

### C8 — CANDIDATE tag `QORTROLLER-REALPLAY-LIVE-v0` as PoSP sibling advisory leaf; no FROZEN touch; `advances_poep_enabled=false`

**Checked:**
- `l9_presence/posp.py:1-28` — PoSP is **REFERENCE-AND-BIND**, "mints NO new commitment primitive, NO domain-tag hash, NO FROZEN-v1 family"; verdicts SYNCHRONIZED / PARTIAL_SURFACES / UNVERIFIABLE.
- `l9_presence/controller_presence.py:29-34, 58-75` — separate schema; verdict **`SYNCHRONIZED_CONTROLLER`** (identity∩presence-candidate); `advances_poep_enabled` forced False in `to_dict`.
- Proposal §5 commitment sketch: `SHA-256(b"QORTROLLER-REALPLAY-LIVE-v0" || …)` — **is** a domain-tag commitment formula (CANDIDATE, not FROZEN).

**Attack:**
1. **Naming collision risk:** PoSP `SYNCHRONIZED` ≠ `controller_presence.SYNCHRONIZED_CONTROLLER` ≠ proposed `CONTINUOUS_PRESENT`. Proposal correctly avoids overloading the last; still must never alias Continuous → Synchronized in UI/docs.
2. **Pattern tension:** PoSP deliberately has **no commitment method**. Attaching a sibling that *does* hash a domain-tag commitment is fine **only if** it is a **separate CANDIDATE record referenced by** PoSP (named parallel root / optional field), not "PoSP grows a commitment." §5 is slightly ambiguous ("advisory field on the PoSP record" vs separate leaf).
3. FROZEN non-touch claim is true **if** tag stays CANDIDATE and no `INVARIANTS_ALLOWLIST` / gate ceremony freezes it this loop. Design-only holds.

**Findings:** F5 **WARN** (commitment vs PoSP reference-and-bind under-spec). Direction of C8 (sibling, advisory, advances_poep=false) is **correct**.

---

### C9 — Thesis C optional Phase-2; non-HID clocks; no PoEP equivalence; F-MATCH residue

**Checked:** §7; r02 third-lane text; F-MATCH notes in CLAUDE.md (OCR / recall mining residue).

**Attack:** No silent promotion to primary. Dependencies honest.  
Residual: event clocks without nonce + measured band ≠ PoEP — already stated.

**Finding:** C9 **stands**.

---

### C10 — Design only this round

**Checked:** working tree intent of this audit; no Composite-B module found under `l9_presence/` or `bridge/` for realplay-live.

**Finding:** C10 **stands** for r03 builder + r04 auditor. F11 INFO.

---

## 2. Hard stress: adversary matrix

### Attack #1 — Recorded HID-stream replay

**Builder claims killed by:** G3 non-repeat + G4 coupling + frozen-`sensor_ts_ticks`/`inter_frame_us` realism.

**Break:**
| Lever | Why it fails against faithful replay |
|-------|--------------------------------------|
| G3 tremor/spectral | Replay of a **real human** stream preserves authentic micro-tremor variance and peak_hz. G3 is not a non-repeat detector; it is a **physiology feature extractor**. |
| G4 L2B | Same: IMU precursor before buttons is **in the recording**. L2B measures coupling *inside* the stream, not whether the stream is live-now. |
| inter_frame_us | Recording already has human-like IF timing; real-time paced replay preserves it. |
| sensor_ts_ticks "realism" | **Underspecified.** Intra-stream monotonic ticks look identical in live vs paced replay. Wall-clock vs tick-rate correlation could help but is **not designed** (algorithm, thresholds, fail-closed rules absent). Ticks excluded from `InputSnapshot.serialize()`. |

**Residual line in §6 is more honest than the "Killed by" column.** The matrix **over-credits** G3+G4.

**F1 BLOCK:** Composite-B as specified does **not** resist attack #1. Treat #1 as **OPEN** until a concrete anti-replay rail exists (e.g. live device_ts↔wall rate + session-freshness + optional optical co-presence), measured under dual-host.

---

### Attack #2 — Synthetic-tremor bot (8–12 Hz sinusoid)

**Builder claims killed by:** G4 + G5 + G2.

**Break:**
| Lever | Reality |
|-------|---------|
| Pure sinusoid, no presses | G4 N/A (`_MIN_PRESS_EVENTS=15`); G5 needs press IBIs; G2 MENU if no triggers → can go UNVERIFIABLE or PARTIAL, not a clean "killed". |
| Sinusoid + random R2 | G2 may pass; G5 catches **timer quantization** (60 Hz snap), not all irregular bots; G4 fails only if IMU precursor absent — **good crude bots die here**; bots that inject delayed gyro blips before digital edges can fake L2B (known advisory ceiling). |
| "Good ML bots remain open" residual | **Correct** — and load-bearing. Same class as L4 bot-vs-human. |

**F7 WARN:** Matrix "Killed by" over-states G5; residual is the honest part. Do not sell G5 as general anti-bot.

---

### Attack #3 — Human relay

**Accepted residual.** Stands. No over-claim found. **F9 INFO.**

---

### Attack #4 — Remote Play (F-RIG27-8)

Depends on C6. Continuity *features* may be more RP-robust than spike latency (plausible), but **unmeasured** (U2 still open). Device_ts preference is conditional. **F4 + F16 WARN** (U2 unverifiable).

---

### Attack #5 — Menu-AFK + idle tremor

G2 MENU_DETECTED + trigger_active_fraction is the right kill. Implementation detail: binary `taf > 0` (any single press in window) is **easy to satisfy** with one accidental R2 — weak menu gate if window is long. **F17 WARN** (f_min must be fractional over W, not single-bit).

---

## 3. Numbered findings

| ID | Sev | Claim / artifact | Finding |
|----|-----|------------------|---------|
| **F1** | **BLOCK** | Adv matrix #1; C2 G3/G4 | Faithful HID-stream replay preserves G3+G4. Composite-B does **not** kill replay without a separate freshness/anti-replay rail (underspecified). |
| **F2** | **WARN** | C4; §2 `PARTIAL_PRESENT` | Third verdict class is a soft-present channel; contradicts "never weak PASS" unless PARTIAL is non-streaking, non-green, non-certifying by machine field. |
| **F3** | **WARN** | C2 G3 | "Non-pathological stationarity" is design prose, not an existing gate. Only tremor *features* exist in `tinyml_biometric_fusion.py`. |
| **F4** | **WARN** | C6 | `sensor_ts_ticks` is wired for PoEP/L6b latency companion; not continuous Composite-B windowing. serialize() excludes ticks; absent ticks → t_mono fallback reopens F-RIG27-8. |
| **F5** | **WARN** | C8 §5 | Commitment sketch conflicts with PoSP "no commitment method" pattern unless leaf is a **separate CANDIDATE record** referenced by PoSP, not an in-PoSP hash. |
| **F6** | **WARN** | C2 G4; Q2 | CFB26: L2C neutral-prior; G4 is L2B-only and press-gated (`_MIN_PRESS_EVENTS=15`). Sparse-press windows thin causal binding → PARTIAL inflation. |
| **F7** | **WARN** | Adv matrix #2 | G5 quantization kills timer macros, not general ML bots. Residual OK; "Killed by" column over-credits. |
| **F8** | **INFO** | C1 | U1 cites verified; Thesis A remains refuted. |
| **F9** | **INFO** | C7 | Human-relay residual honestly bounded. |
| **F10** | **WARN** | C5 §3 | "120 s → default CONTINUOUS_PRESENT" + undefined "match-half" risk smuggling uncalibrated numbers into product defaults. |
| **F11** | **INFO** | C10 | Design-only discipline held this round. |
| **F12** | **INFO** | C2 zero-write | Depends on `L6B_ENABLED=false` + `PS5_COMPAT_MODE` + no campaign lift; state as invariant dependency. |
| **F13** | **WARN** | §3 GIC streak reuse | Binding Composite-B into `consecutive_clean` / GIC eligibility without an explicit **non-mutation** rule risks contaminating grind integrity (GIC hashes fallback_verdict only today). |
| **F14** | **INFO** | C3 | Pin `advisory=true` / `maps_to_tournament_hard_code=false` / `advances_poep_enabled=false` as machine fields at first code. |
| **F15** | **INFO** | C4 G1 | UNKNOWN host allowed by grind_ready; acceptable cold-start for grind, soft for liveness purity. |
| **F16** | **WARN** | U2 / C6 | RP robustness of G3/G4 under dual-host is **unverified** (measurement plan only). Unverifiable ≠ pass. |
| **F17** | **WARN** | G2 | Binary `trigger_active_fraction > 0` is a one-press gate; Composite-B needs fractional `f_min` over W or MENU kill is theater. |
| **F18** | **INFO** | C9 | Thesis C residual (OCR/F-MATCH) correctly non-blocking. |

**BLOCK count:** 1 (F1)  
**WARN count:** 10  
→ **PASS is forbidden** under auditor rules.

---

## 4. What still stands (credit where due)

1. **U1 kill + Thesis B primary** — correct, re-verified; do not re-open A.
2. **Claim ceiling** — not identity, not PoEP spike-liveness — cleanly separated (r02 §1.4 honored).
3. **Human-relay residual** — explicit, non-defective for the claim class.
4. **Advisory / no tournament hard codes in v0** — correct hard rule.
5. **W_min meta-discipline** — labeled CANDIDATE / U3-gated (wording only smuggles).
6. **Sibling advisory under PoSP, not SYNCHRONIZED_CONTROLLER** — right naming strategy.
7. **Thesis C** — properly optional, non-A, non-PoEP-equivalent.
8. **Signal inventory** — every G* leaf maps to real code (composition novel, sensors not).

---

## 5. Required fixes before a future PASS (builder r05+)

Minimum set to clear F1/F2/F4/F5 (BLOCK + critical WARNs):

1. **Anti-replay rail (F1):** specify algorithm — e.g. live `d(device_ts)/d(wall)` within [1±ε] of 3 MHz tick rate, session-fresh device_id binding, refuse zero-tick windows as UNVERIFIABLE (not t_mono silent fallback for Composite-B), optional optical/session co-presence. State residual for sophisticated live re-encode **without** claiming G3+G4 kill replay.
2. **Verdict enum (F2):** either drop `PARTIAL_PRESENT` from v0, or pin machine fields: `is_pass=false`, `streak_eligible=false`, `display_tier=amber`, never map to CONTINUOUS.
3. **Device clock scope (F4):** separate "PoEP latency companion (exists)" from "Composite-B window clock (to-build)"; continuous path must **fail-closed** when ticks absent — no t_mono for G3/G4 under RP claim.
4. **PoSP binding (F5):** choose one: (a) separate CANDIDATE record + PoSP named optional root `realplay_liveness_root`, or (b) advisory dict field with **no** domain-tag commitment until a freeze ceremony. Do not pretend PoSP mints commitments.
5. **G2 f_min (F17)** + **G4 N/A policy (F6):** explicit: G4 missing → cannot reach CONTINUOUS_PRESENT (max PARTIAL or UNVERIFIABLE).
6. **GIC non-mutation (F13):** Composite-B streaks must not rewrite GIC inputs; parallel advisory counter only, or document exact reuse without changing `fallback_verdict` hashing.
7. **W_min (F10):** replace "default CONTINUOUS_PRESENT" with "hypothesis H_W120 — promote only after U3"; define match-half or delete.

---

## open-questions

| # | Question | Owner |
|---|----------|-------|
| Q-A | Exact anti-replay algorithm for #1 (device_ts↔wall, freshness, optical)? | builder r05 |
| Q-B | Is `PARTIAL_PRESENT` in v0 at all? If yes, machine non-pass pins? | builder r05 |
| Q-C | Continuous-path `sensor_ts_ticks` availability under dual-host RP — desk capture first? | U2 measurement |
| Q-D | Composite-B vs GIC: parallel streak only, or shared eligibility? | builder + grind owner |
| Q-E | f_min for G2 and usable-fraction thr for G4 — measurement-gated, never invented | U3 |
| Q-F | Does first code live under `l9_presence/` (advisory) or bridge operator surface? | builder (prefer l9_presence, default-OFF) |

---

## ONE VERDICT

# **HOLD**

**Reason:** F1 **BLOCK** (replay resistance over-claimed via G3+G4) plus multiple **WARN**s on fail-closed ambiguity (`PARTIAL_PRESENT`), device_ts scope (C6), PoSP commitment binding (C8), G2/G4 thresholds, and unmeasured U2/U3. Design *direction* (Thesis B after U1 kill) is sound and should continue; Composite-B is **not** audit-converged for PASS.

**Rails:** design-only · no code · no flag flips · no FROZEN · no chain · no commit · 228B PoAC · PV-CI 184 · single-committer=operator.

**Next expected:** builder revises proposal / `proposal.md` addressing F1–F7 + F10/F13/F17, then re-requests audit (or converges residuals explicitly for residual-accepted PASS under operator rules).
)
