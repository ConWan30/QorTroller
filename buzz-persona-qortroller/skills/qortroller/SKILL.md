---
name: qortroller
description: "Quick-reference QorTroller concepts, commands, and safety rules."
---

# QorTroller Quick Reference

## Core identity

- **QorTroller:** reference V.A.P.I. implementation (Verifiable Autonomous Physical Intelligence) on IoTeX.
- **PoAC:** 228-byte Proof of Autonomous Cognition per cognition cycle.
- **PoEP:** Proof of Embodied Play — controller-side reflex/IMU liveness.
- **PoSP:** Proof of Secure Presence — session-level presence binding.
- **ioID:** IoTeX decentralized identity; token 498 for the certified Edge.
- **VSS:** Verifiable Session Service; seat/queue/session status.

## Certified device

- **DualShock Edge (CFI-ZCP1)** — device id `581a836c`.
- Real `SYNCHRONIZED_CONTROLLER` requires a single-HID bridge fire+IMU ring and a real gameplay session.
- Dry/injected fire is honestly `IDENTITY_ONLY`.

## Useful `@EA` commands

- `@EA status` — rig status
- `@EA repo health` — repo + test health
- `@EA invariant status` — PV-CI gate status
- `@EA failing` — list failing components
- `@EA diagnose status` — queue + job diagnosis
- `@EA job status <id>` — single job digest
- `@EA plan <goal>` — Devin plan (requires explicit `devin` prefix in ask_ea? No, ACP supports `devin @EA plan`)
- `@EA confirm plan <id>` — human-fired; explain only
- `@EA pytest <path>` — run a single test target

## Forbidden patterns

- Shell, chain spend, raw HID/IMU, wallet/private-key, git force push, nsec.
- QorTroller ACP rejects these with `rejected: banned_tool_surface`.

## Gamer commands (gamer key required)

- `python scripts/buzz_ioid_claim.py --ioid-token 498 --device-id 581a836c`
- `python scripts/buzz_pin_match.py <event_id>` (operator or authorized pin)
