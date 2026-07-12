# A2A-CDM · Round 02 · grok — EXPAND

**Role:** Expander (novelty).  
**Subject:** Capture card + certified controller as DePIN modules on IoTeX — interoperable, in sync.  
**Rails held:** separation law · provenance-not-truth · ideation only (no TGE/spend/deploy/primitive edits) · self-tagged maturity.  
**Baseline:** controller ASSERTION (humanity, LIVE testnet) · capture OBSERVATION (card, BUILT advisory default-off) · bus = `session_id` · three sync axes (identity / time PoSR / content `poac_chain_root`) · fabric W3bstream · ioID · DA · Realms · MachineFi · tiers Minimal→Standard→Mesh.

---

## proposals

### Q1-P1: Dual-DID peer pair with asymmetric slash  
[maturity: GATED:ceremony|ioID-controller-live]

- **claim:** Capture witness is a **peer ioID device** with its own DID + TBA, co-signing session seals as OBSERVATION; only the controller DID may emit humanity-grade attestations; slash tables are **asymmetric** (witness slashed for provenance fraud / offline during committed window; controller slashed for humanity-claim fraud — never the reverse).
- **rationale:** Makes Standard tier a true two-module MachineFi pair without collapsing observation into humanity; maps cleanly to existing ioID path + `session_id` join.
- **why-novel:** Most DePIN meshes treat “device” as one economic class; **role-typed slash** (assertion-only vs observation-only) is the modular anti-cheat shape.

### Q1-P2: Capture as co-processor “sense organ” under controller agency  
[maturity: BUILDABLE-NOW]

- **claim:** Capture witness is a **co-processor** to the controller’s agency: no independent stake; it only mints observation commitments **bound to the controller’s session_id**; economic residual (if any) accrues to the **gamer wallet that controls the controller DID**, not a separate operator stake.
- **rationale:** Matches today’s dual-connection reality (Edge + card on one rig / pilot topology) and gamer-sovereignty rails; zero new stake market.
- **why-novel:** Flips “miner owns the sensor” → **gamer owns both lobes**; the card is peripheral compute, not a rival miner.

### Q1-P3: Independent venue oracle with bonded-only observation market  
[maturity: GATED:partner|venue-ops]

- **claim:** Capture is an **independent oracle** operated by venues/TO: stakes bond for uptime + hash-commitment availability; earns observation-attestation fees; **cannot** mint humanity; consumers buy “screen provenance” as a separate product from “isFullyEligible.”
- **rationale:** Separates physical presence at desk from venue integrity services; enables Standard tier without requiring every gamer to own a card.
- **why-novel:** Splits **player DePIN** (controller) from **venue DePIN** (capture rack) — two markets, one `session_id`.

### Q1-P4: Rotating witness lottery (session-ephemeral co-signers)  
[maturity: SPECULATIVE]

- **claim:** For each match, a W3bstream applet randomly selects **k** bonded capture nodes to co-commit screen roots; controller remains sole humanity claimer; slash if selected witness misses window.
- **rationale:** Network effect without permanent per-gamer hardware; still observation-only.
- **why-novel:** Anti-cheat as **committee of cameras**, not one trusted box — still not a truth oracle (replay still possible; cost rises with k).

---

### Q2-P1: session_id as sole bus; discovery via pre-session handshake  
[maturity: BUILDABLE-NOW]

- **claim:** Interoperability bus stays **session_id alone** (SHA-256 join key already live); modules **discover** each other via a local pre-session handshake that exchanges (module_role, device_did_or_null, capability_bitmap) and **commits** a tri-plane manifest under that session_id — no Realm required.
- **rationale:** Zero new chain surface; composes with PoSP/PORT-CERT/WMP as today.
- **why-novel:** Treats the join key as a **DePIN bus**, not mere metadata — discovery is explicit protocol, not ad-hoc wiring.

### Q2-P2: ioID group-binding as “session fleet”  
[maturity: GATED:ceremony|ioID-group-spec]

- **claim:** At session start, controller DID + witness DID(s) form an **ioID group / multi-controller binding** object (off-chain signed intent, on-chain optional hash); bus = group id derived from sorted DIDs + session_id; discovery = group membership check.
- **rationale:** Gives permanent identity mesh (interop vision “controller + witness DID mesh”) without Realms volume gate.
- **why-novel:** Session objects become **named fleets of devices**, portable across games.

### Q2-P3: W3bstream applet as session broker  
[maturity: GATED:ceremony|applet-extension]

