# BRP Renderer — Solo Track

> **This is an out-of-band, parallel, solo development track.**
> It is **NOT** Phase 241 in the sequential VAPI protocol chain.
> It is **NOT** part of any active phase.
> It will integrate downstream once Phase O0 (`vapi-anchor-sentry` +
> `vapi-guardian`) is foundationally live.
> Until then, every surface ships with `"live": false`.

---

## Purpose

This workspace produces a self-contained, locally-runnable, mock-driven
React Three Fiber (R3F) artifact that:

1. Reads from mock telemetry shaped exactly like the production
   PITL/calibration contracts but **never** depends on a live VAPI node, the
   IoTeX testnet, the bridge wallet, or any deployed-addresses registry.
2. Renders an ambient visualization seeded from a deterministic hash of
   verification-side outputs (treated as opaque inputs), with **no feedback
   path** back into VHP, separation ratio, PoAC metadata, or any ZK circuit.
3. Carries `"live": false` on every emulated surface for the entire
   development period.
4. Specifies the integration contract (`INTEGRATION_CONTRACT.md`) that must
   be honored at downstream merge.

---

## Commit 1 scope (this commit)

Math + manifest + contract only. **No** R3F canvas, **no** Storybook, **no**
Playwright, **no** MSW handlers in this commit. Those land in commit 2+.

```
solo/brp-renderer/
├── package.json                      zero monorepo dependency edges
├── tsconfig.json                     strict mode
├── vitest.config.ts                  test runner
├── .eslintrc.json                    INV-BRP-2 (draft) — verification-downstream
├── .gitignore
├── README.md                         this file
├── INTEGRATION_CONTRACT.md           handoff specification
├── src/
│   ├── hash/
│   │   ├── deriveBrpSeed.ts          keccak256("VAPI-BRP-RENDER-v1" || frozen) → uint32
│   │   ├── mulberry32.ts             deterministic 32-bit visual PRNG
│   │   ├── flashBudget.ts            G19/G176/ΔL static analyzer (pure-function form)
│   │   └── __tests__/
│   │       ├── deriveBrpSeed.test.ts            determinism + domain separation + D3 equivalence + canonical vector lock
│   │       ├── mulberry32.test.ts               determinism + period sanity + mean ≈ 0.5
│   │       ├── keccak256-vectors.test.ts        INV-BRP-3 by verification (Ethereum/Keccak-256 reference vectors)
│   │       └── flashBudget.test.ts              every threshold tested at boundary + saturated-red guard
│   └── manifest/
│       ├── brp.manifest.json         live-flag manifest, every component live: false
│       ├── validate.ts               schema validator
│       └── __tests__/
│           └── manifest.test.ts      schema + tamper-rejection
└── pv-ci-drafts/
    ├── inv-brp-1.spec.ts             live-flag honesty (DRAFT — not added to PV-CI)
    ├── inv-brp-2.spec.ts             verification-downstream import boundary
    ├── inv-brp-3.spec.ts             hash-domain isolation
    ├── inv-brp-4.spec.ts             photosensitivity budget
    └── inv-brp-5.spec.ts             accessibility surface
```

---

## Decisions in force

| ID | Resolution | Reasoning |
|----|------------|-----------|
| D1 (isolation) | **1-A**. Workspace lives at `solo/brp-renderer/` — sibling to `frontend/`, **not** inside it. Own `package.json`. No submodule, no symlink, no dependency edge into the protocol monorepo. | Honors the design PDF's load-bearing isolation guarantees while still satisfying "exclusively to VAPI frontend" (the work is in a sibling, not in protocol code). |
| D2 (mount target) | **2-C**. Mount-agnostic. `<BrpMount />` is a self-contained component with a typed prop contract. Mount placement is deferred to the integration ceremony. | The frontend currently has no router and no `/gamer/twin` route — `controller-twin.html` is mounted via iframe. Picking a mount target now would be a stub the ceremony will undo. |
| D3 (hash library) | **viem** instead of `ethers v6`. | Bundle budget — `viem` already provides `keccak256`, `toBytes`, `concat`. Adding `ethers` would cost ~280 KB. Bit-equivalence verified via canonical-vector and equivalence tests (INV-BRP-3 by verification). |
| D4 (commit scope) | **4-B**. Math + manifest + contract only this commit. | Smallest blast-radius foundation. R3F surface, Storybook, Playwright, MSW arrive in commit 2+ once this layer is locked. |

---

## Layout notes (for ceremony auditors)

The design PDF specifies an in-monorepo layout of `src/brp/hash/`,
`src/brp/manifest/`, etc. This solo workspace deliberately uses the flatter
layout `src/hash/`, `src/manifest/`, `pv-ci-drafts/` because the workspace
itself (`solo/brp-renderer/`) already provides the `brp` namespace at the
repo boundary. At ceremony Step 6 (Mount), the integration team relocates
the artifact into `apps/gamer-portal/src/brp/` and re-establishes the inner
`brp/` prefix. The manifest, contract, hash domain, and decision blocks all
carry through unchanged.

