# DePIN / Consent Legitimacy Lane

**Status:** THESIS / strategy artifact (2026-07-10). Loop offline lane after P0-B.  
**Not:** a token whitepaper, TGE plan, deploy runbook, or new crypto primitive.  
**Audience:** operator · Claude (claim ⊆ reality audit) · external legitimacy conversations (only with §5 limits).  
**Rails:** advisory · developer_self / testnet on chain cites · population_certified=False · no fiat · 0 IOTX this lane · no FROZEN edit · PV-CI 182.

**Hand-off from P0-B §7:** the wedge answers *what can be proven on cloud/RP*; this lane answers *why a gamer opts in* — sovereignty + consent + corpus flywheel as a **different moat** from “we detect cheats.”

---

## 1. THE CLAIM (one sentence)

**QorTroller’s DePIN posture gives the gamer cryptographic sovereignty over their own presence and gameplay data — grant and revoke are the gamer’s own key; consent categories gate every legitimate downstream use; FSCA honesty instruments surface revoked-but-still-flowing contradictions — which is the opt-in incentive and the legitimacy contrast vs invasive kernel anti-cheat; it is NOT a live token economy, NOT a TGE, NOT population-certified reward issuance, and NOT a claim that the bridge can move consent on the gamer’s behalf.**

Shorter (only if §5 rides along):

> **You own the data path; the protocol cannot silently sell or keep what you revoke — that is why you run it, not because a token is promised.**

---

## 2. The legitimacy contrast (why this axis exists)

| Kernel / invasive AC | QorTroller DePIN + consent posture |
|----------------------|-------------------------------------|
| Treats the machine as hostile territory; deep client instrumentation | Treats the **gamer as sovereign** over biometric / session data |
| Legitimacy problem: privacy invasiveness, household third parties, always-on rootkits | Legitimacy asset: **no kernel rootkit**, category consent, revoke paths, audit rules |
| Player is a suspect | Player is the **agency-holder** over data their body and controller produce |
| Adoption = “must install or can’t play” | Adoption = **opt-in** for tournaments / research / marketplace tiers |

P0-B’s cloud/RP wedge is a **security gap** story. This lane is an **adoption + legitimacy** story. Both are required for a DePIN anti-cheat to be “real” in the social sense — not only the cryptographic sense.

**Brand line (display):** QorTroller — Core Controllers of their gaming data.  
**Category:** V.A.P.I. (Verified Autonomous Physical Intelligence) under DePIN / IoTeX Internet of Trusted Things.

---

## 3. The flywheel — what actually turns vs what is aspirational

### 3.1 Intended cycle

```text
  gamer opts in (consent categories + optional marketplace)
        │
        ▼
  presence / session evidence accumulates (PoAC, L9, match certs, BCC Match, …)
        │
        ▼
  corpus + oracle quality improve (P0-A SEPARATED is evidence the science path works)
        │
        ▼
  more value for organizers / buyers (attestation service, listings — when gated)
        │
        ▼
  more reason to opt in (sovereignty preserved; revoke remains real)
```

### 3.2 What actually turns **today** (honest)

| Stage | Reality |
|-------|---------|
| **Opt-in / consent machinery** | **Real in code + testnet contracts** — FROZEN CONSENT-v1, local `consent_ledger`, on-chain `VAPIConsentRegistry` (gamer `msg.sender` writes; bridge **reads only**). |
| **Honesty of revoke** | **Real as surveillance rules** — FSCA `CONSENT_REVOKED_BUT_DATA_FLOWING` + `CONSENT_REVOKED_LISTING_ACTIVE` (Curator + ledger). Not the same as automatic global erasure of every offline copy. |
| **Session / presence evidence** | **Real (developer_self)** — PoAC, PoSP, PORT-CERT, VHR, P0-A SEPARATED OP. |
| **Marketplace rails** | **Partially live on testnet** — listings contract, buyer registry, category verifier addresses recorded; Curator packaging paths exist. **Not** a liquid open market with external demand. |
| **Corpus → better oracle → more value** | **Partially demonstrated scientifically** (P0-A OP; BCC Match feeder designed) — **not** a closed economic loop with measurable demand-side spend. |
| **Token / supply-side rewards** | **Design-only / FROZEN sequencing** — Track-2B assessment exists; **no launch language**. |

### 3.3 What is aspirational (do not market as live)

