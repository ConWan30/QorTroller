# A2A-CDM · Round 04 · grok — EXPAND

**Role:** Expander (precision from grounding).  
**Builds on:** Round 02 expand + Round 03 ground (7 BUILDABLE-NOW confirmed; four gates sharpened; D-CDM-1 pending).  
**Rails held:** separation law · provenance ≠ truth · ideation only · honest maturity tags · TGE-freeze economics explicit · CONSENT-v1 enum FROZEN (design-ahead only for v2).

---

## proposals

### Q1-P1: ModuleHello v0 — single envelope, open capability bits  
[maturity: BUILDABLE-NOW]

- **claim:** One pre-session message `qortroller-module-hello-v0` carries: `schema`, `session_id_hint` (optional empty until mint), `module_role` enum, `capability_bits` (uint64 bitmask with reserved high bits), `identity` object `{ scheme: "device_id_sha256" | "did:io" | "none", value: hex|did|"" }`, `plane` ∈ {ASSERTION, OBSERVATION, MEANING, TIME, AGGREGATOR}, `proto_min`/`proto_max` (semver-ish ints), `nonce`, `ts_ns`, optional `sig` (empty pre-keys).
- **rationale:** One schema covers venue / edge / BT / spectator / TO-clock without per-class structs; new modules only set new capability bits or plane — no v2 for “new device type.”
- **why-novel:** **Identity dual-stack in one field** (device_id hash today, DID later) + **bitmask extensibility** so the bus never forks a schema per module class.

### Q1-P2: Versioning discipline — additive bits, never reorder roles  
[maturity: BUILDABLE-NOW]

- **claim:** Versioning rule: (1) `schema` string is the only hard break (`…-v0` → `…-v1` only if a field meaning flips); (2) `capability_bits` is **append-only by bit index** (document registry; unknown bits = ignore, never reject); (3) `module_role` string set is **append-only** (unknown role → treat as AGGREGATOR or reject with `ROLE_UNKNOWN` — pick one policy and freeze); (4) receivers MUST ignore unknown JSON keys (forward-compat).
- **rationale:** Stops “v2 per module” thrash; matches FROZEN-enum lesson without freezing the hello schema as a cryptographic domain tag yet.
- **why-novel:** Explicit **bit-index registry** as the product surface, not ad-hoc JSON shapes.

### Q1-P3: Capability bitmap sketch (v0 assigned + reserved)  
[maturity: BUILDABLE-NOW]

- **claim:** Assign low bits now, reserve high:  
  `0 CAP_POAC_ASSERT` · `1 CAP_HUMANITY_CLAIM` (ASSERTION-only legal) · `2 CAP_SCREEN_COMMIT` · `3 CAP_EVENTS_ROOT` · `4 CAP_DA_BULK` · `5 CAP_BT_RF` · `6 CAP_OPTICAL_SCENE` · `7 CAP_VENUE_MULTI_SEAT` · `8 CAP_EDGE_AGG` · `9 CAP_TO_CLOCK` · `10 CAP_W3S_VALIDATE` · `11–31 reserved module` · `32–63 reserved protocol`. Bus **must reject** `CAP_HUMANITY_CLAIM` if `plane != ASSERTION` (separation at hello).
- **rationale:** Encodes separation law in discovery, before any session seal.
- **why-novel:** Capability firewall **at handshake**, not only at tri-plane verify.

### Q1-P4: Two-phase bind — Hello then SessionBind  
[maturity: BUILDABLE-NOW]

- **claim:** Wire is two messages: **Hello** (module advertises) → bus mints/collects `session_id` → **SessionBind** `{ session_id, module_hello_hash, identity, plane }` so late joiners (venue rack, spectator) attach without a new schema.
- **rationale:** Covers modules that appear mid-bracket; discovery ≠ session start.
- **why-novel:** **Join-as-you-arrive** without module-specific protocols.

---

### Q2-P1: Minimal complete CONSENT-v2 category set (design-ahead)  
[maturity: GATED:CONSENT-v2-ceremony]

