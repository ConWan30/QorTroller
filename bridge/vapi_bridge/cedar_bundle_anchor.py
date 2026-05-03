"""Phase O1 C1 — Cedar bundle dual on-chain anchor (D4 implementation).

This module performs the operator-triggered phase activation: loads a Cedar
bundle file from disk, validates it via cedar_parser, computes the Merkle
root, and fires the dual on-chain anchor that commits the root to BOTH
contracts:

  1. AgentScope.setAgentScopeRoot(agentId, root)        — operational layer
  2. AgentRegistry.updateAgentScope(agentId, newScope)  — governance layer

Per INV-OPERATOR-AGENT-001: operational FIRST, governance SECOND. If the
operational call succeeds but governance reverts, the activation_log row
records both attempts (operational tx_hash + governance tx_hash="reverted")
and FSCA SCOPE_HASH_GOVERNANCE_DRIFT (Phase O1 C2/C3 deferred scope) will
detect the divergence at next poll cycle.

The activation log row is the off-chain mirror of the on-chain
AgentScopeRootSet + AgentScopeUpdated events. UNIQUE(agent_id, to_scope_root)
constraint enforces anti-replay (INV-OPERATOR-AGENT-002).

Phase activation is the ONLY operator-triggered Phase O1 on-chain action.
Per Pass 2C Section 3.2, AgentScope.scopeRoot is the live read path used by
AgentAdjudicationRegistry.requireAgentScope; AgentRegistry.scopeHash is the
governance commitment. Both populated atomically establishes the canonical
Phase O1 baseline.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .cedar_parser import (
    CedarBundleError,
    ParsedBundle,
    bundle_merkle_root,
    parse_bundle,
)


@dataclass(slots=True)
class AnchorResult:
    """Return shape of CedarBundleAnchor.anchor_bundle()."""
    success: bool
    agent_id: str
    from_phase: str
    to_phase: str
    from_scope_root: str
    to_scope_root: str
    bundle_path: str
    governance_tx_hash: Optional[str] = None
    operational_tx_hash: Optional[str] = None
    governance_block_number: Optional[int] = None
    operational_block_number: Optional[int] = None
    activation_log_id: Optional[int] = None
    error: Optional[str] = None


class CedarBundleAnchorError(RuntimeError):
    """Raised on dual-anchor failures (bundle issues, chain reverts, etc.)."""


def _hex_with_0x(b: bytes) -> str:
    """Return 0x-prefixed lowercase hex of bytes."""
    return "0x" + b.hex()


def _operator_authority_hash(operator_api_key: str, reason_text: str, ts_ns: int) -> str:
    """Compute audit binding hash from (operator_api_key + reason_text + ts_ns_be).

    The operator_api_key is the bridge's operator authority secret. The reason_text
    is the operator's stated rationale (≥10 chars per gate validation). The ts_ns
    is the bridge UTC nanosecond timestamp at activation time. Together they
    cryptographically bind the activation to the operator's authority + reason +
    moment, making the operation tamper-evident in the off-chain audit log.
    """
    if not isinstance(operator_api_key, str) or not operator_api_key:
        raise CedarBundleAnchorError("operator_api_key must be non-empty string")
    if not isinstance(reason_text, str) or len(reason_text) < 10:
        raise CedarBundleAnchorError("reason_text must be ≥10 chars")
    if not isinstance(ts_ns, int) or ts_ns < 0:
        raise CedarBundleAnchorError("ts_ns must be non-negative int")
    h = hashlib.sha256()
    h.update(operator_api_key.encode("utf-8"))
    h.update(b"\x00")
    h.update(reason_text.encode("utf-8"))
    h.update(b"\x00")
    h.update(ts_ns.to_bytes(8, "big"))
    return _hex_with_0x(h.digest())


class CedarBundleAnchor:
    """Phase O1 C1 dual on-chain anchor primitive.

    The chain and store dependencies are injected (not imported as singletons)
    so this class can be constructed in tests with mocks. The bundle_dir lets
    the anchor read bundles from a configurable location (default per cfg).
    """

    def __init__(self, chain, store, bundle_dir: Path | str):
        """
        Args:
            chain:      VAPIChain instance with get_agent_scope_root,
                        set_agent_scope_root, update_agent_scope_governance methods
                        (added in B6).
            store:      Store instance with insert_operator_agent_activation
                        helper (added in B5).
            bundle_dir: Repo-relative or absolute path to the directory containing
                        Cedar bundle JSON files.
        """
        self._chain = chain
        self._store = store
        self._bundle_dir = Path(bundle_dir)

    async def anchor_bundle(
        self,
        *,
        bundle_path: str,
        reason_text: str,
        operator_api_key: str,
    ) -> AnchorResult:
        """Fire the dual on-chain anchor for the bundle at bundle_path.

        Atomicity policy (INV-OPERATOR-AGENT-001):
          1. Validate bundle (raises before any chain interaction)
          2. Compute new Merkle root (the to_scope_root)
          3. Read current scopeRoot from chain (the from_scope_root) — fail-closed
          4. Fire AgentScope.setAgentScopeRoot — operational layer FIRST
          5. Fire AgentRegistry.updateAgentScope — governance layer SECOND
          6. Insert operator_agent_activation_log row (always — captures both attempts)
          7. Return AnchorResult

        If step 5 reverts after step 4 succeeds, the activation_log row records
        the divergence (operational_tx_hash populated, governance_tx_hash="reverted")
        and FSCA SCOPE_HASH_GOVERNANCE_DRIFT (Phase O1 C2/C3 deferred) will fire
        on the next poll. Recovery is operator-triggered: re-fire the governance
        leg only via dedicated repair endpoint (deferred to Phase O1 C2).

        No-op short-circuit: if the bundle's Merkle root equals the current
        on-chain scopeRoot, returns AnchorResult(success=True, activation_log_id=None)
        without firing any transactions.
        """
        # Step 1: validate bundle
        try:
            bundle, parsed = self._load_and_parse(bundle_path)
        except (CedarBundleError, FileNotFoundError, json.JSONDecodeError) as e:
            raise CedarBundleAnchorError(f"bundle load/parse failed: {e}") from e

        # Step 2: compute new Merkle root (already computed inside parse_bundle as parsed.merkle_root)
        new_root = parsed.merkle_root
        new_root_hex = _hex_with_0x(new_root)

        # Step 3: read current scopeRoot from chain — fail-closed (raises if address unset).
        # Per V-checks: deployed AgentScope uses getScopeRoot(bytes32), not scopeRoot.
        agent_id_hex = parsed.agent_id
        try:
            from_root_bytes = await self._chain.get_agent_scope_root(agent_id_hex)
        except Exception as e:
            raise CedarBundleAnchorError(
                f"chain.get_agent_scope_root failed: {e}"
            ) from e
        from_root_hex = _hex_with_0x(from_root_bytes)

        # No-op short-circuit: bundle root already on chain
        if from_root_bytes == new_root:
            return AnchorResult(
                success=True,
                agent_id=agent_id_hex,
                from_phase=parsed.phase,
                to_phase=parsed.phase,
                from_scope_root=from_root_hex,
                to_scope_root=new_root_hex,
                bundle_path=str(bundle_path),
                activation_log_id=None,
            )

        # Determine from_phase: empty root = O0_DORMANT; else parse from prior bundle (B-deferred).
        # For Phase O1 C1, conservative inference: if from_root is bytes32(0), it's O0; otherwise unknown.
        from_phase = "O0_DORMANT" if from_root_bytes == b"\x00" * 32 else "PRE_O1_UNKNOWN"

        # Step 4: AgentScope.setAgentScopeRoot — operational layer FIRST per INV-OPERATOR-AGENT-001
        op_tx_hash: Optional[str] = None
        op_block: Optional[int] = None
        try:
            op_result = await self._chain.set_agent_scope_root(agent_id_hex, new_root_hex)
            op_tx_hash = op_result.get("tx_hash")
            op_block = op_result.get("block_number")
        except Exception as e:
            raise CedarBundleAnchorError(
                f"AgentScope.setAgentScopeRoot failed (operational layer; "
                f"governance NOT attempted): {e}"
            ) from e

        # Step 5: AgentRegistry.updateAgentScope — governance layer SECOND
        gov_tx_hash: Optional[str] = None
        gov_block: Optional[int] = None
        gov_error: Optional[str] = None
        try:
            gov_result = await self._chain.update_agent_scope_governance(agent_id_hex, new_root_hex)
            gov_tx_hash = gov_result.get("tx_hash")
            gov_block = gov_result.get("block_number")
        except Exception as e:
            gov_error = str(e)
            gov_tx_hash = "reverted"
            # NOTE: do NOT raise — record the divergence in activation_log so FSCA
            # SCOPE_HASH_GOVERNANCE_DRIFT can detect on next poll. The operator can
            # re-fire just the governance leg via a future repair endpoint.

        # Step 6: insert activation_log row — always, to capture both attempts
        ts_ns = time.time_ns()
        auth_hash = _operator_authority_hash(operator_api_key, reason_text, ts_ns)
        activation_log_id: Optional[int] = None
        try:
            activation_log_id = self._store.insert_operator_agent_activation(
                agent_id=agent_id_hex,
                from_phase=from_phase,
                to_phase=parsed.phase,
                from_scope_root=from_root_hex,
                to_scope_root=new_root_hex,
                bundle_path=str(bundle_path),
                governance_tx_hash=gov_tx_hash or "missing",
                operational_tx_hash=op_tx_hash or "missing",
                governance_block_number=int(gov_block) if gov_block is not None else 0,
                operational_block_number=int(op_block) if op_block is not None else 0,
                operator_authority_hash=auth_hash,
                reason_text=reason_text,
            )
        except Exception as e:
            # Activation log write failed but on-chain state is already mutated.
            # Operator must reconcile manually.
            raise CedarBundleAnchorError(
                f"activation_log insert failed AFTER on-chain mutation "
                f"(operational_tx={op_tx_hash}, governance_tx={gov_tx_hash}): {e}"
            ) from e

        return AnchorResult(
            success=(gov_error is None),
            agent_id=agent_id_hex,
            from_phase=from_phase,
            to_phase=parsed.phase,
            from_scope_root=from_root_hex,
            to_scope_root=new_root_hex,
            bundle_path=str(bundle_path),
            governance_tx_hash=gov_tx_hash,
            operational_tx_hash=op_tx_hash,
            governance_block_number=gov_block,
            operational_block_number=op_block,
            activation_log_id=activation_log_id,
            error=gov_error,
        )

    def _load_and_parse(self, bundle_path: str) -> tuple[dict, ParsedBundle]:
        """Load JSON from bundle_path (resolved against bundle_dir if relative);
        validate via cedar_parser.parse_bundle; return (raw_dict, ParsedBundle)."""
        path = Path(bundle_path)
        if not path.is_absolute():
            path = self._bundle_dir / path
        if not path.exists():
            raise FileNotFoundError(f"Cedar bundle not found: {path}")
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        parsed = parse_bundle(raw)
        # Round-trip integrity: parse_bundle's stored merkle_root must equal
        # bundle_merkle_root(raw) computed independently. Defends against
        # parser-side mutation of the bundle dict.
        recompute = bundle_merkle_root(raw)
        if parsed.merkle_root != recompute:
            raise CedarBundleAnchorError(
                f"Merkle root round-trip mismatch: parser={parsed.merkle_root.hex()} "
                f"recompute={recompute.hex()}"
            )
        return raw, parsed
