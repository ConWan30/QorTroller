"""QorTroller PoEP sub-lane B — menu-lull harvester (Option A: in-Witness handoff).

The device-handoff de-risk returned GO (10/10 clean rounds), so sub-lane B lives in the
Witness process: at a detected gameplay lull (menu/load/pause), hand the controller from the
passive reader to pydualsense, fire a nonce micro-challenge + a SHAM control, capture, hand
back, and harvest to BCC sub-lane B ONLY if the reflex is human-band AND the sham is quiet
(the proven in-game-confound discipline carried over). All gated, default-OFF.

The handoff orchestration takes INJECTED callbacks so the sequence + rollback are fully
unit-testable; the real hardware callbacks (hidapi release/reacquire + pydualsense fire) are
a thin defensive layer wired by the Witness. STATUS: build v0; no FROZEN-v1/PoAC/chain touched.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .poep_derisk import in_human_band


class LullDetector:
    """Detects a sustained low-activity window (menu/load/pause) so a buzz never interrupts
    active play. `activity` is the magnitude of recent stick/trigger change per sample."""

    def __init__(self, activity_threshold: float = 8.0, sustain_samples: int = 30) -> None:
        self.thr = activity_threshold
        self.sustain = sustain_samples
        self._quiet = 0

    def update(self, activity: float) -> bool:
        self._quiet = self._quiet + 1 if activity <= self.thr else 0
        return self.is_lull()

    def is_lull(self) -> bool:
        return self._quiet >= self.sustain

    def reset(self) -> None:
        self._quiet = 0


def should_harvest_b(reflex_latency_ms, sham_reaction) -> bool:
    """Sub-lane B gate: the buzz reflex is in the human band AND the local sham control was
    quiet (so the reaction is genuinely buzz-driven, not the user moving at the menu)."""
    if reflex_latency_ms is None:
        return False
    return in_human_band(reflex_latency_ms) and not bool(sham_reaction)


class HandoffMachine:
    """Option A device handoff for one sub-lane B micro-challenge. Hardware steps are injected
    callbacks (each returns truthy on success; fire_capture returns a sample dict or None) so
    the sequence + rollback are unit-testable. Always tries to return the device to the passive
    reader (reacquire) — the load-bearing step the de-risk validated."""

    def __init__(self, release_passive: Callable, acquire_active: Callable,
                 fire_capture: Callable, release_active: Callable, reacquire_passive: Callable) -> None:
        self._rp, self._aa, self._fc = release_passive, acquire_active, fire_capture
        self._ra, self._rq = release_active, reacquire_passive

    @staticmethod
    def _safe(fn) -> bool:
        try:
            return bool(fn())
        except Exception:
            return False

    @staticmethod
    def _res(ok, stage, sample, reacquired, error) -> dict:
        return {"ok": bool(ok), "stage": stage, "sample": sample,
                "reacquired": bool(reacquired), "error": error}

    def run_one(self) -> dict:
        stage, sample = "release_passive", None
        try:
            if not self._rp():
                return self._res(False, stage, None, False, "release_passive failed")
            stage = "acquire_active"
            if not self._aa():
                return self._res(False, stage, None, self._safe(self._rq), "acquire_active failed")
            stage = "fire_capture"
            sample = self._fc()
            stage = "release_active"
            self._safe(self._ra)
            stage = "reacquire_passive"
            reacq = bool(self._rq())
            return self._res(reacq, "complete" if reacq else stage, sample, reacq,
                             "" if reacq else "reacquire_passive failed")
        except Exception as exc:
            return self._res(False, stage, sample, self._safe(self._rq), f"error:{exc}")


@dataclass
class MenuHarvestConfig:
    enabled: bool = False
    activity_threshold: float = 8.0
    sustain_samples: int = 30


class MenuHarvester:
    """Ties lull detection + a captured micro-challenge sample to a gated BCC sub-lane B record.
    `bcc_harvester` is a BCCHarvester (its own enabled + sublane_b_enabled flags also gate)."""

    def __init__(self, bcc_harvester, cfg: Optional[MenuHarvestConfig] = None) -> None:
        self.bcc = bcc_harvester
        self.cfg = cfg or MenuHarvestConfig()
        self.lull = LullDetector(self.cfg.activity_threshold, self.cfg.sustain_samples)

    def feed_activity(self, activity: float) -> bool:
        return self.lull.update(activity)

    def offer_sample(self, lull_confirmed: bool, reflex_latency_ms, sham_reaction) -> dict:
        if not self.cfg.enabled or not lull_confirmed:
            return {"harvested": False, "reason": "disabled_or_no_lull"}
        if not should_harvest_b(reflex_latency_ms, sham_reaction):
            return {"harvested": False, "reason": f"gate:latency={reflex_latency_ms},sham={sham_reaction}"}
        rec = self.bcc.record_poep({"reflex_latency_ms": float(reflex_latency_ms),
                                    "sham_reaction": bool(sham_reaction)})
        return {"harvested": rec is not None,
                "reason": "ok" if rec else "bcc_sublane_b_off",
                "bcc_seq": rec["seq"] if rec else None}
