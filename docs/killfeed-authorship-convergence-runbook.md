# Kill-feed Authorship Convergence Runbook (next session)

The capture that brings **everything together** — coupling (B1 flash / B2 kill-marker / geometric / cross-
channel latency) **and** kill-feed authorship — in one session, so the live `status()` reports them side by
side. Tonight's finding (cycle 56): correlation channels can't separate genuine play from active-spectate-spam;
**authorship can** (a kill-feed row crediting your handle, `QorTrola30`, bound to your R2 onset). Advisory /
default-off; no FROZEN-v1 / 228B PoAC / chain / IOTX.

## Prerequisite — install Tesseract (one-time)
`pytesseract` is already installed; only the **engine binary** is missing. Install the UB-Mannheim build:
- Download/run **`tesseract-ocr-w64-setup-*.exe`** (https://github.com/UB-Mannheim/tesseract/wiki), default
  path `C:\Program Files\Tesseract-OCR\`. `hud_ocr.py` auto-locates it there (no PATH edit needed).
- Verify: `python -c "from l9_presence import hud_ocr; print(hud_ocr.ocr_available())"` → should print `True`.
  If `False`, the authorship channel simply abstains (UNVERIFIABLE) and coupling still runs — fail-open.

## The handle
Default `QORTROLLER_HANDLE=QorTrola30` (already baked in). Set the env var only if your in-game name differs.

## Run the convergence capture (one command)
```powershell
cd C:\Users\Contr\vapi-pebble-prototype; python scripts/retina_capture_daemon.py start --label converge --monitor 1 --diag-every 4 --killfeed
```
Wait for `CAPTURE LIVE` (silent, no popups), then:
1. **PLAY and get kills/downs** — the kill-feed shows `QorTrola30 ☠ X`, bound to your R2 → **AUTHORED**.
2. Later, **die and spectate + spam R2** — the feed shows teammates' kills, never your name → **SPECTATED**.

Stop when done:
```powershell
python scripts/retina_capture_daemon.py stop --label converge
```

## What converges in `status()` (the bridge logs it as `RGC diag:`)
- Coupling (the correlation family): `coupling_score`, `th_coupling` (B1), `th2_coupling` (B2), `*_lag_ms`,
  `ts_source` — these fire on BOTH genuine and active-spectate (that's the limitation).
- **Authorship (the differentiator):** `kf_verdict` ∈ {AUTHORED_PRESENT, SPECTATED_NOT_AUTHORED,
  OWN_KILL_UNBOUND, NO_KILL_EVENTS, UNVERIFIABLE} + `kf_own_kills` / `kf_other_kills` / `kf_bound_kills`.

## Acceptance criteria (what proves authorship works)
- During your kills: `kf_verdict=AUTHORED_PRESENT`, `kf_own_kills>0`, `kf_bound_kills>0`.
- During spectate-spam: `kf_verdict=SPECTATED_NOT_AUTHORED`, `kf_own_kills=0`, `kf_other_kills>0`.
- If `kf_verdict` stays `UNVERIFIABLE`/`NO_KILL_EVENTS` during real kills → the **ROI is off** (see below) or
  tesseract isn't resolving.

## Kill-feed ROI calibration (the one thing that needs tuning)
The ROI is fractional `fx,fy,fw,fh` of the captured frame; default `0.62,0.10,0.36,0.22` (top-right, where the
Warzone feed lives). If `kf_*` reads nothing during kills, adjust and pass `--killfeed-roi`:
```powershell
... start --label converge --monitor 1 --diag-every 4 --killfeed --killfeed-roi 0.60,0.08,0.38,0.26
```
Quick check that the ROI lands on the feed: while playing, watch the bridge log for the one-time
`kill-feed authorship ON (tesseract=True, roi=..., handle=q0rtr01a30)` line, then for `kf_own_kills` climbing
as you get eliminations. If it never climbs, widen/move the ROI toward where your kill-feed renders.

## The point
Coupling proves a **live human on a live screen** (presence). Authorship proves **it's the player's OWN game,
not a spectated one** — the gap tonight's data showed correlation cannot close. Fuse them: presence × authorship.
