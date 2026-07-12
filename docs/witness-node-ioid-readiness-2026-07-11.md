# Witness Node + ioID Registration Readiness (TRL-1 R3) — 2026-07-11

**The card is "one purchase, two roadmaps"** (alignment doc §7): the RP recall ceiling *now*, and the
seed of a new DePIN device category — the **gaming witness node** — *later*. This note defines that
node and confirms its on-chain identity path is real. Readiness check:
`python scripts/witness_node_ioid_readiness.py` → **READY** (every prerequisite already deployed).

## The witness node (N3)

RP-CLOSE-1 measured that same-machine capture contends with Remote Play's GPU decoder (process
isolation refuted live). The deployable answer is a sidecar **DEVICE**, not a co-process. The AMANKA
capture card + its host is the **v0 proxy**; a dedicated sidecar (its own silicon) is **v1**. Either
way the property is the same:

> The controller is the trusted thing that **acts**; the witness node is the trusted thing that
> **sees** — its own silicon, off the gamer's hot path, observer-effect-free by construction.

It runs the trio-retina perception tier (observation plane). Per the loop's law it **may suggest,
never assert** — its outputs travel as `retina_perception_root` referenced by PoSP, never inlined.

## IoTeX identity path (grounded — the machinery already exists)

The witness node registers as a *device with its own identity*, using the **same machinery the
certified controller already uses**, applied to the observer:

| prerequisite | on-chain / in-repo | role |
|---|---|---|
| **ioID device identity** | `VAPIioIDRegistry` `0xF7885B588718b891B2234477D031607da4a7ACfe` (deployed) | the node's DID / token — its independent identity |
| **device birth cert** | `VAPIManufacturerDeviceRegistry` `0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0` (deployed) | the node's provenance (silicon-rooted, Path A) |
| **registration pattern** | `bridge/vapi_bridge/agent_registration.py` (`ioid_did` / `ioid_token`, e.g. the Curator DID) | the proven mint flow to reuse |
| **event validation** | `w3bstream/applet/` (`frame_grabbing=false` pinned) | the node's perception events validated mechanically, never captured |
| **boundary discipline** | Arc 7 DA sidecar-pointer | scene payloads on DA, 32B root on the wire |

## Why this is the answer to `verifier_independence=False` (RP-7)

RP-7 banked `verifier_independence=False` because the capture and the verification share the gamer's
machine/keys. **An independent witness DEVICE with its OWN on-chain ioID is exactly what "independent
verifier" means physically** — it is not the gamer's key, not the bridge's key. When the witness node
holds its own ioID, the RP-7 rail (`bridge/tests/test_dcert7_verifier_independence.py`) has a real path
to flip to independent. This is maximal IoTeX alignment expressed as hardware.

## ioID-registration readiness checklist

Everything needed to register a witness node **already exists** (readiness check: READY). The actual
registration is a future, **operator + device + spend gated** ceremony (not fired here):

1. Provision the node's device identity + birth cert (Path A `provision_device_mfg.py` pattern → VMDR).
2. Mint the ioID (DID + token + TBA) via `VAPIioIDRegistry`, reusing the `agent_registration.py` flow.
3. Bind the node's perception-event schema to W3bstream validation (mechanical-only).
4. Re-run the RP-7 rail with the node's independent identity → confirm it flips.

**Rails:** this cycle registers nothing, writes no chain state, spends no IOTX. It confirms the path is
real and readies the ceremony. Advisory-first; observation never asserts; the node's outputs stay
pointer-only at the PoSP boundary.

## Two-roadmap sequencing

| roadmap | trigger | status |
|---|---|---|
| RP recall ceiling | card arrives (TRL-1 R1/R2 ready) | desk-ready now |
| witness-node DePIN category | operator-fired ioID ceremony on a witness device | path confirmed real (this note) |

---

*TRL-1 R3 - witness-node + ioID readiness. Loop: `docs/trio-readiness-loop-trl1-2026-07-11.md`.
Check: `scripts/witness_node_ioid_readiness.py`.*
