# QorTroller — Claude Design Master Prompt + Integration Checklist

**Purpose**: Remodel the QorTroller frontend using Claude's design-generation feature, grant-evaluator-optimized (depth + sophistication + cryptographic forensic surfaces front-and-center), WITHOUT drifting the backend data contract and WITH the 3D Controller Twin correctly incorporated.
**Date**: 2026-05-19 · **Anchor HEAD**: `d4436298` · **Brand-lock**: QRESCE-0001 v0.5 (`2c762835`)
**Scope (operator-locked)**: curated subset — Gamer hero + forensic/crypto depth surfaces + Operator Initiative O3 evidence. Manufacturer + Marketplace deferred (zero partners/listings).

This document has two parts:
- **Part A — The Master Prompt**: paste into Claude's design feature (artifacts) to prototype the *look*. Iterate freely on aesthetics; the data contract is frozen.
- **Part B — The Integration Checklist**: the per-component verification gate for porting the validated design into the real repo via Claude Code, so backend alignment is provably maintained.

---

# PART A — THE MASTER PROMPT

> Copy everything from the `=== BEGIN MASTER PROMPT ===` line to `=== END MASTER PROMPT ===` into Claude's design feature. Fill the `[VIEW]` placeholder with the one view you're designing this iteration (start with `Gamer`).

