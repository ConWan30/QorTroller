"""QorTroller L9 — Input-Output Causal Presence (DESIGN-ONLY empirical probe).

The next PITL layer after L8 (BT presence). L9 proves the human's physical
controller inputs CAUSALLY DRIVE the rendered game state — the one correlation
no anti-cheat performs, sitting on the cloud-client attestation gap RICOCHET
publicly concedes is open in Warzone.

Built entirely local + deterministic (no cloud model) so it can become part of
a cryptographic determination rather than an opinion. Mirrors the established
L2B/L2C causal-lag-search pattern and extends it from input<->IMU to
input<->rendered-output.

STATUS: design-only empirical probe. Touches NO FROZEN-v1 primitive, NO PoAC
wire format, NO chain, NO grind/PCC mode. Every build phase is gated on the
probe's GO/NO-GO: does the coupling/residual score separate human-driven from
script/aimbot-driven sessions through PS Remote Play latency?

Modules:
  coupling.py        — deterministic coupling + residual math (numpy-only; the core)
  cv_motion.py       — optical-flow camera angular velocity from frames (opencv)
  screen_capture.py  — background Remote Play window capture (dxcam->mss fallback)
  session_recorder.py— synced HID-input + frame-motion session recorder
  derisk_check.py    — the decisive 10-minute check (capture non-black? HID reads?)
"""

__all__ = ["__version__"]
__version__ = "0.0.1-probe"
