# QorTroller × IoTeX Halo Grants — DePIN Incubator Application

> **Status:** Draft for operator review · Submission target: IoTeX Halo Grants
> Program · Tier: **Project Grants → DePIN Incubator**

---

## One-sentence pitch

**QorTroller is the reference implementation of V.A.P.I. — a coined DePIN
sub-category where a gamer's hands on a certified controller are themselves
the cryptographic agency-holder over the data those inputs generate — built
natively on IoTeX L1 with 53 live testnet contracts, 14 FROZEN-v1
cryptographic primitives, and an end-to-end Verified-Human-Replay (VHR)
proof pipeline that proves humanity without revealing identity.**

---

## What this grant funds

A **mainnet promotion ladder** for the QorTroller protocol AND a
**reference-controller R&D track** that closes Sony-hardware dependency
and ships the Internet-of-Trusted-Things reference DePIN controller
IoTeX's mission has been waiting for. Six load-bearing funding lanes:

1. **Multi-contributor mainnet trusted-setup re-ceremony** (≥3
   independent contributors per practitioner norm; current testnet
   ceremony has 2, see `docs/data-economy-arc5-ceremony-transcript.md`)
2. **Batched mainnet deploy** of the 14-contract Data Economy ladder
   (Arcs 1–6) + the on-chain Operator Initiative fleet
3. **First tournament-operator integration** consuming
   `VAPIProtocolLens.isFullyEligible()` as a single-call eligibility gate
4. **Path A Arc 2 — silicon-rooted per-PoAC signing** on ATECC608A or
   equivalent secure element (the explicitly-scoped-out v1 → v2 frontier
   per `docs/path-a-arc2-prompt.md`)
5. **Reference DePIN controller — design, prototype, semiconductor-
   partnership outreach.** Includes formal introduction to **Qorvo
   Semiconductor** regarding chip-level alignment for the four IC
   categories a V.A.P.I.-native controller requires: secure
   microcontroller (PoAC-record silicon-root signing), high-precision
   IMU (L2 gravity discrepancy + L4 micro-tremor fingerprint), Hall-
   effect / TMR stick sensors (Sensor Stack v2.1 PRIMARY-DISCRIMINATOR
   candidate), and adaptive-trigger force feedback (the L4-coupled-to-
   L6 challenge-response channel). The hardware ask is **honest**:
   grant funds the R&D + outreach, not a finished product. Partnership
   with Qorvo is the OUTREACH GOAL of this lane, not a completed
   negotiation.
6. **Independent security audit** of the marketplace-listing +
   consent-manifest contracts pre-mainnet.

The grant covers (a) ceremony coordination + auditor stipend, (b) the
IOTX budget for mainnet deploys (~50–100 IOTX once-off + ~95 IOTX/year
for the temporal-beacon keeper at empirical 2.6 s/block on IoTeX), (c)
hardware acquisition for Path A Arc 2 secure elements (~$200) + sensor-
stack characterization (Hall-effect / TMR mod kits for the v2.1 same-
model separability study, ~$2k), (d) **reference-controller R&D**:
schematic + PCB design, prototype fabrication, EVT / DVT iteration,
firmware bring-up (~$25–40k depending on parts sourcing), (e) **Qorvo
partnership outreach**: introduction package, technical alignment
sessions, partnership coordination (~$5k), and (f) independent contract
audit (~$15–25k).

---

## Why QorTroller is DePIN-Incubator-tier ready (not Developer-tier)

| Eligibility criterion | Evidence |
|---|---|
| "Existing product" | **53 live testnet contracts** (chain 4690); 4,400+ automated tests; **174 PV-CI invariants** enforced on every PR via GitHub Actions matrix CI |
| "Expertise in field" | Coined the **V.A.P.I.** (Verifiable Autonomous Physical Intelligence) DePIN sub-category; **14 FROZEN-v1 cryptographic primitives** with auditor-reproducible domain tags; six published ZKBA artifact types |
| "DePIN from scratch OR adding DePIN elements" | **Native DePIN** — the protocol's whole thesis is "physical input source = cryptographic actor"; not a port, not an add-on |
| Build native to IoTeX | Uses IoTeX-specific surfaces: P256 precompile at `0x0100` for ECDSA verification, IoTeX Roll-DPoS block hashes as PoSR temporal beacons, ioID DID infrastructure references throughout |
| On-chain proof of activity | **Operator Initiative O3_ACTING ceremony fired live 2026-05-17** (6 txs, Fleet Readiness Root `0x54b4b698…` permanently committed); **GIC_100 milestone reached 2026-05-05** (chain head `0x0e9d453d…`); first device registered + first gamer-self-sovereign consent manifest written from real wallets |
| Empirical claim third parties can falsify | AIT separation ratio **1.199** at N=37, all inter-player pairs >1.0; corpus published; methodology open |
| Open source | **Public GitHub repo** (flipped 2026-05-31); whitepaper v5; comprehensive zero-trust security assessment; full ceremony transcript; deploy-hold audit |

