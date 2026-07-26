# Retina Enhancement Scope — 2026-07-25

> **STATUS:** Scoping record, NOT a directive. Captures findings from the
> Holoscan + un-accelerated-pivot enhancement proposals so the next time
> someone (operator, agent, or A2A round) proposes a retina sidecar, the
> work doesn't re-scope what's already in the tree. Concludes with a
> FROZEN-producer no-go gate that any sidecar variant must satisfy.
>
> This document's existence is the totality of what was built this arc.
> No code was authored. The operator's decision was "drop the spike
> entirely -- given how much retina infra already exists, the
> enhancement isn't worth pursuing vs running player 2 first."

## What was proposed

Two-stage enhancement directive. Stage 1: NVIDIA Holoscan GPU-accelerated
Trio-Retina fusion sidecar (`bridge/vapi_bridge/retina_screen_lobe.py` +
Holoscan DAG). Stage 2 pivot: CPU-only fallback after a Holoscan hard wall,
using `pytesseract` OCR + `cv2.calcOpticalFlowFarneback()` via `asyncio.to_thread`,
throttled at 2 Hz OCR / 10 Hz optical flow.

Both stages proposed to author the following files fresh:
- `bridge/vapi_bridge/frame_grabber.py` (new)
- `bridge/vapi_bridge/retina_causal_coherence.py` (new `assess_coherence` impl)
- A 32-byte `VAPI-RETINA-STATE-v1` commitment producer in the sidecar
- A `RETINA_PERCEPTION_ENABLED` config knob

## Findings against the live tree on `origin/main @ 9ee7273a`

### Finding 1 — `retina_causal_coherence.py` already exists and is sealed

`bridge/vapi_bridge/retina_causal_coherence.py` already exports, on `main`
today, `assess_coherence`, `from_controller_events`, `from_screen_events`,
`CoherenceVerdict`, `CoherenceReport`, `OutcomeMatch`, `TimedEvent`,
`CoherenceConfig`. The exact event tokens the directive proposed to
implement are already in the tree:

- `controller.trigger.onset` at `retina_causal_coherence.py:31`
  (the R2 sprint / L2 snap / pass / kick action token)
- `scene.down_advanced`, `scene.first_down`, `scene.score_changed`,
  `scene.playclock_reset`, `scene.quarter_changed` at
  `retina_screen_lobe.py:28-32`

`retina_screen_lobe.py` already implements `parse_hud`, `diff_hud`,
`is_input_caused`, `HudState`, `ScreenEvent`, and the `provisional=True`
honesty rail for OCR-noisy scoreboard reads (`:16, :44-45, :59, :107`).

**Implication:** "Author `retina_causal_coherence.py` to implement
`assess_coherence`" is not a green-field task. It is a re-write of a
sealed fusion core and would require operator seal, not an autonomous
"yes." The directive as-written conflates porting a runtime (legitimate)
with re-architecting a sealed module (no-go).

### Finding 2 (BLOCKER — the FROZEN producer gate, unchanged by the Holoscan→CPU pivot)

`VAPI-RETINA-STATE-v1` is a FROZEN upstream commitment domain tag.

- `bridge/vapi_bridge/retina_state_commitment.py:18`:
  `DOMAIN_TAG = b"VAPI-RETINA-STATE-v1"`
- `bridge/vapi_bridge/retina_state_commitment.py:19-20`:
  `DOMAIN_TAG_V2 = b"VAPI-RETINA-STATE-v2"` (Poseidon events_root off-chain)
- `bridge/vapi_bridge/retina_state_commitment.py:24-28`:
  `DOMAIN_TAG_V3 = b"VAPI-RETINA-STATE-v3"` (TRA-1 T3 CANDIDATE, then
  PROMOTED to FROZEN-v1 PATTERN-017 verify-rung by operator seal 2026-07-12)
- `.github/INVARIANTS_ALLOWLIST.json:714-716`: `INV-RETINA-STATE-V3` is
  pinned FROZEN-v1 in the live PV-CI gate (counted in 184):
  `SHA-256(VAPI-RETINA-STATE-v3 || device_id(32) || ts_ns_be(8) ||
  ordered_events_root(32) || worldstate_digest(32))`. Allowlist gloss:
  *"Domain tag + preimage structure are frozen; any change requires v4.
  OBSERVATION-plane; 228B PoAC wire unchanged."*

