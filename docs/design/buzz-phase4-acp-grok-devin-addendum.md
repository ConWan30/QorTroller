# Buzz × QorTroller — Phase 4 ACP Addendum
## Grok Build + Devin AI as the Operator Harness

**Status:** LOCKED (operator decision)  
**Date:** 2026-07-31  
**Parent document:** `docs/design/buzz-qortroller-gamer-mvp-v0.md`  
**Authors:** Operator (Con) + Grok  
**Aligns with:** Phase 3 commits through `53bf17f` (match-pin, community topology, dogfooded ioID claim flow)

---

## 0. Purpose

This addendum resolves the open decision in §12.5 of the parent design document and defines Phase 4 of the Buzz integration.

**Decision locked:**  
Phase 4 ACP runtime shall be a **custom dual-harness** using:

- **Grok Build** — primary, fast, low-latency ops agent
- **Devin AI** — secondary, heavy engineering / multi-file / deep diagnosis agent

This replaces the previously open options (goose, claude-agent-acp, or generic custom wrapper).

---

## 1. Current Landed Context (as of 2026-07-31)

Phase 3 is substantially complete and dogfooded:

| Capability | Status | Key commit(s) |
|---|---|---|
| Match-pin workflow (`#matches` + `buzz_pin_match.py`) | Landed + dogfooded | `22d1c9f` |
| Full community topology (`#matches`, `#disputes`, `#announcements`) | Landed | `5d8d30a` |
| Gamer ioID claim flow (self-asserted, operator never touches gamer key) | Landed + dogfooded | `5d8d30a`, `adcff0c` |
| Periodic session digests + NIP-OA | Landed | `bab57e6` |
| Architecture C (Python truth plane → Rust `qortroller-buzz` helper) | Stable | `0466a7c` onward |
| PV-CI | 184 | Consistent across recent commits |

Phase 4 therefore starts from a working Phase 1–3 bot that already publishes digests, respects honesty flags, and preserves the identity matrix.

---

## 2. Core Principle (unchanged)

> Buzz is the social/ops plane.  
> QorTroller is the truth plane.  
> Nostr carries only pointers, status, and operator signals — never the biometric substrate.

Phase 4 extends the EA from a pure reporter (Phases 1–3) into an addressable operator surface while preserving every existing rail.

---

## 3. Architecture

```
#rig-ops  (@EA <command>)
        │
        ▼
┌──────────────────────────────────────┐
│         ACP Gateway (thin)           │
│  • Authenticates as EA bot (NIP-OA)  │
│  • Parses mention + intent           │
│  • Enforces allow-list               │
│  • Routes by complexity              │
└──────────────────┬───────────────────┘
                   │
     ┌─────────────┴─────────────┐
     ▼                           ▼
┌─────────────────┐     ┌──────────────────────┐
│   Grok Build    │     │      Devin AI         │
│  (primary)      │     │  (heavy engineering)  │
│                 │     │                      │
│ • status        │     │ • multi-file changes │
│ • pytest        │     │ • deep diagnosis     │
│ • invariants    │     │ • larger refactors   │
│ • ceremony steps│     │ • complex test runs  │
│ • health checks │     │                      │
└─────────────────┘     └──────────────────────┘
     │                           │
     └─────────────┬─────────────┘
                   ▼
          Safe Tool Surface
     (shell=False + allow-list only)
                   │
                   ▼
          Reply to #rig-ops
       (summary only — digests)
```

**Routing heuristic (initial):**
- Simple / fast / read-only / single-command → Grok Build
- Multi-step, multi-file, deep analysis, or explicit “devin” keyword → Devin

This continues the pattern already visible in the repository: Devin has been the primary co-author on the bulk of the Phase 1–3 Buzz work (`Generated with [Devin]`). Phase 4 formalizes that division of labor inside an addressable ACP surface.

---

## 4. Identity & Authority Rules (non-negotiable)

| Identity              | Role in Phase 4                          | Forbidden                          |
|-----------------------|------------------------------------------|------------------------------------|
| Gamer / SYSTEM        | Never acted by either agent              | Agents must never claim gamer identity |
| EA / Operator Steward | Both Grok Build and Devin act only as EA | Must not speak as the gamer        |
| Controller silicon    | Referenced by claim tags only            | Never signs chat                   |
| Operator (human)      | Sole commit, spend, and ceremony authority | Agents propose / execute safe tools only |

