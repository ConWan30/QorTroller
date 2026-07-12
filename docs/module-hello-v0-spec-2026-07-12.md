# ModuleHello v0 — the QorTroller module-bus discovery handshake (spec)

**2026-07-12 · A2A-CDM build ① (grok Q1-P1..P4, grounded R05). SPEC ONLY — no wire implementation
ships until a second physical module exists (the capture card).** Design goal: **one schema covers
every module class forever** — new device types set new capability bits or a new plane value; the
schema itself never forks per module.

## The two messages

**1 · Hello** (module advertises, pre-session):

```json
{
  "schema": "qortroller-module-hello-v0",
  "session_id_hint": "",
  "module_role": "OBSERVATION_WITNESS",
  "plane": "OBSERVATION",
  "capability_bits": 12,
  "identity": { "scheme": "device_id_sha256", "value": "581a836c..." },
  "proto_min": 0, "proto_max": 0,
  "nonce": "<128-bit hex>", "ts_ns": 0, "sig": ""
}
```

**2 · SessionBind** (after the bus mints/collects `session_id` — late joiners welcome):

```json
{
  "schema": "qortroller-module-bind-v0",
  "session_id": "<sha256 join key>",
  "module_hello_hash": "<sha256 of the canonical Hello JSON>",
  "identity": { "scheme": "device_id_sha256", "value": "..." },
  "plane": "OBSERVATION"
}
```

Discovery ≠ session start: a venue rack or spectator device Hellos once, then Binds to each session
as it begins — **join-as-you-arrive, no module-specific protocol.**

## Identity dual-stack

`identity.scheme` ∈ `device_id_sha256` (today — the VMDR-registered controller hash and its module
siblings) · `did:io` (when devices gain ioID DIDs) · `none` (pre-provisioned bring-up only; a `none`
module can NEVER carry `CAP_HUMANITY_CLAIM`). One field, both eras — no schema break at ioID arrival.

## Capability bits (append-only registry; unknown bits IGNORED, never rejected)

| bit | name | legal plane |
|-----|------|-------------|
| 0 | `CAP_POAC_ASSERT` | ASSERTION only |
| 1 | `CAP_HUMANITY_CLAIM` | **ASSERTION only — bus MUST reject elsewhere (separation law at hello-time)** |
| 2 | `CAP_SCREEN_COMMIT` | OBSERVATION |
| 3 | `CAP_EVENTS_ROOT` | OBSERVATION |
| 4 | `CAP_DA_BULK` | AGGREGATOR |
| 5 | `CAP_BT_RF` | OBSERVATION |
| 6 | `CAP_OPTICAL_SCENE` | OBSERVATION |
| 7 | `CAP_VENUE_MULTI_SEAT` | OBSERVATION |
| 8 | `CAP_EDGE_AGG` | AGGREGATOR |
| 9 | `CAP_TO_CLOCK` | TIME |
| 10 | `CAP_W3S_VALIDATE` | any (validation is plane-neutral) |
| 11–31 | reserved: module classes | — |
| 32–63 | reserved: protocol | — |

`plane` ∈ {ASSERTION, OBSERVATION, MEANING, TIME, AGGREGATOR} — matches the tri-plane law; only
ASSERTION may ever claim humanity. The hello-time firewall is the **discovery-layer twin** of the
shipped manifest firewall (`tri_plane_manifest._ASSERTING_FIELDS`, proven under forge in TPF-1 F4).

## Versioning discipline (the anti-"v2-per-module" rules)

1. The `schema` string is the ONLY hard break — bump `-v0`→`-v1` only if a field's *meaning* flips.
2. `capability_bits` is **append-only by bit index**; this table is the registry; unknown bits are
   ignored, never rejected.
3. `module_role` strings are **append-only**; **unknown role → REJECT with `ROLE_UNKNOWN`**
   (**D-CDM-2 resolved 2026-07-12, Grounder recommendation adopted**: silently granting AGGREGATOR to
   an unknown role is a quiet capability grant — fail-closed matches house discipline).
4. Receivers MUST ignore unknown JSON keys (forward-compat).
5. This spec is **NOT a FROZEN-v1 cryptographic surface** — no domain tag, no commitment formula. If a
   Hello hash ever enters a sealed artifact, THAT commitment freezes under its own tag; the schema
   stays a protocol document.

## Rails

Separation law enforced at two layers (hello-time bit check + manifest-verify field check).
Provenance-not-truth unchanged — no capability bit claims content truth. Implementation is gated on a
second physical module (the card, CWL-1); until then this spec + the capability registry are the
deliverable. TGE frozen; no chain contact.

---
*A2A-CDM build ① — spec from grok R04 Q1-P1/P2/P3/P4 + Claude R05 grounding; D-CDM-2 resolved (reject
`ROLE_UNKNOWN`). Operator-paced; wire implementation is card-gated.*