| Stage | Status |
|-------|--------|
| Demand-side billing (organizers pay for attestation in protocol utility units) | Track-2B Phase 1 **design** — prerequisite for any reward schedule |
| Supply-side rewards for corpus / witnesses with hard period caps | Track-2B Phase 2 — **after** demand data |
| Burn-and-mint composition | Track-2B Phase 3 |
| TGE / liquid token | **Hard-gated** — see §5.1; not this thesis’s product |
| Population-scale corpus flywheel | Blocked on multi-operator adoption + privacy-safe capture — not on a missing slogan |

**Flywheel sentence for external use:**

> The sovereignty rails are real enough that opt-in is *legible*; the science rails are real enough that contribution *can* improve the oracle; the economic rails are **staged and gated** so rewards never outrun consent or separation honesty.

---

## 4. Evidence graph — deployed vs code-complete vs designed-only

*Discipline: each row is checked against repo + `contracts/deployed-addresses.json` notes. “LIVE (testnet)” means address recorded as deployed on chainId 4690 in that file / phase notes — **not** mainnet, **not** population production.*

### 4.1 Consent sovereignty (load-bearing)

| Surface | Maturity | Path / address | Notes |
|---------|----------|----------------|-------|
| **CONSENT FROZEN-v1 formula** | **FROZEN code** | `bridge/vapi_bridge/consent_categories.py` — `compute_consent_hash`, `_CONSENT_TAG = b"VAPI-CONSENT-v1"` | `SHA-256(tag \|\| device_id_b32 \|\| bitmask_be(4) \|\| expires_at_be(8) \|\| ts_ns_be(8))` |
| **Categories (enum)** | **FROZEN** | Same + `VAPIConsentRegistry.sol` enum | `TOURNAMENT_GATE=0`, `ANONYMIZED_RESEARCH=1`, `MANUFACTURER_CERT=2`, `MARKETPLACE=3` — position-for-position |
| **Local `consent_ledger`** | **Code-complete / operational** | store + operator record/revoke endpoints | Operational truth; operator API may write **local** ledger only |
| **`VAPIConsentRegistry`** | **LIVE (testnet)** | `0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA` (`_phase237_status: deployed`) | Gamer `grantConsent` / `revokeConsent` via **msg.sender**; bridge `chain.is_consent_valid` / `get_consent_record` **view-only**, fail-open if address empty |
| **Bridge never grants/revokes on-chain** | **Hard rule** | `CLAUDE.md` Hard Rules | Compromised bridge cannot rewrite on-chain consent; only local ops + read |

### 4.2 Honesty instruments (consent made non-decorative)

| Surface | Maturity | Path | Notes |
|---------|----------|------|-------|
| **FSCA `CONSENT_REVOKED_BUT_DATA_FLOWING`** | **Code-complete** (HIGH) | `fleet_signal_coherence_agent.py` CONTRADICTION rules | Joins `consent_ledger.revoked_at` to post-revoke `records` rows — GDPR Art.17 **candidate** signal |
| **FSCA `CONSENT_REVOKED_LISTING_ACTIVE`** | **Code-complete** (CRITICAL) | same + Curator `FLAGGED_CONSENT_AMBIGUOUS` | Marketplace consent cleared while listing still active; Curator loop cadence + FSCA poll (doc: ≤5 min / ≤15 min class) |
| **BiometricPrivacyComplianceAgent** | **Code-complete**, privacy decay TBD | BP-001 temporal decay rails | Related privacy metabolism; not the sovereignty key |

These rules **surface** contradictions; they do not by themselves erase every offline copy of data. Honesty = “we detect and flag,” not “GDPR solved.”

### 4.3 Data-economy stack

