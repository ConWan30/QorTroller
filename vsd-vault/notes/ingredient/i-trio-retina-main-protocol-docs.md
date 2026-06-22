---
type: ingredient
id: i-trio-retina-main-protocol-docs
created: 2026-06-22T00:00:00Z
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
source: repo-main
---

External-source anchors for Trio-Retina on QorTroller `main` (Phase 3 shipped, default-OFF):

- `README.md` — Trio-Retina row (advisory perception oracle, PV-CI INV-RETINA-001/002)
- `docs/retina-w3bstream-integration.md` — `retina_state_commitment` sidecar + three commitment axes
- `docs/retina-depin-policy-governor-v1.md` — DePIN policy governor qualifiers
- `bridge/vapi_bridge/retina_controller_embedder.py` — HID → `WorldState` / `Event`
- `bridge/vapi_bridge/retina_perception.py` — orchestration + store persistence
- `bridge/vapi_bridge/retina_depin_policy.py` — runtime arm / effective flags
- `bridge/vapi_bridge/dualshock_integration.py` — hot-path hook (~L1850)
- `bridge/vapi_bridge/session_adjudicator.py` — `_enrich_retina_evidence` (read-only)
- `audits/retina_pilot_enabled_2026-06-20.json` — pilot posture artifact
