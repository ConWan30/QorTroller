"""Phase 235-BRIDGE-WEDGE-FIX — regression guards for the event-loop wedge.

Bug: bridge wedged its asyncio event loop ~5 seconds after startup at counter=6.
py-spy stack trace showed the MainThread "active" inside SQLite via:

    get_biometric_fingerprint   (store.py)
    compute_distance            (continuity_prover.py)
    should_attest               (continuity_prover.py)
    _check_continuity           (dualshock_integration.py)

`_check_continuity` was an `async def` running sync DB calls directly on the
event loop thread. Same pattern existed in `session_adjudicator_validator`'s
`_validate_ruling` GIC-stamp cluster (a latent blocker that would have fired
on the first ruling adjudication during the grind).

Fix: every sync Store / prover call inside an `async def` is wrapped in
`asyncio.to_thread(...)`. These tests are static guards that prevent the
to_thread wraps from being reverted in a future refactor.

Tests:
  T-WEDGE-1: _check_continuity wraps its sync DB / prover calls
  T-WEDGE-2: SessionAdjudicatorValidationAgent wraps its sync DB calls
  T-WEDGE-3: Store has the new get_unvalidated_rulings helper introduced
             to consolidate the validator's connection-context-manager block
"""
import inspect
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub heavy optional deps that chain.py / dualshock_integration.py import
# transitively before we try to import the modules under inspection.
from unittest.mock import MagicMock as _MagicMock
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)
_web3_mod = sys.modules["web3"]
for _attr in ["AsyncWeb3", "AsyncHTTPProvider", "Web3"]:
    if not hasattr(_web3_mod, _attr):
        setattr(_web3_mod, _attr, _MagicMock())
_web3_exc = sys.modules["web3.exceptions"]
for _attr in ["ContractLogicError", "TransactionNotFound"]:
    if not hasattr(_web3_exc, _attr):
        setattr(_web3_exc, _attr, Exception)
_eth_acc = sys.modules["eth_account"]
if not hasattr(_eth_acc, "Account"):
    setattr(_eth_acc, "Account", _MagicMock())

pytestmark = pytest.mark.smoke


# ---------------------------------------------------------------------------
# T-WEDGE-1: _check_continuity wraps sync calls in asyncio.to_thread
# ---------------------------------------------------------------------------

def test_t_wedge_1_check_continuity_uses_to_thread():
    """Phase 235-BRIDGE-WEDGE-FIX guard.

    `_check_continuity` was the py-spy-confirmed wedge site. Its body iterates
    devices and per pair calls Store + ContinuityProver methods that each
    issue ≥1 sync SQLite read — `get_biometric_fingerprint` alone scans the
    `records` table without a covering index. When this ran on the event
    loop thread, the first should_attest() pinned the loop for seconds.

    This static guard fails if a future refactor drops the to_thread wraps.
    """
    from vapi_bridge.dualshock_integration import DualShockTransport
    src = inspect.getsource(DualShockTransport._check_continuity)

    # Each Store / prover entry point inside the loop body must run on a
    # worker thread.  Listed in roughly the order they appear.
    required_wraps = [
        "asyncio.to_thread(self._store.list_devices",
        "asyncio.to_thread(\n                        self._store.is_device_claimed",
        "asyncio.to_thread(\n                        self._continuity_prover.should_attest",
        "asyncio.to_thread(\n                        self._continuity_prover.make_proof_hash",
        "asyncio.to_thread(\n                                    self._store.mark_device_claimed",
    ]
    for needle in required_wraps:
        assert needle in src, (
            f"DualShockTransport._check_continuity must keep `{needle.strip()}` — "
            "removing the to_thread wrap re-introduces the Phase 235 wedge "
            "(py-spy stack: get_biometric_fingerprint → should_attest → _check_continuity)."
        )


# ---------------------------------------------------------------------------
# T-WEDGE-2: validator GIC + PCC cluster wraps sync calls in asyncio.to_thread
# ---------------------------------------------------------------------------

