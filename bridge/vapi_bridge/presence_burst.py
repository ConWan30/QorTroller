"""Presence-burst (duty-cycle) capture controller — coexist with the live Remote Play stream.

WGC screen-capture competes with Remote Play's GPU decoder (the observer effect: capturing the screen lags
the very game it watches — confirmed live A/B, capture-on=choppy / capture-off=smooth, INDEPENDENT of rate,
because WGC forces DWM to copy every composed frame to the capture pool regardless of how often we read it;
only STOPPING the session frees the GPU). So continuous capture is unusable during gameplay.

But COUPLED_CLEAN is reachable in a few seconds (proven live: coupling 0.348/0.259 at ~13.6fps). So instead
of capturing continuously, capture BRIEF BURSTS: start the WGC session, accumulate ~burst_s of input->screen
coupling (HID is fed continuously by the dualshock loop, independent of capture state), read the presence
verdict, then STOP the session — releasing the GPU so gameplay is smooth between bursts. This matches
QorTroller's attestation model better than surveillance: prove presence WHEN asked (periodic or on-demand),
like a captcha / PoEP, not continuously.

Default-off (retina_capture_burst_enabled). No FROZEN-v1 / 228B PoAC / chain / IOTX. Advisory presence lobe.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional


class PresenceBurstController:
    """Toggles a RetinaGameCapture-like source in bursts. The source must expose:
    start() -> bool, stop() -> None, status() -> dict (with nqpv_verdict / coupling_score / ...)."""

    def __init__(self, rgc: Any, *, burst_s: float = 6.0, period_s: float = 60.0,
                 trigger_path: str = "", log: Any = None, de_gate: bool = False,
                 de_keep_quantile: float = 0.5, sample_interval_s: float = 1.0) -> None:
        self._rgc = rgc
        self._burst_s = max(1.0, float(burst_s))
        self._period_s = max(0.0, float(period_s))   # <=0 -> ON-DEMAND only (no periodic capture)
        self._trigger_path = trigger_path or ""
        self._log = log
        # P1 decoupled-energy gate (default-off): when on, the burst SAMPLES coupling windows across burst_s,
        # ranks them by decoupled_energy, and bases the verdict on the median coupling of the genuine-aim
        # (lowest-DE) windows — dropping walking/world-scroll-diluted windows. Off -> path is byte-identical.
        self._de_gate = bool(de_gate)
        self._de_keep_quantile = float(de_keep_quantile)
        self._sample_interval_s = max(0.2, float(sample_interval_s))
        self._lock = asyncio.Lock()                  # single-flight: never two overlapping bursts
        self._running = False
        self.last_proof: Optional[dict] = None

    async def fire_once(self) -> dict:
        """One presence burst: start capture, accumulate burst_s, read the verdict, STOP capture (free GPU).

        Single-flight (a concurrent call waits its turn). Fail-open: any start/read error -> ok=False proof,
        and the capture is ALWAYS stopped in finally (the GPU must never be left held)."""
        async with self._lock:
            t0 = time.time()
            try:
                started = bool(self._rgc.start())
            except Exception as exc:  # noqa: BLE001
                return self._record(False, None, None, None, None, time.time() - t0, f"start_error:{exc!r}")
            if not started:
                return self._record(False, None, None, None, None, time.time() - t0, "capture_start_failed")
            try:
                if self._de_gate:
                    return await self._fire_gated(t0)
                await asyncio.sleep(self._burst_s)
                try:
                    st = self._rgc.status() or {}
                except Exception:  # noqa: BLE001
                    st = {}
                return self._record(True, st.get("nqpv_verdict"), st.get("coupling_score"),
                                    st.get("negative_control"), st.get("grid_samples"),
                                    time.time() - t0, None)
            finally:
                try:
                    self._rgc.stop()      # release the GPU -> smooth gameplay between bursts
                except Exception:  # noqa: BLE001
                    pass

    async def _fire_gated(self, t0: float) -> dict:
        """P1 gated burst: reset the window history, SAMPLE status across burst_s (each sample populates a
        coupling window in the RGC), then base the verdict on the decoupled-energy-gated median coupling of
        the genuine-aim windows. Fail-open; the caller's finally still STOPS the capture."""
        try:
            rh = getattr(self._rgc, "reset_burst_history", None)
            if rh:
                rh()
        except Exception:  # noqa: BLE001
            pass
        end = time.time() + self._burst_s
        while time.time() < end:
            await asyncio.sleep(min(self._sample_interval_s, max(0.0, end - time.time())))
            try:
                self._rgc.status()        # populates the burst window history via latest_l9_report
            except Exception:  # noqa: BLE001
                pass
        try:
            st = self._rgc.status() or {}
        except Exception:  # noqa: BLE001
            st = {}
        coupled, rep, n_kept, n_total = False, None, 0, 0
        try:
            g = self._rgc.burst_gated_summary(self._de_keep_quantile)
            coupled, rep, n_kept, n_total = bool(g.coupled), g.representative_coupling, g.n_kept, g.n_total
        except Exception:  # noqa: BLE001
            pass
        verdict = "COUPLED_CLEAN" if coupled else ("IMPLAUSIBLE" if n_total else None)
        proof = self._record(True, verdict, rep, st.get("negative_control"), st.get("grid_samples"),
                             time.time() - t0, None)
        proof["de_gated"] = True
        proof["n_kept"] = n_kept
        proof["n_total"] = n_total
        return proof

    def _record(self, ok: bool, verdict, coupling, null, grid, elapsed_s: float,
                reason: Optional[str]) -> dict:
        proof = {
            "ok": ok, "verdict": verdict, "coupling_score": coupling, "negative_control": null,
            "grid_samples": grid, "burst_s": round(self._burst_s, 2),
            "elapsed_s": round(elapsed_s, 2), "reason": reason, "ts": time.time(),
        }
        self.last_proof = proof
        if self._log is not None:
            try:
                self._log.info("presence-burst proof: verdict=%s coupling=%s ok=%s",
                               verdict, coupling, ok)
            except Exception:  # noqa: BLE001
                pass
        return proof

    async def run_periodic(self) -> None:
        """Duty-cycle loop: a burst, then a GPU-free gap (smooth gameplay), repeat. <=0 period -> on-demand only.
        Starts with an initial delay so the bridge finishes booting before the first (briefly-laggy) burst."""
        if self._period_s <= 0:
            return
        self._running = True
        await asyncio.sleep(min(self._period_s, 20.0))
        while self._running:
            try:
                await self.fire_once()
            except Exception:  # noqa: BLE001 — the loop must survive any single burst failure
                pass
            await asyncio.sleep(max(1.0, self._period_s - self._burst_s))

    async def run_on_demand(self, poll_s: float = 3.0) -> None:
        """ON-DEMAND: NO periodic capture (zero lag during play). Poll for a trigger file; when it appears,
        fire ONE full-rate proof burst (accept the brief lag — a deliberate verification moment, like a
        captcha) and delete the trigger. The lightest live-play posture: smooth until a proof is requested.
        Trigger a proof by creating the file (e.g. `touch <trigger_path>`)."""
        import os
        if not self._trigger_path:
            return
        self._running = True
        await asyncio.sleep(min(poll_s, 10.0))
        while self._running:
            try:
                if os.path.exists(self._trigger_path):
                    try:
                        os.remove(self._trigger_path)
                    except Exception:  # noqa: BLE001
                        pass
                    if self._log is not None:
                        self._log.info("presence-burst: on-demand trigger -> firing proof burst")
                    await self.fire_once()
            except Exception:  # noqa: BLE001 — the watcher must survive any failure
                pass
            await asyncio.sleep(max(1.0, poll_s))

    async def run(self) -> None:
        """Dispatch: periodic duty-cycle (period>0) or on-demand file-trigger (period<=0 — zero lag until
        a proof is explicitly requested)."""
        if self._period_s > 0:
            await self.run_periodic()
        else:
            await self.run_on_demand()

    def stop(self) -> None:
        self._running = False
