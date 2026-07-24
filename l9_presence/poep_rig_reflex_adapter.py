"""EdgeReflexAdapter - the L3 fire+IMU MECHANISM (rig-only). gp/l3-adapter r02 build.

Adapts the PROVEN fused reflex primitive (scripts/poep_live_capture._fire_probe_silent, which built the
N=52 Edge-reflex corpus) into challenge_live's SPLIT FireFn/ImuCaptureFn interface. The primitive fires
AND captures in one call; challenge_live wants fire_fn(amp,nonce) THEN imu_capture_fn(t_fire). So the
adapter is fused-behind-split: fire_fn runs the whole primitive (real HID _sync_write) + analysis,
stashes the ImuWindow one-shot, returns FireResult; imu_capture_fn pops the stash. The primitive is
reused WHOLE (no decomposition -> zero measurement drift vs the corpus).

CLAIM CEILING (grok r02 FIX #8 - mechanism only): building or running this does NOT flip poep_enabled /
L6B / L6_CHALLENGES, and does NOT by itself make SYNCHRONIZED_CONTROLLER rig-reachable. candidate=True
needs bridge-attested activity, which conflicts with the exclusive HID this mechanism requires
(dual-writer). The single-HID bridge fire+IMU ring is the NEXT arc. `real_hardware=True` marks only that
a real force fired - it is NOT a presence verdict. advances_poep_enabled=False.

Honesty rails (grok r02 break-test): real_hardware=True IFF a real _sync_write executed (no import-only /
pre-write-abort / mock path sets it True in production); no clean reflex peak -> latency 0 + MEASURED
peak (NEVER band-filled) so the sealed verify fails honestly; one-shot stash (consume+clear); refuse to
fire when the bridge holds the pad (no dual-open). The adapter passes RAW features only - the sealed
challenge_live / verify_live_response owns the verdict; the adapter never sets candidate / live_hardware.
Design steered by grok (docs/a2a/poep/round-l3-adapter-02-grok-brainstorm.txt).
"""
from __future__ import annotations

import os
import secrets
from typing import Any, Callable, Optional

from l9_presence.poep_gameplay_live import (
    LIVE_FIRE_ENV,
    FireResult,
    ImuWindow,
    clamp_amplitude,
)

CLAIM_CEILING = (
    "L3 fire+IMU mechanism only. Does NOT flip poep_enabled / L6B / L6_CHALLENGES and does NOT by "
    "itself make SYNCHRONIZED_CONTROLLER rig-reachable (bridge-attested activity conflicts with the "
    "exclusive HID this requires). real_hardware=True marks a real force fired, not a presence verdict."
)

# Gameplay-scaled anti-tell delay (named; NOT desk 3-12s, NOT 0). The activity gate decides WHEN to call
# fire_fn; the poll-burst tell lives inside the fire window, so a small CSPRNG pre-fire delay is retained.
GAMEPLAY_MIN_DELAY_S = 0.5
GAMEPLAY_MAX_DELAY_S = 2.5

# fire_probe(amplitude, nonce, delay_s) -> (t_challenge_ns, payload). Does the REAL _sync_write; raises on
# any hardware failure BEFORE returning. `payload` is opaque to the adapter core (handed to analyze).
FireProbeFn = Callable[[int, str, float], "tuple[int, Any]"]
# analyze(payload) -> (latency_ms|None, peak_lsb, precursor_gap_ms|None). Pure feature extraction.
AnalyzeFn = Callable[[Any], "tuple[Optional[float], float, Optional[float]]"]
DelayFn = Callable[[], float]
BridgeRunningFn = Callable[[], bool]


def _csprng_delay(min_s: float = GAMEPLAY_MIN_DELAY_S, max_s: float = GAMEPLAY_MAX_DELAY_S) -> float:
    lo, hi = min(min_s, max_s), max(min_s, max_s)
    span = max(0.0, hi - lo)
    return lo + (secrets.randbelow(10_000) / 10_000.0) * span


