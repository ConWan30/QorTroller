# QorTroller — DePIN Interoperability Vision (IoTeX full-stack positioning)

**Status:** VISION / SEQUENCING DOC (2026-07-11). Repo-grounded — every claim below was verified against
code, deployed addresses, or live external state during the 2026-07-11 research sweep (agent inventory of
8 IoTeX surfaces + WMP blueprint read + IIP-64 live check). Loop: this doc frames; grok designs the gated
items; Claude audits+builds; operator fires anything that spends or signs.
**Rails:** TGE frozen · advisory/testnet posture · gamer-sovereign consent (`msg.sender == gamer`) ·
post-φ action-only exports (the biometric moat NEVER exports) · WMP's own rule: registry deploys are
positioning-or-demand choices the operator makes explicitly.

---

## 1. The positioning (one sentence)

**QorTroller makes a consumer game controller a full IoTeX DePIN citizen — its own ioID identity and
token-bound wallet, its data flows validated by W3bstream, its humanity and session integrity proven in
ZK, its timeline anchored by temporal beacons, and its output sold or exported only by the gamer's own
on-chain signature — with the capture card (OA-RP-1, arriving) completing the loop by adding an attested
*outcome* channel to the attested *action* channel.**

---

## 2. Inventory — what exists TODAY (from the 2026-07-11 sweep)

| Surface | Status | Anchor |
|---|---|---|
| Consent manifest (Arc 4, 19-field, gamer-sovereign) | **LIVE** | `VAPIConsentManifestRegistry` `0x5F7c8068…`; first gamer-signed manifest written 2026-06-05 (`allowReplayProofs=true`) |
| Temporal beacons (Arc 6 PoSR) | **LIVE + keeper ACTIVE** | `VAPITemporalBeaconRegistry` `0x96244031…`; keeper set 2026-06-25, first anchor block 45008576; ~0.258 IOTX/day cadence |
| Replay-proof ZK (Arc 5 v1 + recency-bound v2) | **LIVE**, one **REAL** proof accepted on-chain | v2 `0xf4106736…`; M17 `ReplayProofVerified` block 45479067 |
| Device identity — manufacturer + gamer keys | **LIVE** | `VAPIManufacturerDeviceRegistry` `0x2e5B5FB1…` (birth certs, signingPath/proofTier FROZEN) + `VAPIPoEPRegistry` `0x4Dcfa11d…` (gamer-sovereign composite keys) |
| ioID registry | **LIVE** (contract) + **code-complete device path** | `VAPIioIDRegistry` `0xF7885B58…` (Phase 55); `bridge/vapi_bridge/controller_ioid_registration.py` — gamer-signed EIP-712 permit → `did:io:{device_id}` DID doc + TBA via `ioID.wallet(tokenId)`; DEVICE_ID_CANON_v1 = keccak256(65B P-256 pubkey) |
| W3bstream applet | **BUILT** (Rust wasm; validation-only sandbox) | `w3bstream/applet/src/lib.rs` — 64-block cadence (INV-W3S-001), pq_commitment format (INV-W3S-005), retina commitment (INV-W3S-006); `EvmLogPayload` **already carries `events_root`** |
| WMP lane (action-provenance export) | **code-complete, fixtures-only** | `wmp/bundle_assembler.py` + `wmp_export.py` + 5-check consumer verifier `sdk/wmp_verify.py`; `VAPIWorldModelConsentRegistry` (WMP-4) **undeployed** (~0.1–0.3 IOTX) |
| Marketplace + curator packaging | **LIVE contract; submission operator-fired** | `VAPIDataMarketplaceListings` `0x78Df84Cc…`; `curator_packaging_loop.py` (floors: ≥10 sessions, ≥72h cooling; FORBIDDEN_FIELDS frozen; buyer enum FROZEN INV-BUY-001) |
| Buyer-category ZK (Arc 2) | verifier **LIVE**, **prover ABSENT** | `VAPIBuyerCategoryVerifier` deployed; `zk_buyer_verifier.py` is read-only |
| PQ / IIP-64 | **BLOCKED-EXTERNAL** | IIP-64 PR #72 OPEN, dormant since 2026-05-23 (live-checked 2026-07-11); 0x0B precompile absent → Arc 7 sidecar-pointer stays the PQ posture |

### Three stale-blueprint facts that make WMP Phase-2 cheaper than written

The WMP blueprint (2026-06-05) predates the July arc. Its Phase-2 promote list is ~3/5 already built:
1. **"Keeper unset" is stale** — beacons anchor live since 06-25 → the RECENCY check can go live now.
2. **"Wire snarkjs" is done** — the PORT-CERT full-VERIFIED runner already runs real `groth16 verify`,
   and M17 is a real proof (not a fixture).
3. **The Poseidon helper exists** — `compute_inputs_replay_proof.js` (Arc 5) is the matrix↔root
   Phase-2 ingredient.

---

## 3. Doable NOW (ranked; costs honest)