| Surface | Maturity | Address / path | Notes |
|---------|----------|----------------|-------|
| **VAPIDataMarketplace** (Phase 69) | **LIVE (testnet)** | `0x15D2Ac6d5802Bb8cBb8d3E35648385a7821630cC` | Three-tier licensing exchange (historical deploy) |
| **VAPIDataMarketplaceListings** | **LIVE (testnet)** | `0x78Df84Cc512EdCaC0e58a03e4852627E2F62E3bC` | Phase 238 Step H; Curator suspend path exists in O3 design |
| **VAPIBuyerRegistry** | **LIVE (testnet)** | `0x3742189eBDC09B115FA7e841C884247E9856130B` | Curator-attested buyer credentials |
| **VAPIBuyerCategoryVerifier** | **Address recorded** | `0x7EEc6B7Eb843532227528F63a0bC95D6cc537E53` | ZK / category verification surface (verify wiring before external “buyer ZK live” claims) |
| **Curator packaging** | **Code-complete** | `curator_packaging_loop.py`, O3 agent | Consent hash checks; packaging aborts on mismatch (tests) |
| **VAPIConsentManifestRegistry** (Arc 4 structured manifest) | **LIVE (testnet)** — `eth_getCode`-verified | `0x5F7c8068D0e61818FCD613D47e68a9Ea906a2743` | **Drift RESOLVED 2026-07-10:** `eth_getCode` on IoTeX 4690 returns **3869 bytes** of bytecode → deployed (control `VAPIConsentRegistry` = 2247 bytes confirms the RPC). The `docs/data-economy-deploy-hold-and-arc5-readiness.md` "DEFERRED" prose is **stale/superseded** (mirrors the `_reconciliation_2026_05_24` eth_getCode-correction precedent). Env-wiring check still advised before *consuming* it, but the address is live on testnet |
| **LISTING-v1 / marketplace commitment** | **Code / design family** | whitepaper + curator paths | Listings reference consent; not a free-for-all data dump |

### 4.4 IoTeX DePIN framing (infrastructure, not token)

| Surface | Maturity | Notes |
|---------|----------|-------|
| **ioID** | Integrated / testnet history | Device identity DID path; Path A MFG registry LIVE |
| **W3bstream** | Code-complete Wasm sandbox | Mechanical validation only (`frame_grabbing=false`); not a reward faucet |
| **Track-2B DePIN reward assessment** | **Canonical design anchor** | `wiki/assessments/DePIN Reward Architecture for VAPI Track-2B.md` — burn/mint, caps, **TGE gated** on demand-side reality + separation honesty |
| **AIT separation_ratio 1.199** | **Empirical (testnet demo corpus)** | Clears a science demo bar; **does not** authorize tournament hard BLOCK or token launch by itself |

---

## 5. Non-negotiable limits (audit must pass)

### 5.1 Token sequencing is FROZEN (no launch language)

- **Never** propose TGE, liquid token merchandising, or “rewards go live next week” in this lane.  
- Track-2B: demand-side billing **before** supply-side issuance; burn-and-mint last; TGE gated on measurable demand + separation defensibility discipline.  
- AIT ratio > 1.0 is a **science** milestone, not a **token** green light. Tournament-BLOCK enforcement and population-certified ops remain separate gates.  
- Reward economics in any discussion stay **utility-framed / design-only**.

### 5.2 Gamer-sovereignty invariant

- On-chain `grantConsent` / `revokeConsent`: **gamer wallet `msg.sender` only**.  
- Bridge / operator: **read** via `is_consent_valid` / `get_consent_record`; local `consent_ledger` for operational coordination — **never** “the bridge granted marketplace consent for you.”  
- Compromised bridge **cannot** rewrite on-chain consent state (read-only views).

### 5.3 Consent ≠ omniscient privacy

- Tournament ToS / category consent **does not** automatically cover **incidentally captured household third parties** (BIPA / GDPR Art.9 / CIPA lessons — Track-1 sensor stack).  
- Prefer **presence / optical-witness / non-mic** paths over any microphone or always-listening capture.  
- FSCA flags post-revoke **data flow** and **active listings** — necessary but not sufficient for full legal erasure of all offline copies.

### 5.4 Scope tags on every chain / science cite

- **testnet** (IoTeX 4690) · **developer_self** where presence science is cited · **population_certified=False** · **no fiat** settlement claims.

### 5.5 Engineering freeze for this lane

- No new FROZEN-v1 family · no chain writes in the thesis work · **0 IOTX** · PV-CI **182** unchanged · no capture-path edits.

### 5.6 Approved vs forbidden phrases

| OK | Not OK |
|----|--------|
| “Gamer-sovereign per-category consent; bridge reads only” | “We manage your consent for you” |
| “FSCA flags revoke-vs-flow contradictions” | “Fully GDPR-compliant erasure guaranteed” |
| “Marketplace rails exist on testnet; economic loop is staged” | “Live DePIN rewards / TGE soon” |
| “Opt-in legitimacy vs kernel invasiveness” | “Better than Ricochet at detection” (different axis; P0-B owns detection gap) |
| “Track-2B utility design, gated” | “Tokenomics launch roadmap for investors” |

---

## 6. Relationship to P0-B wedge (do not conflate)

