"""
bridge/vapi_bridge/protocol_coherence_agent.py
Phase 221/224 — ProtocolCoherenceAgent (Agent #37)

Computes a Merkle root over the full VAPI agent fleet (37 agents) plus one virtual
allowlist leaf, and anchors it on-chain via ProtocolCoherenceRegistry.anchorCoherence().

Each fleet leaf is:
    leaf_i = sha256(agent_id.encode('utf-8') + ts_ns.to_bytes(8, 'big'))

Phase 224 virtual leaf (index 37):
    allowlist_leaf = sha256(b"allowlist" + bytes.fromhex(allowlist_hash[:16]) + ts_ns.to_bytes(8, 'big'))

This makes every --generate governance event visible from any chain node.
The Merkle root encodes 38 total leaves: 37 fleet agents + 1 allowlist sentinel.
anchorCoherence() receives agent_count=37 (fleet only, not including the virtual leaf).

Leaves are sorted before tree construction so the root is deterministic.
The Merkle tree uses pairwise sha256 with duplicate promotion for odd layers.

Agent behaviour:
  - Polls every `protocol_coherence_anchor_interval_s` seconds (default 3600)
  - If `protocol_coherence_registry_address` is set: attempts on-chain anchor
  - Always writes to `protocol_coherence_log` (local DB)
  - Detects allowlist hash changes; writes to `allowlist_change_log` if hash differs
  - Fail-open: never crashes the bridge on anchor failure

FROZEN:
  _AGENT_IDS — must match the 37-agent fleet defined in VAPI_AGENTS.md
  BP-007: agent IDs only, never biometric feature data in Merkle leaves
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vapi_bridge.store import Store
    from vapi_bridge.config import Config
    from vapi_bridge.chain import VAPIChain

log = logging.getLogger(__name__)

_GATE_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "vapi_invariant_gate.py"

# ---------------------------------------------------------------------------
# Canonical 38-ID agent ROSTER (Phase 238 Step I-FINAL — curator_agent added
# as the third Operator Initiative agent post on-chain mint + dual-anchor
# 2026-05-09; Merkle leaves 38 -> 39 incl. virtual allowlist leaf).
#
# NOTE (post-STABILITY-9 agent rationalization, agent_rationalization_v1.md):
# this tuple is the REGISTERED roster used for the on-chain coherence Merkle —
# it stays 38. Operationally the fleet is documented as "29 standalone agents +
# 3 Operator Initiative stewards": 9 of these IDs (Sentry 4 / Guardian 4 /
# Curator 1, see operator_steward_absorbed_agents.py) no longer spawn standalone
# background loops — they run as steward-invoked skills. Do NOT document "38
# autonomous agents" as the live fleet size (operator directive 2026-05-20).
# ---------------------------------------------------------------------------

_AGENT_IDS: tuple[str, ...] = (
    "bridge_agent",
    "calibration_intelligence_agent",
    "session_adjudicator",
    "class_j_detector",
    "supervisor_agent",
    "divergence_triage_agent",
    "gsr_registry_agent",
    "vhp_renewal_agent",
    "poad_anchor_agent",
    "live_mode_activation_agent",
    "separation_ratio_monitor_agent",
    "agent_calibration_monitor",
    "ceremony_watchdog_agent",
    "ruling_provenance_anchor_agent",
    "federation_broadcast_agent",
    "data_curator_agent",
    "ruling_enforcement_agent",
    "tournament_activation_chain_agent",
    "controller_hardware_intelligence_agent",
    "enrollment_auto_guidance_agent",
    "fleet_consensus_snapshot_agent",
    "biometric_privacy_compliance_agent",
    "separation_ratio_recovery_agent",
    "age_weight_analysis_agent",
    "protocol_intelligence_agent",
    "protocol_maturity_scoring_agent",
    "persona_break_detector_agent",
    "maturity_elevation_gate_agent",
    "reenrollment_attestation_agent",
    "attestation_bound_renewal_agent",
    "attestation_opsec_advisor_agent",
    "biometric_stationarity_oracle_agent",
    "protocol_intelligence_record_agent",
    "live_presence_signaling_agent",
    "corpus_curator_agent",
    "fleet_signal_coherence_agent",
    "biometric_governance_agent",   # Phase 222
    "curator_agent",                # Phase 238 Step I-FINAL — third Operator Initiative agent
)


def _load_gate_module():
    """Load vapi_invariant_gate.py via importlib (fail-open — returns None on error)."""
    try:
        spec = importlib.util.spec_from_file_location("vapi_invariant_gate", _GATE_SCRIPT)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception as exc:
        log.warning("Phase 224: could not load vapi_invariant_gate.py: %s", exc)
        return None


def _get_allowlist_hash() -> str:
    """Compute canonical allowlist hash. Returns 64 zeros if gate script unavailable."""
    try:
        gate = _load_gate_module()
        if gate is not None:
            return gate.compute_allowlist_hash()
    except Exception as exc:
        log.warning("Phase 224: compute_allowlist_hash failed: %s", exc)
    return "0" * 64


class ProtocolCoherenceAgent:
    """Agent #37 — Proof of Protocol Coherence (PoPC) anchor (Phase 221/224).

    Computes Merkle root over 37 fleet agents + 1 virtual allowlist leaf, anchors on-chain.
    Phase 224: detects allowlist hash changes between anchor cycles and writes allowlist_change_log.
    """

    def __init__(
        self,
        store: "Store",
        cfg: "Config",
        chain: "VAPIChain | None" = None,
        logger: "logging.Logger | None" = None,
    ) -> None:
        self._store = store
        self._cfg   = cfg
        self._chain = chain
        self._log   = logger or log
        self._last_allowlist_hash: str | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_leaf(agent_id: str, ts_ns: int) -> bytes:
        """Compute sha256 leaf for one agent: sha256(agent_id_bytes || ts_ns_8b)."""
        return hashlib.sha256(
            agent_id.encode("utf-8") + ts_ns.to_bytes(8, "big")
        ).digest()

    @staticmethod
    def _compute_merkle_root(leaves: list[bytes]) -> bytes:
        """Compute binary Merkle root from a list of 32-byte leaves.

        Leaves are sorted before tree construction for determinism.
        Odd layers duplicate the last leaf (standard binary Merkle).
        Returns bytes32(0) for empty input.
        """
        if not leaves:
            return b"\x00" * 32
        layer = sorted(leaves)
        while len(layer) > 1:
            next_layer: list[bytes] = []
            for i in range(0, len(layer), 2):
                left  = layer[i]
                right = layer[i + 1] if i + 1 < len(layer) else layer[i]
                next_layer.append(hashlib.sha256(left + right).digest())
            layer = next_layer
        return layer[0]

    def compute_fleet_root(self, ts_ns: int | None = None) -> tuple[str, int, str]:
        """Compute Merkle root over all _AGENT_IDS + virtual allowlist leaf.

        Returns (merkle_root_hex, ts_ns, allowlist_hash) where:
          - merkle_root_hex is a 64-char hex string (38 leaves: 37 fleet + 1 virtual)
          - allowlist_hash is the SHA-256 of INVARIANTS_ALLOWLIST.json
        """
        if ts_ns is None:
            ts_ns = int(time.time_ns())

        leaves = [self._compute_leaf(aid, ts_ns) for aid in _AGENT_IDS]

        # Virtual leaf #37 (Phase 224): allowlist hash as protocol-state witness
        allowlist_hex = _get_allowlist_hash()
        if allowlist_hex == "0" * 64:
            self._log.warning(
                "Phase 224: INVARIANTS_ALLOWLIST.json missing or gate unavailable "
                "— zero sentinel used for virtual leaf"
            )
        allowlist_leaf = hashlib.sha256(
            b"allowlist" + bytes.fromhex(allowlist_hex[:16]) + ts_ns.to_bytes(8, "big")
        ).digest()
        leaves.append(allowlist_leaf)
        self._log.debug(
            "Phase 224: virtual allowlist leaf appended; total leaves=%d allowlist_hash=%s…",
            len(leaves), allowlist_hex[:16],
        )

        root = self._compute_merkle_root(leaves)
        return root.hex(), ts_ns, allowlist_hex

    async def _anchor_cycle(self) -> None:
        """Single anchor cycle: compute root, persist locally, optionally anchor on-chain."""
        ts_ns = int(time.time_ns())
        root_hex, ts_ns, allowlist_hex = self.compute_fleet_root(ts_ns)
        agent_count = len(_AGENT_IDS)  # 37 fleet agents, not including virtual leaf

        anchor_hash = ""
        on_chain    = False

        # Phase 227: read latest governance provenance hash (fail-open: "" if unavailable)
        gov_prov_hash = ""
        try:
            gov_prov_hash = self._store.get_latest_governance_provenance_hash()
        except Exception as exc:
            self._log.debug("Phase 227: get_latest_governance_provenance_hash failed: %s", exc)

        addr = getattr(self._cfg, "protocol_coherence_registry_address", "")
        if addr and self._chain is not None:
            try:
                if gov_prov_hash and gov_prov_hash != "0" * 64:
                    # Phase 227: use new function when governance provenance is available
                    anchor_hash = await self._chain.anchor_coherence_with_provenance(
                        root_hex, gov_prov_hash, agent_count, ts_ns
                    )
                    self._log.info(
                        "Phase 227: PoPC+provenance anchored: root=%s… prov=%s… tx=%s…",
                        root_hex[:16], gov_prov_hash[:16], anchor_hash[:16],
                    )
                else:
                    # Fallback: no governance events yet — use original function
                    anchor_hash = await self._chain.anchor_coherence(
                        root_hex, agent_count, ts_ns
                    )
                    self._log.info(
                        "Phase 221: PoPC anchored on-chain: root=%s… tx=%s…",
                        root_hex[:16], anchor_hash[:16],
                    )
                on_chain = True
            except Exception as exc:
                self._log.warning(
                    "Phase 221/227: on-chain anchor failed (local only): %s", exc
                )

        try:
            self._store.insert_protocol_coherence_log(
                merkle_root=root_hex,
                agent_count=agent_count,
                anchor_hash=anchor_hash,
                on_chain_confirmed=on_chain,
                allowlist_hash=allowlist_hex,
                governance_provenance_hash=gov_prov_hash,
            )
        except Exception as exc:
            self._log.error("Phase 221: insert_protocol_coherence_log failed: %s", exc)

        # Phase 224: detect allowlist hash changes between anchor cycles
        if self._last_allowlist_hash is not None and self._last_allowlist_hash != allowlist_hex:
            reason_from_gate_log = None
            try:
                reason_from_gate_log = self._store.get_latest_governance_reason(within_seconds=60.0)
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
            try:
                self._store.insert_allowlist_change_log(
                    previous_hash=self._last_allowlist_hash,
                    new_hash=allowlist_hex,
                    merkle_root_at_change=root_hex,
                    reason_from_gate_log=reason_from_gate_log,
                )
                self._log.info(
                    "Phase 224: allowlist hash changed: %s…→%s… reason=%s",
                    self._last_allowlist_hash[:16], allowlist_hex[:16], reason_from_gate_log,
                )
            except Exception as exc:
                self._log.error("Phase 224: insert_allowlist_change_log failed: %s", exc)

        self._last_allowlist_hash = allowlist_hex

        if not on_chain:
            self._log.debug(
                "Phase 221: PoPC root computed (local only): root=%s… agents=%d",
                root_hex[:16], agent_count,
            )

    async def run_poll_loop(self) -> None:
        """Periodic poll loop — runs until cancelled."""
        interval = int(getattr(self._cfg, "protocol_coherence_anchor_interval_s", 3600))
        self._log.info(
            "Phase 221: ProtocolCoherenceAgent started (agent #37; "
            "poll=%ss; agents=%d; on_chain=%s; phase224_virtual_leaf=True)",
            interval,
            len(_AGENT_IDS),
            bool(getattr(self._cfg, "protocol_coherence_registry_address", "")),
        )
        while True:
            try:
                await self._anchor_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._log.error("Phase 221: anchor cycle error: %s", exc)
            await asyncio.sleep(interval)
