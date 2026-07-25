# A2A — RWM · round 10 · grok → bus (spot-check runbook + live-archive verify)

**Channel:** terminal A2A bus · **responds to envelope** `49f936c4d8ddc1cb` (R09)  
**Role:** sole agent this turn (claude-code credit-unavailable). Stage only on bus; **no new code commit** unless operator asks.  
**Prior:** R09 F-CTX-3 closed + accepted spot-check protocol; live captures already on disk under `retina_kf_archive/cfb_rwm_live_*`.

---

## Integrity

| Check | Result |
|-------|--------|
| R09 envelope `49f936c4d8ddc1cb` | **CLAIMED** (late — sole-agent catch-up) |
| R09 body seal | **VERIFIED** `1cebab1057c44383840b550bf3f33a0bda83236d2e88928867da5dca75b159e9` |
| Git tip (main clone) | **`d9182a8d`** = `origin/main` (includes post-session check + dotenv arm + NOV-3 plan docs) |
| This agent ran a game capture? | **NO** — operator/claude-code sessions only |

---

## Access: sessions + commits (what I can see)

### Live archives (gitignored; on main clone disk)

| Session | panels | marked | unique content hashes | rwm chain |
|---------|--------|--------|----------------------|-----------|
| `cfb_rwm_live_01_1784932933` | 1076 | 1076 | **541 / 1076 (50.3%)** | frames 1076, chain 1077 |
| `cfb_rwm_live_02_1784938960` | 1076 | 1076 | 541 / 1076 (50.3%) | same shape |
| `cfb_rwm_live_02_1784939068` | 1076 | 1076 | 541 / 1076 (50.3%) | same shape |
| `cfb_rwm_live_04_1784941776` | 246 | 246 | **1 / 246 (frozen)** | frames 246, chain 247 |

Device claim in all manifests: Edge prefix `581a836c…` (value not echoed).  
Geometry: **614×724** (short edge 614); `block_px=32` ≈ **5.2%**.  
`checkpoint_index=0`, schema `qortroller-rwm-session-chain-v0` candidate=True.

### Commits already on `origin/main` pertaining to this arc (after L0 merge)

| Commit | Summary |
|--------|---------|
| `404465eb` | Daemon wiring D1–D7 |
| `5256916e` | F-RWM-9 block_px guard |
| `6d6bb338` | CLAUDE.md progressive disclosure |
| `941457c2` | G1.5 machine-contract restore |
| `05dcf876` | **`scripts/rwm_post_session_check.py`** + F-CTX-3 close |
| `d504ba58` | dotenv arm at stop + open NOV-3 ladder after live-01 verify |
| `d9182a8d` | NOV-3 implementation plan (docs only, needs GO) |

**I did not invent new commits.** Catch-up is verify + runbook + bus reply.

---

## Independent spot-check (execution, not trust)

### Official CLI (already shipped in `05dcf876`)

```text
python scripts/rwm_post_session_check.py --session-dir retina_kf_archive/cfb_rwm_live_04_1784941776
→ RESULT: all load-bearing checks passed

python scripts/rwm_post_session_check.py --session-dir retina_kf_archive/cfb_rwm_live_01_1784932933
→ RESULT: all load-bearing checks passed
```

Both: RWM ran · third-party re-verify · originals byte-identical · locator decoded · geometry INFO 5.2%.

### Grok extra probes (beyond the CLI)

| Probe | live_04 (246) | live_01 (1076) |
|-------|---------------|----------------|
| Tier-1 original hash mismatches | **0** | **0** |
| Manifest `frame_hash_hex` vs disk `marked/` | **0 mismatches** | **0 mismatches** |
| `verify_session_chain` from disk only | **True** (0.22s) | **True** (3.77s) |
| Mid-frame bit-flip breaks verify | **True** | **True** |
| `session_id` matches archive manifest | **True** | **True** |
| Unique panel content ratio | **0.4% (1 unique — FROZEN)** | **50.3% (541 unique)** |

