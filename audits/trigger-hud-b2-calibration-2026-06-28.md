# Trigger→HUD Channel B2 — live calibration pass (2026-06-28)

**Regime:** PS Remote Play / Warzone, dev-cert, single subject. DualShock Edge USB→laptop, combat-triggered
15s bursts (auto-fire on R2 rising edge ≥40, 18s cooldown). B2 = `center_roi_redness` (RED kill/down marker)
vs R2 trigger, causal-lag Pearson + time-shuffled null. Source: bridge `trigger-hud burst:` log lines.
0 capture failures across the firing portion of the session.

## Corpus
- **Gunfight positives (N=40):** 0.302 0.097 0.238 0.231 0.098 0.09 0.144 0.139 0.145 0.168 0.238 0.045
  0.116 0.077 0.155 0.082 0.021 0.473 0.332 0.224 0.148 0.111 0.145 0.15 0.155 0.516 0.334 0.114 0.282
  0.215 0.054 0.072 0.09 0.034 0.407 0.317 0.208 0.163 0.111 0.082
- **Spectate-fire negatives (N=8, two blocks):** block 1 — 0.24 0.072 0.216 0.092 0.142 ; block 2 —
  0.261 0.029 0.233  (R2 pulled while spectating a teammate's POV — your trigger cannot *cause* their
  on-screen hits).
- Time-shuffled nulls throughout: ~0.002–0.033 → the coupling is real causal structure, not chance.

## Distributions
| set | n | min | median | p90 | max |
|---|---|---|---|---|---|
| gunfight + | 40 | 0.021 | 0.146 | 0.332 | 0.516 |
| spectate − | 8 | 0.029 | 0.167 | 0.247 | 0.261 |

## `calibrate()` verdict: **INSUFFICIENT_DATA** (n_null = 8 < N_FLOOR = 10; ≥30 for production)
No FAR-safe threshold can be certified yet — but the directional finding is clear and important.

## Two findings

### 1. B2 is a KILL/DOWN detector, not a "you fired" detector
The red marker B2 keys on appears on a down/kill, not every bullet. The gunfight bursts split bimodally: a
**kill cluster (8 bursts, 0.282–0.516)** and a no-kill body (0.02–0.24). Reframed as *"your trigger caused a
real down,"* B2 is a far stronger, game-state-bound claim than "you pulled the trigger."

### 2. The negatives are BIMODAL — *active*-spectate runs hot (the load-bearing result)
- **Calm spectate** (teammate looting/rotating): 0.029 0.072 0.092 0.142 → clean, well below any threshold.
- **Active-combat spectate** (teammate in a fight, red markers on their screen): 0.216 0.233 0.24 **0.261**
  → nearly touches the kill-positive floor. **Margin kill-min 0.282 vs active-neg-max 0.261 = ~0.021.**
- Mechanism: firing while watching action, your ~20s-spaced R2 pulls catch the spectated screen's
  flashes/red-markers by chance — or you subconsciously fire in rhythm with the on-screen combat. That is
  correlational, NOT causal (your trigger doesn't cause their screen), but B2 alone can't tell them apart.

## Honest conclusion
- The current `L9_TH_COUPLING_THRESHOLD = 0.20` is **too low** for this regime — active-spectate negatives
  (0.22–0.26) sit above it. A ~0.27 threshold clears all 8 negatives (FAR=0) and isolates the kill cluster,
  but the **~0.02 margin is too thin to be robust** — noise/variance would produce false accepts.
- **B2 cannot stand alone** as the proof over Remote Play: an adversary replaying/spectating *active* footage
  and firing along can approach kill-coupling. This is precisely the case the multi-channel gate is designed
  for — fuse B2 with the geometric channel + recoil-compensation (C1) under a shared session render-latency
  constraint, so a forged channel breaks the cross-channel lag invariant even if it fakes one channel's score
  (see `vsd-vault/.../s-multi-channel-presence-gate`, `s-recoil-compensation-coupling`).

## Next pass (to certify / advance)
- **Resolve the session-4 no-fire first:** after the Remote Play reconnect, combat bursts stopped firing with
  the controller still streaming HID frames — the **R2 probe** (`dualshock_integration.py`, logs each R2 pull
  value) is loaded to distinguish "trigger below threshold" from "live input blind on USB"
  (the dual-connection-blind pattern). A few deliberate R2 pulls will read it out.
- **Finish the negative corpus to N≥10 (toward ≥30):** more *calm*-spectate (the clean floor) so the FAR
  estimate is honest; the *active*-spectate hard negatives are already represented.
- **Then:** if a ~0.27 threshold survives the larger negative set with a real margin, bump the default and
  document B2 as a trigger→down proof; otherwise B2 stays advisory and the verdict goes into the fusion gate,
  not standalone.

No FROZEN-v1 / 228B PoAC / chain / IOTX touched. Advisory presence-oracle calibration only.
