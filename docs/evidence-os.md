# Evidence OS

> Forensic instrument panel for VAPI. Five workspaces under `/os/*` that
> reveal what the protocol has done, what it is doing right now, what
> needs operator judgement, and how every claim can be re-derived in
> a browser without trust.

---

## 1. Why Evidence OS exists

The legacy VAPI dashboard at `/` is a 6-tab SPA organised by **audience**
(Gamer / Developer / Manufacturer / BRP / Marketplace / VPM Registry).
That layout is useful when the question is "who is this screen for?" — but
it is the wrong shape when the operator's question is **"what does the
protocol claim, and is it true?"**

Evidence OS is organised by **investigation**, not audience. Each of its
five workspaces answers one operator question in roughly three seconds:

| Workspace      | Operator question                                  |
|----------------|----------------------------------------------------|
| Evidence Graph | Where does any given claim come from?              |
| Live Match     | Can this session count right now?                  |
| Operator Queue | What needs my judgement?                           |
| Forensic Replay | Re-verify any past claim in this browser.         |
| Protocol State | What is the protocol-wide posture?                 |

The shell aesthetic is deliberately not generic cyber-neon. It targets
**laboratory measurement device** — oscilloscope graticule, evidence-room
labelling, restrained palette. Type does the work; colour is redundant
to text.

Evidence OS ships alongside (does not replace) the existing 6-tab SPA
and the six top-level public viewer routes. They share the same hooks,
the same crypto verifier catalog, and the same FROZEN-region invariants.

---

## 2. Five workspace purposes

### `/os/evidence` — Evidence Graph

The signature workspace. Renders the protocol's substrate layers as
node cards (HID frames → PoAC records → GIC chain → APOP → PCC → AIT
→ GIC / VHP / ZKBA / VPM / Curator → on-chain anchor) **with measured
SVG relationship edges drawn between them**. Each node carries a
mythology line (one sentence the operator can quote to a stakeholder),
a status badge, a detail line, and a source reference. Each edge
encodes a real protocol binding — cryptographic / predicate-gate /
derived-poll / kill-switch-deferred — measured against post-mount DOM
positions so it stays pinned across viewport and flex-wrap changes.

The graph holds two honesty rules tightly:

- **No phantom relationships.** When either endpoint of an edge is
  missing from the rendered DOM (e.g. a node that hasn't shipped
  yet), the edge is silently dropped. Nothing is ever drawn for a
  relationship the workspace can't ground in two real cards.
- **Mobile honesty.** Below 760px viewport (the same threshold
  where the AppShell rail collapses to a horizontal scroller), the
  SVG layer suppresses entirely — once cards flex-wrap into a
  vertical stack, horizontal lines between same-row neighbours
  would mislead. The text-summary remains screen-reader accessible
  at every viewport so the dataflow model is never lost on narrow
  screens.

Use this surface when somebody asks **"how do I get from a controller
plugged into a USB port to a tournament-eligible signed credential?"**

### `/os/live` — Live Match

The operator's active-session decision surface. One dominant verdict —
counting / blocked / dormant / mock — answers "can this session count?"
A live signal pane (capture, host, play, chain) shows the inputs to
that verdict. A blocker list renders only when a gate fails, with
human translation first and protocol term as supporting detail.

Use this surface during a grind. Glance at the verdict. If it's
**SESSION COUNTS**, keep playing. If it's blocked, the dominant
blocker headline tells the operator what to fix.

### `/os/queue` — Operator Queue

The unified decision surface across every protocol input that needs
human judgement: Sentry / Guardian / Curator drafts, Curator-flagged
listings, Cedar bundle + scope-hash drift findings, O3 readiness
blockers, and the live invariant gate. One sorted list (severity
then recency), one detail panel with a two-click confirm for
destructive operations, one write-guard cascade for safety.

Use this surface when the operator is the bottleneck. The queue
contains every item that's waiting on a human.

### `/os/replay` — Forensic Replay

The browser-side verification surface. Paste any cryptographic claim
the protocol publishes — a session commitment hash, a grind session
id, a device/counter pair, a VHP token id, an algorithm name — and
the workspace detects the input type, mounts the corresponding viewer,
and re-runs the FROZEN-v1 cryptographic algorithms in the browser.
The viewer's own panels (CryptoReplayPanel, PoacBodyHasher,
GicChainTimeline) surface OK / MISMATCH per primitive next to the
protocol-side claim.