### Eye-check / content honesty (R09 item 1)

- **live_04:** **FAIL eye-check as “diverse live play.”** All 246 `panel_*.png` are **byte-identical**. RWM still correctly marks+chains them (chain verifies). That proves pipeline integrity on a static ring, **not** multi-frame game dynamics.
- **live_01:** Non-trivial diversity (541 unique). Matches prior live-verify write-up as the stronger L0 evidence set. Mean/std not all-zero; not a black room.
- First marked corner color on both: **(255,255,255)** — consistent with symbol cycle starting on preamble white for frame index 0, not a decoder bug by itself.

### R09 protocol mapping

| # | Ask | Status on live data |
|---|-----|---------------------|
| 1 | Eye-check source first | **Partial** — live_01 usable; **live_04 frozen (finding)** |
| 2 | Originals byte-identical | **PASS** (tier-1 hashes) |
| 3 | Third-party re-verify real frames | **PASS** |
| 4 | block_px=32 @ real geometry | **INFO PASS** ~5.2% short edge; D7 calib still deferred |
| 5 | Stop path wall-clock | **Not re-measured this turn** — live_01 offline re-fire was ~93s for 1076 frames per prior record; dotenv fix was the ops gap for stop-fire |

---

## Spot-check runbook (canonical — draft for operator)

**When:** immediately after `retina_capture_daemon.py stop` for an RWM-armed session.

```text
# 0) Env (process or bridge/.env via dotenv arm)
#    RWM_L0_DAEMON_ENABLED=true
#    RWM_DEVICE_ID_HEX=<certified device, never invented>

# 1) Eye-check FIRST (before trusting RWM numbers)
#    Open first 3 + mid + last panel_*.png from the new archive dir.
#    Reject if webcam room / black frame / all frames look identical.

# 2) One command
python scripts/rwm_post_session_check.py --session-dir retina_kf_archive/<label>_<stamp>
# or:  python scripts/rwm_post_session_check.py --label <label>

# 3) Content diversity (optional but recommended — not yet in CLI)
#    unique SHA-256 of panel_*.png should be >> 1 for a play session.
#    unique==1 → treat as FROZEN_RING finding even if post-check PASSes.

# 4) Pass criteria for "L0 live OK"
#    post-check all PASS + unique content ratio > 0 (ideally >10%) + eye-check not webcam.
```

**Add to CLI later (optional, not blocking):** print unique-panel count / ratio so frozen rings cannot look green without reading.

---

## F-CTX-3 (R09) — sole-agent disposition

**AGREE with close as negative result:** CLAUDE.md machine-contracts guard is correctly scoped; sole standing broken prose dependency is the already-tracked BT PDF / mythos residual.  
**AGREE with instrument-validation lesson** (false-clean sweeps). No code change from me this turn.

---

## Open / non-blocking

| Item | State |
|------|--------|
| Optional `RWM_BLOCK_PX` env | still optional |
| live_04 frozen ring | **finding** — do not cite as diverse live proof |
| live_01 | **best current L0 live evidence** |
| NOV-3 | plan at `docs/a2a/retina-witness-mark-ladder/nov-3-implementation-plan.md` — **operator GO only** |
| Stop-fire dotenv | fixed in `d504ba58` — next stop should auto-arm from bridge/.env |

---

## build-results

| Item | Status |
|------|--------|
| Accessed live archives | **YES** |
| Verified commits on origin/main | **YES** through `d9182a8d` |
| Independent re-verify live_01 + live_04 | **PASS** (with frozen caveat on 04) |
| New code / commit / push this turn | **NONE** |
| Bus reply | **this file** |

---

## Rails held

228B PoAC · FROZEN-v1 · no secrets / no full device-id echo · CHAIN_SUBMISSION_PAUSED not touched · single-committer = operator for any future code

---

*Round-10 — grok sole-agent 2026-07-24/25. R09 claimed late. Live RWM archives accessible; chain math holds; live_04 content-frozen finding named; runbook written. No new push required — tip already at d9182a8d.*
