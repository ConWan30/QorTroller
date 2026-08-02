---
name: capture-rig
description: Discipline for live capture sessions on the certified DualShock Edge — the dual-connection topology, the eye-check protocol before trusting any frame, PCC host-state semantics, and the L6B/PoEP enablement gates. Read before starting, driving, or interpreting a live rig session.
---

# Live capture rig

## Ask before you start

Never launch a live capture, replay, or rig smoke test unannounced. Say what is
about to run and confirm the operator is ready — a rig session takes their
hands and their console.

## The only valid topology

**Dual-connection: USB-C to the laptop AND Bluetooth to the PS5.** The game is
PS5-exclusive, so BT must stay paired; the USB link is what the bridge reads.

`CaptureHealthMonitor` infers host state **purely from USB poll-rate statistics**
— it is completely blind to BT pairing. Stable ~1000 Hz USB polling reports
`EXCLUSIVE_USB` regardless of the PS5 connection. Do not "fix" a healthy
dual-connection setup by unpairing.

- CV < 0.20 and rate ≥ 900 Hz → `EXCLUSIVE_USB`
- CV ≥ 0.40 → `CONTESTED` (session won't count; finish the play, wait for recovery)
- 200–350 Hz → `EXCLUSIVE_BT`

PS Remote Play during a grind is **not** recommended — its USB audio/HID traffic
perturbs poll rate into `CONTESTED`. Normal BT gameplay does not.

## Default dual-path start (this operator rig — 2026-08-02)

**Read first every session:** `docs/runbook/NEXT_SESSION_FIRST.md`

| Index | Device | Role |
|------:|--------|------|
| 0 | `720p HD Camera` | House webcam — **never** |
| 1 | capture card path | Bridge `--uvc-index 1` |
| 2 | `OBS Virtual Camera` | Streamer `--streamer-device 2` + `dshow` |

```powershell
.\scripts\start_ncaa27_dual_path.ps1
# same as:
# python scripts/retina_capture_daemon.py start --label ncaa27 `
#   --uvc-index 1 --streamer --streamer-device 2 --streamer-fps 15
python scripts/retina_capture_daemon.py stop
```

Daemon passes OBS streamer defaults (`dshow`, device-name, `obs_virtual`, eye-check snapshot).
Streamer is observation-only — never merge into `poep_enabled`.

## The eye check — do this before trusting any frame

**Content-verify the first ring crop before queueing anything downstream.**

This is not paranoia. A persisted `uvc_index=0` once pointed the capture at the
operator's webcam instead of the capture card, and *two full sessions* recorded
the room before anyone noticed. Frames were purged from both copies. A session
that looks healthy by every metric can still be watching the wrong thing.
On this rig, index **0 is still the house webcam** — always prefer the locked map above.

Related: crops must come from the **full-resolution** buffer, not the governor's
downscaled optical-flow buffer. Reading OCR off a 5x-downscaled panel shrinks a
~600px region to ~76px and returns nothing — the same bug appeared twice, in the
panel path and again in the killfeed path.

## Enablement gates — earned, not flipped

- **`L6B_ENABLED=false`** until N≥50 usable reflex captures *on the certified
  device*. The honest gate is `l9_presence.poep_reflex_gate.is_usable_reflex`
  (allowlisted policy AND IMU-corroborated AND in-band AND not-artifact) — raw
  counts overstate. As of 2026-07-18 the registered Edge has usable N=220, so
  the gate is **met**; the flag still does not flip on its own. Enabling is an
  operator decision and seal.
- **`poep_enabled=false`.** PoEP presence is a live-protocol property, not an
  offline model — an offline reflex model scored AUC 0.971 and still failed the
  adversarial gate at FAR 0.76.
- **`GSR_ENABLED=false`** — N=0 GSR sessions.
- Campaign mode (`POEP_CAMPAIGN_MODE`, process-scoped, never persisted) may run
  the nonce-bound fire path for corpus growth while `L6B_ENABLED` stays false.
  It does **not** enable the auto-tick or the humanity-formula contribution.

## Reading verdicts honestly

Render verdicts as-is: `UNVERIFIABLE` / `PARTIAL_SURFACES` / `SYNCHRONIZED`,
honest-null when a surface is absent. Packaging never rounds a verdict up.
`AUTHORED` stays 0 under dual-connection HID by the KAS hygiene gate — that is
a topology fact, not a scoring failure to be worked around.

## Related

- `docs/runbook/NEXT_SESSION_FIRST.md` — **first doc every live session**
- `docs/runbook/streamer-retina-perception-v0.md` — streamer perception ops
- `scripts/start_ncaa27_dual_path.ps1` — one-command dual-path start
- `biometric-calibration` skill — what the layers measure
- `docs/a2a/poep/` — the PoEP round history
- `bridge/vapi_bridge/capture_continuity.py` — PCC state machine
