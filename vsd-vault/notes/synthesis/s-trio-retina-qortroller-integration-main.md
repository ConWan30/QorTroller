---
type: synthesis
id: s-trio-retina-qortroller-integration-main
title: Trio-Retina integration on QorTroller main (Phase 3)
created: 2026-06-22T00:00:00Z
modified: 2026-06-22T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 60
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-trio-retina-main-protocol-docs", "c-trio-retina-advisory-second-oracle", "s-purpose-of-vapi"]
---

## Summary

Trio-Retina in QorTroller is a **DePIN-governed, default-OFF advisory perception sidecar**: certified HID windows → Trio-Retina-shaped events → `retina_state_commitment` cross-linked to PoAC records, surfaced to operators/adjudicator/FSCA, with optional W3bstream/DA/PDA rails. It preserves gamer sovereignty and the FROZEN PoAC record.

## Data path (main)

```
DualSense Edge HID (dualshock_integration, ~120-frame ring @ ~1 kHz)
  → retina_depin_policy (Edge / PCC / poll-rate qualifiers)
  → retina_perception.run_controller_perception → retina_controller_embedder
  → retina_state_commitment + events_root (SHA-256 v1 or Poseidon v2)
  → Store.retina_event_log (+ optional DA / PDA / W3bstream)
  → pitl_meta advisory fields + SessionAdjudicator evidence_json.retina
  → FSCA cross-oracle MEDIUM contradictions vs L4
```

## Operator surfaces

- Policy/status: `GET /bridge/retina-policy-status`, `/bridge/retina-status`, `/bridge/retina-alerts`
- Evidence slice: `GET /agent/retina-evidence-slice` (mirrors adjudicator binding)
- Disarm: `POST /operator/disarm-retina-policy`
- External ingest (optional): `POST /operator/retina-event` when `RETINA_EXTERNAL_INGEST_ENABLED`

## Honest scope boundaries

- Does **not** modify 228-byte PoAC or chain link hash.
- Does **not** auto-block tournament eligibility; L4 remains primary biometric gate.
- May **disagree** with L4; disagreement is forensic signal, not silent override.
- L9 presence ↔ retina fusion (screen/controller lobes, HUD-OCR) lives on held PR #51 — **not** on `main`.

## VSD ingestion note

This synthesis maps protocol state on `main` into the vault corpus for methodology grounding. Enabling perception remains operator-paced (`RETINA_PERCEPTION_ENABLED` or qualified auto-arm); the VSD loop does not flip runtime flags.