- **claim:** Propose v2 **append-only after v1’s four positions** (never reorder 0–3):  
  | idx | name | covers |  
  |-----|------|--------|  
  | 0–3 | *(unchanged v1)* | tournament / research / mfg / marketplace |  
  | **4** | `OBSERVATION_CAPTURE` | card/HDMI/retina capture provenance products |  
  | **5** | `VENUE_OBSERVATION` | multi-seat / venue-operated observation catalogs |  
  | **6** | `SPECTATOR_OPTICAL` | room/phone scene-hash co-witness (still privacy-legal gated to use) |  
  | **7** | `WORLD_MODEL_EXPORT` | WMP-class action demos (today’s greenfield registry can later merge or dual-key) |  
  | **8** | `DATA_SKU_JOINED` | right to sell **joined** action+observation packs (not either alone) |  
  Completeness argument: every Round-02 module maps to **capture locus** (who held the sensor) × **export class** (what leaves the rig); 4–8 cover locus (player card / venue / spectator) + export (observation / WM / joined). New hardware usually reuses a locus; new products usually reuses an export class.
- **rationale:** One ceremony covers mesh modules + dual markets without a six-month v3.
- **why-novel:** Categories designed as **locus × export**, not “one flag per feature request.”

### Q2-P2: Non-goals in v2 (prevent category spam)  
[maturity: GATED:CONSENT-v2-ceremony]

- **claim:** Do **not** add: per-game categories, per-TO categories, “AI training vs research” split (use RESEARCH + policy text), or “humanity attestation” (not a consent category — it’s assertion plane). Mic/speech stays **out** (DROPPED sensor path).
- **rationale:** Completeness by exclusion; stops enum bloat that forces v3.
- **why-novel:** **Explicit refuse list** as part of the design-ahead package.

### Q2-P3: Dual-key transition — v1 bitmask still valid  
[maturity: GATED:CONSENT-v2-ceremony]

- **claim:** v2 domain tag `VAPI-CONSENT-v2` with wider bitmask (e.g. u32); v1 hashes remain valid forever; consumers accept either tag; no silent “v1 marketplace implies observation.”
- **rationale:** Respects FROZEN v1 surface; no position insert into 0–3.
- **why-novel:** **Parallel domain tags** instead of destructive enum insert.

### Q2-P4: Default grants matrix for Standard tier (documentation only)  
[maturity: BUILDABLE-NOW]

- **claim:** Product default **recommendations** (not on-chain): tournament play → v1 `TOURNAMENT_GATE`; shipping observation SKU → requires v2 `OBSERVATION_CAPTURE` when ceremony exists; until then observation stays local/advisory with **no marketplace claim**.
- **rationale:** Lets ops talk honestly under TGE/consent freeze.
- **why-novel:** Separates **UX defaults** from **cryptographic categories**.

---

### Q3-P1: Venue oracle — token-free variant  
[maturity: BUILDABLE-NOW]

- **claim:** Venue charges **fiat (or stable invoice) fee-for-attestation**: pay for N observation certificates + verify support; **no stake, no slash, no token**. Reputation = public verify pass-rate + uptime logs (off-chain or hash-anchored free).
- **what breaks without token:** cryptoeconomic slash, permissionless bonding, automated undercollateral penalties, transferable stake reputation.
- **what survives:** fee-for-service, contract law / ToS, exclusion from next event, public “this venue’s certs re-verify” scoreboard, gamer-owned data still gamer-keyed.
- **rationale:** Q1-P3 venue oracle is a **services business** first.
- **why-novel:** Names “DePIN now” as **verifiable services**, not “wait for MachineFi rewards.”

### Q3-P2: Venue mesh (Q5-P1) — token-free variant  
[maturity: BUILDABLE-NOW]

- **claim:** Smallest mesh = **shared catalog + mutual verification credits**: venues prepaid **verification credits** (API keys / signed vouchers, not tokens) redeemable for cross-seat re-verify compute; catalog is session_id-indexed hashes only.
- **what breaks:** trustless cross-venue slash, global staking pool, anonymous node entry.
- **what survives:** bilateral agreements, shared verify scripts, common schema, reputation of operators, gamer consent still required for any data leave.
- **rationale:** Network effect without TGE.
- **why-novel:** **Credits as ops accounting**, not a blockchain asset.

### Q3-P3: Dual markets (Q5-P3) — token-free variant  
[maturity: GATED:partner|consent-productization]

