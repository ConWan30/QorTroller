"""BCRA — Bridge Connectivity Readiness Aggregator (read-only, packaging-only).

Composes the bridge's already-computed subsystem statuses into ONE coherent connectivity-readiness
attestation across four lanes, so an operator (or a dashboard panel) sees a single honest
"is the bridge fully connected and loaded" view instead of mentally AND-ing ~5 endpoints:

  • CONTROLLER  — capture-health: PCC capture_state + host_state + poll rate (HID/USB to laptop)
  • AGENTS      — fleet coherence + per-agent liveness (the operator agent fleet)
  • CHAIN       — IoTeX RPC reachability + the CHAIN_SUBMISSION_PAUSED kill-switch (honest, not faked)
  • OPERATIONAL — watchdog event chain intact + restart-rate ceiling + GIC chain_intact

See the VSD synthesis note s-bridge-connectivity-aggregator. Sibling shape to provenance_quadrille
(F5) and recency_bound_presence (F2).

WHAT THIS MODULE IS / IS NOT (honesty rails, held across the module):
  • Read-only / packaging ONLY. It READS already-computed subsystem-status dicts; it does NOT
    restart, reconnect, re-init, poll hardware, read the chain, or mutate any subsystem. Callers
    pass the four status dicts (e.g. from get_capture_health_status / fleet coherence / a chain
    reachability probe / get_watchdog_event_chain_status). Fixtures-first, like F2/F5.
  • Honest aggregation is the value-add: a DEGRADED/DISCONNECTED lane can NEVER render the overall
    view as `live`. The CHAIN kill-switch being ON (CHAIN_SUBMISSION_PAUSED) is a TRUE state and
    renders DEGRADED, not green — connectivity must not overclaim.
  • Event-loop safe: composes cached statuses, runs no heavy work on the request path (addresses
    the event_loop_invariants 10s-/health-timeout failure mode).
  • NO new FROZEN-v1 family (no b"VAPI-...-v1" tag; plain SHA-256 packaging digest). NO new PV-CI
    invariant (179 unchanged). SCHEMA is a lowercase packaging string.
  • Does NOT replace the per-subsystem endpoints (they remain authoritative); it COMPOSES them.
    Auto-remediation (reconnect/restart) is OUT of scope — BCRA observes + labels; the operator or
    the watchdog (under its own rate ceiling) acts.

Pure stdlib. Reversible. No chain write, no FROZEN edit.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional

SCHEMA_VERSION = "vapi-bridge-connectivity-v1"   # packaging string (NOT a FROZEN domain tag)

VPM_VISUAL_STATES = ("live", "dry-run", "emulated", "frozen-disabled", "revoked", "unverified")

LANE_ORDER = ("controller", "agents", "chain", "operational")
WATCHDOG_RESTART_CEILING = 3   # mirrors the watchdog rate ceiling (CLAUDE.md hard rule)


class LaneState(str, Enum):
    CONNECTED    = "connected"
    DEGRADED     = "degraded"
    DISCONNECTED = "disconnected"
    UNKNOWN      = "unknown"


class ReadinessVerdict(str, Enum):
    FULLY_CONNECTED     = "fully_connected"      # all four lanes CONNECTED
    DEGRADED            = "degraded"             # some DEGRADED/UNKNOWN, none DISCONNECTED
    PARTIALLY_CONNECTED = "partially_connected"  # at least one lane DISCONNECTED


@dataclass(frozen=True)
class LaneResult:
    state: str       # LaneState value
    evidence: str


def _b(v) -> Optional[bool]:
    return v if isinstance(v, bool) else None


def classify_controller(st: Optional[dict]) -> LaneResult:
    """capture-health: NOMINAL + host EXCLUSIVE_USB/UNKNOWN = connected; DEGRADED/CONTESTED =
    degraded; DISCONNECTED = disconnected; missing = unknown."""
    if not isinstance(st, dict):
        return LaneResult(LaneState.UNKNOWN.value, "controller status absent")
    cap = st.get("capture_state")
    host = st.get("host_state")
    if cap is None:
        return LaneResult(LaneState.UNKNOWN.value, "capture_state missing")
    if cap == "DISCONNECTED":
        return LaneResult(LaneState.DISCONNECTED.value, "capture DISCONNECTED")
    if cap == "NOMINAL" and host in ("EXCLUSIVE_USB", "UNKNOWN"):
        return LaneResult(LaneState.CONNECTED.value, f"NOMINAL on {host}")
    return LaneResult(LaneState.DEGRADED.value, f"capture={cap} host={host}")


def classify_agents(st: Optional[dict]) -> LaneResult:
    """fleet coherence + liveness: coherent and all live = connected; coherent but some down, or
    incoherent = degraded; missing = unknown."""
    if not isinstance(st, dict):
        return LaneResult(LaneState.UNKNOWN.value, "agent fleet status absent")
    coherent = _b(st.get("fleet_coherent"))
    total = st.get("agents_total")
    live = st.get("agents_live")
    if coherent is None or not isinstance(total, int) or not isinstance(live, int):
        return LaneResult(LaneState.UNKNOWN.value, "fleet fields incomplete")
    if coherent and live >= total > 0:
        return LaneResult(LaneState.CONNECTED.value, f"{live}/{total} live, coherent")
    if not coherent:
        return LaneResult(LaneState.DEGRADED.value, f"fleet incoherent ({live}/{total} live)")
    return LaneResult(LaneState.DEGRADED.value, f"only {live}/{total} agents live")


def classify_chain(st: Optional[dict]) -> LaneResult:
    """RPC reachability + kill-switch. Reachable + not paused = connected; reachable + PAUSED =
    DEGRADED (honest: kill-switch on is a true state, not green); unreachable = disconnected."""
    if not isinstance(st, dict):
        return LaneResult(LaneState.UNKNOWN.value, "chain status absent")
    reachable = _b(st.get("rpc_reachable"))
    paused = _b(st.get("submission_paused"))
    if reachable is None:
        return LaneResult(LaneState.UNKNOWN.value, "rpc_reachable missing")
    if not reachable:
        return LaneResult(LaneState.DISCONNECTED.value, "RPC unreachable")
    if paused:
        return LaneResult(LaneState.DEGRADED.value, "RPC reachable; CHAIN_SUBMISSION_PAUSED (kill-switch on)")
    return LaneResult(LaneState.CONNECTED.value, "RPC reachable; submissions enabled")


def classify_operational(st: Optional[dict]) -> LaneResult:
    """watchdog + GIC chains + restart ceiling. A broken watchdog/GIC chain = disconnected
    (integrity break is serious); restarts at/over ceiling = degraded; missing = unknown."""
    if not isinstance(st, dict):
        return LaneResult(LaneState.UNKNOWN.value, "operational status absent")
    wd = _b(st.get("watchdog_chain_intact"))
    gic = _b(st.get("gic_chain_intact"))
    restarts = st.get("restarts_last_hour")
    if wd is None or gic is None or not isinstance(restarts, int):
        return LaneResult(LaneState.UNKNOWN.value, "operational fields incomplete")
    if not wd or not gic:
        broken = "watchdog" if not wd else "GIC"
        return LaneResult(LaneState.DISCONNECTED.value, f"{broken} chain break detected")
    if restarts >= WATCHDOG_RESTART_CEILING:
        return LaneResult(LaneState.DEGRADED.value, f"restarts_last_hour={restarts} >= ceiling")
    return LaneResult(LaneState.CONNECTED.value, f"chains intact, restarts={restarts}")


_CLASSIFIERS = {"controller": classify_controller, "agents": classify_agents,
                "chain": classify_chain, "operational": classify_operational}


def _derive_verdict(lanes: dict) -> ReadinessVerdict:
    states = [lanes[n]["state"] for n in LANE_ORDER]
    if any(s == LaneState.DISCONNECTED.value for s in states):
        return ReadinessVerdict.PARTIALLY_CONNECTED
    if all(s == LaneState.CONNECTED.value for s in states):
        return ReadinessVerdict.FULLY_CONNECTED
    return ReadinessVerdict.DEGRADED


def _derive_visual_state(verdict: ReadinessVerdict) -> str:
    """Anti-overclaim: only an all-lanes-connected bridge earns `live`; else `unverified`."""
    return "live" if verdict == ReadinessVerdict.FULLY_CONNECTED else "unverified"


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class ConnectivityAttestation:
    schema: str
    verdict: str
    visual_state: str
    lanes: dict
    vpm_label: dict
    ts_ns: int
    attestation_hash: str


def assemble_connectivity(controller: Optional[dict], agents: Optional[dict],
                          chain: Optional[dict], operational: Optional[dict],
                          *, ts_ns: int) -> ConnectivityAttestation:
    """Compose the four subsystem statuses into one readiness attestation + a VPM honesty label.
    Read-only: classifies already-computed status; reconnects/restarts nothing."""
    inputs = {"controller": controller, "agents": agents, "chain": chain, "operational": operational}
    lanes = {n: (lambda r: {"state": r.state, "evidence": r.evidence})(_CLASSIFIERS[n](inputs[n]))
             for n in LANE_ORDER}
    verdict = _derive_verdict(lanes)
    visual_state = _derive_visual_state(verdict)

    label_body = {
        "schema": "vsd-vpm-label-v1",            # reuse the shipped VPM honesty-label grammar
        "vpm_id": "QR-BRIDGE-CONNECTIVITY-v1",
        "audience": "operators / dashboard",
        "visual_state": visual_state,
        "capture_mode": "live",
        "proof_weight": 3,                       # CHAIN_ONLY: composes existing status surfaces
        "anchor_status": "none",
        "revocation_status": "active",
        "integrity_label": {
            "proof_type": "BRIDGE-CONNECTIVITY",
            "capture_mode": "live",
            "raw_biometrics_exposed": False,
            "consent_active": True,
            "zk_verified": False,
            "on_chain_anchor": False,
            "proof_weight": 3,
            "revocation_status": "active",
            "limitations": [
                "read-only composition of existing subsystem statuses; not a remediation action",
                "CHAIN kill-switch (CHAIN_SUBMISSION_PAUSED) renders DEGRADED by design, not green",
            ],
        },
        "ts_ns": int(ts_ns),
    }
    label_body["label_hash"] = hashlib.sha256(_canonical(label_body)).hexdigest()

    body = {"schema": SCHEMA_VERSION, "verdict": verdict.value, "visual_state": visual_state,
            "lanes": lanes, "vpm_label": label_body, "ts_ns": int(ts_ns)}
    att_hash = hashlib.sha256(_canonical(body)).hexdigest()
    return ConnectivityAttestation(
        schema=SCHEMA_VERSION, verdict=verdict.value, visual_state=visual_state,
        lanes=lanes, vpm_label=label_body, ts_ns=int(ts_ns), attestation_hash=att_hash)


def verify_attestation(att: dict) -> tuple[bool, str]:
    """Re-verify a serialized connectivity attestation, pure stdlib. Checks (1) canonical hash binds
    the body, (2) visual_state ∈ frozen VPM set, (3) anti-overclaim visual_state == derived(verdict),
    (4) verdict consistent with the lane states, (5) label never claims zk/anchor."""
    if not isinstance(att, dict) or att.get("schema") != SCHEMA_VERSION:
        return False, f"schema not {SCHEMA_VERSION}"
    body = {k: v for k, v in att.items() if k != "attestation_hash"}
    if hashlib.sha256(_canonical(body)).hexdigest() != att.get("attestation_hash"):
        return False, "attestation_hash mismatch (body tampered)"
    if att.get("visual_state") not in VPM_VISUAL_STATES:
        return False, f"visual_state {att.get('visual_state')!r} not in frozen VPM set"
    try:
        verdict = ReadinessVerdict(att.get("verdict"))
    except ValueError:
        return False, f"unknown verdict {att.get('verdict')!r}"
    lanes = att.get("lanes", {})
    if set(lanes) != set(LANE_ORDER):
        return False, "lanes set does not match the four canonical lanes"
    if _derive_verdict(lanes) != verdict:
        return False, "verdict inconsistent with lane states"
    if att.get("visual_state") != _derive_visual_state(verdict):
        return False, f"overclaim: visual_state {att.get('visual_state')!r} != derived"
    il = att.get("vpm_label", {}).get("integrity_label", {})
    if il.get("zk_verified") is not False or il.get("on_chain_anchor") is not False:
        return False, "label must not claim zk_verified or on_chain_anchor"
    return True, f"bridge-connectivity attestation verified (verdict={verdict.value})"
