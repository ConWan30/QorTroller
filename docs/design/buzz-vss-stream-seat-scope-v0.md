# QorTroller × Buzz — Verifiable Stream Seat (VSS)
## Conceptual Framework & Engineering Scope

**Status:** PROPOSED — design only; no implementation until prerequisites clear  
**Date:** 2026-07-31  
**Revision:** v0.2 — clarity rewrite; Buzz human membership locked as sole required identity gate  
**Parents:** `docs/design/buzz-qortroller-gamer-mvp-v0.md`, `docs/design/buzz-phase4-acp-grok-devin-addendum.md`, `docs/design/buzz-phase5-claim-register-v0.md`  
**Harness:** Grok Build (thin / ops) + Devin (heavy multi-file) via existing ACP  
**Product line:** A feature inside the **QorTroller Buzz community** — not a standalone streaming service

---

## 0. What VSS is

> A **human member** of the QorTroller Buzz community may open a stream seat only while their capture path is up and the retina oracle process is running on their bridge. Humans and agents may watch. Pixels never ride the Nostr proof bus.

That is the whole product. Everything else is mechanism, honesty, or phase order.

**Public language** stays inside the Phase 5 claim register. No “cheat-proof stream.” No tournament-grade claims until those gates close.

---

## 1. Design rules (fail-closed)

These rules are not preferences. A design that breaks one is out of scope.

| Rule | Meaning |
|------|---------|
| **Three planes** | Truth (QorTroller) · Media (external URL) · Social (Buzz). Never merge them. |
| **Digests only on Nostr** | Seat events carry status, tags, and a media URL pointer — **never frames**. |
| **One EA steward** | `@EA` can report eligibility. It does not hold gamer keys or own the stream. |
| **Humans open seats; agents view** | `role=bot` and managed agents cannot OPEN. |
| **Buzz membership is identity** | Human community member is required. **IoID is never required.** |
| **Claim register binds speech** | Every public phrase maps to a row — or it is forbidden. |
| **Dual harness, one operator** | Grok and Devin propose; the operator commits. |

“Guaranteed to work” here means **fail-closed and non-contradictory**, not marketing certainty.

---

## 2. Who can open a seat

### Required

1. **Buzz human membership** — the gamer’s npub is a human member of the QorTroller community (`NOT role=bot`).
2. **Capture path up** — documented capture card / path visible to the bridge.
3. **Retina oracle process running** — process health OK (advisory presence; not “humanity proven”).
4. **Gamer-authored event** — seat OPEN/CLOSED is signed with the **gamer’s own** Buzz key.

### Never required

- IoID / IoTeX claim  
- NIP-05, device claim, or any other optional binder  
- Operator-held gamer `nsec`  
- EA or agent opening the seat on the gamer’s behalf  

### Optional tags (display only)

A gamer **may** attach a self-asserted ioID claim, NIP-05, or local device claim to the seat event. These are pointers for viewers who care. They do **not** gate OPEN.

**Lobby copy should say:** join the community as a human → connect capture + oracle → open a seat with your key.  
Not: “get IoID first.”

---

## 3. Prerequisites before code

### Protocol / ops

| ID | Gate | Why |
|----|------|-----|
| **P-OPS** | G5-OPS closed (live `#rig-ops` ACP acceptance) | Seat status rides the same EA surface |
| **P-BOT** | Phase 1–3 bot stable (NIP-OA, digests, `#matches`) | Reuse publish helper + Architecture C |
| **P-CH** | Community topology live | Add `#streams` without redesigning membership |
| **P-CLAIM** | Claim register v0 in force | Blocks hype at launch |
| **P-REG** | No FROZEN / commitment-formula changes | VSS is additive |

### Per streaming gamer (hardware)

| ID | Gate | Why |
|----|------|-----|
| **P-CAP** | Capture path visible to bridge | No video source → no seat |
| **P-RET** | Retina oracle **process** up | Product gate; still advisory |
| **P-BR** | Bridge exposes capture + oracle flags | Eligibility must be machine-checkable |
| **P-KEY** | Gamer’s own Buzz key | Sovereignty |

### Does **not** block v0

G5-MULTI / SEP / L6 / L6B / FRR · tournament language · on-Nostr video · CDN · default-ON retina as population cert · IoID

---

## 4. How a seat works

### State machine

```text
CLOSED ──(eligible)──► OPEN ──(ineligible OR gamer stop)──► CLOSED
           │                         │
           │                         └── always fail-closed
           └── publish kind 9 + media URL
```

**Eligible** iff:

```text
is_human_community_member
AND NOT role_bot
AND capture_path_up
AND retina_oracle_running      # process health, not humanity cert
```

IoID is **not** in this predicate.

### Planes

```text
GAMER RIG
  Controller → Bridge → Retina oracle
  Capture → Media encoder (OBS / WebRTC / RTMP / …)
  Eligibility probe → OPEN / CLOSED
        │                              │
        │ digests + seat events        │ pixels + media keys
        ▼                              ▼
   Buzz (Nostr)                    Media path (not the relay)
   #streams / #matches
   humans + agents view
        │
        ▼
   EA / ACP  (@EA stream status only)
```