- **claim:** List action-provenance and observation-provenance as **two fiat SKUs** (or free research download + paid support); joined pack = third SKU only when both consents exist (v2 later).
- **what breaks:** on-chain settlement in protocol utility units, burn/mint, automated royalty splits in token.
- **what survives:** gamer-sovereign grant/revoke (testnet + ledger), category gates, Curator packaging abort on consent fail, buyer pays fiat off-chain, proof still zero-trust re-verifiable.
- **rationale:** Marketplace contracts can sit idle; **utility is verify + consent**, not the coin.
- **why-novel:** Dual SKU taxonomy works **before** MachineFi liquidity.

### Q3-P4: What must stay frozen until TGE (do not fake)  
[maturity: GATED:TGE]

- **claim:** Do not ship pretend-stake, points-as-token, or “soulbound mining rewards” that imply transferrable economic security; reputation-only is honest; stake-slash designs remain **design-ahead docs only**.
- **rationale:** Grounder gate: staking/slashing/bonds = GATED:TGE.
- **why-novel:** Anti-pattern list protects the loop from crypto cosplay.

---

### Q4-P1: Terminal fail-closed (CONTENT_FORK → UNVERIFIABLE) — consumer argument  
[maturity: BUILDABLE-NOW]

- **claim (side A):** On `poac_chain_root` mismatch across planes, overall **UNVERIFIABLE** / CONTENT_FORK — no “attested” path for the joined object.
- **TO procedure (a):** Match cannot use the **joined** certificate for soft-signal; may still use controller-only ASSERTION path if product allows **plane-split** results (humanity from controller, observation discarded). Forces a human look when planes disagree.
- **Buyer procedure (b):** Auto-reject joined SKU; no silent purchase of contradicted packs.
- **false-terminal cost:** A bug or race in root plumbing kills a **legitimate** session’s joined cert — TO may over-DQ soft signals or lose trust if false-terminals are frequent.
- **why-novel for the debate:** Treats contradiction as **unsafe to market**, not “mostly fine.”

### Q4-P2: Honest-degrade (shipped) — consumer argument  
[maturity: BUILDABLE-NOW]

- **claim (side B):** Keep meaning join **REFERENCE_ATTESTED** when roots mismatch; verification **passes** with a **surfaced contradiction flag** (not silent).
- **TO procedure (a):** Soft-signal UI shows “join degraded / root mismatch” — referee **must** read the flag; risk is ignoring the flag under time pressure (**false-comfort**).
- **Buyer procedure (b):** Bundle may still verify overall if checks are plane-local; buyer who only looks at green overall **misses** the fork — worse for corpus integrity.
- **false-comfort cost:** Contradicted multi-plane story still looks “attested” in skim mode — poison for AI-lab buyers and dispute packets.
- **why-novel for the debate:** Names the failure as **UI/skim liability**, not crypto failure.

### Q4-P3: Recommendation (input to operator, not a decision)  
[maturity: BUILDABLE-NOW]

- **claim / recommend:** **Split the product surface, not the crypto only:**  
  - **Joined object** (tri-plane / PORT-CERT multi-surface / “session certificate full”): **terminal fail-closed** on content-root fork (Q4-P1).  
  - **Plane-local objects** (controller-only humanity, observation-only provenance): still verifiable independently.  
  - Never leave overall green on a **joined** claim when roots fork (fixes false-comfort for buyers).  
  - Mitigate false-terminal with: root plumbing tests, soak on dual-connection, and clear TO copy: “joined cert failed ≠ auto-ban; open controller-only advisory if needed.”
- **rationale:** TO worst case is false-terminal on joined only (recover via plane-split); buyer worst case is false-comfort (harder to undo once trained on). Prefer protecting buyers + dispute packets; give TOs an explicit plane-split escape.
- **why-novel:** **Fail-closed joined + fail-open plane-local** — both sides’ procedures get a clean handle. **Operator still decides D-CDM-1.**

### Q4-P4: Consumer-facing two-bit result (ties Round 03 Q4-P2)  
[maturity: BUILDABLE-NOW]

