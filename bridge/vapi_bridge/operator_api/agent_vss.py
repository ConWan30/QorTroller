"""VSS (Verifiable Stream Seat) eligibility routes — VSS-1.

Implements docs/design/buzz-vss-stream-seat-scope-v0.md §6 (Bridge surface):
  GET /vss/eligibility → fail-closed eligibility probe.

Eligibility is purely hardware-side:
  eligible = capture_up AND retina_oracle_running

It does NOT assert "human proven" and does NOT require IoID.
Buzz human membership is enforced at the seat-publish / Buzz layer, not here.
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Header


def register_agent_vss_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    check_read_key: Callable[[str], None],
) -> None:
    """Register VSS-1 eligibility endpoint."""

    # VSS-1 — GET /vss/eligibility
    # ------------------------------------------------------------------
    @app.get("/vss/eligibility")
    async def get_vss_eligibility(
        x_api_key: str = Header(default=""),
    ):
        """Verifiable Stream Seat eligibility probe (VSS-1).

        Fail-closed: if capture or retina oracle process is down,
        eligible=false with a clear reason.

        Per VSS scope §2:
          - Buzz human membership is required to OPEN a seat, but
            membership is enforced at the Buzz layer, not here.
          - IoID is NEVER required.
          - Retina gate is process health, not humanity cert.
          - No chain writes, no media upload, no FROZEN wire changes.
        """
        check_read_key(x_api_key)
        _now = time.time()

        # --- capture health (from PCC monitor or store) ---
        capture_up = False
        capture_detail = "no monitor attached"
        _monitor = getattr(app, "_pcc_monitor", None)
        if _monitor is not None:
            try:
                _live = _monitor.get_status()
                _cap_state = _live.get("capture_state", "DISCONNECTED")
                capture_up = _cap_state in ("NOMINAL", "DEGRADED")
                capture_detail = (
                    f"capture_state={_cap_state} "
                    f"poll_rate={_live.get('poll_rate_hz', 0):.0f}Hz"
                )
            except Exception as exc:
                capture_detail = f"monitor error: {exc}"
        else:
            # Fallback: read latest from store
            try:
                _cap = store.get_capture_health_status(1)
                _cap_state = _cap.get("capture_state", "DISCONNECTED")
                capture_up = _cap_state in ("NOMINAL", "DEGRADED")
                capture_detail = f"store: capture_state={_cap_state}"
            except Exception:
                capture_detail = "store unreadable"

        # --- retina oracle process health ---
        # The retina oracle "process running" is inferred from the retina
        # DePIN policy state attached to the app at startup. This is
        # advisory presence (process health), NOT humanity certification
        # per VSS scope §2 and the capture-rig skill.
        retina_oracle_running = False
        oracle_detail = "no policy state attached"
        _policy_state = getattr(app, "_retina_policy_state", None)
        if _policy_state is not None:
            # The policy state has an `effective_perception` boolean that
            # reflects whether the retina perception pipeline is effective
            # (package importable + not sim mode + not operator-disarmed).
            try:
                _snap = _policy_state.to_dict() if hasattr(
                    _policy_state, "to_dict"
                ) else {}
                retina_oracle_running = bool(
                    _snap.get("effective_perception", False)
                )
                oracle_detail = (
                    f"effective_perception={retina_oracle_running}"
                )
            except Exception as exc:
                oracle_detail = f"policy state error: {exc}"
        else:
            # Fallback: no policy state attached → oracle process not running.
            # Fail-closed: cfg.retina_perception_enabled defaults to True, but
            # that's a config flag, not a process-health signal. Without a
            # live policy state we cannot confirm the oracle is actually
            # running, so we report false.
            retina_oracle_running = False
            oracle_detail = "no retina policy state attached (process health unconfirmed)"

        # --- fail-closed eligibility ---
        eligible = capture_up and retina_oracle_running

        reasons: list[str] = []
        if not capture_up:
            reasons.append(f"capture down ({capture_detail})")
        if not retina_oracle_running:
            reasons.append(f"retina oracle not running ({oracle_detail})")

        return {
            "eligible": eligible,
            "capture_up": capture_up,
            "retina_oracle_running": retina_oracle_running,
            "reason_if_closed": "; ".join(reasons) if reasons else "",
            "honesty": {
                "poep_enabled": bool(getattr(cfg, "poep_enabled", False)),
                "advisory_oracle": True,
            },
            "timestamp": _now,
        }
