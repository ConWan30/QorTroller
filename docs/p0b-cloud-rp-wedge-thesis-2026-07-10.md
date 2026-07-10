# P0-B — Cloud / Remote Play Narrow-Wedge Thesis

**Status:** THESIS / strategy artifact (2026-07-10). Loop sequence lane 2.  
**Not:** a deploy runbook, a tournament contract, or field-AC certification.  
**Audience:** operator · Claude (format / citation graph / pilot slice) · external organizer conversations (only with limits attached).  
**Rails:** advisory · developer_self · population_certified=False · verifier_independence=False · no FROZEN edit implied.

**Sequence:** P0-A v2 SEPARATED (`6395925a` arc) → P1 anomaly diagnostic (`3b8badc5`, PRIMARY=MARGINAL_AIM) → **this thesis**.

---

## 1. One-sentence wedge

**For cloud and Remote Play clients — where kernel anti-cheat cannot instrument the player machine — QorTroller can supply advisory oracle-viability evidence that aim-active human input is causally coupled to rendered motion and separable from modeled camera-injection automation, plus a multi-surface session certificate stack that third parties can re-check offline; it does not yet certify field cheats, identity, population, or hard tournament enforcement.**

Shorter (organizer one-liner, only if limits follow immediately):

> **Advisory presence attestation for cloud/RP — oracle-viable on aim-active play, not a Ricochet replacement.**

---

## 2. The conceded gap (why a wedge, not full-spectrum AC)

| Incumbent path | Cloud / Remote Play reality |
|----------------|----------------------------|
| Kernel AC (Ricochet, BattlEye, …) | No trusted local kernel on the **game host** the cheater controls when the game runs remotely |
| Server-side pattern detection | Sees the **streamed input stream**, not the controller-as-physical-source |
| GeForce NOW / similar | Vendor docs and industry practice concede a **client attestation gap** for pure cloud clients |

QorTroller’s thesis fits that gap: **prove something at the physical input + rendered output boundary** on the capture path the gamer/operator can run, without claiming kernel-equivalent host trust.

**Beachhead, not ocean:** one threat class (upstream / injected camera motion vs live aim), one environment family (RP/cloud-style clients), **advisory** grade, single-game pilot optional — not “replace kernel AC everywhere.”

---

## 3. What is now honestly citable (evidence graph)

### 3.1 Presence oracle viability (P0-A) — the new load-bearing cite

| Artifact | Claim |
|----------|--------|
| `audits/p0a-presence-op-v2-2026-07-09.{json,md}` | **VERDICT: SEPARATED** under pre-registered constants |
| Schema | `p0a-presence-op-v2` |
| Population | Aim-active sessions only (aim gate = 4× oracle abstain = 10.2 LSB) |
| Classes | Human live vs **modeled** automation (`synth_adversary` full camera injection × 3 modes) |
| Numbers | median human **0.374** · auto **0.067** · gap **0.307** · ratio **5.6** · causality clean (NC collapse) |
| Design | `docs/p0a-presence-separation-study-design.md` |
| v1 honesty | Raw pool **INCONCLUSIVE** remains permanent — no laundering |

**What this allows you to say:**

> We have a pre-registered, recomputable OP showing the L9 causal-coupling oracle separates aim-active human sessions from modeled full-camera-takeover automation on a 3-player developer corpus.

**What this does *not* allow:**

> Field FAR against Cronus/XIM · identity of which human · “all sessions” (low-aim excluded) · population-certified · enforcement.

### 3.2 The “below-threshold player” is classified (P1 diagnostic) — strengthens the wedge

| Artifact | Result |
|----------|--------|
| `audits/p1-anomaly-diagnostic-*.{json,md}` (commit `3b8badc5`) | PRIMARY **`MARGINAL_AIM`**, secondary **`HIGH_RESIDUAL`** |
| `p0a_v2_separated_unchanged` | **true** |
| P1 aim-active | med coupling ~0.09, med aim ~14.8 vs peers ~50 |
| T-H3 / T-H5 | lag/protocol did **not** fire as primary |
| T-H4 | untestable (P1 aim band has **0** peer sessions) |

**Wedge implication (load-bearing honesty):**

> The only labeled player below TAU_HUMAN on the aim-active set is a **low-aim / marginal-activity** style artifact, not a demonstrated false-negative on a peer-matched genuine aimer. That **supports** oracle-viability messaging; it does **not** prove every aimer will clear TAU_HUMAN.

**v3 implication (parked):** uniform-across-players claim is **not cleanly establishable** on this corpus without new real-aim P1 captures or an outcome-shaped gate. Optional; operator GO only.

### 3.3 Multi-surface session stack (already built — cite as composition)

These do **not** replace the OP; they answer “can a third party hold a session story?”

