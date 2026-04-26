# WHAT_IF Entry -- AutoResearch Cycle 2 (2026-04-18)

**Source**: MCP autoresearch cycle 2 (Phase 228->229), AIT+HPSP failure synthesis
**Phase**: 228 -> 229 candidate
**Validation**: APPROVED (0 violations, 13 invariants checked)

---

## WIF-057 -- Haptic Metronome Synchrony Protocol (HMSP): DualShock Edge-Exclusive Cerebellar Timing Probe

**Source**: MCP autoresearch cycle 2 (Phase 228->229), decision synthesis from AIT+HPSP failure analysis
**Phase**: 228 -> 229 candidate
**Validation**: APPROVED (0 violations, 13 invariants checked)

---

**W1 -- Failure mode**: All self-paced and passive probes fail P2/P3 separation because P3 is structurally
non-stationary -- P3's intra-player centroid shifts with arousal state AND posture session-to-session.
AIT accel (P2vP3=0.365), HPSP phone-metronome (CV=0.5+, players not synchronizing), touchpad_corners
(0.401), tremor_resting (declined 1.177->0.689 N=27->42) -- all fail the same way. 4-feature
(tremor+postural) combination improves to P2vP3=0.916 but fails because P3's postural angle
varies by 150+ degrees session-to-session (sessions 002-006: roll~163deg; sessions 008-009: roll~-16deg).
Root cause: ANY probe requiring consistent voluntary behavior or posture from P3 accumulates
intra-player variance faster than inter-player distances grow.
Implication: tournament gate indefinitely blocked unless probe targets a postural-INDEPENDENT
biometric mechanism with external timing ground truth computable by the bridge.

**W2 -- Opportunity (HMSP)**: Bridge fires DualShock Edge haptic motor at exactly 2 Hz (500ms interval)
via HID output command during a 60s capture session. Player taps R2 once per haptic beat.
Bridge records both haptic_fire_timestamp_ms (bridge-side, authoritative) and R2_onset_timestamp_ms
(from HID report stream). Asynchrony = R2_onset - haptic_fire per tap is computed to sub-ms precision.
Features: mean_asynchrony_ms (anticipation/lag bias ~-20ms to +40ms), asynchrony_SD (synchrony
stability, target <30ms for clean data), phase_correction_gain (alpha of IBI correction model,
0.1-0.4 for humans), tap_rate_hz (should be 2.0+/-0.05 for valid sessions).
Cerebellar timing is subcortical and postural-independent -- does not change when P3 shifts grip
or leans differently. P2/P3 may differ in ANTICIPATION BIAS (some people consistently tap
15-20ms early, others late) and CORRECTION GAIN (how fast they resync after drift).
DualShock Edge-exclusive because: (1) requires haptic motor output via HID write -- no other
gaming controller supports sub-50ms haptic latency via USB HID; (2) bridge controls timing
ground truth -- competitor hardware has no equivalent internal metronomic cue with bridge-side
timestamp; (3) 1000 Hz USB polling enables sub-ms asynchrony measurement.
Phase candidate: Phase 229 (FIRST). Minimal code delta: HID haptic output + asynchrony feature
extraction. Does NOT modify BiometricFeatureExtractor hot path until N>=30 calibration.

**Key implementation details**:
- HID haptic output: DualSense output report 0x02 (USB) with vibration bytes at offsets 3-4
- Haptic profile: short (50ms) strong pulse at each 500ms beat mark
- Capture protocol: 5s countdown after haptic starts, 60s recording, 10 discarded warm-up beats
- Valid session gate: tap_count in [100,140] (120 expected); asynchrony_SD < 50ms
- 'hmsp' added to STRUCTURED_PROBE_TYPES (Phase 151 whitelist)
- New capture script: capture_hmsp_v2.ps1 (replaces capture_hpsp.ps1)

**Why HMSP solves what HPSP could not**:
- HPSP v1 CV=0.5+: players tapping freely, no reliable sync to phone metronome
- HMSP: bridge fires haptic at known timestamp; R2 onset is measured from same 1000Hz clock
- Asynchrony is COMPUTABLE to <1ms; no phone, no BPM confusion, no human-metronome latency
- Internal cue eliminates ~100-200ms perceptual delay of phone audio -> player ear -> motor response

**Status**: OPEN. Phase 229 FIRST candidate (replaces AIT as primary novel probe).
AIT sessions retained as training data for accel_tremor_peak_hz feature.