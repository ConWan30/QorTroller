"""Data Economy Arc 1 Commit 2 — CuratorAttestationModule.

The Curator's buyer-credential attestation capability — the WRITE path to
VAPIBuyerRegistry (`0x3742189eBDC09B115FA7e841C884247E9856130B`). This is
deliberately SEPARATE from the bridge's least-privilege READ views in chain.py
(`is_valid_buyer_credential` / `get_buyer_category`, whose ABI carries
isValidCredential/getCategory ONLY — see T-BUY-CHAIN-4). The issuance/revocation
writers live HERE, signed by the bridge wallet, which IS the curatorWallet in v1
(setCuratorWallet fired 2026-05-28 tx 0xaf1209fb…).

Safety posture (the load-bearing part of this module):
  * attest_buyer / revoke_credential default ``dry_run=True``. A live on-chain
    broadcast requires ``dry_run=False`` explicitly AND the global kill-switch
    (CHAIN_SUBMISSION_PAUSED) being off. No credential is ever minted or revoked
    as a side effect of a dry run, and a dry run NEVER calls the chain.
  * On-chain reverts are NOT swallowed (the deliberate inverse of the fail-open
    reads): a failed issueCredential / revokeCredential — "only Curator",
    "already registered", "invalid category", "not registered" — propagates as
    RuntimeError so the operator sees the failure. A write must never silently
    no-op.
  * flag_behavioral_anomaly records the flag to the LOCAL anomaly log for the
    operator's slashing-proposal pipeline. It does NOT autonomously fire a
    slashing proposal or any on-chain transaction — that is an operator decision.

Category guard (INV-BUY-001): attest_buyer rejects any category outside the
FROZEN enum 1..4 BEFORE touching the chain, mirroring the contract's on-chain
``categoryId >= CATEGORY_ACADEMIC && categoryId <= CATEGORY_BRAND`` guard
(INV-BUY-002) so an invalid category fails fast and free.

AuditLog note: the framework spec says "all issuance actions logged to AuditLog
(on-chain)". The deployed AuditLog is a BATCHED Merkle appendCheckpoint anchor,
not a per-event logger — so per-issuance audit truth is (a) the registry's own
CredentialIssued / CredentialRevoked events and (b) this module's local
``action_log``. An on-chain AuditLog checkpoint, if ever desired, is an
operator-fired batch step — never an autonomous per-issuance call.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

# FROZEN category enum — mirrors VAPIBuyerRegistry.sol + PV-CI INV-BUY-001.
CATEGORY_ACADEMIC = 1
CATEGORY_GAME_DEV = 2
CATEGORY_ESPORTS = 3
CATEGORY_BRAND = 4
_VALID_CATEGORIES = frozenset({CATEGORY_ACADEMIC, CATEGORY_GAME_DEV,
                               CATEGORY_ESPORTS, CATEGORY_BRAND})

# Curator WRITE ABI — issueCredential + revokeCredential ONLY. This lives here,
# NOT in chain.py's read-only _VAPI_BUYER_REGISTRY_ABI: least-privilege keeps the
# passive bridge surface incapable of minting/revoking, while the Curator's
# attestation module (this file) holds the writer surface.
_CURATOR_WRITE_ABI = [
    {
        "name": "issueCredential",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "buyerDID", "type": "bytes32"},
            {"name": "categoryId", "type": "uint8"},
            {"name": "evidenceHash", "type": "bytes32"},
        ],
        "outputs": [],
    },
    {
        "name": "revokeCredential",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "buyerDID", "type": "bytes32"}],
        "outputs": [],
    },
]


def _to_bytes32(value: Any) -> bytes:
    """Normalise an evidence/reason hash to a 32-byte value.

    Accepts raw 32-byte ``bytes`` (used directly) or a 0x-prefixed / bare 64-hex
    string. Anything else — wrong length included — raises, because a malformed
    evidence hash must never silently become a zero or truncated on-chain field.
    """
    if isinstance(value, (bytes, bytearray)):
        b = bytes(value)
        if len(b) != 32:
            raise ValueError(f"evidence/reason hash must be 32 bytes, got {len(b)}")
        return b
    if isinstance(value, str):
        b = bytes.fromhex(value.removeprefix("0x"))
        if len(b) != 32:
            raise ValueError(
                f"evidence/reason hash hex must decode to 32 bytes, got {len(b)}"
            )
        return b
    raise TypeError(f"evidence/reason hash must be bytes or hex str, got {type(value)}")


class CuratorAttestationModule:
    """Curator buyer-credential attestation (issue / revoke / flag).

    Active only after the governance ceremony completes (curatorWallet set
    on-chain — done 2026-05-28). Construct with the live ChainClient and Config;
    pass an optional store for durable action/anomaly persistence.
    """

    def __init__(self, chain: Any, cfg: Any, store: Optional[Any] = None) -> None:
        self._chain = chain
        self._cfg = cfg
        self._store = store
        self._registry_address = (getattr(cfg, "buyer_registry_address", "") or "")
        # Local audit surfaces (operational truth alongside on-chain events).
        self.action_log: list[dict] = []   # attest / revoke records (dry-run + live)
        self.anomaly_log: list[dict] = []   # behavioral-anomaly flags

    # ── helpers ──────────────────────────────────────────────────────────────

    def _require_category(self, category_id: int) -> None:
        if int(category_id) not in _VALID_CATEGORIES:
            raise ValueError(
                f"invalid category {category_id}; must be 1..4 "
                "(INV-BUY-001 FROZEN enum: ACADEMIC=1/GAME_DEV=2/ESPORTS=3/BRAND=4)"
            )

    def _write_contract(self):
        """Build the WRITE contract instance, or None when dormant.

        Returns None when the registry address is unset or the chain's async
        web3 is unavailable — so a misconfigured environment fails loud in
        ``_broadcast`` rather than constructing a half-bound contract.
        """
        if not self._registry_address:
            return None
        w3 = getattr(self._chain, "_w3", None)
        if w3 is None:
            return None
        from web3 import Web3
        return w3.eth.contract(
            address=Web3.to_checksum_address(self._registry_address),
            abi=_CURATOR_WRITE_ABI,
        )

    async def _broadcast(self, fn_name: str, *args) -> str:
        """Sign + send a writer call via the bridge wallet (curatorWallet).

        Honours the global kill-switch and reuses ChainClient._send_tx (the same
        gas-estimate + nonce + revert-guard chokepoint every other write uses).
        Reverts propagate — writes fail loud.
        """
        if getattr(self._cfg, "chain_submission_paused", False):
            raise RuntimeError(
                "chain_submission_paused: CuratorAttestationModule cannot "
                "broadcast (CHAIN_SUBMISSION_PAUSED kill-switch active)"
            )
        contract = self._write_contract()
        if contract is None:
            raise RuntimeError(
                "buyer_registry_address unset or chain unavailable — "
                "CuratorAttestationModule cannot broadcast"
            )
        fn = getattr(contract.functions, fn_name)
        return await self._chain._send_tx(fn, *args)

    def _record(self, action: str, buyer_did: Any, b32: bytes,
                category_id: Optional[int], hash_b32: bytes, *,
                dry_run: bool, tx_hash: str) -> str:
        entry = {
            "action": action,
            "buyer_did": str(buyer_did),
            "buyer_did_b32": b32.hex(),
            "category_id": category_id,
            "hash_b32": hash_b32.hex(),
            "dry_run": dry_run,
            "tx_hash": tx_hash,
            "ts_ns": time.time_ns(),
        }
        self.action_log.append(entry)
        if self._store is not None and hasattr(self._store, "record_curator_action"):
            try:
                self._store.record_curator_action(entry)
            except Exception:  # store failure must not break the attestation
                log.exception("record_curator_action persistence failed (non-fatal)")
        if dry_run:
            cat = "" if category_id is None else f" category={category_id}"
            return (
                f"DRY_RUN {action} buyerDID=0x{b32.hex()}{cat} "
                f"hash=0x{hash_b32.hex()} — no transaction broadcast "
                "(set dry_run=False to act on-chain)"
            )
        return tx_hash

    # ── public API ───────────────────────────────────────────────────────────

    async def attest_buyer(self, buyer_did: str, category_id: int,
                           evidence_hash: Any, dry_run: bool = True) -> str:
        """Issue a buyer credential. Default dry_run=True (no chain, no spend).

        Returns the dry-run summary string when dry_run=True, or the on-chain
        tx hash when dry_run=False. Validates the category against the FROZEN
        enum BEFORE any chain contact.
        """
        from .consent_categories import device_id_to_bytes32
        self._require_category(category_id)
        b32 = device_id_to_bytes32(buyer_did)
        ev = _to_bytes32(evidence_hash)
        if dry_run:
            return self._record("attest_buyer", buyer_did, b32, int(category_id),
                                ev, dry_run=True, tx_hash="")
        tx_hash = await self._broadcast("issueCredential", b32, int(category_id), ev)
        return self._record("attest_buyer", buyer_did, b32, int(category_id),
                            ev, dry_run=False, tx_hash=tx_hash)

    async def revoke_credential(self, buyer_did: str, reason_hash: Any,
                                dry_run: bool = True) -> str:
        """Revoke a buyer credential (sets active=false on-chain).

        reason_hash is recorded to the LOCAL action_log for the audit trail but
        is NOT an on-chain argument — the contract's revokeCredential takes only
        buyerDID. Default dry_run=True.
        """
        from .consent_categories import device_id_to_bytes32
        b32 = device_id_to_bytes32(buyer_did)
        reason = _to_bytes32(reason_hash)
        if dry_run:
            return self._record("revoke_credential", buyer_did, b32, None,
                                reason, dry_run=True, tx_hash="")
        # Contract revokeCredential(bytes32) — reason stays off-chain (audit).
        tx_hash = await self._broadcast("revokeCredential", b32)
        return self._record("revoke_credential", buyer_did, b32, None,
                            reason, dry_run=False, tx_hash=tx_hash)

    def flag_behavioral_anomaly(self, buyer_did: str, anomaly_type: str,
                                evidence: dict) -> None:
        """Record a behavioral-anomaly flag for the operator's slashing pipeline.

        Local-only. Does NOT fire a slashing proposal or any on-chain action —
        the operator reviews ``anomaly_log`` and decides. Returns None.
        """
        from .consent_categories import device_id_to_bytes32
        entry = {
            "buyer_did": str(buyer_did),
            "buyer_did_b32": device_id_to_bytes32(buyer_did).hex(),
            "anomaly_type": str(anomaly_type),
            "evidence": dict(evidence) if evidence else {},
            "ts_ns": time.time_ns(),
        }
        self.anomaly_log.append(entry)
        if self._store is not None and hasattr(self._store, "record_curator_anomaly"):
            try:
                self._store.record_curator_anomaly(entry)
            except Exception:
                log.exception("record_curator_anomaly persistence failed (non-fatal)")
        log.warning(
            "CuratorAttestationModule: behavioral anomaly flagged buyer=%s "
            "type=%s — recorded for operator slashing-proposal pipeline "
            "(NO autonomous on-chain action)",
            str(buyer_did)[:24], anomaly_type,
        )
        return None
