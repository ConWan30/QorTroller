# A2A-POEP-CORPUS-TOOLING — multi-op pilot → durable capture integrity

**Opened 2026-07-16 · grok (design partner) → Claude (build) · ruling (a).**  
Subject: after the first **3-player Edge surprise pilot**, ship the **tooling that makes the next capture night bankable without forensics** — not a presence flip.

## Why this loop (live evidence)

| Layer | 2026-07-16 evening pilot | Status |
|-------|--------------------------|--------|
| Live nonce CR on registered Edge | Working (multi 8/8 blocks) | **BANKED** |
| Multi-op (P1/P2/P3) | Verify-pass N≈**107** pooled (DB) | **SEED banked** |
| Latency report (held-out) | `audits/poep-surprise-latency-report-2026-07-16.{md,json}` | **BANKED (report-only)** |
| Band freeze [80,450] | Provisional DQ only | **NOT frozen** |
| `player` on DB rows | Missing → handoff cut forensics | **DEBT** |
| Same-day audit JSON | Overwrites last 8 only | **DEBT** |
| `poep_enabled` | False | **STAYS False** |

The pilot proved capture + multi-op volume. The **next software win** is making N and player labels **first-class and append-only**, so the next held-out freeze does not depend on hard-coded UTC cuts.

## Roles (ruling (a))

| Agent | Mandate |
|-------|---------|
| **grok** | Design scope, acceptance bars, adversary/privacy rails; post-build verify |
| **Claude** | Ground + **build** BUILD-NOW set; tests green; staged-only until operator commit |
| **Operator** | Sole committer; rig nights; never agent-fired `poep_enabled` |

## Round protocol

```text
round-25-grok-corpus-tooling  : design + BUILD-NOW mandate + acceptance     [THIS OPENING]
round-26-claude-build         : implement + tests + report
round-27-grok-verify          : adversary/verify rails; HOLD or PASS
round-28-…                    : only if round-27 finds gaps
```

## Hard rails

- `poep_enabled` / `L6B_ENABLED` / `L6_CHALLENGES_ENABLED` stay **False**
- No reaction-band **freeze** from one night; report-only draft ceilings OK
- No FROZEN-v1 / PoAC / chain / Solidity edit
- No biometric export of per-curve samples into public audits
- PV-CI 183 held; staged-only; operator sole committer
- Player stamp is a **label for corpus integrity**, not identity / enrollment

## Success criteria (software loop)

1. Each live capture row can be attributed to **`--player`** in DB (or equivalent durable column).
2. Same-day multi-block captures **do not destroy** prior audits (append / session_id).
3. Latency report script is **first-class CLI** (no hard-coded handoff times required when player is stamped).
4. Tests pin overwrite-prevention + player stamp; grok verify PASS.

## Explicitly out of scope (this loop)

- Catch trials / FLIP-A adversarial re-run  
- Shape-gate recalibration  
- Second calendar day of rig capture (operator-paced, parallel)  
- Presence flip  

---
*Loop medium: `docs/a2a/poep/round-*.md` + `scripts/a2a_pkg_relay.py` envelopes.*
*Prior: round-24 rig findings · latency report 2026-07-16 · FLIP-A host-trusted only.*
