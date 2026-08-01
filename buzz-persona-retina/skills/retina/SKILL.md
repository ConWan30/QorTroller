---
name: retina
description: "Retina Visual Oracle and VSS quick reference."
---

# Retina / VSS Quick Reference

## L1–L6 stack

| Layer | Name | Input | Output |
|-------|------|-------|--------|
| L1 | Raw sensor stream | DualShock Edge hardware | Unattested bytes |
| L2 | Device attestation | Edge signed reports | Attested features |
| L3 | PoEP reflex ring | Gameplay-live challenges | `poep_enabled`, `fire.real_hardware` |
| L4 | Anomaly / continuity | L2/L3 feature windows | Mahalanobis thresholds, `l4_ok` |
| L5 | Retina VLM verify | Video/audio/game state | Cross-modal digest |
| L6 | PoSP session binding | Session + ioID identity | `verdict`, `commitment_root` |

## Retina model

- `nvidia/nemotron-nano-12b-v2-vl`
- Primary corpus: NCAA College Football 26
- 228-byte PoAC record per cognition cycle

## Key tests

- `bridge/tests/test_retina_visual_oracle.py` — 16 oracle unit tests
- `bridge/tests/test_vss_*.py` — VSS seat/organizer/pilot tests
- `bridge/vapi_bridge/retina_visual_oracle.py` — module smoke

## Useful bridge paths

- `GET /player/session-status` — digest-only seat eligibility
- `GET /operator/vapi/retina/health` — oracle health (if enabled)
- `POST /operator/poep/fire` — operator-fired nonce probe (operator key required)

## Verdict values

- `SYNCHRONIZED_CONTROLLER` — identity + presence + real play line up
- `IDENTITY_ONLY` — identity/ioID proven, but no live rig proof
- `PRESENCE_ONLY` — live activity, but identity unverified
- `UNVERIFIABLE` — insufficient or contradictory evidence

## Forbidden patterns

- Starting live capture without `POEP_LIVE_FIRE_ENABLED=1`
- Fabricating `real_hardware=True`
- Posting raw frames, HID, or L4 features
