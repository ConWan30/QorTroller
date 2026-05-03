# BRP Solo Track — Open Questions for Integration Ceremony

> **Track classification: out-of-band-solo. NOT Phase 241. NOT in the sequential VAPI protocol chain.**
> This document enumerates decisions that the integration ceremony must make. Each entry carries candidates, trade-offs, and a current lean (where one is honest). The renderer ships `live: false` until each question is answered at ceremony time.

---

## Open questions

### OQ-1 — Canonical `frozenOutput` hash family

**Question.** When the host page passes `frozenOutput: Uint8Array` to `<BrpMount />`, which hash family is the canonical source?

The renderer treats `frozenOutput` as opaque. The choice is a *ceremony binding*, not a renderer concern. The choice must be recorded in `INTEGRATION_LOG.md` (created at ceremony) so a future audit can reproduce the visual seed deterministically.

**Candidates and trade-offs.**

| Candidate | Source | Update cadence | Why pick | Why not pick |
|---|---|---|---|---|
| **PoAC `record_hash`** | `SHA-256(raw[:164])` of the latest record | ~1 Hz (per `dualshock_record_interval_s = 1.0` at `bridge/vapi_bridge/dualshock_integration.py:357`) | Most fundamental; tightly bound to the certified hardware capture event. | No public GET-by-hash endpoint exists today (per F-5 closure in `BACKEND_CONTRACT.md`); high cadence may cause visual churn. |
| **GIC chain hash** | `compute_gic(prev, ...)` per CLAUDE.md FROZEN-v1 GIC formula | Per grind session (slower) | Tamper-evident; binds to operational continuity (paired with WEC). | Only meaningful during active grind; static otherwise. |
| **Corpus snapshot commitment** | `compute_corpus_snapshot_commitment(...)` per CLAUDE.md FROZEN-v1 CORPUS-SNAPSHOT formula | On operator force-snapshot | Stable; carries protocol-wide state attribution. | Update cadence is operator-driven, not session-driven; visual rarely changes. |
| **VAME commitment** | Sidecar header `X-VAME-Commitment` already validated by `frontend/src/api/client.js` | Per HTTP response | Already exposed and validated end-to-end; zero new infrastructure. | Per-response cadence may produce more visual churn than aesthetic intent allows. |
| **PoAd hash** | `Phase 111 AdjudicationRegistry` per CLAUDE.md | Per adjudication event | Carries decentralized-quorum attribution. | Adjudication events are sparse; visual rarely changes. |

**Current lean.** None. All five are honest answers depending on what the legibility overlay's "ambient signal" is meant to track. The ceremony picks based on the host page's mount intent.

**Who decides.** Integration ceremony, Step 6 (Mount), with the choice recorded in `INTEGRATION_LOG.md`.

**When.** At ceremony time. Pre-ceremony binding would be premature.

---

### OQ-2 — PITL-snapshot consumption pattern

**Question.** When `<BrpMount />` consumes `pitlSnapshot: PitlSnapshot`, does the host page wire it from `/dash/api/v1/pitl/timeline` or from `/agent/*` live-summary endpoints?

**Candidates and trade-offs.**

| Candidate | Source | Status | Why pick | Why not pick |
|---|---|---|---|---|
| **`/dash/api/v1/pitl/timeline`** | `bridge/vapi_bridge/dashboard_api.py:81`, mounted at `/dash` per `main.py:433` | API-stable (1 commit since initial), but **unconsumed by any active SPA hook** (per F-9 in the assessment) | Direct semantic match: minute-bucketed PITL detection events. | The BRP renderer would be the first SPA traffic exercising the `/dash/api/v1/*` namespace. Risk concentration. |
| **`/agent/*` live-summary endpoints** | e.g. `/agent/protocol-coherence-status`, `/agent/fleet-coherence-summary`, etc. | Already exercised by 17 active `useQuery` hooks in `frontend/src/api/bridgeApi.js` | Healthier traffic profile; the SPA's existing `useCaptureHealth`/`useGrindChain` cadences cover the staleness budget. | Less direct semantic match; aggregation may need composition across multiple endpoints. |

**Current lean.** `/agent/*`. Per F-9 (assessment §7), making the BRP renderer the first SPA consumer of `/dash/api/v1/*` would mean the renderer is also the first traffic exercising those routes in production. That risk concentration is not appropriate for an out-of-band solo track to take on alone. The renderer's prop contract is **namespace-agnostic** (see OQ-3); the host page's choice of upstream is what binds the namespace at integration time.

**Who decides.** Integration ceremony, Step 6 (Mount), informed by production telemetry.

**When.** At ceremony time, with the lean documented in `BACKEND_CONTRACT.md`.

---

### OQ-3 — Namespace agnosticism (resolved-by-design)

**Question.** Does the renderer bind to a specific backend namespace (`/dash/api/v1/*` vs `/agent/*` vs anything else)?

**Resolution.** **No.** The renderer's prop contract is types over `PitlSnapshot`, `EnrollmentSession`, etc. — TypeScript shapes, not URL strings. The host page wires whichever endpoint produces the matching shape; the renderer accepts the props.

This decision is **not deferred** — it is settled by design (D2 = 2-C, mount-agnostic). It is listed here for documentation completeness so a ceremony auditor reading `OPEN_QUESTIONS.md` does not interpret the absence of OQ-3 as a missed item.

**Implication.** OQ-2's lean is a recommendation to the host page, not a binding constraint on the renderer.

---

### OQ-5 — CI workflow placement (added Commit 4d)