Use this surface when **somebody else** challenges a claim. The
operator hands them a URL and they re-derive the answer themselves.

### `/os/protocol` — Protocol State

Read-only protocol-wide observability across four sections:

- **Posture** — kill-switch, PV-CI invariant count, fleet phase alignment.
- **Measurement** — separation_ratios per probe with CLEARED / BELOW 1.0
  status, plus persisted volume (VPM artifacts / MLGA sessions / GIC links).
- **Identity** — chain id, Operator Initiative agent registry.
- **Operator Detail** — invariant gate failure list and FSCA coherence
  counts when an authenticated bridge is reachable; honest unavailable
  panel otherwise.

Use this surface for "what is the protocol's overall state right now?"
or before any wallet-impacting ceremony.

---

## 3. Route map

```
/                                       legacy 6-tab SPA (unchanged)
/explorer                               public landing
/session/:commitmentHex                 public session viewer
/gic/:grindSessionId                    public GIC chain viewer
/record/:deviceId/:counter              public PoAC record viewer
/vhp/:tokenId                           public VHP credential viewer
/algorithms                             public algorithm catalog

/os                                     redirects → /os/evidence
/os/evidence                            EvidenceGraphWorkspace      [shell + Outlet]
/os/live                                LiveMatchWorkspace          [shell + Outlet]
/os/queue                               OperatorQueueWorkspace      [shell + Outlet]
/os/replay                              ForensicReplayWorkspace     [shell + nested Outlet]
/os/replay/session/:commitmentHex       PublicSessionViewer         (reused)
/os/replay/gic/:grindSessionId          GicChainExplorerView        (reused)
/os/replay/record/:deviceId/:counter    PoacRecordExplorerView      (reused)
/os/replay/vhp/:tokenId                 VhpCredentialView           (reused)
/os/replay/algorithms                   AlgorithmCatalogView        (reused)
/os/protocol                            ProtocolStateWorkspace      [shell + Outlet]
```

The `/os/*` routes are an additive layer. The six top-level public
routes remain at their original paths so shareable links keep working
byte-identically. `/` still renders the legacy SPA.

---

## 4. Data sources / hooks per workspace

All hooks are from `frontend/src/api/bridgeApi.js` unless noted.
Hooks tagged `noMock:true` refuse to swap in fabricated data when
the bridge is unreachable — they hold the last successful response or
report an error.

### `/os/evidence` — Evidence Graph

Data hooks:
- `usePublicProtocolState` (public, no auth)
- `usePublicVhp` (public, no auth)
- `useCaptureHealth`, `useGrindChain`, `useActivePlayOccupancy`,
  `useAITSeparation`, `useVpmList`, `useCuratorStatus`