- **claim:** A W3bstream Wasm applet is the **broker**: ingests module heartbeats + commitment digests keyed by session_id; validates ANCHOR_CADENCE / events_root / role tags; emits only “bus_coherent | bus_partial | bus_incoherent” — never a humanity verdict.
- **rationale:** Uses existing sandbox discipline (mechanical validation only; no biometric capture in applet).
- **why-novel:** The bus is **compute**, not storage — modules don’t need to trust each other’s hosts, only the applet’s rules.

### Q2-P4: Realm as per-title module fabric (gated)  
[maturity: GATED:Realms-volume]

- **claim:** When PoAC volume ≥ Realms threshold, a title-specific Realm hosts module registry + bus state machines; until then, Q2-P1/P3 on L1/testnet.
- **rationale:** Honest sequencing with Realms economics; avoids premature app-chain.
- **why-novel:** Realms as **module OS for one game’s DePIN**, not a generic L2 marketing claim.

---

### Q3-P1: Venue node (rack-mounted multi-seat capture)  
[maturity: GATED:hardware|partner]

- **claim:** A **venue node** module aggregates N HDMI captures under one venue ioID; per-seat observation roots still join **player session_id**s; venue never claims humanity for seats.
- **rationale:** Scales Standard tier to LANs/cafés; MachineFi fee to venue for observation uptime.
- **why-novel:** “Internet café as DePIN PoP” with seat-level session join.

### Q3-P2: Spectator-witness (phone / secondary camera, observation-only)  
[maturity: GATED:calibration|privacy]

- **claim:** Spectator devices publish **low-rate optical commitments** (scene hashes, not faces-by-default) joined by session_id as **tertiary observation**; cannot raise humanity score; optional consent category SPECTATOR_OPTICAL.
- **rationale:** Raises spoof cost (must fool desk card + room cameras); stays separation-law safe.
- **why-novel:** Turns the crowd into a **cheap multi-view provenance mesh** without making video the eligibility gate.

### Q3-P3: Edge aggregator (home hub / Pi)  
[maturity: GATED:hardware]

- **claim:** A home **edge aggregator** module co-signs “both lobes online + session_id stable” and holds DA-side bulk (crops, logs); chain only sees 32B commitments; never computes humanity.
- **rationale:** Matches pilot topology (card + Pi); Arc 7 sidecar pattern generalized to session bulk.
- **why-novel:** Explicit **DA home node** as a first-class DePIN module class.

### Q3-P4: Tournament clock / official time module  
[maturity: SPECULATIVE]

- **claim:** An independent **match clock module** emits only schedule + wall-clock anchors joined to session_id; used for PoSR cross-check, not humanity.
- **rationale:** Separates “when the TO says the match ran” from “when beacons fired.”
- **why-novel:** Time as a **module**, not only chain beacons — TO-grade sync without spoofable video truth.

### Q3-P5: BT LAN-tower presence module (Mesh tier)  
[maturity: GATED:calibration|hardware]

- **claim:** BT Classic witness module (L8 path) publishes RF-presence commitments on the same session_id bus; observation/presence co-signal only — never sole humanity gate.
- **rationale:** Already in Mesh tier inventory; separation law already stated in BT calibration anchor.
- **why-novel:** RF lobe as bus peer, not a siloed L8 experiment.

---

### Q4-P1: Partition → PARTIAL_SURFACES with sticky session_id  
[maturity: BUILDABLE-NOW]

- **claim:** Under network partition, modules **keep minting local seals** under the same session_id; federation verdict degrades to PARTIAL/UNVERIFIABLE (PoSP pattern); **never** invent cross-module content-sync; recovery is re-join + optional deferred attestation (offline reliability path).
- **rationale:** Already how PoSP / deferred KAS behave under missing surfaces.
- **why-novel:** Names partition as a **first-class sync mode**, not an error to hide.

### Q4-P2: Replayed feed → provenance holds, humanity unchanged  
[maturity: BUILDABLE-NOW]

- **claim:** If the card is pointed at a replay, observation commitments remain **valid provenance** (who/when/device captured); controller ASSERTION still decides humanity; **content-sync** may succeed (same poac chain) while **semantic gameplay authenticity** stays unclaimed — product surfaces “PROVENANCE_OK · TRUTH_UNASSERTED.”
- **rationale:** Hard rail 2 made operational as a sync-axis outcome, not a footnote.
- **why-novel:** Explicit **two-bit result** (provenance vs truth) under adversarial video — most systems collapse them.

### Q4-P3: Rogue module → role-firewall + majority-of-roles  
[maturity: GATED:ceremony]

- **claim:** Each module carries a **role tag** (ASSERTION | OBSERVATION | TIME | AGGREGATOR); bus rejects any OBSERVATION module publishing humanity fields; rogue/extra modules without role signature → UNVERIFIABLE join; optional **k-of-n observation** if Mesh has multiple witnesses.
- **rationale:** Enforces separation law at the bus, not in marketing copy.
- **why-novel:** **Capability firewall** as the sync defense, not trust-the-host.

