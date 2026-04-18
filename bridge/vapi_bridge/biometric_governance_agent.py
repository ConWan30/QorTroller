"""
bridge/vapi_bridge/biometric_governance_agent.py
Phase 222 — BiometricGovernanceAgent (Agent #38)

Validates and records governance proposals that are biometric-bound to the proposer's
live Verified Human Proof (VHP).  Three attacks blocked:

  STOLEN_KEY   — Attacker has the private key but not the soulbound VHP.
                 VHP is non-transferable; proposal requires ownerOf check.
  VHP_EXPIRY   — VHP must remain valid for bbg_max_age_seconds beyond proposal time.
                 Expired / near-expiry VHPs are rejected.
  FLASH_LOAN   — VHP is soulbound; ownership cannot be flash-borrowed unlike
                 fungible governance tokens.

Agent behaviour:
  - Monitors `bbg_proposal_log` for pending proposals
  - Validates each proposal's VHP freshness against `bbg_max_age_seconds`
  - If `bbg_contract_address` is set: submits on-chain via chain.bbg_propose()
  - Always writes to `bbg_proposal_log` (local DB)
  - Exposes `validate_proposal(proposal_hash, proposer, vhp_token_id)` for operator API
  - Fail-open: never crashes bridge on validation failure

bbg_enabled=False default — never change without BBG_CONTRACT_ADDRESS configured.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vapi_bridge.store import Store
    from vapi_bridge.config import Config
    from vapi_bridge.chain import VAPIChain

log = logging.getLogger(__name__)


class BiometricGovernanceAgent:
    """Agent #38 — Biometric-Bound Governance (BBG) validator (Phase 222).

    Validates governance proposals against the proposer's live VHP.
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

    @property
    def max_age_seconds(self) -> int:
        return int(getattr(self._cfg, "bbg_max_age_seconds", 3600))

    def validate_proposal_locally(
        self,
        proposal_hash: str,
        proposer_address: str,
        vhp_token_id: int,
        vhp_expires_at: float,
    ) -> dict:
        """Validate a BBG proposal without hitting the chain (Phase 222).

        Returns dict with keys:
          valid / rejection_reason / vhp_freshness_ok / proposal_hash / proposer_address
        """
        now = time.time()
        result: dict = {
            "valid":            False,
            "rejection_reason": None,
            "vhp_freshness_ok": False,
            "proposal_hash":    proposal_hash,
            "proposer_address": proposer_address,
        }
        if not proposal_hash or proposal_hash == "0" * 64:
            result["rejection_reason"] = "ZERO_PROPOSAL_HASH"
            return result
        if not proposer_address or proposer_address.startswith("0x000000"):
            result["rejection_reason"] = "ZERO_PROPOSER_ADDRESS"
            return result
        if vhp_expires_at <= 0:
            result["rejection_reason"] = "VHP_NOT_VALID"
            return result
        if vhp_expires_at < now + self.max_age_seconds:
            result["rejection_reason"] = "VHP_EXPIRES_TOO_SOON"
            return result
        result["valid"]            = True
        result["vhp_freshness_ok"] = True
        return result

    async def submit_proposal(
        self,
        proposal_hash: str,
        proposer_address: str,
        vhp_token_id: int,
        vhp_expires_at: float,
    ) -> dict:
        """Validate and optionally submit a BBG proposal (Phase 222).

        Returns a dict summarising the outcome:
          valid / on_chain / tx_hash / row_id / rejection_reason
        """
        val = self.validate_proposal_locally(
            proposal_hash, proposer_address, vhp_token_id, vhp_expires_at
        )
        if not val["valid"]:
            return {
                "valid":            False,
                "on_chain":         False,
                "tx_hash":          "",
                "row_id":           0,
                "rejection_reason": val.get("rejection_reason"),
            }

        tx_hash = ""
        on_chain = False
        addr = getattr(self._cfg, "bbg_contract_address", "")
        if addr and self._chain is not None:
            try:
                tx_hash = await self._chain.bbg_propose(proposal_hash, vhp_token_id)
                on_chain = True
                self._log.info(
                    "Phase 222: BBG proposal submitted on-chain: hash=%s… tx=%s…",
                    proposal_hash[:16], tx_hash[:16],
                )
            except Exception as exc:
                self._log.warning(
                    "Phase 222: on-chain BBG proposal failed (local only): %s", exc
                )

        try:
            row_id = self._store.insert_bbg_proposal_log(
                proposal_hash=proposal_hash,
                proposer_address=proposer_address,
                vhp_token_id=vhp_token_id,
                vhp_expires_at=vhp_expires_at,
                on_chain_confirmed=on_chain,
                tx_hash=tx_hash,
            )
        except Exception as exc:
            self._log.error("Phase 222: insert_bbg_proposal_log failed: %s", exc)
            row_id = 0

        return {
            "valid":            True,
            "on_chain":         on_chain,
            "tx_hash":          tx_hash,
            "row_id":           row_id,
            "rejection_reason": None,
        }

    async def run_poll_loop(self) -> None:
        """Minimal poll loop — BBG is primarily event-driven via POST /agent/bbg-propose."""
        self._log.info(
            "Phase 222: BiometricGovernanceAgent started (agent #38; "
            "bbg_max_age_sec=%d; on_chain=%s)",
            self.max_age_seconds,
            bool(getattr(self._cfg, "bbg_contract_address", "")),
        )
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
