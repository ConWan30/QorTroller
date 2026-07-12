# TRA-1 · T6 — Live retina-standard wiring (card → `retina.event/0.1` + WorldState + v3 commitment)

**Scoped 2026-07-12. DESK scope — no card, no rig, no build yet.** T6 wires the live UVC capture
(now proven: C0 GO, authorship recall PROVEN, reader+daemon committed) into IoTeX's `retina.event/0.1`
standard + a WorldState frame + the **FROZEN-v1 `VAPI-RETINA-STATE-v3`** commitment, and joins that to
the ASSERTION plane under `session_id` (ties TRA-1 → TPF-1/PoSP).

## Grounded current state (what already exists vs. what T6 adds)

| piece | status | seam |
|---|---|---|
| Card → UVC → `_kf_bgr` ROI → RapidOCR → authorship oracle → verdict | **WIRED** (this session) | `qortroller_retina_capture.py` |
| PoSP `retina_perception_root` join | **populated LIVE** — but a **LUMEN-4a candidate** (sha256_v1 `compute_events_root`), *not* the standard/v3 | `retina_capture_daemon.py:305` `_issue_posp` (from `cmd_stop:451`) |
| `retina.event/0.1` emit (`make_event`, T1), WorldState (`make_worldstate`, T2), **v3** commitment (`compute_retina_state_commitment_v3` + `compute_worldstate_digest`, T3 FROZEN), ordered root (`ordered_events_root`) | **BUILT, tested — imported only by tests, NOT live-wired** | `bridge/vapi_bridge/retina_{event_std,worldstate_std,state_commitment,events_root}.py` |
| trio-retina encoder (Option C, T5) | **not imported** (decided: import at T6, deferred sub-step) | `pip install trio-retina` |

**So the gap is narrow and mostly desk-buildable:** turn the authorship the daemon already produces into
*conformant* events + a WorldState, compute the *FROZEN v3* commitment, and feed the *ordered/standard*
root into the PoSP join that LUMEN-4a already opened.

## Increments

| id | cycle | what it does | gate |
|----|-------|--------------|------|
| **T6.1** | **Killfeed authorship → `retina.event/0.1`** | adapter: own/other-kill rows (tonight's `killfeed_raw_reader`/oracle) → `x_qortroller.kill` events via `make_event` (namespaced custom type per F-TRA0-2; required `type`/`t`/`src`; killer/victim as `data`; **no asserting fields** — separation law). Ordered JSON-Lines. Tests over tonight's authorship output + the two rails (separation, biometric floor) refusing asserting/biometric fields. | **DESK ✓ (no card)** |
| **T6.2** | **Live WorldState frame** | `make_worldstate`: video entities (the kill events; perception entities later if the encoder is imported) + the controller as a **locus-only** entity (`controller_entity` — presence/input-space, **no biometric vec**). Validate (conformance + separation + biometric floor). **Honest gap:** the controller's input `vec` is gated on the ASSERTION plane (dual-connection-blind) → v1 WorldState = video/kill events + controller-**presence** locus, not a full input vec. | **DESK ✓** |
| **T6.3** | **FROZEN v3 commitment per session** | at session close: `compute_retina_state_commitment_v3(device, ts_ns, ordered_events_root(events), compute_worldstate_digest(worldstate))` → `audits/retina_state_v3_{session}.json`. Rails: **v3 formula FROZEN — untouched**; commit over QorTroller's *own* canonicalization. The cryptographic verify-rung over live observation. | **DESK ✓** |
| **T6.4** | **`session_id` join to the PoSP** | at `_issue_posp`: set `retina_perception_root` to the **ordered, conformant** events root (upgrading the LUMEN-4a sha256 candidate) and **reference** the v3 commitment as a **named parallel root**. §2.3 rail: the retina root stays a *named parallel* root, **never conflated** with the KAS/assertion root. This is the tri-plane join (TRA-1 ↔ TPF-1). | **DESK ✓** |
| **T6.5** | **trio-retina encoder import (Option C)** | `trio-retina[core]`+`[yolo]`+DINO/V-JEPA embedders → generic perception entities + latent `vec`, wired **through** QorTroller's validate+canonicalize+commit boundary. **DEFERRED** — the killfeed detector (T6.1) is the v1 encoder; import trio-retina when generic object perception earns its heavy deps. | **card-gated · OPTIONAL** |
| **T6.6** | **Live daemon wiring + validation** | wire T6.1–6.4 into `cmd_stop` (advisory, **default-off** flag; fail-open; parallels `_issue_posp`). Run over a live Warzone match: verify the event stream + WorldState + v3 commitment are produced + joined under `session_id` + rails hold. | **RIG (card, Warzone)** |

## Decisions (recommendations — operator decides)

- **D-T6-1 — v1 encoder = QorTroller's killfeed detector, not the heavy trio-retina import.** It already
  produces real `x_qortroller.kill` events; trio-retina (T6.5) adds generic perception *later*. Honors
  Option C ("import at T6") as a deferred sub-step, delivers a real standard+v3 stream cheaply now.
- **D-T6-2 — WorldState controller entity = locus-only / presence** (not a full input `vec`) until the
  ASSERTION plane's dual-connection-blind is resolved. Never export the biometric moat.
- **D-T6-3 — `retina_perception_root` = the ordered conformant events root** (upgrade the LUMEN-4a
  sha256 candidate); the **v3 commitment is referenced as a named parallel root**, not conflated.
- **D-T6-4 — emit at `cmd_stop`, advisory, default-off flag, fail-open** (parallels the KAS/PoSP path;
  never breaks capture).

## Honest ceilings
- **OBSERVATION-plane only.** No PoAC / 228B / chain / IOTX contact; **v3 is FROZEN** (formula untouched);
  the retina root is a **named parallel root** in the PoSP, never conflated with the assertion (§2.3).
- **Advisory, default-off.** Live validation (T6.6) is **rig-gated** on the next Warzone session.
- **Biometric floor + separation law** enforced on every emitted event and WorldState.
- **trio-retina heavy encoder deferred** (T6.5) — not on the T6-v1 critical path.
- **Buildable NOW (no card):** T6.1 → T6.4 — the bulk of T6, because it operates on the authorship the
  daemon already produces. **Rig-gated:** T6.6. **Optional/later:** T6.5.

## Why this is the right next build
The card unlocked OBSERVATION; tonight wired card → authorship. T6 makes that observation speak IoTeX's
*actual* retina standard **and** wear QorTroller's cryptographic verify-rung (v3) — turning a sha256
candidate join into a conformant, committed, sovereignty-owned perception root under `session_id`. It
is the "as-IoTeX-intended" completion of the arc, and ~4/6 of it needs no rig.

---
*TRA-1 T6 scope — 2026-07-12. Desk-buildable T6.1–T6.4 now; T6.5 optional/card-gated; T6.6 rig-gated on
Warzone. FROZEN v3 untouched; separation law + biometric floor hold; OBSERVATION-plane only. Nothing
built or committed here — scope only.*