### Identity matrix

| Identity | Opens seat? | Views? | Signs seat event? |
|----------|-------------|--------|-------------------|
| Gamer (human npub) | **Yes**, if eligible | Yes | **Yes** (gamer key) |
| Operator | Only if also a gamer on their own rig | Yes | Admin only |
| Rig EA bot | **No** | Status digests | Never as gamer |
| Grok / Devin | **No** | Via ops tools | Never |
| Managed Buzz agents | **No** | Yes | Never |

**Hard rule:** seat open events are **gamer-authored**. EA may mirror health digests only.

---

## 5. Buzz surface

VSS is a **channel + event schema + bridge probe** inside the existing QorTroller project — not a second brand.

| Channel | Role |
|---------|------|
| `#streams` | Seat open/close, watch pointers, human + agent viewers |
| `#matches` | Session postcards (unchanged); optional link to a seat |
| `#rig-ops` | Capture/oracle health; `@EA stream status` |
| `#lobby` | How to join as a human member and enable a seat |
| `#announcements` | Policy only; cite claim-register rows |

### Seat event (kind 9, digest-only)

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
    ["ioid_token", "<optional — never required>"],
    ["poep_enabled", "false"],
    ["l6b_enabled", "false"],
    ["candidate_ok", "false"]
  ]
}
```

Close uses the same shape with `seat=CLOSED`.

**Forbidden in content/tags:** frames, base64 video, raw HID, nsec, full PoAC.

Viewers (human or agent) read `#streams` and open `media_url` out-of-band. Agents may summarize digests or flag a down seat; they must not OPEN.

---

## 6. Bridge surface

### Eligibility API (local truth)

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

- Fail-closed if capture or oracle process is down  
- Does not assert “human proven”  
- Does not require IoID  
- No chain writes  

### Gamer helper

`scripts/buzz_vss_seat.py` (name flexible):

1. Poll `/vss/eligibility`
2. Rising edge → publish OPEN (gamer key, Architecture C)
3. Falling edge → publish CLOSED
4. Never upload pixels

### Media path

Any documented encoder that yields an HTTPS or WebRTC URL (OBS + RTMP, self-hosted WHIP, etc.).  
QorTroller does **not** ship a CDN in v0. Integration = URL in the seat event.

---

## 7. ACP (Grok + Devin)

Reuse the existing gateway. New tools only after allow-list review.

| Tool | Harness | Behavior |
|------|---------|----------|
| `get_stream_seat_status` | Grok | Local eligibility + last seat digest |
| `run_pytest` (VSS tests) | Grok | CI hygiene |
| `deep_diagnose vss …` | Devin queue | Multi-file investigation |

**Never:** start a stream as EA, hold gamer media keys, post frames, or flip oracle enablement without a human ceremony.

Grok and Devin are **not** Buzz community agents. They build in the repo via ACP; they do not need community agent profiles to ship VSS.

---

## 8. Work packages

| Lane | Owner | Scope |
|------|--------|--------|
| **Grok Build** | Fast, small PRs | Eligibility shape, tests, seat script skeleton, docs, ACP read tool, claim rows |
| **Devin** | Heavy | Bridge wiring, publish path, channel bootstrap, integration tests, runbook |
| **Operator** | Human | Keys, live community, real-rig dogfood, merge authority, claim language |

| WP | Goal | Acceptance |
|----|------|------------|
| **VSS-0** | Design freeze (this doc) | Operator ack |
| **VSS-1** | `GET /vss/eligibility` fail-closed | Capture down or oracle down → ineligible |
| **VSS-2** | `#streams` + schema constants | Fixture seat event validates; ribbon + optional `session_id` |
| **VSS-3** | Seat open/close helper | Rising/falling edge on operator rig; **gamer key** |
| **VSS-4** | ACP `get_stream_seat_status` | Digest only; scrubbed |
| **VSS-5** | Runbook + claim rows | R-VSS-* gated; never-sayable list updated |
| **VSS-6** | Second human viewer | Another member opens `media_url` |
| **VSS-7** | Agent viewer policy | Bot cannot OPEN; can READ |

No WP may touch FROZEN wire, commitment tags, or spend chain.

---

## 9. Novelty spine (mandatory for “VSS shipped”)

Three features separate VSS from commodity streaming. They are **not optional cosmetics**.

### F1 — Proof-adjacent seat

The seat is a protocol object, not “OBS is live.”

- OPEN only while eligibility holds  
- Honesty ribbon (`poep_enabled`, `l6b_enabled`, `candidate_ok`) posted **as-is**  
- Fail-closed close when capture or oracle drops  
- Media is a URL pointer only  

**Built in:** VSS-1 → VSS-3  
**Acceptance:** capture or oracle down ⇒ seat cannot stay OPEN; ribbon never invents `true`.

### F2 — Verifiable watch parties

The room can bind to a sealed session, not only to a video URL.

- Optional `session_id` on the seat event  
- `#streams` ↔ `#matches` postcard link  
- Media clock and protocol clock stay separate  
- After the match: seat CLOSED; optional PORT-CERT / verify pointer  

