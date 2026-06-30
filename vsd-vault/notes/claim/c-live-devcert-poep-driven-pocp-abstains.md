---
type: claim
id: c-live-devcert-poep-driven-pocp-abstains
title: live developer_self proof is PoEP-driven; PoCP abstains; authorship absent
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 10
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-devcert-preinvestigation-report"]
---

The live recorded `developer_self` proof stream (`audits/devcert-warzone-proof-1782523326.jsonl`) is
PoEP(+CCO+L4L5L6)-driven: `latest_poep_present=true`, `latest_cco=P-T3`, but **`window_retina_coupled=0`
on every row** — the screen-coupling PoCP contributes nothing in practice. Killfeed authorship is absent
from the proof schema **entirely** — `FusedGamerPresenceProof` has no `kf_verdict` field (not merely
unpopulated; the field does not exist), and `cocapture_fields_from_pitl_meta` never reads one. Consequence:
the six PoCP/authorship-strengthening levers target primitives the recorded cert does not bind. Source:
[[i-devcert-preinvestigation-report]] Confirm 1 (GRADE VERIFIED).
