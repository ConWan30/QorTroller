# L0 live verification — `cfb_rwm_live_01` (2026-07-24)

**Verdict: PASS — L0 live-verify gate MET. NOV-3 scope authorized to open.**

## Capture

| Field | Value |
|-------|--------|
| Label | `cfb_rwm_live_01` |
| Archive | `retina_kf_archive/cfb_rwm_live_01_1784932933` (gitignored) |
| Crops archived | 1076 |
| Capture path | OBS virtual camera → daemon (encode/scale in path — stronger than raw card) |
| Device id (claimed) | certified Edge `581a836c…` via `RWM_DEVICE_ID_HEX` in `bridge/.env` |
| Eye-check | Game feed idx re-verified after OBS took exclusive index; webcam idx skipped (room not captured) |

## RWM fire path (honest)

1. **At `stop`:** RWM **silent no-op** — `RWM_L0_DAEMON_ENABLED` / `RWM_DEVICE_ID_HEX` lived in `bridge/.env` but `_issue_rwm_l0` only read process env. Stop is a new process. No `[daemon] RWM:` log line.
2. **Offline recovery:** same `_issue_rwm_l0` against the archived crops with env set → **1076 frames marked + chained** in ~93s.
3. **Post-session check:** EXIT 0, all load-bearing checks PASS.

This is a **valid live L0 proof on real footage**. It is **not** “stop auto-fired RWM on first try.” The dotenv-fallback fix (same commit that opens this ladder) closes that ops gap for the next session.

## Post-check results (load-bearing)

```
[PASS] RWM ran — 1076 frames, schema qortroller-rwm-session-chain-v0 candidate=True
[PASS] third-party re-verify from disk bytes alone
[PASS] originals byte-identical (marked/ sidecar; tier-1 manifest hashes intact)
[PASS] locator decoded correctly on real frames (1076/1076)
[INFO] geometry 614×724; block_px=32 ≈ 5.2% of short edge (plausible; D7 calibration still deferred)
```

## Caveats (do not paper over)

1. **Ring mix:** rolling buffer was full before this session; archive can include older crop timestamps as well as this session’s. Chain integrity still holds; “single pure session” is not claimed.
2. **Many late crops identical size (592402 B):** consistent with static/menu or OBS holding a frame; locator still decoded.
3. **Offline re-fire vs stop-fire:** same code path and same archive; ops wiring was the only gap.
4. **CANDIDATE only:** `qortroller-rwm-session-chain-v0` is not FROZEN-v1; no PV-CI pin; no tournament hard-code.

## Gate rule applied

From `docs/a2a/retina-witness-mark/scope.md`:

> Path A as L0 of the NOV ladder → NOV-3 → NOV-2 → NOV-1, each layer opened only after the prior layer’s live verification passes.

L0 live verification **passed**. This document is the permanent gate record for opening `nov-3-scope.md`.
