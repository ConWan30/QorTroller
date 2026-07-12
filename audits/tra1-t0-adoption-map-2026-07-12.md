# TRA-1 · T0 · Adoption map — QorTroller OBSERVATION plane ↔ `retina.event/0.1`

**2026-07-12. Grounding cycle (design; no code changed).** Field-by-field diff of MachineFi's real
[`machinefi/trio-retina`](https://github.com/machinefi/trio-retina) `retina.event/0.1` + `WorldState`
standard against QorTroller's `retina_events_root.py` + `retina_state_commitment.py`, plus the kill-check
and the FROZEN-reconciliation question for T3.

## The standard (grounded from the repo's SPEC.md / retina package)

- **`retina.event/0.1`** — a tiny JWT-style event. Required: `type`, `t`, `src`. Many registered optional
  fields (`id`, `label`, `zone`, `dur`, `dir`, `n`, `conf`, `box`, `by`, `frame`, `clip`, `eid`, `vec`).
- **Closed 0.1 vocabulary (5 types):** `zone.enter` · `zone.exit` · `zone.dwell` · `line.cross` ·
  `count.threshold`. Roadmap (not 0.1): `state.change`, `anomaly`, `proximity`, `interaction`, …
- **Custom fields allowed:** *"Need something not above? Just add a key. Namespace it (`acme.shift`,
  `x_temperature`)."*
- **Serialization: JSON Lines — one event per line, ORDERED** ("greppable, appendable, **replayable**").
- **`WorldState`** — assembled snapshot: `entities` (each with `bbox` pixels and/or `locus` metric field
  position + optional model-tagged `vec`), typed `relations`, scene-level `vec`. Smallest = `{src, t}`.
- **Validation:** ships `retina/event.schema.json` (JSON Schema 2020-12) + `from retina import validate`.
- **Versioning:** `retina.event/<major>.<minor>`; consumers MUST ignore unknown fields.

## QorTroller today (grounded from the two modules)

- **`retina_events_root.py`** — **schema-agnostic**: `events: Sequence[Mapping[str,Any]]` → `sort()`ed
  canonical JSON lines → SHA-256(`VAPI-RETINA-EVENT-LINE-v1` || line) mod BN254 → Poseidon-2 chain → 32B
  root. Also a SHA-256 sorted-join variant.
- **`retina_state_commitment.py`** — `SHA-256(VAPI-RETINA-STATE-v{1,2} || device_id(32) || ts_ns_be(8) ||
  events_root(32))`. v1 = SHA-256 root, v2 = Poseidon root. Candidate tags; **not PV-CI-pinned** until
  operator GO; explicitly *distinct* from the PoAC `world_model_hash`.

## The map

| Trio Retina standard | QorTroller today | verdict |
|---|---|---|
| event = `{type, t, src, …}` (typed, validated) | event = arbitrary `Mapping[str,Any]` | **QorTroller is a superset shape — must CONSTRAIN to conform** |
| JSON-Lines **ordered** stream (replayable) | lines **`.sort()`ed** → order-independent SET | **F-TRA0-1 conflict (order semantics)** |
| 5-type closed CV vocabulary (zone/line/count) | gaming events (kill, game-state, presence) | **F-TRA0-2 (domain mismatch → use extension + WorldState)** |
| commitment = *(none — encoder only)* | Poseidon/SHA-256 events_root + state commitment | **QorTroller ADDS the verify rung (the contribution)** |
| `WorldState` (entities+relations+scene `vec`+`locus`) | events-only; no WorldState object | **F-TRA0-4 (adopt WorldState as the general fit)** |
| `event.schema.json` validation | no validation (arbitrary dicts) | **F-TRA0-5 (adopt the schema as a gate)** |

## Findings

