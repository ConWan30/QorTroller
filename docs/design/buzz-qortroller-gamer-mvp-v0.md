# Buzz × QorTroller — Gamer MVP Design Scope (v0)

Status: PROPOSED (operator review gate — verification-first skill, V-check)
Authors: Devin + operator (Con)
Date: 2026-07-30

---

## 0. Purpose of this document

Scope the **first real, interoperable** integration of QorTroller onto the
Buzz platform for **gamers**, and define EA's optimized role inside it.

This is NOT the pitch deck. This is the engineering surface that survives
both Buzz's real protocol shapes (NIP-29 `h` tags, kind 9, kind 9000,
NIP-42/NIP-OA, `buzz-cli`) and QorTroller's honesty rails (compose-not-conflate,
FROZEN-v1 preservation, candidate vs sealed, operator-fired chain, no raw
biometrics on a public bus).

The novelty is not "anti-cheat in chat." The novelty is:

> **Buzz is the social/ops plane where humans and the EA coordinate.
> QorTroller is the truth plane where presence and humanity are proven.
> Nostr carries pointers and operator signals — never the biometric substrate.**

Everything below follows from that one sentence.

---

## 1. The novelty, stated plainly

Three things are genuinely novel if built this way. Everything else in the
pitch deck is downstream of these.

### 1.1 Verifiable session coordination as a social primitive

Today a Discord channel says "I won." Nothing proves it. A Buzz channel
that requires a **session postcard** (commitment root + verdict enum +
enablement flags) before a result is pinned makes the *social act* of
claiming a win carry a cryptographic pointer. The proof still lives in
QorTroller; Buzz just refuses to treat a claim as "official" without the
pointer. That composition is novel.

### 1.2 Operator EA as a Buzz-native bot, not a chat LLM

The EA becomes a **countdown-bot-class process**: owns a Nostr key, NIP-42
auths (owner-attested via NIP-OA), self-adds as `role=bot`, listens to
`#rig-ops`, and posts **bounded status + session digests**. It is not an
LLM in the chat loop by default. That keeps the truth plane and the social
plane synchronized without letting free-text LLM output masquerade as
attestation.

### 1.3 Gamer sovereignty preserved across the bus

The gamer's ioID-bound identity proves **the human**. The EA's bot key
proves **the operator steward**. Those never merge. No raw HID, no raw
L4 tremor, no raw IMU, no raw frames cross the Nostr bus. Only digests,
verdict enums, and consent-gated pointers. This is the same
compose-not-conflate discipline the ioID/PoEP fusion already enforces,
extended to the social plane.

---

## 2. Identity matrix (compose, never conflate)

| Identity | Key holder | Proves | Role on Buzz | Never does |
|---|---|---|---|---|
| **Gamer / SYSTEM** | Gamer wallet / ioID-bound identity (DID `did:io:0x0cf36db5…`, ioID tokenId 498, TBA `0xFCee2377…`) | The human | Member: claims, consent, membership, profile | Hand privkey to operator |
| **Controller silicon** | Device path (VMDR pubkey `0x235a2c04…`, birth cert) — NOT a chat npub | The certified Edge | Attestation subject, referenced by `device_id` / `ioid_token` tags as **claims** | Sign chat messages |
| **EA / operator steward** | **Separate** Nostr key, owner-attested (NIP-OA) by operator npub | The operator's agent | Bot: status, alerts, session digests, ops replies | Claim to be the gamer; flip PoEP; fire chain |
| **Match / session verdicts** | Hash-bound commitments (PoAC 228B, PoSP, retina state) — not chat text | What was measured | Linked by `session_id` / commitment root tags | Live in chat content as truth |

**Hard rule:** do not derive the EA bot key from ioID tokenId 498 and use it
as "the gamer." That collapses the four identities above into one and breaks
the sovereignty claim at the foundation.

---

## 3. Event + tag schema (Buzz-correct, digest-only)

All channel messages use **kind 9** with an **`h`** tag (NIP-29 group tag),
not `e` tags, not `["channel", id]`. Channel membership self-add is
**kind 9000** with `role=bot`. Profile is **kind 0**. Auth is **NIP-42**
(kind 22242) with optional **NIP-OA** owner-attestation tag for the EA bot.

