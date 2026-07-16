# WMP × QorTroller — Data-Production Ecosystem Portfolio (looped ideation)

**Status:** LOOP WORKFLOW (operator-invoked 2026-07-11). Each cycle adds verified use-case entries;
the loop stops at saturation (a cycle adds nothing new) or operator interrupt.
**Thesis under exploration:** the human gamer, producing through SKILL with a controller, manifests a
self-contained DePIN data economy — data production, analytics, proofs, and derivative proof-products —
fusing WMP with the full QorTroller stack on IoTeX.
**Hard rails (every entry):** ideation/doc/harness only · no wallet/deploy/chain-write/FROZEN/Solidity ·
WMP-5 outcome labels are **R-WMP5-HOLD** (entries may reference them only as gated-on-that-ruling) ·
TGE frozen, zero tokenomics · post-φ action-only exports (the biometric moat never exports) ·
every entry cites the module/contract that makes it real · claim ceilings mandatory · staged, operator commits.

**Entry schema:** what the gamer's skill produces → what proof attaches → who consumes → IoTeX carrier →
buildable-NOW vs gated (named gate) → claim ceiling.

---

## Cycle 1 — 2026-07-11 — Lens: core proof-products + first derivative class

### UC-1 · Certified action-demonstration corpora (the WMP base product) — **LIVE 2026-07-11** (first real bundle VERIFIED 5/5 zero-stub, recency explicitly deferred; WMP-4 `0x06836Fb8…`, consent tx `0x8f70bca3…`; `audits/wmp-phase2-first-real-bundle-2026-07-11.md`)
- **Produces:** post-φ action traces (stick sectors, trigger states, button mask, IMU gravity sector @60Hz/4-bit) from real matches.
- **Proof:** VHR Groth16 humanity (real proof precedent: M17, block 45479067) + PoSR open/close beacons (keeper LIVE) + Arc 4 consent (`0x5F7c8068…`) → `ProvenanceBundle` (`wmp/bundle_assembler.py`) → consumer runs the 5-check verifier (`sdk/wmp_verify.py`) trustlessly.
- **Consumer:** world-model / imitation-learning labs (Li-taxonomy planner-demo scarcity).
- **IoTeX carrier:** ZK verifiers + TemporalBeaconRegistry + ConsentManifestRegistry; ioID DID join optional (D-IOID-CER-2: honest `ABSENT` allowed pre-registration).
- **Buildable:** **NOW** — WMP Phase-2 promote ≈0.3–0.6 IOTX; 3/5 verifier legs already live-capable (vision doc §2). Gate: operator's explicit WMP-4 deploy choice.
- **Ceiling:** action-only, no observation channel, macro-intent-not-biomechanics, `is_full_pomdp_tuple=false`, demand-is-thesis.

### UC-2 · Skill-stratified corpora (the SKILL axis made into product structure) — **BUILT 2026-07-11** (`d8bf2fe5` — `l9_presence/skill_strata.py` session-demonstration bands + verify-by-rederivation + `wmp_metadata` hook; marker reconciled 2026-07-16)
- **Produces:** the same action corpora, **stratified by protocol-measured skill bands** — session verdict streaks (GIC-eligible clean sessions), L5 rhythm stability, AIT-corpus membership, authored-kill density per match. "Expert vs intermediate demonstrations" is a real curriculum-learning need.
- **Proof:** the strata labels derive ONLY from protocol verdicts already computed (`ruling_validation_log`, KAS records, AIT snapshots) — a labeling harness maps verdict history → band; the band ships as a bundle metadata field, the underlying data stays post-φ. No biometric leaves.
- **Consumer:** curriculum/imitation-learning teams; NPC-difficulty calibration (GAME_DEV buyer category, FROZEN enum INV-BUY-001).
- **IoTeX carrier:** marketplace data-tier bools (Arc 4 Dimension 1 — the 4 skill tiers already exist in the manifest struct!).
- **Buildable:** **NOW (code-only)** — a `wmp/skill_strata.py` labeling harness over existing logs + a strata field in bundle metadata (additive, non-FROZEN). Gate: a grading-methodology note + the ceiling below.
- **Ceiling:** bands are **protocol-internal labels, not certified rank** — no ELO/matchmaking claims, no cross-player identity comparisons (population gate stands), `developer_self` grade.