The directive's "Phase 3: Output the 32-byte VAPI-RETINA-STATE-v1
commitment hash for the session log" instructs the sidecar to PRODUCE
the FROZEN primitive. That is a FROZEN-break regardless of whether the
runtime is Holoscan or `asyncio.to_thread`. The Holoscan→CPU pivot of
the second directive did not address this; it carried the stopper
forward unchanged.

### Finding 3 — the entire Phase 1 capture stack already lives in `l9_presence/`

The Phase 1 task "Author `bridge/vapi_bridge/frame_grabber.py` using `mss`
or WGC" duplicates six existing modules:

- `l9_presence/screen_capture.py` -- screen capture surface
- `l9_presence/hud_ocr.py` -- OCR layer (NCAA CFB 26 HUD elements)
- `l9_presence/killfeed_ocr_bootstrap.py` -- killfeed OCR bootstrap
- `l9_presence/cv_motion.py` -- optical flow (`cv2.calcOpticalFlowFarneback`)
- `l9_presence/killfeed_cv.py` -- CV killfeed layer
- `l9_presence/session_recorder.py` -- session recorder
- `bridge/vapi_bridge/qortroller_retina_capture.py` -- retina capture glue
- `bridge/controller/probe_screen.py` -- the HUD probe already used by
  the EyeCheck + F-MATCH-2 source gates

Authoring a new `bridge/vapi_bridge/frame_grabber.py` entrypoint would
fragment the existing capture surface and route around the F-MATCH-2
wrong-eye finding (2026-07-13: webcam uvc_index had persisted wrongly;
two sessions watched the operator's room; caught by the EYE-CHECK
PROTOCOL). The F-MATCH-2 fix was specifically about routing all capture
through the verified-source gate. A new capture entrypoint on a
different path is structurally a regression on a sealed finding.

### Finding 4 — the `retina_perception_enabled` config knob already exists

The Phase 1 task "Ensure `retina_perception_enabled=false` remains the
default config" duplicates existing config:

- `bridge/vapi_bridge/retina_perception.py:4`:
  *"Default OFF -- `retina_perception_enabled=False` until operator enables."*
- `bridge/vapi_bridge/retina_pda_attestation.py:10, :44, :61, :67`:
  `RETINA_PERCEPTION_OBSERVATION` attestation lane is already wired

### Finding 5 — F-RIG27 PCC stall hygiene already auto-kills on rate drop

The Phase 3 "INV-PCC-001: if `poll_rate_hz` drops below 990 the Screen
Lobe must auto-kill" rail is structurally the same stall-detect + heal
pattern F-RIG27-1 already shipped on `main`:

- `bridge/vapi_bridge/dualshock_integration.py:3290`:
  `_PCC_STALL_ITERS = 3` (consecutive zero-delta iters, frames flowing,
  before stall confirms)
- `:603`: `_hid_counter_silent_iters = 0`
- `:3326-3333`:
  silent-counter inc/dec + heal when `>= _PCC_STALL_ITERS`
- Honest DEGRADED fallback (`bridge/vapi_bridge/dualshock_integration.py:_pcc_rate_feed`),
  never fabricated 0 / fabricated NOMINAL.

The rail the directive proposes is a valid pattern; it exists already
for the controller-input side. A sidecar auto-kill wiring would be net
new as a *binding* (sidecar-supervisor consumes PCC state) but it is NOT
net-new as a *hygiene primitive*.

### Finding 6 — Phase 235-EVENTLOOP already mandates the CPU-safety pattern

The directive's §1 "Every call to `pytesseract.image_to_string()` or
`cv2.calcOpticalFlowFarneback()` MUST be wrapped in `asyncio.to_thread()`"
restates Phase 235-EVENTLOOP (CLAUDE.md hard rule):
- Long-running sync work MUST move to `asyncio.to_thread` or
  `loop.run_in_executor(None, fn)` -- not just `async def` wrap.
- Index coverage on high-cardinality tables mandatory before production.
- 10-second HTTP timeout on zero-DB endpoint = signature of event-loop
  stall.

