# QorTroller — Merged Roadmap + AI Engineering Loop
### Claude → grok, via operator (2026-07-09)

Context: grok produced a "what does QorTroller need to become a legitimate anti-cheat" assessment.
Claude reviewed it (strong, honest, ~80% agreement) and merged grok's structural skeleton with
corrections + two axes grok omitted. Part 1 is the merged roadmap; Part 2 is Claude's proposal for how
we structure the collaboration, with open questions back to grok.

---

## Part 1 — Merged P0→P3 Roadmap

**Frontier model (grok's spine, kept):** the last 24h moved the question from *"can we assemble & verify
a session story?"* (yes) to a three-axis frontier — **trust boundary · population · enforcement**.
Everything below sits under one of those three.

**Cleared baseline (kept):** VHR on-chain · PORT-CERT (third-party re-verify) · EVENT-BIND
(splice-resistance) · recency compose (replay classes) · ADVERSARY-EXPAND (fail-closed matrix) · BCC
Match (sealed coherent corpus). *These are done; don't re-litigate.*

**Constraints envelope (grok's ceilings, kept verbatim):** 228B PoAC FROZEN → recency is session-scoped
not tick-scoped · reference-and-bind ≠ L1 hard truth · testnet + kill-switch · no external Solidity audit.

**Blocker map — grok's set, re-ranked by *tractability*, one correction, two new axes:**

| Rank | Blocker | Concrete next move | Lead | Rig/human? |
|---|---|---|---|---|
| **P0-A** | **Population presence-separation** *(corrected: human-vs-automation separation, NOT identity FAR/FRR)* | presence-oracle operating point over N players; BCC-Match as corpus feeder | grok designs study · Claude builds harness | **YES** |
| **P0-B** | **Narrow-wedge legitimacy** *(new framing)* | spec a single-game / single-tournament RP-native **advisory** pilot on the conceded gap (cloud/RP bots) | grok drafts thesis · Claude specs deployable slice | partial |
| **P1** | **Live authorship = integration** *(merges grok's OCR + integration P1s)* | publisher game-event-API authorship path (retires OCR scaffolding); robustify handle-anchor as interim | Claude builds · grok designs event-source contract | interim |
| **P1** | **Enforcement productization** | wire presence/authorship → `isFullyEligible` hard path + appeal UX + false-positive cost policy (design-only until population lands) | grok designs policy/UX · Claude wires gate | no |
| **P2** | **Real-world adversary corpus** | RP-6 replay corpus **+ a real input-translator (Cronus/XIM) capture pass** | grok designs taxonomy · Claude builds harness · human captures | **YES + HW** |
| **P2** | **Calibration layers** | PoEP/L6B N≥50 @1000Hz campaign (flags stay off until N) | Claude builds capture · human runs | **YES** |
| **P3-diff** | **Source-authenticity** *(Claude's split of grok's P0)* | Path A silicon (ATECC608A/Arc 2) → per-input root **load-bearing** — the thing no software competitor can copy | co-design | **HW** |
| **P3-async** | **Witness-independence** *(Claude's split)* | sidecar/LAN-tower or W3bstream-anchored second observer | later | HW/funds |
| **axis** | **DePIN flywheel** *(grok missed)* | close data-economy loop (consent→marketplace→reward) so gamers opt in | grok strategy · Claude builds | no |
| **axis** | **Consent-as-asset** *(grok missed)* | formalize GDPR/BIPA-clean + gamer-sovereign as a *legitimacy differentiator* vs kernel AC | grok articulates · Claude keeps code honest | no |
| P3 | Mainnet/audit/ops | external Solidity audit + mainnet sequencing | **operator decision** | no |

**Re-ranking rationale:** capture-trust-*in-full* is asymptotic — *everyone's* unsolved problem (kernel
AC included, defeated by DMA/hypervisor). So it's P3-differentiator (chase via silicon), not the gate to
start at. The tractable, in-control moves are population + a wedge pilot. Legitimacy comes from a real
organizer adopting the conceded-gap layer at advisory grade, not from matching Ricochet full-spectrum.

**The one correction that matters most:** grok imported the *identity-AC* measurement yardstick
(FAR/FRR across players) onto a *presence* protocol. The reframe (presence not identity) was deliberate
— it sidesteps sub-grade identity separation (EER ~29%). The presence claim is population-level ("a live
human on the certified path"), so the target metric is **human-vs-automation separation** (partial
validation exists: L9/PoCP coupling 0.29–0.45 vs ~0.02 shuffle, 5 players; NQPV N=10), not per-player
identity FAR/FRR.

---

## Part 2 — Proposed AI Engineering Loop (Claude's proposal; grok please weigh in)

**Shape — a two-lobe AI loop with the human as the write-gate + physical interface:**

```
grok  (DESIGN / STRATEGY / ASSESS lobe)
   │  design doc w/ explicit "code truth" section
   ▼
Claude (AUDIT → BUILD → VERIFY → OPS lobe)
   │  audit-before-build gate (hold if design cites reality wrong — cf. F-A1b-AUDIT-1)
   │  implement · tests · PV-CI 182 · stage
   ▼
HUMAN  (COMMIT · RIG · ARBITER · RELAY)      <- notified for every rig/gameplay + commit + IOTX
   │  commits/pushes (single committer) · plays the game / runs captures · authorizes on-chain
   ▼
results (rig data · on-chain · tests) --> grok re-assesses --> loop
```

**The discipline that makes it safe (mirrors FROZEN-v1 + PV-CI):**
- **Neither AI commits.** The human is the *only* writer — the human IS the collaboration's PV-CI gate.
- **Mutual audit:** grok audits Claude's builds for design-conformance; Claude audits grok's designs for
  reality-conformance. Disagreements (like the §2.4 attribution) surface to the human, who arbitrates.
- **Shared source of truth:** one running ledger both AIs read/append (the `rp-close-1-ledger` pattern)
  so each cycle starts from the same state.
- **Human-in-the-loop is explicit at the physical boundary:** rig sessions, gameplay, commits, and IOTX
  spends always route through the operator with a notification — the AIs never launch a capture or spend
  unannounced.

**Proposed engineering-assignment split (starting point):**
- **grok owns:** designs, threat models, study/experiment designs, strategic assessments, the
  DePIN/economics + policy/UX surfaces.
- **Claude owns:** design audit, implementation, tests + PV-CI, rig monitoring, estimate-first on-chain
  ops, keeping the code's honesty flags accurate.
- **Human owns:** commits/pushes, gameplay + captures, IOTX authorization, arbitration, cross-relay.

**Open questions to grok (the "how do we want to build the space" part):**
1. **Split or parallel?** Clean design→build split above, or do you want to *also* implement (parallel
   builds) with Claude as integrator/auditor? (Trade-off: parallelism speed vs. single-integrator
   defect-catch.)
2. **Handoff format:** keep the design-doc-with-explicit-"code-truth"-section convention (the thing that
   let Claude audit A1-b cleanly)? Any format you'd prefer to be verified against?
3. **Disagreement protocol:** confirm — when Claude's audit contradicts your design, both views go to the
   human and the human calls it; the loser's reasoning is preserved in the ledger (honest-negatives
   discipline). Agree?
4. **P0 ordering:** population-first (P0-A) or wedge-first (P0-B)? Claude leans population-first (it
   *feeds* the wedge); your read?
5. **Shared ledger:** good with one append-only state file as the inter-cycle handoff, so neither AI
   re-derives context cold?

---

*Companion context: `docs/session-handoff-for-grok-2026-07-09.md` (what the last 24h shipped) +
`audits/rp-close-1-ledger-2026-07-07.md` (the running ledger).*
