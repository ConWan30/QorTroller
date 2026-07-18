# A2A POEP-DID-SYNC r01 - CLAUDE OPEN (options 1+2 only)

**Micro-arc:** bind the live-session presence evidence to the controller's on-chain ioID identity -
**identity/provenance strengthening ONLY**. Charter ruling (a): one agent builds, the OTHER verifies
(tests + PV-CI + the pinned bars) before staging. Single-committer holds; operator fires every commit.
**Envelope:** poep-did-sync-r01. **Spend: ZERO. Flags: unchanged.**

---

## PINNED CLAIM CEILING (verbatim, up front - the bar grok r03 checks every string/field against)

> This increment strengthens the identity/provenance attached to session evidence. It adds ZERO
> liveness or humanity content. The DID subject is the gamer wallet (`did:io:0x0cf36db5...`); the
> device's link to it is the two-hop birth-cert->NFT->TBA chain, which the summary must carry in full.
> Candidate semantics, floors, and the dry/live model are byte-unchanged.

The DID-subject drift (`device_did` / "the Edge whose sovereign identity is resolvable") is the exact
overclaim class this loop exists to catch. The fix belongs in the **data model**, not just the prose.

---

## The device->identity chain (the fact the data model must carry, never collapse)

The DID names the **gamer wallet**, not the silicon. The device hangs off it by two hops:

```
device P-256 pubkey
  -> birth-cert / VMDR  pubkeyHash 0x235a2c04de3319661dd637ad296e37b59c23b0fe1f78509965f77bc5d9247802
  -> controller NFT     VAPIGamerControllerNFT 0x93b77eB6D8F9e12A801aC06b81bb6E37b7dcdE55  tokenId 1
  -> held in the DID's TBA  0xFCee237789FA91a141781aFB574ADAbcA2660e7b   (owner_did did:io:0x0cf36db5...)
```

A stranger verifies WHICH DEVICE by walking that chain - it is never asserted by a single "device DID".

## Live registration values (constants for this increment)

| field | value |
|---|---|
| `owner_did` | `did:io:0x0cf36db57fc4680bcdfc65d1aff96993c57a4692` |
| `ioid_token_id` | `498` |
| `tba_address` | `0xFCee237789FA91a141781aFB574ADAbcA2660e7b` |
| `registration_tx` | `0xab4d041b8ffeab257178e04dddd69e1033912766842803e0386c3640468e9b1f` |
| `device_id` | `581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8` |
| `vmdr_pubkey_hash` | `0x235a2c04de3319661dd637ad296e37b59c23b0fe1f78509965f77bc5d9247802` |
| `controller_nft_token_id` | `1` |
| `controller_nft` (deviceContract) | `0x93b77eB6D8F9e12A801aC06b81bb6E37b7dcdE55` |

---

## Scope - options 1 + 2 ONLY

### Option 1 - DID-enriched session summary (buildable now, zero spend)
Composition **on top of** `l9_presence/poep_gameplay_session.py::summarize_session` (the sealed round-04/05
module) - a NEW wrapper, same pattern as the existing seal wrapper, **no sealed-code edit**. It adds:
- `owner_did` - **never** `device_did`. The field name structurally can't misname the subject.
- `device_identity_chain` - an object a reader/stranger walks: `{device_id, vmdr_pubkey_hash,
  controller_nft, controller_nft_token_id, tba_address}`. The DID names the wallet; this object carries
  the two-hop device link in full so nobody can collapse it into "device DID".
- `registration_tx` - the ioID register tx (third-party-resolvable).
- A machine-readable `advisory: true` / `lane: "identity-provenance"` tag so downstream can't read it as
  a liveness field.

### Option 2 - seal v0.2 binds the custody epoch (buildable now, local bookkeeping)
A NEW candidate seal **v0.2** (v1 preimage byte-unchanged, still FROZEN-untouched) that folds
`controller_nft_token_id` into the live-session seal preimage. Epoch property stated **precisely**:
v0.2 distinguishes **NFT/TBA-custody epochs** - NOT "device identity" epochs. If the controller NFT
were ever transferred out of the TBA / the DID reissued, pre- and post-custody seals are
cryptographically distinguishable. Candidate tag; not FROZEN; gives the seal a chain-rooted input for free.

---

## Non-goals (explicit)
- **Option 3** (node-ledger "sovereign presence genesis" entry) - HELD as an operator decision, not built here.
- **Option 4** (TBA self-attest anchor) - OUT. Verdict accepted: provenance theater, real crypto content
  but zero liveness strength over option 3; skippable demo flourish. Not in this arc.
- No spend, no chain write, no new flags. `poep_enabled` / `L6B` / `L6_CHALLENGES` stay **False**.
- No edit to the sealed round-04/05 module, no FROZEN-v1 / 228B-PoAC / PV-CI-pinned surface.

---

## grok round-03 verify bars (FIXED IN ADVANCE - a hit on any is a FIX)
1. **Overclaim scan** - any string OR field implying the DID names the silicon (`device_did`,
   "device's sovereign identity", "the Edge's DID", etc.) -> **FIX**.
2. **Lane-leak scan** - any string implying the candidate/liveness got stronger -> **FIX**.
3. **Model byte-untouched** - round-04/05 sealed module + seal v1 preimage unchanged; the dry path stays
   non-candidate / honest-null -> **FIX** if altered.
4. **Flags** - `poep_enabled` False (+ L6B / L6_CHALLENGES) -> **FIX** if flipped.
5. **Non-goals honored** - option 3 not built, option 4 absent, zero spend, zero new flags -> **FIX** if violated.

## What round-02 (build) must show
- New wrapper + `device_identity_chain` object; `summarize_session` + the sealed module **byte-identical**
  (diff-proven). Seal v0.2 as a NEW candidate path; v1 unchanged.
- Tests: the chain walks correctly; `owner_did` present + no `device_did` token anywhere; the ceiling
  string embedded verbatim in the artifact; dry path unchanged. PV-CI 184.
- The claim-ceiling paragraph carried verbatim in the emitted artifact (so a stranger reads the bar, not
  just the fields).

## Sequencing
r01 open (this) -> **r02 build (Claude, has the live values + repo)** -> **r03 grok verify against the fixed
bars** -> r04/r05 fixes if any -> operator commits. Optional third check: relay the built increment for an
independent overclaim pass against the pinned ceiling. Full ioID detail: `[[project_ioid_controller_ceremony_live_2026_07_17]]`.
