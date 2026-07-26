"""QorTroller × Trio-Retina — bridge advisory perception (Phase B).

Pure orchestration over ``retina_controller_embedder``; persistence via Store.
Default OFF — ``retina_perception_enabled=False`` until operator enables.

ENHANCED: ONNX Runtime + OpenVINO CPU-optimized inference bridge integration.
Dual-Lobe Causal-Coherence framework adds Thread C isolation for trajectory-authenticity
model inference, resolving F-HW-1 throughput bottleneck and event-loop starvation.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .retina_controller_embedder import (
    DEFAULT_DYNAMICS_HORIZON,
    DEFAULT_WINDOW,
    EVT_TRAJECTORY_ANOMALOUS,
    EmbedResult,
    embed_controller_window,
)
from .retina_events_root import EVENTS_ROOT_SCHEME_POSEIDON_V1, EVENTS_ROOT_SCHEME_SHA256_V1
from .retina_state_commitment import EventsRootScheme, compute_retina_state_commitment
from .retina_onnx_bridge import ONNXInferenceSession, create_onnx_bridge

log = logging.getLogger(__name__)

SCHEMA_TAG = "vapi-retina-event-v1"

RULE_RETINA_TRAJECTORY_WITHOUT_L4 = "RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY"
RULE_L4_ANOMALY_WITHOUT_RETINA = "L4_ANOMALY_WITHOUT_RETINA_SIGNAL"


@dataclass(slots=True)
class RetinaPerceptionResult:
    enabled: bool
    source_id: str
    event_count: int = 0
    anomaly_count: int = 0
    trajectory_anomalies: int = 0
    world_state_json: str = ""
    record_hash_hex: str = ""
    state_commitment_hex: str = ""
    ts_ns: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    # Enhanced fields for Dual-Lobe framework
    onnx_inference_enabled: bool = False
    onnx_latency_ms: float = 0.0
    onnx_trajectory_features: Optional[str] = None  # JSON-serialized features


def _snap_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, Mapping):
        return dict(obj)
    return {
        "right_stick_x": int(getattr(obj, "right_stick_x", 128)),
        "right_stick_y": int(getattr(obj, "right_stick_y", 128)),
        "left_stick_x": int(getattr(obj, "left_stick_x", 128)),
        "left_stick_y": int(getattr(obj, "left_stick_y", 128)),
        "l2_trigger": int(getattr(obj, "l2_trigger", 0)),
        "r2_trigger": int(getattr(obj, "r2_trigger", 0)),
        "gyro_x": float(getattr(obj, "gyro_x", 0.0)),
        "gyro_y": float(getattr(obj, "gyro_y", 0.0)),
        "gyro_z": float(getattr(obj, "gyro_z", 0.0)),
        "accel_x": float(getattr(obj, "accel_x", 0.0)),
        "accel_y": float(getattr(obj, "accel_y", 0.0)),
        "accel_z": float(getattr(obj, "accel_z", 1.0)),
    }


def _event_to_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "to_dict"):
        return event.to_dict()
    return dict(event)


def run_controller_perception(
    snap_buffer: Sequence[Any],
    *,
    enabled: bool,
    source_id: str,
    window: int = DEFAULT_WINDOW,
    dynamics_horizon: int = DEFAULT_DYNAMICS_HORIZON,
    record_hash_hex: str = "",
    events_root_scheme: EventsRootScheme = EVENTS_ROOT_SCHEME_SHA256_V1,
    onnx_bridge: Optional[ONNXInferenceSession] = None,
    l0_poll_rate_hz: float = 1000.0,
) -> RetinaPerceptionResult:
    """Encode the trailing HID window; fail-open when disabled or buffer short."""
    ts_ns = time.time_ns()
    if not enabled:
        return RetinaPerceptionResult(enabled=False, source_id=source_id, ts_ns=ts_ns)
    if len(snap_buffer) < window:
        return RetinaPerceptionResult(
            enabled=True,
            source_id=source_id,
            ts_ns=ts_ns,
            error=f"buffer_short:{len(snap_buffer)}<{window}",
        )
    try:
        chunk = [_snap_dict(s) for s in snap_buffer[-window:]]
        embed: EmbedResult = embed_controller_window(
            chunk,
            source_id=source_id,
            dynamics_horizon=dynamics_horizon,
        )
        events = [_event_to_dict(e) for e in embed.events]
        traj = sum(1 for e in embed.events if e.type == EVT_TRAJECTORY_ANOMALOUS)
        ws_json = json.dumps(embed.world_state.to_dict(), separators=(",", ":"))
        dev_for_commit = record_hash_hex[:32] if record_hash_hex else source_id
        commitment = compute_retina_state_commitment(
            dev_for_commit if len(dev_for_commit) >= 32 else source_id,
            ts_ns,
            events,
            events_root_scheme=events_root_scheme,
        )
        
        # Enhanced: ONNX Runtime inference with Thread C isolation
        onnx_enabled = False
        onnx_latency = 0.0
        onnx_features = None
        
        if onnx_bridge is not None:
            # Update L0 poll rate for Thread C safety monitoring
            onnx_bridge.update_l0_poll_rate(l0_poll_rate_hz)
            
            # Run trajectory-authenticity inference in Thread C
            onnx_result = onnx_bridge.run_trajectory_inference(
                chunk, 
                use_thread_c=True
            )
            
            onnx_enabled = onnx_result.error == ""
            onnx_latency = onnx_result.latency_ms
            
            if onnx_enabled and onnx_result.trajectory_features is not None:
                # Serialize features to JSON for result (fail-open on serialization error)
                try:
                    import numpy as np
                    onnx_features = json.dumps(
                        onnx_result.trajectory_features.tolist(),
                        separators=(",", ":")
                    )
                except Exception:
                    onnx_features = None
            elif onnx_result.error:
                log.debug(f"ONNX inference failed (expected if model unavailable): {onnx_result.error}")
        
        return RetinaPerceptionResult(
            enabled=True,
            source_id=source_id,
            event_count=len(events),
            anomaly_count=embed.anomaly_count,
            trajectory_anomalies=traj,
            world_state_json=ws_json,
            record_hash_hex=record_hash_hex,
            state_commitment_hex=commitment,
            ts_ns=ts_ns,
            events=events,
            onnx_inference_enabled=onnx_enabled,
            onnx_latency_ms=onnx_latency,
            onnx_trajectory_features=onnx_features,
        )
    except Exception as exc:
        log.warning("retina perception fail-open: %s", exc)
        return RetinaPerceptionResult(
            enabled=True,
            source_id=source_id,
            ts_ns=ts_ns,
            error=str(exc)[:200],
        )


def persist_retina_result(
    store: Any,
    device_id: str,
    result: RetinaPerceptionResult,
    *,
    source: str = "hid",
    cfg: Any = None,
) -> None:
    """Write events to retina_event_log + agent_events bus (fail-open)."""
    if not result.enabled or result.error or not result.events:
        return
    row_id = 0
    try:
        if hasattr(store, "insert_retina_event_batch"):
            row_id = store.insert_retina_event_batch(
                device_id=device_id,
                events_json=json.dumps(result.events),
                world_state_json=result.world_state_json,
                record_hash_hex=result.record_hash_hex,
                anomaly_count=result.anomaly_count,
                state_commitment_hex=result.state_commitment_hex,
                ts_ns=result.ts_ns,
                source=source,
            )
    except Exception as exc:
        log.warning("retina_event_log insert failed: %s", exc)
        return
    if row_id and result.state_commitment_hex:
        try:
            from .provenance_nodes import register_retina_provenance_node

            register_retina_provenance_node(
                store,
                row_id,
                result.record_hash_hex,
                result.state_commitment_hex,
            )
        except Exception as exc:
            log.debug("retina provenance sync skipped: %s", exc)
    try:
        from .retina_w3bstream import maybe_validate_after_persist

        w3s_result: dict[str, Any] = {}
        if cfg is not None:
            w3s_result = maybe_validate_after_persist(
                store,
                cfg,
                device_id=device_id,
                record_hash_hex=result.record_hash_hex,
                state_commitment_hex=result.state_commitment_hex,
                events=result.events,
            )
    except Exception as exc:
        log.debug("retina w3bstream post-persist skipped: %s", exc)
        w3s_result = {}
    try:
        from .retina_da_upload import maybe_upload_retina_to_da

        if cfg is not None:
            maybe_upload_retina_to_da(
                store,
                cfg,
                device_id=device_id,
                record_hash_hex=result.record_hash_hex,
                state_commitment_hex=result.state_commitment_hex,
                events=result.events,
                world_state_json=result.world_state_json,
                ts_ns=result.ts_ns,
                w3bstream_exit_code=int(w3s_result.get("exit_code", 0)),
            )
    except Exception as exc:
        log.debug("retina DA upload post-persist skipped: %s", exc)
    try:
        from .retina_da_witness import maybe_upload_retina_witness_to_da
        from .retina_events_root import (
            EVENTS_ROOT_SCHEME_POSEIDON_V1,
            EVENTS_ROOT_SCHEME_SHA256_V1,
        )

        if cfg is not None:
            _root_scheme = (
                EVENTS_ROOT_SCHEME_POSEIDON_V1
                if bool(getattr(cfg, "retina_events_root_poseidon_enabled", False))
                else EVENTS_ROOT_SCHEME_SHA256_V1
            )
            maybe_upload_retina_witness_to_da(
                store,
                cfg,
                device_id=device_id,
                record_hash_hex=result.record_hash_hex,
                state_commitment_hex=result.state_commitment_hex,
                events=result.events,
                ts_ns=result.ts_ns,
                w3bstream_exit_code=int(w3s_result.get("exit_code", 0)),
                events_root_scheme=_root_scheme,
            )
    except Exception as exc:
        log.debug("retina DA witness post-persist skipped: %s", exc)
    try:
        from .retina_pda_attestation import maybe_record_retina_pda_attestation
        from .retina_w3bstream import EXIT_OK as _EXIT_OK

        if cfg is not None:
            maybe_record_retina_pda_attestation(
                store,
                cfg,
                device_id=device_id,
                state_commitment_hex=result.state_commitment_hex,
                ts_ns=result.ts_ns,
                w3bstream_exit_code=int(w3s_result.get("exit_code", _EXIT_OK)),
            )
    except Exception as exc:
        log.debug("retina PDA attestation post-persist skipped: %s", exc)
    if result.trajectory_anomalies > 0 and hasattr(store, "write_agent_event"):
        try:
            store.write_agent_event(
                event_type="retina_trajectory_anomaly",
                payload=json.dumps(
                    {
                        "schema": SCHEMA_TAG,
                        "device_id": device_id,
                        "count": result.trajectory_anomalies,
                        "record_hash": result.record_hash_hex,
                        "state_commitment": result.state_commitment_hex,
                        "ts_ns": result.ts_ns,
                    }
                ),
                source="retina_perception",
                device_id=device_id,
                target="bridge_agent",
            )
        except Exception as exc:
            log.warning("retina agent_event insert failed: %s", exc)


def _row_to_binding(row: dict[str, Any]) -> dict[str, Any]:
    """Map a retina_event_log row to adjudicator evidence binding shape."""
    event_count = 0
    try:
        event_count = len(json.loads(row.get("events_json") or "[]"))
    except (json.JSONDecodeError, TypeError):
        pass
    return {
        "record_hash": row.get("record_hash_hex", "") or "",
        "state_commitment": row.get("state_commitment_hex", "") or "",
        "anomaly_count": int(row.get("anomaly_count") or 0),
        "event_count": event_count,
        "created_at": float(row.get("created_at") or 0.0),
    }


def _empty_retina_evidence_slice(*, enabled: bool = False) -> dict[str, Any]:
    return {
        "schema": SCHEMA_TAG,
        "enabled": enabled,
        "bindings": [],
        "aggregate": {
            "total_trajectory_anomalies": 0,
            "latest_state_commitment": "",
            "rows_matched": 0,
        },
    }


def classify_cross_oracle_window(
    l4_mahalanobis: float | None,
    retina_anomaly_count: int,
    *,
    l4_anomaly_threshold: float,
    l4_continuity_threshold: float,
) -> list[str]:
    """Return FSCA rule names that would fire for this window (dry-run classifier)."""
    if l4_mahalanobis is None:
        return []
    fired: list[str] = []
    if retina_anomaly_count > 0 and l4_mahalanobis < l4_continuity_threshold:
        fired.append(RULE_RETINA_TRAJECTORY_WITHOUT_L4)
    if l4_mahalanobis >= l4_anomaly_threshold and retina_anomaly_count == 0:
        fired.append(RULE_L4_ANOMALY_WITHOUT_RETINA)
    return fired


def build_retina_evidence_slice(
    store: Any,
    device_id: str,
    *,
    record_hashes: list[str] | None = None,
    limit: int = 10,
    enabled: bool | None = None,
) -> dict[str, Any]:
    """Read-only Retina cross-oracle slice for SessionAdjudicator evidence_json."""
    try:
        bindings: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()

        if record_hashes:
            for rh in record_hashes[: max(1, limit)]:
                if not rh or rh in seen_hashes:
                    continue
                seen_hashes.add(rh)
                if hasattr(store, "get_retina_by_record_hash"):
                    row = store.get_retina_by_record_hash(rh)
                    if row:
                        bindings.append(_row_to_binding(row))
        elif hasattr(store, "get_retina_event_status"):
            status = store.get_retina_event_status(device_id, limit=limit)
            for row in status.get("entries") or []:
                bindings.append(_row_to_binding(row))

        total_anomalies = sum(b["anomaly_count"] for b in bindings)
        latest_commitment = bindings[0]["state_commitment"] if bindings else ""
        slice_enabled = enabled if enabled is not None else bool(bindings)

        return {
            "schema": SCHEMA_TAG,
            "enabled": slice_enabled,
            "bindings": bindings,
            "aggregate": {
                "total_trajectory_anomalies": total_anomalies,
                "latest_state_commitment": latest_commitment,
                "rows_matched": len(bindings),
            },
        }
    except Exception as exc:
        log.warning("build_retina_evidence_slice fail-open: %s", exc)
        return _empty_retina_evidence_slice(enabled=bool(enabled))