Signature primitive:
- `EvidenceEdgeLayer` (`frontend/src/os/components/EvidenceEdgeLayer.jsx`)
  — measures post-mount DOM positions of every `[data-os-evidence-node]`
  child of its `containerRef` via `getBoundingClientRect`, then draws
  SVG `<line>` elements between them in container-relative coordinates.
  Re-measures on every `ResizeObserver` tick (watches both the
  container and each node, since flex-wrap can change child positions
  without the container's own width changing), with a
  `requestAnimationFrame` debounce so paint doesn't thrash on rapid
  resize. Edge styles map to the FROZEN `os-edge--{solid,dotted,
  dashed,ghost}` classes in `theme.css` (cryptographic / derived /
  predicate / kill-switch-deferred). Falls back to a `window`
  `resize` listener when `ResizeObserver` is absent (older jsdom in
  tests).

Accessibility:
- The `<svg>` rendered by `EvidenceEdgeLayer` carries
  `aria-hidden="true"` because the geometry is a purely visual layer.
- The workspace publishes a visually-hidden relationship summary
  (`<h3>` + `<ul>` of one `<li>` per edge in natural language —
  "X flows into Y as a Z relationship (currently deferred ...)")
  so screen-reader and keyboard users get the same dataflow model
  without depending on the SVG. The summary survives narrow-viewport
  suppression of the SVG layer.

### `/os/live` — Live Match
- `useCaptureHealth`, `useGrindChain`, `useActivePlayOccupancy`
- `useBrpRecordPulse` (WebSocket, custom hook)
- `useBrpControllerOrientation` (WebSocket, custom hook — currently
  dormant pending device-id discovery wiring)
- `useAutoTriggerStatus`, `useAITSeparation`

### `/os/queue` — Operator Queue
- `useOperatorDrafts` (Sentry / Guardian / Curator drafts)
- `useReviewDraft` (POST mutation — accept / reject / overturn_curator)
- `useCuratorStatus`, `useCuratorFlaggedListings`, `useDriftLog`
- `useFleetReadinessRoot` (O3 blockers per agent)
- `useInvariantGateStatus`, `useFleetCoherenceStatus`

### `/os/replay` — Forensic Replay
- `frontend/src/api/publicForensic.js` — `usePublicSession`,
  `usePublicAlgorithms`, `usePublicGicChain`, `usePublicGicLinks`,
  `usePublicAgentRoots`, `usePublicProtocolState`, `usePublicVhp`,
  `fetchPublicRecordBytes`
- `frontend/src/crypto/vapi_verifier.js` — the 14 FROZEN-v1
  cryptographic verifier functions, run in the browser via Web Crypto.

### `/os/protocol` — Protocol State
- `usePublicProtocolState`, `usePublicAgentRoots` (public, no auth)
- `useFleetCoherenceStatus`, `useInvariantGateStatus`
  (operator-auth; degrade to honest unavailable panel when bridge
  offline or api_key missing)

### Shell
- `frontend/src/os/AppShell.jsx` mounts the workspaces under one route
  group; `StatusStrip` reads `usePublicProtocolState`,
  `usePublicAgentRoots`, and `useFleetCoherenceStatus` to surface
  bridge / kill-switch / agent count / merkle / blocker count.

---

## 5. Mock / offline honesty rules

The shell and workspaces must **never paint mock or offline data as
live**. Five rules apply:

1. **`noMock: true` on every grind-critical hook.** A transient bridge
   stall during a live grind must surface as an error or held-last
   value — never as fabricated grind state.
2. **Mock status is its own colour token.** `--os-status-mock` is the
   same hue as `--os-status-blocked` (red), NOT `--os-status-live`
   (green). The DataBadge `mock` variant carries the literal word
   `MOCK`.
3. **Header-strip and verdict labels mirror reality.** When
   `isMockActive()` returns true, the workspace's top-level pill
   reads `MOCK` and the dominant verdict (where applicable, e.g.
   Live Match) reads `MOCK SESSION · not live`.
4. **Honest unavailable, not silent fail.** When an operator endpoint
   is unreachable, the Protocol State workspace renders an explicit
   "Operator detail unavailable" panel with a one-line reason and
   the public posture as the trustworthy baseline. The Operator Queue
   surfaces a per-tile error strip when any source is offline.
5. **Empty states are honest.** The Operator Queue empty state
   explicitly does not say "all clear"; it says "honest quiet" and
   names every source hook it checked. The Verification Receipt empty
   state literally reads "does not imply OK".

---

## 6. Safety / write-action rules

The cascade is enforced in `OperatorQueueWorkspace` and the four
queue primitives:

```
writeGuard =
    'mock-active'        if isMockActive()             else
    'invariant-failing'  if invariant gate failing      else
    null
```

Every write-capable control routes through this cascade. When
`writeGuard` is non-null:

- The inline "Review" button is replaced by an `ActionGuardBadge`
  whose reason key matches the guard, displayed with a labelled
  word AND an `⊘` glyph (never colour-only).
- Inside the detail panel, accept / reject / overturn are visibly
  disabled with the same `ActionGuardBadge`.
- The workspace header right-strip surfaces a banner: `MOCK ACTIVE
  — WRITES DISABLED` or `INVARIANT GATE FAILING — SENSITIVE WRITES
  DISABLED`.
- The invariant-fail event ALSO surfaces as a CRITICAL queue row of
  its own, with recommendation `STOP protocol-altering work. Run
  vapi_invariant_gate.py --report; resolve every failure before
  any write.`

Destructive operations (accept / reject / overturn_curator) require
**two clicks** to fire. The first click arms the action and changes
the button text to `Confirm <decision>`; the second click submits.
A primed action auto-clears after 8 seconds of inactivity so an
operator who walks away mid-decision cannot accidentally fire a
stale decision on return.

The Forensic Replay surface never writes anywhere — it is read-only
public verification. The shell's six public routes likewise never
write. No operator API key is required for `/public/*` reads.

---

## 7. Accessibility / design-system rules

### Design tokens

All Evidence OS components must read from the `--os-*` token family
defined in `frontend/src/os/theme.css`. Hardcoded hex values, legacy
`--vapi-*` tokens, and inline cyberpunk neon are forbidden. The
palette is:

```
Surfaces       --os-bg  --os-panel  --os-panel-soft
Borders        --os-border  --os-border-soft
Text           --os-text  --os-text-dim  --os-text-faint
Status         --os-status-{live,verified,pending,blocked,mock,
                              killswitch,dormant}
Accents        --os-accent  --os-accent-soft
Mythology      --os-chain  --os-derived  --os-predicate  --os-ghost
Type sizing    --os-text-{min,base,label,h3,h2,h1}
Layout         --os-rail-width  --os-strip-h  --os-radius
```

Operator-readable minimums: 11px (`--os-text-min`), 12px
(`--os-text-base`). No nano-text. Monospace font on every label that
shows a hash or hex value.

### Accessibility contract

- **Semantic elements over divs.** Interactive controls are
  `<button>`, `<a>`, `<input>`. Custom clickable divs are forbidden.
  Disabled controls remain in the focus order (e.g. via
  `<button disabled>`) so keyboard users can discover requirements.
- **role attributes** match the semantic widget: navigation uses
  `<nav role="navigation">` and `<NavLink>`, queue list is
  `<ul role="list">` of `<li>`, queue rows are `<button>` carrying
  `aria-expanded` + `aria-controls` for the detail panel, signal
  meters are `<div role="meter" aria-valuemin/max/now>`, status pills
  are `role="status"`, verdict panels are `role="status"
  aria-live="polite"`.
- **No colour-only state.** Every status carries a word
  (`LIVE / VERIFIED / PENDING / BLOCKED / MOCK / PAUSED / DORMANT`).
  Critical severity carries a `!` glyph in addition to the red
  border. Disabled actions carry an `ActionGuardBadge` with a labelled
  reason.
- **Hash readability.** Long hex values render in monospace with
  `word-break: break-all`, truncated middles with the full value
  visible in the `title` attribute and via a copy-to-clipboard button
  on the Verification Receipt.
- **Responsive.** The shell collapses the left rail to a horizontal
  scroller below 760px viewport so the workspace gets full width on
  mobile. Workspace grids use `auto-fit, minmax(...)` rather than
  fixed column counts.
- **Screen-reader hints.** Disabled `ReplayModeTabs` carry a
  visually-hidden hint announced via `aria-describedby` ("Paste a
  session commitment hash first to enable this tab"). EmptyState
  bodies carry `aria-live="polite"` so the queue flipping from
  N items to 0 is announced.

---

## 8. How future stages should extend Evidence OS

1. **One workspace per investigation.** A new workspace exists only
   when it answers an operator question that none of the five existing
   workspaces can. Otherwise extend an existing workspace.
2. **Compose hooks, do not duplicate cryptographic logic.** All
   cryptographic re-derivation happens in
   `frontend/src/crypto/vapi_verifier.js` (a FROZEN-v1 catalog). The
   workspaces compose verifier output; they do not implement crypto.
3. **Add primitives only when reused.** A new component graduates to
   `frontend/src/os/components/` only when two or more workspaces (or
   one workspace and the shell) consume it. Workspace-private helpers
   stay in the workspace file.
4. **Match the existing primitive shape.** Status keys come from the
   DataBadge enum. Required action labels use `ActionGuardBadge` when
   disabled. Severity uses the `critical / warn / info` triple.
   Detail panels use `aria-expanded` + `aria-controls`, never
   `aria-pressed`.
5. **Public surface is the truth-floor.** When a workspace reads from
   both `/public/*` and operator-auth endpoints, render the public
   surface fully first and treat operator detail as additive. If
   operator detail is unavailable, surface a labelled unavailable
   panel — never replace public truth with operator data when
   conflict appears.
6. **Never weaken the safety cascade.** Any new write-capable surface
   must call through the existing `writeGuard` machinery in
   `OperatorQueueWorkspace`. Mock + invariant-failing must disable
   the write; the action must require explicit confirmation.
7. **Test mock / offline / invariant-fail explicitly.** Every new
   workspace ships with at least one test that asserts the workspace
   does not paint fake-live data, one that asserts writes are guarded
   when invariant gate is failing, and one that asserts an honest
   empty / unavailable state.
8. **Preserve the legacy SPA and the six public routes.** No Evidence
   OS change may break the routes at `/`, `/explorer`, `/session/*`,
   `/gic/*`, `/record/*`, `/vhp/*`, or `/algorithms`. The 6-tab SPA
   at `/` is preserved for audience-organised workflows; the public
   routes are the shareable surface.
9. **Audit before celebration.** A new workspace ships with a Mythos
   hardening pass covering responsive layout (390 / 768 / 1280 /
   1920px), keyboard navigation, screen-reader labels, mock honesty,
   safety cascade, copy consistency, bundle hygiene, encoding,
   coverage, and aesthetic consistency. Findings landed as small
   inline fixes; no protocol / bridge / contract changes in audit
   passes.

---

## Provenance

| Stage | Commit       | Date       | Headline                                                        |
|-------|--------------|------------|------------------------------------------------------------------|
| 1     | `bc2a5cb8`   | 2026-05-15 | Shell + Evidence Graph vertical slice                            |
| 2     | `b4a9b12b`   | 2026-05-15 | Live Match session-counts verdict                                |
| 3     | `2014c7a3`   | 2026-05-15 | Operator Queue unified decision surface                          |
| 4     | `b5826189`   | 2026-05-15 | Forensic Replay verification surface                             |
| 5     | `f08d62e7`   | 2026-05-15 | Protocol State posture / measurement / identity                  |
| 5.1   | `ea72b638`   | 2026-05-16 | Mythos hardening audit + `docs/evidence-os.md`                   |
| 5.2   | `7c307495`   | 2026-05-16 | L4 hook-contract regression guards + M5 `role="meter"` + M2 enum |
| 6     | `d11bb07b`   | 2026-05-16 | Evidence Graph measured SVG edges via `EvidenceEdgeLayer`        |

**Stage 5.2 in detail** — picks off three Mythos audit deferrals in
the operator's chosen triage order:
- **L4** — regression guards locking the C1/C2 honesty bugs into CI.
  Four new tests in `frontend/src/__tests__/EvidenceOSHookContracts.test.jsx`:
  T-OS-L4-1 asserts `useBrpControllerOrientation` returns the FROZEN
  `{orientation, connected, framesReceived}` shape (no `.data`
  accessor); T-OS-L4-2 asserts the Live Match IMU meter never claims
  `streaming` when `connected=false`; T-OS-L4-3 + T-OS-L4-4 lock
  StatusStrip's Blockers tile to dormant `—` when coherence is null
  AND reject the C2 `value={0}` source pattern via a static-grep
  guard.
- **M5** — `SignalMeter` upgrades from `role="group"` to
  `role="meter"` (with `aria-valuemin/max/now/text`) when its value
  is numeric; falls back to `role="group"` for non-numeric labels
  (ARIA meter requires a numeric `aria-valuenow`). Matches the
  discipline already used by `_ProbeBar` in `ProtocolStateWorkspace`.
- **M2** — `apopStatus()` in `EvidenceGraphWorkspace` renders the
  human label first with the raw enum appended in parens (`On menu
  / paused — gating GIC (NON_COMPETITIVE_MENU)`); protocol term
  preserved as inspectable secondary detail.

Verification: 122/122 frontend tests pass, `npm run build` PASS,
0 IOTX wallet impact, no bridge restart required.

**Stage 6 in detail** — Evidence Graph crosses from honest placeholder
to real operator surface. The signature workspace now renders real SVG
edges between EvidenceNode cards using measured post-mount DOM positions:
- New primitive: `frontend/src/os/components/EvidenceEdgeLayer.jsx`.
- Eleven edges grounded in real protocol bindings (chain / predicate /
  derived) plus ghost styling for kill-switch-held or dormant targets.
- Re-measures on every `ResizeObserver` tick (watches container +
  every node so flex-wrap changes don't desync geometry).
- Below 760px viewport the SVG suppresses with marker
  `data-os-edge-layer="suppressed-narrow"`; the screen-reader
  relationship summary remains at every viewport.
- Missing endpoints silently drop their edge — no phantom
  relationships ever drawn for nodes not in the DOM.
- Workspace publishes a visually-hidden text dataflow summary that
  lists every edge as natural language, so the provenance model is
  never lost on narrow screens.

Verification: 132/132 frontend tests pass (122 prior + 10 new
T-OS-EDGE-1..9 + T-OS-EDGE-7b), `npm run build` PASS, 0 IOTX wallet
impact, no bridge restart required.

Test counts: 132 frontend tests across 13 files. Bundle: `main`
chunk ~358 KB raw / 107.31 → ~108.9 KB gzipped (Evidence OS arc
remains within the existing main chunk; no new chunks created).
