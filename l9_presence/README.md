# QorTroller L9 — Input-Output Causal Presence

**Status (2026-05-21): Stream A (causal presence / anti-cheat) VALIDATED and banked.
Stream B (render-loop biometric → tournament separation) PARKED at ~72% three-way —
a fusion ingredient, not a standalone gate.** Touches **no FROZEN-v1 primitive, no
228-byte PoAC wire format, no chain, no contract, no grind/PCC mode.**

## The idea
The next PITL layer after L8 (BT presence). Where **L2C** correlates right-stick
velocity against `gyro_z` (controller twist), **L9** correlates the human's aim-stick
input against the **rendered on-screen camera motion** (optical flow), and adds a
**residual decomposition** that localizes motion the stick can't explain. It sits on
the cloud-client attestation gap that streamed clients (Remote Play / GeForce NOW)
leave open. Everything is **local + deterministic** (no cloud model) so it can become
part of a cryptographic determination.

## Two streams, two verdicts (honest)

### Stream A — causal presence / anti-cheat ✅ VALIDATED
Proves a human's input **causally produced** the rendered camera motion, at a human
reaction lag, with the link collapsing under a time-shuffle negative control.
- De-risk **GO**: Remote Play captures non-black via `mss`, HID reads concurrently (~31 fps @ 640×360).
- Human coupling **0.29–0.45**, negative control collapses to **~0.02**, causal lag **25–83 ms**.
- Synthetic adversary: **full camera takeover is caught** (coupling → ~0.05 across static/snap/track).
  Honest limit: a **partial/low-energy assist evades both coupling and global residual** (it hides
  under the human's already-high residual baseline) — `engagement_locked_residual` isolates the
  fire-moment residual for that case.
- Emits a **Proof of Causal Presence (PoCP)** commitment + a gamer-facing **HTML verification card**.

### Stream B — render-loop biometric → separation ⏸ PARKED
A render-derived play-style fingerprint (coupling, yaw/pitch ratio, decoupled energy).
- Gate-1 (within-player stability): **passed** (CV 0.06–0.19 on 3 features; lag noisy at 31 fps).
- Gate-2 (between-player): 2-way LOO **90.9%**; **3-way LOO 72.2%** (P1/P2/P3, 18 reliable sessions),
  separation ratio 1.90, permutation **p=0.0005** (significant). **Below the 80% tournament bar alone.**
- Still beats existing controller biometrics (touchpad 63.6%, AIT 66.7%) and is **orthogonal** to them
  → its real value is **fusion** with controller biometrics, deferred to a separate phase.

## Modules
| file | role |
|---|---|
| `coupling.py` | coupling + residual + negative-control math (the core) — numpy, tested |
| `cv_motion.py` | optical-flow → camera angular velocity (opencv) |
| `screen_capture.py` | capture backends (bettercam→dxcam→mss) + black-frame guard |
| `hid_probe.py` | on-device right-stick byte-offset validator |
| `session_recorder.py` | record / analyze / compare / decouple-control / engagement / **capture** (per-player) |
| `biometric_features.py` | render-loop feature vector; within-player stability; between-player separation + LOO + permutation |
| `synth_adversary.py` | synthetic aimbot generator (dev/threshold tool; tests detector vs a model of a cheat) |
| `pocp.py` | Proof of Causal Presence commitment (**v0 candidate**, FROZEN-safe, not anchored) |
| `verification_card.py` | gamer-facing HTML verification card |
| `witness_agent.py` | **Gameplay Witness Agent** — autonomous capture-time orchestrator |
| `derisk_check.py` | the decisive 10-min capture+HID check (run FIRST) |

## Install (operator rig)
```
pip install bettercam mss opencv-python hidapi numpy
```
(`bettercam`/`mss` for capture; on Python 3.13 the DXGI backends crash in `comtypes` —
`mss` is the crash-free path and captures Remote Play's overlay non-black.)

## Run order
```
python -m l9_presence.derisk_check --backend mss            # 1. GO/NO-GO (Remote Play in-game)
python -m l9_presence.hid_probe                              # 2. confirm right-stick offsets
python -m l9_presence.witness_agent run --player P1         # 3. autonomous capture + PoCP + HTML card
# analysis:
python -m l9_presence.session_recorder capture --player P2 --count 8 --rx 3 --ry 4 --region 640 360 1280 720
python -m l9_presence.biometric_features --between sessions_l9/*.npz   # separation + LOO
python -m l9_presence.biometric_features --permute sessions_l9/*.npz   # significance
```

## What is NOT touched / NOT claimed
- No FROZEN-v1 primitive, no PoAC change, no chain submission, no contract, no grind/PCC mode.
- **PoCP is a v0 candidate**, NOT a registered PATTERN-017 primitive and NOT anchored.
- The Witness Agent's hand-offs to **Sentry / Guardian / Curator / ZKBA are default-OFF dry-run**;
  live anchoring/signing/ZKBA are deferred behind explicit operator opt-in, gate-2 separability,
  and lifting `CHAIN_SUBMISSION_PAUSED`.
- The verification card carries a reproducible **commitment, NOT a zero-knowledge proof** (real ZKBA
  is minted later through the governed ceremony).
- Synthetic adversary tests against a **model** of a cheat; a real aimbot / cheat-free decoupled
  capture (killcam/spectator) is the field confirmation. Physiological/GSR is blocked (`GSR_ENABLED=false`).
- 60 fps WGC (`windows-capture`) is the reserved upgrade to sharpen the noisy lag feature; not built.