### UC-3 · Anti-bot ground-truth baselines (coopetition — selling certified-human to other detectors)
- **Produces:** certified-human input corpora as **training baselines for third-party bot detectors** — "what real human macro-input looks like," provenance-attested.
- **Proof:** identical WMP stack; the *value inversion* is the consumer class — anti-fraud ML teams need uncontaminated human baselines more than anyone, and post-φ is exactly right for them (they need macro patterns + provenance, NOT our micro moat — which never exports, so we can sell to competitor-detectors without arming bot-makers).
- **Consumer:** studio anti-cheat teams, bot-detection vendors, platform trust-and-safety ML.
- **IoTeX carrier:** marketplace listings (`VAPIDataMarketplaceListings` LIVE) + buyer-category ZK gating.
- **Buildable:** gated on the **Arc 2 buyer-category prover** (verifier live `VAPIBuyerCategoryVerifier`, prover ABSENT — the known missing half; code-only build).
- **Ceiling:** baseline-data supplier claim only — never "our data catches X% of bots"; no field-FAR transfer.

### UC-4 · The verified play-résumé (skill-work analytics as a portable credential) — **BUILT 2026-07-11** (`8f12d1d5` — `l9_presence/play_resume.py` assembler + verifier; marker reconciled 2026-07-16)
- **Produces:** a gamer's cryptographic play history digest — verified session counts, clean-streak lengths, match spans (LUMEN-2b), authored-kill totals (KAS), beacon-anchored time windows — the *provable* version of a Tracker.gg profile.
- **Proof:** an assembler rolls existing artifacts (KAS records, PoSP, match certificates, GIC status) into a REFERENCE-AND-BIND résumé document; PORT-CERT-style off-rig verify; optionally bound to the controller's `did:io:` + the gamer's VHP soulbound (tokenId precedent exists).
- **Consumer:** esports org scouting, sponsorship qualification (BRAND buyer category), tournament seeding evidence.
- **IoTeX carrier:** ioID DID + VHP (ERC-4671) + beacons; zero new contracts needed for v1 (document + verifier, chain-referencing).
- **Buildable:** **NOW (code-only)** — `l9_presence/play_resume.py` assembler + verifier, same pattern as `match_certificate.py`. Gate: none hard; ioID join waits on D-IOID-CER-5 wire-up.
- **Ceiling:** counts and verdicts only — **no rank, no identity certification, no "best player" claims**; explicitly `advisory=true`, `population_certified=false` (PORT-CERT precedent fields).

### UC-5 · Provenance-preserving analytics (W3bstream as the verifiable compute rail)
- **Produces:** derived statistics over bundles — APM distributions, session cadence, engagement-window histograms — where **the analytic itself carries provenance** (computed inside the W3bstream wasm sandbox over commitment-bound inputs, so the buyer verifies the *statistic*, not just the raw data).
- **Proof:** extend the existing applet (`w3bstream/applet/src/lib.rs` — `EvmLogPayload` already carries `events_root`) with pure-wasm aggregate functions over bundle references; output = (statistic, input-commitment-set, applet-version) triple.
- **Consumer:** analysts/brands who want metrics without buying raw corpora — a cheaper, smaller product tier.
- **IoTeX carrier:** W3bstream (its actual purpose: verifiable off-chain compute for DePIN).
- **Buildable:** **NOW (code-only, wasm)** — additive applet functions; sandbox stays mechanical-validation+aggregation (no capture, INV-W3S rails hold). Gate: applet test harness extension.
- **Ceiling:** statistics over consented exports only; no cross-gamer aggregation without every contributor's consent bit; no liveness/biometric-derived metrics.

### UC-6 · The BCC supply flywheel (breadth as the production engine)
- **Produces:** the *growth mechanism* for all of the above — the Behavioral Capture Chain (genesis `QORTROLLER-BCC-GENESIS-v0`, dormant, Witness-wired) harvests ONLY presence-certified causal sessions into a self-cleaning corpus. Every new player = new certified supply; the wedge's "open lever = breadth" becomes the data economy's supply curve.
- **Proof:** BCC's own chain + the per-session stack; corpus growth is itself auditable (CORPUS-SNAPSHOT FROZEN-v1 primitive already anchors corpus state on-chain — precedent tx exists).
- **Consumer:** internal (supply); externally it IS the scaling story for buyers ("corpus grows verified").
- **IoTeX carrier:** CORPUS-SNAPSHOT anchoring (ProtocolCoherenceRegistry reuse) + consent per contributor.
- **Buildable:** gated — BCC is deliberately dormant (`enabled=False`); flipping it is an operator decision tied to multi-player capture campaigns (the held science). Named gate: population/presence campaign.
- **Ceiling:** corpus-growth claims only after real N; never imply current N>1-player breadth.

