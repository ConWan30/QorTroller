# Session Continuum v0 — bind RWM into the rest of QorTroller

**Status: BUILT (CANDIDATE)** (2026-07-25).  
Schema: `qortroller-session-continuum-v0`  
**Not** a FROZEN-v1 family. **Not** a domain-tag commitment. REFERENCE-AND-BIND only.

## One-sentence claim (honest ceiling)

For **one** `session_id` (U1) and **one** `device_id` (Edge), a verified L0 RWM optical
chain, optional gamer-sovereign ioID material, optional PoEP presence candidate, and
optional stack cites (NOV-2 / escrow / PoSP / KAS) can be composed into a multi-bit
postcard that **never OR-merges** those planes into a fake single green light.

## Why this layer exists

| Surface | What it already does | Gap closed by continuum |
|---------|----------------------|-------------------------|
| RWM L0 | Per-frame optical chain + device + session | Isolated from identity/presence stack |
| NOV-2 bind | Tip-equality attach to PoAC/GIC | Still tip-only; not multi-plane composition |
| Controller presence | ioID × PoEP dual-bit | No optical / RWM plane |
| U1 `session_identity` | `SHA-256(label_stamp)` join key | Shared but not *composed* into one postcard |

Continuum is the **composition bind** that puts the optical witness plane on the same
join keys as the rest of the protocol — without inventing a new FROZEN primitive.

## Parallel bits (never collapsed)

| Bit | Meaning |
|-----|---------|
| `optical_rwm` | L0 re-verifies from disk; session + device present |
| `session_join` | `session_id` coherent; U1 re-derive when `session_display` cited |
| `device_join` | 32-byte device hex resolvable and consistent |
| `identity_bound` | ioID token/did/tba + registered_device_id match |
| `presence_candidate` | PoEP `presence_session_candidate_ok` + device/session match |
| `stack_cited` | NOV-2 / escrow / PoSP / KAS present + session (and tip) match |

## Closed verdicts

| Verdict | When |
|---------|------|
| `SYNCHRONIZED_CONTINUUM` | optical + session + device + identity + presence |
| `OPTICAL_IDENTITY` | optical + session + device + identity |
| `OPTICAL_PRESENCE` | optical + session + device + presence |
| `OPTICAL_SESSION` | optical + session + device (stack may also be cited) |
| `STACK_WITHOUT_OPTICAL` | identity/presence/stack without verified RWM |
| `PARTIAL` | material present but incomplete joins |
| `UNVERIFIABLE` | device or session **MISMATCH** (fail-closed; clears success bits) |

## Ship surface

| Path | Role |
|------|------|
| `l9_presence/session_continuum.py` | pure composition (stdlib) |
| `bridge/vapi_bridge/rwm_session_continuum.py` | L0 loader + optional JSON surfaces |
| `scripts/rwm_session_continuum_cli.py` | offline CLI build/verify |
| `l9_presence/tests/test_session_continuum.py` | pure multi-bit pins |
| `bridge/tests/test_rwm_session_continuum.py` | seeded L0 integration |

```text
python scripts/rwm_session_continuum_cli.py build \
  --archive retina_kf_archive/cfb_rwm_live_10_1784953588 \
  --label cfb_rwm_live_10 --stamp 1784953588 \
  --ioid audits/ioid_edge_live_ceremony.json \
  --nov2-bind audits/rwm_bind_LIVE10.json \
  --out audits/rwm_continuum_LIVE10_stack.json

python scripts/rwm_session_continuum_cli.py verify \
  --continuum audits/rwm_continuum_LIVE10_stack.json \
  --archive retina_kf_archive/cfb_rwm_live_10_1784953588
```

## Live dogfood (2026-07-25)

Archive: `cfb_rwm_live_10_1784953588` (N=367 diverse panels; Edge `581a836c…`).

| Build | Verdict | Notes |
|-------|---------|-------|
| L0 + U1 display only | `OPTICAL_SESSION` | optical join alone |
| L0 + U1 + ioID ceremony | **`OPTICAL_IDENTITY`** | real Edge + tokenId 498 |
| L0 + U1 + ioID + NOV-2 none-bind | **`OPTICAL_IDENTITY`** + `stack_cited=true` | stack does **not** mint SYNCHRONIZED |

Artifacts: `audits/rwm_continuum_LIVE10.json`, `audits/rwm_continuum_LIVE10_stack.json`,
`audits/rwm_bind_LIVE10.json`, `audits/ioid_edge_live_ceremony.json` (public ids only).

## Explicit non-claims

- Does **not** advance `poep_enabled` / `L6B_ENABLED` / presence candidate mint
- Does **not** mutate 228B PoAC wire or FROZEN-v1 formulas
- Does **not** couple to daemon stop-path (fail-open composition remains offline)
- Does **not** prove re-encode, Path B device signatures, or stranger re-encode proof
- `stack_cited` is **not** a shortcut to `SYNCHRONIZED_CONTINUUM`

## Rails

- PV-CI 184 held (no new invariant)
- `CHAIN_SUBMISSION_PAUSED` untouched
- single-committer: operator
- No secrets in committed artifacts
