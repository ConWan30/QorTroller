# ioID Controller Ceremony — Design Bars (Review Only)

**Status:** DESIGN / BARS (2026-07-11). Code is complete — **no rebuild**.  
**Source vision:** `docs/depin-interop-vision-2026-07-11.md` (commit `c6067a41`) move #1.  
**Code surface:** `bridge/vapi_bridge/controller_ioid_registration.py`  
**On-chain:** `VAPIioIDRegistry` LIVE `0xF7885B588718b891B2234477D031607da4a7ACfe` (Phase 55; confirm in `contracts/deployed-addresses.json`).  
**Rails:** gamer signs · bridge never owns TBA · testnet · no token · DEVICE_ID_CANON_v1 = keccak256(65B SEC1 P-256 pubkey).

---

## 0. What is already locked in code (do not re-litigate)

| Bar | Reality |
|-----|---------|
| **Signer** | Gamer wallet signs EIP-712 `Permit(owner, nonce)` — D-CONTROLLER-IOID-1 Option A |
| **Bridge role** | Read-only orchestrator: pin DID, assemble 8-param `register`, never holds gamer key as policy |
| **DID form** | `did:io:{device_id}` · `EcdsaSecp256r1VerificationKey2019` (P-256) · `controller: [gamer_address]` |
| **Device id** | `DEVICE_ID_CANON_v1` enforced via `verify_device_id_matches_pubkey` before DID build |
| **Optional fields already in API** | `birth_cert_cid` → `alsoKnownAs: ipfs://…` · `mfg_registry_tx` → `proof.type=MfgRegistryBinding` |
| **TBA** | Via `ioID.wallet(tokenId)` after register (agent path precedent) |
| **Silicon permit** | P-256 controller key ≠ secp256k1 permit — gamer wallet signs; Option C silicon-signed permit **blocked** (D-IOID-P256 / IIP-64 class) |

Review sets **ceremony bars** for the first live registration, not a redesign.

---

## 1. v1 DID document: carry NOW vs DEFER

Code already builds a minimal doc; optional hooks exist. Bars for the **first real registration**:

| Field / link | v1 NOW? | Why |
|--------------|---------|-----|
| `id` = `did:io:{device_id}` | **REQUIRED** | Identity string is the whole point |
| `controller` = gamer EOA | **REQUIRED** | Gamer sovereignty; matches permit owner |
| `verificationMethod` P-256 pubkey (canon-bound) | **REQUIRED** | Physical-key binding surface for the DID |
| Service stub (`QorTrollerControllerService`) | **NOW (honest)** | Keep generic; fix placeholder `serviceEndpoint` before external paste — no fake production URL |
| **Birth-cert IPFS CID** (`alsoKnownAs`) | **NOW if cert already pinned**; else **DEFER** | Strengthens “this DID = this manufactured key.” Do **not** invent a CID. If MFG birth cert exists only on-chain and not on IPFS, prefer on-chain binding over a fake CID |
| **MFG-registry binding** (`proof.tx` or equivalent) | **NOW if registerDevice tx exists for this Edge** | Binds DID → manufacturer birth registry (`VAPIManufacturerDeviceRegistry`). Strongest single external check for “not a random key.” Fail-closed for ceremony if device is already on-chain birth-registered: include it |
| **PoEP composite-key reference** | **DEFER (v1)** | PoEP is gamer-sovereign / presence-lane; different trust story. Mixing into DID v1 blurs “device identity” with “presence composite.” Add as optional `service` / `alsoKnownAs` only after a short schema note (separate decision), never required for ioID register success |
| Path A signingPath / proofTier | **DEFER** | On-chain via MFG views; consumer can query registry by device_id. DID bloat not needed for v1 |
| Session / WMP / KAS commitments | **NEVER in DID** | DIDs are long-lived identity; session artifacts are ephemeral — reference DID *from* bundles, not the reverse |

### Formal v1 minimum (ceremony checklist)

```text
PASS only if:
  - device_id == keccak256(65B SEC1 P-256 pubkey)
  - DID.controller includes gamer address that will sign permit
  - verificationMethod.publicKeyHex matches birth material
  - IF mfg birth already on-chain for this device_id → mfg_registry_tx present in DID
  - IF birth cert CID already exists → alsoKnownAs ipfs:// CID present
  - NO PoEP fields required
  - NO biometric / raw HID / L4 fields anywhere in DID
```

**Recommendation:** **MFG binding NOW when available; birth-cert CID NOW when already pinned; PoEP DEFER.** That maximizes first-ceremony credibility without inventing surfaces.

---

## 2. Run-order vs WMP-4 — should DID exist before first WMP bundle?

| Order | Pros | Cons |
|-------|------|------|
| **A. ioID first → WMP bundle** | Bundle can `reference` `did:io:…` + tokenId + TBA; full-loop demo story matches interop vision §4.C; consumer can join identity → action provenance | Requires one gamer-signed ioID tx before export |
| **B. WMP first → ioID later** | Faster to first real action-provenance bundle (WMP Phase-2) | Bundle has no device DID join key; “controller as DePIN citizen” headline deferred; retro-binding is awkward |
| **C. Parallel** | Max velocity | Two incomplete stories; no joint artifact |

### Bar (design ruling proposal)

**Prefer A for the flagship full-loop demo.**  
**Allow B only for fixture / pre-identity WMP Phase-2 dry runs** — those bundles MUST set an honest field such as:

```text
device_identity: ABSENT_IOID_NOT_YET_REGISTERED
```

and must **not** imply a DID.

**WMP-4 deploy is independent of ioID** (consent registry for world-model export). Sequencing:

