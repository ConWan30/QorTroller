# Retina Witness Mark — NOV ladder

**Opened:** 2026-07-24 (operator GO after first live L0 pass on `cfb_rwm_live_01`).

Per `docs/a2a/retina-witness-mark/scope.md` (D-RWM-1 Path A):

```text
L0 (RWM Path A)  →  NOV-3  →  NOV-2  →  NOV-1
```

Each layer opens **only after** the prior layer’s live verification passes.

| Layer | Name | Status |
|-------|------|--------|
| **L0** | RWM Path A — locator + per-frame hash chain sidecar | **LIVE-VERIFIED** 2026-07-24 — see `l0-live-verify-2026-07-24.md` |
| **NOV-3** | Ledger-native dispute escrow (selective disclosure over L0 leaves) | **SCOPE OPEN + PLAN DRAFTED** — `nov-3-scope.md` · `nov-3-implementation-plan.md` (plan-only; build needs operator GO) |
| **NOV-2** | *(not opened)* | gated on NOV-3 live-verify |
| **NOV-1** | *(not opened)* | gated on NOV-2 live-verify |

## Rails (all ladder work)

- 228-byte PoAC wire: **untouched**
- FROZEN-v1 formulas / domain tags: **untouched** unless a future layer explicitly freezes a new CANDIDATE family via PV-CI ceremony
- PV-CI 184 baseline: hold until a deliberate invariant add is operator-sealed
- `CHAIN_SUBMISSION_PAUSED`: held unless operator lifts for a named on-chain step
- single-committer: **operator**
- Capture archives / device ids in proofs: never commit raw ring crops or secrets

## L0 evidence (gate that opened this directory)

- Session: `cfb_rwm_live_01_1784932933`
- Artifact (local, gitignored): `retina_kf_archive/cfb_rwm_live_01_1784932933/rwm_manifest_chain.json`
- `scripts/rwm_post_session_check.py --label cfb_rwm_live_01` → **EXIT 0**
  - chain re-verifies from disk
  - originals byte-identical
  - locator decoded on **1076/1076** real frames (OBS pipeline path)
- Process finding closed in-repo: `cmd_stop` now loads `RWM_*` via `_env_or_bridge_dotenv` (process env wins; else `bridge/.env`)
