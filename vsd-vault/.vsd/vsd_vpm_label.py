"""VSD Self-Verifying Loop — VSD-emits-VPM Integrity Label (pure stdlib).

Makes a VSD synthesis cycle wear the protocol's OWN visual-honesty grammar instead of a
bespoke one. The loop already chains provenance (SIC) + signs notes (Ed25519); this adds the
display-honesty layer VPM gives every protocol artifact: a closed-enum Integrity Label so no
session/UI can render the synthesis state as `live` when the harness or PV-CI gate failed.

WHY a VSD-domain schema (`vsd-vpm-label-v1`) and not the protocol VPM wrapper:
  The SIC head is NOT one of the 7 FROZEN `ZKBAClass` values, so `wrap_zkba_manifest()` would
  force it to masquerade as (e.g.) a GIC artifact — a category lie, the exact overclaim VPM
  exists to prevent. Instead we REUSE VPM's honesty primitives (the 6-element visual-state
  vocabulary + the failure-precedence resolver + the 9-field label) under a distinct VSD schema,
  honestly declaring `proof_weight=CHAIN_ONLY`, `zk_verified=False`, `on_chain_anchor=False`.
  This mirrors the established precedent at scripts/vsd_ui_compiler.py:320 (FROZEN visual-state
  strings reproduced as plain strings so a leaf module runs without importing the wrapper).

DEPENDENCY DISCIPLINE: pure stdlib (hashlib/json) — so the ambient MCP verifier runs in the
MCP interpreter, which lacks the bridge + cryptography deps (same rule as vsd_session_attest).
The full-env synthesizer cross-checks our mirrored vocabulary against the FROZEN
VPMVisualState enum (drift guard) when the wrapper is importable; that check is best-effort.

No FROZEN edit, no chain, no ZKBA masquerade. Reversible.
"""
from __future__ import annotations

import hashlib
import json

LABEL_SCHEMA = "vsd-vpm-label-v1"
LABEL_VERSION = "0.1.0"
VPM_ID = "QR-VSD-SIC-v1"
PROOF_TYPE = "VSD-SIC"
PROOF_WEIGHT_CHAIN_ONLY = 3   # mirrors ProofWeightClass.CHAIN_ONLY (zkba_artifact.py): chain-state-only

# Mirror of the FROZEN VPM artifact visual-state vocabulary (scripts/vsd_ui_compiler.py:322,
# hyphen convention of `vapi-vpm-artifact-v1`). Reproduced as plain strings to stay import-free.
# If the FROZEN set ever changes, the synthesizer's best-effort cross-check surfaces the drift.
VPM_VISUAL_STATES = ("live", "dry-run", "emulated", "frozen-disabled", "revoked", "unverified")
VPM_CAPTURE_MODES = ("live", "dry-run", "emulated", "demo", "frozen-disabled")


def derive_vsd_visual_state(harness_pass: bool, pv_ci_pass: bool, dry_run: bool) -> str:
    """Failure-precedence resolver (the anti-overclaim core, mirroring VPM derive_visual_state).
    A failed verification dominates everything — it can never render `live` OR clean `dry-run`."""
    if not harness_pass or not pv_ci_pass:
        return "unverified"          # highest precedence: verification did not pass
    if dry_run:
        return "dry-run"             # passed but not committed → preview, never `live`
    return "live"                    # passed AND committed to the chain


