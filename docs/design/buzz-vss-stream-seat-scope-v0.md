# QorTroller × Buzz — Verifiable Stream Seat (VSS)
## Conceptual Framework & Engineering Scope (v0)

**Status:** PROPOSED — design-only; no implementation until prerequisites clear  
**Date:** 2026-07-31  
**Parents:** `docs/design/buzz-qortroller-gamer-mvp-v0.md`, `docs/design/buzz-phase4-acp-grok-devin-addendum.md`, `docs/design/buzz-phase5-claim-register-v0.md`  
**Harness:** Grok Build (primary ops / thin slices) + Devin (heavy multi-file) via existing ACP  
**Product line:** Feature inside the **QorTroller Buzz community**, not a standalone streaming company

---

## 0. One-sentence product

> **A human member of the QorTroller community may open a stream seat only while a capture path is live and the retina oracle is running on their bridge; humans and agents may view the room and digests; pixels never ride the Nostr proof bus.**

Call the feature **Verifiable Stream Seat (VSS)**.  
Public language stays inside the Phase 5 claim register (no “cheat-proof stream,” no tournament-grade claims).

---

## 1. Why this can work (design constraints that make it fail-closed)

“Guaranteed to work” here means **fail-closed, phased, and architecturally non-contradictory** — not marketing certainty.

| Constraint | Effect |
|------------|--------|
| Three planes, never merged | Truth (QorTroller) · Media (WebRTC/RTMP/Blossom) · Social (Buzz) |
| Digests-only on Nostr | Kind 9 seat events = status + tags + URL pointer; **no frames** |
| One EA steward | `@EA` reports eligibility; does not own gamer stream keys or pixels |
| Humans stream, agents view | `role=bot` / managed agents **cannot** open a seat |
| Eligibility is local + membership | Bridge health ∧ community member ∧ (optional) ioID claim |
| Claim register binding | Any public sentence maps to a row or is forbidden |
| Dual harness already landed | Grok = fast/read slices; Devin = multi-file; operator commits |

If a design step violates a row above, it is out of scope — not “Phase 2.”

---

## 2. Prerequisites (hard gates before code)

### 2.1 Protocol / ops

| ID | Prerequisite | Why |
|----|----------------|-----|
| **P-OPS** | G5-OPS closed (live `#rig-ops` ACP acceptance) | Seat status must be operable by the same EA surface |
| **P-BOT** | Phase 1–3 bot stable (NIP-OA, digests, `#matches`) | Reuse publish helper + Architecture C |
| **P-CH** | Community topology live (`#lobby`, `#rig-ops`, `#matches`, …) | Add `#streams` without redesigning membership |
| **P-CLAIM** | Claim register v0 in force | Prevents hype language at launch |
| **P-REG** | No FROZEN / commitment-formula changes required | VSS is additive |

### 2.2 Hardware / bridge (per streaming gamer)

| ID | Prerequisite | Why |
|----|----------------|-----|
| **P-CAP** | Capture card (or documented capture path) visible to bridge | Seat is meaningless without a video source |
| **P-RET** | Retina / visual oracle **process running** and health OK | Explicit product gate (still advisory presence — do not upgrade claim grade) |
| **P-BR** | Bridge health endpoint exposes capture + oracle flags | Eligibility must be machine-checkable |
| **P-KEY** | Gamer’s own Buzz key + (recommended) ioID claim | Sovereignty; no operator-held gamer `nsec` |

### 2.3 Explicit non-prerequisites (do not block v0)

- G5-MULTI / SEP / L6 / L6B / FRR
- Tournament-grade language
- On-Nostr video
- Auto prize rail / TGE
- Default-ON retina in the production *protocol* sense (operator **policy** may require process-up for *seat*; that is not a population claim)

---

## 3. Conceptual model

### 3.1 Stream seat state machine

```
CLOSED ──(eligible)──► OPEN ──(ineligible OR gamer stop)──► CLOSED
           │                         │
           │                         └── always fail-closed
           └── announce kind 9 + media URL
```

**Eligible** iff:

```text
is_human_community_member
AND capture_path_up
AND retina_oracle_running    # process/health, not “humanity proven”
AND NOT role_bot
AND (optional v0.1) ioid_claim_present
```

### 3.2 Planes

```
┌─────────────────────────────────────────────────────────┐
│ GAMER RIG                                                 │
│  Controller → Bridge → Retina oracle                      │
│  Capture card → Media encoder (WebRTC/RTMP/etc.)          │
│  Eligibility probe → seat OPEN/CLOSED                     │
└───────────────┬─────────────────────────┬───────────────┘
                │ digests / seat events   │ pixels + media keys
                ▼                         ▼
        Buzz (Nostr)                 Media path
        #streams / #matches          (not the relay)
        humans + agents view
                │
                ▼
        EA bot / ACP (@EA stream status)
```

