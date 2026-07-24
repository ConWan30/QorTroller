"""BridgeFireCaptureAdapter - FireFn/ImuCaptureFn served by the bridge's SINGLE-HID ring. hidring r02.

The honest path to SYNCHRONIZED_CONTROLLER under real play: instead of opening a SECOND controller reader
(the L3 EdgeReflexAdapter's exclusive-HID limit), this adapter asks the RUNNING bridge - which already
owns the one reader + fires via its own L6TriggerDriver + attests activity - to fire a nonce-bound probe
and score the reflex. One reader does activity + fire + IMU, so activity_source=='bridge' and a real fire
coexist -> the sealed candidate rail can honestly reach True.

This is the CLIENT half (contract-defining, decoupled, unit-tested with a fake bridge). It mirrors the L3
adapter's fused-behind-split shape: `fire_fn` POSTs one nonce-bound probe (the bridge fires + captures +
scores on its ring) and one-shot-stashes the ImuWindow; `imu_capture_fn` pops it. The matching bridge
endpoint (`POST /operator/poep/fire`: gated arm + session-loop completion + Future) is the next increment.

WEAKEST-SEAM PIN (grok r02 F): the client NEVER synthesizes a reflex or assumes success. real_hardware,
fired, and the nonce match come ONLY from the bridge response body; a 200 without a confirmed real
nonce-bound fire -> FireResult(fired=False, real_hardware=False). No band-filled latency. One-shot stash.

CLAIM CEILING (mechanism/candidate only): reaching SYNCHRONIZED_CONTROLLER here is a session-liveness
CANDIDATE (advances_poep_enabled=False). It does NOT flip poep_enabled / L6B enablement - the bridge ring
runs under l6b_enabled (the N>=50 usable-Edge-reflex campaign gate) and the endpoint fail-closes otherwise.
Design steered by grok (docs/a2a/poep/round-hidring-02-grok-brainstorm.txt).
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from l9_presence.poep_gameplay_live import FireResult, ImuWindow, clamp_amplitude

CLAIM_CEILING = (
    "Bridge single-HID fire+IMU ring (client). Reaching SYNCHRONIZED_CONTROLLER here is a session-liveness "
    "CANDIDATE (advances_poep_enabled=False); it does NOT flip poep_enabled / L6B enablement. real_hardware, "
    "fired, and the nonce come ONLY from the bridge - the client never synthesizes a reflex."
)

# post_fire(amplitude, nonce) -> dict from the bridge endpoint. Required keys for a real fire:
#   fired: bool, real_hardware: bool, nonce: str (== request), t_fire_ns: int,
#   latency_ms: float|None, peak_lsb: float, precursor_gap_ms: float|None
PostFireFn = Callable[[int, str], dict]


class BridgeFireCaptureAdapter:
    """FireFn/ImuCaptureFn backed by the bridge's ring over an injected `post_fire` callable.

    The real `post_fire` (an HTTP POST to the running bridge) is wired by `make_bridge_fire_adapter`; the
    adapter LOGIC is fully unit-tested with a fake post_fire (no live bridge). The bridge scores the reflex
    on its ONE reader - the client only validates + maps the response.
    """

    def __init__(self, *, post_fire: PostFireFn) -> None:
        self._post_fire = post_fire
        self._stash: dict[int, ImuWindow] = {}

    def fire_fn(self, amplitude: int, nonce: str) -> FireResult:
        amp = clamp_amplitude(amplitude)   # gameplay LOW band; the bridge also clamps
        try:
            resp = self._post_fire(amp, nonce)
        except Exception as e:  # noqa: BLE001 - bridge unreachable / refused surfaces honestly
            return FireResult(fired=False, real_hardware=False, t_fire_ns=0, amplitude=amp,
                              error=f"bridge fire call failed: {e!r}")

        if not isinstance(resp, dict):
            return FireResult(fired=False, real_hardware=False, t_fire_ns=0, amplitude=amp,
                              error="bridge fire response not a dict")

        # WEAKEST-SEAM PIN: a real fire requires the bridge to confirm ALL of fired + real_hardware + a
        # matching nonce. A 200 without them (gate-refused / no write / aliased probe) is NOT a fire.
        confirmed = (
            resp.get("fired") is True
            and resp.get("real_hardware") is True
            and resp.get("nonce") == nonce
        )
        if not confirmed:
            return FireResult(
                fired=False, real_hardware=False, t_fire_ns=0, amplitude=amp,
                error=(f"bridge did not confirm a real nonce-bound fire "
                       f"(fired={resp.get('fired')} real_hardware={resp.get('real_hardware')} "
                       f"nonce_match={resp.get('nonce') == nonce}; {resp.get('error', '')})"),
            )

        try:
            t_fire = int(resp["t_fire_ns"])
            peak = float(resp["peak_lsb"])
        except (KeyError, TypeError, ValueError) as e:
            return FireResult(fired=False, real_hardware=False, t_fire_ns=0, amplitude=amp,
                              error=f"bridge fire response missing/invalid features: {e!r}")

        # No band-fill: no clean peak (latency None/<=0) -> latency 0, MEASURED peak. Sealed verify fails.
        raw_lat = resp.get("latency_ms")
        lat = float(raw_lat) if (raw_lat is not None and float(raw_lat) > 0.0) else 0.0
        precursor = resp.get("precursor_gap_ms")
        window = ImuWindow(
            t_response_ns=t_fire + int(lat * 1e6), latency_ms=lat, peak_lsb=peak,
            precursor_gap_ms=float(precursor) if precursor is not None else 0.0,
        )
        self._stash[t_fire] = window   # one-shot
        return FireResult(fired=True, real_hardware=True, t_fire_ns=t_fire, amplitude=amp)

    def imu_capture_fn(self, t_fire_ns: int) -> Optional[ImuWindow]:
        return self._stash.pop(int(t_fire_ns), None)   # consume+clear; miss / NO_GO(0) / replay -> None


# F-RIG27-6 (grok firetimeout-r02 B): the client urllib timeout must OUTLAST the endpoint's
# wait_for (the HTTP layer sits on the endpoint which sits on the Future). Ordering pin, enforced
# by test: CLIENT_DEFAULT_TIMEOUT_S > endpoint default (POEP_FIRE_TIMEOUT_S=20) > max observed RP
# drain (~11s). Endpoint clamps [5, 60]; the client default sits +5s above the endpoint default.
ENDPOINT_FIRE_TIMEOUT_DEFAULT_S = 20.0
CLIENT_DEFAULT_TIMEOUT_S = 25.0
MAX_OBSERVED_RP_DRAIN_S = 11.0


def make_bridge_fire_adapter(
    *, bridge_url: str = "http://localhost:8080", api_key: str = "",
    timeout_s: float = CLIENT_DEFAULT_TIMEOUT_S,
) -> BridgeFireCaptureAdapter:  # pragma: no cover - needs a live bridge (rig)
    """Wire a real HTTP `post_fire` to the running bridge's POST /operator/poep/fire endpoint.

    The bridge enforces gating (l6b_enabled + POEP_LIVE_FIRE_ENABLED) and does the real fire+score on its
    single reader; a refused/ungated bridge returns fired=False and the adapter reports it honestly.
    """
    import json
    import urllib.request

    # Measured live 2026-07-18: the operator sub-app mounts at /operator AND in-app routes carry their
    # own /operator/ prefix (the documented doubled-prefix convention) -> the external path is DOUBLED.
    url = bridge_url.rstrip("/") + "/operator/operator/poep/fire"

    def _post(amplitude: int, nonce: str) -> dict:
        body = json.dumps({"nonce": nonce, "amplitude": int(amplitude)}).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if api_key:
            req.add_header("x-api-key", api_key)
        with urllib.request.urlopen(req, timeout=timeout_s) as r:  # noqa: S310 - operator-local bridge
            return json.loads(r.read().decode())

    return BridgeFireCaptureAdapter(post_fire=_post)