### 3.1 EA status event (kind 9, `#rig-ops`)

```jsonc
{
  "kind": 9,
  "content": "rig: ALL_READY | bridge: up | oracle: disabled",
  "tags": [
    ["h",   "<channel-uuid>"],
    ["qortroller", "1"],
    ["rig_state", "ALL_READY"],
    ["bridge_health", "up"],
    ["oracle_enabled", "false"],
    ["device_id", "581a836c"],
    ["ioid_token", "498"]
  ]
}
```

`device_id` / `ioid_token` are **claims** (the EA asserts the rig is bound
to that device). They are not proof on the wire. Proof is the offline
session postcard.

### 3.2 Session postcard event (kind 9, `#matches`)

```jsonc
{
  "kind": 9,
  "content": "session 20260730_... | verdict: PRESENCE_CANDIDATE | N: 0",
  "tags": [
    ["h", "<channel-uuid>"],
    ["qortroller", "1"],
    ["session_id", "20260730_..."],
    ["verdict", "PRESENCE_CANDIDATE"],
    ["commitment_root", "<sha256-hex>"],
    ["n_challenges", "0"],
    ["poep_enabled", "false"],
    ["l6b_enabled", "false"],
    ["candidate_ok", "false"]
  ]
}
```

**Honesty tag set is mandatory.** `poep_enabled=false`, `l6b_enabled=false`,
`candidate_ok=false` are posted as-is when that is the truth. The EA never
posts `SYNCHRONIZED_CONTROLLER` unless the sealed `controller_presence`
verdict actually produced it on real hardware. This is the same honesty
spine as the PoEP GP-identity runner.

### 3.3 What NEVER crosses the Nostr bus

- Raw HID frames, raw IMU windows, raw L4 tremor samples
- Raw retina frames or base64 screen captures
- Full PoAC 228-byte payloads (only the commitment root)
- Wallet privkeys, `nsec`, `BRIDGE_PRIVATE_KEY`, device keys
- Any field that would let a reader reconstruct a gamer's biometric baseline

If a richer artifact is consent-gated and useful, post a **Blossom URL**
(NIP-94 file metadata, kind 1063) with a separate consent event — never
inline.

---

## 4. Channel topology (gamer community MVP)

One Buzz community. Five channels. Each has a clear owner.

| Channel | Owner | Who posts | Purpose |
|---|---|---|---|
| `#lobby` | Operator | Humans | Gamer onboarding, ioID claim help, who's-online |
| `#rig-ops` | Operator (EA bot lives here) | EA bot + operator | Rig status, ALL_READY/IDLE, bridge health, oracle state |
| `#matches` | Operator | Humans + EA bot (postcards only) | Session results, pinned official results require postcard |
| `#disputes` | Operator | Humans + EA bot (links only) | Dispute threads; EA posts commitment root + scorecard link, never a unilateral BAN |
| `#announcements` | Operator (admin only) | Operator | Tournament schedules, rule changes, enablement ceremony notes |

The EA bot is a **member** of `#rig-ops` and `#matches` only. It is not an
admin. It cannot manage channels. That matches `--role Bot` in Buzz.

---

## 4a. Operator decisions — RESOLVED (2026-07-30)

| Decision | Resolution |
|---|---|
| Bot auth mode (§12.1) | **Owner-attested (NIP-OA)** by the operator npub |
| EA bot key origin | Fresh key from `buzz-admin generate-key`; **NOT** derived from ioID tokenId 498 |

Remaining open: §12.2 (bot in `#matches`?), §12.3 (ioID claim kind),
§12.4 (Blossom default), §12.5 (ACP runtime).

---

## 4b. V-check findings that changed the build (verified, not assumed)

Three findings from reading the real Buzz tree and this machine. Each one
invalidates part of the original Option 1/2 plan.