- **claim:** Regardless of D-CDM-1, every consumer UI/API returns at least `{ humanity_plane, observation_plane, join_status }` where `join_status` ∈ {SYNCHRONIZED, PARTIAL, CONTENT_FORK, UNVERIFIABLE} — so neither TO nor buyer has a single boolean to misuse.
- **rationale:** Makes false-comfort structurally harder.
- **why-novel:** Productizes the two-bit / multi-status model into the D-CDM-1 resolution path.

---

### Q5-P1: Tournament use of the provenance DAG  
[maturity: BUILDABLE-NOW]

- **claim:** Longitudinal sealed history enables: (1) **same-device continuity** across a weekend (device_id hash join), (2) dispute packets that cite **prior clean sessions** as context (not identity of which human), (3) TO audit “this Edge produced N sealed sessions this event” without trusting the player’s word.
- **rationale:** Single-session cert cannot show continuity or pattern of seals.
- **why-novel:** Tournament value is **continuity of agency hardware**, not a player ELO.

### Q5-P2: Sponsor / brand use  
[maturity: BUILDABLE-NOW]

- **claim:** Sponsors get a **verifiable campaign trail**: “activations were sealed under consent category X across dates” — re-verifiable without the brand trusting the agency’s spreadsheet.
- **rationale:** Single session is an anecdote; a DAG is a trail.
- **why-novel:** Sponsorship ROI as **provenance trail**, not impression counts alone.

### Q5-P3: AI-lab / world-model buyer use  
[maturity: BUILDABLE-NOW]

- **claim:** Labs get **longitudinal action-provenance series** (and later observation series) with consent history — enables non-i.i.d. demos, session-order integrity, and revoke-aware corpus cuts that one-off bundles cannot express.
- **rationale:** WMP + consent chain become a **time-indexed dataset**, not a bag of files.
- **why-novel:** Dataset product = **DAG + consent metabolism**, not raw zip.

### Q5-P4: Honest ceiling at N=1 / developer_self  
[maturity: BUILDABLE-NOW]

- **claim:** At N=1 player / developer_self the DAG **cannot** claim: population statistics, cross-player separability, field FAR, “any human,” marketplace liquidity, or that device_id continuity = **which enrolled person** (identity). It **can** claim: this device_id’s sealed session list re-verifies; consent state was X at export; join keys are consistent.
- **rationale:** Same ceiling as presence/WMP science — longitudinal ≠ broad.
- **why-novel:** Product ceiling written **before** sales language exists.

### Q5-P5: Smallest shippable DAG product  
[maturity: BUILDABLE-NOW]

- **claim:** v0 product = offline folder or index JSON: `{ device_id, sessions: [{session_id, artifact_paths, content_hashes}] }` + script `verify_provenance_dag.py` that re-runs per-artifact verifiers and checks device_id stability — no chain, no token, no ioID required.
- **rationale:** Matches grounded join key (device_id hash); desk-buildable.
- **why-novel:** “Sealed history” as a **verify script + index**, not a portal fantasy.

---

## self-check

| Rail | Status |
|------|--------|
| Separation law | Hello rejects humanity capability on non-ASSERTION; consent v2 has no “video humanity” category |
| Provenance ≠ truth | Q4 multi-status; Q5 ceilings; observation categories ≠ truth claims |
| Ideation only | No spend/deploy/TGE; v2 consent design-ahead only; stake stays GATED:TGE |
| Maturity tags | On every proposal |
| ≥3 per Q | Q1:4 · Q2:4 · Q3:4 · Q4:4 · Q5:5 |
| Grounder gates honored | TGE / CONSENT-v2 / privacy-legal (spectator category design only) / live W3bstream not claimed BUILDABLE as broker |

## optional handoff notes for Grounder / operator

- **D-CDM-1 input:** prefer **fail-closed on joined objects** + **plane-local still verifiable** (Q4-P3); multi-status API (Q4-P4).  
- **Fastest desk builds:** Q1-P1/P2/P3 hello schema stub · Q5-P5 DAG index script · Q3-P1 venue fiat fee narrative.  
- **Do not build yet:** CONSENT-v2 ceremony, spectator optical in production, any stake/slash.

---

*A2A-CDM Round 04 EXPAND — grok — 2026-07-12. For Claude Grounder; operator arbitrates D-CDM-1.*