def _canonical(obj) -> bytes:
    """Sorted-key compact UTF-8 JSON — matches VPM vpm_canonical_json discipline."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_vsd_vpm_label(*, sic_head_hex: str, harness_pass: bool, pv_ci_pass: bool,
                        dry_run: bool, ts_ns: int, drift_forecast: dict | None = None) -> dict:
    """Build a deterministic VSD-VPM Integrity Label dict. `label_hash` is SHA-256 of the
    canonical label sans the hash field — recomputable by any party (see verify_vsd_vpm_label)."""
    capture_mode = "dry-run" if dry_run else "live"
    visual_state = derive_vsd_visual_state(harness_pass, pv_ci_pass, dry_run)
    inputs = {"harness_pass": bool(harness_pass), "pv_ci_pass": bool(pv_ci_pass),
              "dry_run": bool(dry_run)}
    integrity_label = {
        "proof_type": PROOF_TYPE,
        "capture_mode": capture_mode,
        "raw_biometrics_exposed": False,      # synthesis provenance; never biometric
        "consent_active": True,               # N/A to methodology notes → not a blocker
        "zk_verified": False,                 # honest: SIC is a hash chain, not a ZK proof
        "on_chain_anchor": False,             # honest: SIC head is local, not anchored
        "proof_weight": PROOF_WEIGHT_CHAIN_ONLY,
        "revocation_status": "active",
        "limitations": [
            "synthesis-domain provenance only; not a ZKBA biometric artifact",
            "local SIC head; not on-chain anchored",
        ],
    }
    body = {
        "schema": LABEL_SCHEMA,
        "label_version": LABEL_VERSION,
        "vpm_id": VPM_ID,
        "audience": "methodology auditors",
        "sic_head_hex": str(sic_head_hex),
        "inputs": inputs,
        "visual_state": visual_state,
        "capture_mode": capture_mode,
        "proof_weight": PROOF_WEIGHT_CHAIN_ONLY,
        "anchor_status": "none",
        "revocation_status": "active",
        "integrity_label": integrity_label,
        "drift_forecast": drift_forecast or {},
        "ts_ns": int(ts_ns),
    }
    body["label_hash"] = hashlib.sha256(_canonical(body)).hexdigest()
    return body


def verify_vsd_vpm_label(label: dict) -> tuple[bool, str]:
    """Re-verify a VSD-VPM label, pure stdlib. Checks: (1) canonical hash binds the body,
    (2) closed-enum membership of visual_state + capture_mode, (3) the anti-overclaim invariant —
    visual_state MUST equal derive(inputs), so a hand-edited `live` over a failed cycle is caught."""
    if not isinstance(label, dict):
        return False, "label not a dict"
    if label.get("schema") != LABEL_SCHEMA:
        return False, f"schema not {LABEL_SCHEMA}"
    stored = label.get("label_hash")
    body = {k: v for k, v in label.items() if k != "label_hash"}
    if hashlib.sha256(_canonical(body)).hexdigest() != stored:
        return False, "label_hash mismatch (body tampered)"
    if label.get("visual_state") not in VPM_VISUAL_STATES:
        return False, f"visual_state {label.get('visual_state')!r} not in frozen VPM set"
    if label.get("capture_mode") not in VPM_CAPTURE_MODES:
        return False, f"capture_mode {label.get('capture_mode')!r} not in frozen VPM set"
    inp = label.get("inputs", {})
    expected = derive_vsd_visual_state(
        bool(inp.get("harness_pass")), bool(inp.get("pv_ci_pass")), bool(inp.get("dry_run")))
    if label.get("visual_state") != expected:
        return False, (f"overclaim: visual_state {label.get('visual_state')!r} "
                       f"!= honesty-derived {expected!r}")
    il = label.get("integrity_label", {})
    if il.get("zk_verified") is not False or il.get("on_chain_anchor") is not False:
        return False, "VSD label must not claim zk_verified or on_chain_anchor"
    return True, f"VSD-VPM label verified (visual_state={expected})"


def forecast_drift(ledger_rows: list[dict], window: int = 5) -> dict:
    """The 'self-predictive' signal: a pure trend extrapolation over the SIC ledger — NOT a model.
    Reads recent mythos_drift / harness_pass and projects whether the next cycle is likely to
    surface drift. Advisory only; honest about being linear trend, not prediction-magic."""
    rows = [r for r in ledger_rows if isinstance(r, dict)][-window:]
    drifts = [r.get("mythos_drift") for r in rows if isinstance(r.get("mythos_drift"), int)]
    fails = sum(1 for r in rows if r.get("harness_pass") is False or r.get("pv_ci_pass") is False)
    if not drifts:
        trend, forecast = "no-data", "unknown"
    else:
        rising = len(drifts) >= 2 and all(b >= a for a, b in zip(drifts, drifts[1:])) and drifts[-1] > drifts[0]
        if drifts[-1] > 0 or rising:
            trend = "rising" if rising else "nonzero"
            forecast = "drift-likely-next-cycle"
        else:
            trend, forecast = "clean", "clean-projected"
    return {
        "window": len(rows),
        "recent_mythos_drift": drifts,
        "recent_verification_fails": fails,
        "trend": trend,
        "forecast": forecast,
        "basis": "linear trend over SIC ledger; advisory only, not a predictive model",
    }
