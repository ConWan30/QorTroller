# Integration Contract — BRP Solo Track → VAPI Protocol Monorepo

> **Track classification**: out-of-band, parallel, solo. **NOT** Phase 241.
> **NOT** part of the sequential VAPI protocol development chain. Integrates
> downstream of Phase O0 foundational integration (`vapi-anchor-sentry` +
> `vapi-guardian`) once that foundation is live.

This is the explicit handoff specification. The solo track ships the guarantees
in this document; the integration ceremony delivers the matching counterparts.

---

## What the O0-integrated VAPI must expose at ceremony time

At ceremony time, the Phase-O0-integrated VAPI must expose the following, all
`live: true`:

1. A typed `<BrpMount>` slot at `/gamer/twin` with these props:

   | Prop | Type | Notes |
   |------|------|-------|
   | `frozenOutput` | `Uint8Array` | Opaque, post-verification. Renderer never inspects, decodes, or interprets. |
   | `pitlSnapshot` | `PitlSnapshot` | Read-only. Typed against `src/brp/telemetry/contracts.ts` (added in commit 2+). |
   | `enrollmentSession?` | `EnrollmentSession` | Optional. Owner picked at ceremony per **Block V** (deferred). |
   | `aidThreshold` | `number` | Operator-set per **Block Z** (deferred). Default `0.65`. **NOT** the consensus threshold; share of numeric value is accidental. |
   | `liveness` | `{ ambient: boolean; legibility: boolean; telemetry: boolean }` | Drives the `data-live` attribute and visible badge. |

2. An **anchor-sentry stream** that emits `frozenOutput` updates via a stable
   in-app event (not a chain RPC). This is `vapi-anchor-sentry`'s responsibility.

3. A **guardian health hook** that signals when telemetry is degraded so the
   BRP layer can render a degraded-state placeholder rather than stale visuals.

4. A **confirmed hash domain** that the renderer's `"VAPI-BRP-RENDER-v1"` does
   not collide with any reserved protocol prefix. (Pre-checked at this commit
   against the five existing FROZEN-v1 tags; full reservation happens at
   ceremony.)

---

## What invariants must be added at integration time

`INV-BRP-1` through `INV-BRP-5` (drafted in `pv-ci-drafts/inv-brp-*.spec.ts`)
are added to PV-CI as part of the ceremony, raising the gate count by 5.

> **Gate count note**: PV-CI is currently at **N=28** (28 at the time of this
> commit, per CLAUDE.md; verify current value at ceremony time). The ceremony
> raises the gate to **N+5**. This commit does NOT modify the gate; it only
> ships the draft specs ready for ceremony adoption verbatim.

The five drafts:

| ID | Statement | Drafted at |
|----|-----------|-----------|
| INV-BRP-1 | Live-flag honesty: every BRP-namespaced React component renders `data-live` matching its manifest entry. | `pv-ci-drafts/inv-brp-1.spec.ts` |
| INV-BRP-2 | Verification-downstream: no module under `src/brp/**` may import from `poac/**`, `vhp/**`, `consensus/**`, `zk/**`, or sibling VAPI workspaces. | `pv-ci-drafts/inv-brp-2.spec.ts` |
| INV-BRP-3 | Hash-domain isolation: every `keccak256()`/`poseidon()` call from BRP code must pass through `deriveBrpSeed()`. | `pv-ci-drafts/inv-brp-3.spec.ts` |
| INV-BRP-4 | Photosensitivity budget: every animated material must pass at least one WCAG 2.3.1 pathway (G19 OR G176 OR ΔL) AND not trigger the saturated-red guard. | `pv-ci-drafts/inv-brp-4.spec.ts` |
| INV-BRP-5 | Accessibility surface: every BRP canvas root carries `role="presentation"` + `aria-hidden="true"` (or `role="img"` with `aria-label`) plus a sibling DOM description; axe-core zero violations on non-canvas chrome. | `pv-ci-drafts/inv-brp-5.spec.ts` |

---

## Merge ceremony — 8 ordered steps

The ceremony is a documented, witnessed event with these steps, performed in
this order:

1. **Honesty audit.** Operator reads `brp.manifest.json` and confirms every
   entry's `live` field reflects reality.