```
=== BEGIN MASTER PROMPT ===

You are designing a single view of QorTroller's frontend. QorTroller is a
cryptographic anti-cheat protocol for competitive console gaming — the
reference implementation of Verifiable Autonomous Physical Intelligence
(V.A.P.I.), a DePIN sub-category on IoTeX. The audience for THIS remodel is
a technical grant evaluator (IoTeX foundation, possibly with a cryptographer
on staff). The design must read as: sophisticated, real, forensically
honest, alive. NOT generic Web3 neon. NOT a marketing landing page.

Design ONLY the view: [VIEW]

────────────────────────────────────────────────────────────
§1 — BRAND IDENTITY (LOCKED — do not reinterpret)
────────────────────────────────────────────────────────────

- Project name: QorTroller (medial capital T — NEVER "Qortroller" /
  "QORTROLLER" / "Qor Troller"). Pronounced KOR-TROLL-er.
- Category: V.A.P.I. (with periods) — Verifiable Autonomous Physical
  Intelligence. Display the category WITH periods; never as a heading hero.
- Tagline: "QorTroller — Core Controllers of their gaming data."
- Wordmark typography: Syne (display weight 700), with the medial T
  rendered in amber (#f0a868) at weight 800; "Qor" + "roller" in
  #d4dde8. This medial-T accent is a brand signature — use it for the
  wordmark, not for body text.
- Type system:
    Display / wordmark : Syne (700)
    Data / numbers / hashes / monospace : JetBrains Mono
    Body (sparingly)   : Syne (400/500) or system sans
- Palette (void-black forensic instrument, NOT cyber-neon):
    --bg            #04060a   (deeper than typical dark UI)
    --panel         #0a0e14
    --panel-soft    #0d1218
    --border        #1a2230   (mostly-invisible separators)
    --text          #d4dde8
    --text-dim      #8a96a5
    --text-faint    #5a6675   (min 11px usage)
    --accent-amber  #f0a868   (operator/audit; medial-T; predicate gates)
    --status-live   #5bd6a3   (verified live / cryptographically verified)
    --status-pending#f0a868   (in-flight / kill-switch-paused; honest)
    --status-blocked#d65b78   (failed / mismatch / fabricated-data alert)
    --chain         #5bd6a3   (cryptographic flow lines)
    --cyan          #00d4ff   (gamer-tier accent)
- Status colors are SEMANTIC and must ALWAYS pair a text label — never
  color-only. A red state always says why (MISMATCH / BLOCKED / MOCK).

────────────────────────────────────────────────────────────
§2 — AESTHETIC DIRECTION (the feeling)
────────────────────────────────────────────────────────────

Target aesthetic: "forensic instrument panel meets living cryptographic
specimen." Think: an oscilloscope graticule, an evidence-room labelling
discipline, a laboratory measurement device — that is ALSO breathing,
because a real human is on the other end of the controller.

- Restraint over density. Type does the work. No 6px nano-text.
- Motion is evidence of life, not decoration: a hash re-deriving, a chain
  link landing, a verdict pulse — animation should visualize the protocol
  actually computing, never gratuitous parallax.
- Depth visible: a grant evaluator should SEE the cryptographic machinery
  (re-derivation panels, chain timelines, byte tables) rendered as
  first-class heroes, not hidden in tooltips. "This is real" comes from
  showing the math, not claiming it.
- Honesty as aesthetic: when something is paused, unverified, or offline,
  the design says so plainly (amber "KILL-SWITCH PAUSED", red "BRIDGE
  UNREACHABLE", red "MOCK DATA"). Never fake a green state.

────────────────────────────────────────────────────────────
§3 — THE FROZEN DATA CONTRACT (consume verbatim — do NOT invent shapes)
────────────────────────────────────────────────────────────

Your design consumes data from these React hooks. Use the EXACT field
names. Do not invent fields. Do not add mock fallbacks. Each hook returns
`{ data, isLoading, error }` (react-query); read `data?.<field>`.

GRIND-CRITICAL HOOKS (all set noMock:true — see §4):

useGrindChain()  → GET /operator/bridge/grind-chain-status   (poll 5s)
  data: { grind_session_id, chain_length, latest_gic_hash, chain_intact,
          genesis_ts, latest_ts, latest_gameplay_context, timestamp }

useCaptureHealth()  → GET /operator/bridge/capture-health    (poll 3s)
  data: { pcc_enabled, capture_state ("NOMINAL"|"DEGRADED"|"DISCONNECTED"),
          host_state ("EXCLUSIVE_USB"|"EXCLUSIVE_BT"|"CONTESTED"|
                      "DEGRADED"|"DISCONNECTED"),
          poll_rate_hz, sustained_duration_s, grind_mode, grind_ready,
          grind_target, consecutive_clean_toward_target,
          session_counting_paused, gameplay_context_enabled,
          latest_gameplay_context, timestamp }

useGrindAnalytics()  → GET /operator/grind/analytics          (poll 10s)
  data: { grind_session_id, total_validated, stamped_count, success_rate,
          blocking_reason_counts (dict), sessions_per_day,
          projected_gic100_date, last_validation_ts, last_stamp_ts,
          timestamp }

usePCCIntelligence()  → GET /operator/grind/pcc-intelligence   (poll 8s)
  data: { total_episodes, mean_recovery_s, longest_episode_s,
          last_episode_ts, host_state_distribution (dict),
          hid_counter_restarts, timestamp }

useAITSeparation()  → GET /operator/agent/ait-separation-status (poll 20s)
  data: { ait_separation_enabled, n_sessions, separation_ratio,
          all_pairs_above_1, inter_player_mean, intra_player_mean,
          loo_accuracy, pair_distances (dict: "P1vP2"/"P1vP3"/"P2vP3"),
          analysis_date, last_run_ts, n_per_player (dict),
          per_player_tremor_hz (dict), per_player_roll_angle_deg (dict),
          per_player_pitch_angle_deg (dict), timestamp }

useTournamentPreflight()  → GET /operator/agent/tournament-preflight-status (poll 15s)
  data: { separation_ok, l4_ok, gate_ok, cert_ok, audit_ok, overall_pass,
          biometric_ttl_ok, all_pairs_p0_ok, conditions_detail (dict),
          error, timestamp }

useFleetCoherenceStatus()  → GET /operator/agent/fleet-coherence-summary (poll 8s)
  data: { fleet_coherence_enabled, total_open, by_severity, by_mode (dict:
          CONTRADICTION/ORPHAN/INVERSION), active_contradictions,
          active_orphans, active_inversions, last_checked_at, timestamp }

useProtocolCoherence()  → GET /operator/agent/protocol-coherence-status (poll 3s)
  data: { protocol_coherence_enabled, total_anchors, latest_merkle_root,
          agent_count, on_chain_confirmed, last_anchor_ts, timestamp }

PUBLIC / FORENSIC HOOKS (unauthenticated; VAME-validated):

usePublicProtocolState()  → GET /public/protocol-state         (poll 30s)
  data: { kill_switch_paused, pv_ci_invariants_count,
          total_vpm_artifacts, total_grind_chain_links, ... }

usePublicAgentRoots()  → GET /public/agent-roots               (cache 5min)
  data: { agents: [ { agent_id, cedar_bundle_merkle, ... } ] }   (3 agents)

CRYPTOGRAPHIC VERIFIERS (frontend/src/crypto/vapi_verifier.js — the
forensic-honesty heroes; all async, return 64-char hex; SHA-256 via Web
Crypto API, no external libs). These RE-DERIVE commitments in the browser:

  verifyPoacRecordHash(raw228Bytes) → hex   (body[:164] hash; NOT 228)
  verifyGicGenesis(grindSessionId, tsNs) → hex
  verifyGicChainLink(prevGicHex, commitmentHex, verdictCode, hostStateCode, tsNs) → hex
  verifyVameCommitment({chainHead16bHex, tsNs, endpoint, bodyBytes}) → hex
  verifyZkbaCommitment({zkbaClass, proofWeight, componentHashesHex, tsNs}) → hex
  + 10 more in the frozen VERIFIERS registry (corpus-snapshot, consent,
    listing, biometric-snapshot, FRR, MLGA, WEC, VPM-label, cedar-merkle)

FORENSIC COMPONENTS (already exist — design AROUND them, preserve behavior):
  PoacBodyHasher    — fetches 228-byte record, shows body/sig byte table,
                      re-hashes in browser, shows computed-vs-claimed + OK/MISMATCH
  GicChainTimeline  — renders GIC chain, re-computes each link via
                      verifyGicChainLink, OK/MISMATCH per link
  CryptoReplayPanel — runs verifiers for a session, table of
                      algorithm | input | computed | claimed | OK/MISMATCH

────────────────────────────────────────────────────────────
§4 — HARD CONSTRAINTS (NON-NEGOTIABLE — violating any is a regression)
────────────────────────────────────────────────────────────

1. THE 3D CONTROLLER TWIN IS A FROZEN IFRAME SLOT — DO NOT GENERATE IT.
   The twin is a 54MB GLB + React-Three-Fiber + physics model that renders
   itself inside an iframe and connects its OWN live WebSocket + SSE streams
   to the bridge. You CANNOT and MUST NOT try to render it. Treat it as a
   fixed rectangle in your layout:
       <iframe src="/controller-twin.html?minimal=1"
               title="QorTroller 3D Controller Twin"
               style={{position:'absolute', inset:0, width:'100%',
                       height:'100%', border:'none', background:'transparent',
                       zIndex:1}} />
   For PROTOTYPING in artifacts: put a placeholder in the iframe's place —
   a styled <div> labeled "3D CONTROLLER TWIN (live iframe at integration)"
   with a subtle breathing animation or a static controller silhouette.
   Design ALL your overlays/panels at zIndex >= 2 so they float above the
   twin rectangle. The twin owns its rectangle; you own everything around
   and on top of it.

2. NAMED EXPORTS FOR VIEWS. Top-level view components MUST use:
       export function GamerView() { ... }     // ✓
   NOT `export default function`. App.jsx lazy-loads via
   `import('./views/X').then(m => ({ default: m.X }))` — a default export
   crashes the lazy-load and blanks the tab. (Sub-components in
   components/ may use either.)

3. noMock:true IS PRESERVED. The grind-critical hooks (useGrindChain,
   useCaptureHealth, useGrindAnalytics, usePCCIntelligence, useAITSeparation,
   useTournamentPreflight, useFleetCoherenceStatus, + protocol-governance
   hooks) re-throw on network failure instead of showing fabricated data.
   Your component must NEVER introduce a mock/placeholder data fallback for
   these. A transient 5xx must show an honest error/last-known state, never
   invented numbers. (A dashboard that lies about grind state mid-grind is
   worse than one that's honest about being offline.)

4. HONEST EMPTY STATES. When data is unavailable: show "BRIDGE UNREACHABLE"
   / "—" / a clearly-labeled loading state. NEVER fabricate. If mock data
   is ever active (first-load discovery only), a visible red "MOCK DATA"
   banner must show. Green states are earned, never faked.

5. CRYPTO-VERIFIER SURFACES ARE PRESERVED. PoacBodyHasher, GicChainTimeline,
   CryptoReplayPanel must remain functional + visible. These are the
   forensic-honesty heroes for the grant evaluator. You may restyle their
   container, layout, and motion — you may NOT remove the re-derivation
   behavior or hide the computed-vs-claimed OK/MISMATCH output.

6. VAME VALIDATION IS PRESERVED (defense-in-depth; never blocks). If you
   surface VAME status, render NO_VAME / OK / MISMATCH honestly; it must
   never gate the response.

────────────────────────────────────────────────────────────
§5 — SCOPE FOR THIS ITERATION
────────────────────────────────────────────────────────────

Design ONLY: [VIEW]

For the Gamer view (the hero): the 3D twin iframe rectangle is the
centerpiece. Compose around it: the GRIND INTEGRITY CHAIN panel (chain_length
toward grind_target as a living ribbon; chain_intact state; latest_gic_hash
readout), the humanity-proof / capture-health state (capture_state +
host_state with semantic colors), the consent matrix, the gameplay-context
indicator. Glanceable — a gamer checks status, they don't live here.

For the forensic-depth surfaces: make the cryptographic re-derivation
(PoacBodyHasher byte table, GicChainTimeline, CryptoReplayPanel) visually
arresting — this is where a grant evaluator spends time. Byte tables,
chain timelines, computed-vs-claimed hash comparisons rendered as the
specimens under the microscope.

────────────────────────────────────────────────────────────
§6 — OUTPUT FORMAT
────────────────────────────────────────────────────────────

Produce a single React (JSX) component:
- Named export: `export function [VIEW]() { ... }`
- Consumes the hooks from §3 verbatim (you may stub them in the artifact
  with the exact return shape for prototyping, clearly marked
  // STUB FOR PROTOTYPE — real hook at integration)
- Inline styles or a styled-component approach is fine; use the §1 palette
  via CSS custom properties
- The 3D twin as the §4.1 placeholder (artifact) / iframe (integration)
- No external UI kit that fights the forensic-instrument aesthetic

────────────────────────────────────────────────────────────
§7 — ITERATION PROTOCOL
────────────────────────────────────────────────────────────

Each round:
1. Generate the view.
2. Self-critique against §1 (brand), §2 (aesthetic), §4 (hard constraints).
   Explicitly confirm: named export? no invented data fields? twin = iframe
   placeholder? no fabricated fallbacks? crypto surfaces preserved?
3. Refine. Repeat until the look is locked.
4. When locked, hand off to the Part B integration checklist.

=== END MASTER PROMPT ===
```

