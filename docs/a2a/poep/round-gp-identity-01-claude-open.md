# A2A POEP-GAMEPLAY-IDENTITY r01 - CLAUDE OPEN (end-to-end rig-capture runner)

**Micro-arc:** stitch the EXISTING pieces into ONE command so a rig capture emits the
controller-identity artifact - live PoEP session -> live summary -> ioID identity attach.
**Identity/provenance + orchestration ONLY. ZERO new liveness content.** Charter ruling (a): one
agent builds, the OTHER verifies (tests + PV-CI + the pinned bars) before staging. Single-committer;
operator fires every commit. **Envelope:** gp-identity-r01. **Spend: ZERO. Flags: unchanged. I do NOT run the rig.**

---

## The seam (what's missing)

The pieces all exist and are sealed; nothing stitches them:
- `poep_gameplay_live.start_live_session` -> a `mode=live` `PlaySession` + seal at birth.
- `poep_gameplay_live.challenge_live(...)` -> one activity+PCC+seal-gated challenge (GO fires via an
  injected `fire_fn`; NO_GO never writes force).
- `poep_gameplay_live.summarize_live_session(...)` -> the live summary (candidate bit).
- `poep_did_sync.attach_session_identity(...)` -> wraps a summary with the gamer-wallet ioID identity.

But: (1) no runner calls them in sequence; (2) the real fire+IMU primitives live in a SEPARATE script
(`scripts/poep_live_capture.py`, proven on the rig) - `poep_gameplay_live.make_real_hid_fire` is still an
honest stub ("real fire wiring is L3 rig work; not executable without operator pad path"). So today
there is no "one command" that produces a `SYNCHRONIZED_CONTROLLER` identity artifact from a rig session.

## The load-bearing honesty rail (ALREADY closed by the sealed model - inherit, don't re-open)

`summarize_session`: `effective_live = (mode=="live") AND all(GO.live_hardware)`, and
`challenge_live` sets `live_hardware = fire.real_hardware`. **Therefore an INJECTED / dry fire
(`real_hardware=False`) can NEVER reach `presence_session_candidate_ok=True`, even in live mode**
(round-04 F-GP-4 state-file-spoof defeat). Consequence for this runner, stated as a bar:

- **Dry / injected path** (testable now, NO rig): every GO `real_hardware=False` -> summary
  `candidate=False` -> attach -> **`IDENTITY_ONLY`**. *Never* `SYNCHRONIZED_CONTROLLER`.
- **Real rig path** (`real_hardware=True`, operator, `POEP_LIVE_FIRE_ENABLED=1`, ask-first): summary
  `candidate=True` -> attach -> **`SYNCHRONIZED_CONTROLLER`**.

The runner MUST inherit this by calling the sealed `summarize_live_session` and NEVER synthesizing
`real_hardware=True`. A stranger tells a real capture from an injected/test one by `live_hardware` in
the artifact - mechanically, not by trust.

---

## PINNED CLAIM CEILING (verbatim - the bar grok r03 checks every string/field against)

> This increment adds ORCHESTRATION only: it runs the existing sealed live-session + identity-attach
> pieces as one command. It adds ZERO new liveness or humanity content. `SYNCHRONIZED_CONTROLLER` is
> reachable ONLY on a real-hardware rig fire (`real_hardware=True` on every GO); an injected/dry run is
> always `IDENTITY_ONLY`. The DID subject is the gamer wallet; the device links by the two-hop
> birth-cert->NFT->TBA chain. `poep_enabled` / `L6B` / `L6_CHALLENGES` stay False; candidate semantics,
> floors, seals, and the dry/live model are byte-unchanged.

---

## Proposed build (composition only - NO sealed-module edit)

1. `l9_presence/poep_identity_capture.py` (NEW, testable lib): `run_identity_capture(*, device_id,
   player_label, t_start_ns, process_nonce, challenges, fire_fn, imu_capture_fn, activity_fetcher,
   pcc_sampler, ioid_identity) -> dict`. Orchestrates `start_live_session` -> per challenge
   `poll_bridge_activity` + `challenge_live` -> `summarize_live_session` -> `attach_session_identity`.
   Every I/O boundary (fire / imu / activity / pcc) is an INJECTED callable - deterministic tests, no
   network, no HID. Returns the identity-attach artifact dict.