2. **Contract test.** The ceremony runs `npm run test:contract` against the
   live O0 PITL/calibration surface; zero drift is a precondition. (Drafted
   now in this commit's tests; runs at ceremony.)
3. **Hash-domain confirmation.** Operator confirms `"VAPI-BRP-RENDER-v1"` is
   reserved and does not collide with any FROZEN-v1 protocol prefix newer
   than the five checked in this commit.
4. **Decision Block close-out.** Each deferred block (V, Z) gets its
   operator decision recorded in `INTEGRATION_LOG.md` (created at ceremony,
   not by this track).
5. **PV-CI extension.** `INV-BRP-1..5` are added; gate count moves from N
   to N+5; CI proves all N+5 pass. (See gate-count note above — verify N at
   ceremony time.)
6. **Mount.** The BRP repo is vendored (or merged) into the protocol
   monorepo at `apps/gamer-portal/src/brp/`. **No FROZEN-v1 primitive is
   touched. The bridge wallet is not used.**
7. **Live-flag flip.** Per Block W, surfaces flip individually as upstream
   telemetry comes live; default state remains `live: false` for any
   surface whose upstream is not yet `live: true`.
8. **Post-mount smoke.** Playwright run against the integrated `/gamer/twin`
   route, axe-core run, manual photosensitivity walkthrough, PEAT/Harding
   capture on the integrated build for archive.

The ceremony is **reversible**: if any step fails, the BRP layer is unmounted
and the operator returns to the pre-ceremony commit. Because no FROZEN-v1
primitive, no PV-CI invariant, and no wallet has been touched, rollback is
`git revert` plus a CI re-run.

---

## Decision Block Resolutions (T through A1)

Resolved decisions are still subject to operator override at the ceremony;
deferred decisions ship as runtime-pluggable so the ceremony can pick.

| Block | Topic | Status | Resolution |
|-------|-------|--------|------------|
| T | Route topology | RESOLVED | Mount on existing `/gamer/twin` route as a child component, not a fork or sibling. Ceremony confirms slot placement, not topology. |
| U | Hash domain separation | RESOLVED | Renderer-side hash uses `"VAPI-BRP-RENDER-v1"` prepended to every keccak256 input. |
| V | Enrollment overlay ownership | DEFERRED | Solo track ships overlay as passive consumer of `EnrollmentSession` prop with typed shape. Ceremony picks owner (Twin route / O0 guardian / separate enrollment shell). |
| W | `"live": false` contract | RESOLVED | Every component, asset, fixture, adapter ships with explicit `live: false` in its manifest entry, surfaced as a non-dismissible badge and emitted as `data-live="false"` attribute on every rendered root. Three preconditions for `live: true` (a/b/c) listed above. |
| X | PITL row coexistence | RESOLVED (with caveats) | BRP layer reads a read-only snapshot of seven PITL rows as JSON via the mock telemetry contract. Visualization is presented adjacent to (not within) the PITL row container; all BRP pixels are explicitly marked decorative (`role="presentation"` + `aria-hidden="true"` on the WebGL canvas). Caveat for ceremony: confirm whether production PITL surface exposes the snapshot via a stable public API or an internal selector. |
| Y | PV-CI invariants INV-BRP-1..5 | DRAFTED, deferred for addition | Solo track drafts the five invariants but does not add them to PV-CI (locked at N=28 at this commit). Ceremony adopts verbatim. |
| Z | Empirical aid-to-calibration threshold | DEFERRED | Solo track exposes a single configurable prop `aidThreshold: number` (default `0.65`, mirroring the protocol's Epistemic Consensus Protocol threshold purely as a placeholder, with an explicit comment that this is **not** the consensus threshold and only happens to share a numeric value). Ceremony picks after seeing telemetry. |
| A1 | Accessibility & photosensitivity governance | RESOLVED | Three layers, all on by default, all tested: (1) WCAG 2.3.1 conformance proven by construction via the `flashBudget` static analyzer; (2) `prefers-reduced-motion` honored via both CSS and `matchMedia` listener; (3) user-controllable photosensitivity safety toggle in host page chrome, persisted in `localStorage`. |

---

## Honesty-First Invariants (load-bearing rules that survive merge)

These rules must hold in perpetuity, not just during the solo phase:

- **H-1.** The BRP layer never feeds back into VHP, separation ratio, PoAC
  metadata, ZK circuits, the consensus fleet, or any FROZEN-v1 primitive.
  Aesthetics are a *consequence* of verification, never an *input* to it.
- **H-2.** Every BRP-rendered surface declares its `live` state truthfully,
  both visibly (badge) and machine-readably (`data-live`). A `live: true`
  claim must be backed by a `live: true` upstream; INV-BRP-1 enforces this.
- **H-3.** The hash-derivation function is domain-separated and one-way for
  the renderer. The string `"VAPI-BRP-RENDER-v1"` is reserved for this
  purpose and may not be reused.
- **H-4.** The Mulberry32 PRNG is explicitly a *visual* PRNG. No
  cryptographic claim is ever made about its output. No security-relevant
  decision is ever made downstream of its output.
- **H-5.** WCAG 2.3.1 conformance is proven by construction (G19 / G176 /
  ΔL clamp), not by tool. Tool-based capture (PEAT / Harding FPA) is
  defense-in-depth.
- **H-6.** Photosensitivity safety has both an OS preference path
  (`prefers-reduced-motion`) and a user-controllable in-page toggle
  (WCAG 2.2.2 mechanism). Both are enabled by default in test fixtures so
  the developer cannot ship a regression silently.
- **H-7.** The terminal calibration scripts are canonical authority; the
  BRP layer is a downstream consumer. If the legibility overlay disagrees
  with a terminal script's output, the terminal script wins, the overlay
  flags itself as `live: false` for that surface, and a manual operator
  review is triggered.

---

## Wallet & FROZEN-v1 posture

- The bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` is referenced
  in this document only to assert that the solo track does not touch it.
- No private key, mnemonic, or `.env` credential of any VAPI wallet is
  referenced or imported anywhere in this workspace.
- No transaction is ever constructed at runtime.
- No deploy script exists in this workspace.
- No FROZEN-v1 primitive (the seven listed in the design PDF) is read,
  written, or hashed.

---

## Layout note for ceremony auditors

The design PDF specifies the in-monorepo layout as `src/brp/hash/`,
`src/brp/manifest/`, etc. This solo workspace uses the flatter layout
`src/hash/`, `src/manifest/`, `pv-ci-drafts/` because the workspace itself
(`solo/brp-renderer/`) already provides the `brp` namespace at the repo
boundary. At ceremony Step 6 (Mount), the integration team relocates the
artifact into `apps/gamer-portal/src/brp/` and re-establishes the inner
`brp/` prefix; the manifest, contract, hash domain, and decision blocks
all carry through unchanged.