### Q4-P4: Time-axis desync → recency class downgrade, not silent clock skew  
[maturity: BUILDABLE-NOW]

- **claim:** If PoSR open/close beacons missing or mismatched (UC-1-class deferral), modules stay identity-synced via session_id but **time-sync class** becomes TEMPORAL_ONLY / DEFERRED; consumers must not treat PARTIAL as SYNCHRONIZED.
- **rationale:** Mirrors WMP full-verify `--allow-deferred recency` honesty.
- **why-novel:** Treats “honest missing beacon” as a **sync grade**, not a green check with fine print.

### Q4-P5: Content-sync fork (two poac_chain_roots) → hard UNVERIFIABLE  
[maturity: BUILDABLE-NOW]

- **claim:** If controller and witness disagree on `poac_chain_root` for the same session_id, bus emits **CONTENT_FORK** → overall UNVERIFIABLE; no automatic “prefer controller” for observation claims and no automatic “prefer video” for humanity.
- **rationale:** Content-sync axis already defined; make conflict terminal.
- **why-novel:** **Fail-closed fork** prevents raffling which plane “wins.”

---

### Q5-P1: Venue mesh liquidity (smallest real network effect)  
[maturity: GATED:partner|hardware]

- **claim:** **Smallest network-effect config:** ≥2 Standard pairs (controller+witness) under one venue node sharing a **venue observation catalog** (session_id-indexed commitments) + one public verify script — enables cross-seat audit and venue reputation that a single pair cannot.
- **rationale:** Demand-side utility without token: TOs buy mesh integrity, not a coin.
- **why-novel:** Network effect defined as **venue catalog composability**, not user-count vanity.

### Q5-P2: Cross-session provenance graph (player corpus DAG)  
[maturity: BUILDABLE-NOW]

- **claim:** Multiple sessions’ PORT-CERT / WMP / PoSP artifacts form a **gamer-sovereign provenance DAG** joined by device DID + consent; one pair cannot offer longitudinal “this corpus is the same agency’s sealed history.”
- **rationale:** Uses existing export/verify surfaces; consent revokes still apply.
- **why-novel:** Network effect as **time-depth of sealed sessions**, not only multi-device.

### Q5-P3: Data-liquidity layer (observation vs action markets)  
[maturity: GATED:partner|consent-productization]

- **claim:** Dual markets on MachineFi rails: **action-provenance bundles** (WMP, controller-rooted) and **observation-provenance seals** (card-rooted), sold only under gamer consent; pairs enable **joined SKUs** (“action+screen-provenance pack”) that single-module stacks cannot list honestly.
- **rationale:** Separation law becomes a **product taxonomy** (two SKUs, never one “truth pack”).
- **why-novel:** Liquidity from **modular data classes**, not a single blob marketplace.

### Q5-P4: Anti-farm mesh reputation (observation diversity score)  
[maturity: SPECULATIVE]

- **claim:** A network of pairs computes a public **observation-diversity score** (how many independent witness DIDs co-signed sessions) — raises cost of remote-farm single-card spoof without ever using video as humanity gate.
- **rationale:** Network-only metric; single pair always diversity=1.
- **why-novel:** Reputation from **witness plurality**, not aimbot detection claims.

### Q5-P5: Inter-venue federation via session_id + DA roots  
[maturity: GATED:partner|Realms-volume]

- **claim:** Venues federate observation catalogs by exchanging session_id + DA commitments; cross-venue disputes re-verify without trusting either TO’s host — requires multi-operator adoption.
- **rationale:** Extends zero-trust consumer verify to multi-venue.
- **why-novel:** Tournament circuits as **federated DePIN**, not one platform.

---

## self-check (Expander)

| Rail | Status |
|------|--------|
| Separation law | No proposal makes video/screen the humanity gate; roles split slash/markets |
| Provenance ≠ truth | Q4-P2, Q5-P3 explicit |
| Ideation only | No spend/deploy/TGE/token schedule |
| Maturity tags | Present on every proposal |
| ≥3 configs per Q | Q1:4 · Q2:4 · Q3:5 · Q4:5 · Q5:5 |

---

## suggested Grounder priorities (optional handoff)

If Round 3 must pick a thin slice: **Q1-P2 + Q2-P1 + Q4-P1/P2/P5** as BUILDABLE-NOW narrative; **Q1-P1 + Q2-P2** as ceremony-gated mesh; park **Q2-P4 / Q5-P5** on Realms volume.

---

*A2A-CDM Round 02 EXPAND — grok — 2026-07-12. For Claude Grounder integration; operator arbitrates.*