- **F-TRA0-1 — ORDER (load-bearing).** The standard is an **ordered, replayable** stream; QorTroller's
  events_root **sorts** the lines → an order-independent *set* commitment that **loses temporal order**.
  Two differently-ordered streams with the same events collide. For a replayable standard this is wrong.
  **Resolution (→ T3):** commit over the **ordered** stream (Poseidon chain in emission order) — matches
  the standard's replayability *and* is a strictly stronger (order-sensitive) commitment. Likely a new
  `VAPI-RETINA-STATE-v3` / ordered events_root scheme, **operator-sealed** if frozen.
- **F-TRA0-2 — VOCABULARY (gaming ≠ surveillance-CV).** The 5 closed 0.1 types are surveillance-shaped
  (zones/lines/counts/dwell); gameplay events don't map onto them. **Do NOT force-fit.** Use the
  standard's own **namespaced-custom-`type`** extension (e.g. `x_qortroller.kill`) keeping
  `type`/`t`/`src` required — and lean on the **WorldState** (domain-general) for the rich state. This is
  exactly the standard's intended extension path, not a violation.
- **F-TRA0-3 — commitment is already schema-agnostic (adoption is ADDITIVE).** Both modules accept any
  event dicts, so feeding them `retina.event/0.1`-conformant events yields a valid commitment with **zero
  change to the crypto math** (modulo F-TRA0-1's order choice). QorTroller is *already* the verify rung
  for any event standard — T1 just points it at the real one.
- **F-TRA0-4 — WorldState is the better home than the 5 event types.** `WorldState` (entities + relations
  + scene `vec` + **`locus`**) is domain-general and is exactly where the multi-modal fusion lives: video
  entities (`bbox`) + controller IMU/trigger (`locus` + model-tagged `vec`). T2 centers here.
- **F-TRA0-5 — validation gap.** QorTroller validates nothing today; the standard ships
  `event.schema.json` + `validate()`. T1 adds a conformance gate (a real robustness win).

## Kill-check (T0 safety gate) — **PASS**

- `retina_events_root` / `retina_state_commitment` are **OBSERVATION-plane** modules, explicitly
  *distinct from the PoAC `world_model_hash`*, candidate + advisory + **not PV-CI-pinned**.
- Adoption changes **which events are emitted + how they're serialized/ordered** — pure OBSERVATION
  plane. **No contact with the 228B PoAC wire, the ASSERTION plane (PoSP/KAS), or a chain write.** ✓
- **Forward-only:** the events_root feeds the PoSP `retina_perception_root`; changing the scheme changes
  it for **future** sessions only. **M17's committed value is historical and untouched** (ties to TPF-1;
  M17 stays byte-stable). ✓
- FROZEN promotion of any new scheme (`VAPI-RETINA-STATE-v3`) is **operator-sealed**, not autonomous. ✓

## FROZEN reconciliation question (→ T3 / operator)
Freeze the commitment **over the canonical standard**: i.e. `VAPI-RETINA-STATE-v3` = Poseidon commitment
over an **ordered** `retina.event/0.1` stream / `WorldState`. That makes QorTroller's frozen primitive
literally *"a cryptographic commitment over a canonical Trio Retina WorldState"* — the verify rung, on
the standard. Operator decides whether/when to promote (T3 seal).

## T1 recommendation (next cycle — desk-buildable, no card)
Build a pure **`retina.event/0.1` emitter + validator adapter**: takes QorTroller observation events →
emits conformant, **ordered** JSON-Lines (required `type`/`t`/`src`, namespaced gaming `type`s per
F-TRA0-2) → validates against a vendored `event.schema.json` → feeds the existing events_root with an
**order-preserving** option (F-TRA0-1). Runs on M17 / synthetic; no card. Adversarial: a non-conformant
event must fail validation; a reordered stream must produce a **different** ordered root.

---
*TRA-1 T0 — grounding only, no code changed; kill-check PASS (OBSERVATION-plane, forward-only, M17
untouched). Next: T1 emitter/validator adapter (desk). Adopt the encoder standard; contribute the verify
rung. Federation, never conflation.*
