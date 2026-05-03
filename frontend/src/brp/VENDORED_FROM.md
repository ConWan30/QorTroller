# Vendored from `solo/brp-renderer/`

> **Source-of-truth: `solo/brp-renderer/` workspace.** This directory is a
> read-only vendored copy. Edit upstream first, run tests there, then
> re-vendor.

## Vendor anchor

- **Tag:** `brp-milestone-step4-complete`
- **Anchor commit:** `4a3d4793` (capture.mjs serialization + headless GL fix; the
  active milestone-anchored state of the solo workspace at vendor time)
- **Vendored at:** commit β of the incorporation series
  (`OPEN_QUESTIONS.md` OQ-7)

## What's vendored (deployed)

```
frontend/src/brp/
├── components/    AccessibilityShell, AmbientLayer, BrpCanvas,
│                  LegibilityOverlay, BrpMount, PerfOverlay (6 .tsx)
├── hash/          deriveBrpSeed, mulberry32, flashBudget,
│                  sceneFlashBudget (4 .ts)
├── telemetry/     contracts.ts (TypeScript prop contracts)
├── mocks/         loaders.ts + handlers.ts + browser.ts
│   └── fixtures/  pitl.snapshot.json + enrollment.session.json
└── manifest/      brp.manifest.json (static reference; no validator runs here)
```

## What's NOT vendored (stays in solo as design lab)

- `__tests__/` — 118 vitest tests run in solo against the source-of-truth.
- `__stories__/` — Storybook stories run in solo via `npm run storybook`.
- `pv-ci-drafts/` — INV-BRP-1..5 draft specs, ceremony-bound.
- Solo's own `vite.config.ts`, `vitest.config.ts`, `tsconfig.json`,
  `package.json`, `playwright.config.ts`, `e2e/`, `scripts/capture.mjs`,
  `.storybook/`, `public/mockServiceWorker.js`.

## Update procedure

1. Edit in `solo/brp-renderer/src/...`
2. Run `cd solo/brp-renderer && npx vitest run && npx tsc --noEmit`
3. Run `cd solo/brp-renderer && npm run build-storybook && npm run test:e2e`
4. Re-copy the changed files into `frontend/src/brp/` (no automated script
   yet; see OQ-7 for context). Files in this vendored tree mirror solo's
   `src/{components, hash, telemetry, mocks, manifest}/` exactly.
5. Update this file's "Anchor commit" line to the new solo HEAD commit.
6. Manual smoke: `npm run dev` in `frontend/`, click the BRP tab.

## Why vendor instead of import-from-sibling

Per Decision D1 (workspace isolation), `solo/brp-renderer/` has no
submodule, no symlink, no dependency edge into the protocol monorepo.
Vendoring is the explicit OQ-7 exception: the BRP code now lives in
two places, but the audit trail (this file + commit β's message)
keeps the source-of-truth claim unambiguous.

## What overrides this vendoring

The integration ceremony's Step 6 (Mount) relocates the artifact to
`apps/gamer-portal/src/brp/`. At that point, both `solo/brp-renderer/`
(test surface) and `frontend/src/brp/` (vendored deployed instance)
are superseded. Until then, this vendored copy is the deployed surface.