The ESLint `no-restricted-imports` rule in `.eslintrc.json` enforces the
import boundary at the repo level (`solo/brp-renderer/` cannot import from
`frontend/src/**`, `bridge/**`, `contracts/**`, `sdk/**`, `scripts/**`,
`agents/**`, `ethers`, or `hardhat`); after relocation, the same rule
re-targets the `src/brp/**` path with no semantic change.

---

## Running the tests

```bash
cd solo/brp-renderer
npm install
npm test
```

Tests should be deterministic and complete in under a few seconds. No
network call should escape; no chain RPC; no wallet operation.

---

## Commit 2 scope (PV-CI gate-count amend, `3f538547`)

Single-file amend: `INTEGRATION_CONTRACT.md` "Gate count note" paragraph
corrected from N=28 → N=32 to match `.github/INVARIANTS_ALLOWLIST.json`
ground truth at commit time, with provenance recorded in the document
itself (see the "Provenance note" sub-paragraph in `INTEGRATION_CONTRACT.md`).

## Commit 4c scope (LegibilityOverlay + BrpMount + fixtures)

Third sub-commit of the four-step Step 4 R3F surface. Lands the
calibration-aid HUD, the top-level public component, and the
synthetic shape-validation fixtures.

- `src/components/LegibilityOverlay.tsx` — plain-HTML 7-row PITL
  state panel, `position: absolute` over `BrpCanvas`. Deliberately
  NOT drei `<Html>` (deviation from PDF §"Component structure"
  documented in commit message): keeps the overlay as a DOM
  sibling of the canvas, decoupled from `BrpCanvas`'s lifecycle,
  testable in isolation. `role="region"` + `aria-label` +
  `data-live="false"` + `data-brp-overlay="true"`.
  `aidThreshold` gate is a placeholder per Block Z (deferred);
  ceremony picks the real metric. Pure helper `isActiveAidMode`
  exported for unit testing.
- `src/components/BrpMount.tsx` — top-level public component.
  Accepts the full `BrpMountProps` contract from
  `telemetry/contracts.ts`. Composes `<AccessibilityShell>` →
  layout root → `<BrpCanvas>` + `<LegibilityOverlay>` +
  optional `<EnrollmentBadge>`. This is the slot the integration
  ceremony mounts at `/gamer/twin` per Block T.
- `src/mocks/fixtures/{pitl.snapshot,enrollment.session}.json` —
  synthetic shape-validation fixtures. JSON encodes BigInt fields
  as decimal strings; loaders convert at load time.
- `src/mocks/loaders.ts` — typed loaders
  `getMockPitlSnapshot()` + `getMockEnrollmentSession()`. Validate
  shape at module load (throws loudly on malformed fixtures).
  Return frozen, deterministic references.
- `main.tsx` updated: mounts `<BrpMount {...devProps}>` with
  fixture data instead of bare `<BrpCanvas>`. Dev surface now
  shows canvas + overlay + enrollment badge together.

MSW deferred to 4d (where Storybook stories will need
network-level mocking for non-static fixture variations).

Tests: 94 → 107 (+13: 5 LegibilityOverlay + 5 BrpMount +
3 loaders + 3 manifest progression). tsc --noEmit clean.

## Commit 4b scope (R3F core: BrpCanvas + AmbientLayer + sceneFlashBudget)

Second sub-commit of the four-step Step 4 R3F surface. Lands the actual
R3F mount: a hash-seeded ambient mesh under the AccessibilityShell context.

- `src/components/BrpCanvas.tsx` — `@react-three/fiber` Canvas wrapper.
  Consumes `motionShouldPause` from AccessibilityShell context →
  `frameloop="never"` when paused, `"demand"` otherwise (PDF §A1).
  Sets `role="presentation"` + `aria-hidden="true"` on the Canvas root
  (PDF Block X PITL row coexistence). `data-live="false"` on the wrapper.
  Pure helper `computeFrameloop(motionShouldPause)` exported for unit
  testing without R3F.
- `src/components/AmbientLayer.tsx` — pure `seedToInstanceParams(seed,
  count)` generates 64 deterministic instances from Mulberry32 with
  audit-readable bounds (positions ∈ [-1,1]³, rotations ∈ [0, 2π)³,
  scale ∈ [0.5, 1.5]). drei `<Instances>` mesh, single draw call,
  low-poly icosahedron geometry.
- `src/hash/sceneFlashBudget.ts` — INV-BRP-4 progression hook. Bridges
  scene-data to the existing pure-function `flashBudget.evaluateScene`.
  Exports `AMBIENT_LAYER_MATERIAL` static descriptor (frequency_hz=0.5,
  area_css_px2=50,000, delta_luminance=0.05, not red) — passes WCAG
  2.3.1 by construction with 6× / 1.7× / 2× margins on the three
  pathways simultaneously.