---

# PART B — INTEGRATION CHECKLIST

> After the look is locked in artifacts, port each component into the real repo via Claude Code. Run this gate per component BEFORE moving to the next. This is what keeps the backend provably in sync.

## Per-component integration gate

For each ported view/component, confirm ALL of:

- [ ] **Named export** — `export function X()`; verified loads via App.jsx lazy adapter (tab renders, not blank)
- [ ] **Real hooks wired** — every data field read matches a real field in §3 (no invented shapes); imported from `frontend/src/api/bridgeApi.js` / `publicForensic.js`, not stubbed
- [ ] **noMock preserved** — grind-critical hooks still pass `{ noMock: true }`; no mock/placeholder fallback introduced for them
- [ ] **Honest empty states** — bridge-offline path shows honest state (BRIDGE UNREACHABLE / last-known / red MOCK banner); no fabricated numbers
- [ ] **3D twin iframe slot** — `<iframe src="/controller-twin.html?minimal=1">` present + unmodified; overlays at zIndex ≥ 2; twin rectangle owns zIndex 1; NOT regenerated
- [ ] **Crypto-verifier surfaces preserved** — PoacBodyHasher / GicChainTimeline / CryptoReplayPanel still re-derive in-browser + show computed-vs-claimed OK/MISMATCH
- [ ] **VAME preserved** — if surfaced, NO_VAME/OK/MISMATCH renders honestly + never blocks
- [ ] **Brand discipline** — QorTroller medial-cap-T wordmark; no display "VAPI" leakage (V.A.P.I. with periods for category; VAPI byte-prefix only in code/crypto)
- [ ] **Operator route prefix** — operator hooks call `/operator/...` (the doubled-prefix convention); confirm endpoints resolve
- [ ] **Vitest** — `cd frontend && npm test -- --run` passes (currently 137 tests)
- [ ] **Build** — `cd frontend && npm run build` succeeds
- [ ] **Live-bridge visual check** — start bridge + `npm run dev`; verify the view renders real data against the running bridge, the twin iframe connects, no console errors
- [ ] **Mythos brand sweep** — `mythos_frontend_brand_drift` returns 0 findings (no display-VAPI residual introduced)

