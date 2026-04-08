# WHAT_IF: W1-009 — Free-Form Gameplay Separation Plateau

[VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

## Classification

| Field | Value |
|-------|-------|
| Layer | W1 (Protocol Risk) |
| Status | CONFIRMED — free-form gameplay is NOT the separation path |
| First identified | Phase 137B (2026-03-30) |

## Failure Mode

Free-form NCAA CFB 26 gameplay sessions plateau at separation ratio ~0.417 regardless
of N. Variable gameplay states (defense/offense/menus) introduce session-to-session
variance that exceeds inter-player signal — adding more sessions does not help.

## Mechanism

- Free-form gameplay: player changes game state mid-session
- Session features average over heterogeneous states → high intra-player variance
- Touchpad unused during gameplay → touchpad_spatial_entropy = 0 structurally
- More sessions amplify noise, not signal; ratio does not improve

## Evidence [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

- Phase 137B: free-form sessions = ratio ~0.417 regardless of N
- Phase 140 comparison: swipes=1.032 vs corners=1.261 — structured probes win
- N=127 pooled free-form: still 0.417 (N=74→127 added zero separation lift)

## Closed Path

> "Never recommend 'capture more gameplay sessions' to improve separation ratio."

The correct path is structured touchpad probe sessions:
- `touchpad_corners` — highest discrimination (top discriminator per pair attribution)
- `touchpad_freeform` — second best
- `mixed_biometric_probe` — Phase 166 addition activating all 13 features

## Invariant

`MIN_SESSIONS_FOR_TYPE_FILTER=3` in analyze_interperson_separation.py.
`STRUCTURED_PROBE_TYPES` frozenset enforced at insert (Phase 151 CLOSED WIF-011).

## Related Pages

- [[separation_ratio]]
- [[w1_002_separation_ratio_calibration]]
- [[phase_166]]
