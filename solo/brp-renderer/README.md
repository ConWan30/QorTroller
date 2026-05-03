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