| Layer | What it contributes | Key cite |
|-------|---------------------|----------|
| **PoSP** | Session-level synchronized presence (KAS + NQPV + archive join) | `l9_presence/posp.py`, M14/M17 RP reports |
| **KAS / deferred** | Authorship of kills (live / archive) | `kas_deferred`, RP-2c/2d |
| **EVENT-BIND** | Crypto bind of HID onset ↔ screen event via PoAC `record_hash` (splice) | `event_bind.py` — **not** host-compromise proof |
| **PoSR recency** | Session-scoped replay resistance classes | `event_bind_recency.py` |
| **PORT-CERT** | Portable match certificate; off-rig re-verify | `port_cert.py`, M17 demo |
| **VHR on-chain** | Real Groth16 replay proof over M17 matrix + `ReplayProofVerified` | `submit_vhr_proof.py`, block 45479067 |
| **ADVERSARY-EXPAND** | 12 forgeries × named rails, holds | `presence_forgery.py` |
| **BCC Match** | Sealed match-presence corpus (SYNCHRONIZED + coherence) | `bcc_match.py` |

**Composition sentence (for thesis body, not marketing headline):**

> A gamer can hand a third party a portable Match Certificate; that party re-checks PoSP join, optional VHR, and on-chain digests without the rig. Per-event authorship can be splice-bound and recency-classed. Separately, the L9 oracle has a pre-registered human-vs-modeled-automation OP on aim-active play.

---

## 4. The wedge product shape (what an organizer is offered)

### 4.1 In scope for a first pilot (advisory)

| Offer | Grade |
|-------|--------|
| Per-session / per-match **advisory** presence + authorship package (PoSP / KAS / cert) | developer_self proven path |
| Offline **oracle viability** citation (P0-A v2 SEPARATED) for the causal-coupling layer | recomputable artifact |
| Fail-closed refusal examples (M15 link flip, hygiene fail) | empirical honesty |
| Player-sovereign framing (no kernel rootkit; consent rails) | legitimacy axis vs invasive AC |

### 4.2 Explicitly out of scope for that pilot

| Non-offer | Why |
|-----------|-----|
| Hard BLOCK of matchmaking / prize as sole authority | Enforcement productization still design-only |
| “We catch Cronus/XIM in the wild” | P2 real-adversary corpus not done; OP is **modeled** auto |
| “We know which enrolled human” | Identity OP not this stack’s claim |
| “Population-certified” | `population_certified=False` |
| “Trustless capture” | Self-witnessed; Path A silicon = long arc |
| OCR-perfect live killfeed authorship under all RP conditions | Scaffolding; publisher event API is the real path |

### 4.3 Suggested pilot envelope (spec, not committed deploy)

| Knob | Recommended default |
|------|---------------------|
| Games | **One** title (operator’s competitive context) |
| Mode | **Remote Play / cloud-adjacent** client path |
| Grade | **Advisory** only — soft signal + post-match review, not sole prize gate |
| Duration | Single event or weekend cup |
| Human subjects | Developer + opt-in players; no claim of N≥population science |
| Success metric | Organizer can re-verify ≥1 portable cert; 0 silent false “VERIFIED”; honest PARTIAL when tools missing |
| Failure metric | Any marketing that drops §5 limits |

Claude may turn §4.3 into a one-page “deployable slice” checklist later; this thesis does not require new code.

---

## 5. Limits that must travel with every external sentence

**Never drop these when the SEPARATED OP is cited:**

1. **Modeled automation** — synth full camera injection, not real Cronus/XIM/cloud-bot field rates (P2).  
2. **developer_self / not population-certified** — 3-player developer corpus.  
3. **Aim-active only** — low-aim sessions excluded by pre-registered gate; v1 raw pool was INCONCLUSIVE.  
4. **Pooled SEPARATED** — not uniform-across-players; P1 classified MARGINAL_AIM, not a peer-matched aimer fail.  
5. **Advisory** — not hard enforcement / not `isFullyEligible` sole authority.  
6. **Host not trustless** — PORT-CERT makes proofs portable, not capture independent; EVENT-BIND closes splice, not compromised host.  
7. **Testnet / kill-switch context** for on-chain cites — not mainnet production AC.  
8. **No new FROZEN-v1** implied by citing candidates (PoCP, BCC Match, etc.).

### 5.1 Approved external formulations

| OK | Not OK |
|----|--------|
| “Oracle-viability evidence for human vs modeled camera injection on aim-active play” | “Proven anti-cheat against all bots” |
| “Advisory cloud/RP presence attestation stack with third-party re-check of certificates” | “Kernel-equivalent protection for GeForce NOW” |
| “Pre-registered SEPARATED OP (gap 0.307) on a 3-player developer corpus” | “Population-validated FAR/FRR” |
| “P1 below threshold is low-aim style, not classified as automation” | “Every human player clears the gate” |

### 5.2 Canonical wedge paragraph (copy block)

> QorTroller targets the **cloud / Remote Play attestation gap**: environments where kernel anti-cheat cannot sit on the game client. We offer an **advisory** stack that (1) binds multi-surface session evidence (presence, authorship, portable certificate, optional on-chain replay proof), and (2) cites a **pre-registered operating point** showing the causal input→camera oracle separates **aim-active human** sessions from **modeled** full camera-injection automation (SEPARATED: median human 0.374 vs auto 0.067, gap 0.307; schema `p0a-presence-op-v2`). The sole labeled player below the human floor on that aim-active set is classified **marginal aim**, not a peer-matched coupling failure. This is **oracle-viability evidence for a narrow wedge**, not field certification against real cheat hardware, not identity anti-cheat, not population-certified, and not trustless capture.

