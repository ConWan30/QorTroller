---
name: qortroller-concierge
description: "Quick-reference for Retina gamer commands, charter v1 propose/hire, and safety rails."
---

# Retina Quick Reference (Agentic Charter v1)

## Core identity

- **QorTroller:** reference V.A.P.I. implementation on IoTeX.
- **PoAC:** 228-byte Proof of Autonomous Cognition per cognition cycle.
- **PoEP:** Proof of Embodied Play — controller-side reflex/IMU liveness.
- **PoSP:** Proof of Secure Presence — session-level presence binding.
- **ioID:** IoTeX decentralized identity; token 498 for the certified Edge.
- **VSS:** Verifiable stream seat; seat/queue/session status.
- **Clause:** Retina is **P-SOV** (gamer sovereignty). Charter: `docs/design/qortroller-agentic-charter-v1.md`.

## Certified device

- **DualShock Edge (CFI-ZCP1)** — device id `581a836c`.
- Real `SYNCHRONIZED_CONTROLLER` requires a single-HID bridge fire+IMU ring and a real gameplay session.
- Dry/injected fire is honestly `IDENTITY_ONLY`.

## DM commands

| Command | Action | Reply |
|---------|--------|-------|
| `status` | `GET /player/session-status` | Rig/session digest |
| `analytics` | `GET /player/self-analytics` | Gamer data digest |
| `claim <token> <device>` | `buzz_ioid_claim.py` | ioID claim posted to `#lobby` |
| `propose <artifact> <clause> <name> [desc...]` | `buzz_agent_factory.py propose` | Proposal (not mint) |
| `hire <name> --clause P-... --resume "..."` | `buzz_agent_factory.py hire` | Candidate agent (ENABLED off) |
| `brainstorm <topic>` | `propose` brainstorm under **P-FRM** | Framework seed / proposal |
| `help` | none | Command list |

**Deprecated (do not present as primary power):** `create agent|channel|project|workflow|template`.  
If a gamer says “create”, rewrite to **propose** (or **hire** with clause+resume). Mint only after operator approval / mint allow-list.

## Purpose clauses (must declare one)

| Clause | Use |
|--------|-----|
| P-SOV | Sovereignty, claims, consent |
| P-ATT | Attestation / postcard explanation |
| P-VSS | Seat status language only (**never OPEN**) |
| P-WMP | Provenance / deferred export honesty |
| P-OPS | Rig / SAP / invariants |
| P-FRM | Frameworks / WPs |
| P-STU | Studio / SDK pitch ceilings |

**No clause → no hire, no channel.**

## Useful `@EA` commands (operator only)

- `@EA status` — rig status
- `@EA repo health` — repo + test health
- `@EA invariant status` — PV-CI gate status
- `@EA failing` — list failing components
- `@EA diagnose status` — queue + job diagnosis

## Forbidden patterns

- Operator allow-list expansion, shell, chain spend, raw HID/IMU, wallet/private-key, git force push, nsec.
- VSS **OPEN**, claim inflation, candidate→certified upgrades, silent topology (new stable channels without propose).
- QorTroller ACP rejects banned tool surfaces with `rejected: banned_tool_surface`.

## Gamer commands (gamer key required)

- `python scripts/buzz_ioid_claim.py --ioid-token 498 --device-id 581a836c`
- Propose / hire via DM to Retina (never free-form mint as the default).

## Progress is not a creation receipt

Progress = SAP seal / pin / on-chain / human accept — not “channel created.”