- `src/main.tsx` updated: mounts `<BrpCanvas frozenOutput={32-zero-bytes}>`
  inside `<AccessibilityShell>` for dev surface. The locked seed
  `0x87b0f938` (per `deriveBrpSeed.test.ts` canonical-vector lock) is
  what the dev surface visualizes — operator verifies the seed→visual
  chain by reload.

R3F deps added (versions match `frontend/package.json` for ceremony
portability): `@react-three/fiber@^8.17.10`, `@react-three/drei@^9.117.3`,
`three@^0.170.0`, `@types/three@^0.170.0`.

Tests: 79 → 90 (+11). All R3F-WebGL-dependent assertions are deferred
to 4d's Storybook + Playwright; component tests in 4b mock
`@react-three/fiber` and `@react-three/drei` to assert React surface
without WebGL.

PerformanceMonitor (drei) deferred to 4d alongside its Storybook
visual validation.

## Commit 4a scope (TS contracts + Vite + AccessibilityShell)

First sub-commit of the four-step Step 4 R3F surface (4a/4b/4c/4d).
Lands the build/test infrastructure and the pure-DOM accessibility
primitives that the R3F canvas (4b) will compose under:

- `src/telemetry/contracts.ts` — TypeScript shapes for the renderer's
  prop contract: `PitlRow`, `PitlSnapshot`, `EnrollmentSession`,
  `LivenessFlags`, `BrpMountProps`. Mount-agnostic per Decision D2;
  every value is opaque to the renderer.
- `src/components/AccessibilityShell.tsx` — DOM-only component with
  `role="presentation"` + `data-live="false"` shell root, sr-only
  description sibling, `prefers-reduced-motion` matchMedia listener,
  and a WCAG 2.2.2 photosensitivity-safety toggle persisted in
  `localStorage` under the namespaced key `brp:motionDisabled`.
  Exposes `motionShouldPause` to children via React context (4b's
  `BrpCanvas` will consume).
- `vite.config.ts` + `index.html` + `src/main.tsx` — Vite dev surface.
  `npm run dev` mounts the AccessibilityShell with placeholder text;
  `npm run build` produces a tsx build artifact.
- `vitest.config.ts` switches `environment: node → jsdom` (math +
  manifest tests still pass; required for component tests).
- `tsconfig.json` adds `"jsx": "react-jsx"`.
- AccessibilityShell.test.tsx ships +8 tests; manifest.test.ts ships
  +1 progression assertion. Total vitest count: **78** (was 70).

R3F deps (`@react-three/fiber`, `@react-three/drei`, `three`) arrive
in 4b. MSW + fixtures arrive in 4c. Storybook + Playwright + axe-core
+ capture script arrive in 4d.

## Commit 3 scope (backend contract / latency budget / open questions)

Three new documents land alongside the foundation, plus a small manifest
schema extension to track them:

- `BACKEND_CONTRACT.md` — verified-as-of-commit endpoint inventory,
  prop→endpoint mapping for `<BrpMount />`, Q-3 resolution
  (interperson-separation v1 canonical), and an "Upstream spec drift"
  section flagging F-5/F-6 for ceremony auditors.
- `LATENCY_BUDGET.md` — per-prop staleness tolerance with REST polling
  cadence references (matches existing `useCaptureHealth` 3s and
  `useGrindChain` 5s patterns; no new pattern introduced).
- `OPEN_QUESTIONS.md` — OQ-1 (canonical `frozenOutput` hash family;
  five candidates), OQ-2 (PITL-snapshot consumption pattern; lean
  toward `/agent/*`), OQ-3 (namespace agnosticism resolved-by-design),
  OQ-4 (Phase 13X re-read deferred).

Manifest extension: `brp.manifest.json` gains a `docs:` bucket with
three `live: false` entries (one per new doc). Schema validator and
manifest tests extended; total vitest count moves 67 → 70.

R3F canvas surface (Commit 4+) is intentionally out-of-scope for
Commit 3 and will be planned separately once these docs land.

---

## What this commit must NOT do

- Touch any file outside `solo/brp-renderer/`.
- Add R3F components, Storybook, Playwright, MSW handlers, or any rendering
  code.
- Modify `frontend/`, `contracts/`, `agents/`, `scripts/`,
  `deployed-addresses.json`, `CLAUDE.md`, `MEMORY.md`, or any active VAPI
  work stream.
- Add `INV-BRP-1..5` to the PV-CI gate (gate stays at 28 at the time of
  this commit).
- Construct any transaction, reference any private key, or import any RPC
  provider.
- Number this work as a phase. The README, manifest, and
  `INTEGRATION_CONTRACT.md` all explicitly state the out-of-band
  classification.

---

## Honesty-first posture

The work is *safe to do now* because every byte of it is rendering-side and
verification-orthogonal; the work is *not yet integrable* because the O0
Operator series (`anchor-sentry` + `guardian`) must be foundationally live
first to host the telemetry surface BRP consumes.

Honesty-first architecture is not decorative; it is the defensible product
property.
