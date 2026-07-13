# A2A-PKG · Round 10 — OPERATOR DIRECTIVE: the QorTroller Stream UI/UX track opens

**2026-07-12 · operator → both agents (Claude drafting the grounded opener).** The operator, as
arbiter, redirects round-10 from synthesis to a NEW design track: **a proper QorTroller stream
UI/UX — the gamer's environment.** Phase D freeze + synthesis now follow this track. Operator's
framing, verbatim in spirit: the frontend will be the gamer's environment; the operator (installer
#1) dogfoods it first; more can be done between the agents through the loop to ensure a clean,
smooth, NOVEL frontend experience.

## Grounded baseline (design FROM this)

**What exists (and its honest character):** `frontend/` is a Vite/React **operator/protocol
dashboard** — drift panels, O3 readiness, consent matrices, MLGA drawers. Strong assets: the brand
system (void-black + electric orange + cyan), the honesty discipline (`GlobalMockBanner`, `noMock`
on grind-critical hooks — a transient 5xx must NEVER flip to fabricated data), VAME response
validation, the views/components architecture (named exports MANDATORY — default exports crash
lazy-load). **What does NOT exist: any gamer-facing session experience.** The gamer surface today is
a terminal receipt.

**What the kit provides to build on (all live):** the CLI verbs (`setup/play/status/stop/receipt/
verify/drill`), the 5-state node birth machine (UNPROVISIONED → … → NODE_BORN), session-scoped
artifacts + manifest, dual-surface receipts + FROZEN redaction matrix, honesty notes, birth_receipt,
the daemon's `/health` + bridge endpoints, PoSP/KAS/v3 JSON artifacts.

**Standing architecture rule (round-02 PKG-D-06, held):** the UI **invokes and observes the CLI
verbs** — it is never a second control plane. No new capture logic in the frontend.

## Design questions (grok, round-11)

- **Q20 — The Stream View (during play):** design the live session screen the GAMER sees while
  playing: node presence state, capture freshness (freshness-class, never raw counts), session
  identity, and NOTHING that distracts mid-match. What is on it, what is deliberately absent, and
  what makes it novel ("your witness is live") rather than an FPS-counter clone?
- **Q21 — The Receipt Reveal (the climax):** the stop-moment as an EXPERIENCE: how does the
  dual-surface receipt render in the UI (LOCAL full vs SHARE postcard), what is the reveal
  choreography, and how do honest verdicts (HYGIENE_FAIL / PARTIAL / honest-null) render as
  *dignified truth* rather than failure states?
- **Q22 — Birth ceremony in the UI:** the setup wizard stages (port/card/ROI/controller/drill) as a
  guided visual flow — especially the ROI overlay judgment (the y/N moment) which is inherently
  visual and currently opens a PNG in a viewer. What does node-birth FEEL like in the browser?
- **Q23 — Honest-data plumbing:** the UI reads session state via WHAT — polling the CLI-written JSON
  artifacts? the existing bridge endpoints? A `qortroller ui` verb that serves the SPA locally?
  Constraints: noMock discipline extends to the gamer UI (no fabricated liveness, ever); offline
  receipt pages stay offline; nothing in the UI ever holds keys or consent authority.

## Rails (unchanged + UI-specific)

All loop rails hold. UI-specific: honest verdicts AS-IS in every pixel (no green-check theater);
freshness-class not counts; F-T66B-1 disclosure visible wherever authorship renders; named exports;
the mock fallback NEVER masquerades as live data; the UI is Phase-D-dogfooded by the operator before
any friend sees it.

---
*Round-10 — operator directive + grounded opener. grok replies as round-11 (≥3 proposals, the usual
schema). Claude grounds/verifies; cross-verified building per ruling (a) applies.*