| Doc | Question |
|-----|----------|
| **P0-B** | What can we *prove* on cloud/RP, and what OP is citable? |
| **This lane** | Why would a *gamer choose* to participate, and why is that *legitimate*? |

**Combined external story (limits still attach):**

> On cloud/RP, QorTroller offers **advisory presence attestation** with a pre-registered oracle OP (P0-B). Players opt in because **they hold consent keys** and downstream use is category-gated and contradiction-monitored — not because a rootkit is forced on their PC (this doc).

---

## 7. Optional honesty instrument (proposal only — not bundled)

| ID | Idea | Why optional |
|----|------|----------------|
| **D-DEPIN-OPT-1** | **Consent-flow status reporter** (read-only CLI/script): for a device_id, print local ledger categories + on-chain `is_consent_valid` (fail-open) + last FSCA hits for the two CONSENT_REVOKED rules | Makes sovereignty **observable** without moving keys; default-off / offline |
| **D-DEPIN-OPT-2** | **Flywheel metrics stub** (advisory JSON): counts of consent grants/revokes, listings suspended for consent, BCC Match harvest rate — **no** reward math | Prevents “flywheel” from staying pure narrative; **no token fields** |

Neither is required for the thesis to land. Claude should **not** implement unless operator checks a decisions row.

---

## 8. Operator-decisions table

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-DEPIN-1** | Adopt §1 claim + §5 limits as external-safe framing | Yes | ☐ accept ☐ amend |
| **D-DEPIN-2** | Token/TGE language remains forbidden in this lane | Yes | ☐ accept ☐ amend |
| **D-DEPIN-3** | ConsentManifestRegistry drift **RESOLVED** — `eth_getCode` 2026-07-10 = 3869 bytes → **LIVE (testnet)**; old DEFERRED prose stale/superseded | Yes | ☐ accept ☐ amend |
| **D-DEPIN-4** | Pair with P0-B for organizer talks; never drop either doc’s limits | Yes | ☐ accept ☐ amend |
| **D-DEPIN-5** | Optional consent-flow reporter (OPT-1) | Hold | ☐ GO ☐ hold |
| **D-DEPIN-6** | Optional flywheel metrics stub (OPT-2) | Hold | ☐ GO ☐ hold |
| **D-DEPIN-7** | Commit this thesis + ledger line | Operator GO | ☐ commit ☐ hold |

---

## 9. CODE-TRUTH index (verify paths)

| Topic | Path |
|-------|------|
| CONSENT formula + categories | `bridge/vapi_bridge/consent_categories.py` |
| On-chain consent contract | `contracts/contracts/VAPIConsentRegistry.sol` |
| Chain read helpers | `bridge/vapi_bridge/chain.py` (`is_consent_valid`, `get_consent_record`) |
| Hard rules | `CLAUDE.md` — CONSENT FORMULA; bridge never grants/revokes |
| FSCA consent rules | `bridge/vapi_bridge/fleet_signal_coherence_agent.py` |
| FSCA tests | `bridge/tests/test_phase237_consent.py`, `test_phase_238_curator_fsca_rules.py` |
| Deployed addresses | `contracts/deployed-addresses.json` |
| Arc 4 manifest contract | `contracts/contracts/VAPIConsentManifestRegistry.sol` |
| Deploy-hold historical note | `docs/data-economy-deploy-hold-and-arc5-readiness.md` |
| Track-2B rewards (design only) | `wiki/assessments/DePIN Reward Architecture for VAPI Track-2B.md` |
| Marketplace listings | `VAPIDataMarketplaceListings` address in deployed-addresses |
| Buyer registry | `VAPIBuyerRegistry` note LIVE testnet |
| Curator packaging | `bridge/vapi_bridge/curator_packaging_loop.py` |
| P0-B wedge | `docs/p0b-cloud-rp-wedge-thesis-2026-07-10.md` |
| Presence OP (science cite only) | `audits/p0a-presence-op-v2-2026-07-09.json` |

---

## 10. Success criterion for this lane

1. Operator accepts (or amends) §1 + §5.  
2. Claude audit: every “LIVE” row ⊆ addresses file / phase notes; dual-source ManifestRegistry flagged; no TGE language.  
3. No code required to close the lane.  
4. Optional instruments only if D-DEPIN-5/6 GO.

**Sequence after commit:** still operator’s call — **RP-4 (rig)** remains the highest-value hardware lane; this thesis does not unlock captures.

---

*End of DePIN / consent legitimacy lane v0 — 2026-07-10.*
