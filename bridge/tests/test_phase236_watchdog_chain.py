"""Phase 236-WATCHDOG — Watchdog Event Chain (WEC). FROZEN FORMULA v1.

Closes the source-without-tests drift surfaced by the Phase O0 test-coverage
audit: bridge/vapi_bridge/watchdog_chain.py shipped in commit cb902568 but
no test file existed despite CLAUDE.md asserting T236-WD-1..8.

Scope: pure-formula tests against watchdog_chain.py only. The store-level
monotonicity guard (insert_watchdog_event ts_ns bump) and restarts_last_hour
aggregation (get_watchdog_event_chain_status) are exercised through
store-integration tests, not here.

T236-WD-1: genesis_wec deterministic — same inputs → same 32-byte digest
T236-WD-2: compute_wec single-link — manual SHA-256 recompute matches
T236-WD-3: 3-event chain round-trip — all distinct, recomputable end-to-end
T236-WD-4: tamper detection — flipping event_code on event 2 cascades to event 3
T236-WD-5: monotonicity contribution — ts_ns is hashed, so different ts → different WEC
           (formula's contribution to the store-level monotonicity guard)
T236-WD-6: session scoping — different grind_session_id → different sid_hash → different WEC
T236-WD-7: restart counting contribution — BRIDGE_RESTART_TRIGGERED produces a
           hash distinct from BRIDGE_HEALTHY at otherwise-identical inputs
T236-WD-8: invalid input — event_code or pid out of byte/uint32 range raises ValueError
"""
import hashlib
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.watchdog_chain import (
    EVENT_CODES,
    EVENT_NAMES,
    compute_wec,
    genesis_wec,
    grind_session_id_hash,
)

_GRIND_SID = "grind_test_20260501"
_GENESIS_TAG = b"VAPI-WEC-GENESIS-v1"


# ---------------------------------------------------------------------------
# T236-WD-1: genesis determinism
# ---------------------------------------------------------------------------

def test_t236_wd_1_genesis_deterministic():
    ts = 1745000000000000000
    h1 = genesis_wec(_GRIND_SID, ts)
    h2 = genesis_wec(_GRIND_SID, ts)
    assert h1 == h2
    assert len(h1) == 32

    # Manual recompute against FROZEN tag
    expected = hashlib.sha256(
        _GENESIS_TAG + _GRIND_SID.encode() + struct.pack(">Q", ts)
    ).digest()
    assert h1 == expected


# ---------------------------------------------------------------------------
# T236-WD-2: single-link correctness
# ---------------------------------------------------------------------------

def test_t236_wd_2_single_link_correct():
    ts_g = 1745000000000000000
    ts_1 = 1745000001000000000
    pid = 25760

    prev = genesis_wec(_GRIND_SID, ts_g)
    wec_1 = compute_wec(prev, EVENT_CODES["BRIDGE_START"], pid, _GRIND_SID, ts_1)

    expected = hashlib.sha256(
        prev
        + EVENT_CODES["BRIDGE_START"].to_bytes(1, "big")
        + struct.pack(">I", pid)
        + grind_session_id_hash(_GRIND_SID)
        + struct.pack(">Q", ts_1)
    ).digest()

    assert wec_1 == expected
    assert len(wec_1) == 32


# ---------------------------------------------------------------------------
# T236-WD-3: 3-event chain round-trip
# ---------------------------------------------------------------------------

def test_t236_wd_3_chain_3_events():
    ts_g = 1745000000000000000
    ts_1 = ts_g + 1_000_000_000
    ts_2 = ts_g + 2_000_000_000
    ts_3 = ts_g + 3_000_000_000
    pid = 25760

    prev0 = genesis_wec(_GRIND_SID, ts_g)
    wec_1 = compute_wec(prev0, EVENT_CODES["BRIDGE_START"],   pid, _GRIND_SID, ts_1)
    wec_2 = compute_wec(wec_1, EVENT_CODES["BRIDGE_HEALTHY"], pid, _GRIND_SID, ts_2)
    wec_3 = compute_wec(wec_2, EVENT_CODES["BRIDGE_HEALTHY"], pid, _GRIND_SID, ts_3)

    assert len({prev0, wec_1, wec_2, wec_3}) == 4

    # Recompute end-to-end and verify
    r0 = genesis_wec(_GRIND_SID, ts_g)
    r1 = compute_wec(r0, EVENT_CODES["BRIDGE_START"],   pid, _GRIND_SID, ts_1)
    r2 = compute_wec(r1, EVENT_CODES["BRIDGE_HEALTHY"], pid, _GRIND_SID, ts_2)
    r3 = compute_wec(r2, EVENT_CODES["BRIDGE_HEALTHY"], pid, _GRIND_SID, ts_3)
    assert (r1, r2, r3) == (wec_1, wec_2, wec_3)


# ---------------------------------------------------------------------------
# T236-WD-4: tamper detection — flip event_code on event 2 → cascades
# ---------------------------------------------------------------------------