**F-1: `buzz messages send` has no custom-tag flag.**
Its options are `--channel`, `--content`, `--kind`, `--reply-to`,
`--broadcast`, `--file`. So the CLI alone **cannot** emit the queryable digest
tags §3 requires. Without tags there is no `#session_id` / `#verdict` filter,
and the audit story collapses to "read every message."

**F-2: Python on this machine cannot sign Nostr events.**
No `coincurve` / `secp256k1` / `nostr_sdk`. Only `ecdsa`, which is ECDSA —
Nostr requires **BIP-340 Schnorr**. The original draft also hashed
`sort_keys` JSON; NIP-01 requires
`sha256([0, pubkey, created_at, kind, tags, content])`. Both bugs produce
events the relay rejects. Hand-rolling Schnorr is not acceptable here.

**F-3: the default Rust host cannot link.**
Host is `x86_64-pc-windows-gnu` and `dlltool.exe` is absent, so every native
build fails — including `buzz-admin`, which is required to generate the bot
key. MSVC Build Tools are present, so the fix is
`rustup toolchain install stable-x86_64-pc-windows-msvc` and building with
`cargo +stable-x86_64-pc-windows-msvc`. Applied and verified.

### Resulting decision — Architecture C (split by strength)

```
Python (QorTroller truth plane)        Rust (bytes on the wire)
  HardwareWatcher / sessions.db  ──►   qortroller-buzz publish
  computes the digest JSON             signs kind 9 + custom tags
  never touches crypto                 NIP-42 + NIP-OA (buzz-ws-client)
```

Helper: `buzz/examples/qortroller-buzz/` — follows the sanctioned
`examples/countdown-bot` pattern. Subcommands `whoami`, `authtag`, `publish`.
Built and smoke-tested; safety rails verified (refuses `nsec` in content,
refuses bare 64-hex tag values, refuses self-attestation, refuses a
caller-supplied `h` tag, 8 KiB content cap).

Auth-tag posture: mint **once, offline** with `authtag`, then run the bot with
`BUZZ_AUTH_TAG` only. The operator key is never in the bot's environment, so a
compromised bot host does not compromise the operator identity.

Setup runbook: `docs/runbook/buzz-phase1-setup.md`.

---

## 5. Architecture (target)

```
 DualShock Edge ──► QorTroller bridge (truth plane, local)
                         │
                         │ status / session digests ONLY
                         ▼
              qortroller-buzz-bot (thin Python bot, Path A)
                         │
                         │ NIP-42 + NIP-OA (owner-attested)
                         ▼
                   Buzz relay (vendored buzz/, port 3000)
                         │
        ┌────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   Desktop app        Mobile app      (later) buzz-acp
   (humans)          (humans)         → EA conversational ops
                                        (Path B, Phase 4)
```

**Two planes, one bus, no conflation.** Truth stays local and slow to
claim. Social is Buzz. EA spans both only as reporter + operator, never as
gamer substitute.

---

## 6. EA's optimized role (scoped honestly)

| EA job | Mode | What it posts | What it never posts |
|---|---|---|---|
| Rig ops steward | Bot Path A | `rig_state`, bridge health, oracle enabled/disabled | raw IMU, frames, keys |
| Session reporter | Bot Path A | session_id, commitment root, verdict enum, honesty flags | full PoAC payloads in clear |
| Adjudication notifier | Bot Path A | links to offline scorecards / commitment roots | unilateral BAN as truth |
| Operator engineer (Phase 4) | ACP Path B | @mention answers: status, ceremony steps, test summaries | chain spend without triple-gate |
| Gamer coach (future, separate) | Separate **gamer-side** agent | consent-gated tips | claiming proof without live hardware |

**EA is not the gamer. EA is the rig's operator agent.** For multi-gamer
product: each gamer has **their own** bot/agent on their rig; the operator
EA is **house steward** on the community relay.

---

## 7. Phased build (each phase has an acceptance test)

