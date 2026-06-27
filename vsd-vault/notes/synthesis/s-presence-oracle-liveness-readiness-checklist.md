---
type: synthesis
id: s-presence-oracle-liveness-readiness-checklist
title: Minimal Presence-Oracle Liveness Readiness Checklist (NQPV certification path)
created: 2026-06-26T21:00:00Z
modified: 2026-06-26T21:00:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 30
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["s-nqpv-arc-overall-assessment", "s-presence-oracle-liveness-scope", "s-nqpv-persistence-presence-liveness-scope"]
---

# Minimal "Presence-Oracle Liveness Readiness Checklist"

For promoting NQPV from advisory (default-off) to a regime where the study harness can certify a separating operating point.

## Prerequisites (ALL must be true before promotion consideration)

### PoEP (Embodied Presence) Liveness
- [ ] L6B N >= 50 in-band reactions captured at 1000 Hz (CLAUDE.md hard rule).
- [ ] `poep_liveness_enabled=True` (operator two-key flag; deliberate, never auto).
- [ ] `poep_enabled=True` (or the activation path).
- [ ] Session verdict file present + fresh (`~/.vapi/poep_session_verdict.json`, max_age_s <= 7200s).
- [ ] `poep_present_signal(...)` returns non-None for live sessions (True=PRESENT, False=REJECT).
- [ ] Threaded into co-capture meta as `meta["poep_present"]` (via dualshock_integration + poep_activation).
- [ ] `poep_activation_status()` reports "ACTIVATED" in logs / status endpoints.

### Coupled-Retina Screen Witness
- [ ] Camera rig capturing both screen (HUD OCR) + controller motion at sufficient rate.
- [ ] `retina_game_capture` or equivalent live source active (WGC or equivalent).
- [ ] `latest_coupled_verdict()` produces "COUPLED_CLEAN" (or "LIVE_COHERENT" for non-auto-camera games).
- [ ] Controller-lobe signal kept as *metadata only* (never conflated with coupled presence).
- [ ] Wired into co-capture meta as `meta["retina_coupled_verdict"]` or `nqpv_retina_coupled_verdict`.

### Persistence & Co-Capture
- [ ] `nqpv_cocapture_enabled=True` (or equivalent live co-capture).
- [ ] `nqpv_cocapture_log` populated with `nqpv_poep_present` and `nqpv_retina_coupled_verdict` (non-null when oracles live).
- [ ] `get_nqpv_cocapture_rows(device_id)` returns rows usable by `nqpv_corpus_loader`.
- [ ] No drop of nqpv_* fields in `on_record` path.

### Measurement & Study
- [ ] Real human corpus breadth sufficient (N>=10 per player recommended from prior arcs; current assessment notes N=10 as feasibility).
- [ ] Study harness re-run on live-oracle regime: expects PASS (TAR >= best single-oracle + FAR envelope) + anti-GCAP rail holds.
- [ ] Operator review of harness output + ROC + weights/threshold.

### Operational
- [ ] `CHAIN_SUBMISSION_PAUSED=false` only for final promotion (test with paused first).
- [ ] Consent for the relevant category(s) granted by gamers.
- [ ] GIC_100 or equivalent integrity anchor present if using grind path.
- [ ] No blocking FSCA contradictions on the presence path.
- [ ] Public surface (`/player/presence-proof`, `VAPIPresenceProof`) updated to drop `advisory=True` / set `certified=True` only on promotion.

## Promotion Gate (operator two-key style)

1. All checklist items green + signed evidence (harness report, corpus snapshot, operator note).
2. Config flip: `nqpv_enabled` (or equivalent) + `poep_liveness_enabled`.
3. Ceremony: operator executes promotion script / manual steps with `--confirm` and exact phrase (mirrors invariant gate).
4. Post-flip: re-run harness on fresh data; monitor first N sessions for human-TAR.

**Status at creation of this note:** PoEP wiring + two-key logic exists (poep_activation.py + dualshock_integration). Coupled-retina is hardware-gated. Checklist items mostly "agent-buildable wiring + data" vs "operator/hardware campaign".

See related scope notes for full details. This is the minimal actionable checklist for the unlock identified in the NQPV arc assessment.
