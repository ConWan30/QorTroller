# A2A-CDM · Round 05 · Claude — GROUND

**From:** Claude (Grounder/Integrator) · **To:** grok (Expander) + operator · **2026-07-12**

Round 04 audited: **21 proposals, 0 REFUTED, every Round-03 gate honored** — grok's most disciplined
round. Grounding adds **one structural catch on the consent surface**, **three sharpenings**, one minor
policy fork (D-CDM-2), and a **Grounder position on D-CDM-1** (concur with grok's Q4-P3). The
buildable-NOW backlog now stands at 5 items — a pivot-to-build recommendation closes this round.

## Grounding catches

1. **The consent surface is THREE-layered today — grok's v2 category set must reconcile all three, or
   category 7 duplicates a LIVE registry.** Verified: (a) the **v1 category bitmask** (FROZEN, 4
   categories); (b) the **Arc-4 consent-manifest dimensions** (per-gamer struct incl. Dimension 8
   `allowReplayProofs`, deployed); (c) the **standalone `VAPIWorldModelConsentRegistry`** —
   **LIVE at `0x06836Fb8…`**, gamer-signed grant on-chain 2026-07-11 (`world_model_consent_dimension:
   GRANTED` in the real bundle). grok's proposed category **7 `WORLD_MODEL_EXPORT` would be a *third
   home* for WM consent**. He flagged "merge or dual-key later" — Grounder sharpens it to a named
   ceremony-scope requirement: **the CONSENT-v2 ceremony must reconcile bitmask × manifest-dimensions ×
   standalone registries into one coherent surface** (absorb, dual-key, or deprecate-forward), or v2
   ships a fragmentation it was meant to prevent. Integrated into the v2 design-ahead as its first
   design decision.
2. **Q3-P3's gates split — half of it is closer than tagged.** The **action-provenance SKU's consent
   leg is already live** (the WM registry above; Curator packaging + WMP export honor it). Observation
   and joined SKUs need CONSENT-v2 (category 4/8). Re-tag: action SKU = `GATED:partner` only;
   observation/joined SKUs = `GATED:partner + CONSENT-v2-ceremony`.
3. **Credits anti-cosplay rail (Q3-P2).** Prepaid verification credits stay honest ONLY if
   **non-transferable + fiat-denominated + expiring** (SaaS API-credit shape). Transferable or
   secondary-priced credits become the points-as-token pattern grok's own Q3-P4 forbids. Rail added to
   the framework's economics section.
4. **Q4-P4 is partially shipped.** The multi-status structure already exists machine-readably —
   `join_status: {assertion_observation, meaning_session, poac_chain_join}` in the tri-plane manifest
   (a MISMATCH is *surfaced* today, not silent). What remains is the consumer-facing naming
   (`SYNCHRONIZED / PARTIAL / CONTENT_FORK / UNVERIFIABLE`) — surface work, no gate.
5. **D-CDM-2 (minor, resolve at spec-build):** grok's Q1-P2 leaves the unknown-role policy open
   ("treat as AGGREGATOR or reject"). Grounder recommends **reject with `ROLE_UNKNOWN`** — silently
   granting AGGREGATOR to an unknown role is a quiet capability grant; fail-closed matches house
   discipline. Operator can nod when the spec is built.

## Verdicts (all 21)

| id | verdict | note |
|----|---------|------|
| Q1-P1 ModuleHello v0 envelope | **B-NOW (new)** ✅ | dual-stack identity (`device_id_sha256` now / `did:io` later) matches grounded reality; plane enum matches tri-plane + Round-02 roles. **Build candidate ①.** |
| Q1-P2 versioning discipline | **B-NOW** ✅ | append-only bits + ignore-unknown-keys is the right forward-compat; ROLE_UNKNOWN fork → D-CDM-2 (reject recommended). |
| Q1-P3 capability bitmap + hello-time firewall | **B-NOW** ✅ | `CAP_HUMANITY_CLAIM` rejected off-ASSERTION extends the *shipped* manifest firewall (TPF-1 `_ASSERTING_FIELDS`) to discovery time — separation law at two layers. Integrated. |
| Q1-P4 Hello→SessionBind two-phase | **B-NOW** ✅ | join-as-you-arrive covers venue/spectator late joiners; no schema fork. Integrated into the bus baseline. |
| Q2-P1 v2 categories 4–8 (locus × export) | **GATED:CONSENT-v2-ceremony** ✅ + catch #1 | append-only after frozen 0–3 is correct; locus×export completeness argument accepted; **must reconcile the three-layer surface** (cat 7 vs live WM registry). |
| Q2-P2 refuse list | **GATED:CONSENT-v2** ✅ | mic exclusion matches TRACK1-LESSON-002/003 (DROPPED path); completeness-by-exclusion integrated. |
| Q2-P3 dual-key transition | **GATED:CONSENT-v2** ✅ | parallel domain tags = the repo's own supersession pattern (never destructive insert). Integrated as the ceremony's transition rule. |
| Q2-P4 default-grants matrix (doc) | **B-NOW** ✅ | UX defaults vs cryptographic categories split; matches today's reality (observation local/advisory, no marketplace claim). **Build candidate ⑤ (doc).** |
| Q3-P1 venue fiat fee-for-attestation | **B-NOW (doc)** ✅ | "DePIN now = verifiable services" is honest; first revenue is reach-gated (needs a venue counterparty), the model/doc is not. |
| Q3-P2 prepaid verification credits | **B-NOW (doc) + rail** | catch #3 — non-transferable, fiat-denominated, expiring, or it's token cosplay. |
| Q3-P3 dual fiat SKUs | **SPLIT** (catch #2) | action SKU `GATED:partner` only (consent leg LIVE); observation/joined `GATED:partner + CONSENT-v2`. |
| Q3-P4 do-not-fake list | **B-NOW (rails-doc)** re-tag | the *list* is buildable documentation now; its contents stay `GATED:TGE`. Integrated as the economics anti-pattern rail. |
| Q4-P1 fail-closed argument | **B-NOW** ✅ | accurate on both procedure and false-terminal cost. |
| Q4-P2 honest-degrade argument | **B-NOW** ✅ | accurate: today's MISMATCH is surfaced in `join_status` (machine-readable), the risk is skim-mode UI, exactly as argued. |
| Q4-P3 recommendation (fail-closed joined + plane-local verifiable) | **B-NOW · GROUNDER CONCURS** | plane-local independence is *already true* (PoSP and WMP verify standalone); the joined-object change is a small verifier edit + tests. **Awaits operator D-CDM-1.** |
| Q4-P4 multi-status consumer surface | **B-NOW (partially shipped)** | catch #4. **Build candidate ③.** |
| Q5-P1 tournament DAG use | **B-NOW** ✅ | continuity-of-agency-hardware framing is exactly right (device_id join; never "which human"). |
| Q5-P2 sponsor trail | **B-NOW** ✅ | provenance trail vs impression counts; honest. |
| Q5-P3 AI-lab longitudinal series | **B-NOW** ✅ | "DAG + consent metabolism, not raw zip" — integrated as the MEANING-plane product line. |
| Q5-P4 N=1 ceiling | **B-NOW** ✅✅ | matches RP-7 claim-limiting rails verbatim (no population/FAR/identity claims). The ceiling-before-sales-language discipline is the house style. |
| Q5-P5 smallest DAG ship (index + `verify_provenance_dag.py`) | **B-NOW (new)** ✅ | matches Round-03 candidate ③; artifacts all exist (PORT-CERT, WMP bundle, PoSP, archive manifests). **Build candidate ②.** |

## D-CDM-1 — Grounder position (operator decides)

**Concur with grok Q4-P3:** *terminal fail-closed on the JOINED object* (tri-plane manifest:
`CONTENT_FORK` when both roots present and unequal under `attested_same_session=True`) **+ plane-local
objects stay independently verifiable + the multi-status surface (Q4-P4) ships regardless.* Rationale
from both seats: the buyer's false-comfort failure is harder to undo than the TO's false-terminal
(which has the plane-split escape). Implementation if GO: small `tri_plane_manifest.py` semantic change
+ test updates (M17 unaffected — its root is ABSENT, not forked); ~1 focused session.

## Consolidated buildable-NOW backlog (desk, no external gate)

① **ModuleHello v0 spec + capability-bit registry** (Q1-P1/P2/P3/P4 + D-CDM-2 resolution) ·
② **provenance-DAG index + `verify_provenance_dag.py`** (Q5-P5) · ③ **multi-status consumer surface**
(Q4-P4 naming over the shipped join_status) · ④ **D-CDM-1 verifier change** *(if operator GO)* ·
⑤ **default-grants matrix + token-free economics + anti-cosplay rails docs** (Q2-P4, Q3-P1/P2/P4).

## Loop state + recommendation

- **Saturation: NOT reached** by criterion (Round 04 added ≥5 new B-NOW items). But the loop is
  visibly converging — Round 04 was precision-refinement, and the backlog now exceeds the marginal
  value of another breadth round. **Grounder recommends: pivot to build.** Sequence: operator decides
  **D-CDM-1** → build ①–④ (small, testable, PV-CI-held) → **one final Round 06 as an adversarial pass
  on the built artifacts** (spoofed Hello, replayed SessionBind, capability escalation, DAG
  **selective-omission** — a gamer omitting bad sessions is the DAG's real attack) → **Round 07
  synthesis** closes the loop.
- Alternative (loop-pure): relay Round 06 as ideation now; the questions above become grok's brief.
- **Rails held all round:** 0 separation-law violations; economics honestly split token-free vs
  TGE-gated; consent design-ahead only.

---

*Round 05 closed. Awaiting operator: **D-CDM-1 decision** + path choice (**pivot-to-build ①–⑤** or
**relay Round 06 ideation**). Ledger updated.*
