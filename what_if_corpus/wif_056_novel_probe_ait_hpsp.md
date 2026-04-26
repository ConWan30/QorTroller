# WHAT_IF Entry -- AutoResearch Cycle 1 (2026-04-18)

**Source**: MCP autoresearch cycle 1 (Phase 228), synergistic tools:
  vapi_protocol_state + vapi_what_if + vapi_validate_proposal + vapi_autoresearch_seed + vapi_query_what_if
**Phase**: 228 -> 229 candidate
**Validation**: APPROVED (0 violations, 13 invariants checked)

---

## WIF-056 -- Structural Probe Non-Stationarity: Self-Paced Probes Fail as P3 Centroid Drifts

**W1 -- Failure mode**: Both tremor_resting (1.177->0.689, N=27->42) and touchpad_corners
(1.261->0.728, N=11->35) show structural ratio DECLINE as corpus grows. Root cause: P3
intra-player Mahalanobis variance=1.154 -- P3 centroid shifts session-to-session because all
current probes are self-paced or passive. Adding more sessions of same probe type accelerates
ratio decline. Indefinite TGE blocker if probe type unchanged.

**W2A -- HPSP (Phase 230)**: Haptic-Paced Sensorimotor Synchrony Protocol. External 2 Hz
metronome (phone or L6 haptic), player taps R2 in sync (120 taps / 60s). Features:
mean_tap_asynchrony, asynchrony_sd, phase_correction_gain, synchrony_index. Cerebellar timing
is subcortical -- independent of P3 behavioral variability. P2/P3 separates because cerebellar
timing is individual-specific even when passive grip signatures overlap.

**W2B -- AIT (Phase 229 FIRST)**: Active Isometric Trigger Tremor. Player holds L2 at ~50%
(analog ~127) for 30s. L2 analog FFT (4096-point, 4-15 Hz search). task_tremor_peak_hz +
task_tremor_band_power. Motor unit synchronization frequency is anatomically-fixed, more stable
than resting tremor which varies with sympathetic arousal state. Extends existing AccelTremorFFT
pipeline (Phase 205/213) to L2 domain. Minimal code delta.

**Invariants preserved**: Wire format unchanged; L4 thresholds unchanged (new features added to
analysis only, not hot-path until N>=30 calibration complete); no frozen constants modified.

**Status**: OPEN. AIT Phase 229 candidate. HPSP Phase 230 candidate.