---

## What's already shipped (evidence package)

- **Data Economy ladder, Arcs 1–6:** buyer registry → ZK buyer-category proof
  → curator packaging loop → structured consent manifest (gamer-address-keyed,
  self-sovereign by Solidity invariant) → VHR replay-proof pipeline → PoSR
  session-recency binding (Arc 6, FROZEN-v1 #14 `VAPI-TEMPORAL-BEACON-v1`)
- **Arc 7 cryptographic sidecar:** post-quantum commitment binding through
  the verification path (additive — `pqCommitment` carried alongside beacon
  hashes; opaque to registry, required-non-zero)
- **PITL 9-layer anti-cheat stack** with calibrated humanity-probability
  formula (per-feature weights earned by within-corpus separation, not
  opinion)
- **Operator Initiative fleet at O3_ACTING:** first ≥3-agent fleet at full
  action authority in any DePIN gaming protocol (Sentry + Guardian + Curator)
- **Methodology Layer (VAD + ZKBA + VPM):** six artifact types composing
  proofs over the FROZEN primitives
- **Path A silicon-rooted iPACT:** manufacturer-authoritative device birth
  registry; first real DualSense Edge registered on-chain
- **L9 Presence arc:** strategic identity → presence reframe; PoEP +
  PoCP validated; honest negatives published (GCAP lattice)
- **GitHub Actions matrix CI** (Python 3.10/3.11/3.12 × Node 18/20 + Rust +
  WASM) enforcing the 174-invariant gate on every PR

---

## What's deferred (honest about what the grant unlocks)

- **Mainnet deploys:** all 14 contracts currently on testnet; mainnet
  promotion requires the re-ceremony + a deliberate batched deploy day
- **First live VHR proof against a real gameplay session:** the bridge
  + Arc 5 + Arc 6 wiring is complete and tested; first real proof lands
  on the next gameplay window after a bridge restart (recordable on-chain
  via the deployed verifier at `0x5182372d…`)
- **Tournament partner integration:** the `VAPIProtocolLens.isFullyEligible()`
  call is a single-line integration for any tournament operator; no live
  partner yet (grant-supported outreach is part of the ask)
- **Path A Arc 2 hardware silicon:** ATECC608A integration is the prompt-
  ready next arc; gated on physical hardware connection (`docs/path-a-arc2-prompt.md`)
- **Sensor Stack v2:** Hall-effect stick same-model separability study
  requires N≥20 stock + N≥20 batched aftermarket units (~$2k hardware)

---

## Why a purpose-built reference controller is architecturally necessary (Path A v1 → v2)

QorTroller's Path A architecture currently treats the **DualSense Edge
CFI-ZCP1** as the reference certified device because that's the
production hardware available today. Path A Arc 1 (LIVE 2026-05-26/27)
ships silicon-rooted iPACT *renewal authenticity* — proving the
controller's identity at session-boundary cadence. Path A Arc 1's
explicitly-scoped-out v1 → v2 frontier is the **per-PoAC-record
silicon-root** — proving every 228-byte cognition-cycle record was
signed by the certified silicon, not just the host. v2 closes the only
remaining trust-model gap in the protocol.

The `VAPIManufacturerDeviceRegistry` (LIVE at
`0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0`) already encodes the
manufacturer-authoritative trust model with FROZEN
`signingPath = {1=A silicon, 2=B host}` and FROZEN
`proofTier = {1=FULL CFI-ZCP1, 2=STANDARD CFI-ZCT1, 3=BASIC}` enums.
The contract surface is **designed for multiple certified
manufacturers**. Sony is the v1 reference. **A QorTroller-controlled
reference design is the v2 architecture** — not a parallel project,
but the next certified-manufacturer row in a registry that has been
waiting for it.

The Sensor Stack v2.1 architectural revision (`docs/methodology/sensor_stack_v2_1_architectural_revision.md`)
identifies the **adaptive-trigger force-curve** as the PRIMARY
DISCRIMINATOR candidate (8-bit per trigger axis at ~1 kHz on Edge over
USB; inter-subject EER 1–15 % lab-to-field per Saevanee 2009 / Antal
2015 / Wakita 2006 / Miyajima 2007 / Van Vugt 2013). The Hall-effect /
TMR stick separability question (Empirical Unknown #4) is the load-
bearing study gating cross-session controller identity claims. A
purpose-built reference controller lets QorTroller specify these
sensor surfaces at chip selection time — eliminating the dependency
on aftermarket DualSense mods that the v2.1 revision currently
contemplates.

**Qorvo Semiconductor is a credible chip-category match across all
four required ICs**: secure microcontroller (PoAC silicon-root signing
+ ATECC608A-class secure element), high-precision IMU (the L2 gravity-
discrepancy + L4 micro-tremor surfaces depend on IMU resolution),
Hall-effect / TMR stick sensors (Sensor Stack v2.1 PRIMARY-
DISCRIMINATOR candidate), and adaptive-trigger force feedback (the
L4-coupled-to-L6 challenge-response channel). The outreach ask in this
grant is **honest**: introduce QorTroller's V.A.P.I. category to
Qorvo's gaming / IoT vertical, evaluate chip-level alignment, explore
partnership terms. Grant funding the outreach + technical alignment
sessions is the correct grant framing — not a pretense that a deal
exists.

A **reference DePIN controller** is also exactly the artifact IoTeX's
Internet-of-Trusted-Things mission has been waiting for: a hardware
reference design that future DePIN-gaming projects can manufacture
under license, that ships with IoTeX-native ioID DID infrastructure
baked into bring-up firmware, and that demonstrates the
manufacturer-track concretely instead of as documentation.

---

## Roadmap — milestones tied to grant funding

| Milestone | Deliverable | Estimated funding lane |
|---|---|---|
| **M1** (month 1) | Mainnet trusted-setup re-ceremony, ≥3 contributors, public transcript published | Coordination + auditor stipend |
| **M2** (month 2) | Mainnet deploy of all 14 Data Economy contracts + Operator Initiative fleet | Mainnet IOTX gas budget |
| **M3** (month 3) | First live VHR proof on real NCAA CFB 26 session, recorded on-chain, demo video published | Testnet → mainnet bridge config; demo asset for IoTeX newsletter |
| **M4** (months 4–5) | Tournament-operator integration partnership (target: collegiate esports league) | Outreach + integration support |
| **M5** (months 4–6) | Path A Arc 2 — real ATECC608A silicon-rooted PoAC signing | Hardware (~$200) + integration time |
| **M6** (months 5–7) | Sensor Stack v2 PRIMARY DISCRIMINATOR validation (Hall-effect same-model separability study) | Hardware (~$2k Hall-effect Edge mods) + corpus collection |
| **M7** (months 6–9) | Independent security audit of marketplace + consent registry | Audit firm engagement |
| **M8** (month 9) | Phase 99 token launch (gates already cleared: separation>1.0, GIC_100, Phase O3 ACTING) | Launch coordination + marketing |
| **M9** (months 3–4) | **Qorvo Semiconductor partnership outreach** — introduction package + V.A.P.I.-category technical brief delivered; ≥1 technical alignment session held; partnership scope letter exchanged (whether positive or negative, the outcome is a publicly-citable evaluation) | Outreach package preparation, travel, technical-alignment sessions |
| **M10** (months 4–9) | **Reference-controller schematic + PCB design + EVT prototype** — secure-microcontroller for Path A Arc 2 silicon-rooted PoAC signing; Hall-effect / TMR sticks per Sensor Stack v2.1 PRIMARY-DISCRIMINATOR study; high-precision IMU exceeding DualSense Edge baseline; adaptive-trigger force-curve ≥8-bit @ 1 kHz; USB-C polling stable at ≥1002 Hz to match Phase 234.7 PCC NOMINAL requirement | Engineering design, PCB fab, prototype components, firmware bring-up |
| **M11** (months 9–12) | **DVT iteration + open reference-design publication** — schematic + BOM + firmware open-sourced under same license as the protocol; manufacturing spec ready for OEM partner; first device of QorTroller's own reference design registered on-chain via `VAPIManufacturerDeviceRegistry` as a new certified manufacturer | DVT components, OEM engagement, IoTeX-native bring-up firmware (ioID DID + PoAC silicon-root from first boot) |

---

## Why this matters to IoTeX's mission

The IoTeX foundation's stated mission centers on the **Internet of Trusted
Things** — DePIN protocols where physical devices have cryptographic
agency. QorTroller is a maximally on-thesis instance of that mission:
the gamer + their certified controller are themselves first-class
cryptographic actors on IoTeX L1. The protocol uses IoTeX-specific
surfaces (P256 precompile, Roll-DPoS block hashes, ioID DID) that
would be expensive or impossible to replicate on other L1s. Successful
mainnet promotion gives IoTeX a flagship gaming-DePIN reference
implementation: open source, auditor-reproducible, with a coined
category (V.A.P.I.) that future DePIN-gaming projects can compose
against.

The competitive surface QorTroller closes — cloud-gaming bot detection,
backdated session attacks, biometric privacy under tournament eligibility
gates — is exactly the surface published anti-cheat literature flags as
unsolved (WormVision Lite MAX userscript published 2024-12-26; NVIDIA's
GeForce NOW anti-cheat compatibility guide conceding the cloud-client
attestation gap; Activision RICOCHET Season 02 rolling out input-pattern
detection on the input-stream side because device attestation was
structurally compromised). QorTroller's V.A.P.I. category is the
honest architectural answer to those documented gaps.

**On the manufacturer-track / hardware angle specifically:** IoTeX's
Trusted Things mission is conceptually complete only when the
"trusted" physical device exists as more than a documentation
reference. The `VAPIManufacturerDeviceRegistry` is already deployed and
accepting certified manufacturers. The QorTroller reference controller
M9–M11 deliverables convert IoTeX's mission from "we have the
infrastructure to certify trusted devices" to "here is the first
trusted DePIN-native gaming device, fully open, manufactured under a
QorTroller-controlled reference design, with chip-level alignment
explored with Qorvo Semiconductor or comparable silicon partner." The
manufacturer-track + the Qorvo outreach are how the V.A.P.I. category
becomes a hardware reality that any DePIN-gaming project can compose
against.

---

## References (artifacts available for review)

- **Whitepaper:** `docs/qortroller-whitepaper-v5.md`
- **Genesis assessment:** `docs/qortroller-genesis-assessment.md`
- **Zero-trust security assessment:** `docs/qortroller-zero-trust-security-assessment.md`
- **Arc 5 spec + ceremony transcript:** `docs/VAPI_REPLAY_PROOF_PIPELINE_SPEC (1).md`, `docs/data-economy-arc5-ceremony-transcript.md`
- **Arc 6 PoSR keeper runbook:** `docs/posr-keeper-runbook.md`
- **Deploy-hold + Arc 5 readiness audit:** `docs/data-economy-deploy-hold-and-arc5-readiness.md`
- **PV-CI invariant gate (174 invariants):** `scripts/vapi_invariant_gate.py`
- **Live testnet contracts:** `contracts/deployed-addresses.json` (chain ID 4690)
- **GitHub Actions matrix CI:** `.github/workflows/ci.yml`

---

## Contact + repo

- **Repository:** https://github.com/ConWan30/QorTroller (public)
- **Active wallet (testnet):** `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`
- **Chain:** IoTeX testnet (4690); mainnet promotion is the load-bearing
  ask of this grant
- **License:** MIT (see `LICENSE`)

---

*Draft prepared 2026-06-01. Ready for operator polish + Halo Grants
submission. The protocol's whole architectural thesis — that the gamer's
hands are cryptographically meaningful, anchored on IoTeX L1, with
strict gamer-self-sovereignty enforced by `msg.sender` — is the kind of
on-thesis DePIN instance the Halo Grants program was designed to
incubate.*
