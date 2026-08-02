---
name: qortroller-concierge
description: "Quick-reference for Retina gamer commands, creation rules, and safety rails."
---

# Retina Quick Reference

## Core identity

- **QorTroller:** reference V.A.P.I. implementation on IoTeX.
- **PoAC:** 228-byte Proof of Autonomous Cognition per cognition cycle.
- **PoEP:** Proof of Embodied Play — controller-side reflex/IMU liveness.
- **PoSP:** Proof of Secure Presence — session-level presence binding.
- **ioID:** IoTeX decentralized identity; token 498 for the certified Edge.
- **VSS:** Verifiable Session Service; seat/queue/session status.

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
| `create agent <name> <role>` | `buzz_agent_factory.py create-agent` | Child agent `.env` created |
| `create channel <name> <desc>` | `buzz_agent_factory.py create-channel` | Channel created |
| `create project <name> <goal>` | `buzz_agent_factory.py create-project` | Channel + NIP-34 repo created |
| `create workflow <name> <steps>` | `buzz_agent_factory.py create-workflow` | Channel + workflow created |
| `create template <name> <desc>` | `buzz_agent_factory.py create-template` | NIP-23 note created |
| `brainstorm <topic>` | `buzz_agent_factory.py brainstorm` | Brainstorm post seeded |
| `help` | none | Command list |

## Useful `@EA` commands (operator only)

- `@EA status` — rig status
- `@EA repo health` — repo + test health
- `@EA invariant status` — PV-CI gate status
- `@EA failing` — list failing components
- `@EA diagnose status` — queue + job diagnosis

## Forbidden patterns

- Operator commands, shell, chain spend, raw HID/IMU, wallet/private-key, git force push, nsec.
- QorTroller ACP rejects these with `rejected: banned_tool_surface`.

## Gamer commands (gamer key required)

- `python scripts/buzz_ioid_claim.py --ioid-token 498 --device-id 581a836c`
- Any `create` or `brainstorm` command via DM to Retina.
