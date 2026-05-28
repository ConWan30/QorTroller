"""Data Economy Arc 1 Commit 2 — CuratorAttestationModule (curator write path).

The Curator's buyer-credential WRITE path. These tests lock the safety posture
that makes the module safe to ship into an autonomous bridge: dry-run never
touches the chain, the FROZEN category enum is enforced before any chain
contact, reason hashes stay off-chain, anomaly flags are local-only, and
on-chain reverts propagate (writes fail loud — the inverse of the fail-open
reads).

   T-CUR-ATT-1  dry_run=True (the default) returns a summary string, records ONE
                action_log entry with dry_run=True/tx_hash="", and NEVER calls
                the chain. Also: an out-of-range category raises ValueError
                BEFORE any chain contact (INV-BUY-001 guard).
   T-CUR-ATT-2  attest_buyer(dry_run=False) broadcasts issueCredential with the
                bytes32 buyerDID + category + bytes32 evidence hash and returns
                the tx hash; action_log records the live entry.
   T-CUR-ATT-3  revoke_credential(dry_run=False) broadcasts revokeCredential with
                ONLY the bytes32 buyerDID — the reason_hash is audit-only and
                MUST NOT be an on-chain argument.
   T-CUR-ATT-4  flag_behavioral_anomaly records to the LOCAL anomaly_log, returns
                None, and fires NO chain call and NO action_log entry.
   T-CUR-ATT-5  A contract revert (non-governance-expanded Curator → "only
                Curator") propagates out of attest_buyer — the write is NEVER
                silently swallowed.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from bridge.vapi_bridge.curator_attestation import CuratorAttestationModule
from bridge.vapi_bridge.consent_categories import device_id_to_bytes32


@dataclass
class _Cfg:
    buyer_registry_address: str = "0x3742189eBDC09B115FA7e841C884247E9856130B"
    chain_submission_paused: bool = False


class _ExplodingChain:
    """A chain whose _send_tx blows up if touched — proves dry-run never calls."""

    async def _send_tx(self, fn, *args):  # noqa: ANN001
        raise AssertionError("_send_tx must NOT be called during a dry run")


_EV = "ab" * 32  # 64-hex evidence hash


def _module(chain=None, cfg=None):
    return CuratorAttestationModule(chain or _ExplodingChain(), cfg or _Cfg())


# ── T-CUR-ATT-1 ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CUR_ATT_1_dry_run_returns_summary_no_chain():
    m = _module()
    summary = await m.attest_buyer("did:io:buyer-1", 2, _EV)  # dry_run defaults True
    assert isinstance(summary, str) and "DRY_RUN" in summary
    assert len(m.action_log) == 1
    e = m.action_log[0]
    assert e["dry_run"] is True and e["tx_hash"] == ""
    assert e["category_id"] == 2
    assert e["buyer_did_b32"] == device_id_to_bytes32("did:io:buyer-1").hex()
    # INV-BUY-001 guard: out-of-range category raises BEFORE any chain contact.
    with pytest.raises(ValueError):
        await m.attest_buyer("did:io:buyer-x", 5, _EV)
    with pytest.raises(ValueError):
        await m.attest_buyer("did:io:buyer-x", 0, _EV)


# ── T-CUR-ATT-2 ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CUR_ATT_2_attest_buyer_broadcasts_issue_credential():
    m = _module()
    calls = []

    async def fake_broadcast(fn_name, *args):
        calls.append((fn_name, args))
        return "0x" + "cd" * 32

    m._broadcast = fake_broadcast  # type: ignore[assignment]
    tx = await m.attest_buyer("did:io:buyer-2", 3, _EV, dry_run=False)
    assert tx == "0x" + "cd" * 32
    assert len(calls) == 1
    fn_name, args = calls[0]
    assert fn_name == "issueCredential"
    assert args[0] == device_id_to_bytes32("did:io:buyer-2")   # bytes32 buyerDID
    assert args[1] == 3                                          # categoryId
    assert args[2] == bytes.fromhex(_EV)                        # bytes32 evidence
    assert m.action_log[-1]["dry_run"] is False
    assert m.action_log[-1]["tx_hash"] == tx


# ── T-CUR-ATT-3 ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CUR_ATT_3_revoke_broadcasts_only_buyer_did():
    m = _module()
    calls = []

    async def fake_broadcast(fn_name, *args):
        calls.append((fn_name, args))
        return "0x" + "ef" * 32

    m._broadcast = fake_broadcast  # type: ignore[assignment]
    reason = "11" * 32
    tx = await m.revoke_credential("did:io:buyer-3", reason, dry_run=False)
    assert tx == "0x" + "ef" * 32
    fn_name, args = calls[0]
    assert fn_name == "revokeCredential"
    # ONLY buyerDID on-chain — reason_hash MUST NOT be an on-chain argument.
    assert args == (device_id_to_bytes32("did:io:buyer-3"),)
    # reason is preserved off-chain in the local audit trail.
    assert m.action_log[-1]["hash_b32"] == bytes.fromhex(reason).hex()


# ── T-CUR-ATT-4 ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CUR_ATT_4_anomaly_flag_local_only():
    m = _module()  # _ExplodingChain → any chain contact would fail the test
    out = m.flag_behavioral_anomaly(
        "did:io:buyer-4", "wash_purchase", {"listings": 12, "window_s": 60}
    )
    assert out is None
    assert len(m.anomaly_log) == 1
    a = m.anomaly_log[0]
    assert a["anomaly_type"] == "wash_purchase"
    assert a["evidence"] == {"listings": 12, "window_s": 60}
    assert a["buyer_did_b32"] == device_id_to_bytes32("did:io:buyer-4").hex()
    # No on-chain action, no issuance record.
    assert m.action_log == []


# ── T-CUR-ATT-5 ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_CUR_ATT_5_contract_revert_propagates():
    m = _module()

    async def reverting_broadcast(fn_name, *args):
        raise RuntimeError("Contract revert: only Curator")

    m._broadcast = reverting_broadcast  # type: ignore[assignment]
    # The write must fail LOUD — never silently swallowed.
    with pytest.raises(RuntimeError, match="only Curator"):
        await m.attest_buyer("did:io:buyer-5", 4, _EV, dry_run=False)