```text
① Controller ioID registration (identity)
② WMP-4 deploy + gamer world-model consent (if not already)
③ First real WMP bundle WITH optional device_did reference
```

WMP-4 does not need DID to deploy. **DID should exist before any external claim that the bundle is “from this controller’s DePIN identity.”** Action-only fixture bundles may ship without DID.

**WMP-5 (outcome labels)** — if later permitted — same rule: reference DID + KAS commitments; never embed identity secrets in event roots.

---

## 3. Cost bars + triple-gate posture (one gamer-signed tx)

### 3.1 Cost envelope (testnet, estimate-first)

| Item | Bar |
|------|-----|
| **Expected gas class** | ~0.2–0.5 IOTX (interop vision estimate — **re-measure with `estimate_gas` before send**) |
| **Hard cap (recommended)** | **0.75 IOTX** single-tx ceiling for v1 ceremony (above estimate × ~1.5–2 headroom) |
| **Wallet** | Gamer wallet funds the register (or explicit sponsor path documented); bridge wallet **not** silently subsidizing without operator note |
| **Pinata / IPFS pin** | Off-chain; separate from IOTX; fail-closed if pin fails (no register with empty URI) |

### 3.2 Triple-gate (house rules — apply before broadcast)

Mirror keeper / VHR / deploy posture:

| Gate | Requirement |
|------|-------------|
| **G1 Estimate-first** | `estimate_gas` (or equivalent) succeeds; log estimate; **no static gas that can OOG** |
| **G2 Cap** | `estimate * 1.25 ≤ hard_cap` (or operator-raised cap in writing); abort if not |
| **G3 Intent** | Explicit operator flag e.g. `IOID_CONTROLLER_REGISTER_CONFIRM=1` **and** gamer-signed permit present (not bridge-forged); `dry_run=True` default |
| **G4 (optional readback)** | Post-tx: parse tokenId · `ioID.wallet(tokenId)` non-zero · DID URI resolvable |

**Bridge never:** generates permit with its own key as gamer; overwrites on-chain gamer controller; auto-registers every connect.

**Skeleton honesty:** current `register_controller_ioid` still has dry-run / placeholder readbacks in the non-dry path comments — **live ceremony requires the agent-path-quality send + event parse wiring to be verified green once** before any external “registered live” claim. Bars above assume that wire-up is done under operator GO; design does not invent a new flow.

---

## 4. Claim ceiling for announcements

### 4.1 “First game controller with its own DID + wallet”

| Verdict | Reason |
|---------|--------|
| **Do not claim absolute “first” without a sourced competitive survey** | Web/market DID literature is broad; gaming + ioID + TBA is a **narrow niche**, but **firstness is a global claim** and fails the same bar as uncited competitive AC claims (reachability / source-check rule). |
| **OK after ceremony (sourceable, scoped)** | “We registered a DualSense Edge as an **ioID device** on **IoTeX testnet**, with DID `did:io:{device_id}`, gamer as controller, and a **token-bound account** via `ioID.wallet(tokenId)` — code path: `controller_ioid_registration.py`.” |
| **OK as thesis** | “Consumer game controllers as DePIN citizens (identity + TBA)” — **positioning**, not firstness. |
| **Not OK** | “First game controller DID ever” · “mainnet production identity product” · “token launch” · “bridge owns your controller wallet” · silicon-rooted permit (P-256) until that path exists |

### 4.2 Pre-announcement checklist

```text
[ ] Live tx on testnet 4690, explorer link
[ ] DID document CID resolvable; fields match ceremony checklist §1
[ ] device_id canon verified against pubkey
[ ] Gamer was signer (permit); bridge role disclosed
[ ] No "first" unless operator-approved competitive memo with sources
[ ] Testnet + no-token rails in the same paragraph as the claim
```

---

## 5. Operator decision table

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-IOID-CER-1** | v1 DID: MFG tx NOW if available; birth CID NOW if pinned; PoEP DEFER | Yes | ☑ **ACCEPTED 2026-07-11** |
| **D-IOID-CER-2** | Full-loop: ioID **before** external WMP identity claim; fixtures may omit DID with honest ABSENT | Yes | ☑ **ACCEPTED 2026-07-11** |
| **D-IOID-CER-3** | Triple-gate + 0.75 IOTX hard cap; estimate-first; dry_run default | Yes | ☑ **ACCEPTED 2026-07-11** |
| **D-IOID-CER-4** | No absolute “first controller DID” without sourced survey | Yes | ☑ **ACCEPTED 2026-07-11** |
| **D-IOID-CER-5** | Fire live registration (spend + gamer sign) | Hold until GO | ☑ **HOLD 2026-07-11** — hard pre-req per Claude audit: the live send/readback path is placeholder (`ioid_token_id = 42`, `controller_ioid_registration.py` ~L293); wire-up build (agent-path quality, `operator_session_register_agents.py` step-7 precedent) must go green BEFORE any GO |

---

## 6. CODE-TRUTH index

| Topic | Path |
|-------|------|
| DID build + optional CID/MFG | `bridge/vapi_bridge/controller_ioid_registration.py` `build_controller_did_document` |
| Canon device_id | `device_birth_cert.compute_device_id_from_pubkey_hex` / `verify_device_id_matches_pubkey` |
| Register orchestration | `register_controller_ioid` (dry_run default True) |
| Deployed ioID registry | `contracts/deployed-addresses.json` → `VAPIioIDRegistry` |
| Agent register precedent | `bridge/scripts/operator_session_register_agents.py` step 7 |
| Sequencing context | `docs/depin-interop-vision-2026-07-11.md` §3 #1, §7 |

---

*ioID ceremony review bars v0 — 2026-07-11. Design only; gamer signs; bridge never; testnet; no token.*