### 3.3 Identity matrix (extended, still compose-not-conflate)

| Identity | Streams? | Views? | Signs seat event? |
|----------|----------|--------|-------------------|
| Gamer (human npub) | **Yes** if eligible | Yes | **Yes** (gamer key) |
| Operator | No (unless also gamer on their rig) | Yes | Admin only |
| Rig EA bot | **No** | Yes (status) | Status/digest only, never as gamer |
| Grok / Devin | **No** | Via ops tools | Never |
| Managed Buzz agents | **No** | Yes | Never |

Hard rule: **seat open events are gamer-authored**, not EA-authored. EA may *mirror* or *confirm* health digests.

---

## 4. Buzz surface (seamless community feature)

### 4.1 Project

- Single Buzz **project/community**: QorTroller
- VSS is a **channel + event schema + bridge probe**, not a second product brand

### 4.2 Channels

| Channel | VSS role |
|---------|----------|
| `#streams` | Seat open/close events, watch pointers, human+agent viewers |
| `#matches` | Session postcards (unchanged); optional link to active seat |
| `#rig-ops` | Operator/EA: oracle/capture health, `@EA stream status` |
| `#lobby` | Onboarding: how to claim ioID + enable seat |
| `#announcements` | Policy only (admin); cite claim-register rows |

### 4.3 Event schema (kind 9, digest-only)

**Seat open (gamer key):**

```jsonc
{
  "kind": 9,
  "content": "stream seat OPEN | capture: up | oracle: running | media: <url>",
  "tags": [
    ["h", "<streams-channel-uuid>"],
    ["qortroller", "1"],
    ["vss", "1"],
    ["seat", "OPEN"],
    ["capture", "up"],
    ["retina_oracle", "running"],
    ["media_url", "https://..."],
    ["session_id", "<optional>"],
    ["ioid_token", "<optional claim>"],
    ["poep_enabled", "false"],
    ["l6b_enabled", "false"],
    ["candidate_ok", "false"]
  ]
}
```

**Seat close:** same shape, `seat=CLOSED`, no requirement to keep media URL live.

**Forbidden in content/tags:** frames, base64 video, raw HID, nsec, full PoAC.

### 4.4 Viewer model

- Humans and agents in the community can read `#streams`
- Clients open `media_url` out-of-band
- Agents may summarize digests / flag down seats; they must not open seats

---

## 5. Bridge / engineering surface

### 5.1 New minimal API (local truth)

```text
GET /vss/eligibility
→ {
    "eligible": bool,
    "capture_up": bool,
    "retina_oracle_running": bool,
    "reason_if_closed": "...",
    "honesty": { "poep_enabled": false, "advisory_oracle": true }
  }
```

Rules:

- Fail-closed if oracle process down or capture missing
- Does not assert “human proven”
- No chain writes

### 5.2 Gamer-side helper (thin)

`scripts/buzz_vss_seat.py` (name flexible):

1. Poll `/vss/eligibility`
2. If rising edge to eligible → publish seat OPEN (gamer key, Architecture C helper)
3. If falling edge → seat CLOSED
4. Never upload pixels

### 5.3 Media path (out of QorTroller core)

V0 accepts **any** documented encoder that yields an HTTPS or WebRTC URL (OBS + RTMP service, self-hosted WHIP, etc.).  
QorTroller **does not** ship a CDN in v0. Integration = “URL in the seat event.”

---

## 6. ACP integration (Grok + Devin)

Reuse existing gateway; **add tools only after allow-list review**.

| Tool | Harness | Behavior |
|------|---------|----------|
| `get_stream_seat_status` | Grok | Local eligibility + last seat digest summary |
| `run_pytest <vss tests>` | Grok | CI hygiene |
| `deep_diagnose vss …` | Devin queue | Multi-file investigation only |

**Never:** start stream as EA, hold gamer media keys, post frames, flip oracle enablement without human ceremony.

---

## 7. Work packages — who builds what

### Lane discipline

| Lane | Owner | Scope |
|------|--------|--------|
| **Grok Build** | Fast, small PRs | Eligibility endpoint shape, tests, seat script skeleton, docs, ACP read tool, claim-register row draft |
| **Devin** | Heavy | Multi-file bridge wiring, helper publish path, channel bootstrap, integration tests, runbook |
| **Operator** | Human | Keys, live community, capture/oracle on real rig, merge authority, claim language |

### WP sequence (each has acceptance — no “big bang”)