## Sequencing

1. **Gamer view first** (the hero; the twin iframe stage). Get it stunning + gated-clean before any other.
2. **Forensic-depth surfaces** (PoacBodyHasher / CryptoReplayPanel / GicChainTimeline restyled). The grant-evaluator "this is real" payload.
3. **Operator Initiative O3 evidence** (fleet state, Cedar authority, ceremony evidence).
4. **Deferred**: Manufacturer + Marketplace — design only when real partners/listings exist; currently empty aspirational surfaces.

## After all curated views integrated

- [ ] Full Vitest pass (no regressions across the 137 baseline)
- [ ] `mythos_frontend_brand_drift` = 0
- [ ] PV-CI gate `python scripts/vapi_invariant_gate.py` = 128/128 (frontend changes shouldn't touch invariants; confirm)
- [ ] IA cleanup decision (the 6-tab → gamer-first restructure) — fold in here if doing the public-launch-optimized pass; defer if grant-evaluator depth is the priority

---

## Why this stays in sync (the architectural guarantee)

The design tool operates ONLY on the **presentation layer**. The **data layer** (hooks, verifiers, VAME, the twin iframe, the noMock contract, the named-export requirement) is handed to it as a FROZEN input in §3-§4 and re-verified per-component in Part B. The design can be as stunning as the operator wants; the plumbing cannot drift, because:
- The hooks are consumed verbatim (real field names; Part B confirms no invented shapes)
- The twin is never regenerated (it's an iframe; the design composes around it)
- The crypto-honesty surfaces are preserved (Part B gate)
- Every integration is verified against the live bridge before the next

The 3D twin — the thing the operator couldn't incorporate before — is incorporated by NOT trying to render it: it's a fixed iframe rectangle the design stages around. That's the unlock.

---

*Drafted 2026-05-19 at HEAD `d4436298`. Data contract spot-verified against live source (iframe path, named-export adapter, noMock pattern, 15-verifier VERIFIERS registry, useGrindChain fields). Brand discipline per QRESCE-0001 v0.5. Update if the hook contract or twin mechanism changes.*