def test_t_wedge_2_validator_uses_to_thread():
    """Latent blocker fix: `_validate_ruling` runs after every adjudication
    during the grind.  Its sync DB cluster (PCC snapshot, validation insert,
    GIC monotonicity guard, chain-hash update, gate summary, agent event)
    would have wedged the loop on session 1 even after the _check_continuity
    fix.  This guard pins the to_thread wraps in place.
    """
    from vapi_bridge.session_adjudicator_validator import (
        SessionAdjudicatorValidationAgent,
    )
    src_validate = inspect.getsource(SessionAdjudicatorValidationAgent._validate_ruling)
    src_consume  = inspect.getsource(
        SessionAdjudicatorValidationAgent._consume_pending_rulings
    )

    required_in_validate = [
        # write_agent_event (divergence path)
        "asyncio.to_thread(\n                self._store.write_agent_event",
        # PCC snapshot (Phase 235-B)
        "asyncio.to_thread(self._store.get_capture_health_status",
        # validation row insert (Phase 75)
        "asyncio.to_thread(\n            self._store.insert_validation_record",
        # GIC chain reads (Phase 235-A / INV-GIC-001/002)
        "asyncio.to_thread(\n                    self._store.get_prev_grind_chain_hash",
        "asyncio.to_thread(self._store.get_prev_gic_ts_ns",
        # GIC chain write
        "asyncio.to_thread(\n                    self._store.update_grind_chain_hash",
        # validation summary (gate emission)
        "asyncio.to_thread(\n                self._store.get_validation_summary",
        # gate-passed event write
        "asyncio.to_thread(\n                    self._store.write_agent_event",
    ]
    for needle in required_in_validate:
        assert needle in src_validate, (
            f"SessionAdjudicatorValidationAgent._validate_ruling must keep "
            f"`{needle.strip()}` — Phase 235-BRIDGE-WEDGE-FIX guard."
        )

    # _consume_pending_rulings used to open a connection-context-manager and
    # fetchall on the event loop thread; it must now route through the
    # Store helper on a worker thread.
    assert "asyncio.to_thread(self._store.get_unvalidated_rulings" in src_consume, (
        "SessionAdjudicatorValidationAgent._consume_pending_rulings must call "
        "Store.get_unvalidated_rulings via asyncio.to_thread — opening a SQLite "
        "connection on the event loop thread re-introduces the wedge."
    )

    # And the raw `with self._store._conn() as conn:` pattern must NOT come
    # back into this method.
    assert "self._store._conn()" not in src_consume, (
        "SessionAdjudicatorValidationAgent._consume_pending_rulings must not "
        "open a Store connection directly — use Store.get_unvalidated_rulings "
        "(which itself runs inside an asyncio.to_thread worker)."
    )


# ---------------------------------------------------------------------------
# T-WEDGE-3: Store.get_unvalidated_rulings helper exists with the correct query
# ---------------------------------------------------------------------------

def test_t_wedge_3_store_helper_exists():
    """The validator's old `with self._store._conn() as conn:` block was
    extracted into a Store helper so the entire connection-open / execute /
    fetchall / close lifecycle runs inside one to_thread() call instead of
    straddling the event loop.  This guard ensures the helper stays present
    and keeps its LEFT JOIN query — losing it would force the validator
    back to inline SQL on the event loop thread.
    """
    from vapi_bridge.store import Store
    assert hasattr(Store, "get_unvalidated_rulings"), (
        "Store must expose get_unvalidated_rulings(limit) — extracted in "
        "Phase 235-BRIDGE-WEDGE-FIX so session_adjudicator_validator can run "
        "the full connection lifecycle on a worker thread."
    )
    src = inspect.getsource(Store.get_unvalidated_rulings)
    assert "LEFT JOIN ruling_validation_log" in src, (
        "Store.get_unvalidated_rulings must keep its LEFT JOIN against "
        "ruling_validation_log — semantics: rows in agent_rulings without a "
        "matching validation row."
    )
    assert "rvl.id IS NULL" in src, (
        "Store.get_unvalidated_rulings query must filter on rvl.id IS NULL "
        "(the unvalidated condition)."
    )
