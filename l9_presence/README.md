# QorTroller L9 — Input-Output Causal Presence

**Status (2026-05-21): Stream A (causal presence / anti-cheat) VALIDATED + banked.
Stream B (render-loop biometric → separation) — investigation COMPLETE across 4 players:
L9 alone is a real, GENERALIZING, latency-robust separator (90.9% / 72.2% / 62.5% LOO at
2/3/4 players, all p≤0.0007, 1.8×→2.5× chance) but not tournament-grade alone; FUSION did
NOT reliably help (the 3-player 77.8% relied on error-complementarity that flipped to
correlated when a 4th player was added; AIT was correlated throughout). No signal partner
is a reliable path to 80% — the lever is MORE PLAYERS, not more signals.** Touches **no
FROZEN-v1 primitive, no 228-byte PoAC wire format, no chain, no contract, no grind/PCC mode.**

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

### Stream B — render-loop biometric → separation ⏸ generalizes, not standalone-tournament-grade
A render-derived play-style fingerprint (coupling, yaw/pitch ratio, decoupled energy).
- Gate-1 (within-player stability): **passed** (CV 0.06–0.19 on 3 features; lag noisy at 31 fps).
- Gate-2 (between-player), L9 alone, **all permutation-significant (p≤0.0007):**

  | Players | LOO | chance | ratio to chance |
  |---|---|---|---|
  | 2-way (P1/P2) | 90.9% | 50% | 1.8× |
  | 3-way (P1–P3) | 72.2% | 33% | 2.2× |
  | 4-way (P1–P4) | 62.5% | 25% | **2.5×** |

  Accuracy falls as classes grow (expected) but the **signal-to-chance margin widens** — it
  **generalizes** to new people, not an artifact of a fixed three. Beats controller biometrics
  (touchpad 63.6%, AIT 66.7%). Below 80% standalone.

#### Fusion investigation (F0–F3 / FB0–FB3) — fusion did NOT reliably help
Score-level fusion of L9 with controller biometrics, validated with a permutation guardrail +
an **error-independence (Yule's Q)** test:

| Partner | players | errors vs L9 | fused LOO |
|---|---|---|---|
| free-gameplay L4 | 3 | complementary (Q = −0.47) | 77.8% (p=0.0007) |
| free-gameplay L4 | **4** | **correlated (Q = +0.88)** | **58.3% (hurts)** |
| AIT trigger battery | 3 | correlated (Q = +0.875) | 72.2% |

**Findings:** (1) the promising 3-player fusion (77.8%) **did not generalize** — adding a 4th
player flipped the errors to correlated and fusion stopped helping; (2) **independence, not
partner strength, drives fusion** — and it wasn't stable across players/partners; (3) **fusion
is not a reliable path to 80%.** The durable result is **L9 alone**, which generalizes.

**Latency robustness (P4 finding):** P4 ran a high-latency stream — clean coupling (up to 0.955)
at **~400–500 ms** lag vs ~40–80 ms on the low-latency rig. The causal-lag window was widened
260→500 ms; L9 detects human causal presence even across a 400 ms cloud-stream (strengthens the
cloud-client-attestation thesis).

**Dead-ends ruled out with data (not opinion):** Mahalanobis / richer-feature classifiers
(covariance-regime sweep: diagonal endpoint 72% dominates the whole continuum); fusion as a
reliable booster (above); weight-tuning and bar-lowering (refused — would not generalize). The
one lever that consistently helps the signal hold up is **more players**.

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
pip install windows-capture mss opencv-python hidapi numpy   # windows-capture = WGC, 60fps
```
Backends, preference order: **`wgc`** (Windows.Graphics.Capture, 60 fps, overlay-capable,
no comtypes — sharpens the lag feature; `pip install windows-capture`) → `mss` (GDI,
crash-free ~31 fps, the proven fallback) → `bettercam`/`dxcam` (DXGI; crash in `comtypes`
on Python 3.13 — avoid). Pass `--backend wgc` for 60 fps.

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
- **WGC capture BUILT + VALIDATED** (`screen_capture.py` `wgc` backend via `windows-capture`):
  `--backend wgc` runs **~44 fps during gameplay** (vs mss ~31) after a GIL-yield fix — overlay-capable,
  crash-free, falls back to mss if absent. **BUT WGC adds ~400 ms of capture latency** (DWM compositor
  buffering): same player's lag reads ~580 ms on WGC vs ~110 ms on mss. Implications: (a) the **lag feature
  does NOT sharpen** — its noise was a search-window / spurious-peak issue, not frame-rate, and WGC confounds
  it with pipeline latency → **lag stays excluded from the biometric** (the 3 stable features remain);
  (b) **don't mix backends in one biometric corpus** (coupling/lag differ by backend latency); (c) for WGC,
  set `L9_LAG_MAX_MS≈800` or coupling truncates at the 500 ms default. WGC's real value is higher-fps,
  overlay-capable, crash-free *coupling* capture — not lag.
