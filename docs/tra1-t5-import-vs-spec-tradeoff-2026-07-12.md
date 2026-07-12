# TRA-1 · T5 · Import `trio-retina` vs. spec-only — tradeoff + recommendation

**2026-07-12. OPERATOR DECISION cycle.** This doc lays out the tradeoffs and recommends; the decision
is the operator's. No code changes; no dependency added.

> **✅ DECISION (operator-confirmed 2026-07-12): Option C — phased.** QorTroller stays **spec-only** for
> the schema + commitment (layer ①, ours regardless — byte-stable, rail-guarded); `trio-retina` is
> imported as the **ENCODER** (layer ②) at **T6 when the card lands**. **No dependency added now;
> nothing to build until the card.** The candidate encoder-import seam is named in the recommendation.

## The reframing that makes this clean

It is **not** one binary ("QorTroller's code vs. MachineFi's library"). It is **two separable
layers**, and only the second is actually in question:

| Layer | What it does | Who should own it | In question? |
|---|---|---|---|
| **① Schema + commitment** (T1–T4) | validate `retina.event/0.1` + WorldState · canonicalize · **`VAPI-RETINA-STATE-v3` commitment** · the two rails (separation law, biometric floor) | **QorTroller — must stay ours** | **No** |
| **② Encoder / perception** | detect → track → embed → produce events + WorldState (DINOv2 / V-JEPA latents, YOLO, tracker, compose) | The hard part QorTroller lacks; **trio-retina's whole reason to exist** | **Yes** |

Layer ① **must** stay QorTroller-owned no matter what, for two non-negotiable reasons:
1. **Byte-stability of the commitment.** A committed artifact must be reproducible forever. Our
   canonicalization (sorted-key JSON) is pinnable; a third-party's internal serialization is not.
   Even if we import the encoder, we re-canonicalize its output ourselves before committing.
2. **The rungs trio-retina doesn't have.** It is *encoder-only* by design — no cryptographic
   verify, no consent, no separation-law rail, no biometric floor. Those are exactly our
   contribution. They stay ours as an overlay regardless of the encoder choice.

So the real question is narrow: **for layer ②, do we import `trio-retina`, and when?**

## Grounding — what each side actually is

**`trio-retina`** (Apache-2.0, `pip install trio-retina`, Python 3.10+, verified 2026-07-12):
- **core = numpy-only** (light): `Event` / `WorldState` / `validate()` / `event.schema.json` / the
  compose `|` pipeline / zone-line-count rules / IoU tracker / the `retina` CLI.
- **extras (heavy):** `[yolo]` → Ultralytics + torch · `[video]` → OpenCV (files/RTSP/webcam) ·
  embedders `DinoV2Embedder` (per-object `vec`) + `VJepa2Embedder` (scene `vec`) · `[all]`.

**QorTroller today (T1–T4, merged):** `retina_event_std.py` + `retina_worldstate_std.py` +
`compute_retina_state_commitment_v3` — pure stdlib, zero deps, byte-stable, rail-guarded, 53
tests green. It emits/validates the standard and commits it; it has **no detectors or embedders**
(the OBSERVATION perception is today a narrow custom killfeed-OCR path).

## The three options

| | **A — Spec-only forever** | **B — Import core now** | **C — Import encoder at T6 (phased)** |
|---|---|---|---|
| new deps now | none | `trio-retina[core]` (numpy) | none now; `[yolo]`+embedders at card |
| gets embedders/detectors | ✗ never | ✗ (core has none) | ✓ (DINO/V-JEPA, YOLO, tracker) |
| stays in sync w/ upstream spec | manual | ✓ automatic | ✓ (at adoption) |
| commitment byte-stability | ✓ (ours) | ✓ (ours, over lib output) | ✓ (ours, over lib output) |
| supply-chain surface added | none | small (numpy already present) | heavy — but **card-gated** |
| "first-class IoTeX consumer" | compatible/parallel | partial | ✓ strongest |
| decision-reversible | ✓ | ✓ | ✓ |
| refactors green T1–T4 code | ✗ | ✓ (wrap lib Event/WorldState) | ✗ now / seam only at T6 |

**Reading it:** Option A misses the embedders (the "deep-axis winners for free" that trio-retina's
own DESIGN.md sells) and the strongest positioning. Option B pays a refactor of *working, tested,
byte-stable* code to replace a ~150-line trivial schema — for a sync benefit on a 5-type spec that
rarely moves; low value now. Option C gets the real prize (the encoder + latent `vec` channel)
exactly when it's usable — the card, a real game detector — and keeps zero new deps until then.

## Recommendation — **Option C (phased): spec-owned commitment + encoder-imported at T6**

- **Now (this T5 decision):** **keep spec-only** — T1–T4 stay as the canonical *validate + canonicalize
  + commit* boundary. Add **no dependency**. The schema is trivial and already byte-stable + rail-
  guarded; replacing it today buys little and costs a refactor of green code.
- **At T6 (card):** **import `trio-retina` as the ENCODER** — `[core]` + `[yolo]` + the DINO/V-JEPA
  embedders — to produce the events + WorldState + the model-tagged latent `vec` channel that
  QorTroller genuinely can't cheaply build. Wire its output **through** QorTroller's boundary:

  ```text
  trio-retina encoder  →  events + WorldState  →  [QorTroller: validate + 2 rails +
       (detect/track/embed)                          canonicalize + VAPI-RETINA-STATE-v3]
  ```

  QorTroller supplies the game-specific detector/rules (killfeed/HUD → namespaced `x_qortroller.*`
  events per F-TRA0-2); trio-retina supplies the framework + the embedders.

**Rails that hold regardless of the choice:**
- The commitment is **always** computed over *QorTroller's* canonicalization, **never** the library's
  serialization (byte-stability). Pin the exact `trio-retina` version if imported.
- The **separation law + biometric floor stay as a QorTroller overlay** — trio-retina permits
  arbitrary custom fields and knows nothing of the humanity plane or the moat; our rails are the
  guard between its output and our commitment.
- The heavy extras (`[yolo]`/`[video]`/embedders → torch/opencv/ultralytics) are **card-gated**: no
  new supply-chain surface on the public repo until the card makes them useful.

## The upstream opportunity (name it, don't act on it)
QorTroller's three contributions — the **cryptographic verify rung** (`v3`), the **separation-law
rail**, and the **biometric floor** — are exactly the "read, log, and **verify**" + sovereignty
consumers trio-retina's DESIGN.md invites but does not build. They are candidate **upstream PRs** to
`machinefi/trio-retina` if a deeper IoTeX relationship is wanted. Strategic, operator-decided, later.

## Honest ceilings
- Everything here is **design**; no dep added, no code changed, PV-CI 182 untouched, TGE frozen.
- Option C's encoder import is **card-gated** (T6) — there is no live perception to feed it until then.
- The decision is **reversible** at every step (the boundary layer ① is the constant).

---
*TRA-1 T5 — tradeoff 2026-07-12; recommendation = Option C (phased). **DECIDED: Option C,
operator-confirmed 2026-07-12.** No dependency added now; QorTroller stays spec-only for
schema+commitment (layer ①, ours regardless), and imports `trio-retina` as the ENCODER (layer ②)
at T6/card. Nothing to build until the card. T5 CLOSED.*
