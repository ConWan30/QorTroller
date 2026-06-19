"""Consent + erasure routes (D-DECON-2 operator_api residue #11).

Register-function split per audits/decon-store-map.md agent_consent domain.
Routes byte-identical to the former inline handlers in _app.py.
"""
from __future__ import annotations

import asyncio
import time
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Query


def register_agent_consent_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    chain,
    check_key: Callable[[str], None],
    check_rate: Callable[[str], None],
    check_read_key: Callable[[str], None],
) -> None:
    """Register consent cockpit, ledger, erasure, and Phase 237 category routes."""

    # Consent Cockpit F2 — GET /agent/wallet-devices (2026-06-05)
    @app.get("/agent/wallet-devices")
    async def get_wallet_devices_endpoint(
        wallet: str = "",
        include_vhp: bool = False,
        api_key: str = "",
    ):
        """Wallet → device_id bindings sourced from on-chain registrations."""
        check_key(api_key)
        check_rate(api_key)
        bindings: list[dict] = []
        if wallet:
            try:
                bindings = chain.get_wallet_devices(wallet, include_vhp=include_vhp)
            except Exception:
                bindings = []  # fail-open: cockpit shows no-binding state
        return {
            "wallet":      wallet,
            "bindings":    bindings,
            "include_vhp": bool(include_vhp),
            "timestamp":   time.time(),
        }

    @app.get("/agent/consent-history")
    async def get_consent_history_endpoint(
        device_id: str = "",
        limit: int = 50,
        api_key: str = "",
    ):
        """Consent grant/revoke history for one device_id (Cockpit v1)."""
        check_key(api_key)
        check_rate(api_key)
        _enabled = bool(getattr(cfg, "consent_ledger_enabled", True))
        _entries: list[dict] = []
        if _enabled and device_id:
            try:
                _entries = store.get_consent_history(device_id, limit=limit)
            except Exception:
                _entries = []  # fail-open: cockpit shows empty timeline
        return {
            "device_id":              device_id,
            "consent_ledger_enabled": _enabled,
            "entries":                _entries,
            "timestamp":              time.time(),
        }

    @app.get("/agent/consent-gate-status")
    async def get_consent_gate_status_endpoint(api_key: str = ""):
        """Consent Gate enforcement status (Phase 161 BP-002, WIF-018/020 closure)."""
        check_key(api_key)
        check_rate(api_key)
        try:
            _gate_data = store.get_consent_gate_status()
            _enabled   = bool(getattr(cfg, "consent_ledger_enabled", True))
            return {
                "consent_ledger_enabled": _enabled,
                "gate_active":            _enabled,
                "violations_total":       _gate_data["violations_total"],
                "last_violation_ts":      _gate_data["last_violation_ts"],
                "timestamp":              time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/consent-snapshot-delta")
    async def get_consent_snapshot_delta_endpoint(api_key: str = ""):
        """Consent snapshot delta since last separation ratio commit (Phase 164 WIF-023)."""
        check_key(api_key)
        check_rate(api_key)
        try:
            _snap = store.get_consent_snapshot_delta()
            return {
                "consent_ledger_enabled":  bool(getattr(cfg, "consent_ledger_enabled", True)),
                "found":                   _snap["found"],
                "commit_hash":             _snap["commit_hash"],
                "n_consented_at_commit":   _snap["n_consented_at_commit"],
                "n_consented_live":        _snap["n_consented_live"],
                "delta":                   _snap["delta"],
                "revoked_since_commit":    _snap["revoked_since_commit"],
                "snapshot_ts":             _snap["snapshot_ts"],
                "timestamp":               time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/consent-aware-corpus-status")
    async def get_consent_aware_corpus_status_endpoint(api_key: str = ""):
        """Consent-aware corpus coverage status (Phase 162 WIF-021)."""
        check_key(api_key)
        check_rate(api_key)
        try:
            _cov = store.get_consent_corpus_coverage()
            return {
                "consent_ledger_enabled":    bool(getattr(cfg, "consent_ledger_enabled", True)),
                "active_consent_count":      _cov["active_consent_count"],
                "revoked_count":             _cov["revoked_count"],
                "erasure_requested_count":   _cov["erasure_requested_count"],
                "consent_corpus_defensible": _cov["consent_corpus_defensible"],
                "timestamp":                 time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/consent-status/{device_id}")
    async def get_consent_status_endpoint(device_id: str, api_key: str = ""):
        """Consent Ledger status for a device (Phase 160, BP-002, WIF-018/019)."""
        check_key(api_key)
        check_rate(api_key)
        try:
            _enabled160 = bool(getattr(cfg, "consent_ledger_enabled", True))
            _cstatus    = store.get_consent_status(device_id)
            return {
                "consent_ledger_enabled": _enabled160,
                "consent_given":          _cstatus["consent_given"],
                "consent_ts":             _cstatus["consent_ts"],
                "revoked":                _cstatus["revoked"],
                "erasure_requested":      _cstatus["erasure_requested"],
                "erasure_completed":      _cstatus["erasure_completed"],
                "timestamp":              time.time(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/agent/register-consent")
    async def register_consent_endpoint(
        device_id: str,
        consent_type: str = "biometric_processing",
        api_key: str = "",
    ):
        """Register biometric processing consent for a device (Phase 160, BP-002)."""
        check_key(api_key)
        check_rate(api_key)
        if not getattr(cfg, "consent_ledger_enabled", True):
            raise HTTPException(status_code=422, detail="consent_ledger: disabled")
        try:
            _ts = time.time()
            store.insert_consent_record(
                device_id=device_id,
                consent_type=consent_type,
                consent_given=True,
                consent_ts=_ts,
            )
            return {
                "registered":   True,
                "device_id":    device_id,
                "consent_type": consent_type,
                "consent_ts":   _ts,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/agent/revoke-consent")
    async def revoke_consent_endpoint(
        device_id: str,
        reason: str = "",
        execute_erasure: bool = True,
        api_key: str = "",
    ):
        """Revoke consent and execute GDPR Art.17 erasure for a device (Phase 160, BP-002)."""
        check_key(api_key)
        check_rate(api_key)
        if not getattr(cfg, "consent_ledger_enabled", True):
            raise HTTPException(status_code=422, detail="consent_ledger: disabled")
        try:
            _updated = store.revoke_consent(
                device_id=device_id,
                reason=reason,
            )
            _fields = 0
            _completed = False
            if execute_erasure:
                _fields    = store.mark_erasure_complete(device_id)
                _completed = True
            return {
                "revoked":           _updated,
                "device_id":         device_id,
                "fields_anonymized": _fields,
                "erasure_completed": _completed,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/agent/erasure-certificate")
    async def get_erasure_certificate(
        device_id: str = "",
        x_api_key: str = Header(default=""),
    ):
        """Tool #138 — GDPR Art.17 erasure certificate for a device (Phase 192)."""
        check_read_key(x_api_key)
        if not device_id:
            raise HTTPException(status_code=422, detail="device_id required")
        cert = store.get_erasure_certificate(device_id)
        return {
            "device_id":         device_id,
            "certificate_found": cert is not None,
            "certificate_hash":  cert["certificate_hash"] if cert else None,
            "player_id":         cert["player_id"] if cert else None,
            "post_erasure_ratio": float(cert["post_erasure_ratio"]) if cert else None,
            "anchored":          bool(cert["anchored"]) if cert else False,
            "on_chain_tx_hash":  cert["on_chain_tx_hash"] if cert else None,
            "ts_ns":             int(cert["ts_ns"]) if cert else None,
            "timestamp":         time.time(),
        }

    @app.get("/agent/gamer-consent-status")
    async def get_gamer_consent_status(
        x_api_key: str = Header(default=""),
        device_id: str = Query(default=""),
        category: str = Query(default=""),
    ):
        """Per-category consent state for a device (Phase 237-CONSENT)."""
        check_read_key(x_api_key)
        if not device_id.strip():
            raise HTTPException(422, "device_id query param is required")
        try:
            cat = category.strip() or None
            return await asyncio.to_thread(
                store.get_category_consent_status, device_id, cat
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/operator/record-category-consent")
    async def record_category_consent(
        api_key: str = Query(default=""),
        device_id: str = Query(default=""),
        category: str = Query(default=""),
        ttl_s: int = Query(default=0, ge=0),
        consent_hash: str = Query(default=""),
        reason: str = Query(default=""),
    ):
        """Record per-category consent in the local consent_ledger (Phase 237-CONSENT)."""
        check_key(api_key)
        check_rate(api_key)
        if not device_id.strip():
            raise HTTPException(422, "device_id required")
        _reason = (reason or "").strip()
        if len(_reason) < 10:
            raise HTTPException(
                422, "reason must be at least 10 characters (operator audit field)"
            )
        try:
            row_id = await asyncio.to_thread(
                store.grant_category_consent,
                device_id,
                category,
                ttl_s,
                consent_hash,
                time.time_ns(),
            )
            return {
                "row_id":       int(row_id),
                "device_id":    device_id,
                "category":     category,
                "granted":      True,
                "ttl_s":        int(ttl_s),
                "consent_hash": consent_hash,
                "reason":       _reason,
                "on_chain":     False,
                "timestamp":    time.time(),
            }
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/operator/revoke-category-consent")
    async def revoke_category_consent(
        api_key: str = Query(default=""),
        device_id: str = Query(default=""),
        category: str = Query(default=""),
        reason: str = Query(default=""),
    ):
        """Revoke per-category consent in the local consent_ledger (Phase 237-CONSENT)."""
        check_key(api_key)
        check_rate(api_key)
        if not device_id.strip():
            raise HTTPException(422, "device_id required")
        _reason = (reason or "").strip()
        if len(_reason) < 10:
            raise HTTPException(
                422, "reason must be at least 10 characters (operator audit field)"
            )
        try:
            updated = await asyncio.to_thread(
                store.revoke_category_consent,
                device_id,
                category,
                _reason,
            )
            return {
                "row_updated": bool(updated),
                "device_id":   device_id,
                "category":    category,
                "reason":      _reason,
                "on_chain":    False,
                "timestamp":   time.time(),
            }
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
