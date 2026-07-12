# Trio Retina Alignment Loop (TRA-1) — adopt IoTeX's real encoder standard on the OBSERVATION plane

**Drafted 2026-07-12.** An orchestrated loop to align QorTroller's OBSERVATION plane with **IoTeX
MachineFi's real, shipping [`machinefi/trio-retina`](https://github.com/machinefi/trio-retina) library**
— adopting its `retina.event/0.1` + `WorldState` standard — and positioning QorTroller as the
**cryptographic verify + sovereignty consumer** of that standard, plus the **humanity ASSERTION plane
Trio Retina deliberately doesn't have.**

> **The correction that opened this loop:** Trio Retina is not our naming — it is a genuine MachineFi
> Labs encoder standard (Apache-2.0, `pip install trio-retina`, actively developed) whose data model —
> *"one standard queryable stream of **events + latent state**"* — QorTroller's `retina_events_root` +
> `retina_state_commitment` already mirror. We built a parallel reimplementation; TRA-1 makes it an
> adoption + a contribution.

## Grounding (verified 2026-07-12, the real Trio family)

| repo | role | TRA-1 relevance |
|---|---|---|
| **`machinefi/trio-retina`** ★121, Apache-2.0 | the **encoder** of the world-model stack (`s = Enc(x)`) — model-agnostic `WorldState`; `retina.event/0.1` symbolic + model-tagged `vec` latent; numpy/CPU/edge | **the standard TRA-1 adopts** |
| `machinefi/trio-core` ★15 | real-time vision engine (YOLO + VLM + auto-calibration, REST) | optional runtime; not required to adopt the spec |
| `machinefi/trio-python` / `trio-examples` | SDK — "live streams → AI data sources" | closest analog to the MEANING plane; QuickSilver-adjacent (separate loop) |
| ~~`machinefi/trio-lumen`~~ | **does not exist (404)** | **"trio-lumen" is QorTroller's own MEANING-plane name — keep it, label it honestly as ours, NOT MachineFi** |

**The 1:1 mapping TRA-1 formalizes:**

| Trio Retina standard | QorTroller today | TRA-1 target |
|---|---|---|
| `retina.event/0.1` symbolic stream (`type`/`t`/`src` + optional) | `retina_events_root` (`VAPI-RETINA-EVENT-LINE-v1`, candidate) | emit the **real** format; commit over it |
| `WorldState` (entities + relations + scene `vec`; `bbox`/`locus`) | `retina_state_commitment` (`VAPI-RETINA-STATE-v1/v2`, candidate) | commit over the **standard** WorldState bytes |
| encoder = **state, never a verdict** | OBSERVATION plane = suggests, never asserts | **separation law hard-coded at the data layer** |

## North star