def test_t236_wd_4_tamper_detection():
    ts_g = 1745000000000000000
    ts_1 = ts_g + 1
    ts_2 = ts_g + 2
    ts_3 = ts_g + 3
    pid = 25760

    prev0 = genesis_wec(_GRIND_SID, ts_g)
    wec_1 = compute_wec(prev0, EVENT_CODES["BRIDGE_START"],   pid, _GRIND_SID, ts_1)
    wec_2 = compute_wec(wec_1, EVENT_CODES["BRIDGE_HEALTHY"], pid, _GRIND_SID, ts_2)
    wec_3 = compute_wec(wec_2, EVENT_CODES["BRIDGE_HEALTHY"], pid, _GRIND_SID, ts_3)

    # Tamper: rewrite event 2 as BRIDGE_UNRESPONSIVE (DB edit on event_code column)
    tampered_wec_2 = compute_wec(
        wec_1, EVENT_CODES["BRIDGE_UNRESPONSIVE"], pid, _GRIND_SID, ts_2
    )
    assert tampered_wec_2 != wec_2

    # Recomputing event 3 from the tampered chain produces a hash that diverges
    # from the stored wec_3 — the chain break is detectable.
    recomputed_wec_3 = compute_wec(
        tampered_wec_2, EVENT_CODES["BRIDGE_HEALTHY"], pid, _GRIND_SID, ts_3
    )
    assert recomputed_wec_3 != wec_3


# ---------------------------------------------------------------------------
# T236-WD-5: monotonicity contribution — ts_ns is hashed
# ---------------------------------------------------------------------------

def test_t236_wd_5_ts_ns_is_hashed():
    """The store-level monotonicity guard relies on the formula being sensitive
    to ts_ns. Two events with identical (prev, code, pid, sid) but different ts_ns
    must produce different WEC hashes."""
    ts_g = 1745000000000000000
    pid = 25760

    prev = genesis_wec(_GRIND_SID, ts_g)
    wec_a = compute_wec(prev, EVENT_CODES["BRIDGE_HEALTHY"], pid, _GRIND_SID, ts_g + 1)
    wec_b = compute_wec(prev, EVENT_CODES["BRIDGE_HEALTHY"], pid, _GRIND_SID, ts_g + 2)
    assert wec_a != wec_b


# ---------------------------------------------------------------------------
# T236-WD-6: session scoping — different grind_session_id → different WEC
# ---------------------------------------------------------------------------

def test_t236_wd_6_session_scoping():
    ts_g = 1745000000000000000
    ts_1 = ts_g + 1
    pid = 25760
    sid_a = "grind_alpha_20260501"
    sid_b = "grind_beta_20260501"

    # Genesis hashes for two different sessions diverge on the sid bytes
    gen_a = genesis_wec(sid_a, ts_g)
    gen_b = genesis_wec(sid_b, ts_g)
    assert gen_a != gen_b

    # And so do downstream WECs computed from a SHARED prev under different sids
    shared_prev = b"\x00" * 32
    wec_a = compute_wec(shared_prev, EVENT_CODES["BRIDGE_START"], pid, sid_a, ts_1)
    wec_b = compute_wec(shared_prev, EVENT_CODES["BRIDGE_START"], pid, sid_b, ts_1)
    assert wec_a != wec_b

    # sid_hash itself differs
    assert grind_session_id_hash(sid_a) != grind_session_id_hash(sid_b)
    assert len(grind_session_id_hash(sid_a)) == 16


# ---------------------------------------------------------------------------
# T236-WD-7: restart counting contribution — distinct hash for BRIDGE_RESTART_TRIGGERED
# ---------------------------------------------------------------------------

def test_t236_wd_7_restart_event_distinguishable():
    """restarts_last_hour aggregation in store.get_watchdog_event_chain_status
    counts rows where event_code == BRIDGE_RESTART_TRIGGERED. The formula must
    produce a distinct hash for that event vs nearby events at otherwise-identical
    inputs, so a row's event_code can't be silently swapped to disguise a restart."""
    ts_g = 1745000000000000000
    ts_1 = ts_g + 1
    pid = 25760
    prev = genesis_wec(_GRIND_SID, ts_g)

    healthy = compute_wec(prev, EVENT_CODES["BRIDGE_HEALTHY"],           pid, _GRIND_SID, ts_1)
    restart = compute_wec(prev, EVENT_CODES["BRIDGE_RESTART_TRIGGERED"], pid, _GRIND_SID, ts_1)
    refused = compute_wec(prev, EVENT_CODES["BRIDGE_RESTART_REFUSED_GIC"], pid, _GRIND_SID, ts_1)
    halt    = compute_wec(prev, EVENT_CODES["WATCHDOG_HALT"],            pid, _GRIND_SID, ts_1)

    # All four event-code substitutions produce distinct hashes
    assert len({healthy, restart, refused, halt}) == 4

    # Round-trip code/name table while we're here
    assert EVENT_NAMES[EVENT_CODES["BRIDGE_RESTART_TRIGGERED"]] == "BRIDGE_RESTART_TRIGGERED"
    assert EVENT_CODES["WATCHDOG_HALT"] == 0xFF


# ---------------------------------------------------------------------------
# T236-WD-8: invalid input → ValueError
# ---------------------------------------------------------------------------

def test_t236_wd_8_invalid_input_raises():
    ts_g = 1745000000000000000
    prev = genesis_wec(_GRIND_SID, ts_g)

    # event_code out of byte range
    with pytest.raises(ValueError):
        compute_wec(prev, -1, 1, _GRIND_SID, ts_g + 1)
    with pytest.raises(ValueError):
        compute_wec(prev, 0x100, 1, _GRIND_SID, ts_g + 1)

    # pid out of uint32 range
    with pytest.raises(ValueError):
        compute_wec(prev, EVENT_CODES["BRIDGE_HEALTHY"], -1, _GRIND_SID, ts_g + 1)
    with pytest.raises(ValueError):
        compute_wec(prev, EVENT_CODES["BRIDGE_HEALTHY"], 0x1_0000_0000, _GRIND_SID, ts_g + 1)