---

## Cycle 2 — 2026-07-11 — Lenses: organizer-side · academic · fleet · federation · WMP-5-contingent

### UC-7 · Federated integrity intelligence (organizer-network data product)
- **Produces:** anonymized, consented cross-instance integrity signals — verdict-class distributions and threat patterns shared between QorTroller-running events, so each organizer benefits from every other organizer's observations.
- **Proof:** the federation surfaces already exist — `bridge/vapi_bridge/federation_bus.py` + `FederatedThreatRegistry.sol` (in `deployed-addresses.json`); signals ride as commitments, never raw sessions.
- **Consumer:** tournament-organizer network (the pilot's natural expansion: one organizer → a mesh).
- **IoTeX carrier:** FederatedThreatRegistry anchoring; consent per contributing gamer.
- **Buildable:** mostly EXISTS dormant — gate: pilot demand (≥2 participating events) + a federation-consent note. No new chain spend to design.
- **Ceiling:** pattern-sharing only; no cross-event player identification (identity claims stay off the table).

### UC-8 · Controller-fleet capability telemetry (hardware-partner data product) — **BUILT 2026-07-16** (`bridge/vapi_bridge/wmp/fleet_telemetry.py` — device-MODEL aggregation over l6b_probe_log CCO rows; min-devices-per-bucket floor suppresses under-floor buckets entirely; no device_id in output, per-unit fingerprinting structurally excluded; 7 tests)
- **Produces:** aggregated controller-MODEL capability distributions — trigger-force-curve classes, haptic response envelopes, per-tier verification rates — device data, not gamer data.
- **Proof:** the CapabilityOracle + CCO Phase G measurements already exist (`capability_oracle.py`; `CCO_PHASE_G_VALIDATED_TIERS` — PREMIUM_EDGE N=210, MID_TIER N=130, operator-attested); an aggregation harness rolls per-model stats with device-count floors.
- **Consumer:** hardware vendors/design houses (the Qorvo outreach precedent is exactly this audience) + the HWFL-1 dev-kit lane's own BOM decisions.
- **IoTeX carrier:** marketplace listing (device-telemetry tier) + MFG registry proofTier joins.
- **Buildable:** **NOW (code-only)** — aggregation harness over existing CCO data. Gate: an aggregation-floor rule (min devices per bucket) so no single controller is identifiable.
- **Ceiling:** device-class statistics only; never per-gamer, never per-unit fingerprints (CROSS-LESSON-001 separability constraint respected).

### UC-9 · IRB-grade motor-behavior research datasets (academic positioning of UC-1)
- **Produces:** the same post-φ action corpora, packaged for human-subjects research with the property IRBs actually care about: **provable consent lifecycle** — grant, scope, revocation all on-chain + the append-only `consent_event_log` receipt timeline (grant→revoke→regrant = 3 preserved rows), plus the GDPR Art-17 erasure path with `post_erasure_recompute` audit trail (WIF-024 closed).
- **Proof:** identical WMP stack; the differentiator is the consent-provenance documentation bundle.
- **Consumer:** academic HCI / motor-control / esports-science labs (ACADEMIC buyer category, FROZEN enum).
- **IoTeX carrier:** ConsentManifestRegistry + consent receipts; WMP verifier for the data legs.
- **Buildable:** **NOW (doc + packaging)** — an "IRB companion" document over UC-1's pipeline. Gate: WMP Phase-2 (same as UC-1).
- **Ceiling:** we supply consent *evidence*, not IRB approval; "cryptographic consent" ≠ legal erasure of every offline copy (DePIN §5.2-5.3 caveat carries verbatim).

### UC-10 · Tournament integrity reports (aggregate organizer analytics) — **BUILT 2026-07-16 (structure; a pilot fills it)** (`l9_presence/integrity_report.py` — REFERENCE-AND-BIND rollup over match certificates + fail-closed re-derivation verifier; ceilings ride verbatim; 8 tests)
- **Produces:** per-event rollups of the pilot's per-match artifacts — N matches certified, verdict distribution, re-check pass rate, dispute outcomes — the organizer's post-event "integrity report."
- **Proof:** REFERENCE-AND-BIND rollup over match certificates (`scripts/match_certificate.py` artifacts); each row re-derivable from the cited certs.
- **Consumer:** the organizer (event marketing + governance) and their sponsors.
- **IoTeX carrier:** none new — certificates already carry beacon/chain references.
- **Buildable:** **NOW (code-only)** — a rollup script in the pilot ops lane. Gate: a real pilot producing ≥N certs.
- **Ceiling:** describes certificate outcomes only; the four pilot ceilings ride along verbatim (advisory, never-ban, etc.).

### UC-11 · Per-device production attribution via ioID TBAs (fleet economics, pre-token)
- **Produces:** each registered controller's DID accrues an auditable production ledger — which bundles/certificates reference `did:io:{device_id}` — device-level supply *accounting* (who produced what), the precondition for any future compensation design.
- **Proof:** DID references in bundles (D-IOID-CER-2's honest-ABSENT rule inverted: once registered, bundles carry the join) + the TBA as the device's on-chain anchor point.
- **Consumer:** internal economics + future marketplace settlement design; gamers (their device's provable output).
- **IoTeX carrier:** ioID + TBA (`ioID.wallet(tokenId)`).
- **Buildable:** gated on **D-IOID-CER-5 wire-up** (the placeholder-readback build) + registration ceremony.
- **Ceiling:** **accounting only — no rewards, no payments, no token language** (TGE frozen; the TBA holds references, never funds, until that gate formally clears).

### UC-12 · Outcome-annotated planner demos — **R-WMP5-HOLD-gated (reference only)**
- The flagship `(action + sparse outcome labels)` product is designed decision-first in `docs/wmp5-outcome-annotation-scope-ruling-2026-07-11.md` and **ruled HOLD 2026-07-11**. It enters this portfolio only if the operator re-rules IN against the T1–T6 test after the card-clean event channel is proven live. No design work here by rail.

---

## Buildable-NOW shortlist (after cycle 2)

| Rank | Item | Cost | Why |
|---|---|---|---|
| 1 | **UC-4 play-résumé assembler** | code-only | Proven certificate pattern; visceral demo; zero spend |
| 2 | **UC-2 skill-strata harness** | code-only | Turns SKILL into product structure from existing logs |
| 3 | **UC-10 integrity-report rollup** | code-only | Completes the pilot story; needs a real pilot to fill |
| 4 | **UC-8 fleet-telemetry aggregator** | code-only | Hardware-partner audience already engaged (Qorvo) |
| 5 | **UC-1 WMP Phase-2 promote** | ~0.5 IOTX | The base product; operator deploy choice |
| 6 | **UC-5 W3bstream analytics fns** | code-only (wasm) | Verifiable-compute pillar |
| 7 | **UC-3 buyer prover** | code-only | Closes Arc 2 |

## Cycle 3 — 2026-07-11 — Final lens (cross-DePIN) + last sweep + SATURATION CALL

### UC-13 · Cross-DePIN context fusion (partner-gated, thesis-grade — stated honestly)
- **Produces:** consented action corpora enriched with a SECOND DePIN network's context stream (e.g., wearable exertion, environmental telemetry) — `(verified human action, verified physical context)` pairs.
- **Proof:** the rails that make it *possible* are the shared IoTeX primitives — ioID as the common identity layer across device classes, W3bstream as the common validation rail, per-source consent. Nothing in-repo implements a partner stream; this entry exists to mark the shape, not claim readiness.
- **Consumer:** embodied-AI research (context-conditioned demonstrations).
- **IoTeX carrier:** ioID (cross-network DID joins) + W3bstream.
- **Buildable:** **GATED — external partner DePIN** + a per-stream consent architecture design. Thesis-grade until a partner exists; the honest analog of the HWFL-1 "narrative intel is not the selection" rule.
- **Ceiling:** never claimed in any pilot/marketing material until a partner integration is live.

### UC-14 · Commissioned certified playtesting (service model, not corpus sale)
- **Produces:** targeted, NDA-compatible play sessions on a studio's build, with the full provenance stack attached — the studio gets *certified-human* playtest input data instead of "we think these testers were real."
- **Proof:** identical per-session stack (PoAC → post-φ → VHR → PoSR → consent); the difference is the engagement shape — commissioned production rather than open-corpus sale, so consent scopes to one buyer.
- **Consumer:** studios pre-release (GAME_DEV category, FROZEN enum) — playtest fraud/inattention is a real QA cost.
- **IoTeX carrier:** consent manifest (per-buyer scoping via buyer-category bools) + WMP verifier as the deliverable's re-check.
- **Buildable:** **NOW at N=1 scale** (the rig is the service); gate for scale = population breadth (BCC lever, UC-6).
- **Ceiling:** `developer_self` scale honesty — one-rig capacity until breadth exists; no QA-outcome guarantees.

### UC-15 · Self-analytics — the gamer consuming their own verified data (demand-side seed) — **BUILT 2026-07-16** (`bridge/vapi_bridge/wmp/self_analytics.py` — pure clean-streak/cadence/authored-progression aggregator + read-only Store adapter over public getters; self-view ceiling rails baked in + guarded; 10 tests; poep/chain untouched. **Endpoint wired same day:** read-only `GET /player/self-analytics` in `operator_api/_app.py`, read-key auth, `asyncio.to_thread` per event-loop discipline; 3 endpoint tests)
- **Produces:** the producing gamer's own dashboard over their verified history — clean-streak trends, authored-kill progression, session cadence — the *self-consumption* loop that makes the data economy sticky before any external buyer exists.
- **Proof:** none needed beyond what exists — it's the gamer's own data, zero consent friction; rendered from `ruling_validation_log`, KAS records, grind analytics (the `vapi_grind_analytics` surface + GamerView frontend already exist).
- **Consumer:** the gamer (retention/engagement driver; the demand-side seed of the flywheel).
- **IoTeX carrier:** none required (local-first); optional DID join later.
- **Buildable:** **NOW (code-only, frontend + existing endpoints)**.
- **Ceiling:** self-view only; comparisons across players re-enter the population gate — not before that science.

### Final sweep — candidates evaluated and folded (not new UCs)
- *Esports insurance/underwriting* → consumer variant of UC-10 certificates, not a product class.
- *Accessibility/motor-diversity research* → UC-9 sub-case (same IRB-grade packaging).
- *Coaching marketplaces* → UC-15 + UC-4 composition; nothing new attaches proof-wise.
- *Data DAOs / collective bargaining for gamer data* → governance-shaped, touches token-adjacent rails → CLOSED-BY-RAIL with the financial lens until TGE gate clears.

## SATURATION DECLARED — 2026-07-11, cycle 3
Three cycles, 15 entries, two lenses closed-by-rail (financial/derivative; data-DAO governance). Cycle-3
additions were one honest partner-gated shape + two engagement-shape variants — the marginal-novelty curve
has flattened: further candidates reduce to consumer variants of existing entries or rail-blocked shapes.
**The loop stops here per its own discipline** (pending wakeup will confirm-and-not-reschedule).

## FINAL buildable-NOW shortlist (the portfolio's output)

| Rank | Item | Cost | The one-line case |
|---|---|---|---|
| 1 | **UC-4 play-résumé assembler** | code-only | **BUILT 2026-07-11** (`8f12d1d5`) |
| 2 | **UC-2 skill-strata harness** | code-only | **BUILT 2026-07-11** (`d8bf2fe5`) |
| 3 | **UC-15 self-analytics view** | code-only | **BUILT 2026-07-16** (module + `GET /player/self-analytics`) |
| 4 | **UC-10 integrity-report rollup** | code-only | **BUILT 2026-07-16 (structure)** — a real pilot fills it |
| 5 | **UC-8 fleet-telemetry aggregator** | code-only | **BUILT 2026-07-16** (floor-protected model buckets) |
| 6 | **UC-1 WMP Phase-2 promote** | ~0.5 IOTX | **LIVE 2026-07-11** (first real bundle VERIFIED) |
| 7 | **UC-5 W3bstream analytics fns** | code-only (wasm) | REMAINING — its own Rust/wasm arc |
| 8 | **UC-3 buyer prover** | code-only | REMAINING — its own ZK-prover arc (verifier live, prover absent) |

**Portfolio read:** the coherent picture is a three-ring economy — (inner) the gamer consumes their own
verified output (UC-15/4), (middle) skill-structured corpora + services sell to labs/studios/organizers
(UC-1/2/3/9/10/14), (outer) the network itself produces data (fleet/federation/flywheel, UC-6/7/8/11) —
every ring provenance-first, consent-sovereign, and pre-token by rail. The controller is the mint;
skill is the commodity; proofs are the packaging.

---

*Loop discipline: every future cycle appends a dated section + updates the shortlist + the saturation tracker; entries are audited claim⊆reality against the repo before landing; staged only — operator commits.*