> **QorTroller = Trio Retina, made verifiable and gamer-owned — plus the humanity assertion plane it
> doesn't have.** Trio Retina produces state; it has *no* cryptographic verification, *no* consent, *no*
> on-chain provenance, and *no* humanity oracle. Those four rungs are exactly QorTroller's stack. We
> become the **verify + sovereignty consumer** of MachineFi's own encoder — a first-class member of the
> "multi-consumer wide L1" Trio Retina is explicitly designed for (`DESIGN.md`: consumers = *"rules,
> LLM, dynamics, humans, **audit**"* → a state you can *"read, log, and **verify**"*).

## The law (unchanged — and *reinforced* by adoption)

Trio Retina is **encoder-only by explicit design** (*"we say 'encoder,' not 'world model'… we forecast,
we don't control"*). It emits **state, never a decision.** That is the *same* discipline as QorTroller's
**observation may suggest; only assertion may claim.** Adopting the standard does not threaten the
separation law — it **hard-codes it into the wire format**, because the standard itself refuses to carry
verdicts. The humanity verdict stays cryptographic and on the controller, off the encoder. Federation,
not conflation.

## Cycle shape

```text
while not saturated and not operator_interrupt:
  1. Pick the next cycle (below)
  2. GROUND against the REAL trio-retina spec (retina.event/0.1 + WorldState), not our assumptions
  3. ADDITIVE only: adoption sits BESIDE today's behavior; our crypto layer sits ON TOP of the standard
  4. Kill-check every cycle: NO PoAC/228B/ASSERTION-plane/chain contact; FROZEN promotion is operator-sealed
  5. Verify (pytest + PV-CI 182) + bank + STAGE for operator commit
  6. Live cycles are RIG-gated on the capture card (CWL-1 handoff); desk cycles run on M17/synthetic now
```

## Backlog

| id | cycle | what it does | gate |
|----|-------|--------------|------|
| **T0** | **Ground the standard vs. our reimplementation** | **BANKED** — `audits/tra1-t0-adoption-map-2026-07-12.md`. Kill-check **PASS** (OBSERVATION-plane only; forward-only; M17 untouched). Findings: **F-TRA0-1** order (standard = ordered/replayable, ours = sorted *set* → commit ordered), **F-TRA0-2** gaming ≠ 5-type CV vocab (use namespaced `type` + WorldState), **F-TRA0-3** commitment already schema-agnostic → adoption is ADDITIVE, **F-TRA0-4** WorldState is the general fit + `locus`/`vec` fusion home, **F-TRA0-5** adopt `event.schema.json` validation | **DESK ✓** |
| **T1** | **`retina.event/0.1` emitter/adapter** | **BANKED** — `bridge/vapi_bridge/retina_event_std.py` (`make_event`/`validate_event`/`is_valid`/`to_jsonl`) emits + validates the **real** spec (required `type`/`t`/`src`, closed vocab + namespaced-custom `type` per F-TRA0-2, omit-empty). Order-preserving root `compute_events_root_poseidon_ordered` added to `retina_events_root` (**additive**; sorted behavior byte-identical). 11 tests incl. the **F-TRA0-1 adversarial proven in code**: ordered root is order-sensitive, legacy sorted root collides on reorder. 31 green; PV-CI 182 | **DESK ✓** |
| **T2** | **`WorldState` + `locus`/`vec` fusion channel** | **BANKED** — `retina_worldstate_std.py` (`make_worldstate`/`make_entity`/`make_vec`/`controller_entity`/`validate_worldstate`). Video entities = `bbox` + model-tagged visual `vec`; the controller = `locus` (input-space field subject), **no latent** (moat never exports). **Biometric floor** rail refuses `pre_processor.FORBIDDEN_COLUMNS` (test pins it in sync) + separation law (T4) over the whole state. Fusion demo `scripts/tra1_worldstate_fusion_demo.py` → committed example `audits/tra1-t2-fusion-worldstate-example.json` (video+controller+scene, both rails PASS). 11 tests (47 retina suite); PV-CI 182. **Live IMU+video fusion card-gated (T6)** | **DESK ✓** |
| **T3** | **The VERIFY rung (QorTroller's contribution)** | **BANKED (mechanism + real artifact)** — `compute_retina_state_commitment_v3` (`VAPI-RETINA-STATE-v3` **CANDIDATE**): commits the **ordered** events root (F-TRA0-1) + binds the **WorldState** frame; rail-guarded (conformance + separation law + biometric floor all refuse BEFORE commit). **Real Poseidon commitment computed** (`72724e74…`; `audits/tra1-t3-state-v3-example.json`). 6 forge tests (order-sensitive · WorldState-tamper-caught · asserting/biometric-refused · distinct-from-v2). 53 retina suite; PV-CI 182. **⏸ FROZEN-v1 promotion (PV-CI pin + allowlist) HELD FOR OPERATOR SEAL — never autonomous** | **DESK ✓ · SEAL ⏸ operator** |
| **T4** | **Separation-law conformance check** | **BANKED** — `separation_law_problems`/`emits_state_only` in `retina_event_std.py`: no `retina.event`/WorldState entity may carry an asserting/humanity field (`verdict`/`presence_score`/`humanity`/`eligible`/`poac`/`kas`/…). Enforced **fail-closed on emit + serialize + commit** (`make_event`/`to_jsonl`/`ordered_events_root` all refuse); scans nested WorldState `entities`/`relations`. 6 tests incl. cross-layer proof (tri-plane manifest `_ASSERTING_FIELDS` ⊆ the rail). 37 green; PV-CI 182 | **DESK ✓** |
| **T5** | **Adoption decision — import vs. spec-only** | **TRADEOFF DRAFTED** — `docs/tra1-t5-import-vs-spec-tradeoff-2026-07-12.md`. Reframed as two layers: ① schema+commitment+rails (stays QorTroller-owned regardless), ② encoder/perception (the only thing in question). **Recommend Option C (phased): spec-owned commitment now + import `trio-retina` as the ENCODER at T6/card** (DINO/V-JEPA embedders + heavy deps card-gated). Rails hold regardless (commit over *our* canonicalization; separation+biometric overlay). Upstream-PR opportunity (v3 verify rung + rails → `machinefi/trio-retina`) named. **✅ DECIDED: Option C (operator-confirmed 2026-07-12)** — no dependency added now; encoder import at T6/card | **DECIDED ✓** |
| **T6** | **Live conformance (CWL-1 handoff)** | with the card: run the encoder over live capture, emit conformant `retina.event/0.1`, verify-rung commits it, cross-check with the ASSERTION plane under `session_id` (ties to TPF-1) | **RIG (card)** |

## Honest ceilings

- **OBSERVATION plane only.** No PoAC / 228B wire / ASSERTION-plane / chain contact; FROZEN promotion is
  operator-sealed. Adoption is **additive** — today's behavior stays until a cycle explicitly swaps it.
- **Adopt the *spec* first (cheap, high-alignment); importing the *library* is T5's operator decision.**
- **`trio-lumen` is ours, not MachineFi's** — TRA-1 does not touch the MEANING plane; a QuickSilver /
  `trio-python` "data source" integration is a separate future loop.
- **The multi-modal fusion is card-gated for live** — T1–T4 run on M17/synthetic now; T6 needs the card.
- **We contribute verify + sovereignty + assertion; we do not claim the encoder** — Trio Retina owns the
  encoder rung; we ride its winners (DINOv2/V-JEPA) for free and add the rungs it doesn't do.
- Audio stays dropped (BIPA/GDPR sovereignty). PV-CI 182 every cycle. TGE frozen.

## Why this is the real alignment

Every prior loop this arc (TPF-1, CWL-1, A2A-CDM) treated the OBSERVATION plane as *ours*. TRA-1 corrects
that: the OBSERVATION plane has a **real IoTeX standard**, and QorTroller already mirrors it. Adopting
`retina.event/0.1` stops a parallel reinvention, plugs QorTroller into MachineFi's actual encoder
standard as its **verify-and-own consumer**, expresses the controller+card fusion in that standard's own
`locus`/`vec` channels, and does it all while *hard-coding* the separation law into the wire format. It
is the most "as-IoTeX-intended" move available — and it makes QorTroller's defining rungs (crypto verify,
gamer sovereignty, humanity assertion) the exact things MachineFi's encoder is missing.

---

*TRA-1 orchestrator — drafted 2026-07-12. Operator-paced; T0–T4 desk-buildable on M17/synthetic now,
T6 card-gated (CWL-1 handoff); FROZEN promotion + any deploy operator-sealed. Adopt the encoder standard;
contribute the verify rung. Federation, never conflation.*
