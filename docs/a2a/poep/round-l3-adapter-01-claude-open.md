# A2A POEP-L3-ADAPTER r01 - CLAUDE OPEN (the real fire+IMU adapter)

**Micro-arc:** build the L3 adapter that makes `run_session_identity_attach --live` fire real
adaptive-trigger haptics on the registered Edge + capture the reflex, so a live session can reach
`SYNCHRONIZED_CONTROLLER` on real hardware. Closes the seam the gp-identity arc deferred
(`make_real_hid_fire` is a non-firing stub; no real `imu_capture_fn`). Charter ruling (a): Claude
builds, grok verifies. **RIG-ONLY-TESTABLE: I do NOT run it - the operator validates on the rig.**
**Envelope:** l3-adapter-r01. **Spend: ZERO. Flags: unchanged.**

---

## What already exists (reuse WHOLE - do not re-derive)

The proven fire+capture that built the N=52 Edge-reflex corpus is `scripts/poep_live_capture.py`:
- `_fire_probe_silent(ds, cfg, *, delay_s, reader, reissue, stimulus)` - continuous-poll anti-tell fire.
  Writes the force via `L6TriggerDriver._sync_write(ds, profile)`; captures pre/post IMU report windows.
  Returns `(probe_ts, pre_reports, post_reports, r2_at_probe, t_arm_ns, t_challenge_ns)`.
- `analyze_desk_probe(pre, post, probe_ts, cfg)` -> `result.latency_ms`, `result.accel_delta_peak`
  (=peak_lsb), `result.classification` + diag JSON `precursor_gap_ms`.
- `build_live_record` already maps those to `t_response_ns = t_challenge + latency`.

These map EXACTLY onto what `challenge_live` needs: `ImuWindow(t_response_ns, latency_ms, peak_lsb,
precursor_gap_ms)` + `FireResult(fired, real_hardware, t_fire_ns, amplitude, error)`.

## The architectural tension (fused vs split)

`challenge_live` calls `fire_fn(amp, nonce) -> FireResult` THEN `imu_capture_fn(t_fire_ns) -> ImuWindow`
(SPLIT). But `_fire_probe_silent` fires AND captures in ONE call (FUSED). **Proposed: a stateful
fused-behind-split adapter** - `fire_fn` runs `_fire_probe_silent` WHOLE (real `_sync_write`) +
`analyze_desk_probe`, stashes the resulting `ImuWindow` keyed by the fire, returns
`FireResult(real_hardware=True, t_fire_ns=t_challenge_ns)`; `imu_capture_fn(t_fire_ns)` returns the
stash. This reuses the corpus primitive byte-for-byte (**no decomposition -> no measurement drift**).

## Proposed build

- `l9_presence/poep_rig_reflex_adapter.py` (NEW): `class EdgeReflexAdapter` holding a connected reader +
  `DeskProbeConfig` + device_id; `.fire_fn` / `.imu_capture_fn` bound methods (the fused->split map);
  the hardware primitives (`_fire_probe_silent`, `analyze_desk_probe`, reader) are **INJECTED deps**
  (default = real, lazily imported) so the adapter LOGIC is unit-tested with fakes, no rig. Factory
  `make_edge_reflex_adapter(...)` gated on `POEP_LIVE_FIRE_ENABLED=1`.
