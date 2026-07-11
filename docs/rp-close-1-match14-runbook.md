# Match 14 Runbook — RP-2, Option B (same-machine Remote Play)

**D-RP-1: B-then-A (2026-07-07).** This is the Option-B leg: one full match played over
Remote Play on today's hardware, full authorship stack live. Success converts the
"novel anti-cheat when playing Remote Play" claim from extrapolated to demonstrated and
publishes the honest RP recall floor. Match 15 (Option A, sidecar capture device) reruns
this after hardware acquisition — the B/A delta is publishable evidence.

Operator-run only — never launched unannounced.

## Success tiers (all honest results — publish whichever lands)

1. **Full:** KAS `AUTHORED_SESSION` + PoSP `SYNCHRONIZED` + RP recall floor published.
2. **Partial:** dense classify + promotion chain ran but `INSUFFICIENT_KILLS` /
   low authored — publish the density numbers; they price Option A's hardware.
3. **Diagnostic:** stack degraded under RP → the KAS record's own fields localize the
   stage (windows_total → inline_classifications → promotion events → authored), same
   discipline as the C-3.2 fix chain. A named fault is a result.

## Pre-match (PowerShell, from repo root)

```powershell
# 1. Kill stale heavy processes (M11 lesson) — the preflight will verify
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Select ProcessId,CommandLine

# 2. VPN OFF — McAfee/WireGuard throttled RP 16->29fps (2026-06-27 measured)

# 3. Preflight gate — must print GO or GO_WITH_WARNINGS (investigate any WARN)
$env:RETINA_KILLFEED_CAPTURE_MAX = "1800"
python scripts/match_preflight.py --capture-dir retina_kf_crops_match14
```

## Launch (ONE terminal — the daemon spawns its own lean bridge; see NOTE below)

```powershell
# CRITICAL: the daemon's spawned bridge AND its stop-time PoSP issuance both read
# DB_PATH from THIS shell's env (falls back to bridge/.env, then the default 5.3GB DB).
# Wrong DB at stop -> zero fusion rows -> PARTIAL, never SYNCHRONIZED.
$env:DB_PATH = "$HOME\.vapi\bridge_match14.db"
$env:PRESENCE_LEAN_MODE = "true"
$env:NQPV_COCAPTURE_ENABLED = "true"
$env:RETINA_KILLFEED_CAPTURE_MAX = "1800"
python scripts/retina_capture_daemon.py start --session-anchor --killfeed-inline `
    --dense-classify --classify-burst --hid-events `
    --capture --capture-dir retina_kf_crops_match14 `
    --label "match14_rp_option_b" --diag-every 4
```

NOTE (learned live, Match 14): `--kas` is a STOP flag, not a start flag — KAS issues at
close. ALSO: the daemon SPAWNS its own bridge (detached, port 8080) — do NOT start a
separate bridge first; two bridges = port bind failure + shared-HID contention (the
exact M12 failure mode). The daemon-only launch IS the whole stack; set the lean/NQPV
env in the daemon's shell so the spawned bridge inherits it.

Play one full match. Do not run anything else heavy on the laptop during it.

## Stop (CRITICAL: same capture dir, or the archive copies the wrong ring;
## run from the SAME launch terminal so DB_PATH is still set; --kas lives HERE)

```powershell
$env:RETINA_KILLFEED_CAPTURE_DIR = "retina_kf_crops_match14"
python scripts/retina_capture_daemon.py stop --kas --label "match14_rp_option_b"
```

Stop issues the KAS record, the PoSP record (`audits/posp_record_match14_*.json`),
and the session archive (`retina_kf_archive/match14_rp_option_b_*/`).

## Post-match audit chain (offline, order matters)

```powershell
# A. Verify the PoSP record (Arc A verifier; exit 0 = VERIFIED)
python scripts/verify_posp_record.py audits/posp_record_match14_rp_option_b_*.json

# B. RP recall floor: dense-archive ground truth vs live KAS authored count
#    (same methodology as C-3.3 / the RP-3 precision scan)
python scripts/rp_ocr_precision_scan.py `
    --archive retina_kf_archive/match14_rp_option_b_* `
    --out audits/rp_ocr_precision_scan_match14.json
```

Then: compare cluster count (ground-truth kills in archive) vs KAS `authored_kills` →
that ratio IS the published RP recall floor (M13 HDMI baseline: 8/27 = 29.6% at K=3).
Update `audits/rp-close-1-ledger-2026-07-07.md` (RP-2 state + findings) and note the
zero-false-read bar result on the RP-dense archive (extends RP-3's precision evidence
past its sampling-starved caveat).

## Known risks going in (measured, not guessed)

- Archive density will trail M13's 524 (M12 under RP managed 35) — that's the point of
  measuring; lean mode + fresh DB + VPN-off are the mitigations that were absent in M12.
- K=3 promotion may rarely complete inside kill windows at RP fps — tier-2 outcome.
- WGC capture contends with RP's GPU decoder regardless (process isolation refuted);
  Option A exists precisely because this ceiling is architectural.
