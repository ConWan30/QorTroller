---
type: synthesis
id: s-bridge-connectivity-aggregator
title: Build a read-only Bridge Connectivity Readiness Aggregator (BCRA)
created: 2026-06-24T00:00:00Z
modified: 2026-06-24T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 40
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Recommends the next build for synchronizing how the bridge loads + displays/processes ALL
connectivity (controllers, agents, chain, operational). Grounded in the live surface; the recommendation
is `likely`, the build itself is an operator decision. Sibling shape to [[s-f5-provenance-quadrille-built]].

THE GAP (observed, not assumed): connectivity status is REAL but SCATTERED. The bridge exposes
dozens of `/agent/*-status` endpoints, FOUR separate `/health` definitions (monitoring.py,
operator_api/_app.py, operator_api/health_gate.py, public_forensic_api.py x2), plus standalone
`/bridge/capture-health` (controller/PCC), `/bridge/grind-chain-status` (GIC), and
`/operator/watchdog-status` (operational). FleetSignalCoherenceAgent tracks agent-fleet coherence
separately again. There is NO single read-only surface that composes controller + agent-fleet +
chain-reachability + operational/watchdog into ONE coherent "is the bridge fully connected and
loaded" view. An operator today reads ~5 endpoints and mentally ANDs them.

THE BUILD — BCRA, a read-only packaging aggregator (same discipline as F2/F5):
  - Composes already-computed subsystem statuses into one readiness attestation across four lanes:
      CONTROLLER  (capture-health: PCC state + host EXCLUSIVE_USB/CONTESTED + poll rate)
      AGENTS      (fleet coherence + per-agent liveness / enabled flags)
      CHAIN       (RPC reachability + kill-switch CHAIN_SUBMISSION_PAUSED state — honest, not faked)
      OPERATIONAL (watchdog event chain intact + restart-rate ceiling + GIC chain_intact)
  - Per-lane state {CONNECTED / DEGRADED / DISCONNECTED / UNKNOWN} + an overall readiness verdict.
  - Emits a VPM honesty label: visual_state=`live` ONLY when all four lanes CONNECTED; any
    DEGRADED/DISCONNECTED lane -> `unverified`; CHAIN lane reports paused-by-design as DEGRADED, not
    green (the kill-switch being on is a TRUE state, must not render as full connectivity).

WHY IT FITS THE PROTOCOL (not generic ops): the value-add is HONEST AGGREGATION — a degraded
subsystem cannot render as all-green, mirroring the anti-overclaim grammar VPM/F2/F5/VSD-emits-VPM
already hold. It also addresses the event_loop_invariants concern (a 10s /health timeout signals a
blocked event loop): BCRA is read-only + composes cached subsystem statuses, never runs heavy work
on the request path, so it stays a fast, non-blocking readiness probe.

HONESTY RAILS (held, identical to F2/F5):
  - Read-only / packaging ONLY — composes existing status surfaces; does NOT restart, reconnect,
    re-init, or mutate any subsystem. Callers pass the four subsystem-status dicts (fixtures-first).
  - No new FROZEN-v1 family (no b"VAPI-...-v1" tag; plain SHA-256 packaging digest if a stamp is
    wanted). No new PV-CI invariant. SCHEMA is a lowercase packaging string.
  - Anti-overclaim by construction + tamper-evident verify_attestation re-check (visual_state ==
    derived). DISPLAY is downstream: the same dict feeds a dashboard panel, but BCRA itself only
    PROCESSES + LABELS connectivity; it never claims a lane is up that its source says is down.

SCOPE DISCIPLINE: BCRA does not REPLACE the existing endpoints (they stay as the authoritative
per-subsystem truth); it COMPOSES them into one coherent readiness view, the controller/agent/chain
analog of what provenance_quadrille did for the four chains. Promotion to auto-remediation
(reconnect/restart) is explicitly OUT of scope and would be a separate operator decision — BCRA
observes + labels, the operator (or watchdog, under its own rate ceiling) acts.