**Question.** Where does the GitHub Actions workflow live, given the workspace's D1 isolation guarantee?

**Resolution.** **Deferred to integration ceremony Step 6 (Mount).** GitHub Actions only reads from repo-root `.github/workflows/`. Placing a workflow there would touch a path **outside** `solo/brp-renderer/`, violating Decision D1 (out-of-band isolation, no monorepo edges). Decision: defer to ceremony. At Step 6, when the artifact is vendored into the protocol monorepo's `apps/gamer-portal/src/brp/`, CI binding becomes natural — the protocol monorepo's existing CI infrastructure picks up the new path.

**Local-time substitute.** `npm run test:e2e` runs Playwright + axe-core against a built Storybook locally. The 4d gate works without CI. Capture script `npm run capture` produces WebM artifacts on demand.

**Who decides.** Integration ceremony, Step 6 (Mount).

**When.** At ceremony time. Pre-ceremony CI binding would force a D1 exception with no offsetting benefit.

---

### OQ-6 — PEAT/Harding FPA conversion pipeline (added Commit 4d)

**Question.** Captures from `npm run capture` are WebM (VP9). PEAT (Photosensitive Epilepsy Analysis Tool) requires 25fps uncompressed AVI. Is the conversion script part of the renderer or operator-driven?

**Resolution.** **Operator-driven; documented but not committed as a script.** The conversion is a single ffmpeg invocation:
```
ffmpeg -i dist/captures/<story>.webm -an -vcodec rawvideo -y -r 25 output.avi
```
Documented in `README.md` §"Commit 4d scope" subsection. ffmpeg is not committed as a workspace dep (large binary; system-installed). Operator runs the conversion when a tagged-milestone PEAT audit is needed.

**Why not ship the script?** Two reasons: (a) ffmpeg-side scripting is one line of bash, not script-worthy as a committed artifact; (b) PEAT itself is "retired" per UAMS Web Services (per CLAUDE.md / design-PDF research note); the W3C technique G19/G176/ΔL static analyzer (already shipped in 4a's `flashBudget.ts`) is the authoritative WCAG 2.3.1 conformance proof. PEAT is defense-in-depth.

**Who decides.** Operator at any tagged-milestone audit.

**When.** Ad-hoc, post-milestone.

---

### OQ-4 — Phase 13X research artifact re-read

**Question.** Should the Phase 13X research artifact's exact WebSocket prescription (`useRef`-managed WS with sequenced PoAC ingest, per the BRP design PDF's upstream context) be re-read before commit 4 (R3F surface)?

**Resolution.** **Deferred, conditionally.**

The Backend State Assessment §DW-2 evidence is sufficient for the docs in this commit:

- Active SPA uses zero WebSockets (`frontend/src/api/*.js` grep returns only `legacy/ControllerTwin.jsx:79,91`).
- Backend exposes three WS endpoints (`/ws/records`, `/ws/frames`, `/ws/twin/{device_id}` at `bridge/vapi_bridge/transports/http.py:230,248,797`).
- PoAC production cadence is ~1 Hz (`dualshock_integration.py:357`).
- Per-prop staleness budgets in `LATENCY_BUDGET.md` are all satisfied by REST polling at 3-5s cadence.

REST polling is the recommendation. The 13X prescription only needs re-reading if commit 4 surfaces a specific case where REST polling is genuinely insufficient — at which point the re-read happens *then*, not now.

**Who decides.** Author of commit 4 (R3F canvas), informed by whether their implementation hits a case requiring streaming.

**When.** Conditionally, during commit 4 design — not during this commit.

---

## Resolved decisions (NOT open)

For ceremony-auditor completeness, the items below are **not** open questions; they are settled and shipped:

| ID | Topic | Resolution | Where shipped |
|---|---|---|---|
| D1 | Workspace isolation | `solo/brp-renderer/` sibling to `frontend/`, no monorepo edges | Commit `8da89b59`; `README.md` "Decisions in force" table |
| D2 | Mount target | Mount-agnostic; ceremony picks placement | Commit `8da89b59`; `INTEGRATION_CONTRACT.md` Block T resolution |
| D3 | Hash library | viem, substituted for `ethers@6`; bit-equivalence verified | Commit `8da89b59`; `src/manifest/brp.manifest.json#hash_library`; `src/hash/__tests__/deriveBrpSeed.test.ts` canonical-vector lock at `0x87b0f938` |
| D4 | Commit 1 scope | Math + manifest + contract only; R3F deferred | Commit `8da89b59`; `README.md` |
| Q-1 (was D-1) | PV-CI gate count | N=32 at commit time per `.github/INVARIANTS_ALLOWLIST.json` | Commit `3f538547` (F-1 amend); `INTEGRATION_CONTRACT.md` "Gate count note" |
| Q-3 | `interperson-separation-data{,-v2}.json` selection | v1 canonical (35 keys, 2026-05-01); v2 stale historical (25 keys, 2026-03-11) | This commit; `BACKEND_CONTRACT.md` "Q-3 resolution" |

---

## Cross-references

- `BACKEND_CONTRACT.md` — endpoint inventory and prop→endpoint mapping (this commit).
- `LATENCY_BUDGET.md` — per-prop staleness tolerance and polling cadence (this commit).
- `INTEGRATION_CONTRACT.md` — ceremony steps, decision-block resolutions, honesty-first invariants (commit `8da89b59`, amended `3f538547`).
- `README.md` — workspace overview and commit-scope summary (commit `8da89b59`, this commit appends `## Commit 3 scope`).
