"""Biometric / VHP / attestation routes (D-DECON-2 operator_api residue #15).

Register-function split per audits/decon-store-map.md agent_biometric domain.
Routes byte-identical to the former inline handlers in _app.py.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Query

log = logging.getLogger(__name__)


def register_agent_biometric_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    chain,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
    check_read_key: Callable[[str], None],
) -> None:
    """Register VHP mint/status, biometric TTL, attestation, and renewal HTTP routes."""

    # --- Phase 99C: VHP Soulbound Token ---

    @app.post("/agent/mint-vhp")
    async def mint_vhp(
        api_key: str = Query(..., description="Shared operator API key"),
        device_id: str = Query(..., description="Device identifier"),
        to_address: str = Query(..., description="Recipient Ethereum address for VHP token"),
        sepproof_commitment: str = Query(
            default="",
            description=(
                "Phase 237-ZK-SEPPROOF (Step G): optional 64-char hex BIOMETRIC-SNAPSHOT-v1 "
                "commitment to bind the VHP to a ZK-attested separation proof. "
                "Required when vhp_sepproof_required=true; optional otherwise. "
                "Validation: snapshot must exist in biometric_snapshot_log AND "
                "on_chain_confirmed=true."
            ),
        ),
    ):
        """Mint a VHP soulbound token for a device that has passed all three gate conditions.

        Gate conditions (all must be true):
          1. audit_valid=True — activation audit passes (get_activation_audit_summary)
          2. gate_passed=True — validation gate has consecutive_clean >= gate_n
          3. dry_run=False — bridge is in live enforcement mode

        Returns tx_hash + expires_at on success. Returns 422 on gate failure.
        """
        check_key(api_key)
        check_rate(api_key)
        import hashlib

        # Gate condition 1: audit_valid
        try:
            audit = store.get_activation_audit_summary()
        except Exception:
            audit = {}
        if not audit.get("audit_valid"):
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(
                status_code=422,
                detail={"error": "audit_valid=False — activation audit not passed"},
            )

        # Gate condition 2: gate_passed
        try:
            gate_n = getattr(cfg, "validation_gate_n", 100)
            max_div = getattr(cfg, "validation_max_divergence_rate", 1.0)
            summary = store.get_validation_summary(gate_n, max_div)
        except Exception:
            summary = {}
        if not summary.get("gate_passed"):
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(
                status_code=422,
                detail={"error": "gate_passed=False — validation gate not cleared"},
            )

        # Gate condition 3: not dry_run
        if getattr(cfg, "agent_dry_run_mode", True):
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(
                status_code=422,
                detail={"error": "dry_run=True — live mode not active; set AGENT_DRY_RUN=false"},
            )

        # Build VHP data (needed for consecutive_clean before ioSwarm gate)
        device_id_hash = "0x" + hashlib.sha256(device_id.encode()).hexdigest()
        consecutive_clean = summary.get("consecutive_clean", 0)
        rulings = store.get_agent_rulings(device_id, limit=1)
        confidence_score = int(rulings[0]["confidence"] * 10000) if rulings else 0
        mpc_hash = getattr(cfg, "mpc_ceremony_hash_cache", None) or "0x" + "0" * 64

        # Phase 110: ioSwarm VHP Mint Authorization — fail-CLOSED quorum gate (additive, 4th gate)
        _ioswarm_mint_on = getattr(cfg, "ioswarm_vhp_mint_enabled", False)
        if _ioswarm_mint_on:
            def _get_recent_block_count(_store, _device_id):
                """Count recent BLOCK rulings for device (last 7 days). Never raises."""
                try:
                    import time as _t_blk
                    cutoff = _t_blk.time() - 7 * 86400
                    recent = _store.get_agent_rulings(_device_id, limit=50)
                    return sum(1 for r in recent if r.get("verdict") == "BLOCK"
                               and r.get("created_at", 0) >= cutoff)
                except Exception:
                    return 0

            from fastapi import HTTPException as _HTTPException
            try:
                from ..ioswarm_vhp_mint_coordinator import IoSwarmVHPMintCoordinator
                from ..ioswarm_live_node_client import IoSwarmLiveNodeClient as _ILNC131m
                _live_client_m = _ILNC131m(cfg=cfg, store=store)
                _mint_auth = IoSwarmVHPMintCoordinator(cfg=cfg, store=store, live_client=_live_client_m).authorize(
                    device_id=device_id,
                    consecutive_clean=int(consecutive_clean),
                    recent_block_count=_get_recent_block_count(store, device_id),
                )
                if not _mint_auth.get("authorized", False):
                    raise _HTTPException(
                        status_code=422,
                        detail={
                            "error":          "ioswarm_quorum_denied",
                            "quorum_verdict": _mint_auth.get("quorum_verdict", "DENY"),
                            "agreement_ratio": _mint_auth.get("agreement_ratio", 0.0),
                        },
                    )
            except _HTTPException:
                raise
            except Exception as _exc:
                # Fail-CLOSED (W1): coordinator exception blocks mint
                raise _HTTPException(
                    status_code=422,
                    detail={
                        "error":   "ioswarm_coordinator_error",
                        "message": str(_exc),
                    },
                ) from _exc

        # Gate condition 5: dual-primitive eligibility (only when enabled)
        if getattr(cfg, "dual_primitive_gate_enabled", False):
            import hashlib as _hl114
            import time as _time115
            _poad_hash_114 = store.get_latest_poad_hash_for_device(device_id)
            if not _poad_hash_114:
                from fastapi import HTTPException as _HTTPException
                raise _HTTPException(
                    status_code=422,
                    detail={"error": "dual_primitive_gate: no PoAd hash found for device — run adjudication first"},
                )
            _device_hash_114 = _hl114.sha256(device_id.encode()).hexdigest()
            try:
                _dual = await chain.is_dual_eligible(_device_hash_114, _poad_hash_114)
            except Exception as _exc_dual:
                _dual = {"eligible": False, "poac_valid": False, "poad_valid": False}
            # Phase 115: epoch-window staleness check (sub-check of gate 5)
            # Phase 118: per-device override takes precedence over global window
            _poad_age_s = -1.0
            _epoch_ok = True
            if getattr(cfg, "epoch_window_enabled", False):
                _ts_ns = store.get_poad_ts_ns_for_device(device_id)
                if _ts_ns is not None:
                    _poad_age_s = (_time115.time_ns() - _ts_ns) / 1e9
                    _dev_override = store.get_device_epoch_override(device_id)
                    _epoch_win = _dev_override if _dev_override is not None else float(getattr(cfg, "epoch_window_seconds", 86400))
                    _epoch_ok = _poad_age_s <= _epoch_win
                    # Phase 119: increment use_count when override is active + gate passes
                    if _dev_override is not None and _epoch_ok:
                        try:
                            store.increment_override_use_count(device_id)
                        except Exception:
                            pass  # non-blocking; fail-open: M-1 cleanup 2026-05-16
                else:
                    _epoch_ok = False
                    _poad_age_s = -1.0
            store.insert_vhp_dual_gate_log(
                device_id=device_id,
                poad_hash=_poad_hash_114,
                eligible=_dual["eligible"],
                poac_valid=_dual["poac_valid"],
                poad_valid=_dual["poad_valid"],
                mint_allowed=_dual["eligible"] and _epoch_ok,
                poad_age_seconds=_poad_age_s,
                epoch_window_ok=_epoch_ok,
            )
            if not _dual["eligible"]:
                from fastapi import HTTPException as _HTTPException
                raise _HTTPException(
                    status_code=422,
                    detail={
                        "error":      "dual_primitive_gate: not eligible",
                        "poac_valid": _dual["poac_valid"],
                        "poad_valid": _dual["poad_valid"],
                    },
                )
            if not _epoch_ok:
                from fastapi import HTTPException as _HTTPException
                raise _HTTPException(
                    status_code=422,
                    detail={
                        "error":           "epoch_window: PoAd too old",
                        "poad_age_seconds": _poad_age_s,
                        "epoch_window_seconds": float(getattr(cfg, "epoch_window_seconds", 86400)),
                    },
                )

        # Phase 237-ZK-SEPPROOF Gate 6: ZK separation proof commitment binding
        # ────────────────────────────────────────────────────────────────────
        # Two-tier behaviour controlled by cfg.vhp_sepproof_required:
        #   False (default): if sepproof_commitment is supplied, validate; mint
        #                     proceeds either way. Allows general-enrollment VHPs
        #                     without requiring an attested SEPPROOF anchor —
        #                     preserves backward compatibility.
        #   True (operator opt-in): sepproof_commitment is REQUIRED. Mint rejects
        #                            with 422 if missing or unanchored. This is
        #                            the tournament-grade VHP path.
        # Validation in either tier: when commitment is supplied, the snapshot
        # must exist in biometric_snapshot_log AND have on_chain_confirmed=true.
        _sep_required = bool(getattr(cfg, "vhp_sepproof_required", False))
        _sep_supplied = bool(sepproof_commitment.strip())
        _sep_anchored = False
        _sep_row_id   = 0
        if _sep_supplied:
            try:
                with store._conn() as _conn237vhp:
                    _row237vhp = _conn237vhp.execute(
                        "SELECT id, on_chain_confirmed FROM biometric_snapshot_log "
                        "WHERE snapshot_commitment = ? LIMIT 1",
                        (sepproof_commitment.strip().lower(),),
                    ).fetchone()
                if _row237vhp is None:
                    from fastapi import HTTPException as _HTTPException
                    raise _HTTPException(
                        status_code=422,
                        detail={
                            "error": "sepproof_commitment not found in biometric_snapshot_log",
                            "commitment": sepproof_commitment.strip()[:16] + "...",
                        },
                    )
                _sep_row_id = int(_row237vhp["id"])
                _sep_anchored = bool(_row237vhp["on_chain_confirmed"])
                if not _sep_anchored:
                    from fastapi import HTTPException as _HTTPException
                    raise _HTTPException(
                        status_code=422,
                        detail={
                            "error": "sepproof_commitment not anchored on-chain "
                                     "(on_chain_confirmed=false)",
                            "commitment": sepproof_commitment.strip()[:16] + "...",
                            "row_id":     _sep_row_id,
                        },
                    )
            except Exception as _sep_exc_row:
                # Re-raise HTTPException; wrap others as 500
                from fastapi import HTTPException as _HTTPException
                if isinstance(_sep_exc_row, _HTTPException):
                    raise
                raise _HTTPException(
                    status_code=500,
                    detail={"error": f"sepproof lookup failed: {_sep_exc_row}"},
                ) from _sep_exc_row
        elif _sep_required:
            # Required tier and no commitment supplied — reject mint
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(
                status_code=422,
                detail={
                    "error": "vhp_sepproof_required=true: sepproof_commitment query "
                             "param required (tournament-grade VHP gate)",
                },
            )

        # Phase 122: confidence_score multiplier from battery-stratified separation ratio
        _multiplier_enabled = getattr(cfg, "confidence_multiplier_enabled", False)
        _original_score = confidence_score
        _multiplier = 1.0
        _bt_strat_ratio_122 = -1.0
        if _multiplier_enabled:
            try:
                _snaps122 = store.get_separation_ratio_status(limit=1)
                _bt_strat_ratio_122 = (
                    _snaps122[0].get("bt_strat_ratio", -1.0) if _snaps122 else -1.0
                )
                if _bt_strat_ratio_122 >= 0:
                    _floor122 = float(getattr(cfg, "confidence_multiplier_floor", 0.0))
                    _multiplier = max(_floor122, min(1.0, _bt_strat_ratio_122))
                    confidence_score = max(0, int(_original_score * _multiplier))
                    try:
                        store.insert_confidence_multiplier_log(
                            device_id=device_id,
                            original_score=_original_score,
                            multiplier=_multiplier,
                            final_score=confidence_score,
                            bt_strat_ratio=_bt_strat_ratio_122,
                        )
                    except Exception:
                        pass  # non-blocking; fail-open: M-1 cleanup 2026-05-16
            except Exception:
                pass  # non-blocking — multiplier failure must not block mint; fail-open: M-1 cleanup 2026-05-16

        # Mint on-chain
        try:
            tx_hash = await chain.mint_vhp(
                to_address, device_id_hash, cert_level=1,
                consecutive_clean=consecutive_clean,
                confidence_score=confidence_score,
                mpc_ceremony_hash=mpc_hash,
                ttl_days=90,
            )
        except Exception as exc:
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(status_code=500, detail={"error": str(exc)})

        expires_at = time.time() + 90 * 86400
        store.insert_vhp_issuance(
            device_id=device_id,
            token_id=0,  # on-chain token_id not known synchronously from event
            tx_hash=tx_hash,
            expires_at=expires_at,
            cert_level=1,
            consecutive_clean=consecutive_clean,
            to_address=to_address,
        )
        return {
            "tx_hash": tx_hash,
            "expires_at": expires_at,
            "device_id": device_id,
            "to_address": to_address,
            "consecutive_clean": consecutive_clean,
            "confidence_score": confidence_score,
            "pre_multiplier_score": _original_score,
            "confidence_multiplier": round(_multiplier, 4),
            # Phase 237-ZK-SEPPROOF Step G — sepproof binding metadata
            "sepproof_commitment":      sepproof_commitment.strip() if _sep_supplied else "",
            "sepproof_anchored":        bool(_sep_anchored),
            "sepproof_row_id":          int(_sep_row_id),
            "sepproof_required":        bool(_sep_required),
            "timestamp": time.time(),
        }

    @app.get("/agent/vhp-status/{device_id}")
    def vhp_status(
        device_id: str,
        api_key: str = Query(..., description="Shared operator API key"),
    ):
        """Return the latest VHP issuance record for a device.

        is_valid=True when expires_at > now. Returns found=False if no issuance recorded.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            record = store.get_vhp_status(device_id)
            if record is None:
                return {
                    "device_id": device_id,
                    "found": False,
                    "is_valid": False,
                    "vhp_contract_address": getattr(cfg, "vhp_contract_address", ""),
                    "timestamp": time.time(),
                }
            is_valid = record.get("expires_at", 0) > time.time()
            return {
                "device_id": device_id,
                "found": True,
                "is_valid": is_valid,
                "token_id": record.get("token_id", 0),
                "cert_level": record.get("cert_level", 1),
                "consecutive_clean": record.get("consecutive_clean", 0),
                "expires_at": record.get("expires_at", 0),
                "tx_hash": record.get("tx_hash", ""),
                "to_address": record.get("to_address", ""),
                "vhp_contract_address": getattr(cfg, "vhp_contract_address", ""),
                "timestamp": time.time(),
            }
        except Exception as exc:
            log.warning("vhp_status: %s", exc)
            return {"device_id": device_id, "found": False, "is_valid": False,
                    "error": str(exc), "timestamp": time.time()}

    @app.get("/agent/vhp-renewal-log")
    def vhp_renewal_log(
        api_key: str = Query(...),
        device_id: str = Query(default="", description="Filter by device_id (optional)"),
        limit: int = Query(default=20),
    ):
        """Return VHP auto-renewal log (Phase 102). VHPRenewalAgent (14th agent) populates."""
        check_key(api_key)
        check_rate(api_key)
        try:
            logs = store.get_vhp_renewal_log(
                device_id=device_id if device_id else None, limit=limit
            )
            return {"logs": logs, "total_count": len(logs), "timestamp": time.time()}
        except Exception as exc:
            return {"logs": [], "total_count": 0, "error": str(exc), "timestamp": time.time()}

    @app.get("/agent/first-vhp-status")
    def first_vhp_status(api_key: str = Query(...)):
        """Return the first VHP issuance record (Phase 103).
        is_simulation=True when tx_hash starts with 'sim_'.
        found=False when no VHP has ever been issued.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            vhp = store.get_first_vhp_status()
            if vhp is None:
                return {"found": False, "is_simulation": False, "timestamp": time.time()}
            vhp["found"] = True
            vhp["timestamp"] = time.time()
            return vhp
        except Exception as exc:
            return {"found": False, "error": str(exc), "timestamp": time.time()}

    # Phase 159 — GET /agent/biometric-privacy-status
    # ------------------------------------------------------------------
    @app.get("/agent/biometric-privacy-status")
    async def get_biometric_privacy_status_endpoint(api_key: str = ""):
        """BiometricPrivacyComplianceAgent status (Phase 159, agent #22, BP-001).

        Returns: biometric_privacy_enabled, bp001_half_life_days,
        records_monitored, records_expired, mean_decay_factor, warning_triggered,
        privacy_budget_epsilon, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t159
        try:
            _enabled159   = bool(getattr(cfg, "biometric_privacy_enabled", True))
            _half_life159 = float(getattr(cfg, "bp001_half_life_days", 90.0))
            _status159    = store.get_privacy_compliance_status()
            return {
                "biometric_privacy_enabled": _enabled159,
                "bp001_half_life_days":      _half_life159,
                "records_monitored":         _status159["records_monitored"],
                "records_expired":           _status159["records_expired"],
                "mean_decay_factor":         _status159["mean_decay_factor"],
                "warning_triggered":         _status159["warning_triggered"],
                "privacy_budget_epsilon":    _status159["privacy_budget_epsilon"],
                "timestamp":                 _t159.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 158 — GET /agent/gsr-hmac-validation-status
    # ------------------------------------------------------------------
    @app.get("/agent/gsr-hmac-validation-status")
    async def get_gsr_hmac_validation_status_endpoint(api_key: str = ""):
        """GSR Class K HMAC frame validation status (Phase 158, WIF-014).

        Returns: gsr_hmac_enabled, gsr_hmac_key_configured, total_validations,
        valid_count, rejected_count, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t158a
        try:
            _enabled158 = bool(getattr(cfg, "gsr_hmac_enabled", False))
            _key_cfg    = bool(getattr(cfg, "gsr_hmac_key_hex", ""))
            _status     = store.get_gsr_hmac_validation_status(limit=5)
            return {
                "gsr_hmac_enabled":       _enabled158,
                "gsr_hmac_key_configured": _key_cfg,
                "total_validations":      _status["total_validations"],
                "valid_count":            _status["valid_count"],
                "rejected_count":         _status["rejected_count"],
                "timestamp":              _t158a.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 158 — GET /agent/pohbg-status
    # ------------------------------------------------------------------
    @app.get("/agent/pohbg-status")
    async def get_pohbg_status_endpoint(api_key: str = ""):
        """PoHBG (Proof of Hardware Biometric Grip) status (Phase 158, WIF-015).

        Returns: pohbg_enabled, total_pohbg, latest_pohbg_hash,
        latest_device_id, latest_ts_ns, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t158b
        try:
            _enabled158p = bool(getattr(cfg, "pohbg_enabled", False))
            _pohbg_st    = store.get_pohbg_status(limit=1)
            _latest      = _pohbg_st["recent_hashes"][0] if _pohbg_st["recent_hashes"] else None
            return {
                "pohbg_enabled":    _enabled158p,
                "total_pohbg":      _pohbg_st["total_pohbg"],
                "latest_pohbg_hash": _latest["pohbg_hash"] if _latest else None,
                "latest_device_id": _latest["device_id"] if _latest else None,
                "latest_ts_ns":     _latest["ts_ns"] if _latest else None,
                "timestamp":        _t158b.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 173 — GET /agent/separation-ratio-recovery-status
    # Phase 190 — GET /agent/live-presence-signaling-status
    # ------------------------------------------------------------------
    @app.get("/agent/live-presence-signaling-status")
    async def get_live_presence_signaling_status_endpoint(api_key: str = ""):
        """LivePresenceSignalingAgent status (Phase 190, agent #34).

        Bidirectional VAPI presence channel: dual-path routing via controller LED+haptic
        (ps5_compat_mode aware) + ANSI terminal color stream (always active).

        Returns: live_presence_signaling_enabled/total_signals/controller_fired_count/
        ps5_suppressed_count/latest_signal_source/latest_signal_type/
        latest_terminal_output/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t190
        try:
            _enabled190 = bool(getattr(cfg, "live_presence_signaling_enabled", False))
            _status190  = store.get_presence_signal_status()
            return {
                "live_presence_signaling_enabled": _enabled190,
                "total_signals":          _status190.get("total_signals", 0),
                "controller_fired_count": _status190.get("controller_fired_count", 0),
                "ps5_suppressed_count":   _status190.get("ps5_suppressed_count", 0),
                "latest_signal_source":   _status190.get("latest_signal_source", ""),
                "latest_signal_type":     _status190.get("latest_signal_type", ""),
                "latest_terminal_output": _status190.get("latest_terminal_output", ""),
                "timestamp":              _t190.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 189 — GET /agent/pir-chain-status + POST /agent/create-pir
    # ------------------------------------------------------------------
    @app.get("/agent/pir-chain-status")
    async def get_pir_chain_status_endpoint(api_key: str = ""):
        """ProtocolIntelligenceRecordAgent chain status (Phase 189, agent #33).

        SHA-256 hash-linked PIR chain. chain_intact=True for empty chain (vacuous).
        Returns: pir_chain_enabled/total_pirs/chain_intact/latest_cycle/
        latest_pir_hash/latest_phase_produced/latest_threat_forecast/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t189
        try:
            _enabled189 = bool(getattr(cfg, "pir_chain_enabled", False))
            _status189  = store.get_pir_chain_status()
            return {
                "pir_chain_enabled":        _enabled189,
                "total_pirs":               _status189.get("total_pirs", 0),
                "chain_intact":             _status189.get("chain_intact", True),
                "latest_cycle":             _status189.get("latest_cycle", 0),
                "latest_pir_hash":          _status189.get("latest_pir_hash", ""),
                "latest_phase_produced":    _status189.get("latest_phase_produced", 0),
                "latest_threat_forecast":   _status189.get("latest_threat_forecast", ""),
                "timestamp":                _t189.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/agent/create-pir")
    async def create_pir_endpoint(
        wif_hash: str,
        cycle_number: int = 0,
        phase_produced: int = 0,
        threat_forecast: str = "",
        harness_score: float = 0.0,
        api_key: str = "",
    ):
        """Create a Protocol Intelligence Record (Phase 189).

        Returns 409 on duplicate pir_hash (anti-replay).
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t189b
        try:
            row_id, _pir_hash189 = store.insert_pir(
                cycle_number=cycle_number,
                phase_produced=phase_produced,
                wif_hash=wif_hash,
                threat_forecast=threat_forecast,
                harness_score=harness_score,
                eval_timestamp=_t189b.time(),
            )
            return {"created": True, "row_id": row_id, "pir_hash": _pir_hash189}
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 188 — GET /agent/biometric-stationarity-status
    # ------------------------------------------------------------------
    @app.get("/agent/biometric-stationarity-status")
    async def get_biometric_stationarity_status_endpoint(
        api_key: str = "",
        player_id: str = "",
    ):
        """BiometricStationarityOracleAgent status (Phase 188, agent #32).

        Discriminates P1 genuine drift from adversarial window exploitation using
        Agent 25 chain_integrity_score as the key discriminating signal.

        Returns: biometric_stationarity_enabled/player_id/p_genuine_drift/
        p_adversarial_window/stationarity_verdict/biometric_stationarity_confidence/
        total_adversarial_alerts/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t188
        try:
            _enabled188 = bool(getattr(cfg, "biometric_stationarity_enabled", False))
            _status188  = store.get_biometric_stationarity_status(
                player_id=player_id if player_id else None
            )
            _s = _status188 or {}
            return {
                "biometric_stationarity_enabled":   _enabled188,
                "player_id":                        _s.get("player_id", player_id),
                "p_genuine_drift":                  float(_s.get("p_genuine_drift", 0.0)),
                "p_adversarial_window":             float(_s.get("p_adversarial_window", 0.0)),
                "stationarity_verdict":             _s.get("stationarity_verdict", "STABLE"),
                "biometric_stationarity_confidence": float(_s.get("biometric_stationarity_confidence", 0.5)),
                "total_adversarial_alerts":         int(_s.get("total_adversarial_alerts", 0)),
                "timestamp":                        _t188.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 187 — GET /agent/attestation-opsec-status + GET /agent/vhp-reenrollment-badge-status
    # ------------------------------------------------------------------
    @app.get("/agent/attestation-opsec-status")
    async def get_attestation_opsec_status_endpoint(
        api_key: str = "",
        player_id: str = "",
    ):
        """AttestationOpSecAdvisorAgent status (Phase 187, agent #31, WIF-033 W1 CLOSED).

        Monitors timing_disclosure_risk: adversary monitoring IoTeX mempool for
        registerAttestation() tx can extract hash before confirmation.

        Returns: mempool_opsec_enabled/timing_disclosure_risk/active_attestations/
        re_enrollment_window_active/recommendation/total_high_risk_events/player_id/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t187a
        try:
            _enabled187 = bool(getattr(cfg, "mempool_opsec_enabled", False))
            _status187  = store.get_attestation_opsec_status(
                player_id=player_id if player_id else None
            )
            return {
                "mempool_opsec_enabled":        _enabled187,
                "timing_disclosure_risk":       _status187.get("timing_disclosure_risk", "LOW"),
                "active_attestations":          int(_status187.get("active_attestations", 0)),
                "re_enrollment_window_active":  bool(_status187.get("re_enrollment_window_active", False)),
                "recommendation":               _status187.get("recommendation", ""),
                "total_high_risk_events":       int(_status187.get("total_high_risk_events", 0)),
                "player_id":                    _status187.get("player_id", player_id),
                "timestamp":                    _t187a.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/vhp-reenrollment-badge-status")
    async def get_vhp_reenrollment_badge_status_endpoint(
        api_key: str = "",
        player_id: str = "",
    ):
        """VHPReenrollmentBadge status (Phase 187, WIF-033 W2 CLOSED).

        ERC-4671 soulbound badge minted after each successful re-enrollment attestation.
        LIVE 2026-04-10 at 0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C.

        Returns: reenrollment_badge_enabled/player_id/badge_token_id/re_enrollment_count/
        total_badges/ttl_days/dry_run/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t187b
        try:
            _enabled187b = bool(getattr(cfg, "reenrollment_badge_enabled", False))
            _status187b  = store.get_reenrollment_badge_status(
                player_id=player_id if player_id else None
            )
            return {
                "reenrollment_badge_enabled": _enabled187b,
                "player_id":          _status187b.get("player_id", player_id),
                "badge_token_id":     int(_status187b.get("badge_token_id", 0)),
                "re_enrollment_count": int(_status187b.get("re_enrollment_count", 0)),
                "total_badges":       int(_status187b.get("total_badges", 0)),
                "ttl_days":           float(_status187b.get("ttl_days", 90.0)),
                "dry_run":            bool(_status187b.get("dry_run", True)),
                "timestamp":          _t187b.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 186 — GET /agent/attestation-bound-renewal-status
    # ------------------------------------------------------------------
    @app.get("/agent/attestation-bound-renewal-status")
    async def get_attestation_bound_renewal_status_endpoint(
        api_key: str = "",
        player_id: str = "",
    ):
        """AttestationBoundRenewalAgent status (Phase 186, agent #30, WIF-032 W2 CLOSED).

        Validates that every renewal has a valid active HMAC attestation from Phase 185.

        Returns: attestation_bound_renewal_enabled/player_id/latest_attestation_hash/
        latest_renewal_approved/denial_reason/total_blocked/total_approved/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t186
        try:
            _enabled186 = bool(getattr(cfg, "attestation_bound_renewal_enabled", False))
            _status186  = store.get_attestation_bound_renewal_status(
                player_id=player_id if player_id else None
            )
            return {
                "attestation_bound_renewal_enabled": _enabled186,
                "player_id":               _status186.get("player_id", player_id),
                "latest_attestation_hash": _status186.get("latest_attestation_hash", ""),
                "latest_renewal_approved": bool(_status186.get("latest_renewal_approved", False)),
                "denial_reason":           _status186.get("denial_reason", ""),
                "total_blocked":           int(_status186.get("total_blocked", 0)),
                "total_approved":          int(_status186.get("total_approved", 0)),
                "timestamp":               _t186.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 185 — GET /agent/reenrollment-attestation-status
    # ------------------------------------------------------------------
    @app.get("/agent/reenrollment-attestation-status")
    async def get_reenrollment_attestation_status_endpoint(
        api_key: str = "",
        player_id: str = "",
    ):
        """ReEnrollmentAttestationAgent status (Phase 185, agent #29, WIF-032 W1 CLOSED).

        HMAC-SHA256 attestation token gates re-enrollment window.
        Adversary cannot forge without REAUTH_ATTESTATION_SECRET.

        Returns: reauth_attestation_enabled/player_id/attestation_hash/issued_at/
        expires_at/active/hmac_mode/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t185
        try:
            _enabled185 = bool(getattr(cfg, "reauth_attestation_enabled", True))
            _secret185  = getattr(cfg, "reauth_attestation_secret", "")
            _hmac_mode  = bool(_secret185)
            _attest185  = store.get_active_attestation(player_id if player_id else "")
            return {
                "reauth_attestation_enabled": _enabled185,
                "player_id":       _attest185.get("player_id", player_id),
                "attestation_hash": _attest185.get("attestation_hash", ""),
                "issued_at":       float(_attest185.get("issued_at", 0.0)),
                "expires_at":      float(_attest185.get("expires_at", 0.0)),
                "active":          bool(_attest185.get("active", False)),
                "hmac_mode":       _hmac_mode,
                "timestamp":       _t185.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 183 — GET /agent/maturity-elevation-plan
    # ------------------------------------------------------------------
    @app.get("/agent/maturity-elevation-plan")
    async def get_maturity_elevation_plan_endpoint(api_key: str = ""):
        """MaturityElevationGateAgent elevation plan (Phase 183, agent #28, WIF-027 W2 CLOSED).

        Reads 6-component protocol_maturity_log and generates actionable elevation_plan
        per component (gap/action/estimated_sessions/blocking).
        elevation_available=True when gap_to_target < 0.05.

        Returns: maturity_elevation_enabled/current_tier/target_tier/gap_to_target/
        elevation_available/elevation_plan/estimated_sessions_total/critical_component/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t183
        import json as _json183
        try:
            _enabled183 = bool(getattr(cfg, "maturity_elevation_enabled", True))
            _status183  = store.get_maturity_elevation_status()
            _plan_json  = _status183.get("elevation_plan_json", "{}")
            try:
                _plan = _json183.loads(_plan_json)
            except Exception:
                _plan = {}
            return {
                "maturity_elevation_enabled": _enabled183,
                "current_tier":              _status183.get("current_tier", "ALPHA"),
                "target_tier":               _status183.get("target_tier", "BETA"),
                "gap_to_target":             float(_status183.get("gap_to_target", 1.0)),
                "elevation_available":       bool(_status183.get("elevation_available", False)),
                "elevation_plan":            _plan,
                "estimated_sessions_total":  int(_status183.get("estimated_sessions_total", 0)),
                "critical_component":        _status183.get("critical_component", ""),
                "timestamp":                 _t183.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 182 — GET /agent/persona-break-status
    # ------------------------------------------------------------------
    @app.get("/agent/persona-break-status")
    async def get_persona_break_status_endpoint(
        api_key: str = "",
        player_id: str = "",
    ):
        """PersonaBreakDetectorAgent status (Phase 182, agent #27, WIF-028 deeper mitigation).

        Monitors LOO accuracy trend over last 5 separation_ratio_snapshots per player.
        persona_break_detected=True when mean_loo < persona_break_loo_threshold (0.20).

        Returns: persona_break_detection_enabled/player_id/loo_accuracy_trend/tdi_current/
        persona_break_detected/re_enrollment_urgency/n_snapshots_used/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t182
        try:
            _enabled182 = bool(getattr(cfg, "persona_break_detection_enabled", True))
            _status182  = store.get_persona_break_status(
                player_id=player_id if player_id else None
            )
            return {
                "persona_break_detection_enabled": _enabled182,
                "player_id":              _status182.get("player_id", player_id),
                "loo_accuracy_trend":     float(_status182.get("loo_accuracy_trend", 1.0)),
                "tdi_current":            float(_status182.get("tdi_current", 0.0)),
                "persona_break_detected": bool(_status182.get("persona_break_detected", False)),
                "re_enrollment_urgency":  _status182.get("re_enrollment_urgency", "MEDIUM"),
                "n_snapshots_used":       int(_status182.get("n_snapshots_used", 0)),
                "timestamp":              _t182.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # NOTE: The POST /agent/renew-separation-ratio-commitment already exists (Phase 180).
    # Phase 181 adds corpus_delta_detected key to the response — handled inside that endpoint.
    # Phase 180 — POST /agent/renew-separation-ratio-commitment + GET /agent/renewal-chain-status
    # ------------------------------------------------------------------
    @app.post("/agent/renew-separation-ratio-commitment")
    async def renew_separation_ratio_commitment_endpoint(
        ratio: float,
        n_sessions: int,
        n_players: int,
        players_sorted: str = "",
        dry_run: bool = True,
        api_key: str = "",
    ):
        """Biometric Renewal Engine — trigger consent-bound separation ratio renewal (Phase 180).

        When the biometric credential TTL is expired (age_days > biometric_credential_ttl_days),
        the operator triggers this endpoint to compute a new commit_hash, link it to the
        previous commit via prev_commit_hash, and store the chain record.

        New commit hash: SHA-256(prev_hash + ratio_str + N + N_consented + players + ttl_days + ts_ns).
        n_consented read live from get_consent_corpus_coverage() (Phase 163 pattern).
        dry_run=True (default): no chain call; dry_run=False calls SeparationRatioRegistry.renewCommit().

        Returns: renewal_enabled, prev_commit_hash, new_commit_hash, ttl_days,
        dry_run, total_renewals, n_consented, error.
        """
        check_key(api_key)
        check_rate(api_key)
        import hashlib as _hl, time as _t180, struct as _s
        try:
            _ttl_days = float(getattr(cfg, "biometric_credential_ttl_days", 90.0))
            _renewal_enabled = bool(getattr(cfg, "renewal_enabled", False))

            # Read prev commit hash from latest separation_ratio_registry_log
            _age_status = store.get_biometric_credential_age_status(ttl_days=_ttl_days)
            _prev_hash  = str(_age_status.get("commit_hash", ""))

            # Read n_consented live (Phase 163 pattern)
            _consent_cov = store.get_consent_corpus_coverage()
            _n_consented = int(_consent_cov.get("active_consent_count", 0))

            # Compute new hash: SHA-256(prev_hash + ratio_str + N + N_consented + players + ttl_days + ts_ns)
            _ts_ns       = _t180.time_ns()
            _ratio_str   = f"{float(ratio):.6f}"
            _players_str = str(players_sorted) if players_sorted else ""
            _preimage = (
                _prev_hash
                + _ratio_str
                + str(n_sessions)
                + str(_n_consented)
                + _players_str
                + f"{_ttl_days:.1f}"
                + str(_ts_ns)
            ).encode()
            _new_hash = "sha256:" + _hl.sha256(_preimage).hexdigest()

            _on_chain_tx: "str | None" = None
            _error: "str | None" = None

            # Chain call only when renewal_enabled=True AND dry_run=False
            if _renewal_enabled and not dry_run and _prev_hash:
                try:
                    from ..chain import ChainClient as _CC180
                    _chain180 = _CC180(cfg)
                    _ratio_millis = int(float(ratio) * 1000)
                    _on_chain_tx = await _chain180.renew_separation_ratio_commitment(
                        prev_hash_hex=_prev_hash.removeprefix("sha256:"),
                        new_hash_hex=_new_hash.removeprefix("sha256:"),
                        ttl_days=int(_ttl_days),
                        ratio_millis=_ratio_millis,
                        n_sessions=n_sessions,
                        n_consented=_n_consented,
                    )
                except Exception as exc_chain:
                    _error = f"chain call failed: {exc_chain}"
                    _on_chain_tx = None

            # Store renewal chain record
            store.insert_biometric_renewal_chain_log(
                prev_commit_hash=_prev_hash,
                new_commit_hash=_new_hash,
                n_consented=_n_consented,
                n_sessions=n_sessions,
                ttl_days=_ttl_days,
                on_chain_tx=_on_chain_tx,
                dry_run=dry_run,
                renewal_reason="TTL_EXPIRY",
            )

            # Phase 181: Consent-Bound Renewal Provenance — snapshot corpus at renewal time
            _corpus_delta = False
            try:
                import json as _json181
                _active_devices = store.get_active_consent_devices()
                _players_now    = sorted({str(d.get("device_id", "")) for d in _active_devices})
                _players_json   = _json181.dumps(_players_now)
                _revoked_count  = int(_consent_cov.get("revoked_count", 0))
                # Check corpus delta: compare against prior snapshot for same commit if exists
                _prior = store.get_renewal_consent_snapshot(_prev_hash) if _prev_hash else None
                if _prior:
                    _prior_players = _json181.loads(_prior.get("players_consented_json", "[]"))
                    _corpus_delta  = set(_prior_players) != set(_players_now)
                store.insert_renewal_consent_snapshot(
                    new_commit_hash=_new_hash,
                    n_consented=_n_consented,
                    players_json=_players_json,
                    revoked=_revoked_count,
                    delta=_corpus_delta,
                )
            except Exception:
                pass  # non-fatal: provenance snapshot must not block renewal; fail-open: M-1 cleanup 2026-05-16

            _chain_status = store.get_biometric_renewal_chain_status()
            return {
                "renewal_enabled":     _renewal_enabled,
                "prev_commit_hash":    _prev_hash,
                "new_commit_hash":     _new_hash,
                "ttl_days":            _ttl_days,
                "dry_run":             dry_run,
                "total_renewals":      int(_chain_status.get("total_renewals", 0)),
                "n_consented":         _n_consented,
                "corpus_delta_detected": _corpus_delta,
                "error":               _error,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/renewal-chain-status")
    async def get_renewal_chain_status_endpoint(api_key: str = ""):
        """Biometric Renewal Engine — renewal chain status (Phase 180).

        Returns the current state of the biometric renewal commitment chain.
        Shows total_renewals, latest prev/new commit hashes, and ttl_days.
        renewal_enabled=False by default (infrastructure-first).

        Returns: renewal_enabled, total_renewals, latest_renewal_ts,
        prev_commit_hash, new_commit_hash, ttl_days, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            _status180 = store.get_biometric_renewal_chain_status()
            _status180["renewal_enabled"] = bool(getattr(cfg, "renewal_enabled", False))
            return _status180
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    @app.get("/agent/biometric-credential-age")
    async def get_biometric_credential_age_endpoint(api_key: str = ""):
        """Biometric Credential TTL Gate status (Phase 178, WIF-029 W1 closure).

        Checks whether the latest SeparationRatioRegistry.sol commitment has exceeded
        the 90-day biometric TTL. Expired credentials BLOCK tournament authorization
        and require operator-triggered recalibration.

        age_days computed live from the latest separation_ratio_registry_log commit_ts.
        ttl_expired=True when age_days > biometric_credential_ttl_days (default 90).

        Returns: ttl_enabled, commit_hash, commit_ts, age_days, ttl_days,
        ttl_expired, recalibration_required, timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        try:
            from ..tournament_activation_chain_agent import TournamentActivationChainAgent as _TACA
            _taca178 = _TACA(cfg=cfg, store=store, bus=None)
            _result178 = _taca178.check_biometric_credential_ttl()
            return _result178
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Phase 198 — GET /agent/biometric-ttl-scaling-status
    # ------------------------------------------------------------------
    @app.get("/agent/biometric-ttl-scaling-status")
    async def get_biometric_ttl_scaling_endpoint(api_key: str = ""):
        """Biometric TTL Decay Scaling status (Phase 198).

        When biometric_ttl_decay_scaling_enabled=True:
          effective_ttl = base_ttl × (mean_decay_factor / 0.50)
          Clamped to [base_ttl × 0.25, base_ttl × 4.0].
        mean_decay_factor from BP-001 BiometricPrivacyComplianceAgent (Phase 159).

        Returns: effective_ttl_days/base_ttl_days/scaling_factor/
                 mean_decay_factor/scaling_enabled/timestamp.
        """
        check_key(api_key)
        check_rate(api_key)
        import time as _t198
        try:
            _base198    = float(getattr(cfg, "biometric_credential_ttl_days", 90.0))
            _scaling198 = bool(getattr(cfg, "biometric_ttl_decay_scaling_enabled", False))
            _result198  = store.get_effective_biometric_ttl(
                base_ttl_days=_base198, scaling_enabled=_scaling198
            )
            return {**_result198, "timestamp": _t198.time()}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/biometric-snapshot-status")
    async def get_biometric_snapshot_status_endpoint(
        x_api_key: str = Header(default=""),
    ):
        """Read-only summary of biometric_snapshot_log: total snapshots + latest.

        Returns 9 keys: total_snapshots, latest_commitment, feature_dim,
        n_players, ts_ns, on_chain_confirmed, tx_hash, trigger_reason, timestamp.
        """
        check_read_key(x_api_key)
        return await asyncio.to_thread(store.get_biometric_snapshot_status)