| # | Move | IoTeX feature | Cost / gate |
|---|---|---|---|
| **1** | **Register the DualSense Edge as an ioID device** — code-complete gamer-signed EIP-712 → DID + token-bound account. *The controller literally gets its own decentralized identity and wallet.* | ioID | ~0.2–0.5 IOTX, one gamer-signed tx. The single most symbolic DePIN act available |
| **2** | **WMP Phase-2 promote → first REAL provenance bundle** — deploy WMP-4; Cockpit consent toggle; wire the 3 already-built legs; export one real-match bundle; a stranger runs `verify_action_provenance.py` → 5/5 | ZK + beacons + consent | ~0.3–0.6 IOTX total. Headline: first cryptographically-verifiable human action-demonstration corpus (humanity + recency + consent all on-chain-checkable) |
| **3** | **W3bstream validates KAS event roots** — `EvmLogPayload.events_root` already exists; extend applet validation to the kill-event roots → W3bstream becomes the off-chain compute rail for the authorship stack | W3bstream | Code-only, 0 IOTX |
| **4** | **First real marketplace listing** — consent live (`allowReplayProofs=true`), packaging loop built, M17 real proof exists; submission deliberately operator-fired | Marketplace | Operator decision + small gas; the pre-token demand-side utility demo |
| **5** | **Buyer-category prover** — close the Arc 2 loop (buyer proves category in ZK to access tier-gated listings) | ZK | Code build, 0 IOTX |

---

## 4. Novel ideas the capture card unlocks

**A. Outcome-annotated provenance bundles (WMP-5 candidate — flagship).** WMP v1 is action-channel-only
by design. The July arc built what the blueprint never anticipated: discrete, cryptographically-bound
**outcome events** — kills tied to trigger pulls (KAS/EVENT-BIND), match boundaries (LUMEN-2b),
session-joined + beacon-anchored. For world-model *planners*, `(action-trace + sparse outcome events)`
is demonstration data **with reward annotation** — exactly the scarcity the taxonomy names. The card's
clean 60fps feed makes the outcome channel reliable. ⚠️ **Gate: an explicit scope ruling** — kill events
are macro-public labels (present in every esports replay), *not* pixels/biometrics, but the
observation-channel prohibition must be formally distinguished and `scope_disclosure` extended. grok
design + operator ruling required; never a unilateral build.

**B. Controller + witness DID mesh.** Once the controller has an ioID, the witness box (card + Pi — the
pilot topology) becomes a second ioID device class: **two independent IoTeX identities co-signing the
same physical session**. Certificates stop saying "trust one machine" and start saying "two independent
identities agree." DePIN attestation-as-a-mesh; no other gaming project has this shape. Gated on the
witness hardware (post-card follow-on).

**C. The full-loop demo.** One real match, one artifact chain: controller (ioID DID) → 1000Hz PoAC →
post-φ matrix → real Groth16 VHR proof → beacon-anchored recency → gamer-signed consent → WMP bundle →
marketplace listing → a stranger verifies every link with public tools. Every IoTeX pillar exercised by
one Warzone match; assembleable within ~2 IOTX once the card lands.

---

## 5. Real-data WMP production pipeline (concrete, post-card)

```
match (card, 60fps direct HDMI)
  ├─ 1000Hz HID → PoAC records (228B, FROZEN)            [existing]
  ├─ post-φ sanitized matrix (FORBIDDEN_COLUMNS wiped)    [Arc 5, existing]
  ├─ real Groth16 VHR proof                               [proven — M17]
  ├─ PoSR open/close beacons                              [keeper LIVE]
  ├─ gamer consent (Arc 4 live + WMP-4 once deployed)     [1 deploy + 1 gamer tx]
  └─ (candidate WMP-5) KAS event roots as outcome labels  [gated on scope ruling]
        ↓
  bundle_assembler → wmp_export (real-export guard lifts w/ WMP-4)
        ↓
  consumer: verify_action_provenance.py → 5/5 VERIFIED (no trust in QorTroller required)
```

---

## 6. Honest gates (unchanged by this vision)

- **PQ on-chain**: blocked (IIP-64 dormant); Arc 7 sidecar-pointer remains correct.
- **Silicon Path B / per-PoAC silicon root**: hardware-gated (Arc 2/3+).
- **TGE**: frozen. Everything above is utility/provenance, deliberately pre-token.
- **Presence science** (PoEP N≥50, population, real-adversary FAR): demand-held per operator decision.
- **WMP-4 deploy**: cheap, but the blueprint's own rule says deploys are explicit operator choices
  (positioning vs demand-pulled) — never automatic.

## 7. Recommended sequencing

① Controller ioID registration (the thesis made literal) → ② WMP Phase-2 + first real bundle (the corpus
headline) → ③ full-loop demo doc → hold **A** for grok design + scope ruling; **B** until the witness
box exists; **4/5** behind operator/demand.

---

*DePIN interop vision v1 — 2026-07-11. Sources: agent sweep (8 surfaces, file:line-grounded),
`docs/world-model-provenance.md`, `contracts/deployed-addresses.json`, IIP-64 PR #72 live check.*
