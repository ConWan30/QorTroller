# Retina cross-oracle calibration audit (2026-06-20)

Dry-run FSCA classifier vs L4 Mahalanobis on replay windows.
Real `hw_*.json` replay: 3 session(s), 3000 frames/session (capped from up to 180002 available). Advisory dry-run — not a substitute for live tournament adjudication.

## Aggregate

| Metric | Value |
|--------|-------|
| Data provenance | real hw_*.json |
| Sessions | 3 |
| Windows | 147 |
| RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY | 0 |
| L4_ANOMALY_WITHOUT_RETINA_SIGNAL | 0 |
| Agreement rate | 1.0 |

## Caveats

- Agreement rate reflects mutual quiescence: both oracles stayed quiet on this data,
  which is the expected/clean outcome for genuine human captures (no adversarial input).
  It is NOT validation against spoofed/aimbot trajectories — use `--synthetic --aimbot-snap-at`
  or `--macro-flat` for adversarial cross-oracle checks.
- L4 mahalanobis is ~0 across all windows. Two contributing effects: (1) calibration
  captures here are still-hold/neutral-stick probes, so L5/trajectory signal is naturally
  near zero; (2) the replay L4 proxy updates the fingerprint with the same window it then
  measures (self-referential), so distance trends to ~0 on smooth sequential windows.
  Treat the L4 arm as a structural sanity check, not a live Mahalanobis verdict.

## Per session

### hw_005
- windows=49 rule1=0 rule2=0 agreement=1.0

### hw_006
- windows=49 rule1=0 rule2=0 agreement=1.0

### hw_007
- windows=49 rule1=0 rule2=0 agreement=1.0