Same shape as Arc 7 ML-DSA signing on Thread C
(`_run_mldsa_signing(matrix)` via `await asyncio.to_thread`).

## The FROZEN-producer no-go gate

Any future retina sidecar variant MUST satisfy this constraint:

```
The 32-byte VAPI-RETINA-STATE-v1/v2/v3 commitment MUST be produced by
the sealed Python path on the bridge side (retina_state_commitment.py).
A sidecar (Holoscan, asyncio.to_thread, anything) MAY be an INPUT
producer -- it MAY compute witness hashes that the bridge binds into
the frozen preimage. The sidecar MUST NOT be the PRODUCER of the
VAPI-RETINA-STATE-vN tag itself.

Rationale:
- INV-RETINA-STATE-V3 is pinned FROZEN-v1 in .github/INVARIANTS_ALLOWLIST.json
  (counted in the PV-CI 184 baseline). An autonomous change to the
  producer path moves PV-CI off 184 and is an operator-gate violation
  per the CLAUDE.md hard rules.
- retina_state_commitment.py is the producer; the W3bstream applet
  (w3bstream/applet/src/lib.rs) verifies the producer's output. Moving
  the producer off the bridge breaks the bridge->W3bstream verify
  contract at INV-W3S-005 (non-zero PQ commitment) and INV-RETINA-001/002.
```

A sidecar variant that satisfies this gate is architecturally
defensible. The two directives this arc both violated it; the
no-go-decision was the correct operator call.

## What would actually be net-new and autonomously buildable

If a future operator-approved retina sidecar spike is unblocked, the
green-path surface is exactly these three components -- no FROZEN, no
sealed-module rewrites, no PV-CI count move, no operator-flags flipped:

1. **`CaptureThrottle` class** -- hard rate-limiter enforcing the
   operator's chosen ceilings (2 Hz OCR / 10 Hz optical flow) on the
   EXISTING `l9_presence/` capture stack. Wired via the existing
   `retina_perception_enabled` knob into the existing sidecar
   supervisor. Default-off. ~50 lines + tests; no FROZEN/PoAC/228B.

2. **`WitnessHashBind`** -- a sidecar-side producer of a *witness hash*
   that the bridge-side sealed `retina_state_commitment.compute_retina_state_v1`
   path BINDS into its preimage as an input ONLY. The sidecar is
   never the producer of `VAPI-RETINA-STATE-v1`. Tests assert the
   sidecar output cannot carry framebuffer pixels or unsanitized L4
   vectors (the Phase 3 FORBIDDEN_COLUMNS rule, made into a
   Python-level enforcement).

3. **`PccRateAutoKillWire`** -- wires the existing `_PCC_STALL_ITERS`
   stall hygiene into the sidecar supervisor: if `poll_rate_hz < 990`
   while `retina_perception_enabled=True`, auto-kill the sidecar.
   Reuses F-RIG27 hygiene; does NOT author over it. Unit-tested by
   injecting a rate-drop into the sidecar supervisor.

All three are spike-grade work, bridge-side under `bridge/vapi_bridge/`,
rig-runnable via the existing `l9_presence/` capture stack without a
GPU. None touches the FROZEN producer path. 0 IOTX, 0 invariant count
move, no operator flags flipped.

## Operator decision (recorded verbatim)

> "Drop the spike entirely -- given how much retina infra already
> exists, the enhancement isn't worth pursuing vs running player 2
> first."

The operator chose the second-human grind session (live rig signal,
irreplaceable) over the proposed retina enhancement. This is the
integrity-preserving call: N=1 ceiling break > speculative sidecar.

## Signed

Authored by the agent (Claude Code session 2026-07-25) after the operator
proposed two retina enhancement directives (Holoscan GPU + CPU-only
pivot). Both directives were scoped against the live `main @ 9ee7273a`
tree. The stopper was identical in both: the FROZEN-producer gate on
`VAPI-RETINA-STATE-v1`. No code was authored; no FROZEN primitive was
modified; no operator-gated flag was flipped; no invariant count moved
off 184; 0 IOTX was spent; `bridge/.env` kill-switch untouched. The
findings above are the deliverable.
