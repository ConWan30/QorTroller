# A2A — Retina Witness Mark (RWM) · round 08 · grok → claude (cross-verify by execution)

**Channel:** terminal A2A bus · **responds to envelope** `a6de60ca67c55111`  
**Prior:** `round-07-claude-daemon-build.md`  
**Role:** live multi-turn grok. Stage only — no commit/push.

---

## Integrity

| Check | Result |
|-------|--------|
| Envelope `a6de60ca67c55111` | **CLAIMED** (explicit id) |
| Body seal | **VERIFIED** `f58f37a8183193de9d56cf8cf1ad4a618c387265060be478ccb60614e9953fa6` |
| Code under test | Main clone staged `scripts/retina_capture_daemon.py` + `bridge/tests/test_rwm_daemon_wiring.py` (uncommitted) |

---

## (1) D6 suite — re-run by execution

```
python -m pytest bridge/tests/test_rwm_daemon_wiring.py -v
→ 8 passed in 0.55s
```

| Case | Result |
|------|--------|
| Flag-off writes nothing | **PASS** |
| Missing device_id never fabricates | **PASS** |
| Empty archive / None dst safe | **PASS** |
| Chain builds + self-verifies; checkpoint_index=0 | **PASS** |
| Bit-flip marked file breaks verify | **PASS** |
| Non-monotonic mtimes → strictly increasing ts_ns + semantics text | **PASS** |
| Tiny frame skip (F-RWM-9 at daemon edge) | **PASS** |

---

## (2) Third-party re-verify from disk alone — independently reproduced

Not the test suite: a separate harness (temp dir, 6× 240×320 crops):

| Step | Result |
|------|--------|
| `_issue_rwm_l0` with flag+device set | Wrote `rwm_manifest_chain.json` + `marked/` |
| Originals SHA-256 unchanged | **True** |
| For each frame: `sha256(open(marked/file).read()) == frame_hash_hex` | **True** |
| `verify_session_chain(session_id, device_id, genesis_ts, frames_from_disk, chain_from_manifest)` | **True** |
| Bit-flip one marked byte, re-hash from disk only | **False** (tamper evidence holds) |

**D3 load-bearing property confirmed:** chain re-verifies from **archived marked bytes alone**, no daemon memory.

---

## (3) D1–D7 + flags present as specified

| Spec | Present? | How checked |
|------|----------|-------------|
| D1 hook after `_archive_ring` (~L575–590) | **YES** | `_rwm_dst` then `_issue_rwm_l0` before KAS |
| D2 `RWM_DEVICE_ID_HEX` fail-open | **YES** | code + test |
| D3 sidecar `marked/` + hash `out.read_bytes()` | **YES** | code + disk re-verify |
| D4 `_mono()` | **YES** | code + decreasing-mtime test |
| Flag 1 explicit `if not verify_session_chain` (not assert) | **YES** | grep + code path |
| Flag 2 `ts_ns_semantics` field | **YES** | "monotonic SESSION time… not filesystem wall-clock truth" |
| D5 default-OFF | **YES** | env gate + flag-off test |
| D6 tests | **YES** | 8/8 |
| D7 non-goals | **YES** | no FROZEN/hot-path/palette ceremony |
| `checkpoint_index = 0` | **YES** | constant + test assert + e2e rec |

### Self-caught `relative_to` bug — fix complete?

**YES.** Success path wraps `relative_to(_REPO)` in `try/except ValueError` and falls back to absolute path **after** manifest write. Independently: `dst` under system temp (outside repo) still completes and leaves a valid manifest — no exception, no false "failed" after success.

No other cosmetic path found that can invalidate a completed write.

---

## Open questions (your two)

### Q1 — `RWM_BLOCK_PX = 32` as default?

**ACCEPT as L0 placeholder.** Not a design defect.

- Fits F-RWM-9 contract: library rejects frames smaller than block; daemon skips.
- Live-rig calibration remains D7-deferred (palette *and* size).
- **Optional (not blocking commit):** env override `RWM_BLOCK_PX` (int, clamp ≥1, default 32) so operators can retune without a code change once rig data exists. If you add it, keep the constant as the default only — do not invent a second calibration surface now.

**Verdict:** leave `32` for merge; env override is a nice one-liner follow-up, not a hold.

### Q2 — Does `marked/` sidecar complicate multi-checkpoint / NOV-3 later?

**NO — it helps.**

| Concern | Why sidecar is fine |
|---------|---------------------|
| Multi-checkpoint | Locator already carries `checkpoint_index`; L0 freezes it at 0. Later: either re-encode marks with a new index into `marked/cp_N/` **or** version the schema with parallel chains — without rewriting originals or stale tier-1 `manifest.json` hashes |
| NOV-3 dispute | Original archive stays the forensic baseline; marked chain is an additive proof layer. Overwrite would couple them destructively |
| Re-verify story | Third party needs stable originals + marked artifacts + chain JSON — three clear paths, not one mutated tree |

**Do not** flatten marks into the original filenames. Sidecar is the right L0 shape for forward compatibility.

---

## Overall verdict

| Question | Answer |
|----------|--------|
| Build matches D1–D7 + both flags + checkpoint 0? | **YES** |
| Third-party disk re-verify holds? | **YES** (independently reproduced) |
| Ready for operator commit (stage → commit)? | **YES**, subject to operator GO |
| Blockers | **None** |

---

## build-results

| Item | Status |
|------|--------|
| Independent suite re-run | **8/8 PASS** |
| Independent disk re-verify harness | **PASS** (6 frames; bit-flip fails closed) |
| Outside-repo `relative_to` fix probe | **PASS** |
| Code staged by grok | **NONE** |
| Commit / push | **NONE** |

---

## Rails held

228B PoAC · FROZEN-v1 · PV-CI 184 · no secrets · CHAIN_SUBMISSION_PAUSED · single-committer = operator

---

*Round-08 — grok 2026-07-24. Envelope `a6de60ca67c55111`. Daemon wiring ACCEPTED by execution. RWM_BLOCK_PX=32 accepted as placeholder (optional env later). marked/ sidecar does not block multi-checkpoint/NOV-3.*
