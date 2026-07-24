"""Grind / GIC / WEC / corpus snapshot routes (D-DECON-2 operator_api residue #19).

Register-function split per audits/decon-store-map.md agent_grind domain.
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import time
from typing import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from ..agent_auth import AgentIdentity

log = logging.getLogger(__name__)


def register_agent_grind_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    chain,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
    check_read_key: Callable[[str], None],
    check_agent_token,
) -> None:
    """Register grind pipeline, capture health, snapshot anchor, and agent-commit read routes."""


    # Phase 234.7 — GET /bridge/capture-health
    # ------------------------------------------------------------------
    @app.get("/bridge/capture-health")
    async def get_capture_health(
        x_api_key: str = Header(default=""),
    ):
        """Physical Capture Continuity status (Phase 234.7).

        Returns real-time HID poll rate, controller host arbitration state,
        and grind-mode readiness gate.  Updated each _session_loop iteration
        (~1 Hz).

        Returns (11 keys): pcc_enabled, capture_state, host_state, poll_rate_hz,
        sustained_duration_s, grind_mode, grind_ready, grind_target,
        consecutive_clean_toward_target, session_counting_paused, timestamp.

        capture_state: NOMINAL (>=950 Hz) | DEGRADED | DISCONNECTED
        host_state:    EXCLUSIVE_USB | EXCLUSIVE_BT | CONTESTED | UNKNOWN
        grind_ready:   True only when NOMINAL + EXCLUSIVE_USB + 30s sustained
        session_counting_paused: grind_mode=True AND grind_ready=False
        """
        check_read_key(x_api_key)
        import time as _t2347
        _pcc_enabled = bool(getattr(cfg, "pcc_enabled", True))
        _grind_mode  = bool(getattr(cfg, "grind_mode", False))
        _grind_target = int(getattr(cfg, "grind_target", 100))

        # Live monitor status (if monitor is wired via pcc_monitor kwarg at startup)
        _monitor = getattr(app, "_pcc_monitor", None)
        if _monitor is not None:
            _live = _monitor.get_status()
            _capture_state = _live["capture_state"]
            _host_state    = _live["host_state"]
            _poll_rate_hz  = _live["poll_rate_hz"]
            _sustained     = _live["sustained_duration_s"]
            _grind_ready   = _live["grind_ready"]
            # Phase 235-BRIDGE-WEDGE-FIX: flush transitions to store on a worker
            # thread.  Each insert is a SQLite write — running them on the event
            # loop made every capture-health poll wait on WAL contention.
            _transitions = _monitor.pop_transitions()
            if _transitions:
                def _flush_transitions(rows):
                    for r in rows:
                        try:
                            store.insert_capture_health_event(
                                capture_state=r["new_state"],
                                host_state=r["host_state"],
                                poll_rate_hz=r["poll_rate_hz"],
                                transition_reason=r["reason"],
                                grind_mode=_grind_mode,
                            )
                        except Exception:
                            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
                await asyncio.to_thread(_flush_transitions, _transitions)
        else:
            # Fallback: read last DB entry (controller not connected or monitor not wired)
            # Phase 235-BRIDGE-WEDGE-FIX: SQLite read off the event loop.
            _db_status = await asyncio.to_thread(store.get_capture_health_status)
            _capture_state = _db_status.get("capture_state", "DISCONNECTED")
            _host_state    = _db_status.get("host_state", "UNKNOWN")
            _poll_rate_hz  = float(_db_status.get("poll_rate_hz", 0.0))
            _sustained     = 0.0
            _grind_ready   = False

        # Grind progress from validation summary
        # Phase 235-BRIDGE-WEDGE-FIX: get_validation_summary scans
        # ruling_validation_log; py-spy caught it blocking the event loop here
        # at store.py:5480 inside _conn().
        _val_summary: dict = {}
        try:
            from ..active_play_occupancy import normalize_active_play_gate_mode
            _apop_mode = normalize_active_play_gate_mode(
                getattr(cfg, "active_play_occupancy_gate_mode", "shadow")
            ) if bool(getattr(cfg, "active_play_occupancy_enabled", True)) else "shadow"
            _val_summary = await asyncio.to_thread(
                store.get_validation_summary, _grind_target, 1.0, _apop_mode
            )
            _consec_clean = int(_val_summary.get("consecutive_clean", 0))
        except Exception:
            _consec_clean = 0

        _session_counting_paused = _grind_mode and not _grind_ready

        _gameplay_disc_enabled = bool(getattr(cfg, "gameplay_discrimination_enabled", True))
        _latest_gameplay_ctx = _val_summary.get("latest_gameplay_context")

        # ATTEST-FEEDS (F-RIG27-1/2, first CFB 27 rig): honest rate-source visibility + a LIVE
        # bridge-attested activity fraction (same main reader that mints records; no adjudicator
        # dependency). Fields come ONLY from the live transport — absent transport -> honest
        # defaults (stalled False / sources None / fraction None) so nothing reads as attestation.
        _transport_af = getattr(app, "_transport", None)
        _rate_stalled = bool(getattr(_transport_af, "_rate_counter_stalled", False))
        _rate_source = getattr(_transport_af, "_rate_source", None) if _transport_af else None
        _hid_restarts = int(getattr(_transport_af, "_hid_counter_restarts", 0) or 0)
        _law = getattr(_transport_af, "_live_activity_window", None) if _transport_af else None
        if _law is not None and len(_law) > 0:
            _live_fraction = sum(_law) / len(_law)
            _live_n = len(_law)
            _live_src = "bridge_main_reader"
        else:
            _live_fraction = None
            _live_n = 0
            _live_src = None

        return {
            "pcc_enabled":                   _pcc_enabled,
            "capture_state":                 _capture_state,
            "host_state":                    _host_state,
            "poll_rate_hz":                  _poll_rate_hz,
            "rate_counter_stalled":          _rate_stalled,
            "rate_source":                   _rate_source,
            "hid_counter_restarts":          _hid_restarts,
            "live_trigger_active_fraction":  _live_fraction,
            "live_activity_window_n":        _live_n,
            "live_activity_source":          _live_src,
            "sustained_duration_s":          _sustained,
            "grind_mode":                    _grind_mode,
            "grind_ready":                   _grind_ready,
            "grind_target":                  _grind_target,
            "consecutive_clean_toward_target": _consec_clean,
            "session_counting_paused":       _session_counting_paused,
            "gameplay_context_enabled":      _gameplay_disc_enabled,
            "latest_gameplay_context":       _latest_gameplay_ctx,
            "timestamp":                     _t2347.time(),
        }
    # Phase O5-MLGA Stage 3 — GET /agent/mlga-live-session-status
    # ------------------------------------------------------------------
    @app.get("/agent/mlga-live-session-status")
    async def get_mlga_live_session_status(
        x_api_key: str = Header(default=""),
    ):
        """Current MLGA session tracker state. Reports whether a session
        is open, running totals (poac records / R2 / L2 / GIC advances /
        APOP state distribution), session duration, total sessions
        persisted lifetime. Operator dashboard surface.

        Returns:
          enabled: bool
          has_open_session: bool
          session_id: str (if open)
          session_open_ts_ns / session_duration_s (if open)
          n_poac_records / n_trigger_pulls_r2 / n_trigger_pulls_l2
          gic_advances_in_session
          apop_state_counts: dict
          bt_observability: int (0/1/2)
          sessions_persisted_total: int
          last_close_ts_ns / last_close_reason
          timestamp: float

        Returns empty/disabled shape if cfg.mlga_session_tracker_enabled=False
        or tracker not yet wired (bridge starting up).
        """
        check_read_key(x_api_key)
        import time as _t_mlga
        _tracker = getattr(app, "_mlga_tracker", None)
        if _tracker is None:
            return {
                "enabled":              bool(
                    getattr(cfg, "mlga_session_tracker_enabled", False)
                ),
                "has_open_session":     False,
                "tracker_wired":        False,
                "sessions_persisted_total": 0,
                "timestamp":            _t_mlga.time(),
            }
        try:
            status = _tracker.live_status()
        except Exception as exc:  # noqa: BLE001
            return {
                "enabled":              True,
                "has_open_session":     False,
                "tracker_wired":        True,
                "error":                f"{type(exc).__name__}: {exc}",
                "timestamp":            _t_mlga.time(),
            }
        # MLGASessionLiveStatus is a slotted dataclass — serialize to dict
        return {
            "enabled":                  status.enabled,
            "has_open_session":         status.has_open_session,
            "tracker_wired":            True,
            "session_id":               status.session_id,
            "session_open_ts_ns":       status.session_open_ts_ns,
            "session_duration_s":       status.session_duration_s,
            "n_poac_records":           status.n_poac_records,
            "n_trigger_pulls_r2":       status.n_trigger_pulls_r2,
            "n_trigger_pulls_l2":       status.n_trigger_pulls_l2,
            "gic_advances_in_session":  status.gic_advances_in_session,
            "apop_state_counts":        dict(status.apop_state_counts),
            "bt_observability":         status.bt_observability,
            "sessions_persisted_total": status.sessions_persisted_total,
            "last_close_ts_ns":         status.last_close_ts_ns,
            "last_close_reason":        status.last_close_reason,
            "timestamp":                _t_mlga.time(),
        }

    # Phase 241-APOP — GET /agent/active-play-occupancy-status
    # ------------------------------------------------------------------
    @app.get("/agent/active-play-occupancy-status")
    async def get_active_play_occupancy_status(
        x_api_key: str = Header(default=""),
    ):
        """Latest Active Play Occupancy Proof status.

        APOP is shadowed by default.  In hybrid/strict modes this endpoint shows
        the exact controller-native evidence used alongside legacy GAD.
        """
        check_read_key(x_api_key)
        import time as _t241
        from ..active_play_occupancy import normalize_active_play_gate_mode

        _enabled = bool(getattr(cfg, "active_play_occupancy_enabled", True))
        _mode = normalize_active_play_gate_mode(
            getattr(cfg, "active_play_occupancy_gate_mode", "shadow")
        )
        try:
            _grind_target = int(getattr(cfg, "grind_target", 100))
            _summary = await asyncio.to_thread(
                store.get_validation_summary,
                _grind_target,
                1.0,
                _mode if _enabled else "shadow",
            )
            _latest_gctx = _summary.get("latest_gameplay_context")
            _status = await asyncio.to_thread(
                store.get_latest_active_play_occupancy_status,
                _enabled,
                _mode,
                _latest_gctx,
            )
            _status["timestamp"] = _t241.time()
            return _status
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 235-GAD — POST /operator/override-gameplay-context
    # ------------------------------------------------------------------
    @app.post("/operator/override-gameplay-context")
    async def override_gameplay_context(
        ruling_validation_log_id: int = Query(...),
        reason: str = Query(default=""),
        api_key: str = Query(default=""),
    ):
        """Override automatic MENU_DETECTED classification to ACTIVE_GAMEPLAY.

        Use when the automatic classification was incorrect (e.g., controller analog
        stick fault caused false MENU_DETECTED during a competitive match).
        Logs to gameplay_classification_disagreements for post-hoc analysis.

        Returns: {accepted, ruling_validation_log_id, reason, timestamp}
        """
        check_key(api_key)
        import time as _tgad
        if len(reason.strip()) < 10:
            raise HTTPException(
                status_code=422,
                detail="reason must be at least 10 characters"
            )
        store.override_gameplay_context(ruling_validation_log_id, reason)
        log.info(
            "Gameplay context overridden for ruling_validation_log_id=%d reason='%s'",
            ruling_validation_log_id, reason,
        )

        # Phase O5-MLGA Stage 9: DISPUTE-PACKET-v1 autonomous emission.
        # An operator-initiated gameplay-context override is effectively
        # a dispute against the automatic adjudication. Fail-open: any
        # emission failure logs internally + does NOT affect the
        # override response. Worker-thread to keep the event loop free.
        try:
            from ..dispute_packet_emitter import emit_dispute_packet
            await asyncio.to_thread(
                emit_dispute_packet,
                store=store, cfg=cfg,
                dispute_id=f"dispute-rvl-{ruling_validation_log_id}",
                ruling_validation_log_id=int(ruling_validation_log_id),
                adjudicator_agent_id="guardian",
                evidence_count=1,
                dispute_status="open",
                reason=str(reason),
            )
        except Exception as _disp_exc:  # noqa: BLE001
            log.warning(
                "DISPUTE-PACKET emit hook failed (non-fatal): %s", _disp_exc,
            )

        return {
            "accepted":                True,
            "ruling_validation_log_id": ruling_validation_log_id,
            "reason":                  reason,
            "timestamp":               _tgad.time(),
        }

    # Phase 235-PGV — POST /operator/gic-reset (Pre-Grind Validation Category 5)
    # ------------------------------------------------------------------
    @app.post("/operator/gic-reset")
    async def operator_gic_reset(
        reason: str = Query(default=""),
        api_key: str = Query(default=""),
    ):
        """Clear app._gic_chain_broken flag after operator investigation and repair.

        Requires operator api_key. reason must be at least 10 characters.
        Logs the reason for audit trail. Does NOT repair the chain — the operator
        must fix the underlying DB issue or start a new GRIND_SESSION_ID first.

        Returns: {accepted, was_broken, reason, timestamp}
        """
        check_key(api_key)
        import time as _tgic
        if len(reason.strip()) < 10:
            raise HTTPException(
                status_code=422,
                detail="reason must be at least 10 characters (e.g., 'DB restored from backup')"
            )
        _was_broken = bool(getattr(app, "_gic_chain_broken", False))
        app._gic_chain_broken = False
        store.set_gic_chain_broken(False)
        try:
            store.write_agent_event(
                event_type="gic_chain_reset",
                payload=_json.dumps({"reason": reason, "was_broken": _was_broken}),
                source="operator",
                target="bridge_agent",
                device_id="",
            )
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
        log.warning(
            "GIC chain broken flag RESET by operator — was_broken=%s reason='%s'",
            _was_broken, reason,
        )
        return {
            "accepted":   True,
            "was_broken": _was_broken,
            "reason":     reason,
            "timestamp":  _tgic.time(),
        }

    # Retina DePIN policy — POST /operator/disarm-retina-policy
    # ------------------------------------------------------------------
    @app.post("/operator/disarm-retina-policy")
    async def operator_disarm_retina_policy(
        reason: str = Query(default=""),
        api_key: str = Query(default=""),
    ):
        """Operator disarm of runtime Retina auto-arm (audit reason required)."""
        check_key(api_key)
        import time as _t_rdis
        if len(reason.strip()) < 10:
            raise HTTPException(
                status_code=422,
                detail="reason must be at least 10 characters",
            )
        _transport = getattr(app, "_transport", None)
        if _transport is not None:
            _transport._retina_operator_disarmed = True
            if hasattr(_transport, "_refresh_retina_policy"):
                _transport._refresh_retina_policy()
        try:
            store.insert_retina_policy_log(
                event_type="operator_disarm",
                arm_source="operator_disarm",
                qualifiers_json=_json.dumps({"reason": reason}),
                effective_perception=False,
            )
        except Exception:
            pass
        try:
            store.write_agent_event(
                event_type="retina_policy_disarm",
                payload=_json.dumps({"reason": reason}),
                source="operator",
                target="bridge_agent",
                device_id="",
            )
        except Exception:
            pass
        log.warning("Retina policy disarmed by operator — reason='%s'", reason)
        return {
            "accepted": True,
            "reason": reason,
            "timestamp": _t_rdis.time(),
        }

    # Phase 235-A — GET /bridge/grind-chain-status
    # ------------------------------------------------------------------
    @app.get("/bridge/grind-chain-status")
    async def get_grind_chain_status(
        x_api_key: str = Header(default=""),
    ):
        """Grind Integrity Chain status (Phase 235-A).

        Returns (7 keys): grind_session_id, chain_length, latest_gic_hash,
        chain_intact, genesis_ts, latest_ts, timestamp.
        """
        check_read_key(x_api_key)
        import time as _t235a
        # Phase 235-BRIDGE-WEDGE-FIX: both Store reads run on a worker thread
        # so this endpoint stays responsive while the DB scans (which can be
        # >1s on large ruling_validation_log tables).
        try:
            _grind_sid = getattr(cfg, "grind_session_id", "")
            _status = await asyncio.to_thread(
                store.get_grind_chain_status, _grind_sid, cfg
            )
            _gad_summary = await asyncio.to_thread(store.get_validation_summary, 1)
            _latest_gctx = _gad_summary.get("latest_gameplay_context")
            # Surface grind_target so the frontend ribbon / progress widgets
            # show the live target (not the hardcoded 100 fallback). Bumped
            # 2026-06-05 to 200 after GIC_100 was reached; SessionBoundary
            # DetectorAgent needs target > chain_length to stay armed.
            _grind_target = int(getattr(cfg, "grind_target", 0) or 0)
            return {
                **_status,
                "latest_gameplay_context": _latest_gctx,
                "grind_target": _grind_target,
                "timestamp": _t235a.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    # Phase 236-WATCHDOG — GET /operator/watchdog-status
    # ------------------------------------------------------------------
    # Read-only audit surface for the Watchdog Event Chain (WEC).
    # Bridge reads watchdog_event_log; the watchdog itself is the only writer.
    # Pairs with /bridge/grind-chain-status: GIC tracks cognitive sessions,
    # WEC tracks operational continuity. Together they prove a grind run.
    @app.get("/operator/watchdog-status")
    async def get_watchdog_status(
        x_api_key: str = Header(default=""),
    ):
        """Watchdog Event Chain status (Phase 236-WATCHDOG).

        Returns (10 keys):
          grind_session_id, chain_length, latest_wec_hash, chain_intact,
          last_event_code, last_event_name, last_event_ts,
          restarts_last_hour, genesis_ts, timestamp.
        """
        check_read_key(x_api_key)
        import time as _t236w
        try:
            _grind_sid = getattr(cfg, "grind_session_id", "")
            _status = await asyncio.to_thread(
                store.get_watchdog_event_chain_status, _grind_sid, 200
            )
            return {**_status, "timestamp": _t236w.time()}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # BCRA — GET /bridge/connectivity
    # ------------------------------------------------------------------
    # Read-only Bridge Connectivity Readiness Aggregator: composes the four
    # already-computed subsystem statuses (CONTROLLER / AGENTS / CHAIN /
    # OPERATIONAL) into ONE honest readiness view + a VPM honesty label, so the
    # dashboard shows a single coherent "is the bridge fully connected + loaded"
    # signal instead of the operator AND-ing ~5 endpoints. Honest by design: the
    # CHAIN kill-switch (CHAIN_SUBMISSION_PAUSED) renders DEGRADED not green; any
    # degraded/unknown lane keeps the overall view off `live`. Event-loop safe:
    # store scans run on worker threads; the RPC reachability probe is bounded.
    @app.get("/bridge/connectivity")
    async def get_bridge_connectivity(
        x_api_key: str = Header(default=""),
    ):
        """Aggregated bridge connectivity readiness (BCRA).

        Returns the ConnectivityAttestation dict: schema, verdict, visual_state,
        per-lane {state, evidence}, vpm_label, ts_ns, attestation_hash.
        """
        check_read_key(x_api_key)
        import time as _tbcra
        from dataclasses import asdict as _asdict
        from ..bridge_connectivity_aggregator import assemble_connectivity

        # CONTROLLER — live PCC monitor if wired (same source as /bridge/capture-health)
        _controller = None
        _mon = getattr(app, "_pcc_monitor", None)
        if _mon is not None:
            try:
                _live = _mon.get_status()
                _controller = {"capture_state": _live.get("capture_state"),
                               "host_state": _live.get("host_state"),
                               "poll_rate_hz": _live.get("poll_rate_hz")}
            except Exception:
                _controller = None

        # AGENTS — fleet liveness wiring deferred to a fleet-status source; honest
        # UNKNOWN until then (the aggregator handles None without overclaiming).
        _agents = None

        # CHAIN — kill-switch from cfg (cheap, authoritative) + bounded RPC reach probe
        _paused = bool(getattr(cfg, "chain_submission_paused", True))
        _rpc_ok = None
        _w3 = getattr(chain, "_sync_w3", None)
        if _w3 is not None:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(lambda: _w3.eth.block_number), timeout=3.0)
                _rpc_ok = True
            except Exception:
                _rpc_ok = False
        _chain = {"rpc_reachable": _rpc_ok, "submission_paused": _paused}

        # OPERATIONAL — watchdog + GIC chain intactness + restart rate (worker thread)
        _operational = None
        try:
            _grind_sid = getattr(cfg, "grind_session_id", "")
            _wd = await asyncio.to_thread(
                store.get_watchdog_event_chain_status, _grind_sid, 200)
            _gic = await asyncio.to_thread(store.get_grind_chain_status, _grind_sid, cfg)
            _operational = {"watchdog_chain_intact": bool(_wd.get("chain_intact")),
                            "gic_chain_intact": bool(_gic.get("chain_intact")),
                            "restarts_last_hour": int(_wd.get("restarts_last_hour") or 0)}
        except Exception:
            _operational = None

        att = assemble_connectivity(_controller, _agents, _chain, _operational,
                                    ts_ns=time.time_ns())
        return {**_asdict(att), "timestamp": _tbcra.time()}

    # Phase B backlog #8 — POST /operator/ipact-challenge
    # ------------------------------------------------------------------
    # Issue a fresh iPACT re-attestation challenge (bridge-issued 32-byte CSPRNG
    # nonce, single-use + TTL). The device composite-signs the nonce (①) under the
    # dedicated CHALLENGE_TAG; VHPRenewalAgent verifies + computes the reattest_proof.
    # Stdlib-only path (no PQ libs) — the verify (composite_sig) is lazy-imported in
    # the agent only when enforcement is ON.
    @app.post("/operator/ipact-challenge")
    def issue_ipact_challenge(
        device_id: str = Query(..., description="Device requesting a re-attestation challenge"),
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Issue a fresh iPACT re-attestation challenge (Phase B #8).

        Returns: challenge_id, device_id, nonce_hex (32B), expires_at, challenge_tag.
        """
        check_key(api_key)
        check_rate(api_key)
        from ..ipact_challenge import SHARED_CHALLENGE_STORE, CHALLENGE_TAG
        ch = SHARED_CHALLENGE_STORE.issue(device_id)
        return {
            "challenge_id": ch.challenge_id,
            "device_id": ch.device_id,
            "nonce_hex": ch.nonce.hex(),
            "expires_at": ch.expires_at,
            "challenge_tag": CHALLENGE_TAG.decode(),
        }
    # Phase 236-CORPUS-SNAPSHOT — GET /agent/corpus-snapshot-status
    # ------------------------------------------------------------------
    # Read-only audit surface for the corpus-snapshot chain (the third
    # pillar alongside GIC + WEC). Surfaces the latest snapshot's commitment,
    # wiki/fleet/ratio bindings, and whether it's been anchored on-chain.
    @app.get("/agent/corpus-snapshot-status")
    async def get_corpus_snapshot_status(
        x_api_key: str = Header(default=""),
    ):
        """Corpus snapshot status (Phase 236-CORPUS-SNAPSHOT).

        Returns (10 keys): total_snapshots, latest_commitment, wiki_hash,
        agent_root, separation_ratio, corpus_n, last_snapshot_ts,
        on_chain_confirmed, trigger_reason, timestamp.
        """
        check_read_key(x_api_key)
        try:
            return await asyncio.to_thread(store.get_corpus_snapshot_status)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 236-CORPUS-SNAPSHOT — POST /operator/force-corpus-snapshot
    # ------------------------------------------------------------------
    # Phase 237.5: on-chain anchoring is now active. Order of operations:
    # compute commitment → anchor via AdjudicationRegistry.anchorAdjudication(
    # commitment, "CORPUS_SNAPSHOT") → insert row with anchor result already
    # populated in the same insert call (no post-insert UPDATE pattern).
    # Anchor failure does not block the snapshot insert — row records
    # (tx_hash="", on_chain_confirmed=False) for graceful audit-trail
    # degradation. The local snapshot is always authoritative; the on-chain
    # anchor adds tamper-evidence at the inter-database layer for future
    # ZK-SEPPROOF binding (PHASE_237_5_DESIGN.md §4).
    @app.post("/operator/force-corpus-snapshot")
    async def force_corpus_snapshot(
        api_key: str = Query(default=""),
        reason: str = Query(default=""),
    ):
        """Operator-triggered corpus snapshot (Phase 236-CORPUS-SNAPSHOT).

        Args:
            api_key: Must match cfg.operator_api_key (full operator auth, not read-only).
            reason:  Operator-provided audit string; minimum 10 characters.

        Returns:
            Dict with row_id, snapshot_commitment, wiki_hash, agent_root,
            separation_ratio, corpus_n, ts_ns, trigger_reason, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        _reason = (reason or "").strip()
        if len(_reason) < 10:
            raise HTTPException(
                422, "reason must be at least 10 characters (operator audit field)"
            )

        import time as _t236snap
        from ..corpus_snapshot import (
            agent_root_from_hex,
            compute_corpus_commitment,
            compute_wiki_snapshot_hash,
        )
        # wiki_dir resolves to <project_root>/wiki — Config has wiki_dir if present,
        # else fall back to "wiki" relative to bridge cwd.
        _wiki_dir = getattr(cfg, "wiki_dir", "wiki")

        try:
            # Compute inputs concurrently where possible
            wiki_hash = await asyncio.to_thread(compute_wiki_snapshot_hash, _wiki_dir)
            pcs = await asyncio.to_thread(store.get_protocol_coherence_status)
            ait = await asyncio.to_thread(store.get_ait_separation_status)

            agent_root = agent_root_from_hex(pcs.get("latest_merkle_root"))
            ratio = float(ait.get("separation_ratio", 0.0))
            corpus_n = int(ait.get("n_sessions", 0))
            ts_ns = _t236snap.time_ns()

            commitment = compute_corpus_commitment(
                wiki_hash, agent_root, ratio, corpus_n, ts_ns
            )

            # Phase 237.5: anchor FIRST so the insert can record the live
            # result in one call. anchor_corpus_snapshot never raises;
            # returns (None, False) on any failure path so the snapshot
            # insert always proceeds (graceful degradation).
            tx_hash_hex, anchored = await chain.anchor_corpus_snapshot(
                commitment.hex(),
            )

            row_id = await asyncio.to_thread(
                store.insert_corpus_snapshot,
                commitment.hex(),
                wiki_hash.hex(),
                agent_root.hex(),
                ratio,
                corpus_n,
                ts_ns,
                _reason,
                bool(anchored),                # on_chain_confirmed
                tx_hash_hex or "",             # tx_hash
                "",                            # ipfs_cid (deferred)
            )

            return {
                "row_id":              int(row_id),
                "snapshot_commitment": commitment.hex(),
                "wiki_hash":           wiki_hash.hex(),
                "agent_root":          agent_root.hex(),
                "separation_ratio":    ratio,
                "corpus_n":            corpus_n,
                "ts_ns":               ts_ns,
                "trigger_reason":      _reason,
                "on_chain_confirmed":  bool(anchored),
                "tx_hash":             tx_hash_hex or "",
                "timestamp":           _t236snap.time(),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 237-ZK-SEPPROOF — POST /operator/anchor-biometric-snapshot
    # ------------------------------------------------------------------
    # Reads the most recent AIT row's centroids_json + cov_inv_json, computes
    # the BIOMETRIC-SNAPSHOT-v1 commitment via biometric_snapshot.compute_biometric_commitment,
    # anchors it on AdjudicationRegistry (best-effort, fail-open per kill-switch),
    # and persists to biometric_snapshot_log. The commitment is the public input
    # binding for ZK-SEPPROOF circuits.
    #
    # 422 conditions: missing/empty centroids in latest ait_session_log row
    # (operator must run analyze_interperson_separation.py with the Phase 237
    # extension that persists centroids + cov_inv before this endpoint succeeds).
    @app.post("/operator/anchor-biometric-snapshot")
    async def anchor_biometric_snapshot_endpoint(
        api_key: str = Query(default=""),
        reason: str = Query(default=""),
    ):
        """Operator-triggered biometric snapshot anchor (Phase 237-ZK-SEPPROOF).

        Args:
            api_key: Must match cfg.operator_api_key (full operator auth).
            reason:  Operator-provided audit string; minimum 10 characters.

        Returns:
            Dict with row_id, snapshot_commitment, feature_dim, n_players,
            sorted_player_ids, ts_ns, trigger_reason, on_chain_confirmed,
            tx_hash, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        _reason = (reason or "").strip()
        if len(_reason) < 10:
            raise HTTPException(
                422, "reason must be at least 10 characters (operator audit field)"
            )

        import json as _j237ep
        import time as _t237ep
        from ..biometric_snapshot import compute_biometric_commitment

        try:
            # Pull the latest AIT row directly so we can read the new
            # centroids_json + cov_inv_json columns. get_ait_separation_status
            # exists for higher-level summary; here we need the raw row.
            with store._conn() as _conn237:
                row = _conn237.execute(
                    "SELECT id, centroids_json, cov_inv_json, n_per_player_json "
                    "FROM ait_session_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
            if row is None:
                raise HTTPException(
                    422,
                    "no AIT session row available — run analyze_interperson_separation.py "
                    "--session-type ait --write-snapshot first",
                )
            try:
                cents_raw = _j237ep.loads(row["centroids_json"] or "{}")
                # JSON keys are strings — coerce to int player_ids
                centroids = {int(k): list(v) for k, v in cents_raw.items()}
            except Exception as exc:
                raise HTTPException(
                    422, f"centroids_json parse failed: {exc}",
                )
            try:
                cov_inv = _j237ep.loads(row["cov_inv_json"] or "[]")
            except Exception as exc:
                raise HTTPException(
                    422, f"cov_inv_json parse failed: {exc}",
                )
            if not centroids or not cov_inv:
                raise HTTPException(
                    422,
                    "latest AIT row has empty centroids/cov_inv — run "
                    "analyze_interperson_separation.py with Phase 237 "
                    "extension that persists geometric inputs",
                )

            sorted_ids = sorted(centroids.keys())
            feature_dim = len(centroids[sorted_ids[0]])
            ts_ns = _t237ep.time_ns()

            commitment = compute_biometric_commitment(
                feature_dim=feature_dim,
                sorted_player_ids=sorted_ids,
                centroids_by_player=centroids,
                cov_inv=cov_inv,
                ts_ns=ts_ns,
            )

            # Anchor first so the insert can record the live result in one
            # call. anchor_biometric_snapshot never raises; returns
            # (None, False) on any failure (kill-switch, missing config,
            # tx revert, duplicate) so the local insert always proceeds.
            tx_hash_hex, anchored = await chain.anchor_biometric_snapshot(
                commitment.hex(),
            )

            row_id = await asyncio.to_thread(
                store.insert_biometric_snapshot,
                commitment.hex(),
                feature_dim,
                sorted_ids,
                centroids,
                cov_inv,
                ts_ns,
                int(row["id"]),                     # ait_session_log_id
                _reason,
                bool(anchored),                     # on_chain_confirmed
                tx_hash_hex or "",                  # tx_hash
            )

            return {
                "row_id":              int(row_id),
                "snapshot_commitment": commitment.hex(),
                "feature_dim":         feature_dim,
                "n_players":           len(sorted_ids),
                "sorted_player_ids":   sorted_ids,
                "ts_ns":               ts_ns,
                "trigger_reason":      _reason,
                "on_chain_confirmed":  bool(anchored),
                "tx_hash":             tx_hash_hex or "",
                "ait_session_log_id":  int(row["id"]),
                "timestamp":           _t237ep.time(),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/auto-trigger-status")
    async def get_auto_trigger_status(
        x_api_key: str = Header(default=""),
    ):
        """SessionBoundaryDetectorAgent telemetry.  Returns (10 keys):
        auto_trigger_enabled, agent_alive, fires_this_run, last_fire_age_s,
        next_eligible_in_s, min_interval_s, quiescence_window,
        activity_window, stopped, timestamp.

        Throttle math: next_eligible_in_s = max(0, min_interval_s -
        last_fire_age_s).  Counts down every 5s on the dashboard side.
        """
        check_read_key(x_api_key)
        import time as _tat
        agent = getattr(app, "_sbda", None)
        if agent is None:
            return {
                "auto_trigger_enabled": bool(getattr(cfg, "auto_trigger_enabled", False)),
                "agent_alive":          False,
                "fires_this_run":       0,
                "last_fire_age_s":      None,
                "next_eligible_in_s":   0.0,
                "min_interval_s":       int(getattr(cfg, "auto_trigger_min_interval_s", 300)),
                "quiescence_window":    int(getattr(cfg, "auto_trigger_quiescence_window", 60)),
                "activity_window":      int(getattr(cfg, "auto_trigger_activity_window", 120)),
                "stopped":              False,
                "timestamp":            _tat.time(),
            }
        try:
            telem = agent.get_telemetry()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"telemetry failed: {exc}") from exc
        telem["agent_alive"] = True
        telem["timestamp"]   = _tat.time()
        return telem

    # Phase 235-OBSERVABILITY — GET /grind/session-history
    # ------------------------------------------------------------------
    # Exposes ruling_validation_log data with a derived blocking_reason
    # field so operators can diagnose why specific sessions did or did not
    # advance the GIC chain — without direct SQLite access (which Windows
    # exclusive-lock makes impossible while the bridge runs).
    @app.get("/grind/session-history")
    async def get_grind_session_history(
        x_api_key: str = Header(default=""),
        limit: int = Query(default=20, ge=1, le=200),
    ):
        """Per-session GIC eligibility history with blocking_reason (Phase 235-OBSERVABILITY).

        Returns last N ruling_validation_log rows for the current grind session.
        Each row includes stamped (bool) and blocking_reason (None when stamped,
        otherwise a string explaining which gate blocked the GIC stamp).
        """
        check_read_key(x_api_key)
        import time as _tobs
        _grind_sid = getattr(cfg, "grind_session_id", "")
        try:
            rows = await asyncio.to_thread(
                store.get_grind_session_history, limit, _grind_sid
            )
            return {
                "rows":             rows,
                "count":            len(rows),
                "grind_session_id": _grind_sid,
                "timestamp":        _tobs.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 235-CONTENTION — GET /grind/pcc-intelligence
    # ------------------------------------------------------------------
    # BT contention episode analytics: how often does the PS5 reclaim BT
    # during menu idle, how long does recovery take, and how many times
    # has the self-healing hidapi counter thread needed to reconnect.
    @app.get("/grind/pcc-intelligence")
    async def get_pcc_intelligence(
        x_api_key: str = Header(default=""),
    ):
        """BT contention pattern intelligence (Phase 235-CONTENTION).

        Returns capture_health_log episode analytics plus hid_counter_restarts
        from the live DualShockTransport instance (fail-open 0 when not wired).
        """
        check_read_key(x_api_key)
        import time as _tcon
        try:
            analytics = await asyncio.to_thread(store.get_bt_contention_analytics)
            transport = getattr(app, "_transport", None)
            analytics["hid_counter_restarts"] = (
                getattr(transport, "_hid_counter_restarts", 0) if transport is not None else 0
            )
            analytics["timestamp"] = _tcon.time()
            return analytics
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 235-ANALYTICS — GET /grind/analytics
    # ------------------------------------------------------------------
    # Aggregate grind pipeline analytics: success rate, blocking reason
    # distribution, sessions-per-day velocity, projected GIC_100 date.
    @app.get("/grind/analytics")
    async def get_grind_analytics(
        x_api_key: str = Header(default=""),
    ):
        """Grind pipeline aggregate analytics (Phase 235-ANALYTICS).

        Reads ruling_validation_log for the current grind session and returns
        success_rate, blocking_reason_counts, sessions_per_day, and
        projected_gic100_date.
        """
        check_read_key(x_api_key)
        _grind_sid = getattr(cfg, "grind_session_id", "")
        _gate_n    = int(getattr(cfg, "grind_target", 100))
        try:
            result = await asyncio.to_thread(
                store.get_grind_analytics, _grind_sid, _gate_n
            )
            return result
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    # ------------------------------------------------------------------
    # Phase O0 Stream 4-prep Session 2 — five read-only agent endpoints.
    #
    # Per Pass 2C Section 5.1 lines 794-799 (Decision B3: agent- prefix
    # path naming preserved). All five require Depends(check_agent_token)
    # which composes OAuth 2.1 token verification + HMAC request signing
    # verification + nonce dedup + timestamp freshness (Decisions A1..A7
    # from Stream 4-prep Session 1 + B1..B4 from Session 2).
    #
    # Phase O0 scope: bridge:agent:phases:read (read-only). Write scopes
    # deferred to P1+ when agents gain write authority.
    #
    # The 154+ existing /operator/* and /agent/* endpoints with x-api-key
    # auth are UNCHANGED. Only these five new endpoints accept agent
    # tokens; mixing operator keys with these endpoints is rejected via
    # the dependency's missing-Authorization check.
    # ------------------------------------------------------------------

    @app.get("/agent/agent-commit-history")
    async def agent_commit_history_endpoint(
        agent_id: str = "",
        limit: int = 20,
        auth: AgentIdentity = Depends(check_agent_token),
    ):
        """Read AGENT_COMMIT v1 history from agent_commit_log.

        Phase O0 Stream 3-prep Session 1 + Session 2 wire-up.
        Returns the last `limit` commits (default 20), DESC ts_ns,
        optionally filtered by agent_id. Stream 3-prep Session 1's
        store.get_agent_commit_history() backs this endpoint.
        """
        try:
            rows = await asyncio.to_thread(
                store.get_agent_commit_history,
                agent_id, int(limit),
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "client_id":     auth.client_id,
            "filter_agent":  agent_id,
            "limit":         int(limit),
            "count":         len(rows),
            "commits":       rows,
            "timestamp":     time.time(),
        }

    @app.get("/agent/agent-commit-status")
    async def agent_commit_status_endpoint(
        auth: AgentIdentity = Depends(check_agent_token),
    ):
        """Latest AGENT_COMMIT v1 record summary (8 keys per Session 1).

        Returns the same shape as store.get_agent_commit_status():
          total_commits / latest_hash / latest_agent_id /
          latest_commit_sha / latest_ts_ns / on_chain_confirmed /
          anchor_id / timestamp.
        """
        try:
            status = await asyncio.to_thread(store.get_agent_commit_status)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        # Augment with the authenticated client_id for audit trail.
        status["client_id"] = auth.client_id
        return status

    @app.get("/agent/physical-data-attestation-history")
    async def pda_history_endpoint(
        agent_id: str = "",
        attestation_type: str = "",
        limit: int = 20,
        auth: AgentIdentity = Depends(check_agent_token),
    ):
        """Read PHYSICAL_DATA_ATTESTATION v1 history from
        physical_data_attestation_log. Filterable by agent_id and/or
        attestation_type per Stream 3-prep Session 2's
        get_physical_data_attestation_history().
        """
        try:
            rows = await asyncio.to_thread(
                store.get_physical_data_attestation_history,
                agent_id, attestation_type, int(limit),
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {
            "client_id":               auth.client_id,
            "filter_agent":            agent_id,
            "filter_attestation_type": attestation_type,
            "limit":                   int(limit),
            "count":                   len(rows),
            "attestations":            rows,
            "timestamp":               time.time(),
        }

    @app.get("/agent/physical-data-attestation-status")
    async def pda_status_endpoint(
        auth: AgentIdentity = Depends(check_agent_token),
    ):
        """Latest PHYSICAL_DATA_ATTESTATION v1 record summary (8 keys
        per Session 2). Returns the same shape as
        store.get_physical_data_attestation_status().
        """
        try:
            status = await asyncio.to_thread(
                store.get_physical_data_attestation_status,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        status["client_id"] = auth.client_id
        return status

    @app.get("/agent/agent-registry-status")
    async def agent_registry_status_endpoint(
        auth: AgentIdentity = Depends(check_agent_token),
    ):
        """Read AgentRegistry contract state.

        Decision B2: deferred-activation pattern. When
        cfg.agent_registry_address is empty (Stream 2-deploy not yet
        landed AgentRegistry on IoTeX testnet), returns:
            {
              "registry_address": "",
              "deployed":         false,
              "client_id":        ...,
              "timestamp":        ...,
              "status":           "AgentRegistry not yet deployed
                                   (Stream 2-deploy gated on wallet ≥3 IOTX)"
            }

        When the address is populated, would query the contract for
        registered-agent count and other read-only state. The on-chain
        read path is left as a TODO until Stream 2-deploy lands the
        contract — at that point, an `agent_registry_count` and similar
        view-call wrappers will be added to chain.py and surfaced here.
        """
        addr = getattr(cfg, "agent_registry_address", "")
        if not addr:
            return {
                "registry_address": "",
                "deployed":         False,
                "client_id":        auth.client_id,
                "timestamp":        time.time(),
                "status": (
                    "AgentRegistry not yet deployed "
                    "(Stream 2-deploy gated on wallet ≥3 IOTX per Pass 2A V8)"
                ),
            }
        # Live path — populated when Stream 2-deploy lands the contract.
        return {
            "registry_address": addr,
            "deployed":         True,
            "client_id":        auth.client_id,
            "timestamp":        time.time(),
            "status":           "AgentRegistry deployed; live read path TBD",
        }