### Phase 0 — Hygiene (now, before any code)
- Burn the `nsec` hardcoded in `ea_buzz_bridge.py` / `bridge/vapi_bridge/ea_buzz_bridge.py` — treat as compromised.
- Move all keys to env (`BUZZ_PRIVATE_KEY`, `BUZZ_OWNER_PRIVATE_KEY`, `NIM_API_KEY`, `QUICKSILVER_API_KEY`, `BRIDGE_PRIVATE_KEY`).
- Add the scratch bridge files to `.gitignore` or delete them.
- Confirm vendored `buzz/` runs: `cd buzz && . ./bin/activate-hermit && just setup && just relay` → relay at `ws://localhost:3000`.
- **Acceptance:** `git log -p -- buzz/vapi_bridge/ea_buzz_bridge.py ea_buzz_bridge.py` shows no `nsec`; `buzz` relay boots clean.

### Phase 1 — Proof bot (2–5 days) — the corrected "Option 1"
Implement `scripts/qortroller_buzz_bot.py` modeled on `buzz/examples/countdown-bot`, NOT the draft Python:
- **Key:** new EA bot key (NOT derived from ioID 498), **owner-attested** by operator npub via NIP-OA, role `bot`.
- **Auth:** NIP-42 challenge-response; if relay requires membership, also carry NIP-OA `auth` tag.
- **Profile:** kind 0, name "QorTroller Rig EA", picture = small SVG.
- **Self-add:** kind 9000 with `["h", channel]`, `["p", bot_pubkey]`, `["role", "bot"]` to `#rig-ops` and `#matches`.
- **Subscribe:** kind 9 filter on `h` tag for those two channels.
- **Commands (bounded, ignore self):**
  - `!status` → rig_state + bridge + oracle_enabled
  - `!ready` → is HardwareWatcher at ALL_READY?
  - `!session <id>` → look up session postcard from local `.qortroller/sessions.db`, post digest only
- **Emits (kind 9, digest tags from §3):** rig state changes, session postcards on session end.
- **Sources wired to real QorTroller state:** `HardwareWatcher.last_state`, `BridgeClient.health`, `VisualOracleConfig().enabled`. **No fabricated SYNCHRONIZED.**
- **Acceptance:** desktop shows bot in members; `!status` reply matches rig without lying; `git log` shows no secrets; PV-CI gate still 184.

### Phase 2 — Attestation digests (1–2 weeks)
- On session end (bridge event or EA ticker stop), post the §3.2 postcard with the **real** verdict enum and honesty flags.
- Optional: Blossom upload (NIP-94 / kind 1063) of the scorecard JSON if the gamer consented — separate consent event, never auto.
- Align with RWM L0 / optical postcards if desired — still digests on Nostr, full artifacts offline.
- **Acceptance:** a third party can `buzz messages get --channel <matches-uuid>` and verify the commitment root against the QorTroller verifier without ever seeing raw biometrics.

### Phase 3 — Gamer community MVP (2–4 weeks)
- One community: your play group. Channels per §4.
- Gamer joins with **own** npub; links ioID in profile/claim event (kind 0 `ioid_token` tag, or a dedicated claim kind) — **without giving the operator their privkey**.
- Match channel requires bot-confirmed session postcard to pin "official" result (channel admin pins the postcard event id).
- **Acceptance:** one real NCAA CFB 26 session between two gamers produces a pinned, verifiable result in `#matches` with both gamers' ioID claims and the EA postcard.

### Phase 4 — ACP for EA ops (optional, "large scale" operator surface)
- `buzz-acp` + `goose` / `claude-agent-acp`, OR a thin ACP wrapper around EA's safe tool subset.
- Scope: engineering/ops (@"run pytest", @"invariant status", @"ceremony steps"), **not** live HID fire.
- Tool surface via `buzz-cli` + MCP subset mirroring EA's safe tools (`shell=False` discipline preserved).
- **Acceptance:** operator @mentions EA in `#rig-ops`, EA runs `pytest bridge/tests/test_retina_visual_oracle.py` and posts the summary; never spends chain.

### Phase 5 — Product claims (only after enablement)
- Population band, multi-gamer FRR, L6B/N seals, independent verifier path.
- Only then does language move from "candidate presence on Buzz" toward "tournament-grade."

---

## 8. Non-goals (explicit, to prevent scope creep)

