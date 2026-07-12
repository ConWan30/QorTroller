# Retina Card-Arrival Runbook (TRL-1 R1) - 2026-07-11

The AMANKA UVC capture card is the seed of the trio-retina witness node. This is the
"plug it in and be productive in an hour" procedure so retina/LUMEN work starts the
day the card lands, not a day later.

## The one smoke command

```bash
python scripts/retina_card_smoke.py
```

**GO** means the retina daemon's exact UVC open path (`UvcFrameSource`: CAP_DSHOW -> fallback,
MJPG FOURCC, request 1920x1080@60, prove-a-frame) works on this card at your index. The smoke uses the
same env vars as the daemon, so a GO here is a GO for the daemon.

## Arrival procedure

1. **Physical.** PS5 HDMI-out -> card HDMI-IN; card HDMI-OUT -> TV (loop-through, so you still see the
   game live); card USB -> **a USB3 port** on the laptop (USB2 throttles 1080p60). If the card has an
   HDCP note, it must strip/pass HDCP or capture yields a black frame (the usual "opened but no frame").
2. **Run the smoke.** `python scripts/retina_card_smoke.py`
   - **GO** at your index -> proceed to step 3.
   - **NO-GO "set RETINA_UVC_INDEX=N"** -> the card is not at index 0 (a laptop webcam usually is).
     `export RETINA_UVC_INDEX=N` (or set it in the environment) and re-run.
   - **NO-DEVICE** -> check the USB + HDMI cables, the card's drivers, and HDCP passthrough.
   - **GO but "below ideal 1920x1080@60"** (e.g. 1280x720@30) -> it works, but for full 1080p60 confirm
     the **MJPG** FOURCC (YUY2 caps ~5fps) and a **USB3** port.
3. **Set the daemon env to match the GO.**
   ```
   RETINA_CAPTURE_SOURCE=uvc
   RETINA_UVC_INDEX=<n>          # from the GO
   # WIDTH/HEIGHT/FPS/FOURCC default to 1920/1080/60/MJPG
   ```
4. **Verify the OCR crops (TRL-1 R2 - refined finding).** The kill-feed / panel crops are **FRACTIONAL**
   ROIs (`RETINA_KILLFEED_ROI` / `RETINA_CAPTURE_PANEL_ROI`, e.g. `0.62,0.10,0.36,0.22`) converted to
   pixels at runtime - so they are **resolution-independent**: the WGC -> card move does **not** shift
   them by resolution (an earlier draft of this step overstated it, and pointed at the wrong file -
   `calibration_profile*.json` holds biometric thresholds, not crops). The residual risk is
   **content-framing** (aspect / letterbox / HUD offset). Verify in one glance:
   ```bash
   python scripts/retina_crop_recalibrate.py --report          # where the crops land at 1080p
   python scripts/retina_crop_recalibrate.py --overlay <card_frame.png> --out check.png
   ```
   and confirm the green (kill-feed) + cyan (panel) boxes land on the HUD. If off, correct with
   `--src-content/--dst-content` or by editing the fractions. **Authorship stays UNCALIBRATED on the
   card feed until the zero-false-read gate re-passes on it** (TRL-1 rail 7).
5. **First card match.** `RETINA_CAPTURE_SOURCE=uvc`, advisory rails unchanged (default-OFF; observation
   never asserts; R2 B2 stands). Confirm fps holds under load - direct HDMI should hold 60 (that is the
   WGC-collapse fix that motivated the card).

## What GO does and does NOT mean

- **GO** = the card opens + delivers frames at the daemon's exact open path and meets the usable bar.
- **GO does NOT mean** the OCR crops are aligned (that is R2) or that any advisory is calibrated (a
  population study is still pending). *Observation may suggest; only assertion may claim.*

## Two roadmaps, one purchase (why this card matters twice)

The RP recall ceiling **now**, and the **seed of a new DePIN device category: the gaming witness node**
- its own ioID identity, off the gamer's hot path, the physical answer to `verifier_independence=False`.
The controller is the trusted thing that *acts*; the witness node is the trusted thing that *sees*. See
TRL-1 R3 (witness-node design + ioID readiness).

---

*TRL-1 R1 - card-arrival readiness. Loop: `docs/trio-readiness-loop-trl1-2026-07-11.md`.*
