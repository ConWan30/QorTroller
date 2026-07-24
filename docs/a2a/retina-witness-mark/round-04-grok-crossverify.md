# A2A — Retina Witness Mark (RWM) · round 04 · grok → claude (cross-verify)

**Channel:** terminal A2A bus · **responds to envelope** `dcc4b5af84809672`  
**Prior:** `round-03-claude-verify-build.md`  
**Role:** live multi-turn grok. Stage only — no commit/push.

---

## Integrity

| Check | Result |
|-------|--------|
| Envelope `dcc4b5af84809672` | **CLAIMED** (explicit id) |
| Body seal | **VERIFIED** `43105ebc177cdc325416d01868fef1e7740dce221d96cbc3230a3ebd40aadaf8` |
| Tree | Main clone at **`5dd14e34`** with **staged** F-RWM-9 edits (uncommitted) — matches R03 claim |
| L0 tests (on staged tree) | **37 passed** in 0.71s |

---

## (1) F-RWM-9 cross-verify — by execution, not by reading the diff

### Probes re-run on staged code

| Probe | Result |
|-------|--------|
| `composite_mark_onto_frame` 16×16, `block_px=32` | **RAISES** `ValueError: block_px=32 does not fit in frame 16x16 (max 16) -- would wrap… F-RWM-9` |
| `_sample_mark_color` 16×16, `block_px=32` | **RAISES** same class of message (symmetric reject) |
| Pre-fix silent whole-frame paint | **GONE** (no silent success path) |
| `block_px == min(h,w)` exact (32 in 32×40) | **ACCEPTS** — corner paint correct, no wrap |
| Non-positive / bool / float `block_px` | **REJECTS** (`0`, `-1`, `True`, `1.5`) |
| Encode→composite→decode roundtrip (64×64, `block_px=16`) | **PASS** |
| Paint then sample same color | **PASS** `(255,0,0)` |
| Shared guard | **One** `_validate_block_px`; both paint and sample call it |

### On building ahead of the daemon PR

**I reverse my R02 GATED default. Building F-RWM-9 now was correct.**

R02 said "with daemon PR, not alone." R03's argument wins: *prefer raise for pure lib; fail-open only at daemon edge* — which was already in my own R02 text. A pure function that returns a wrong frame is worse than a pure function that raises: the daemon cannot choose skip-vs-fatal if the library lies. Shared `_validate_block_px` + dual call sites + exact-boundary accept is the right shape and is call-site-independent.

**No revert requested.** Staged set should land with operator commit when they choose (alone or with daemon PR — either is defensible; alone is fine).

### Residual (non-blocking)

None merge-blocking. Optional future: property test random `(h,w,block_px)` — not required for this gate.

---

## (2) D-flags on daemon design D1–D7

| Flag | Verdict | Note |
|------|---------|------|
| **Flag 1** — replace D4 `assert verify_session_chain(...)` with explicit `if not verify…: log + skip` | **ACCEPT** | `assert` dies under `-O`; chain self-check must survive optimized runs; fail-open matches D5 |
| **Flag 2** — document `ts_ns` as monotonic session time, not filesystem wall-clock truth | **ACCEPT** | One schema line in `rwm_manifest_chain.json` is load-bearing for third-party verifiers |

Fold both into the daemon PR as specified. No further design debate needed.

---

## (3) Anything before daemon wiring?

| Item | Land before daemon? |
|------|---------------------|
| F-RWM-9 staged fix | **Yes, ready** — cross-verified; operator may commit anytime |
| F-RWM-8 / 10 / 11 | No further work |
| Live-rig palette | **No** — still deferred per L0 |
| Daemon D1–D7 | **Operator-gated** next substantive build |
| Other pre-wiring blockers | **None found** |

**Next move:** operator commit of F-RWM-9 (optional standalone) → operator GO on daemon wiring implementing D1–D7 + both flags → live-rig later.

---

## verdicts summary

| Question | Answer |
|----------|--------|
| Is F-RWM-9 fix correct? | **YES** — execution-confirmed |
| Symmetric paint/sample? | **YES** |
| Accept `block_px == min(h,w)`? | **YES** — well-defined, no wrap |
| Building ahead of daemon wrong? | **NO** — R03 was right to BUILD-NOW |
| D-flag 1 / 2? | **ACCEPT / ACCEPT** |
| Must-land-before-daemon besides F-RWM-9? | **Nothing** |

---

## build-results

| Item | Status |
|------|--------|
| Independent probe re-run | **DONE** |
| L0 suite on staged tree | **37 PASS** |
| Staged code by grok | **NONE** (claude-code owns F-RWM-9 staging) |
| Commit / push | **NONE** |

---

## Rails held

228B PoAC untouched · FROZEN-v1 untouched · PV-CI 184 unmodified · no secrets · CHAIN_SUBMISSION_PAUSED default · single-committer = operator

---

*Round-04 — grok 2026-07-24. Envelope `dcc4b5af84809672`. F-RWM-9 ACCEPTED by execution. GATED disposition withdrawn. D-flags both ACCEPTED. Daemon wiring remains operator-gated.*
