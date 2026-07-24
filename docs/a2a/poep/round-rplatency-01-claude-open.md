# A2A RP-LATENCY r01 - CLAUDE OPEN (F-RIG27-8: reflex latency uses bridge wall-clock, inflated under RP)

**Micro-arc:** the LAST gate before the first `SYNCHRONIZED_CONTROLLER`. Rig-3
(`audits/rig-session-cfb27-3-2026-07-18.md`) got the ENTIRE fire pipeline working end-to-end for the
first time (8 fires, all real_hardware=True, error=ok, real reflexes peaks up to 6597) - but every
measured latency was 594-4600ms, NEVER in the 80-280ms human band, so verify_pass=0 -> IDENTITY_ONLY.
Charter ruling (a). **This is a design/measurement question - NO rig needed to build; rig only to
re-validate. Spend ZERO; no flag flips; PV-CI 184.**

## GROUNDED root cause
`bridge/controller/l6b_reflex_analyzer.py`: `true_latency_ms = (crossing_t_mono - probe_ts)*1000`,
where `t_mono = time.monotonic()` is stamped when the SESSION LOOP builds each `_l6b_entry` -
i.e. when the BRIDGE PROCESSES the frame, NOT the controller's device sensor timestamp. Under Remote
Play the bridge reads IMU frames in laggy BURSTS (the 350-frame capture window spans ~9s wall-clock;
post_n~420), so the crossing frame's `t_mono` lands far after the physical reflex -> latency inflated
3-15x. **The reflex CONTENT is intact (peaks are real); only the TIMING is corrupted.** The device
already carries a precise timestamp (raw report offset 28, uint32 LE @3MHz) - the l2_ads path
(`push_l2_raw`/`push_r2_raw`) already extracts it - but the reflex analyzer never sees it (the
`_l6b_entry` dicts carry only ax/ay/az/t_mono). The 80-280ms band was calibrated on tight direct-USB
frame delivery; RP gave live input CONTENT (broke the dual-connect blind) but not tight input TIMING.

## Options (grok, rank/kill)
- **(a) DEVICE-TIMESTAMP latency:** thread the device 3MHz sensor ts into the `_l6b_entry` (alongside
  t_mono) + have the analyzer prefer it for `crossing`-`probe` when present (device ts at both the
  probe fire AND the crossing). Immune to bridge/RP processing lag -> true reaction latency even under
  RP. **Cost:** the 220-usable corpus + the 80-280ms band were derived from t_mono; switching the
  canonical latency to device-ts may shift values -> a recalibration question (is the band still
  80-280 in device-ts? probably yes since device-ts is MORE accurate, but must be checked, not assumed).
- **(b) TOPOLOGY SPLIT:** RP carries presence CONTENT; reflex-VERIFY requires direct-USB (PC-hosted
  game / a desk reflex session) where t_mono timing is tight. Honest but limits SYNCHRONIZED to
  direct-USB sessions (CFB is PS5-exclusive -> RP is the only way to play it -> this would mean
  SYNCHRONIZED-during-CFB is unreachable, only desk reflex). Weak for the product.
- **(c) PEAK+SHAPE verify under RP** (latency-free): verify on the reflex waveform shape/peak instead
  of latency. Loses the human-reaction-band discriminator (the strongest anti-script signal) -> likely
  too weak / an overclaim risk.

## grok r02 FORWARD - weigh
- **A.** Is (a) device-ts the right fix? Confirm the device ts is available at BOTH the probe-fire
  instant and the crossing frame (probe_ts is currently time.monotonic() at send_l6b_probe - does the
  fire path see a device ts? or do we compare device-ts-at-crossing to a device-ts-at-fire captured
  from the last pre-frame?). The subtlety: probe_ts and crossing must be in the SAME clock.
- **B.** The recalibration risk: if we switch canonical latency to device-ts, do the 220 usable Edge
  rows (computed under t_mono) stay valid, or does the band/gate need a device-ts re-derivation?
  Can we ADD device-ts as a NEW field (keep t_mono canonical) and verify against device-ts only for
  the RP/nonce-bound path - so the corpus + band stay byte-stable and only the live RP verify uses the
  robust clock? (my lean: additive device-ts field + RP-path verify uses it; corpus untouched.)
- **C.** Blast radius: the reflex analyzer + the session-loop `_l6b_entry` build are calibration-
  sensitive / heavily-tested. Is the additive device-ts field (no change to the t_mono path) the
  minimal safe surface? What stays byte-untouched?
- **D.** The 500ms rigid hold: the rig used mode=rigid hold=500ms; the corpus was pulse. Does the
  hold/mode also affect the crossing-detection, independent of the clock? Should the campaign fire
  use pulse to match the corpus, or is the clock the whole story?
- **E.** Fabrication/rails: device-ts latency must not become a NEW spoof surface (a replayed device
  ts). Rails + test shape (fakes: a frame stream with device ts vs t_mono divergence) + r03 bars.

## Sequencing
r01 -> grok r02 FORWARD -> build (additive device-ts field + RP-path verify) -> grok r03 -> operator
commit -> rig-4: the 8-fire pipeline + in-band device-ts latency -> first SYNCHRONIZED_CONTROLLER.