- EA bot key remains separate and owner-attested (NIP-OA).  
- Neither Grok Build nor Devin may hold or derive the gamer’s ioID key.  
- Final merge, push, and any chain action remain human-only.  
- This is the same compose-not-conflate discipline already enforced by the dogfooded ioID claim flow (`buzz_ioid_claim.py`).

---

## 5. Allowed Tool Surface (v0)

Strict allow-list. Everything else is rejected by the ACP Gateway.

| Tool                    | Description                                      | Preferred Harness |
|-------------------------|--------------------------------------------------|-------------------|
| `run_pytest <path>`     | Run specific pytest target and return summary    | Grok Build / Devin |
| `run_invariant_gate`    | Execute `scripts/vapi_invariant_gate.py`         | Grok Build        |
| `get_rig_status`        | Current HardwareWatcher + bridge + oracle state  | Grok Build        |
| `get_session_summary <id>` | Digest-only session postcard lookup           | Grok Build        |
| `list_ceremony_steps`   | Return current ceremony checklist                | Grok Build        |
| `health_check`          | Quick component smoke imports + shell=False check| Grok Build        |
| `deep_diagnose <topic>` | Multi-file / complex investigation               | Devin             |

**Hard bans (enforced by gateway):**
- Any tool that can execute arbitrary shell
- Any wallet / contract / gas / chain-write tool
- Any tool that returns raw HID, IMU, L4, frames, or full PoAC payloads
- Any tool that mutates FROZEN surfaces without operator ceremony

All shell execution must continue to go through the existing hardened path (`shell=False` + `shlex.split`) already verified in recent commits and `AGENTS.md`.

---

## 6. Acceptance Criteria

**Primary acceptance test:**

1. Operator posts in `#rig-ops`:  
   `@EA run pytest bridge/tests/test_retina_visual_oracle.py`
2. ACP Gateway routes to Grok Build (or Devin if heavy).
3. Agent executes the test via the safe tool surface.
4. EA bot replies in-thread with a clean summary (pass/fail counts + short note).
5. No chain interaction occurs.
6. No secrets, raw biometrics, or full PoAC data appear in the reply.
7. `python scripts/vapi_invariant_gate.py` still reports 184 (or current pinned count).

**Secondary acceptance:**
- `@EA invariant status` returns the current PV-CI result.
- `@EA health` returns a short component status block.
- Explicit routing works: `@EA devin diagnose <topic>` goes to Devin.

---

## 7. Non-Goals (Phase 4)

- No gamer-facing conversational agent (that is a future separate lane).
- No automatic prize / bounty / chain actions.
- No live HID or controller control from Buzz.
- No elevation of either agent to commit authority.
- No relaxation of digest-only posting rules.
- No replacement of the existing Phase 1–3 bot; Phase 4 sits *on top* of it.
- No change to Architecture C (Python truth plane → Rust wire helper).

---

## 8. Implementation Notes

- ACP Gateway should be a thin, long-running process (Python preferred for consistency with `scripts/qortroller_buzz_bot.py`).
- It re-uses the existing EA bot identity and NIP-OA attestation already proven in Phase 1–3.
- Grok Build and Devin are treated as external harnesses invoked via their respective interfaces; the gateway never embeds their private keys.
- All replies remain kind-9 messages with the standard honesty / digest tag discipline established in Phase 2–3.
- Logging and audit trail of every ACP invocation must be kept locally (not on Nostr).
- Prefer continuing the existing commit attribution style (`Generated with [Devin]` / clear co-author notes) when Devin is the active harness for a change.

---

## 9. Relationship to Parent Document

This addendum:
- Resolves §12.5 of `buzz-qortroller-gamer-mvp-v0.md`
- Leaves all other sections of the parent document in force
- Keeps Phases 0–3 and Phase 5 unchanged
- Maintains the “Bot first, ACP second” ordering
- Reflects the now-landed state of Phase 3 (match-pin, topology, ioID claims)

---

## 10. Greenlight Gate for Phase 4 Implementation

Before any Phase 4 code is written:

1. Operator confirms this addendum (Grok Build + Devin locked).  ✅ (this commit)
2. Allow-list in §5 is accepted or adjusted.
3. Acceptance test in §6 is accepted.
4. Existing Phase 1–3 bot remains green and digest-only (current state as of `53bf17f`).

Once greenlit, implementation may begin with the ACP Gateway + Grok Build path first (lowest risk), followed by Devin routing.

---

**End of Phase 4 Addendum**
