---
type: synthesis
id: s-gamer-frontend-redesign
title: A gamer-first frontend that shows what QorTroller actually proves
created: 2026-06-24T00:00:00Z
modified: 2026-06-24T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: possible
effort: 45
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Brainstorm (confidence: possible; a design direction, not a build commitment) for redesigning the
gamer frontend so connecting a controller to the bridge FEELS like what QorTroller is: the gamer is
the cryptographic owner of their play. Grounded in the surfaces that now exist; building is a
separate operator decision. Pairs with the new BCRA endpoint ([[s-bcra-built]]).

THE GAP: the current dashboard is operator/developer-shaped — scattered status panels, ~5 endpoints
the viewer must mentally AND. It does not narrate the protocol's promise to a GAMER: "a live human
on a certified device, owning the data their hands produce." It shows telemetry, not sovereignty.

DESIGN SPINE — "THE MOMENT OF PROOF" (one screen, one story, top to bottom):
  1. CONNECT — the instant the controller hits the bridge, a single hero state driven by the new
     GET /bridge/connectivity BCRA lane view: CONTROLLER / AGENTS / CHAIN / OPERATIONAL as four
     honest lights. The VPM visual_state IS the hero color (live / degraded / unverified) — the
     gamer sees one truthful "you're connected and proven" state, never a fake all-green.
  2. YOU ARE LIVE — render PoCP/L9 causal presence + the F2 recency-bound-presence verdict as a
     living pulse: "your hands are driving this, right now, and it can't be replayed." The
     adaptive-trigger force-curve (the moat) is the signature animation — the gamer SEES their own
     biomechanical fingerprint as art, not a number.
  3. YOU OWN IT — the data-sovereignty story (consent manifest + ZKBA + marketplace): plain-language
     toggles for what the gamer permits (tournament / research / marketplace), each a real consent
     category, each gamer-wallet-signed (NEVER bridge-granted — the sovereignty invariant made
     visible). "Your gameplay, your keys, your call."
  4. THE RECEIPT — the provenance quadrille (F5) + GIC progress as a gamer-legible "match receipt":
     a single integrity seal they can show/share, with the honest caveats (not tournament-grade yet;
     not anchored) rendered as calm secondary text, not hidden.

THE NOVELTY (why this is QorTroller, not a generic gamer dashboard):
  - HONESTY AS AESTHETIC: the VPM closed-enum grammar becomes the visual language. `live` is
    saturated/animated; `dry-run`/`emulated` are striped/desaturated; `unverified`/`degraded` are
    warning-banded. The UI CANNOT render a state the protocol can't prove — anti-overclaim is the
    design system, not a disclaimer. This is the inverse of every anti-cheat that asserts trust;
    QorTroller SHOWS it and shows its limits.
  - THE CONTROLLER IS THE PROTAGONIST: the hero visual is the gamer's own controller + its live
    force-curve / tremor signature, not a logo. Connecting it is the narrative open.
  - SOVEREIGNTY IS INTERACTIVE: consent is a control the gamer operates with their own wallet, on
    screen, reversibly — the one thing no kernel anti-cheat can offer, made the centerpiece.

HONESTY RAILS FOR THE BUILD (held, mirroring the rest of the protocol):
  - Read from real endpoints only; noMock:true on every grind/connectivity hook (a transient 5xx
    must never silently fabricate a green state mid-session — existing frontend hard rule).
  - The frontend DISPLAYS verdicts; it never computes or asserts proof. visual_state comes from the
    server's VPM label, never recolored client-side to look better.
  - Phased + reversible: Stage 1 = the BCRA hero connect-state (buildable now on the live endpoint);
    Stage 2 = presence pulse + force-curve; Stage 3 = sovereignty toggles (needs gamer-wallet flow);
    Stage 4 = the shareable receipt. Each stage ships honest-partial, never faking later stages.

NEXT MOVE IF PURSUED (operator decision): Stage 1 — a GamerView hero panel bound to
GET /bridge/connectivity, rendering the four lanes + VPM visual_state as the single connect-state.
Read-only, reversible, no FROZEN/chain. The frontend-design skill can carry the visual language.
