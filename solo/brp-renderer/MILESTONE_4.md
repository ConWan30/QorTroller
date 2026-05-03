# BRP Solo Track — Milestone: Step 4 Complete

> **Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential VAPI protocol chain.**
> Self-review note for tag `brp-milestone-step4-complete`.
> Date: 2026-05-03.

---

## Status

**Step 4 (R3F surface) is fully shipped across four sub-commits + two repair commits + the F-1 amend + the foundation. The BRP renderer's local development surface is structurally complete and ready for integration ceremony binding.**

The track has reached the natural milestone the design PDF anticipates: every file, test, story, and tooling artifact required by the design specification is now in place. The renderer's WCAG 2.3.1 + 2.2.2 + canvas-a11y + `prefers-reduced-motion` + photosensitivity-toggle conformance is verifiable end-to-end.

What remains is **integration-ceremony work** (vendoring into the protocol monorepo's `apps/gamer-portal/src/brp/`), and that depends on Phase O0 (`vapi-anchor-sentry` + `vapi-guardian`) being foundationally live. Phase O0 is currently paused pending wallet refill per the protocol monorepo's `CLAUDE.md`. The BRP track sits in a stable holding state; nothing further can ship through the solo track until the ceremony unlocks.

---

## What shipped (nine commits)

| # | Commit | Purpose | Files |
|---|---|---|---|
| 1 | `8da89b59` | Foundation: math + manifest + INV-BRP-1..5 drafts + INTEGRATION_CONTRACT + README | 20 |
| 2 | `3f538547` | F-1 amend: PV-CI gate count 28 → 32 (verification-discipline-first drift correction) | 1 |
| 3 | `fc89ae85` | Repair 1: narrow `.gitignore` exception + restored 3 manifest files silently dropped from `8da89b59` by the `MANIFEST` rule | 4 |
| 4 | `e9db8c1c` | Step 3: `BACKEND_CONTRACT.md` + `LATENCY_BUDGET.md` + `OPEN_QUESTIONS.md` + manifest `docs:` bucket | 7 |
| 5 | `7c9cae81` | Step 4a: TypeScript prop contracts + Vite + AccessibilityShell | 14 |
| 6 | `246bb718` | Step 4b: R3F core (BrpCanvas + AmbientLayer + sceneFlashBudget + main.tsx mount) | 12 |
| 7 | `3dda7ae6` | Repair 2: broadened `.gitignore` BRP exception (kills the silent-skip class) | 1 |
| 8 | `8fb43c65` | Step 4c: LegibilityOverlay + BrpMount + MSW fixtures + loaders | 12 |
| 9 | `b3b7f39d` | Step 4d: Storybook + Playwright + axe-core + capture script + PerfOverlay (+ bundled LegibilityOverlay color-contrast amendment) | 26 |

**Total: 97 file deltas across 9 atomic commits.** No commit was reverted, amended, or force-pushed. Every commit was bracketed by Hold-1 proposal → Y/N approval → Hold-2 verification → atomic commit.

---

## Test surface

| Test type | Count | Where |
|---|---|---|
| vitest unit/component (jsdom) | **118** | `npm test` |
| Playwright + axe-core e2e (chromium) | **22** | `npm run test:e2e` |
| Storybook stories (visual contract) | **21** + meta-test = 22 | `npm run storybook` (dev) / `npm run build-storybook` |
| `tsc --noEmit` (strict mode + `noUncheckedIndexedAccess` + `noImplicitOverride`) | clean | `npx tsc --noEmit` |
| ESLint `no-restricted-imports` rule (INV-BRP-2 draft) | active | `npm run lint` |

The 118 vitest tests cover: 9 deriveBrpSeed + 6 mulberry32 + 6 keccak256-vectors + 15 flashBudget + 4 sceneFlashBudget + 5 AmbientLayer + 4 BrpCanvas + 8 AccessibilityShell + 6 LegibilityOverlay + 5 BrpMount + 3 mockLoaders + 3 PerfOverlay + 16 manifest schema progression + 22 PV-CI INV-BRP-1..5 draft specs.

The 22 Playwright tests cover one axe-core run per Storybook story (no rules disabled — full standard axe ruleset) plus a meta-test asserting the empty disabled-rules list.

---

## Three real bugs caught by verification-discipline-first

1. **F-1 (commit `3f538547`).** PV-CI gate-count documentation drift. The Hold-1 D-1 correction at the foundation commit (lowering from 32 to 28 based on a CLAUDE.md NOTE) was *itself* drift in the opposite direction — the actual `.github/INVARIANTS_ALLOWLIST.json` had 32 entries. Caught by the Backend State Assessment session's F-1 finding. Lesson: the discipline catches drift in *both* directions, including drift the operator + assistant introduced in good faith.

2. **`.gitignore` silent-skip (commits `fc89ae85` + `3dda7ae6`).** Foundation commit `8da89b59`'s message claimed it shipped three manifest files. It did not — `MANIFEST` (line 20 of repo-root `.gitignore`) silently matched `solo/brp-renderer/src/manifest/` on Windows (case-insensitive). The `git status --short` Hold-2 check passed because the files were never dirty. Caught at Step 3 commit's verification, repaired narrowly in `fc89ae85`. Then **the same class recurred** at Step 4c when `*.session.json` matched `enrollment.session.json`. Caught earlier this time by `git check-ignore -v` on every staged path (the Hold-2 invariant added after `fc89ae85`'s lesson). Repaired broadly in `3dda7ae6`: workspace-wide negation `!solo/brp-renderer/**` placed at end-of-file (last-match-wins). The class is now structurally closed.

3. **WCAG AA color-contrast violation in LegibilityOverlay (commit `b3b7f39d` 4c amendment).** The original LegibilityOverlay (commit `8fb43c65`) blended text via parent `opacity: row.active ? 1 : 0.4` rules; this collapsed `#dde` text against the active-aid background `#233547` to a perceived `#6e788a` at 2.81:1, failing WCAG AA (4.5:1). Caught the *first time* axe-core actually ran in 4d. Source-component test in 4c was functionally correct (ARIA, structure, semantics) but visually inaccessible — exactly the kind of bug only end-to-end visual validation surfaces. Bundled fix in 4d's atomic commit: discrete colors instead of opacity blending.

---

## Verification-discipline lessons recorded

- **`git status --short` collapses untracked directories.** Future Hold-2 must also use `--untracked-files=all` to reveal individual file visibility (recorded in `3dda7ae6`).
- **`git check-ignore -v` on every staged path is non-negotiable.** It catches silent-skip drift the `git status` invariant alone cannot detect (recorded in `fc89ae85` and `3dda7ae6`).
- **Per-rule narrow exceptions are tactical and brittle. Workspace-wide exceptions are strategic and maintainable.** When a class of drift recurs, broaden once instead of patching twice (recorded in `3dda7ae6`).
- **Source-component tests can be functionally correct and visually inaccessible.** ARIA-attribute assertions ≠ axe-core conformance. The verification-discipline gate must include real-browser axe runs against built stories (recorded in `b3b7f39d`).
- **R3F's `frameloop` keeps the page busy; `networkidle` never fires for R3F-rendering Playwright tests.** Use `domcontentloaded` + selector wait + a brief settle (recorded in `b3b7f39d`).
- **The original Hold-1 D-1 correction was wrong against ground truth.** Stale CLAUDE.md NOTE blocks can produce drift even when the operator and assistant both reason carefully. The binding answer is the file-on-disk, not the documentation about it (recorded in `3f538547`).

---

## What remains (all ceremony-bound or operator-driven)

| Item | Status | Where tracked |
|---|---|---|
| Mount placement at `/gamer/twin` | Ceremony Step 6 | `INTEGRATION_CONTRACT.md` Block T |
| Enrollment-overlay ownership | Ceremony Step 4 (Block V deferred) | `INTEGRATION_CONTRACT.md` Block V |
| Empirical aid-to-calibration threshold | Ceremony Step 4 (Block Z deferred) | `INTEGRATION_CONTRACT.md` Block Z |
| Canonical `frozenOutput` hash family | Ceremony decision | `OPEN_QUESTIONS.md` OQ-1 |
| PITL-snapshot consumption pattern (`/agent/*` lean) | Ceremony decision | `OPEN_QUESTIONS.md` OQ-2 |
| Phase 13X re-read | Conditional, deferred | `OPEN_QUESTIONS.md` OQ-4 |
| GitHub Actions CI workflow | Ceremony Step 6 (D1-bound) | `OPEN_QUESTIONS.md` OQ-5 |
| PEAT/Harding 25fps AVI conversion | Operator-driven ffmpeg one-liner | `OPEN_QUESTIONS.md` OQ-6 |
| INV-BRP-1..5 adoption to PV-CI gate | Ceremony Step 5 | drafted in `pv-ci-drafts/` |
| Tagged-milestone WebM capture archive | Operator-driven via `npm run capture` | per design PDF §"Cadence" |
| Visual regression baselines | Ceremony / future commit | not started (commit-bloat trade-off) |
| Live-flag flips (`live: false` → `true`) | Ceremony Step 7 | per `live_flag_transition_rules` in `brp.manifest.json` |

---

## Untouched (proven across every commit)

- `CLAUDE.md`, `MEMORY.md`, repo-root `.gitignore` after the two scoped repairs
- `frontend/`, `bridge/`, `contracts/`, `sdk/`, `agents/`, `scripts/`
- The 5 FROZEN-v1 cryptographic primitives (GIC + WEC + VAME + CORPUS-SNAPSHOT + CONSENT)
- The PV-CI invariant gate (still N=32 at `b3b7f39d`)
- Bridge wallet `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` — referenced exactly once across 97 file deltas, in `INTEGRATION_CONTRACT.md`'s wallet-posture paragraph asserting non-touch
- Pre-existing 535-line repo-wide dirty tree byte-identical pre/post every commit (with one operator-noted exception for ambient calibration-agent activity during long Storybook builds in 4d)

---

## Self-review

The track demonstrated the verification-discipline-first pattern under realistic conditions. Three classes of drift were caught and repaired cleanly. Every commit is single-concern; every commit is atomically reversible; every commit's message records *why* alongside *what*. The two repair commits are not failures — they are the discipline working: drift surfaced at a checkpoint, repair landed as a separate single-concern commit, work continued.

The milestone is ready for the integration ceremony when Phase O0 unlocks. Until then, the track is in a stable holding state. The next operator decision is whether to push the nine commits to `origin/main` (currently 9 ahead, never auto-pushed per the explicit guardrail) or hold them locally pending ceremony.

---

## Tag binding

This document is the self-review note for `git tag brp-milestone-step4-complete` placed on commit `b3b7f39d`. The tag is annotated with a one-line summary; this `MILESTONE_4.md` is the long-form record. Future tagged milestones (per design PDF §"Cadence") follow the same convention.
