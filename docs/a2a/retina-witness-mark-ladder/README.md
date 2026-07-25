# Retina Witness Mark — NOV ladder

**Opened:** 2026-07-24 (operator GO after first live L0 pass on `cfb_rwm_live_01`).

Per `docs/a2a/retina-witness-mark/scope.md` (D-RWM-1 Path A):

```text
L0 (RWM Path A)  →  NOV-3  →  NOV-2  →  NOV-1
```

Each layer opens **only after** the prior layer’s live verification passes.

| Layer | Name | Status |
|-------|------|--------|
| **L0** | RWM Path A — locator + per-frame hash chain sidecar | **DIVERSE CITE CLOSED** — `live_10` N=367 unique=367 + locator PASS; see `l0-live-session-live10-2026-07-25.md` (live_07/08 frozen OBS/menu; live_09 de-dup hold) |
| **NOV-3** | Ledger-native dispute escrow (selective disclosure over L0 leaves) | **BUILT + DOGFOOD** — live_01/05/07; pure-session ladder note `ladder-dogfood-live07-2026-07-25.md` |
| **NOV-2** | Cross-primitive session bind + multi-checkpoint locator | **BUILT + DOGFOOD** — bind + checkpoints + SHARE on live_07 |
| **NOV-1** | Portable stranger-verify dispute pack | **BUILT + DOGFOOD** — sd1 + **NOV-1.1 merkle** archive-free verify on live_07 |

## L0 hold posture (do not auto-advance)

| Item | State |
|------|--------|
| Primitives + F-RWM-9 + daemon wiring | on `main` |
| Default | **inert** — `RWM_L0_DAEMON_ENABLED` default false; needs `true` + `RWM_DEVICE_ID_HEX` |
| Live evidence | `cfb_rwm_live_01` (1076 frames, ~50% unique) preferred over `live_04` (frozen ring) |
| Post-check | `scripts/rwm_post_session_check.py` (includes unique-panel diversity INFO / `--strict-diversity`) |
| Live watch | `scripts/rwm_live_session_watch.py` — first-crop `eye_check_prompt` + mid-session `frozen_ring_alert` (default ≥10 identical recent crops; `--diversity-alert-at N`) |
| Mark size | default 32; optional `RWM_BLOCK_PX` env / `bridge/.env` (invalid → default) |
| Panel crop de-dup | `save_capture_crops` skips when `_panel_ts` unchanged **or** panel BGR SHA-256 unchanged (F-RWM-FROZEN + F-RWM-FROZEN-CONTENT; live_04–08) |
| NOV-3 code | does **not** couple to `cmd_stop` |
| NOV-2 | `scripts/rwm_nov2_cli.py` bind/checkpoints/share; pure modules under `bridge/vapi_bridge/rwm_*.py` |
| NOV-1 | `scripts/rwm_nov1_cli.py build --mode sd1_inline_media_v0\|merkle_inline_media_v0` |

## NOV-3 ship surface

| Path | Role |
|------|------|
| `bridge/vapi_bridge/rwm_dispute_escrow.py` | pure build/verify |
| `scripts/rwm_dispute_escrow.py` | offline CLI |
| `bridge/tests/test_rwm_dispute_escrow.py` | T1–T10 style suite |
| schema | `qortroller-rwm-dispute-escrow-v0` CANDIDATE |

```text
python scripts/rwm_dispute_escrow.py build \
  --archive retina_kf_archive/cfb_rwm_live_01_1784932933 \
  --reveal 0,1,2,3 \
  --reason "tournament dispute: sample frames" \
  --case-id DEMO-001

python scripts/rwm_dispute_escrow.py verify \
  --escrow audits/rwm_escrow_DEMO-001.json \
  --archive retina_kf_archive/cfb_rwm_live_01_1784932933
```

**Honest ceiling:** membership of L0 leaf hashes in a committed set + subset reveal. Not re-encode proof, not FROZEN, not on-chain, not stop-path.

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
  - locator decoded on real frames
  - content diversity measured (non-frozen preferred)
- Process finding closed in-repo: `cmd_stop` loads `RWM_*` via `_env_or_bridge_dotenv` (process env wins; else `bridge/.env`)