**Built in:** schema at VSS-2; dogfood bind by VSS-6  
**Acceptance:** a stranger can tell “watching a URL” from “room claims session X”; missing bind is honest absence.

### F3 — Gamer sovereignty

- Seat events signed by the **gamer** key only  
- Buzz human membership is the membership gate  
- IoID / other binders optional  
- EA cannot open a gamer seat  

**Built in:** VSS-3 (key path), VSS-7 (bot ban)  
**Acceptance:** no operator `nsec` in the path; claim tags never sold as on-chain verification without a separate verify path.

### Integration map

```text
VSS-0  design freeze
  │
VSS-1  eligibility ──────────────────► F1 probe
  │
VSS-2  #streams + schema ────────────► F1 ribbon + F2 session_id slot
  │
VSS-3  open/close dogfood ───────────► F1 fail-closed + F3 gamer key
  │
VSS-4  ACP status ───────────────────► operator view of F1
  │
VSS-5  claim rows ───────────────────► R-VSS-01..07
  │
VSS-6  second human viewer ──────────► F2 watch-party dogfood
  │
VSS-7  agent policy ─────────────────► F3 human-only OPEN
```

**Ship rule:** VSS-3 without F1 honesty tags or gamer-authored events is incomplete. F2 bind may be absent on first dogfood; the schema must still allow it.

### Later (must not block F1–F3)

| ID | Feature | Earliest |
|----|---------|----------|
| S1 | Agent viewers (summarize / flag down) | VSS-7 |
| S2 | Anti-farm (one seat per key, no empty OPEN) | after VSS-7 |
| S3 | Consent-gated highlight / verify pointer | after VSS-6 |
| S4 | `@EA stream status` | VSS-4 (already in spine) |
| S5 | Organizer pilot room (seat + pin + portcert) | after VSS-6 |
| S6 | Multi-gamer seats | after G5-MULTI |

### Not in VSS

Global discovery algo · pixels on Nostr · “verified human live” before Phase 5 gates · agent/EA as streamer · ban-as-proof · first-party CDN as a VSS milestone

---

## 10. Claim register (draft rows)

| ID | Phrase | Grade | Gate |
|----|--------|-------|------|
| R-VSS-01 | “Stream seat is OPEN while capture and retina oracle process report up.” | G0 | VSS-1..3 |
| R-VSS-02 | “Seat events are digests + media URL pointers on Buzz.” | G0 | VSS-2 |
| R-VSS-03 | “Only human community members can open a seat; agents may view.” | G1 | VSS-7 |
| R-VSS-04 | “Stream is humanity-proven / tournament-grade.” | G4 | **Forbidden** until Phase 5 gates |
| R-VSS-05 | “Seat carries honesty ribbon (flags as-is).” | G0 | F1 / VSS-2..3 |
| R-VSS-06 | “This room is watching sealed session `<session_id>`.” | G0 | F2 when bind is real |
| R-VSS-07 | “Gamer self-asserted ioID claim accompanies this seat.” | G1 | Optional only |

Promote rows only by editing `docs/design/buzz-phase5-claim-register-v0.md` in a reviewed commit.

---

## 11. Non-goals and risks

**Non-goals:** Twitch feature parity · video on Nostr · EA/Grok/Devin as streamer · ban as cryptographic truth · default-ON retina as population cert · requiring G5-MULTI for single-operator dogfood · replacing Phase 1–3 bot or Architecture C · requiring IoID to stream

| Risk | Mitigation |
|------|------------|
| Oracle confused with proof | Ribbon + claim register; copy says “process running” |
| Media URL rot / leak | HTTPS, gamer-controlled; close seat on stop; no secrets in tags |
| Bot stream farms | Membership role check; reject `role=bot` for OPEN |
| CDN scope creep | Media path third-party in v0 |
| Build before G5-OPS | P-OPS hard gate for live `#streams` |

---

## 12. Greenlight (operator)

Start **VSS-1** only after:

1. P-OPS (or written waiver: local eligibility only, no live `#streams`)
2. Ack of three-plane split and no frames on Nostr
3. Ack that retina gate is **process health**, not humanity cert
4. Ack that **Buzz human membership** is the only required membership gate; **IoID is never required**
5. Ack F1–F3 as mandatory for “VSS shipped”
6. Ack R-VSS-01..07 as draft until promoted in the claim register

---

## 13. Parents and summary

- Does **not** close G5-OPS or Phase 5 enablement gates; it depends on the former for live seats and stays orthogonal to the latter  
- Extends the identity matrix of `buzz-qortroller-gamer-mvp-v0.md` without conflating gamer and EA  
- ACP tools follow `buzz-phase4-acp-grok-devin-addendum.md` allow-list discipline  

**VSS** = proof-adjacent seat control + Buzz viewing room + external media URL, built as additive work packages on the existing Grok/Devin harness.  
**Novelty** = eligibility-gated human broadcast in a humans-and-agents workspace — not a new video network.

---

**End of Verifiable Stream Seat scope (v0.2)**
