"""Calibration / separation / L4 / graduation routes (D-DECON-2 operator_api residue #14).

Register-function split per audits/decon-store-map.md agent_calibration domain.
Routes byte-identical to the former inline handlers in _app.py.
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Query, Request


def register_agent_calibration_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
    check_read_key: Callable[[str], None],
    repo_root,
) -> None:
    """Register L4 calibration, separation ratio, capture, and graduation HTTP routes."""


    # --- Phase 125: Per-Battery L4 Calibration Apply ---

    @app.post("/agent/apply-l4-battery-calibration")
    def apply_l4_battery_calibration(
        api_key: str = Query(...),
        battery_type: str = Query(..., description="Battery type (touchpad/trigger/button/gameplay)"),
        anomaly_threshold: float = Query(..., description="L4 anomaly threshold [5.0, 15.0]"),
        continuity_threshold: float = Query(..., description="L4 continuity threshold [3.0, 10.0]"),
        n_sessions: int = Query(default=0, description="Number of calibration sessions used"),
        calibration_feature_dim: "int | None" = Query(
            default=None,
            description="Feature dimension used for calibration (default: live_feature_dim)",
        ),
        notes: "str | None" = Query(default=None),
    ):
        """Phase 125 — Apply a per-battery L4 calibration result.

        Inserts a track into l4_threshold_tracks (bounds enforced: anomaly [5.0, 15.0],
        continuity [3.0, 10.0]) and logs the calibration run for audit traceability.

        Also updates calibration_feature_dim in config to match live_feature_dim,
        clearing the Phase 123 staleness flag when calibration_feature_dim == live_feature_dim.

        Returns 422 if threshold bounds are violated (W1 threshold pollution protection).
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            live_dim = int(getattr(cfg, "live_feature_dim", 13))
            cal_dim  = int(calibration_feature_dim) if calibration_feature_dim is not None else live_dim
            import time as _t125
            row_id = store.insert_l4_threshold_track(
                battery_type=battery_type,
                anomaly_threshold=anomaly_threshold,
                continuity_threshold=continuity_threshold,
                n_sessions=n_sessions,
                calibrated_at=_t125.time(),
                active=True,
            )
            run_id = store.insert_l4_battery_calibration_run(
                battery_type=battery_type,
                anomaly_threshold=anomaly_threshold,
                continuity_threshold=continuity_threshold,
                n_sessions=n_sessions,
                calibration_feature_dim=cal_dim,
                notes=notes,
            )
            # Update calibration_feature_dim in config to clear staleness flag
            object.__setattr__(cfg, "calibration_feature_dim", cal_dim)
            stale = int(getattr(cfg, "live_feature_dim", 13)) != cal_dim
            return {
                "track_id":               row_id,
                "run_id":                 run_id,
                "battery_type":           battery_type,
                "anomaly_threshold":      round(anomaly_threshold, 4),
                "continuity_threshold":   round(continuity_threshold, 4),
                "n_sessions":             n_sessions,
                "calibration_feature_dim": cal_dim,
                "stale":                  stale,
                "timestamp":              _t125.time(),
            }
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 126: L4 Threshold Router Status ---

    @app.get("/agent/l4-router-status")
    def l4_router_status(api_key: str = Query(...)):
        """Phase 126 — L4 per-battery threshold router status.

        Returns lookup statistics from l4_threshold_router_log.
        When l4_battery_threshold_enabled=True, the router selects per-battery
        anomaly/continuity thresholds from l4_threshold_tracks for each session;
        falls back to global 7.009/5.367 when no active track matches.

        BehavioralArchaeologist Phase 126 constants: _WARMUP_COEFF=20_000 and
        _BURST_CV_DIVISOR=2.0 are now named constants (previously inline magic numbers).
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t126
        try:
            enabled = bool(getattr(cfg, "l4_battery_threshold_enabled", False))
            logs = store.get_l4_router_log(limit=1000)
            total_lookups = len(logs)
            per_battery_lookups = sum(
                1 for e in logs if e.get("threshold_source") == "per_battery"
            )
            global_fallback_count = total_lookups - per_battery_lookups
            last_battery_type = logs[0]["battery_type"] if logs else ""
            last_source = logs[0]["threshold_source"] if logs else ""
            return {
                "l4_battery_threshold_enabled": enabled,
                "total_lookups":                total_lookups,
                "per_battery_lookups":          per_battery_lookups,
                "global_fallback_count":        global_fallback_count,
                "last_battery_type":            last_battery_type,
                "last_source":                  last_source,
                "timestamp":                    _t126.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 124: L4 Per-Battery Threshold Track Registry ---

    @app.get("/agent/l4-threshold-tracks")
    def l4_threshold_tracks(
        api_key: str = Query(...),
        battery_type: "str | None" = Query(default=None),
        active_only: bool = Query(default=False),
    ):
        """Phase 124 — L4 per-battery threshold track registry.

        Returns registered per-battery L4 threshold pairs. Operators insert tracks
        after running threshold_calibrator.py per battery type against 13-feature corpus
        (Phase 123 recalibration prerequisite). Default thresholds 7.009/5.367 (Phase 57)
        apply globally when no per-battery track is active.

        W1 mitigation: insert_l4_threshold_track enforces bounds [5.0–15.0] anomaly /
        [3.0–10.0] continuity to prevent threshold pollution attacks.
        W2: battery-adaptive VHP confidence score (per-battery bt_strat_ratio × per-battery
        threshold quality) — Phase 125 candidate.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            enabled = bool(getattr(cfg, "l4_battery_threshold_enabled", False))
            tracks = store.get_l4_threshold_tracks(
                battery_type=battery_type, active_only=active_only
            )
            return {
                "l4_battery_threshold_enabled": enabled,
                "track_count":                  len(tracks),
                "active_count":                 sum(1 for t in tracks if t["active"]),
                "battery_types_tracked":        list({t["battery_type"] for t in tracks}),
                "tracks":                       tracks,
                "timestamp":                    time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/agent/l4-threshold-track")
    def insert_l4_threshold_track(
        api_key: str = Query(...),
        battery_type: str = Query(...),
        anomaly_threshold: float = Query(...),
        continuity_threshold: float = Query(...),
        n_sessions: int = Query(default=0),
        calibrated_at: float = Query(default=0.0),
    ):
        """Phase 124 — Insert a per-battery L4 threshold track.

        Bounds enforced: anomaly [5.0, 15.0]; continuity [3.0, 10.0].
        Returns 422 if bounds violated (W1 threshold pollution protection).
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            row_id = store.insert_l4_threshold_track(
                battery_type=battery_type,
                anomaly_threshold=anomaly_threshold,
                continuity_threshold=continuity_threshold,
                n_sessions=n_sessions,
                calibrated_at=calibrated_at,
            )
            return {
                "id":                   row_id,
                "battery_type":         battery_type,
                "anomaly_threshold":    round(anomaly_threshold, 4),
                "continuity_threshold": round(continuity_threshold, 4),
                "n_sessions":           n_sessions,
                "timestamp":            time.time(),
            }
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 123: L4 Calibration Staleness Monitor ---

    @app.get("/agent/l4-calibration-status")
    def l4_calibration_status(api_key: str = Query(...)):
        """Phase 123 — L4 Mahalanobis threshold calibration staleness monitor.

        Reports whether the L4 thresholds (anomaly=7.009, continuity=5.367, Phase 57)
        were calibrated on the same feature dimension as the live bridge uses.
        Phase 57: calibration_feature_dim=12, N=74.
        Phase 121: live_feature_dim=13 (_BIO_FEATURE_DIM expanded +touchpad_spatial_entropy).
        stale=True when live_feature_dim != calibration_feature_dim.

        W1 (Phase 123): Thresholds calibrated on 12-feature space are technically stale
        against a 13-feature live system. Impact is bounded: index 12 is zero-variance
        in hw_* sessions (auto-excluded from Mahalanobis), but touchpad-active sessions
        will show drift once touchpad calibration sessions are collected.

        Recalibration path: python scripts/threshold_calibrator.py sessions/*.json
        then update CALIBRATION_FEATURE_DIM=13 + CALIBRATION_N_SESSIONS in env.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            live_dim   = int(getattr(cfg, "live_feature_dim", 13))
            calib_dim  = int(getattr(cfg, "calibration_feature_dim", 12))
            n_sessions = int(getattr(cfg, "calibration_n_sessions", 74))
            calib_ts   = float(getattr(cfg, "calibration_timestamp", 0.0))
            anomaly    = float(getattr(cfg, "l4_anomaly_threshold", 7.009))
            continuity = float(getattr(cfg, "l4_continuity_threshold", 5.367))
            stale      = live_dim != calib_dim
            return {
                "current_feature_dim":    live_dim,
                "calibration_feature_dim": calib_dim,
                "stale":                  stale,
                "anomaly_threshold":      round(anomaly, 4),
                "continuity_threshold":   round(continuity, 4),
                "calibration_n_sessions": n_sessions,
                "calibration_timestamp":  calib_ts,
                "timestamp":              time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 122: VHP Confidence Score Separation Ratio Multiplier Status ---
    # --- Phase 121: Biometric Inter-Person Separation Ratio Status ---

    @app.get("/agent/separation-ratio-status")
    def separation_ratio_status(api_key: str = Query(...)):
        """Phase 121 — Biometric inter-person separation ratio status.

        Tournament deployment requires ratio > 1.0 (current: ~0.474 pooled).
        Reads separation_ratio_current config field (Phase 108) and most recent
        separation_ratio_snapshots entry. touchpad_spatial_entropy (Phase 121
        feature index 12) improves separation by adding anatomical grip signature.
        L4 threshold recalibration deferred to Phase 122.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            pooled = float(getattr(cfg, "separation_ratio_current", 1.261))
            snapshots = store.get_separation_ratio_status(limit=1)
            bt_strat = snapshots[0].get("bt_strat_ratio", -1.0) if snapshots else -1.0
            tournament_ready = pooled >= 1.0
            return {
                "pooled_ratio":             round(pooled, 4),
                "battery_stratified_ratio": round(bt_strat, 4) if bt_strat >= 0 else -1.0,
                "tournament_blocker":       not tournament_ready,
                "target_ratio":             1.0,
                "gap_to_target":            round(max(0.0, 1.0 - pooled), 4),
                "tournament_ready":         tournament_ready,
                "timestamp":                time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # --- Phase 127: Tournament Pre-Launch Preflight ---

    def _run_preflight_checks() -> dict:
        """Internal helper: evaluate all 8 preflight conditions and return result dict."""
        import json as _json127

        # P0: separation_ratio >= min_separation_ratio (Phase 166: configurable gate, default 0.70)
        sep_ratio = float(getattr(cfg, "separation_ratio_current", 0.0))
        _snap = store.get_separation_ratio_status(limit=1)
        if _snap:
            sep_ratio = float(_snap[0].get("pooled_ratio", sep_ratio))
        _min_sep = float(getattr(cfg, "min_separation_ratio", 0.70))
        separation_ok = sep_ratio >= _min_sep

        # P0: L4 staleness cleared (live_feature_dim == calibration_feature_dim)
        live_dim  = int(getattr(cfg, "live_feature_dim", 13))
        calib_dim = int(getattr(cfg, "calibration_feature_dim", 12))
        l4_ok = (live_dim == calib_dim)

        # P0: gate_passed (chain_length ≥ gate_n is the GIC_N milestone semantic).
        # Phase 239 fix 2026-05-05: GIC_100 is the cumulative achievement preserved
        # in chain_length. consecutive_clean is the leading-streak instantaneous
        # health signal — it can break to 1 after any PCC DISCONNECT despite the
        # chain having already accumulated 100 gold-standard stamps. Use either
        # signal: leading-streak satisfies (live, no recent break) OR cumulative
        # chain has reached the milestone (GIC_N achieved at any point).
        gate_n   = int(getattr(cfg, "validation_gate_n", 100))
        max_div  = float(getattr(cfg, "validation_max_divergence_rate", 1.0))
        gate_s   = store.get_validation_summary(gate_n, max_div)
        chain_length = 0
        try:
            _grind_sid = str(getattr(cfg, "grind_session_id", "") or "")
            if _grind_sid:
                _chain = store.get_grind_chain_status(_grind_sid, cfg=cfg) or {}
                chain_length = int(_chain.get("chain_length", 0))
        except Exception:
            chain_length = 0
        gate_ok  = bool(gate_s.get("gate_passed", False)) or chain_length >= gate_n

        # P0: cert_valid
        cert     = store.get_latest_enforcement_certificate()
        cert_ok  = bool(
            cert is not None
            and cert.get("audit_valid")
            and time.time() <= cert.get("expires_at", 0)
        )

        # P0: audit_valid
        audit    = store.get_activation_audit_summary()
        audit_ok = bool(audit.get("audit_valid", False))

        # P0: biometric_ttl_ok — credential not expired AND renewal chain has ≥1 entry (Phase 196)
        _ttl196     = float(getattr(cfg, "biometric_credential_ttl_days", 90.0))
        _ttl_status = store.get_biometric_credential_age_status(ttl_days=_ttl196)
        _renewal_ch = store.get_biometric_renewal_chain_status()
        _ttl_expired      = bool(_ttl_status.get("ttl_expired", False)) if _ttl_status else False
        _renewal_has_entry = int(_renewal_ch.get("total_renewals", 0)) > 0
        biometric_ttl_ok  = (not _ttl_expired) and _renewal_has_entry

        # P0: all_pairs_p0_ok — every inter-player pair has separation ratio >= 1.0 (Phase 197)
        # Phase 199: all_pairs_gate_enabled=False bypasses per-pair check for prototype mode
        # (known P2/P3 proximity ceiling — touchpad_corners protocol structurally limited).
        _def197 = store.get_separation_defensibility_status()
        _all_pairs_gate = bool(getattr(cfg, "all_pairs_gate_enabled", True))
        if not _all_pairs_gate:
            all_pairs_p0_ok = True  # Prototype mode: per-pair gate disabled
        else:
            all_pairs_p0_ok = bool(_def197.get("all_pairs_above_1", False)) if _def197 else False

        # P0: ait_defensibility_ok — AIT all_pairs_above_1=True AND all players have >=10 sessions (Phase 231)
        # Closes the gap where all_pairs_p0_ok could be True with <10 sessions/player.
        # Reads from ait_session_log (latest row). Fail-closed: False when no AIT data.
        _ait231 = store.get_ait_separation_status()
        if _ait231:
            _ait_all_pairs231 = bool(_ait231.get("all_pairs_above_1", False))
            _ait_npp231      = _ait231.get("n_per_player", {}) or {}
            _ait_all_min231  = bool(_ait_npp231) and all(
                int(v) >= 10 for v in _ait_npp231.values()
            )
            ait_defensibility_ok = _ait_all_pairs231 and _ait_all_min231
        else:
            ait_defensibility_ok = False

        # P1 warnings
        dual_gate_warned    = not bool(getattr(cfg, "dual_primitive_gate_enabled", False))
        epoch_window_warned = not bool(getattr(cfg, "epoch_window_enabled", False))
        ioswarm_warned      = not bool(getattr(cfg, "ioswarm_vhp_mint_enabled", False))

        overall_pass = (
            separation_ok and l4_ok and gate_ok and cert_ok and audit_ok
            and biometric_ttl_ok and all_pairs_p0_ok and ait_defensibility_ok
        )

        conditions = {
            "separation_ratio": sep_ratio,
            "separation_ok": separation_ok,
            "l4_live_dim": live_dim,
            "l4_calib_dim": calib_dim,
            "l4_ok": l4_ok,
            "consecutive_clean": gate_s.get("consecutive_clean", 0),
            "chain_length": chain_length,
            "gate_ok": gate_ok,
            "cert_ok": cert_ok,
            "audit_ok": audit_ok,
            "biometric_ttl_expired": _ttl_expired,
            # CI-debt fix 2026-07-24 (docs/a2a/ci-debt/backlog.md): len(_renewal_ch) counts
            # the status dict's own keys (a roughly-constant shape, ~7), not the actual
            # renewal count. Same class of copy-paste bug as the 2 endpoint fixes elsewhere
            # in this file (PR #18's Copilot review flagged this exact line at the time);
            # this branch's audit of the same file caught the other 2 but missed this one
            # until an independent PR review cross-referenced the prior review comments.
            # total_renewals is the same field _renewal_has_entry already reads at line 338.
            "biometric_renewal_entries": int(_renewal_ch.get("total_renewals", 0)),
            "biometric_ttl_ok": biometric_ttl_ok,
            "all_pairs_p0_ok": all_pairs_p0_ok,
            "ait_defensibility_ok": ait_defensibility_ok,
            "dual_primitive_gate_enabled": not dual_gate_warned,
            "epoch_window_enabled": not epoch_window_warned,
            "ioswarm_vhp_mint_enabled": not ioswarm_warned,
            "overall_pass": overall_pass,
        }
        row_id = store.insert_tournament_preflight_log(
            separation_ok=separation_ok,
            l4_ok=l4_ok,
            gate_ok=gate_ok,
            cert_ok=cert_ok,
            audit_ok=audit_ok,
            dual_gate_warned=dual_gate_warned,
            epoch_window_warned=epoch_window_warned,
            ioswarm_warned=ioswarm_warned,
            overall_pass=overall_pass,
            conditions_json=_json127.dumps(conditions),
            biometric_ttl_ok=biometric_ttl_ok,
            all_pairs_p0_ok=all_pairs_p0_ok,
            ait_defensibility_ok=ait_defensibility_ok,
        )
        return {
            "run_id":               row_id,
            "separation_ok":        separation_ok,
            "l4_ok":                l4_ok,
            "gate_ok":              gate_ok,
            "cert_ok":              cert_ok,
            "audit_ok":             audit_ok,
            "biometric_ttl_ok":     biometric_ttl_ok,
            "all_pairs_p0_ok":      all_pairs_p0_ok,
            "ait_defensibility_ok": ait_defensibility_ok,
            "dual_gate_warned":     dual_gate_warned,
            "epoch_window_warned":  epoch_window_warned,
            "ioswarm_warned":       ioswarm_warned,
            "overall_pass":         overall_pass,
            "conditions":           conditions,
            "timestamp":            time.time(),
        }

    @app.post("/agent/run-tournament-preflight")
    def run_tournament_preflight(api_key: str = Query(...)):
        """Phase 127 — Run tournament pre-launch preflight checks.

        Evaluates 5 P0 conditions (BLOCK activation if failed) and 3 P1 warnings.
        Persists result to tournament_preflight_log for audit trail.
        POST /agent/commit-activation reads the latest preflight to enforce P0 gates.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            return _run_preflight_checks()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/tournament-preflight-status")
    def tournament_preflight_status(api_key: str = Query(...)):
        """Phase 127 — Return latest tournament preflight result.

        Returns the most recent preflight run from tournament_preflight_log.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            logs = store.get_tournament_preflight_status(limit=1)
            if logs:
                import json as _json127b
                latest = logs[0]
                try:
                    cond = _json127b.loads(latest.get("conditions_json", "{}"))
                except Exception:
                    cond = {}
                return {
                    "found":               True,
                    "run_id":              latest["id"],
                    "separation_ok":       latest["separation_ok"],
                    "l4_ok":               latest["l4_ok"],
                    "gate_ok":             latest["gate_ok"],
                    "cert_ok":             latest["cert_ok"],
                    "audit_ok":            latest["audit_ok"],
                    "biometric_ttl_ok":      latest.get("biometric_ttl_ok", True),
                    "all_pairs_p0_ok":       latest.get("all_pairs_p0_ok", False),
                    "ait_defensibility_ok":  latest.get("ait_defensibility_ok", False),
                    "dual_gate_warned":      latest["dual_gate_warned"],
                    "epoch_window_warned": latest["epoch_window_warned"],
                    "ioswarm_warned":      latest["ioswarm_warned"],
                    "overall_pass":        latest["overall_pass"],
                    "conditions":          cond,
                    "created_at":          latest["created_at"],
                    "timestamp":           time.time(),
                }
            return {
                "found": False, "overall_pass": False,
                "separation_ok": False, "l4_ok": False,
                "gate_ok": False, "cert_ok": False, "audit_ok": False,
                "biometric_ttl_ok": True, "all_pairs_p0_ok": False,
                "ait_defensibility_ok": False,
                "timestamp": time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Phase 129 — GET /agent/separation-ratio-breakthrough
    # ------------------------------------------------------------------
    @app.get("/agent/separation-ratio-breakthrough")
    async def get_separation_ratio_breakthrough_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t129
        try:
            rows = store.get_separation_ratio_breakthrough(limit=5)
            if rows:
                latest = rows[0]
                return {
                    "breakthrough_detected": True,
                    "breakthrough_ratio":    float(latest.get("after_ratio", 0.0)),
                    "breakthrough_ts":       float(latest.get("breakthrough_at", 0.0)),
                    "n_players":             int(latest.get("n_players", 0)),
                    "error":                 None,
                    "timestamp":             _t129.time(),
                }
            # CI-debt fix 2026-07-24 (docs/a2a/ci-debt/backlog.md): this branch previously
            # referenced all_rows/gate_addr/last_valid/last_node_count/_t130 -- none of
            # which exist in this function's scope (copy-paste from a different endpoint,
            # apparently Phase 130's swarm-gate status). Every call with no breakthrough
            # rows yet raised NameError, caught below, returned as a 500 -- honest fix is
            # the same 5-key shape the success branch returns, just with "not yet" values,
            # matching this endpoint's own test contract (test_7_endpoint_5_keys).
            return {
                "breakthrough_detected": False,
                "breakthrough_ratio":    0.0,
                "breakthrough_ts":       0.0,
                "n_players":             0,
                "error":                 None,
                "timestamp":             _t129.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 134 — POST /agent/run-l4-recalibration
    # ------------------------------------------------------------------
    @app.post("/agent/run-l4-recalibration")
    async def run_l4_recalibration_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t134a
        try:
            _jobs = store.get_l4_recalibration_jobs(limit=1)
            if _jobs and _jobs[0].get("status") == "running":
                _age = _t134a.time() - _jobs[0].get("started_at", 0.0)
                if _age < 600:
                    raise HTTPException(status_code=409, detail="recalibration_already_running")
            _job_id = store.insert_l4_recalibration_job(started_at=_t134a.time())
            import asyncio as _aio134
            import subprocess as _sp134
            import sys as _sys134
            import os as _os134
            async def _run_bg():
                try:
                    _script = str(repo_root / "scripts" / "recalibrate_l4_pipeline.py")
                    _db = getattr(cfg, "db_path", _os134.path.expanduser("~/.vapi/bridge.db"))
                    _proc = await _aio134.create_subprocess_exec(
                        _sys134.executable, _script, "--db", _db,
                        stdout=_aio134.subprocess.DEVNULL, stderr=_aio134.subprocess.DEVNULL,
                    )
                    try:
                        await _aio134.wait_for(_proc.wait(), timeout=300.0)
                    except _aio134.TimeoutError:
                        # Mythos audit (MEDIUM): wait_for cancels the awaiting
                        # coroutine but leaves the child process running — kill
                        # + reap it so recalibrate_l4_pipeline.py doesn't orphan.
                        _proc.kill()
                        await _proc.wait()
                        raise
                except Exception as _exc:
                    store.update_l4_recalibration_job(
                        job_id=_job_id, status="failed",
                        sessions_processed=0, anomaly_result=0.0, continuity_result=0.0,
                        completed_at=_t134a.time(), error=str(_exc),
                    )
            _aio134.ensure_future(_run_bg())
            return {"job_id": _job_id, "started": True, "timestamp": _t134a.time()}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 134 — GET /agent/l4-recalibration-status
    # ------------------------------------------------------------------
    @app.get("/agent/l4-recalibration-status")
    async def get_l4_recalibration_status_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t134b
        try:
            _jobs = store.get_l4_recalibration_jobs(limit=1)
            _stale = (
                getattr(cfg, "live_feature_dim", 13)
                != getattr(cfg, "calibration_feature_dim", 12)
            )
            if not _jobs:
                return {
                    "in_progress": False,
                    "last_run_ts": 0.0,
                    "sessions_processed": 0,
                    "new_anomaly_threshold": getattr(cfg, "l4_anomaly_threshold", 7.009),
                    "new_continuity_threshold": getattr(cfg, "l4_continuity_threshold", 5.367),
                    "stale": _stale,
                    "timestamp": _t134b.time(),
                }
            _j = _jobs[0]
            return {
                "in_progress": _j.get("status") == "running",
                "last_run_ts": _j.get("completed_at") or _j.get("started_at", 0.0),
                "sessions_processed": _j.get("sessions_processed", 0),
                "new_anomaly_threshold": _j.get("anomaly_result") or getattr(cfg, "l4_anomaly_threshold", 7.009),
                "new_continuity_threshold": _j.get("continuity_result") or getattr(cfg, "l4_continuity_threshold", 5.367),
                "stale": _stale,
                "timestamp": _t134b.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 134 — GET /agent/auto-separation-snapshot-status
    # ------------------------------------------------------------------
    @app.get("/agent/auto-separation-snapshot-status")
    async def get_auto_separation_snapshot_status_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t134c
        try:
            # CI-debt fix 2026-07-24 (docs/a2a/ci-debt/backlog.md): the return statement
            # here previously referenced active_rows/emulator_mode/node_urls_raw/
            # node_timeout_s/registry_rows/last_quorum_ts/_t131 -- none of which exist in
            # this function's scope (copy-paste from a different endpoint, apparently a
            # Phase 131 node/registry/quorum-status one). Every call raised NameError,
            # caught below, returned as a 500. The correctly-computed local variables
            # right above (_enabled/_snaps/_count/_last_ts) were already the right ones,
            # just never used -- wiring them into the response, matching this endpoint's
            # own test contract (test_8_auto_snapshot_status_5_keys).
            _enabled = bool(getattr(cfg, "auto_separation_snapshot_enabled", False))
            _snaps = store.get_separation_ratio_status(limit=10)
            _count = len(_snaps)
            _last_ts = _snaps[0].get("created_at", 0.0) if _snaps else 0.0
            _last_ratio = _snaps[0].get("pooled_ratio", 0.0) if _snaps else 0.0
            return {
                "auto_separation_snapshot_enabled": _enabled,
                "snapshot_count":                   _count,
                "last_snapshot_ts":                 _last_ts,
                "last_snapshot_ratio":              _last_ratio,
                "timestamp":                        _t134c.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 148 — GET /agent/calibration-health
    # ------------------------------------------------------------------
    @app.get("/agent/calibration-health")
    async def get_calibration_health_endpoint(api_key: str = ""):
        check_key(api_key)
        check_rate(api_key)
        import time as _t148
        try:
            rows = store.get_agent_calibration_health(limit=32)
            # Latest result per agent_id
            seen: dict = {}
            for row in rows:
                aid = row.get("agent_id", 0)
                if aid not in seen:
                    seen[aid] = row
            healthy  = sum(1 for r in seen.values() if r.get("result") == "PASS")
            degraded = sum(1 for r in seen.values() if r.get("result") != "PASS")
            failed   = [r.get("agent_name") for r in seen.values() if r.get("result") != "PASS"]
            mcp_enabled = bool(getattr(cfg, "mcp_server_enabled", False))
            return {
                "agent_count":       16,
                "healthy_count":     healthy,
                "degraded_count":    degraded,
                "failed_agents":     failed,
                "latest_tests":      list(seen.values()),
                "mcp_server_enabled": mcp_enabled,
                "timestamp":         _t148.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 150 — GET /agent/separation-defensibility-status
    # ------------------------------------------------------------------
    @app.get("/agent/separation-defensibility-status")
    async def get_separation_defensibility_status_endpoint(
        api_key: str = "",
        session_type: str = "touchpad_corners",
    ):
        """Return latest separation ratio defensibility report (Phase 150, WIF-010 closure).

        defensible=True requires ALL players >= min_n_per_player (default 10) AND
        ratio > 1.0 AND all inter-player pair distances > 1.0.
        Current state: P1=3, P2=4, P3=4 — all below target; defensible=False.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t150
        try:
            _min_n = int(getattr(cfg, "min_touchpad_sessions_per_player", 10))
            _row = store.get_separation_defensibility_status(
                session_type=session_type if session_type else None
            )
            if _row is None:
                _per = store.get_post_erasure_recompute_status()
                return {
                    "defensible":               False,
                    "ratio":                    0.0,
                    "n_per_player":             {},
                    "min_n_per_player":         _min_n,
                    "all_pairs_above_1":        False,
                    "found":                    False,
                    "post_erasure_recomputed_at": _per.get("latest_recompute_ts"),
                    "timestamp":                _t150.time(),
                }
            _per = store.get_post_erasure_recompute_status()
            # Phase 168: include bootstrap CI from latest separation_ratio_snapshot
            _snap_rows = store.get_separation_ratio_status(limit=1)
            _snap = _snap_rows[0] if _snap_rows else {}
            return {
                "defensible":               bool(_row.get("defensible")),
                "ratio":                    float(_row.get("ratio", 0.0)),
                "n_per_player":             _row.get("n_per_player", {}),
                "min_n_per_player":         int(_row.get("min_n_per_player", _min_n)),
                "all_pairs_above_1":        bool(_row.get("all_pairs_above_1")),
                "found":                    True,
                "post_erasure_recomputed_at": _per.get("latest_recompute_ts"),
                "ci_lower":                 float(_snap.get("ci_lower", 0.0)),
                "ci_upper":                 float(_snap.get("ci_upper", 0.0)),
                "n_bootstrap":              int(_snap.get("n_bootstrap", 0)),
                "timestamp":                _t150.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 151 P1 — GET /agent/enrollment-capture-guidance
    # ------------------------------------------------------------------
    @app.get("/agent/enrollment-capture-guidance")
    async def get_enrollment_capture_guidance_endpoint(
        api_key: str = "",
        min_n: int = 10,
    ):
        """Per-player capture guidance: sessions needed per structured probe type (Phase 151 P1).

        Returns a breakdown per probe type (touchpad_corners / touchpad_freeform /
        touchpad_swipes) of how many more sessions each player needs to reach min_n.
        Use this endpoint to plan calibration capture sessions during gameplay.

        overall_ready=True only when ALL players have >= min_n sessions in ALL probe
        types AND ratio > 1.0 for each — the tournament defensibility target.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t151
        try:
            _min_n = int(getattr(cfg, "min_touchpad_sessions_per_player", min_n))
            _guidance = store.get_enrollment_capture_guidance(min_n=_min_n)
            _guidance["timestamp"] = _t151.time()
            return _guidance
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 152 — GET /agent/centroid-velocity-status
    # ------------------------------------------------------------------
    @app.get("/agent/centroid-velocity-status")
    async def get_centroid_velocity_status_endpoint(
        api_key: str = "",
        probe_type: str = "touchpad_corners",
    ):
        """Per-probe biometric fingerprint drift rate (Phase 152).

        Returns: probe_type, velocity (ratio/sec), ratio_prev, ratio_curr,
        dt_seconds, n_snapshots_used, stagnant, velocity_per_day, timestamp.
        stagnant=True when velocity_per_day < 0.001 (plateau threshold).
        Reads from separation_defensibility_log; velocity=0 when < 2 snapshots.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t152
        try:
            _row = store.get_centroid_velocity_status(probe_type=probe_type)
            if _row is None:
                _computed = store.compute_centroid_velocity(probe_type=probe_type)
            else:
                _computed = {
                    "velocity":           float(_row.get("velocity", 0.0)),
                    "ratio_prev":         float(_row.get("ratio_prev", 0.0)),
                    "ratio_curr":         float(_row.get("ratio_curr", 0.0)),
                    "dt_seconds":         float(_row.get("dt_seconds", 0.0)),
                    "n_snapshots_used":   int(_row.get("n_snapshots_used", 0)),
                    "stagnant":           bool(_row.get("stagnant")),
                }
            return {
                "probe_type":         probe_type,
                "velocity":           _computed["velocity"],
                "ratio_prev":         _computed["ratio_prev"],
                "ratio_curr":         _computed["ratio_curr"],
                "dt_seconds":         _computed["dt_seconds"],
                "n_snapshots_used":   _computed["n_snapshots_used"],
                "stagnant":           _computed["stagnant"],
                "velocity_per_day":   _computed["velocity"] * 86400,
                "timestamp":          _t152.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 153 — GET /agent/separation-ratio-registry-status
    # ------------------------------------------------------------------
    @app.get("/agent/separation-ratio-registry-status")
    async def get_separation_ratio_registry_status_endpoint(api_key: str = ""):
        """On-chain separation ratio registry status (Phase 153).

        Returns: separation_ratio_on_chain_enabled, registry_address, commit_hash,
        ratio_millis, n_sessions, n_players, committed (bool), on_chain_tx, timestamp.
        commit_hash = SHA-256(ratio_str + n_sessions + players_sorted + ts_ns).
        Committed=True after chain.record_separation_ratio_on_chain() confirms tx.
        Infrastructure-first: separation_ratio_on_chain_enabled=False default.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t153
        try:
            _row = store.get_separation_ratio_registry_status()
            _enabled = bool(getattr(cfg, "separation_ratio_on_chain_enabled", False))
            _addr = getattr(cfg, "separation_ratio_registry_address", "")
            if _row is None:
                return {
                    "separation_ratio_on_chain_enabled": _enabled,
                    "registry_address": _addr,
                    "commit_hash":  None,
                    "ratio_millis": 0,
                    "n_sessions":   0,
                    "n_players":    0,
                    "committed":    False,
                    "on_chain_tx":  None,
                    "found":        False,
                    "timestamp":    _t153.time(),
                }
            return {
                "separation_ratio_on_chain_enabled": _enabled,
                "registry_address": _addr,
                "commit_hash":  _row.get("commit_hash"),
                "ratio_millis": int(_row.get("ratio_millis", 0)),
                "n_sessions":   int(_row.get("n_sessions", 0)),
                "n_players":    int(_row.get("n_players", 0)),
                "committed":    bool(_row.get("committed")),
                "on_chain_tx":  _row.get("on_chain_tx"),
                "found":        True,
                "timestamp":    _t153.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 154 — GET /agent/capture-stagnation-status
    # ------------------------------------------------------------------
    @app.get("/agent/capture-stagnation-status")
    async def get_capture_stagnation_status_endpoint(
        api_key: str = "",
        probe_type: str = "touchpad_corners",
    ):
        """Probe capture stagnation monitor (Phase 154).

        Returns: probe_type, sessions_in_window, window_days, sessions_per_day,
        stagnant (bool), stagnation_threshold, found (bool), timestamp.
        stagnant=True when sessions_per_day < stagnation_threshold (default 0.5/day).
        Reads separation_defensibility_log entries over rolling window_days window.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t154
        try:
            _threshold = float(getattr(cfg, "capture_stagnation_threshold", 0.5))
            _window = float(getattr(cfg, "capture_stagnation_window_days", 7.0))
            _row = store.get_capture_stagnation_status(probe_type=probe_type)
            if _row is None:
                _computed = store.compute_capture_stagnation(
                    probe_type=probe_type,
                    window_days=_window,
                    threshold=_threshold,
                )
                return {
                    **_computed,
                    "found":     False,
                    "timestamp": _t154.time(),
                }
            return {
                "probe_type":           probe_type,
                "sessions_in_window":   int(_row.get("sessions_in_window", 0)),
                "window_days":          float(_row.get("window_days", _window)),
                "sessions_per_day":     float(_row.get("sessions_per_day", 0.0)),
                "stagnant":             bool(_row.get("stagnant")),
                "stagnation_threshold": float(_row.get("stagnation_threshold", _threshold)),
                "found":                True,
                "timestamp":            _t154.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    @app.get("/agent/separation-ratio-recovery-status")
    async def get_separation_ratio_recovery_status_endpoint(api_key: str = ""):
        """SeparationRatioRecoveryAgent status (Phase 173, agent #23).

        Detects P1 temporal non-stationarity (converging-downward ratio trend).
        trend_velocity: dRatio/dSnapshot — negative = converging downward.
        recovery_action: STABLE | AGE_WEIGHTING | P1_RE_ENROLLMENT | MORE_SESSIONS.

        Returns: separation_recovery_enabled, current_ratio, trend_velocity,
        n_snapshots_used, recovery_needed, recovery_action, recommendation, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t173
        try:
            _enabled173 = bool(getattr(cfg, "separation_recovery_enabled", True))
            _rows173    = store.get_separation_ratio_recovery_status(limit=1)
            _latest173  = _rows173[0] if _rows173 else {}
            return {
                "separation_recovery_enabled": _enabled173,
                "current_ratio":    float(_latest173.get("current_ratio",  0.0)),
                "trend_velocity":   float(_latest173.get("trend_velocity", 0.0)),
                "n_snapshots_used": int(_latest173.get("n_snapshots_used", 0)),
                "recovery_needed":  bool(_latest173.get("recovery_needed", False)),
                "recovery_action":  str(_latest173.get("recovery_action",  "STABLE")),
                "recommendation":   str(_latest173.get("recommendation",   "")),
                "timestamp":        _t173.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    @app.get("/agent/tremor-resting-probe-status")
    async def get_tremor_resting_probe_status(api_key: str = ""):
        """Tremor Resting Probe status (Phase 199 — 199-B).

        Describes the tremor_resting structured probe type: 30-second still-hold session
        that isolates neurological tremor signal from gameplay motion artifacts.

        tremor_peak_hz is the primary inter-player discriminator:
          P1 ~9.37 Hz (essential tremor), P2 ~1.71 Hz, P3 ~2.85 Hz.
        During gameplay, P3's intra-player variance (mean=1.154) contaminates this signal.
        A still resting probe removes that contamination and tightens P3's centroid.

        Returns: probe_type, enabled, capture_instructions, primary_features,
                 suppressed_features, target_duration_s, sessions_needed_per_player,
                 all_pairs_gate_enabled (prototype mode indicator), timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t199
        try:
            _enabled199   = bool(getattr(cfg, "tremor_resting_probe_enabled", False))
            _all_pairs199 = bool(getattr(cfg, "all_pairs_gate_enabled", True))
            return {
                "probe_type": "tremor_resting",
                "enabled":    _enabled199,
                "capture_instructions": (
                    "Hold the DualShock Edge completely still — thumbs resting lightly on "
                    "sticks (no pressure), fingers off triggers, controller flat in both "
                    "palms.  Do not move for 30 seconds.  The bridge will capture raw "
                    "accelerometer data and extract neurological tremor frequency signature."
                ),
                "primary_features":    ["tremor_peak_hz", "tremor_band_power",
                                        "micro_tremor_accel_variance"],
                "suppressed_features": ["stick_autocorr_lag1", "stick_autocorr_lag5",
                                        "grip_asymmetry", "touchpad_spatial_entropy"],
                "target_duration_s":          30,
                "sessions_needed_per_player": 5,
                "all_pairs_gate_enabled":     _all_pairs199,
                "prototype_mode_active":      not _all_pairs199,
                "timestamp":                  _t199.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 199 — GET /agent/probe-gate-config-status
    # ------------------------------------------------------------------
    @app.get("/agent/probe-gate-config-status")
    async def get_probe_gate_config_status(api_key: str = ""):
        """Prototype Separation Gate configuration status (Phase 199 — 199-A).

        separation_ok uses min_separation_ratio (Phase 166 default=0.70):
          ratio=0.728 >= 0.70 → separation_ok=True.
        all_pairs_p0_ok uses all_pairs_gate_enabled (Phase 199):
          True  (production default) → strict per-pair >= 1.0 enforcement
          False (prototype mode)    → gate bypassed; overall_pass driven by separation_ok

        Returns: all_pairs_gate_enabled, min_separation_ratio, prototype_mode_active,
                 separation_ok_threshold, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t199g
        try:
            _all_pairs_g  = bool(getattr(cfg, "all_pairs_gate_enabled", True))
            _min_sep_g    = float(getattr(cfg, "min_separation_ratio", 0.70))
            return {
                "all_pairs_gate_enabled":  _all_pairs_g,
                "min_separation_ratio":    _min_sep_g,
                "prototype_mode_active":   not _all_pairs_g,
                "separation_ok_threshold": _min_sep_g,
                "timestamp":               _t199g.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 202 — GET /agent/tremor-convergence-status
    # ------------------------------------------------------------------
    @app.get("/agent/tremor-convergence-status")
    async def get_tremor_convergence_status_endpoint(api_key: str = ""):
        """TremorRestingConvergenceOracle status (Phase 202).

        Returns the latest tremor_resting separation ratio velocity snapshot.
        Velocity = (ratio_curr - ratio_prev) / N_delta between successive sessions.
        convergence_stable=True when velocity >= 0 for 2 consecutive sessions.
        sessions_to_target_est: linear extrapolation of sessions needed to reach ratio=1.0.

        When convergence_stable=False and consecutive_positive=0, the RATIO_VELOCITY_NEGATIVE
        ORPHAN rule in FleetSignalCoherenceAgent fires, blocking VHP MINT_QUORUM=0.80.

        Returns: tremor_convergence_enabled, convergence_stable, velocity, ratio,
                 consecutive_positive, sessions_to_target_estimate, n_sessions,
                 session_type, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t202
        try:
            _enabled202 = bool(getattr(cfg, "tremor_convergence_enabled", False))
            _status202  = store.get_tremor_convergence_status("tremor_resting")
            return {
                "tremor_convergence_enabled":    _enabled202,
                "convergence_stable":            bool(_status202.get("convergence_stable", 0)) if _status202 else None,
                "velocity":                      float(_status202.get("velocity", 0.0))        if _status202 else None,
                "ratio":                         float(_status202.get("ratio", 0.0))            if _status202 else None,
                "consecutive_positive":          int(_status202.get("consecutive_positive", 0)) if _status202 else 0,
                "sessions_to_target_estimate":   int(_status202.get("sessions_to_target_est", 0)) if _status202 else 0,
                "n_sessions":                    int(_status202.get("n_sessions", 0))           if _status202 else 0,
                "session_type":                  str(_status202.get("session_type", "tremor_resting")) if _status202 else "tremor_resting",
                # Phase 206: non-convergence detection
                "non_convergence_detected":      bool(_status202.get("non_convergence_detected", False)) if _status202 else False,
                "consecutive_negative":          int(_status202.get("consecutive_negative", 0))  if _status202 else 0,
                "timestamp":                     _t202.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Phase 205 — GET /agent/accel-tremor-fft-status
    # ------------------------------------------------------------------
    @app.get("/agent/accel-tremor-fft-status")
    async def get_accel_tremor_fft_status(x_api_key: str = Header(default="")):
        """AccelTremorFFT fallback status (Phase 205).

        Reports whether the accel magnitude FFT fallback for tremor_peak_hz is
        enabled and the still-hold detection threshold.  When enabled, still-hold
        sessions (tremor_seed probe type) compute tremor_peak_hz from the IMU
        accelerometer ring (1-15 Hz search range) instead of the right_stick_x
        velocity FFT (which returns 0 at neutral=128 during still-hold).

        Returns 5 keys:
          accel_tremor_fallback_enabled / still_hold_var_threshold /
          fallback_source / tremor_search_range_hz / timestamp
        """
        check_read_key(x_api_key)
        import time as _t205
        _enabled205 = bool(getattr(cfg, "accel_tremor_fallback_enabled", True))
        _nfft213    = int(getattr(cfg, "accel_fft_nfft", 4096))
        _bin_hz     = round(1000.0 / _nfft213, 4)  # at 1000 Hz nominal sampling rate
        return {
            "accel_tremor_fallback_enabled": _enabled205,
            "still_hold_var_threshold":      4.0,
            "fallback_source":               "accel_magnitude_fft" if _enabled205 else "stick_fft_only",
            "tremor_search_range_hz":        [1.0, 15.0],
            "accel_fft_nfft":                _nfft213,
            "bin_width_hz":                  _bin_hz,
            "timestamp":                     _t205.time(),
        }

    # ------------------------------------------------------------------
    # Phase 207 — GET /agent/dry-run-graduation-status
    # ------------------------------------------------------------------
    @app.get("/agent/dry-run-graduation-status")
    async def get_dry_run_graduation_status(x_api_key: str = Header(default="")):
        """StagedDryRunGraduationGate status (Phase 207).

        Reports the current state of all graduation stages and overall gate config.
        staged_graduation_enabled=False means all agents remain in dry_run=True;
        the endpoint is read-only and always available for monitoring.

        Returns 6 keys:
          staged_graduation_enabled / rollback_window_sessions / fp_threshold /
          stages / active_stage_count / timestamp
        """
        check_read_key(x_api_key)
        import time as _t207
        _enabled207   = bool(getattr(cfg, "staged_graduation_enabled", False))
        _window207    = int(getattr(cfg, "graduation_rollback_window_sessions", 10))
        _fp_thresh207 = int(getattr(cfg, "graduation_fp_threshold", 2))
        _stages207: list = []
        try:
            _stages207 = store.get_all_graduation_stages()
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
        _active207 = sum(1 for s in _stages207 if not s.get("rollback_triggered"))
        return {
            "staged_graduation_enabled":  _enabled207,
            "rollback_window_sessions":   _window207,
            "fp_threshold":               _fp_thresh207,
            "stages":                     _stages207,
            "active_stage_count":         _active207,
            "timestamp":                  _t207.time(),
        }

    # ------------------------------------------------------------------
    # Phase 207 — POST /agent/activate-graduation-stage
    # ------------------------------------------------------------------
    @app.post("/agent/activate-graduation-stage")
    async def activate_graduation_stage(
        request: Request,
        x_api_key: str = Header(default=""),
    ):
        """Activate a dry-run graduation stage for a specific agent (Phase 207).

        P0 preconditions (fail-closed):
          - staged_graduation_enabled=True
          - tournament_preflight overall_pass=True
          - non_convergence_detected=False

        Request body (JSON):
          - agent_id: str  (required)
          - notes:    str  (optional)

        Returns activation result with precondition breakdown.
        HTTP 422 if preconditions not met or agent_id missing.
        """
        import time as _t207p
        # P0 fail-fast: check enabled flag before key auth (no state change, safe)
        if not bool(getattr(cfg, "staged_graduation_enabled", False)):
            raise HTTPException(
                status_code=422,
                detail=(
                    "staged_graduation_enabled=False — set STAGED_GRADUATION_ENABLED=true "
                    "and ensure tournament_preflight overall_pass=True before activating."
                ),
            )
        check_read_key(x_api_key)
        _body207 = {}
        try:
            _body207 = await request.json()
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
        _agent_id207 = str(_body207.get("agent_id", "")).strip()
        if not _agent_id207:
            raise HTTPException(status_code=422, detail="agent_id required")

        from ..staged_dry_run_graduation_agent import StagedDryRunGraduationAgent as _SDRGA
        _graduation_agent207 = _SDRGA(cfg=cfg, store=store, bus=None)
        _result207 = _graduation_agent207.activate_stage(
            agent_id=_agent_id207,
            notes=str(_body207.get("notes", "")),
        )
        if not _result207.get("activated"):
            raise HTTPException(
                status_code=422,
                detail=_result207.get("error", "activation_failed"),
            )
        return {
            "activated":       _result207["activated"],
            "row_id":          _result207.get("row_id"),
            "stage_number":    _result207.get("stage_number"),
            "agent_id":        _agent_id207,
            "preconditions":   _result207.get("preconditions", {}),
            "timestamp":       _t207p.time(),
        }

    # ------------------------------------------------------------------
    # Phase 214 — GET /agent/graduation-autowatch-status
    # ------------------------------------------------------------------
    @app.get("/agent/graduation-autowatch-status")
    async def get_graduation_autowatch_status(
        probe_type: str = "",
        x_api_key: str = Header(default=""),
    ):
        """GraduationAutowatchBridge status (Phase 214 — WIF-041 mitigation).

        Reports whether the graduation autowatch is enabled and the history of
        all_pairs_p0_ok transition events observed by SeparationRatioMonitorAgent.
        When a trigger_fired entry exists, StagedDryRunGraduationAgent has been
        notified to evaluate graduation preconditions automatically.

        Returns 6 keys:
          graduation_autowatch_enabled / trigger_count / evaluated_count /
          last_trigger_probe_type / last_preconditions_met / timestamp
        """
        check_read_key(x_api_key)
        import time as _t214
        _enabled214 = bool(getattr(cfg, "graduation_autowatch_enabled", True))
        _status214: dict = {
            "total_entries": 0,
            "trigger_count": 0,
            "evaluated_count": 0,
            "last_trigger_ratio": None,
            "last_trigger_probe_type": None,
            "last_preconditions_met": None,
            "last_blockers": [],
            "entries": [],
            "timestamp": _t214.time(),
        }
        try:
            _status214 = store.get_graduation_autowatch_status(
                probe_type=probe_type or None,
                limit=10,
            )
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
        return {
            "graduation_autowatch_enabled": _enabled214,
            "trigger_count":               _status214.get("trigger_count", 0),
            "evaluated_count":             _status214.get("evaluated_count", 0),
            "last_trigger_probe_type":     _status214.get("last_trigger_probe_type"),
            "last_preconditions_met":      _status214.get("last_preconditions_met"),
            "timestamp":                   _status214.get("timestamp", _t214.time()),
        }

    # ------------------------------------------------------------------
    # Phase 208 — GET /agent/corpus-regression-guard-status
    # ------------------------------------------------------------------
    @app.get("/agent/corpus-regression-guard-status")
    async def get_corpus_regression_guard_status(
        probe_type: str = "",
        x_api_key: str = Header(default=""),
    ):
        """CorpusRatioRegressionGuard status (Phase 208 — WIF-039 W1+W2).

        Reports whether the corpus ratio regression guard is enabled and whether a
        prior separation ratio breakthrough (all_pairs_above_1=True) has been recorded
        for the requested probe type.  When guard_active=True, any future corpus insert
        with all_pairs_above_1=False will raise CorpusRegressionError unless an override
        is registered first.

        Query param:
          probe_type: str (optional) — filter by probe type; omit for global latest

        Returns 7 keys:
          corpus_ratio_regression_guard_enabled / guard_active / breakthrough_ratio /
          breakthrough_n / provenance_hash / override_count / timestamp
        """
        check_read_key(x_api_key)
        import time as _t208
        _guard_enabled208 = bool(getattr(cfg, "corpus_ratio_regression_guard_enabled", False))
        try:
            _status208 = store.get_corpus_regression_guard_status(
                probe_type=probe_type if probe_type else None
            )
        except Exception as _e208:
            _status208 = {
                "guard_active":      False,
                "breakthrough_ratio": None,
                "breakthrough_n":    None,
                "provenance_hash":   None,
                "override_count":    0,
                "probe_type":        probe_type or None,
                "timestamp":         _t208.time(),
            }
        return {
            "corpus_ratio_regression_guard_enabled": _guard_enabled208,
            "guard_active":      _status208.get("guard_active", False),
            "breakthrough_ratio": _status208.get("breakthrough_ratio"),
            "breakthrough_n":    _status208.get("breakthrough_n"),
            "provenance_hash":   _status208.get("provenance_hash"),
            "override_count":    _status208.get("override_count", 0),
            "timestamp":         _t208.time(),
        }

    # ------------------------------------------------------------------
    # Phase 215 — GET /agent/l4-dim-sync-status
    # ------------------------------------------------------------------
    @app.get("/agent/l4-dim-sync-status")
    async def get_l4_dim_sync_status(
        x_api_key: str = Header(default=""),
    ):
        """L4 calibration dimension sync status (Phase 215 — G-003 closure).

        Reports whether the L4 threshold dimension sync has been completed,
        confirming that the existing thresholds (anomaly=7.009, continuity=5.367)
        calibrated at dim=12 remain valid for the live 13-feature space.
        Feature 12 (touchpad_spatial_entropy) is structurally zero in gameplay
        sessions (NCAA CFB 26), so no recalibration is required.

        Returns 7 keys:
          l4_dim_sync_enabled / sync_completed / from_dim / to_dim /
          anomaly_threshold / continuity_threshold / timestamp
        """
        check_read_key(x_api_key)
        import time as _t215
        _enabled215 = bool(getattr(cfg, "l4_dim_sync_enabled", True))
        try:
            _status215 = store.get_l4_dim_sync_status()
        except Exception:
            _status215 = {
                "sync_completed":        False,
                "from_dim":              None,
                "to_dim":                None,
                "anomaly_threshold":     None,
                "continuity_threshold":  None,
                "timestamp":             _t215.time(),
            }
        return {
            "l4_dim_sync_enabled":   _enabled215,
            "sync_completed":        _status215.get("sync_completed", False),
            "from_dim":              _status215.get("from_dim"),
            "to_dim":                _status215.get("to_dim"),
            "anomaly_threshold":     _status215.get("anomaly_threshold"),
            "continuity_threshold":  _status215.get("continuity_threshold"),
            "timestamp":             _t215.time(),
        }

    # Phase 220 — GET /agent/per-pair-gap-projection
    # ------------------------------------------------------------------
    @app.get("/agent/per-pair-gap-projection")
    async def get_per_pair_gap_projection(
        x_api_key: str = Header(default=""),
        session_type: str = "",
        n_runs: int = 5,
    ):
        """Per-pair gap TGE timeline projection (Phase 220).

        For each blocker pair, projects days until distance reaches 1.0 using
        current velocity. WORSENING/STABLE pairs return projection_feasible=False.

        Returns 7 keys: per_pair_gap_projection_enabled / projections /
                        any_feasible / max_days_to_1_0 / projected_tge_date /
                        session_type / timestamp
        """
        check_read_key(x_api_key)
        import time as _t220
        _enabled220 = bool(getattr(cfg, "per_pair_gap_projection_enabled", True))
        _st220 = session_type.strip() or None
        try:
            _proj220 = store.get_per_pair_gap_projection(
                session_type=_st220, n_runs=int(n_runs)
            )
        except Exception:
            _proj220 = {
                "projections": [], "any_feasible": False,
                "max_days_to_1_0": None, "projected_tge_date": None,
                "session_type": _st220, "timestamp": _t220.time(),
            }
        return {
            "per_pair_gap_projection_enabled": _enabled220,
            "projections":       _proj220.get("projections", []),
            "any_feasible":      _proj220.get("any_feasible", False),
            "max_days_to_1_0":   _proj220.get("max_days_to_1_0"),
            "projected_tge_date": _proj220.get("projected_tge_date"),
            "session_type":      _proj220.get("session_type"),
            "timestamp":         _t220.time(),
        }

    # ------------------------------------------------------------------
    # Phase 219 — GET /agent/tournament-blocker-summary
    # ------------------------------------------------------------------
    @app.get("/agent/tournament-blocker-summary")
    async def get_tournament_blocker_summary(
        x_api_key: str = Header(default=""),
    ):
        """Aggregated TGE blocker summary (Phase 219).

        Queries tournament_preflight_log, per_pair_gap_log, and capture velocity
        to produce a single list of all active blockers with source/severity.

        Returns 8 keys: tournament_blocker_summary_enabled / total_blockers / blockers /
                        overall_blocked / preflight_pass / capture_healthy /
                        all_pairs_above_1 / timestamp
        """
        check_read_key(x_api_key)
        import time as _t219
        _enabled219 = bool(getattr(cfg, "tournament_blocker_summary_enabled", True))
        try:
            _summary219 = store.get_tournament_blocker_summary()
        except Exception:
            _summary219 = {
                "total_blockers": 1,
                "blockers": [{"source": "error", "key": "internal", "detail": "Summary unavailable", "severity": "P0"}],
                "overall_blocked": True,
                "preflight_pass": False,
                "capture_healthy": False,
                "all_pairs_above_1": False,
                "timestamp": _t219.time(),
            }
        return {
            "tournament_blocker_summary_enabled": _enabled219,
            "total_blockers":   _summary219.get("total_blockers", 0),
            "blockers":         _summary219.get("blockers", []),
            "overall_blocked":  _summary219.get("overall_blocked", True),
            "preflight_pass":   _summary219.get("preflight_pass", False),
            "capture_healthy":  _summary219.get("capture_healthy", False),
            "all_pairs_above_1": _summary219.get("all_pairs_above_1", False),
            "timestamp":        _t219.time(),
        }

    # ------------------------------------------------------------------
    # Phase 218 — GET /agent/capture-velocity-oracle
    # ------------------------------------------------------------------
    @app.get("/agent/capture-velocity-oracle")
    async def get_capture_velocity_oracle(
        x_api_key: str = Header(default=""),
        probe_type: str = "touchpad_corners",
    ):
        """Unified capture velocity oracle (Phase 218).

        Synthesizes Phase 152 centroid velocity + Phase 154 capture stagnation
        into a single response with recommended_action.

        Returns 9 keys: capture_velocity_oracle_enabled / probe_type / sessions_per_day /
                        sessions_stagnant / ratio_velocity / velocity_stagnant /
                        overall_capture_healthy / recommended_action / timestamp
        """
        check_read_key(x_api_key)
        import time as _t218
        _enabled218 = bool(getattr(cfg, "capture_velocity_oracle_enabled", True))
        _pt218 = probe_type.strip() or "touchpad_corners"
        try:
            _oracle218 = store.get_capture_velocity_oracle_status(probe_type=_pt218)
        except Exception:
            _oracle218 = {
                "probe_type": _pt218,
                "sessions_per_day": 0.0,
                "sessions_stagnant": True,
                "ratio_velocity": 0.0,
                "velocity_stagnant": True,
                "overall_capture_healthy": False,
                "recommended_action": "ERROR",
                "timestamp": _t218.time(),
            }
        return {
            "capture_velocity_oracle_enabled": _enabled218,
            "probe_type":                      _oracle218.get("probe_type", _pt218),
            "sessions_per_day":                _oracle218.get("sessions_per_day", 0.0),
            "sessions_stagnant":               _oracle218.get("sessions_stagnant", True),
            "ratio_velocity":                  _oracle218.get("ratio_velocity", 0.0),
            "velocity_stagnant":               _oracle218.get("velocity_stagnant", True),
            "overall_capture_healthy":         _oracle218.get("overall_capture_healthy", False),
            "recommended_action":              _oracle218.get("recommended_action", "UNKNOWN"),
            "timestamp":                       _t218.time(),
        }

    # ------------------------------------------------------------------
    # Phase 217 — GET /agent/per-pair-gap-trend
    # ------------------------------------------------------------------
    @app.get("/agent/per-pair-gap-trend")
    async def get_per_pair_gap_trend(
        x_api_key: str = Header(default=""),
        pair_key: str = "",
        session_type: str = "",
        n_runs: int = 5,
    ):
        """Per-pair Mahalanobis gap trend velocity (Phase 217).

        Returns distance velocity (delta per day) for the requested pair_key over
        the last n_runs analysis runs.  trend is IMPROVING/WORSENING/STABLE/UNKNOWN.

        Returns 8 keys: per_pair_gap_trend_enabled / pair_key / distances /
                        velocity_per_day / trend / n_runs / blocker_resolved / timestamp
        """
        check_read_key(x_api_key)
        import time as _t217
        _enabled217 = bool(getattr(cfg, "per_pair_gap_trend_enabled", True))
        _pk217 = pair_key.strip() or "P1vP3"
        _st217 = session_type.strip() or None
        try:
            _trend217 = store.get_per_pair_gap_trend(
                pair_key=_pk217, session_type=_st217, n_runs=int(n_runs)
            )
        except Exception:
            _trend217 = {
                "pair_key": _pk217, "session_type": _st217, "distances": [],
                "analysis_dates": [], "velocity_per_day": None,
                "trend": "UNKNOWN", "n_runs": 0, "timestamp": _t217.time(),
            }
        # blocker_resolved=True only if the most recent distance is >= 1.0
        _dists217 = _trend217.get("distances", [])
        _blocker_resolved = bool(_dists217 and _dists217[0] >= 1.0)
        return {
            "per_pair_gap_trend_enabled": _enabled217,
            "pair_key":                  _trend217.get("pair_key", _pk217),
            "distances":                 _dists217,
            "velocity_per_day":          _trend217.get("velocity_per_day"),
            "trend":                     _trend217.get("trend", "UNKNOWN"),
            "n_runs":                    _trend217.get("n_runs", 0),
            "blocker_resolved":          _blocker_resolved,
            "timestamp":                 _t217.time(),
        }

    # ------------------------------------------------------------------
    # Phase 216 — GET /agent/per-pair-gap-status
    # ------------------------------------------------------------------
    @app.get("/agent/per-pair-gap-status")
    async def get_per_pair_gap_status(
        x_api_key: str = Header(default=""),
        session_type: str = "",
    ):
        """Per-pair Mahalanobis inter-player distance log status (Phase 216).

        Returns per-pair distances from the most recent analysis run, including
        which pairs are above 1.0 and which are the tournament blockers.
        Returns 7 keys: per_pair_gap_log_enabled / all_pairs_above_1 / pairs /
                        session_type / pair_count / blocker_pairs / timestamp
        """
        check_read_key(x_api_key)
        import time as _t216
        _enabled216 = bool(getattr(cfg, "per_pair_gap_log_enabled", True))
        _stype216 = session_type.strip() or None
        try:
            _status216 = store.get_per_pair_gap_status(session_type=_stype216)
        except Exception:
            _status216 = {
                "all_pairs_above_1": False,
                "pairs": [],
                "session_type": _stype216,
                "pair_count": 0,
                "timestamp": _t216.time(),
            }
        _pairs216 = _status216.get("pairs", [])
        _blockers216 = [p for p in _pairs216 if not p.get("above_1_0", True)]
        return {
            "per_pair_gap_log_enabled": _enabled216,
            "all_pairs_above_1":        _status216.get("all_pairs_above_1", False),
            "pairs":                    _pairs216,
            "session_type":             _status216.get("session_type"),
            "pair_count":               _status216.get("pair_count", 0),
            "blocker_pairs":            _blockers216,
            "timestamp":                _t216.time(),
        }

    # Phase 229 — GET /agent/ait-separation-status
    # ------------------------------------------------------------------
    @app.get("/agent/ait-separation-status")
    async def get_ait_separation_status(
        x_api_key: str = Header(default=""),
    ):
        """AIT (Active Isometric Trigger) separation status (Phase 229).

        Returns the latest AIT separation analysis from ait_session_log.
        Populated by:
          - python scripts/analyze_interperson_separation.py --session-type ait
            --write-snapshot
          - POST /agent/run-ait-analysis

        Returns (11 keys): ait_separation_enabled, n_sessions, separation_ratio,
        all_pairs_above_1, inter_player_mean, intra_player_mean, loo_accuracy,
        pair_distances, analysis_date, last_run_ts, timestamp.

        separation_ratio >= 1.199 (N=24, 2026-04-18) — Phase 229 breakthrough result:
        all inter-player distances > 1.0 for the first time across all probe types.
        """
        check_read_key(x_api_key)
        import time as _t229
        try:
            _enabled229 = bool(getattr(cfg, "ait_separation_enabled", True))
            _status229  = store.get_ait_separation_status()
            _status229["ait_separation_enabled"] = _enabled229
            return _status229
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc


