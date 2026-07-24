# A2A round 06 — Grok RE-VERIFY: Composite-B v2.1 (post-F1-BLOCK fix)

**Role:** grok (adversarial auditor / re-verifier)  
**Prior:** `docs/a2a/real-play-liveness/round-05-claude-fix.md`  
**Body integrity of prior:** sha256 `3b2d24327c16fab6a20f2785eed3b4d2bdef244e8fd5b96613e25123757fb8fe` — **MATCH** (recomputed on disk)  
**Prior audit integrity:** `round-04-grok-audit.md` sha256 `ed1bacc05c905f23e72466af6a3532d4cd95f2447c3f68f0391402e6acfdca52` — **MATCH**  
**Envelope in:** `8aef8eb3d8af7bbd`  
**Posture:** design-only re-verify — no code, no flag flips, no FROZEN edits, no chain, no commit.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` default · single-committer=operator · zero mid-play HID output.

---

## verdicts

| Item | r04 | r05 fix status | One-line |
|------|-----|----------------|----------|
| **F1 anti-replay / live-now** | BLOCK | **CLOSED:STRUCTURE + WARN residual** | Rail is real and correctly demotes G3/G4; "layers 1–2 defeat paced dump-replay" still overstates (see §2). |
| **F2 verdict enum pins** | WARN | **CLOSED** | PARTIAL pinned non-pass (`is_pass=false`, amber, no SYNCHRONIZED alias). |
| **F3 G* gates to-build honesty** | WARN | **CLOSED** | Explicit honesty pin: leaf features exist; gate functions to-build. |
| **F4 device_ts fail-closed** | WARN (C6) | **CLOSED** | PoEP companion vs continuous window separated; no `t_mono` fallback for liveness claim. |
| **F5 PoSP separate-record** | WARN (C8) | **CLOSED** | Separate `realplay_liveness_v0` + named root; PoSP mints no commitment; no freeze this loop. |
| **F6 G4-missing → PARTIAL** | WARN (C4) | **CLOSED** | G4 absent → max PARTIAL; rail-absent → UNVERIFIABLE. |
| **F7 G5 honesty** | WARN | **CLOSED** | Matrix: G5 = timer-quantized macros only; ML residual OPEN. |
| **F10 W_min hypotheses** | WARN (C5) | **CLOSED** | H_W30/H_W120/H_Wlong; "default" + "match-half" removed. |
| **F13 GIC non-mutation + Q1** | WARN | **CLOSED** | Parallel advisory counter only; Q1 no longer feeds consecutive_clean/GIC. |
| **F17 fractional f_min** | WARN | **CLOSED** | G2 fractional ≥ f_min over W; MENU=0; NULL invents no credit. |
| **F16 U2 RP robustness** | WARN | **REMAINS WARN (honest)** | Still unmeasured; correctly labeled hypothesis — not a regression. |
| **C1 U1 CLOSED:NO** | stood | **STANDS** | Spot-reverified; Thesis A dead. |
| **C2 zero-injection** | stood w/ caveat | **STANDS** | Inventory + to-build honesty + flag dependency stated. |
| **C3 claim ceiling** | stood | **STANDS** | Population liveness only; machine advisory fields pinned. |
| **C7 human-relay residual** | stood | **STANDS** | Explicit accepted ceiling. |
| **C9 Thesis C optional** | stood | **STANDS** | Non-blocking Phase-2; F-MATCH residue carried. |
| **C10 design-only** | stood | **STANDS** | This re-verify did not implement Composite-B. |
| **C11 live-now rail (NEW)** | n/a | **HOLD w/ residual** | Direction correct; defeat-claim for naive paced dump is incomplete (F19). |
| **NEW F19 paced-dump residual** | — | **WARN** | Real-time 1× dump re-injection with original device_ts into a fresh session can pass layers 1–2. |
| **NEW F20 PARTIAL "rail thin"** | — | **WARN (minor)** | PARTIAL text says "rail or gate thin" while rail-absent is UNVERIFIABLE — pin thin vs absent. |
| **Overall** | HOLD | **HOLD** | All r04 BLOCK/critical WARNs structurally fixed; residual WARNs remain → PASS forbidden under mandate. |

**ONE VERDICT: HOLD**

Reason: r05 is a **strong, honest revision** that closes the F1 *structure* (anti-replay rail separate from G3/G4) and every mandatory wording fix (F2/F4/F5/F6/F7/F10/F13+Q1/F17). It does **not** yet clear a residual-free PASS because (1) the live-now defeat claim for **naive real-time paced dump re-injection** is still overstated relative to what layers 1–2 mathematically do (F19), and (2) mandate rule: any surviving WARN keeps HOLD. Design is audit-converging; one more residual-tightening pass can unlock residual-accepted PASS if operator allows residual class to be explicit.

---

## build-results

| Surface | Result |
|---------|--------|
| Integrity check r05 body | **PASS** (sha256 match) |
| Integrity check r04 prior | **PASS** (sha256 match) |
| Finding close-out (F1–F17) | **DONE** — see §1 |
| New-break hunt | **DONE** — F19, F20 (minor) |
| Spot-verify `_DEVICE_TS_TICKS_PER_MS` | **PASS** — `dualshock_integration.py:201` = 3000.0 |
| Spot-verify `sensor_ts_ticks` not in serialize | **PASS** — `dualshock_emulator.py:174-176` |
| Spot-verify PoSP no-commitment | **PASS** — `posp.py:1-13, 47-48` REFERENCE-AND-BIND |
| Composite-B code | **NOT BUILT** (design-only rails) |
| Flag flips (L6B / poep_enabled / CHAIN_SUBMISSION_PAUSED) | **UNTOUCHED** |
| Tests this round | **none required** (re-verify design; no BUILD-NOW code items) |
| Artifact | `docs/a2a/real-play-liveness/round-06-grok-reverify.md` (skeleton first, then filled) |
| Stage/commit | auditor does not commit; stage-only allowed for docs |

---

## open-questions

| # | Question | Owner |
|---|----------|-------|
| Q-R1 | Does residual-accepted PASS require only explicit F19 residual language, or a stronger layer-1 absolute clock / challenge / optical-required-for-CONTINUOUS? | builder r07 + operator |
| Q-R2 | Session-freshness: bind *evaluation metadata* only, or bind a session-start **challenge nonce** into the window evidence so HID-only dumps cannot be re-hosted? | builder (F19 close) |
| Q-R3 | PARTIAL "rail thin" — define thr for partial rate-lock drift vs hard fail → UNVERIFIABLE | builder |
| Q-R4 | ε for device_ts↔wall rate lock — measurement-gated (U2) or provisional CANDIDATE constant with fail-closed band? | U2 |
| Q-R5 | First code under `l9_presence/` default-OFF vs bridge operator surface? | builder (prefer `l9_presence`, default-OFF) |
| Q-R6 | F16 U2 desk capture with `sensor_ts_ticks` populated end-to-end under dual-host RP — still open | operator hardware |

---

## 0. Integrity + method

1. SHA-256 of `round-05-claude-fix.md` and `round-04-grok-audit.md` (PowerShell `Get-FileHash`) — both **MATCH** envelope.
2. Wrote this file's skeleton **first** (mandate), then filled after investigation.
3. Spot-verified load-bearing cites against live repo (device_ts constant, serialize exclusion, PoSP module doc, session_id as join key elsewhere in `l9_presence/`).
4. Adversarial focus: does §2.5 actually establish live-now, or hand-wave? Residual honesty? Cross-check every r04 required fix.
5. Unverifiable = WARN. Surviving WARN → HOLD. No code built.

---

## 1. Finding close-out (r04 → r05)

### F1 BLOCK — anti-replay / live-now (primary)

**r04 required:** separate anti-replay rail; stop crediting G3+G4; refuse zero-tick as UNVERIFIABLE; state sophisticated residual without claiming physiology kills replay.

**r05 delivered:**
- §2.5 three-layer rail (device_ts↔wall rate lock + session-freshness + optional optical).
- Explicit load-bearing correction: G3/G4 = human-shaped only, **not** live-now.
- Adversary matrix #1 rewritten: killed by rail, **NOT** G3/G4.
- C11 NEW claim matches that architecture.
- Residual: "sophisticated live-re-encode remains OPEN" — stated.

**Spot-check layer primitives:**
- `_DEVICE_TS_TICKS_PER_MS = 3000.0` at `dualshock_integration.py:201` — **real**.
- `_rp_device_latency_ms` is still **spike-latency** helper — r05 correctly says continuous window clock is **to-build** (F4 closed).
- Fail-closed no `t_mono` for Composite-B liveness — **correct** design rule (today's L6b path *does* fall back; design must not reuse that).

**Attack on §2.5 (does it establish live-now?):**

| Layer | What it actually does | What it does **not** do |
|-------|----------------------|-------------------------|
| **1 Rate lock** `d(device_ts)/d(wall) ∈ [1±ε]·rate` | Kills fast-forward / slow-mo / stuck / badly forged clocks | **Does not kill 1× real-time paced dump** with *original* device_ts preserved — relative rate over the window matches live |
| **2 Session-freshness** (session_id / beacon salt) | Kills re-use of **old Composite-B artifacts / stored windows** from a foreign session | **Does not kill HID re-injection into a *new* session** — session_id is bridge-minted, not in the HID dump; new session gets a fresh binding and passes |
| **3 Optical (optional Phase-2)** | Strong live-now when present | Non-blocking for v0 — correctly stated |

**Conclusion on F1:**
- **Structural BLOCK is closed.** The design no longer pretends tremor/coupling kill replay. That was the r04 BLOCK core.
- **Defeat-claim residual (F19 WARN):** C11 / matrix #1 still say layers 1–2 "defeat naive/paced dump-replay." Under a faithful 1× re-injection of a real human HID dump into a fresh live session (original ticks, wall-paced), **both layers can pass**. That *is* the classic dump-replay F1 named. Calling only "sophisticated live-re-encode" the residual **understates** the residual class.

**Honest residual wording that would clear the over-claim (builder r07):**
> v0 layers 1–2 defeat *time-warped* / *artifact-replayed* / *foreign-session evidence reuse* attacks. Real-time 1× HID dump re-injection into a fresh session remains **OPEN** without layer-3 optical (or a session-start challenge nonce bound into the window evidence, or absolute device-clock bootstrap anchor). Sophisticated live-re-encode is a superset of that OPEN class, not the only member.

**F1 status: CLOSED:STRUCTURE + WARN residual (F19).** Not a re-opened BLOCK if residual is accepted as design ceiling; not PASS under strict "any WARN keeps HOLD."

---

### F2 — PARTIAL soft-pass → CLOSED

Machine pins present: `is_pass=false`, `streak_eligible=false`, `display_tier=amber`, no CONTINUOUS/SYNCHRONIZED alias. CONTINUOUS requires rail + gates. **Closed.**

Minor residual: see F20 (PARTIAL text "rail thin" vs rail-absent UNVERIFIABLE).

---

### F3 — G* aspirational gates → CLOSED

Honesty pin: leaf features exist; composite gate functions to-build. G3 no longer invents "non-pathological stationarity" as a shipped gate. **Closed.**

---

### F4 — device_ts scope / fail-closed → CLOSED

§4 correctly separates PoEP/L6b spike companion (exists) from continuous Composite-B window clock (to-build). Fail-closed UNVERIFIABLE when ticks absent; **no t_mono fallback** for the liveness claim. serialize() exclusion acknowledged. **Closed** as design. Implementation must not copy L6b's t_mono fallback.

---

### F5 — PoSP commitment vs reference → CLOSED

§5 chooses separate CANDIDATE record `realplay_liveness_v0` + named optional root `realplay_liveness_root` (parallel to `kas_session_root` / `retina_perception_root`). Explicit: PoSP mints no commitment; no domain-tag freeze this loop; tag stays CANDIDATE. Matches `posp.py` REFERENCE-AND-BIND. Naming discipline vs SYNCHRONIZED / SYNCHRONIZED_CONTROLLER stated. **Closed.**

---

### F6 — G4 missing → CLOSED

G4 absent (sparse presses / CFB26 L2C neutral) → max PARTIAL, cannot CONTINUOUS. Rail mandatory for CONTINUOUS; absence → UNVERIFIABLE. **Closed.**

---

### F7 — G5 over-credit → CLOSED

Matrix #2: G5 only if timing quantized; good ML bots OPEN; "NOT a general anti-bot." **Closed.**

---

### F10 — W_min smuggling → CLOSED

H_W30 / H_W120 / H_Wlong=one CFB quarter; hypotheses only; "default CONTINUOUS_PRESENT" and "match-half" removed. **Closed.**

---

### F13 + Q1 — GIC non-mutation → CLOSED

§3: parallel advisory counter only; MUST NOT feed consecutive_clean / GIC / fallback_verdict hash. §9 Q1 superseded to same rule (self-catch). Contradiction fixed. **Closed.**

---

### F17 — fractional f_min → CLOSED

G2 fractional ≥ f_min over W; MENU contributes 0; NULL invents no credit; matrix #5 updated. **Closed.**

---

### F16 — U2 unmeasured → REMAINS WARN (honest)

Still a hypothesis. Correctly not claimed as fact. Does not regress; still counts as surviving WARN under mandate.

---

### INFO items (F8/F9/F11/F12/F14/F15/F18)

All remain standing or improved (F12 zero-write invariant dependency restated; F14 machine fields pinned in C3/C8). No reopen.

---

## 2. C11 + adversary matrix re-attack

### Attack #1 — Recorded HID-stream replay

| Subcase | Killed by v2.1? | Auditor note |
|---------|-----------------|--------------|
| Fast-forward / slow-mo dump | **Yes** (rate lock) | Solid |
| Reuse old Composite-B window artifact on new session | **Yes** (session-freshness) | Solid as *evidence* anti-replay |
| 1× real-time dump re-injection, original device_ts, into **new** session | **No (OPEN)** | F19 — over-claimed as "naive/paced dump defeated" |
| Live-re-encode with forged ticks tracking wall + fresh token | **OPEN** (stated) | Correct residual language |
| + matching optical | Harder / Phase-2 | Correct non-blocking |

**Verdict:** matrix is **much more honest** than r03; still one over-credit on "paced dump."

### Attack #2 — Synthetic tremor

Honest. G4 when presses + G2 fractional; G5 only quantization; ML OPEN. **Stands.**

### Attack #3 — Human relay

Accepted residual. **Stands.**

### Attack #4 — Remote Play

Fail-closed device_ts path + U2 unmeasured. **Honest.**

### Attack #5 — Menu-AFK

Fractional f_min. **Stands** (threshold still unmeasured — U3, OK for CANDIDATE).

---

## 3. New findings this re-verify

| ID | Sev | Finding |
|----|-----|---------|
| **F19** | **WARN** | Layers 1–2 do not defeat **1× paced HID dump re-injection into a fresh session** with original device_ts. Residual class is broader than "sophisticated live-re-encode." Narrow C11 / matrix #1 residual wording. Optional strengtheners (pick ≥1 for residual-accepted PASS): (a) session-start challenge nonce mixed into window evidence, (b) CONTINUOUS requires optical layer-3, (c) absolute device-clock bootstrap vs session wall start with non-forgeable continuity, (d) explicit residual-accepted PASS with corrected residual text only (operator call). |
| **F20** | **WARN (minor)** | PARTIAL_PRESENT defined as "rail or a gate thin" while rail-**absent** is UNVERIFIABLE. Pin: rail fail-closed (absent/zero ticks/hard rate fail) → UNVERIFIABLE; only *soft* rate-lock within partial band → PARTIAL. Prevents PARTIAL becoming soft rail-fail. |
| **F21** | **INFO** | ε, f_min, G4 usable-fraction thr remain unstated numeric hypotheses — correct for CANDIDATE; pin "never invent in first code" at implement. |

No new BLOCK. No FROZEN/PoAC/chain pressure. No Thesis A resurrection attempt.

---

## 4. What stands strongly (credit)

1. **U1 CLOSED:NO / Thesis A dead** — re-verified; do not re-open.
2. **Architecture split** human-shaped (G*) vs live-now (rail) — the load-bearing intellectual fix.
3. **Fail-closed machine enum** CONTINUOUS / PARTIAL / UNVERIFIABLE with non-pass pins.
4. **PoSP pattern-correct** separate record + named root; no fake freeze.
5. **GIC non-mutation + Q1 self-catch** — grind integrity protected.
6. **G5 / ML residual / human-relay residual** — honest ceilings.
7. **W_min as hypotheses** — smuggle language removed.
8. **Design-only rails held** this loop.

---

## 5. Minimum to unlock PASS (r07)

Under **strict** mandate (any WARN → HOLD), residual-free PASS needs:

1. **F19 residual wording** corrected (and/or one hardener a–c above if operator wants a stronger claim).
2. **F20** thin-vs-absent rail pin (one sentence).
3. **F16** either accepted as residual-accepted WARN under operator residual-PASS rules, or left as measurement debt that still blocks pure PASS — **operator call**.

Under **residual-accepted PASS** (operator option, not automatic this round):  
r05 + F19 residual text fix + F20 pin + explicit "U2/U3 unmeasured, residual-accepted" seal → PASS possible without code. This re-verify does **not** auto-grant that; mandate keeps HOLD while WARNs survive.

**Not required for next design PASS:** implementing Composite-B code, flag flips, FROZEN freeze, optical mandatory (unless chosen as F19 hardener).

---

## 6. Claims C1–C11 (re-verify summary)

| Claim | Status |
|-------|--------|
| C1 U1 CLOSED:NO | **STANDS** |
| C2 zero-injection + to-build gates | **STANDS** |
| C3 ceiling + advisory machine fields | **STANDS** |
| C4 fail-closed + PARTIAL pins | **STANDS** (F20 minor wording) |
| C5 W_min hypotheses | **STANDS** |
| C6 device_ts scope + fail-closed | **STANDS** |
| C7 human-relay residual | **STANDS** |
| C8 separate CANDIDATE + PoSP root | **STANDS** |
| C9 Thesis C optional | **STANDS** |
| C10 design-only | **STANDS** |
| C11 rail establishes live-now | **PARTIAL** — structure stands; defeat-scope of layers 1–2 overstated (F19) |

---

## ONE VERDICT

# **HOLD**

**Why not PASS:** Surviving WARNs (F19 residual over-claim on paced dump; F20 minor; F16 U2 unmeasured). Mandate: any surviving WARN keeps HOLD.

**Why not re-BLOCK:** F1 *structure* is fixed — G3/G4 no longer falsely kill replay; a real anti-replay rail is specified; residual is acknowledged (needs wider residual class language). Critical F2/F4/F5/F6/F7/F10/F13/F17 all **CLOSED**.

**Rails:** design-only · no code · no flag flips · no FROZEN · no chain · no commit · 228B PoAC · PV-CI 184 · single-committer=operator.

**Next expected:** builder r07 residual-tightening (F19 wording ± hardener, F20 pin) → re-request re-verify for residual-accepted **PASS**, or operator seals residual-accepted PASS on this HOLD with explicit F19 acceptance.
