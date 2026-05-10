"""Phase O1 C2 — In-process Cedar shadow runtime.

When an Operator Agent attempts a skill (read, kms-sign, ipfs-pin, etc.)
the runtime evaluates the action against the agent's currently-anchored
Cedar bundle and persists the decision to operator_agent_shadow_log.

In O1_SHADOW phase, NOTHING IS ENFORCED.  The runtime returns a CedarDecision
which higher-level call sites are expected to log + observe but not act on.
This is the deliberate design: shadow mode collects empirical decision-pattern
data so the operator can decide on Phase O2_SUGGEST advancement (where
suggested-only diffs land) and Phase O3_AUTONOMOUS later (where decisions
gate skill execution).

PRIMITIVE INVARIANTS
====================

INV-OPERATOR-AGENT-004 (FROZEN per PV-CI):
  evaluate_agent_action() FAILS OPEN.  Any error path (bundle missing,
  parse failure, store error) returns the safe-default decision
  CedarDecision.FORBID_DEFAULT_DENY but does NOT raise.  Higher-level
  call sites must NEVER assume action permission from this runtime —
  caller is always responsible for what to do with the decision.

INV-OPERATOR-AGENT-005 (FROZEN per PV-CI):
  Bundle Merkle root is recomputed at every evaluation (not cached).
  This makes BUNDLE_HASH_DRIFT (FSCA rule, Phase O1 C3) detectable —
  if the bundle file is mutated post-anchor, evaluations will use the
  mutated content but the recomputed Merkle root will not match the
  on-chain anchored root.  FSCA correlates the two at the next sweep
  and surfaces the drift.

ARCHITECTURE
============

Single async entrypoint `evaluate_agent_action()`:
  1. Resolve cedar_bundles/{bundle_filename} path from cfg
  2. Load + canonicalize JSON
  3. Recompute Merkle root via cedar_parser.bundle_merkle_root()
  4. Parse via cedar_parser.parse_bundle()
  5. Evaluate via cedar_parser.evaluate(agent_id, action, resource, context)
  6. Persist via store.insert_operator_agent_shadow_log()
  7. Return ShadowEvalResult slotted dataclass

draft_payload_hash is provided by caller (e.g., the proposed kms-sign
content's SHA-256) — the runtime does NOT generate or interpret payloads.
Pass "" if no payload exists.

source field tags the call site origin (e.g., "operator_endpoint",
"agent_loop", "test") for shadow-log analytics.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .cedar_parser import (
    CedarDecision,
    bundle_merkle_root,
    canonical_bytes,
    evaluate,
    parse_bundle,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ShadowEvalResult:
    """Result of one Cedar evaluation in shadow mode."""

    agent_id: str
    action: str
    resource: str
    decision: CedarDecision
    bundle_merkle_root_hex: str
    bundle_path: str
    shadow_log_row_id: int
    error: Optional[str] = None

    @property
    def is_permit(self) -> bool:
        return self.decision in (
            CedarDecision.PERMIT,
            CedarDecision.PERMIT_WITH_SHADOW_CONSTRAINT,
        )

    @property
    def is_forbid(self) -> bool:
        return not self.is_permit


def _bundle_path_for_agent(agent_id_hex: str, cfg) -> Optional[Path]:
    """Resolve the agent's Cedar bundle file by Q9-frozen agentId.

    Reads cfg.operator_agent_anchor_sentry_id + cfg.operator_agent_guardian_id
    + cfg.operator_agent_curator_id + cfg.cedar_bundle_dir to map agent_id →
    bundle filename.  Returns None when no mapping found (caller fail-opens).

    Phase O1-CURATOR C2 (2026-05-09): Curator added as third agent.  Its
    bundle (curator_o1_shadow_v1.json) lives in the same cedar_bundles/
    directory and is resolved by the same pattern.  Curator's architectural
    divergence (MockKMSClient testnet path vs Sentry/Guardian's GitHub App
    + AWS KMS) does NOT affect bundle resolution — that divergence is at
    the attestation-signing layer (kms-sign action), not at policy
    evaluation.
    """
    sentry_id = str(getattr(cfg, "operator_agent_anchor_sentry_id", "") or "").lower()
    guardian_id = str(getattr(cfg, "operator_agent_guardian_id", "") or "").lower()
    curator_id = str(getattr(cfg, "operator_agent_curator_id", "") or "").lower()
    bundle_dir = str(getattr(cfg, "cedar_bundle_dir", "bridge/vapi_bridge/cedar_bundles") or "")
    aid_lower = agent_id_hex.lower()
    if aid_lower == sentry_id:
        return Path(bundle_dir) / "anchor_sentry_o1_shadow_v1.json"
    if aid_lower == guardian_id:
        return Path(bundle_dir) / "guardian_o1_shadow_v1.json"
    if aid_lower == curator_id:
        return Path(bundle_dir) / "curator_o1_shadow_v1.json"
    return None


def _safe_decision_value(d: CedarDecision) -> str:
    """Stringify CedarDecision for SQLite + JSON."""
    try:
        return str(d.value)
    except Exception:
        return str(d)


async def evaluate_agent_action(
    *,
    agent_id: str,
    action: str,
    resource: str,
    context: Optional[dict] = None,
    draft_payload_hash: str = "",
    source: str = "evaluate_agent_action",
    cfg,
    store,
) -> ShadowEvalResult:
    """Evaluate one (agent, action, resource, context) tuple in shadow mode.

    Always returns a ShadowEvalResult — never raises.  On any error path,
    decision = FORBID_DEFAULT_DENY (safest possible default), error field is
    populated with a short reason, and a shadow log row IS still written
    so the failure is auditable.

    Args:
        agent_id:           Q9-frozen agent identity hex (with 0x prefix)
        action:             Cedar action string ("category:name")
        resource:           Cedar resource (typically "lane://...")
        context:            Optional runtime context dict (shadow_mode flag, etc.)
        draft_payload_hash: SHA-256 of the proposed payload, or ""
        source:             Call-site identifier for telemetry
        cfg:                Bridge config (must expose cedar_bundle_dir +
                            operator_agent_anchor_sentry_id +
                            operator_agent_guardian_id)
        store:              Bridge store (must expose
                            insert_operator_agent_shadow_log)
    """
    ctx = context if isinstance(context, dict) else {}
    context_json = json.dumps(ctx, sort_keys=True, separators=(",", ":"))

    # --- Resolve bundle ---
    bundle_path = _bundle_path_for_agent(agent_id, cfg)
    if bundle_path is None:
        # No mapping for this agent — fail-open, log + deny.
        return _persist_and_return(
            store=store,
            agent_id=agent_id,
            action=action,
            resource=resource,
            context_json=context_json,
            decision=CedarDecision.FORBID_DEFAULT_DENY,
            bundle_merkle_root_hex="",
            bundle_path="",
            draft_payload_hash=draft_payload_hash,
            source=source,
            error="no_bundle_mapping_for_agent_id",
        )

    if not bundle_path.exists():
        return _persist_and_return(
            store=store,
            agent_id=agent_id,
            action=action,
            resource=resource,
            context_json=context_json,
            decision=CedarDecision.FORBID_DEFAULT_DENY,
            bundle_merkle_root_hex="",
            bundle_path=str(bundle_path),
            draft_payload_hash=draft_payload_hash,
            source=source,
            error="bundle_file_missing",
        )

    # --- Load + parse ---
    try:
        raw_text = bundle_path.read_text(encoding="utf-8")
        raw_obj = json.loads(raw_text)
    except Exception as exc:
        return _persist_and_return(
            store=store,
            agent_id=agent_id,
            action=action,
            resource=resource,
            context_json=context_json,
            decision=CedarDecision.FORBID_DEFAULT_DENY,
            bundle_merkle_root_hex="",
            bundle_path=str(bundle_path),
            draft_payload_hash=draft_payload_hash,
            source=source,
            error=f"bundle_load_failed: {type(exc).__name__}",
        )

    # INV-OPERATOR-AGENT-005: recompute Merkle root every evaluation,
    # not cached — required for FSCA BUNDLE_HASH_DRIFT detection.
    try:
        merkle_root_bytes = bundle_merkle_root(raw_obj)
        merkle_hex = "0x" + merkle_root_bytes.hex()
    except Exception as exc:
        return _persist_and_return(
            store=store,
            agent_id=agent_id,
            action=action,
            resource=resource,
            context_json=context_json,
            decision=CedarDecision.FORBID_DEFAULT_DENY,
            bundle_merkle_root_hex="",
            bundle_path=str(bundle_path),
            draft_payload_hash=draft_payload_hash,
            source=source,
            error=f"merkle_compute_failed: {type(exc).__name__}",
        )

    try:
        parsed = parse_bundle(raw_obj)
    except Exception as exc:
        return _persist_and_return(
            store=store,
            agent_id=agent_id,
            action=action,
            resource=resource,
            context_json=context_json,
            decision=CedarDecision.FORBID_DEFAULT_DENY,
            bundle_merkle_root_hex=merkle_hex,
            bundle_path=str(bundle_path),
            draft_payload_hash=draft_payload_hash,
            source=source,
            error=f"bundle_parse_failed: {type(exc).__name__}",
        )

    # --- Evaluate ---
    try:
        decision = evaluate(
            parsed,
            agent_id=agent_id,
            action=action,
            resource=resource,
            context=ctx,
        )
    except Exception as exc:
        return _persist_and_return(
            store=store,
            agent_id=agent_id,
            action=action,
            resource=resource,
            context_json=context_json,
            decision=CedarDecision.FORBID_DEFAULT_DENY,
            bundle_merkle_root_hex=merkle_hex,
            bundle_path=str(bundle_path),
            draft_payload_hash=draft_payload_hash,
            source=source,
            error=f"evaluate_raised: {type(exc).__name__}",
        )

    return _persist_and_return(
        store=store,
        agent_id=agent_id,
        action=action,
        resource=resource,
        context_json=context_json,
        decision=decision,
        bundle_merkle_root_hex=merkle_hex,
        bundle_path=str(bundle_path),
        draft_payload_hash=draft_payload_hash,
        source=source,
        error=None,
    )


def _persist_and_return(
    *,
    store,
    agent_id: str,
    action: str,
    resource: str,
    context_json: str,
    decision: CedarDecision,
    bundle_merkle_root_hex: str,
    bundle_path: str,
    draft_payload_hash: str,
    source: str,
    error: Optional[str],
) -> ShadowEvalResult:
    """Persist the evaluation row + return the result.

    Persistence failure does NOT raise — logged then row_id=0 returned.
    """
    decision_str = _safe_decision_value(decision)
    row_id = 0
    try:
        row_id = int(
            store.insert_operator_agent_shadow_log(
                agent_id=agent_id,
                action=action,
                resource=resource,
                context_json=context_json,
                decision=decision_str,
                bundle_merkle_root=bundle_merkle_root_hex,
                bundle_path=bundle_path,
                draft_payload_hash=draft_payload_hash,
                source=source,
            )
        )
    except Exception as exc:
        log.warning(
            "Phase O1 C2: shadow_log persist failed agent=%s action=%s: %s",
            agent_id[:18], action, exc,
        )
    return ShadowEvalResult(
        agent_id=agent_id,
        action=action,
        resource=resource,
        decision=decision,
        bundle_merkle_root_hex=bundle_merkle_root_hex,
        bundle_path=bundle_path,
        shadow_log_row_id=row_id,
        error=error,
    )


# ----------------------------------------------------------------------
# Phase O1 C3 — Drift detection (operator-triggered sweep primitive).
# ----------------------------------------------------------------------
#
# Two FROZEN drift signatures audit the Operator Agent integrity surface:
#
#   BUNDLE_HASH_DRIFT
#     Recompute Merkle root from cedar_bundles/{agent}_{phase}_v1.json
#     vs the to_scope_root in the agent's most recent activation_log row.
#     CRITICAL — means someone modified the bundle file post-anchor without
#     re-anchoring, breaking the on-chain → off-chain provenance chain.
#
#   SCOPE_HASH_GOVERNANCE_DRIFT
#     AgentScope.getScopeRoot(agent_id) vs AgentRegistry.getAgent(agent_id)
#     .scopeHash on chain.
#     CRITICAL — operational and governance layers should be byte-identical
#     per D4 dual-anchor invariant.  Divergence means one tx landed and the
#     other did not (partial anchor) OR one was overwritten without the
#     other.
#
# Both checks are operator-triggered (no auto-sweep loop in C3 — operator
# decides cadence) and write findings to operator_agent_drift_log.  FSCA
# wiring deferred to Phase O1 D once architectural support for non-SQL
# rules lands.
# ----------------------------------------------------------------------

import hashlib as _hl
import secrets as _secrets


@dataclass(frozen=True, slots=True)
class DriftFinding:
    """One drift event detected by a sweep."""

    agent_id: str
    drift_type: str          # "BUNDLE_HASH_DRIFT" | "SCOPE_HASH_GOVERNANCE_DRIFT"
    expected_value: str      # the anchored truth
    actual_value: str        # the observed (drifted) value
    bundle_path: str
    evidence_json: str
    drift_log_row_id: int


@dataclass(frozen=True, slots=True)
class DriftSweepResult:
    """Aggregate result of one drift sweep cycle."""

    sweep_id: str
    agents_checked: int
    findings: list[DriftFinding]
    error: Optional[str] = None

    @property
    def clean(self) -> bool:
        return not self.findings


def _sweep_id() -> str:
    """Generate an opaque sweep identifier (8-byte hex)."""
    return _secrets.token_hex(8)


def detect_bundle_hash_drift(
    *, cfg, store, sweep_id: Optional[str] = None,
) -> DriftSweepResult:
    """Recompute Merkle root from each agent's bundle file vs anchored value.

    For each known operator agent, read the most-recent activation_log row,
    load the bundle file, recompute the Merkle root, and compare. Any
    mismatch is a BUNDLE_HASH_DRIFT finding written to operator_agent_drift_log.

    Returns DriftSweepResult — never raises (fail-open per
    INV-OPERATOR-AGENT-004 spirit; sweep that fails is a finding itself).
    """
    sid = sweep_id or _sweep_id()
    findings: list[DriftFinding] = []

    sentry_id = str(getattr(cfg, "operator_agent_anchor_sentry_id", "") or "").lower()
    guardian_id = str(getattr(cfg, "operator_agent_guardian_id", "") or "").lower()
    candidates = [aid for aid in (sentry_id, guardian_id) if aid]

    for aid in candidates:
        try:
            rows = store.get_operator_agent_activation_log(aid, limit=1)
        except Exception as exc:
            log.warning(
                "Phase O1 C3: BUNDLE_HASH_DRIFT lookup failed agent=%s: %s",
                aid[:18], exc,
            )
            continue
        if not rows:
            # Agent not yet activated — no anchored truth to compare against; skip.
            continue
        anchored = rows[0]
        anchored_root = str(anchored.get("to_scope_root") or "").lower()
        bundle_path_str = str(anchored.get("bundle_path") or "")
        bundle_path = Path(bundle_path_str)
        if not bundle_path.exists():
            ev = json.dumps({
                "reason": "bundle_file_missing",
                "anchored_to_scope_root": anchored_root,
                "anchored_at": anchored.get("activated_at"),
            }, sort_keys=True, separators=(",", ":"))
            row_id = _persist_drift(
                store, aid, "BUNDLE_HASH_DRIFT",
                anchored_root, "<file_missing>", str(bundle_path), ev, sid,
            )
            findings.append(DriftFinding(
                agent_id=aid,
                drift_type="BUNDLE_HASH_DRIFT",
                expected_value=anchored_root,
                actual_value="<file_missing>",
                bundle_path=str(bundle_path),
                evidence_json=ev,
                drift_log_row_id=row_id,
            ))
            continue
        try:
            raw = json.loads(bundle_path.read_text(encoding="utf-8"))
            recomputed = "0x" + bundle_merkle_root(raw).hex()
        except Exception as exc:
            ev = json.dumps({
                "reason": f"bundle_recompute_failed: {type(exc).__name__}",
                "anchored_to_scope_root": anchored_root,
            }, sort_keys=True, separators=(",", ":"))
            row_id = _persist_drift(
                store, aid, "BUNDLE_HASH_DRIFT",
                anchored_root, "<recompute_failed>", str(bundle_path), ev, sid,
            )
            findings.append(DriftFinding(
                agent_id=aid,
                drift_type="BUNDLE_HASH_DRIFT",
                expected_value=anchored_root,
                actual_value="<recompute_failed>",
                bundle_path=str(bundle_path),
                evidence_json=ev,
                drift_log_row_id=row_id,
            ))
            continue
        if recomputed.lower() != anchored_root:
            ev = json.dumps({
                "reason": "merkle_root_mismatch",
                "anchored": anchored_root,
                "recomputed": recomputed,
                "bundle_path": str(bundle_path),
            }, sort_keys=True, separators=(",", ":"))
            row_id = _persist_drift(
                store, aid, "BUNDLE_HASH_DRIFT",
                anchored_root, recomputed, str(bundle_path), ev, sid,
            )
            findings.append(DriftFinding(
                agent_id=aid,
                drift_type="BUNDLE_HASH_DRIFT",
                expected_value=anchored_root,
                actual_value=recomputed,
                bundle_path=str(bundle_path),
                evidence_json=ev,
                drift_log_row_id=row_id,
            ))
        # else: clean — no row written

    return DriftSweepResult(
        sweep_id=sid,
        agents_checked=len(candidates),
        findings=findings,
    )


async def detect_scope_hash_governance_drift(
    *, cfg, store, chain, sweep_id: Optional[str] = None,
) -> DriftSweepResult:
    """Compare AgentScope.getScopeRoot vs AgentRegistry.getAgent.scopeHash.

    For each known operator agent, do two on-chain reads + compare. Any
    divergence is a SCOPE_HASH_GOVERNANCE_DRIFT finding (CRITICAL).

    Async (chain reads are async).  Fail-open: chain unavailable → no
    findings written + error field populated.
    """
    sid = sweep_id or _sweep_id()
    findings: list[DriftFinding] = []
    sweep_error: Optional[str] = None

    if chain is None:
        return DriftSweepResult(
            sweep_id=sid,
            agents_checked=0,
            findings=[],
            error="chain_not_configured",
        )

    sentry_id = str(getattr(cfg, "operator_agent_anchor_sentry_id", "") or "").lower()
    guardian_id = str(getattr(cfg, "operator_agent_guardian_id", "") or "").lower()
    candidates = [aid for aid in (sentry_id, guardian_id) if aid]

    for aid in candidates:
        op_root_hex = ""
        gov_root_hex = ""
        try:
            op_bytes = await chain.get_agent_scope_root(aid)
            op_root_hex = "0x" + op_bytes.hex() if op_bytes else ""
        except Exception as exc:
            sweep_error = f"agent_scope_read_failed: {type(exc).__name__}"
            continue
        try:
            # Read governance scope from AgentRegistry.getAgent
            gov_root_hex = await _read_governance_scope(chain, aid)
        except Exception as exc:
            sweep_error = f"agent_registry_read_failed: {type(exc).__name__}"
            continue
        if op_root_hex.lower() != gov_root_hex.lower():
            ev = json.dumps({
                "agent_scope_root":   op_root_hex,
                "registry_scope_hash": gov_root_hex,
            }, sort_keys=True, separators=(",", ":"))
            row_id = _persist_drift(
                store, aid, "SCOPE_HASH_GOVERNANCE_DRIFT",
                op_root_hex, gov_root_hex, "", ev, sid,
            )
            findings.append(DriftFinding(
                agent_id=aid,
                drift_type="SCOPE_HASH_GOVERNANCE_DRIFT",
                expected_value=op_root_hex,
                actual_value=gov_root_hex,
                bundle_path="",
                evidence_json=ev,
                drift_log_row_id=row_id,
            ))

    return DriftSweepResult(
        sweep_id=sid,
        agents_checked=len(candidates),
        findings=findings,
        error=sweep_error,
    )


async def _read_governance_scope(chain, agent_id_hex: str) -> str:
    """Read AgentRegistry.getAgent(agent_id).scopeHash via chain ABI.

    Encapsulated so detect_scope_hash_governance_drift stays focused.
    Returns 0x-prefixed hex string of the bytes32 scopeHash.
    """
    # The chain object should expose a method for this. If not, we read
    # via an inline contract call. Keep it tolerant of either pattern.
    if hasattr(chain, "get_agent_governance_scope"):
        result = await chain.get_agent_governance_scope(agent_id_hex)
        if isinstance(result, (bytes, bytearray)):
            return "0x" + bytes(result).hex()
        return str(result)
    # Fallback: inline ABI call. The AgentRegistry.getAgent returns
    # (publicKey, scopeHash, status) — second element is the scopeHash.
    abi = [{
        "name": "getAgent", "type": "function", "stateMutability": "view",
        "inputs": [{"name": "agentId", "type": "bytes32"}],
        "outputs": [
            {"name": "publicKey", "type": "address"},
            {"name": "scopeHash", "type": "bytes32"},
            {"name": "status", "type": "uint8"},
        ],
    }]
    addr = getattr(chain._cfg, "agent_registry_address", "") if hasattr(chain, "_cfg") else ""
    if not addr:
        raise RuntimeError("agent_registry_address not configured")
    contract = chain._w3.eth.contract(address=addr, abi=abi)
    aid_bytes = bytes.fromhex(agent_id_hex.removeprefix("0x"))
    result = await contract.functions.getAgent(aid_bytes).call()
    scope_hash_bytes = result[1] if isinstance(result, (list, tuple)) else result
    if isinstance(scope_hash_bytes, (bytes, bytearray)):
        return "0x" + bytes(scope_hash_bytes).hex()
    return str(scope_hash_bytes)


def _persist_drift(
    store,
    agent_id: str,
    drift_type: str,
    expected_value: str,
    actual_value: str,
    bundle_path: str,
    evidence_json: str,
    sweep_id: str,
) -> int:
    """Persist drift finding via store helper.  Returns row_id (0 on failure)."""
    try:
        return int(
            store.insert_operator_agent_drift(
                agent_id=agent_id,
                drift_type=drift_type,
                expected_value=expected_value,
                actual_value=actual_value,
                bundle_path=bundle_path,
                evidence_json=evidence_json,
                sweep_id=sweep_id,
            )
        )
    except Exception as exc:
        log.warning(
            "Phase O1 C3: drift_log persist failed agent=%s drift=%s: %s",
            agent_id[:18], drift_type, exc,
        )
        return 0