### 5.3 Claude audit flags (2026-07-10) — verify before external use

Two flags from the lane-2 claim audit (**limits ⊆ claims otherwise PASS**; all *internal* numbers
recomputed real against the committed artifacts):

1. **Competitive claims are the one non-repo-verifiable class.** §2's "GeForce NOW concedes a client
   attestation gap" and "Ricochet input-pattern detection" are cited from a prior internal anchor and
   were **not re-verified against the vendor docs this session.** Confirm against the actual NVIDIA /
   Activision sources **before quoting either to an organizer** — everything else in the thesis is
   verified against the repo; these two lean on outside sources.
2. **EVENT-BIND is mechanism-proven, not live-validated.** The crypto splice-bind is tested +
   demonstrated synthetically; it has **not** run on a real authored-kill live capture (M18 was blocked
   on the handle anchor / RP-4). §3.3's "can be splice-bound" hedge is correct — **do not let it drift
   to "validated live."**

---

## 6. Citation graph (for Claude formatting / handouts)

```text
P0-B wedge thesis (this doc)
├── P0-A v2 SEPARATED .............. audits/p0a-presence-op-v2-2026-07-09.*
│   └── design ..................... docs/p0a-presence-separation-study-design.md
│   └── v1 INCONCLUSIVE (honesty) .. audits/p0a-presence-op-2026-07-09.*
├── F-P0A-V2-1 classified .......... P1 diagnostic PRIMARY=MARGINAL_AIM
│   └── design ..................... docs/p1-anomaly-diagnostic-design-2026-07-10.md
│   └── result ..................... audits/p1-anomaly-diagnostic-* (commit 3b8badc5)
├── Session stack .................. PoSP / KAS / PORT-CERT / VHR / EVENT-BIND
│   └── RP empirical ............... audits/rp-close-1-ledger-2026-07-07.md (M14–M17)
│   └── forgery matrix ............. audits/presence_forgery_matrix.json
├── Roadmap context ................ docs/qortroller-ai-loop-collab-2026-07-09.md (P0-B row)
└── Explicit non-claims ............ §5 this doc + design §7s
```

---

## 7. Relationship to remaining board

| Item | Role relative to wedge |
|------|------------------------|
| **P2 real adversary (Cronus/XIM, RP-6)** | Required before any “field cheat” language |
| **Publisher event API** | Retires OCR authorship fragility for live product |
| **Enforcement productization** | After organizer demand + population; not a prerequisite for advisory pilot |
| **Path A silicon** | Long-horizon source-authenticity differentiator |
| **DePIN / consent flywheel** | Why gamers opt in — parallel legitimacy axis (see collab doc) |
| **RP-4 latency cal** | Research unlock (LUMEN-3); not required to *cite* the OP |
| **Optional P0-A v3** | Parked until real-aim P1 (or new players) — not needed for wedge launch language |

---

## 8. Operator-decisions table

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-P0B-1** | Adopt §1 / §5.2 as external-safe wording | Yes | ☐ accept ☐ amend |
| **D-P0B-2** | Pilot envelope §4.3 (single game, advisory, soft gate) | Yes | ☐ accept ☐ amend |
| **D-P0B-3** | Do **not** claim field Cronus/XIM or population-certified | Yes | ☐ accept ☐ amend |
| **D-P0B-4** | v3 uniform-player OP remains parked | Yes | ☐ accept ☐ amend |
| **D-P0B-5** | Claude: citation handout / one-pager from §5.2 + graph | Optional | ☐ GO ☐ hold |
| **D-P0B-6** | Commit this thesis + ledger line | Operator GO | ☐ commit ☐ hold |

---

## 9. CODE-TRUTH / artifact paths (verify before external use)

| Path | Role |
|------|------|
| `audits/p0a-presence-op-v2-2026-07-09.json` | SEPARATED OP machine record |
| `audits/p0a-presence-op-v2-2026-07-09.md` | Human OP report |
| `audits/p0a-presence-op-2026-07-09.*` | v1 INCONCLUSIVE (keep cited) |
| `l9_presence/presence_separation_study.py` | OP harness |
| `l9_presence/synth_adversary.py` | Modeled negative class |
| `l9_presence/coupling.py` | Oracle math |
| P1 diagnostic audits (post-`3b8badc5`) | MARGINAL_AIM classification |
| `l9_presence/port_cert.py` | Portable cert |
| `docs/session-handoff-for-grok-2026-07-09.md` | Stack inventory |

---

## 10. Success criterion for this lane

Lane 2 is **done** when:

1. This thesis is accepted (or amended) by the operator.  
2. Every external cite of SEPARATED uses §5 limits.  
3. Claude (optional) produces a formatted one-pager whose claims ⊆ this doc.  
4. No code change is required for the thesis itself.

**Next in sequence after commit:** operator’s call — **RP-4 (rig)** or DePIN/consent prose, or stop at pause.

---

*End of P0-B cloud/RP wedge thesis v0 — 2026-07-10.*