class EdgeReflexAdapter:
    """Fused-behind-split FireFn/ImuCaptureFn over an injected reflex primitive.

    All hardware lives behind the injected `fire_probe` / `analyze` / `bridge_running` callables, so the
    adapter LOGIC is fully unit-tested with fakes (no rig). The real callables are wired by the env-gated
    `make_edge_reflex_adapter` factory below.
    """

    def __init__(
        self,
        *,
        fire_probe: FireProbeFn,
        analyze: AnalyzeFn,
        bridge_running: BridgeRunningFn,
        delay_fn: DelayFn = _csprng_delay,
    ) -> None:
        self._fire_probe = fire_probe
        self._analyze = analyze
        self._bridge_running = bridge_running
        self._delay_fn = delay_fn
        self._stash: dict[int, ImuWindow] = {}

    # -- FireFn --------------------------------------------------------------------------------------
    def fire_fn(self, amplitude: int, nonce: str) -> FireResult:
        amp = clamp_amplitude(amplitude)   # gameplay LOW band (40-80); never desk 255

        # FIX #1: refuse to fire while the bridge holds the pad - no dual-open race, no half-open garbage.
        if self._bridge_running():
            return FireResult(
                fired=False, real_hardware=False, t_fire_ns=0, amplitude=amp,
                error="bridge_running_dual_writer (exclusive HID required; stop the bridge to fire)",
            )

        delay_s = float(self._delay_fn())
        # FIX #3: any abort BEFORE/AT the write -> fired=False, real_hardware=False (no synthesized success).
        try:
            t_challenge_ns, payload = self._fire_probe(amp, nonce, delay_s)
        except Exception as e:  # noqa: BLE001 - hardware/driver failure surfaces honestly
            return FireResult(
                fired=False, real_hardware=False, t_fire_ns=0, amplitude=amp,
                error=f"fire aborted pre/at write: {e!r}",
            )

        # The real _sync_write executed (stimulus path returned) -> a real force fired.
        t_fire = int(t_challenge_ns)
        try:
            latency_ms, peak_lsb, precursor = self._analyze(payload)
        except Exception as e:  # noqa: BLE001
            # The write DID happen (real_hardware=True); we just couldn't score -> no window stashed ->
            # imu_capture_fn returns None -> challenge_live records no_imu_window -> verify fails honestly.
            return FireResult(
                fired=True, real_hardware=True, t_fire_ns=t_fire, amplitude=amp,
                error=f"analyze failed (no window): {e!r}",
            )

        # FIX #4: no clean peak -> latency 0 (None/<=0), peak as MEASURED. NEVER band-fill a latency.
        lat = float(latency_ms) if (latency_ms is not None and float(latency_ms) > 0.0) else 0.0
        window = ImuWindow(
            t_response_ns=t_fire + int(lat * 1e6),
            latency_ms=lat,
            peak_lsb=float(peak_lsb),
            precursor_gap_ms=float(precursor) if precursor is not None else 0.0,
        )
        self._stash[t_fire] = window   # FIX #2: one-shot stash keyed by the fire instant
        return FireResult(fired=True, real_hardware=True, t_fire_ns=t_fire, amplitude=amp)

    # -- ImuCaptureFn --------------------------------------------------------------------------------
    def imu_capture_fn(self, t_fire_ns: int) -> Optional[ImuWindow]:
        # FIX #2: consume-and-clear. A miss (NO_GO's imu_capture_fn(0), replay, or wrong key) -> None.
        return self._stash.pop(int(t_fire_ns), None)


def make_edge_reflex_adapter(
    *,
    device_id: Optional[str] = None,
    mode: str = "pulse",
    hold_ms: int = 1500,
    pre_samples: int = 50,
    poll_interval_s: float = 0.008,
    capture_window_ms: float = 900.0,
    response_threshold_lsb: float = 500.0,
    reissue: bool = True,
) -> EdgeReflexAdapter:  # pragma: no cover - hardware path (rig-only; never CI)
    """Wire the REAL Edge reflex primitive into an EdgeReflexAdapter. GATED on POEP_LIVE_FIRE_ENABLED=1.

    All hardware imports are lazy + inside this factory so the module loads HID-free on CI/dev boxes.
    Mirrors poep_gameplay_live.make_real_hid_fire's gate. Returns an adapter whose fire_fn does a REAL
    adaptive-trigger force write + reflex capture on the connected Edge.
    """
    if os.environ.get(LIVE_FIRE_ENV, "") != "1":
        raise RuntimeError(
            f"real fire gated: set {LIVE_FIRE_ENV}=1 on the operator rig (never CI)"
        )

    import json

    from bridge.vapi_bridge.l6b_desk_session import DeskProbeConfig, analyze_desk_probe
    from controller.dualshock_emulator import DualSenseReader, HAS_DUALSENSE
    from scripts.l6b_desk_reaction_session import _bridge_running, _resolve_registered_edge_device_id
    from scripts.poep_live_capture import _fire_probe_silent

    if not HAS_DUALSENSE:
        raise RuntimeError("pydualsense not installed -- pip install pydualsense (operator rig)")

    reader = DualSenseReader()
    if not reader.connect():
        raise RuntimeError("could not connect to the DualSense Edge (rig)")
    ds = reader.ds
    dev_id = device_id or _resolve_registered_edge_device_id() or "unregistered-rig"

    def _real_fire_probe(amp: int, nonce: str, delay_s: float) -> "tuple[int, Any]":
        cfg = DeskProbeConfig(
            r2_force=clamp_amplitude(amp), mode=mode, hold_ms=max(50, min(2000, hold_ms)),
            pre_samples=pre_samples, poll_interval_s=poll_interval_s,
            capture_window_ms=capture_window_ms, response_threshold_lsb=response_threshold_lsb,
        )
        # stimulus=True -> _fire_probe_silent does the REAL L6TriggerDriver._sync_write.
        probe_ts, pre, post, _r2, _t_arm, t_challenge = _fire_probe_silent(
            ds, cfg, delay_s=delay_s, reader=reader, reissue=reissue, stimulus=True
        )
        return int(t_challenge), (pre, post, probe_ts, cfg)

    def _real_analyze(payload: Any) -> "tuple[Optional[float], float, Optional[float]]":
        pre, post, probe_ts, cfg = payload
        result, diag_json = analyze_desk_probe(pre, post, probe_ts, cfg)
        try:
            precursor = json.loads(diag_json).get("precursor_gap_ms")
        except Exception:  # noqa: BLE001
            precursor = None
        return result.latency_ms, float(result.accel_delta_peak), precursor

    def _bridge_up() -> bool:
        try:
            return bool(_bridge_running())
        except Exception:  # noqa: BLE001 - if we can't tell, assume contention (fail-closed, refuse fire)
            return True

    print(f"[l3-adapter] EdgeReflexAdapter wired for device {dev_id} (mode={mode}). {CLAIM_CEILING}")
    return EdgeReflexAdapter(
        fire_probe=_real_fire_probe, analyze=_real_analyze, bridge_running=_bridge_up
    )
