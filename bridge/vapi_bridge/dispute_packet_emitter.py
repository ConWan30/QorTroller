"""Phase O5-MLGA Stage 9 (DISPUTE-PACKET autonomy) — fires on operator override.

Sixth autonomous VPM artifact class. Wires `DISPUTE-PACKET-v1` to fire
on operator-initiated dispute events. Today's concrete trigger is
POST /operator/override-gameplay-context (Phase 235-GAD): an operator
overriding an automatic MENU_DETECTED ruling to ACTIVE_GAMEPLAY is
effectively a dispute against an automated adjudication. The
emission packages the dispute for audit trail.

When real dispute lifecycle infrastructure ships (future phase with
dedicated disputes table), it imports + calls `emit_dispute_packet`
the same way. This module is the wiring point.

Design:
  • Event-driven (no polling). Called from the override endpoint after
    the override is recorded.
  • Fail-open: any failure logs + returns None; never affects the
    operator's override response.
  • One artifact per dispute event.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


_VALID_ADJUDICATOR_AGENTS = ("anchor_sentry", "guardian", "curator")
_VALID_STATUSES = ("open", "under_review", "resolved", "escalated")


def _build_integrity_label(*, status: str) -> Dict[str, Any]:
    return {
        "proof_type":             "VPM-DISPUTE-PACKET",
        "capture_mode":           "live",
        "raw_biometrics_exposed": False,
        "consent_active":         "n/a",
        "zk_verified":            False,
        "on_chain_anchor":        False,
        "proof_weight":           "CHAIN_ONLY",
        "revocation_status":      "active",
        "limitations":            [
            f"Autonomous emission on dispute event (status={status}); "
            "supplements Guardian audit-trail surface, does not "
            "replace it.",
        ],
    }


def _lookup_ruling_commitment(
    *, store, ruling_validation_log_id: int,
) -> str:
    """Pull grind_chain_hash from ruling_validation_log (Phase 235-A
    GIC chain link hash — the canonical per-ruling cryptographic ID).
    Returns "" on any lookup failure (caller synthesizes)."""
    try:
        db_path = getattr(store, "_db_path", None) or getattr(
            store, "db_path", None
        )
        if not db_path:
            return ""
        con = sqlite3.connect(db_path, timeout=2.0)
        try:
            row = con.execute(
                "SELECT grind_chain_hash FROM ruling_validation_log "
                "WHERE id=?",
                (int(ruling_validation_log_id),),
            ).fetchone()
        finally:
            con.close()
        if row and row[0]:
            return str(row[0]).lower().removeprefix("0x")
        return ""
    except Exception:  # noqa: BLE001
        return ""


def emit_dispute_packet(
    *,
    store,
    cfg,
    dispute_id: str,
    ruling_validation_log_id: int = 0,
    tournament_id: int = 0,
    disputed_player_address: str = "0x" + "0" * 40,
    adjudicator_agent_id: str = "guardian",
    evidence_count: int = 1,
    dispute_status: str = "open",
    reason: str = "",
) -> Optional[Dict[str, Any]]:
    """Emit one DISPUTE-PACKET-v1 VPM artifact for the trigger event.

    Returns the manifest dict on success, None on any failure. Never
    raises.
    """
    try:
        if adjudicator_agent_id not in _VALID_ADJUDICATOR_AGENTS:
            log.warning(
                "DISPUTE-PACKET emit: invalid adjudicator=%s; defaulting "
                "to 'guardian'", adjudicator_agent_id,
            )
            adjudicator_agent_id = "guardian"
        if dispute_status not in _VALID_STATUSES:
            log.warning(
                "DISPUTE-PACKET emit: invalid status=%s; defaulting to "
                "'open'", dispute_status,
            )
            dispute_status = "open"

        ts_ns = time.time_ns()

        # Disputed ruling hash — look up from ruling_validation_log;
        # fall back to a synthesized hash if not found (defense for
        # cases where the ruling row was already pruned or the
        # trigger event doesn't reference a ruling row).
        ruling_hex = _lookup_ruling_commitment(
            store=store,
            ruling_validation_log_id=ruling_validation_log_id,
        )
        if not ruling_hex or len(ruling_hex) != 64:
            ruling_hex = hashlib.sha256(
                f"synthetic_ruling:{ruling_validation_log_id}:{ts_ns}"
                .encode("utf-8")
            ).hexdigest()

        # Attestation chain hash — SHA-256 over the dispute provenance
        # signal: dispute_id + reason + ts_ns. Stable per emission.
        attestation_hex = hashlib.sha256(
            json.dumps({
                "dispute_id":  dispute_id,
                "reason":      reason,
                "ts_ns":       ts_ns,
            }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        integrity_label = _build_integrity_label(status=dispute_status)

        snapshot = {
            "vpm_id":                     "DISPUTE-PACKET-v1",
            "dispute_id":                 str(dispute_id),
            "ruling_validation_log_id":   int(ruling_validation_log_id),
            "tournament_id":              int(tournament_id),
            "disputed_player_address":    str(disputed_player_address),
            "disputed_ruling_hash_hex":   ruling_hex,
            "adjudicator_agent_id":       adjudicator_agent_id,
            "evidence_count":             int(evidence_count),
            "attestation_chain_hash_hex": attestation_hex,
            "dispute_status":             dispute_status,
            "reason":                     str(reason)[:200],  # cap
            "ts_ns":                      ts_ns,
        }
        digest = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
            .encode("utf-8")
        ).hexdigest()

        output_dir = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "artifacts" / "dispute_packet"
        )
        import sys as _sys
        _scripts_path = str(
            Path(__file__).resolve().parents[2] / "scripts"
        )
        if _scripts_path not in _sys.path:
            _sys.path.insert(0, _scripts_path)
        from vpm_compile_dispute_packet import (
            build_dispute_packet_artifact,
        )

        manifest = build_dispute_packet_artifact(
            dispute_id=dispute_id,
            tournament_id=tournament_id,
            disputed_player_address=disputed_player_address,
            disputed_ruling_hash_hex=ruling_hex,
            adjudicator_agent_id=adjudicator_agent_id,
            evidence_count=evidence_count,
            attestation_chain_hash_hex=attestation_hex,
            dispute_status=dispute_status,
            created_ts_ns=ts_ns,
            integrity_label=integrity_label,
            zkba_manifest_hash_hex=digest,
            visual_state="live",
            capture_mode="live",
            output_dir=output_dir,
            ts_ns=ts_ns,
        )

        preimage_json = json.dumps(snapshot, sort_keys=True,
                                    separators=(",", ":"))
        row_id = store.insert_vpm_artifact(
            commitment_hex=manifest.output_hash_hex,
            vpm_id="DISPUTE-PACKET-v1",
            zkba_class=5,             # ZKBAClass.CONSENT (Guardian audit family)
            proof_weight=3,           # CHAIN_ONLY
            visual_state="live",
            capture_mode="live",
            integrity_label_hash_hex=manifest.integrity_label_hash_hex,
            wrapper_schema="vapi-vpm-artifact-v1",
            zkba_manifest_hash_hex=digest,
            manifest_uri=manifest.output_path,
            compiler_output_hash_hex=manifest.output_hash_hex,
            preimage_json=preimage_json,
            ts_ns=ts_ns,
        )
        log.info(
            "DISPUTE-PACKET emitted: dispute=%s status=%s row=%d "
            "adjudicator=%s commit=%s...",
            dispute_id, dispute_status, row_id, adjudicator_agent_id,
            manifest.output_hash_hex[:16],
        )
        return {
            "action": "emitted",
            "row": row_id,
            "commitment_hex": manifest.output_hash_hex,
            "dispute_id": dispute_id,
        }
    except Exception as exc:  # noqa: BLE001
        import traceback as _tb
        log.warning(
            "DISPUTE-PACKET emit failed for dispute=%s: %s\n%s",
            dispute_id, exc, _tb.format_exc(),
        )
        return None
