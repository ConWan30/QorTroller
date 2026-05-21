# QorTroller L9 — Input-Output Causal Presence (design-only empirical probe)

**Status:** design-only probe. Touches **no FROZEN-v1 primitive, no PoAC wire
format, no chain, no grind/PCC mode**. Every downstream build phase is gated on
the probe's GO/NO-GO.

## The idea
The next PITL layer after L8 (BT presence). Where **L2C** correlates right-stick
velocity against `gyro_z` (controller twist), **L9** correlates the human's
aim-stick input against the **rendered on-screen camera motion**, and adds a
**residual decomposition** that localizes motion the stick can't explain — the
aimbot/injection signature. It sits on the cloud-client attestation gap RICOCHET
publicly concedes is open in Warzone. Everything here is **local + deterministic**
(no cloud model) so it can become part of a cryptographic determination.

## The one question this probe answers (GO / NO-GO)
> Does the deterministic input↔on-screen-motion **coupling/residual score
> separate a human-driven session from a script/aimbot-driven one**, through PS
> Remote Play latency?

If yes → build Steps 2–5 (see `docs` plan). If no → stop; record the finding.

## Modules
| file | role | deps |
|---|---|---|
| `coupling.py` | coupling + residual math (the core) | numpy only ✅ tested |
| `screen_capture.py` | Remote Play capture (dxcam→mss) + black-frame guard | numpy; dxcam/mss optional |
| `cv_motion.py` | optical-flow camera angular velocity | opencv-python |
| `session_recorder.py` | record + offline-analyze a labeled session | numpy, opencv, hidapi |
| `derisk_check.py` | the decisive 10-min check (run FIRST) | dxcam/mss + hidapi |

## Install (operator rig)
```
pip install dxcam opencv-python hidapi numpy        # dxcam = Windows; mss as fallback
```

## Run order
1. **De-risk first** (Remote Play open + Warzone visible + controller in hand):
   ```
   python -m l9_presence.derisk_check
   ```
   GO = non-black capture AND HID reads. If black → disable Windows
   "Hardware-accelerated GPU scheduling" + reboot, OR use a WGC backend; keep
   Remote Play **maximized**.
2. **Record sessions** (~10 human, ~10 scripted-for-adversarial-test):
   ```python
   from l9_presence.session_recorder import record_session, analyze_session
   record_session("h01.npz", duration_s=90, label="human",  region=(0,0,1920,1080))
   record_session("s01.npz", duration_s=90, label="scripted", region=(0,0,1920,1080))
   print(analyze_session("h01.npz")); print(analyze_session("s01.npz"))
   ```
3. **Compare distributions** — human `coupling_score` should clearly exceed
   scripted, scripted `decoupled_energy` should clearly exceed human, and the
   `neg_control_margin` should be large for humans. That separation is the GO.

## Honest limits (must hold)
- **Remote Play latency/jitter** is absorbed by the causal-lag search but is a
  confounder — the **negative control (time-shuffled input) must collapse**.
- **Legitimate aim-assist also adds residual.** The probe measures the
  *separation* between the human-with-aim-assist residual baseline and the aimbot
  residual, not absolute residual. Characterize the human baseline first.
- **CV is research-grade** — validate `cv_motion` extraction against eyeball
  ground truth on a few clips before trusting scores.
- **Input-masked aimbots** (fake stick input + real aim-assist) partially defeat
  coupling — the probe tests the simple decoupled case first; this is a known open
  limit, not a solved claim.
- HID stick byte-offsets differ USB vs BT — wire `session_recorder` to
  `controller/hid_report_parser.py` and validate on-device.

## What this is NOT
No new FROZEN-v1 primitive, no invented crypto, no cloud model, no PoAC change,
no grind-mode change. If the probe says GO, integration reuses your existing
stack (L2B/L2C lag-search pattern, AdjudicationRegistry anchor, FSCA, the
Operator Initiative) — adding exactly one new layer (L9) and one `warzone`
game profile.
```