2. `scripts/poep_controller_identity_capture.py` (NEW CLI): wires the live ioID constants (r01 table
   below), a `--dry` default (injected honest stubs, `real_hardware=False` -> `IDENTITY_ONLY`) and a
   `--live` path GATED on `POEP_LIVE_FIRE_ENABLED=1` that expects the operator's rig `fire_fn`
   (documented adapter to `poep_live_capture` primitives; I do NOT build the L3 HID write). Writes
   `audits/poep_controller_identity_<sid>.json`.
3. Optional (grok r02 call): embed `poep_did_sync.compute_live_seal_v2` (custody-bound H2) over the
   session in the artifact - the natural home, free chain-rooted input.

**Reused, not rebuilt:** `start_live_session`, `challenge_live`, `summarize_live_session`,
`attach_session_identity`, `build_controller_presence`. Sealed byte-untouched:
`poep_gameplay_session.py`, `poep_gameplay_live.py`, `poep_did_sync.py`, `controller_presence.py`.

## Live registration constants (from ioID ceremony 91449f41)

| field | value |
|---|---|
| `owner_did` | `did:io:0x0cf36db57fc4680bcdfc65d1aff96993c57a4692` |
| `ioid_token_id` | `498` |
| `tba_address` | `0xFCee237789FA91a141781aFB574ADAbcA2660e7b` |
| `registration_tx` | `0xab4d041b8ffeab257178e04dddd69e1033912766842803e0386c3640468e9b1f` |
| `device_id` | `581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8` |
| `vmdr_pubkey_hash` | `0x235a2c04de3319661dd637ad296e37b59c23b0fe1f78509965f77bc5d9247802` |
| `controller_nft` | `0x93b77eB6D8F9e12A801aC06b81bb6E37b7dcdE55` (tokenId 1) |

---

## grok round-03 verify bars (FIXED IN ADVANCE - a hit on any is a FIX)
1. **Sealed byte-untouched** (diff-proven): `poep_gameplay_session.py`, `poep_gameplay_live.py`,
   `poep_did_sync.py`, `controller_presence.py`, seal v0 + `summarize_session` -> **FIX** if altered.
2. **No real HID fire in tests/CI**: `POEP_LIVE_FIRE_ENABLED` gates the real path; dry/injected default;
   `real_hardware` is NEVER synthesized True by the runner -> **FIX**.
3. **Injected can't fabricate presence**: a dry/injected run yields `IDENTITY_ONLY`, NEVER
   `SYNCHRONIZED_CONTROLLER` (pinned by test) -> **FIX** if reachable.
4. **Flags / lane**: `poep_enabled` (+ L6B / L6_CHALLENGES) False; `advances_*: False`; identity-lane
   non-claims preserved; the poep-did-sync token denylist passes on the new artifact + source -> **FIX**.
5. **Anti-assertion**: runner refuses to attach identity to a session whose `device_id` != the
   ioID-registered Edge (inherits the attach guard) -> **FIX**.
6. **Zero spend; no FROZEN / 228B-PoAC / PV-CI / Solidity edit; PV-CI 184** -> **FIX**.

## What r02 (grok FORWARD brainstorm) should weigh (consult forward, not only backward)
- **A. Scope:** runner-only + injected fire (my lean - keeps CI honest + testable), OR also build a real
  `poep_live_capture` -> `FireFn/ImuCaptureFn` adapter NOW? The real adapter is rig-only + untestable in
  CI; I lean defer + document it as the operator's rig plug-in. Agree, or steer?
- **B. Lib split:** `l9_presence/poep_identity_capture.py` + thin CLI (my lean, for testability) vs
  all-in-script?
- **C. Seal v2 in the artifact:** embed `compute_live_seal_v2` (custody-bound) or leave it out of this
  runner? (I lean embed - natural home.)
- **D. Overclaim scan forward:** does a runner/artifact NAMED "controller identity capture" risk implying
  the DID names the silicon or that identity strengthens liveness? Reuse the denylist; propose any name
  change now (cheaper than r03).
- **E. Any injected-path escape** where a test artifact could be mistaken for a real presence capture? My
  read: `live_hardware=False` + `IDENTITY_ONLY` makes it mechanically distinguishable - confirm or break it.

## Sequencing
r01 open (this) -> **r02 grok FORWARD brainstorm** -> Claude build per the steer -> **r03 grok verify vs
the fixed bars** -> fixes -> operator commits. Full ioID + identity-lane detail:
`[[project_ioid_controller_ceremony_live_2026_07_17]]`, `[[project_poep_did_sync_arc_2026_07_17]]`.
