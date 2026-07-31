# Buzz × QorTroller — Phase 4 ACP Addendum
## Grok Build + Devin AI as the Operator Harness

**Status:** CODE LANDED (operational acceptance pending)  
**Date:** 2026-07-31  
**Code commit:** `de50a6d` (PR #102, squash-merged)  
**Parent document:** `docs/design/buzz-qortroller-gamer-mvp-v0.md`  
**Runbook:** `docs/design/buzz-phase4-acp-gateway-runbook.md`  
**Authors:** Operator (Con) + Grok; implementation by Devin  
**Aligns with:** Phase 3 commits through `53bf17f`; Phase 4 code `de50a6d`

---

## 0. Purpose

This addendum resolves the open decision in §12.5 of the parent design document and defines Phase 4 of the Buzz integration.

**Decision locked:**  
Phase 4 ACP runtime is a **custom dual-harness** using:

- **Grok Build** — primary, fast, low-latency ops agent
- **Devin AI** — secondary, heavy engineering / multi-file / deep diagnosis agent

---

## 1. Landed state (2026-07-31)

### Phase 3 base (complete)

| Capability | Status | Key commit(s) |
|---|---|---|
| Match-pin workflow (`#matches` + `buzz_pin_match.py`) | Landed + dogfooded | `22d1c9f` |
| Full community topology (`#matches`, `#disputes`, `#announcements`) | Landed | `5d8d30a` |
| Gamer ioID claim flow (self-asserted) | Landed + dogfooded | `5d8d30a`, `adcff0c` |
| Periodic session digests + NIP-OA | Landed | `bab57e6` |
| Architecture C (Python truth → Rust helper) | Stable | `0466a7c` onward |

### Phase 4 code (complete)

| Deliverable | Status |
|---|---|
| `scripts/qortroller_acp_gateway.py` | Landed (`de50a6d`) |
| `bridge/tests/test_qortroller_acp_gateway.py` (40 tests) | Green |
| Grok Build primary / Devin heavy routing | Landed |
| Fail-closed `ACP_OPERATOR_PUBKEYS` | Landed |
| Fixed-argv + `shell=False` tool surface | Landed |
| Digest-only replies + secret scrubbing | Landed |
| Local audit trail (`audits/acp_gateway.jsonl`, gitignored) | Landed |
| Devin hand-off queue (no impersonation) | Landed |
| Phase 1–3 bot `@EA` prefix support | Landed |
| Live `--eval` acceptance (health / invariant / pytest / ban) | Passed in PR |
| PV-CI | **188** (live gate; baseline grew past the 184 quoted at design time) |

### Phase 4 operational acceptance (operator-local, still open)

These require the operator’s live Buzz channel and key material; they cannot be completed from a remote design session:

1. Set `ACP_OPERATOR_PUBKEYS=<operator hex pubkey>` in `scripts/.env`.
2. `ACP_DRY_RUN=1 python scripts/qortroller_acp_gateway.py` against live `#rig-ops`.
3. Live `#rig-ops` posts of the four acceptance commands; confirm in-thread digests.
4. Confirm no secrets / raw substrate / chain interaction in any reply.

Until those four clear, Phase 4 is **code-landed, ops-pending**.

---

## 2. Core Principle (unchanged)

> Buzz is the social/ops plane.  
> QorTroller is the truth plane.  
> Nostr carries only pointers, status, and operator signals — never the biometric substrate.

---

## 3. Architecture (as implemented)

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
│  (primary)      │     │  (heavy / queued)     │
└─────────────────┘     └──────────────────────┘
     │                           │
     └─────────────┬─────────────┘
                   ▼
          Safe Tool Surface (shell=False)
                   │
                   ▼
          Reply to #rig-ops (digest only)
```

**Routing:** simple/read-only → Grok Build; `deep_diagnose` or explicit `@EA devin …` → Devin (queued hand-off, no result claim).

---

## 4. Identity & Authority Rules (non-negotiable)

Unchanged from design. EA bot key separate and owner-attested. Neither harness claims gamer identity. Operator retains sole commit / spend / ceremony authority.

---

## 5. Allowed Tool Surface (v0 — as shipped)

| Tool | Preferred Harness |
|------|-------------------|
| `run_pytest <path>` | Grok Build (`@EA devin run pytest …` → Devin) |
| `run_invariant_gate` | Grok Build |
| `get_rig_status` | Grok Build |
| `get_session_summary <id>` | Grok Build |
| `list_ceremony_steps` | Grok Build |
| `health_check` | Grok Build |
| `deep_diagnose <topic>` | Devin (queue only) |

Hard bans: arbitrary shell, wallet/chain/gas, raw HID/IMU/L4/frames/PoAC, FROZEN mutation without ceremony.

---

## 6. Acceptance Criteria

**Code acceptance (done in PR #102):** 40 tests green; `--eval` path verified for invariant / health / pytest / banned command; PV-CI 188 PASS; no chain / keys / raw substrate.

**Ops acceptance (operator-local):** see §1 operational checklist.

---

## 7. Non-Goals (Phase 4)

Unchanged: no gamer-facing agent, no auto prize rail, no live HID from Buzz, no agent commit authority, no digest-rule relaxation, no replacement of Phase 1–3 bot, no Architecture C change.

---

## 8. Relationship to Parent Document & Phase 5

- Resolves §12.5 of `buzz-qortroller-gamer-mvp-v0.md`.
- Phase 5 (product claims) remains gated behind enablement — see `docs/design/buzz-phase5-product-claims-scope.md`.
- “Bot first, ACP second” ordering preserved.

---

**End of Phase 4 Addendum (closeout revision)**
