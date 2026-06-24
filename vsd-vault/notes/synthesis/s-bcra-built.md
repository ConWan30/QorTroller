---
type: synthesis
id: s-bcra-built
title: BCRA bridge connectivity aggregator BUILT (read-only, packaging-only)
created: 2026-06-24T00:00:00Z
modified: 2026-06-24T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 40
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

The aggregator recommended in [[s-bridge-connectivity-aggregator]] is now built:
`bridge/vapi_bridge/bridge_connectivity_aggregator.py` + 17 tests. This note records WHAT shipped and
the honesty rails it holds. Third read-only fusion in the arc after F2
([[s-f2-recency-bound-presence-built]]) and F5 ([[s-f5-provenance-quadrille-built]]).

WHAT: a read-only aggregator that composes the bridge's already-computed subsystem statuses into ONE
connectivity-readiness attestation across four lanes — CONTROLLER (capture-health PCC + host + poll
rate), AGENTS (fleet coherence + liveness), CHAIN (RPC reachability + CHAIN_SUBMISSION_PAUSED kill-
switch), OPERATIONAL (watchdog chain + GIC chain + restart ceiling). Each lane classifies to
CONNECTED / DEGRADED / DISCONNECTED / UNKNOWN; overall verdict FULLY_CONNECTED / DEGRADED /
PARTIALLY_CONNECTED. Replaces the operator's manual "read ~5 endpoints and mentally AND them."

HONESTY RAILS (why this is a VSD-worthy build):
  - Read-only / packaging ONLY — composes existing status dicts; never restarts, reconnects, re-inits,
    polls hardware, reads the chain, or mutates a subsystem. Callers pass the four status dicts.
  - The LOAD-BEARING honesty test: the CHAIN kill-switch being ON (CHAIN_SUBMISSION_PAUSED) renders
    DEGRADED, never green — a true state must not display as full connectivity; this in turn forces the
    overall verdict below FULLY_CONNECTED and visual_state to `unverified`, not `live`. A disconnected
    lane forces PARTIALLY_CONNECTED. verify_attestation re-checks verdict-vs-lanes consistency AND
    visual_state == derived, so a hand-edited `live` or a lane flipped to `connected` is rejected.
  - Event-loop safe: composes cached statuses, no heavy work on the request path (addresses the
    event_loop_invariants 10s-/health-timeout failure mode).
  - NO new FROZEN-v1 family (no b"VAPI-...-v1" tag; AST-over-bytes test guards it). NO new PV-CI
    invariant (179 unchanged). SCHEMA is a lowercase packaging string. Does NOT replace the per-
    subsystem endpoints (they stay authoritative); it COMPOSES them. Auto-remediation is OUT of scope.

WHY IT MATTERS: directly answers "ensure all connectivity to agents, controllers, etc is displayed
and processed" — one coherent, honestly-labeled readiness view the dashboard can render and the
operator can trust, where no degraded subsystem can hide behind an all-green light. It is the
controller/agent/chain analog of what provenance_quadrille did for the four chains: honest aggregation
over already-shipped surfaces, fixtures-first, reversible, no new crypto.
