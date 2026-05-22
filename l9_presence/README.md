# QorTroller L9 — Input-Output Causal Presence

**Status (2026-05-21): Stream A (causal presence / anti-cheat) VALIDATED + banked.
Stream B (render-loop biometric → separation) — FUSION PHASE COMPLETE: L9 alone 72%
three-way; fusion with gameplay biometrics 77.8% (validated, complementary errors);
fusion with the AIT battery ruled out (correlated errors). No available signal partner
reaches the 80% bar — the remaining lever is MORE PLAYERS (4-way capture is the live
next step), not more signals.** Touches **no FROZEN-v1 primitive, no 228-byte PoAC wire
format, no chain, no contract, no grind/PCC mode.**

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

### Stream B — render-loop biometric → separation ⏸ 77.8% (below 80% bar)
A render-derived play-style fingerprint (coupling, yaw/pitch ratio, decoupled energy).
- Gate-1 (within-player stability): **passed** (CV 0.06–0.19 on 3 features; lag noisy at 31 fps).
- Gate-2 (between-player): 2-way LOO **90.9%**; **3-way LOO 72.2%** (P1/P2/P3), ratio 1.90,
  permutation **p=0.0005** (real). Beats existing controller biometrics (touchpad 63.6%, AIT 66.7%).
- Below the 80% tournament bar alone → went to fusion.

#### Fusion phase outcome (F0–F3 / FB0–FB3)
Score-level fusion of L9 with controller biometrics, each validated with a permutation
guardrail + an **error-independence (Yule's Q)** test. Two partners tried, on real co-captured data:

| Partner | partner LOO | errors vs L9 | fused LOO |
|---|---|---|---|
| free-gameplay L4 (Option A) | 50% | **complementary** (Q = −0.47) | **77.8%** (p = 0.0007) |
| AIT trigger battery (Option B) | 56% | **correlated** (Q = +0.875) | 72.2% |

**Findings:** (1) **fusion is real** — complementary errors lift L9 +11 pts to 77.8%; (2)
**independence beats partner strength** — the weak-but-orthogonal gameplay signal fused
*better* than the strong-but-correlated AIT (AIT shares L9's physiological failure modes);
(3) **no available signal partner crosses 80%.** The remaining lever is **more players**
(the 3-player ceiling), not more signals — a 4-way capture is the live next step.

**Dead-ends ruled out with data (not opinion):** Mahalanobis / richer-feature classifiers
(covariance-regime sweep showed the diagonal endpoint 72% dominates the whole continuum);
weight-tuning and bar-lowering (refused — would not generalize).

## Modules
| file | role |
|---|---|
| `coupling.py` | coupling + residual + negative-control math (the core) — numpy, tested |
| `cv_motion.py` | optical-flow → camera angular velocity (opencv) |
| `screen_capture.py` | capture backends (bettercam→dxcam→mss) + black-frame guard |
| `hid_probe.py` | on-device right-stick byte-offset validator |
| `session_recorder.py` | record / analyze / compare / decouple-control / engagement / **capture** (per-player) |
| `biometric_features.py` | render-loop feature vector; within-player stability; between-player separation + LOO + permutation + Mahalanobis sweep |
| `synth_adversary.py` | synthetic aimbot generator (dev/threshold tool; tests detector vs a model of a cheat) |
| `imu_probe.py` | on-device IMU (gyro/accel) offset+scale validator (still→rotate; de-provisionalizes L4) |
| `cocapture.py` | F1 co-capture recorder (1 kHz HID + frames → L9 **and** L4 views) + autonomous F3-readiness |
| `fusion.py` | F0 score-level combiner + error-independence (Yule's Q) + permutation; FB0 player-paired round-assembler |
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

### Fusion run (co-capture both views, then fuse)
```
python -m l9_presence.imu_probe                                  # once per controller (still→rotate)
python -m l9_presence.cocapture capture --player P1 --count 6    # play normally; game VISIBLE in region
python -m l9_presence.cocapture readiness                        # autonomously says if F3 can run
# F3: build player-paired rounds -> fusion.fusion_report(rounds, ["l9","ait"])  (see FUSION_SCOPE*.md)
```
Design docs: `FUSION_SCOPE.md` (overall) and `FUSION_SCOPE_B.md` (strong-partner round).

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