- **No raw biometrics on Nostr.** Ever. Digests and pointers only.
- **No auto prize rail v0.** Chain writes stay operator-fired, triple-gate, kill-switch pattern. Prize distribution is Phase 5+.
- **No EA as gamer substitute.** EA is house steward. Gamer-side agents are a separate future lane.
- **No "100% fair forever" claims until enablement.** `poep_enabled` / `l6b_enabled` / N≥50 are still gated; honest SYNCHRONIZED needs the real single-HID bridge fire+IMU ring.
- **No forcing EA into ACP prematurely.** Bot first (truth + liveness signals), ACP second (conversation around those signals).
- **No public BAN as truth.** A posted BAN without held-out process is still social politics. Crypto proves what evidence claimed, not that the ban was just.

---

## 9. Interoperability prerequisites (checklist before Phase 1 code)

- [ ] Vendored `buzz/` boots: `just relay` → `ws://localhost:3000`.
- [ ] `buzz-admin generate-key` produces a fresh EA bot keypair (saved to env, not committed).
- [ ] Operator npub is a relay member (so NIP-OA owner-attestation works on a closed relay).
- [ ] `BUZZ_ALLOW_NIP_OA_AUTH=true` set on the relay if using owner-attested bot auth.
- [ ] `buzz-cli` builds: `cargo build --release -p buzz-cli` → `./target/release/buzz`.
- [ ] `buzz messages send --channel <uuid> --content "test"` works from CLI (proves auth + write path).
- [ ] QorTroller `HardwareWatcher` + `BridgeClient` importable from `qortroller.py` without launching the TUI.
- [ ] `python scripts/vapi_invariant_gate.py` clean (184).
- [ ] `.gitignore` covers `ea_buzz_bridge.py`, `bridge/vapi_bridge/ea_buzz_bridge.py`, `.qortroller/`, all `.env`.

---

## 10. Privacy + public-repo rules

- Repo is public. Anything pushed is world-readable.
- Never commit: `.env`, `nsec`, wallet keys, `BRIDGE_PRIVATE_KEY`, raw `sessions/`, biometric dumps, `audits/rwm_*`, `cfb_rwm_live_*.jsonl`.
- Gamer ioID link is a **claim** the gamer posts themselves; the operator never posts "gamer X is ioID 498" on their behalf without consent.
- Blossom uploads of scorecards require an explicit consent event from the gamer's own key.

---

## 11. Relationship to existing QorTroller rails

| Rail | How this MVP respects it |
|---|---|
| FROZEN-v1 preservation | No PoAC/PoSP/retina commitment formula touched; only posts digests of their outputs |
| Compose-not-conflate (ioID/PoEP fusion) | Identity matrix §2 is the same discipline extended to the social plane |
| Operator-fired chain | No chain writes from the bot; Phase 5+ prize rail stays triple-gate |
| Verification-first | This doc is a V-check; Phase 1 has an acceptance test before code merges |
| Chain-spend skill | Not triggered — no spend, no deploy, no gas estimation in Phases 0–4 |
| PV-CI gate | Must stay 184 across every phase |

---

## 12. Open operator decisions (need answers before Phase 1)

1. **Bot auth mode:** standalone bot key, or owner-attested (NIP-OA) by your operator npub? (Recommend owner-attested for a closed relay.)
2. **Channel scope:** is the EA bot allowed in `#matches` (postcards) or only `#rig-ops`?
3. **Gamer ioID claim mechanism:** kind 0 profile tag, or a dedicated claim kind (e.g. a new kind 9xxx)?
4. **Scorecard Blossom upload:** on by default (consent-gated), or off until Phase 3?
5. **ACP in Phase 4:** goose, claude-agent-acp, or a custom ACP wrapper around EA tools?

---

## 13. Greenlight gate

This document is PROPOSED. Per the verification-first skill, no Phase 1
code is written until the operator:

1. Confirms the identity matrix §2 (especially: EA key NOT derived from ioID 498).
2. Picks answers to the open decisions §12.
3. Approves Phase 0 hygiene (key burn + scrub) as safe to execute.

Once approved, Phase 1 is the first build commit.