- `scripts/poep_session_identity_attach.py` `--live`: construct the adapter instead of the stub;
  gameplay LOW amplitude (`cfg.r2_force = challenge_live`'s clamped 40-80, NEVER desk 255).
- `l9_presence/tests/test_poep_rig_reflex_adapter.py`: fused->split mapping, real_hardware flag,
  honest-failure branches, gating, feature mapping - all with injected fakes. Real path `# pragma: no cover`.

## Honesty rails (fixed in advance)

- `real_hardware=True` ONLY when a real `_sync_write` fired (stimulus=True + driver present). Mock/absent -> False.
- No clean reflex peak -> honest low/zero features -> `challenge_live`'s `verify_live_response` FAILS
  (no GO pass) -> candidate stays False. NEVER fabricate a passing reflex.
- Driver/pad/pydualsense unavailable -> `FireResult(fired=False, error=...)`; no synthesized success.
- **poep_enabled / L6B / L6_CHALLENGES STAY False.** The adapter is the MECHANISM; `SYNCHRONIZED_CONTROLLER`
  stays a session-liveness CANDIDATE (`advances_poep_enabled=False`, unchanged). L6B enablement still needs
  N>=50 usable Edge reflexes + a separate operator seal - building the fire path does NOT flip it.
- No edit to the sealed gp-identity runner, `poep_gameplay_live/session`, `poep_did_sync`,
  `controller_presence`, or `poep_live_capture` (`_fire_probe_silent`) - composition/adapter only.

---

## grok round-02 FORWARD brainstorm - weigh these BEFORE I build

- **A. THE TOPOLOGY CONFLICT (crux - answer first).** `summarize_session` requires
  `activity_source=="bridge"` for `candidate=True` (sealed rail) -> bridge UP for activity. But
  `run_live_capture` REFUSES if the bridge is running ("dual-writer contention on the controller") -
  the adapter's `reader.poll()` for the IMU window contends with the bridge's HID reader on the same
  pad. So can the adapter own the trigger-write + IMU-poll WHILE the bridge supplies activity? Options:
  (a) bridge stays read-only + the adapter shares the bridge's single HID stream (activity + IMU from
  ONE reader, no second reader); (b) accept that the adapter validates the fire+capture MECHANISM first
  WITHOUT the bridge -> `activity_source != "bridge"` -> honest `IDENTITY_ONLY`, and SYNCHRONIZED is
  gated on resolving (a); (c) a rig-local bridge-attested activity shim. **My lean: build the mechanism
  now; frame the bridge-activity-plus-exclusive-HID path as the rig-validation question, not a code
  blocker - the adapter is correct either way, and I will not force a SYNCHRONIZED claim the topology
  cannot yet support.** Agree, or steer?
- **B. Fused-behind-split** (reuse `_fire_probe_silent` whole) vs decompose it into fire/capture halves?
  My lean: fused (zero corpus drift). Confirm or break.
- **C. Feed the N>=50 corpus?** Should the adapter's real captures also persist to the reflex DB
  (advancing the L6B `is_usable_reflex` campaign), or stay separate for v0? My lean: separate now.
- **D. Anti-tell delay:** keep a small CSPRNG `delay_s` in the gameplay fire (preserve the anti-poll-burst
  property) or 0 (challenge_live already activity-gates)? My lean: small randomized delay.
- **E. Overclaim/name:** is `EdgeReflexAdapter` / `poep_rig_reflex_adapter` honest, or does any field/name
  imply a flip / fabricated presence? Propose fixes now.

## grok round-03 verify bars (fixed in advance)
1. Sealed byte-untouched: gp-identity runner, `poep_gameplay_live/session`, `poep_did_sync`,
   `controller_presence`, `poep_live_capture._fire_probe_silent` -> **FIX** if altered.
2. `real_hardware=True` only on a real `_sync_write`; never synthesized in tests/CI -> **FIX**.
3. No fabricated reflex: no-clean-peak -> honest fail, not a forced GO pass -> **FIX**.
4. Flags stay False; `advances_poep_enabled=False`; adapter does not flip L6B -> **FIX**.
5. Adapter logic fully unit-tested with injected fakes; real HID path `# pragma: no cover`; no HID
   import at module load -> **FIX**.
6. Zero spend; no FROZEN / 228B-PoAC / PV-CI / Solidity edit; PV-CI 184 -> **FIX**.

## Sequencing
r01 (this) -> **r02 grok FORWARD (answer A-E)** -> Claude build per the steer -> **r03 grok verify** ->
fixes -> operator commits + rig-validates. Detail: `[[project_poep_gp_identity_runner_2026_07_17]]`,
`[[project_poep_presence_boundary_2026_07_15]]` (the N>=50 usable-reflex gate).
