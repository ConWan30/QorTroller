"""Retina DePIN Policy Governor — prerequisite qualifications and runtime arm state.

Governs when trio-retina HID binding may run on the DualSense Edge transport path.
Not a perception layer: dynamics stay in ``retina_controller_embedder`` /
``retina_perception``. See ``docs/retina-depin-policy-governor-v1.md``.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

log = logging.getLogger(__name__)

SONY_VID = 0x054C
SONY_EDGE_PID = 0x0DF2
EDGE_PROFILE_ID = "sony_dualshock_edge_v1"
MIN_POLL_RATE_HZ = 900.0
AUDIT_WARN_MAX_AGE_DAYS = 14

_RUNTIME_STATE: "RetinaPolicyState | None" = None


@dataclass(frozen=True, slots=True)
class TransportSnapshot:
    """Injected view of live transport + PCC for qualifier evaluation."""

    is_sim_mode: bool = True
    dualshock_enabled: bool = False
    transport_running: bool = False
    profile_id: str | None = None
    phci_tier: str | None = None
    hid_vendor_id: int = 0
    hid_product_id: int = 0
    poll_rate_hz: float = 0.0
    capture_state: str = "DISCONNECTED"
    device_id_hex: str = ""
    trio_retina_importable: bool = False
    operator_disarmed: bool = False


@dataclass(slots=True)
class RetinaPolicyState:
    armed: bool = False
    arm_source: str = "unarmed"  # manual | auto_edge_connect | unarmed | operator_disarm
    qualifiers: dict[str, str] = field(default_factory=dict)
    effective_perception: bool = False
    effective_fsca: bool = False
    effective_adjudicator: bool = False
    device_id_hex: str = ""
    ts: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "armed": self.armed,
            "arm_source": self.arm_source,
            "qualifiers": dict(self.qualifiers),
            "effective_perception": self.effective_perception,
            "effective_fsca": self.effective_fsca,
            "effective_adjudicator": self.effective_adjudicator,
            "device_id_hex": self.device_id_hex,
            "ts": self.ts,
        }


def _qual(status: str, reason: str = "") -> str:
    return f"{status}:{reason}" if reason else status


def _trio_retina_importable() -> bool:
    try:
        import retina  # noqa: F401
        return True
    except ImportError:
        return False


trio_retina_importable = _trio_retina_importable


def _audit_freshness_warn(repo_root: Path | None = None) -> str:
    """Return WARN reason if cross-oracle audit is stale; empty if OK or missing."""
    root = repo_root or Path(__file__).resolve().parents[2]
    audit_path = root / "audits" / "retina_cross_oracle_latest.json"
    if not audit_path.is_file():
        return "no_audit_artifact"
    try:
        data = json.loads(audit_path.read_text(encoding="utf-8"))
        as_of = str(data.get("as_of") or data.get("generated_at") or "")
        if not as_of:
            return "audit_missing_date"
        # Accept YYYY-MM-DD prefix
        from datetime import datetime, timezone

        dt = datetime.strptime(as_of[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - dt).days
        if age_days > AUDIT_WARN_MAX_AGE_DAYS:
            return f"audit_stale_{age_days}d"
    except Exception as exc:
        return f"audit_parse_error:{exc}"[:80]
    return ""


def evaluate_prerequisites(
    cfg: Any,
    snap: TransportSnapshot,
    *,
    repo_root: Path | None = None,
) -> RetinaPolicyState:
    """Pure qualifier evaluation; does not mutate config or env."""
    ts = time.time()
    quals: dict[str, str] = {}

    pkg_ok = snap.trio_retina_importable or _trio_retina_importable()
    quals["Q-PKG"] = _qual("PASS" if pkg_ok else "FAIL", "trio_retina_missing")

    hw_ok = not snap.is_sim_mode
    quals["Q-HW"] = _qual("PASS" if hw_ok else "FAIL", "sim_mode")

    transport_ok = bool(snap.dualshock_enabled and snap.transport_running)
    quals["Q-TRANSPORT"] = _qual("PASS" if transport_ok else "FAIL")

    vidpid_ok = (
        snap.hid_vendor_id == SONY_VID and snap.hid_product_id == SONY_EDGE_PID
    ) or snap.profile_id is not None
    quals["Q-VIDPID"] = _qual("PASS" if vidpid_ok else "FAIL")

    certified_only = bool(getattr(cfg, "retina_certified_edge_only", True))
    edge_ok = True
    if certified_only:
        edge_ok = (
            snap.profile_id == EDGE_PROFILE_ID
            or (snap.phci_tier or "").upper() == "ATTESTED"
        )
    quals["Q-EDGE"] = _qual("PASS" if edge_ok else "FAIL", snap.profile_id or "unknown")

    cap = (snap.capture_state or "DISCONNECTED").upper()
    pcc_ok = cap in ("NOMINAL", "DEGRADED")
    quals["Q-PCC"] = _qual("PASS" if pcc_ok else "FAIL", cap)

    poll_ok = float(snap.poll_rate_hz) >= MIN_POLL_RATE_HZ
    quals["Q-POLL"] = _qual("PASS" if poll_ok else "FAIL", f"{snap.poll_rate_hz:.0f}hz")

    audit_warn = _audit_freshness_warn(repo_root)
    quals["Q-AUDIT"] = _qual("WARN" if audit_warn else "PASS", audit_warn)

    hard_pass = all(
        q.startswith("PASS") for k, q in quals.items() if k != "Q-AUDIT"
    )
    auto_arm_enabled = bool(getattr(cfg, "retina_policy_auto_arm", True))
    manual = bool(getattr(cfg, "retina_perception_enabled", False))

    if snap.operator_disarmed:
        armed = False
        arm_source = "operator_disarm"
    elif manual:
        armed = True
        arm_source = "manual"
    elif auto_arm_enabled and hard_pass and not snap.is_sim_mode:
        armed = True
        arm_source = "auto_edge_connect"
    else:
        armed = False
        arm_source = "unarmed"

    state = RetinaPolicyState(
        armed=armed,
        arm_source=arm_source,
        qualifiers=quals,
        device_id_hex=snap.device_id_hex,
        ts=ts,
    )
    return resolve_effective_flags(cfg, state)


def resolve_effective_flags(cfg: Any, state: RetinaPolicyState) -> RetinaPolicyState:
    """Apply layered config flags to produce effective_* outputs."""
    manual = bool(getattr(cfg, "retina_perception_enabled", False))
    perception = manual or (state.armed and state.arm_source != "operator_disarm")

    fsca_layer = bool(getattr(cfg, "retina_fsca_cross_oracle_enabled", True))
    adj_layer = bool(getattr(cfg, "retina_adjudicator_context_enabled", True))

    state.effective_perception = perception
    state.effective_fsca = perception and fsca_layer
    state.effective_adjudicator = perception and adj_layer
    return state


def set_runtime_policy_state(state: RetinaPolicyState | None) -> None:
    global _RUNTIME_STATE
    _RUNTIME_STATE = state


def get_runtime_policy_state() -> RetinaPolicyState | None:
    return _RUNTIME_STATE


def is_effective_perception(cfg: Any) -> bool:
    if bool(getattr(cfg, "retina_perception_enabled", False)):
        return True
    state = get_runtime_policy_state()
    return bool(state and state.effective_perception)


def is_effective_fsca(cfg: Any) -> bool:
    if not bool(getattr(cfg, "retina_fsca_cross_oracle_enabled", True)):
        return False
    return is_effective_perception(cfg)


def is_effective_adjudicator(cfg: Any) -> bool:
    if not bool(getattr(cfg, "retina_adjudicator_context_enabled", True)):
        return False
    return is_effective_perception(cfg)


def build_transport_snapshot_from_ds(ds: Any, cfg: Any) -> TransportSnapshot:
    """Build snapshot from DualShockTransport + optional PCC monitor."""
    profile = getattr(ds, "_device_profile", None)
    pcc = getattr(ds, "_pcc_monitor", None)
    poll_rate = 0.0
    capture_state = "DISCONNECTED"
    if pcc is not None:
        try:
            st = pcc.get_status()
            poll_rate = float(st.get("poll_rate_hz") or 0.0)
            capture_state = str(st.get("capture_state") or "DISCONNECTED")
        except Exception:
            pass

    dev_hex = ""
    if getattr(ds, "_device_id", None) is not None:
        dev_hex = ds._device_id.hex()

    return TransportSnapshot(
        is_sim_mode=bool(getattr(ds, "_is_sim_mode", True)),
        dualshock_enabled=bool(getattr(cfg, "dualshock_enabled", False)),
        transport_running=True,
        profile_id=getattr(profile, "profile_id", None) if profile else None,
        phci_tier=getattr(getattr(profile, "phci_tier", None), "name", None),
        hid_vendor_id=int(getattr(profile, "hid_vendor_id", 0) or 0) if profile else 0,
        hid_product_id=(
            int(profile.hid_product_ids[0])
            if profile and getattr(profile, "hid_product_ids", None)
            else 0
        ),
        poll_rate_hz=poll_rate,
        capture_state=capture_state,
        device_id_hex=dev_hex,
        trio_retina_importable=_trio_retina_importable(),
        operator_disarmed=bool(getattr(ds, "_retina_operator_disarmed", False)),
    )


def refresh_policy_from_transport(
    ds: Any,
    cfg: Any,
    *,
    store: Any | None = None,
    repo_root: Path | None = None,
) -> RetinaPolicyState:
    """Evaluate, set runtime state, optionally log arm/disarm transitions."""
    prev = get_runtime_policy_state()
    snap = build_transport_snapshot_from_ds(ds, cfg)
    state = evaluate_prerequisites(cfg, snap, repo_root=repo_root)
    set_runtime_policy_state(state)

    if store is not None and hasattr(store, "insert_retina_policy_log"):
        try:
            prev_armed = bool(prev.armed) if prev else False
            if state.armed != prev_armed:
                store.insert_retina_policy_log(
                    event_type="arm" if state.armed else "disarm",
                    arm_source=state.arm_source,
                    device_id=state.device_id_hex,
                    qualifiers_json=json.dumps(state.qualifiers),
                    effective_perception=state.effective_perception,
                )
        except Exception as exc:
            log.debug("retina_policy_log insert skipped: %s", exc)

    return state


def qualifiers_summary(state: RetinaPolicyState | None) -> str:
    if not state:
        return "uninitialized"
    fails = [k for k, v in state.qualifiers.items() if v.startswith("FAIL")]
    if not fails and state.armed:
        return f"armed:{state.arm_source}"
    if fails:
        return "blocked:" + ",".join(fails[:3])
    return state.arm_source
