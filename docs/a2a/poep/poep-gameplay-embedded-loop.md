# A2A-POEP-GAMEPLAY — in-session presence challenges (not desk probes)

**Opened 2026-07-17 · operator-authorized · grok ↔ Claude · ruling (a).**  
Subject: replace the **desk-probe ritual** as the primary presence path with **gameplay-embedded challenges** — rare, low-amplitude, nonce-bound stimuli **during real play**, gated on activity + session identity, packaged as **session liveness**.

## Why this loop (operator signal)

Desk GO/NO_GO volume measures FA rates and band stats. It does **not** deeply answer  
“a human is holding the certified Edge **while gaming**.”  
Product-logical differentiator vs probe-farming: **play context + sparse live challenge + session join**.

## Claim (locked language — candidate, not flip)

> During an active play session on the registered Edge, under a **trusted capture host**,  
> sparse unpredictable adaptive-trigger challenges produce live-bound responses under catch rules.  
> This is **session liveness**, not identity, not anti-compromised-PC (FLIP-B).

`poep_enabled` / `L6B_ENABLED` / `L6_CHALLENGES_ENABLED` stay **False** until operator two-key + evidence.

## Roles (ruling (a))

| Agent | Mandate |
|-------|---------|
| **grok** | Design claim, architecture, adversary bars, phase cut; post-build verify |
| **Claude** | Ground + **build** BUILD-NOW; tests; staged-only |
| **Operator** | Sole committer; live dual-connect dogfood; never agent-fired flip |

## Round protocol

```text
round-01-grok-open     : design + BUILD-NOW (B1→B2 skeleton)     [THIS OPENING]
round-02-claude-build  : implement + tests + report
round-03-grok-verify   : adversary / dual-connect honesty / PASS|HOLD
round-04-…             : only if gaps
```

## Hard rails

- 228B PoAC / FROZEN-v1 untouched  
- No chain write / no IOTX in this loop  
- Dual-connection aware: USB→PC challenge+IMU; BT→console play (operator topology)  
- In-game amplitude **low** (not desk force=255 default) — play must remain usable  
- Catch trials optional in-session; desk capture path remains for calibration only  
- PV-CI held; staged-only; operator sole committer  

## Success (software loop)

1. Session shell: start/stop play session with `session_id`, device_id, activity samples.  
2. Activity gate: challenges only when gameplay-active (not pure menu).  
3. Sparse scheduler: CSPRNG intervals; reuses `poep_live_verify` (+ optional catch).  
4. Session summary artifact (not 40 desk JSON overwrites).  
5. Tests green; claim language cannot be confused with identity or FLIP-B.  
6. Explicit: **not** desk-probe N expansion as the goal.

## Explicitly out of scope

- More desk-only volume campaigns as the main deliverable  
- `poep_enabled=True`  
- F-PATHA-1 / VMDR re-anchor  
- Waveform gate freeze  
- Tournament BLOCK from presence ticks alone  

---
*Loop medium: `docs/a2a/poep/round-gameplay-*.md` + `scripts/a2a_pkg_relay.py`.*  
*Prior: desk multi-op seed + catch FA start + adversary software gate PASS; operator reframe 2026-07-17.*