| WP | Goal | Acceptance | Primary |
|----|------|------------|---------|
| **VSS-0** | Design freeze (this doc) | Operator ack; no code | — |
| **VSS-1** | `GET /vss/eligibility` fail-closed | Unit tests: capture down → ineligible; oracle down → ineligible | Grok → Devin if bridge depth |
| **VSS-2** | `#streams` channel + schema constants | Bot/member can post fixture seat event; tags validated | Devin |
| **VSS-3** | `buzz_vss_seat.py` open/close | Rising/falling edge dogfood on operator rig | Devin + operator |
| **VSS-4** | ACP `get_stream_seat_status` | `@EA` digest only; scrubbed | Grok |
| **VSS-5** | Runbook + claim-register rows | R-VSS-* phrases gated; never-sayable list updated | Grok |
| **VSS-6** | Second human viewer | Another community member opens `media_url` | Operator |
| **VSS-7** (optional) | Agent viewer policy | Bot cannot OPEN; can READ | Devin |

No WP may touch FROZEN wire, commitment tags, or spend chain.

---

## 8. Claim register additions (draft rows)

| ID | Phrase | Grade | Gate |
|----|--------|-------|------|
| R-VSS-01 | “Stream seat is OPEN while capture and retina oracle process report up.” | G0 | VSS-1..3 landed |
| R-VSS-02 | “Seat events are digests + media URL pointers on Buzz.” | G0 | VSS-2 |
| R-VSS-03 | “Only human community members can open a seat; agents may view.” | G1 | VSS-7 policy |
| R-VSS-04 | “Stream is humanity-proven / tournament-grade.” | G4 | **Forbidden** until full Phase 5 gates |

When these rows are promoted, edit `docs/design/buzz-phase5-claim-register-v0.md` in a reviewed commit — no silent upgrades.

---

## 9. Non-goals (v0)

- Twitch feature parity (clips, discoverability, ads, global CDN)
- Video payloads on Nostr
- EA or Devin/Grok as streamer identity
- Ban-from-stream as cryptographic truth
- Default-ON retina as population certification
- Requiring G5-MULTI before a **single-operator** dogfood seat
- Replacing Phase 1–3 bot or Architecture C

---

## 10. Risk register

| Risk | Mitigation |
|------|------------|
| Oracle advisory confused with proof | Honesty tags + claim register; eligibility copy says “process running” |
| Media URL rot / private leak | HTTPS, gamer-controlled; close seat on stop; no secrets in tags |
| Bot stream farms | Membership role check; reject `role=bot` for OPEN |
| Scope creep into CDN | Media path explicitly third-party in v0 |
| CI Mythos/CODEOWNERS noise | Same operator-merge discipline as #102/#103; no baseline drift in VSS PRs |
| Building before G5-OPS | **P-OPS hard gate** — no VSS-3 live without ops EA |

---

## 11. Development environment (harness discipline)

Use the **same harness that already shipped Phase 4/5**, not a new agent zoo:

1. **Single source of truth** — this scope doc + claim register
2. **ACP bus** — `@EA` / queue Devin; no second identity for Grok/Devin on Buzz
3. **Attackable claims** — each WP ends in a test or dogfood checklist
4. **Operator sole merge** — agents propose; operator commits
5. **Brainstorm later complexity only inside WP boundaries** — e.g. WHIP self-host, Blossom VOD, multi-rig seats = new WPs after VSS-6

Brainstorming rule: **any new idea must name the plane it touches (truth / media / social) and the WP it extends; if it merges planes, reject.**

---

## 12. Greenlight gate (operator)

Implement **VSS-1** only after:

1. P-OPS (or explicit waiver: local-only eligibility, no live `#streams`)
2. Ack of three-plane split and “no frames on Nostr”
3. Ack that retina gate is **process health**, not humanity cert
4. Ack claim rows R-VSS-01..04 as draft until promoted in the claim register

---

## 13. Relationship to parent docs

- Does **not** resolve Phase 5 enablement gates; VSS is orthogonal social/media seating
- Does **not** close G5-OPS; it *depends* on it for live seat announcements
- Extends identity matrix of `buzz-qortroller-gamer-mvp-v0.md` §2 without conflating gamer and EA
- ACP tools follow `buzz-phase4-acp-grok-devin-addendum.md` allow-list discipline

---

## 14. Summary

VSS is a **community feature**: proof-adjacent **seat control** + Buzz **viewing room** + external **media URL**, engineered as additive WPs on the existing Grok/Devin ACP harness. Novelty is **eligibility-gated human broadcast in a humans-and-agents workspace**, not a new video network.

---

**End of Verifiable Stream Seat scope (v0)**
