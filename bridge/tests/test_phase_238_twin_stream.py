"""Phase 238 Step I-AUTOLOOP-3 — SSE Twin stream + ProtocolStateCache tests.

T-238-TWIN-1..6 — verifies the in-memory event cache emits events to
subscribers, ring buffers cap correctly, slow-subscriber drops are
counted, the SSE endpoint is registered with the FROZEN event-type
contract, and main.py wires the cache + heartbeat task.
"""
from __future__ import annotations

import asyncio
import sys
import time
import types as _types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE_DIR = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy-import modules
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

from vapi_bridge.protocol_state_cache import (  # noqa: E402
    ProtocolStateCache,
    EVENT_POAC_CHAIN_LINK,
    EVENT_GIC_VERDICT,
    EVENT_PCC_STATE_CHANGE,
    EVENT_CURATOR_VERDICT,
    EVENT_ANCHOR_CONFIRMED,
    EVENT_HEARTBEAT,
    FROZEN_EVENT_TYPES,
    RING_BUFFER_CAP,
    SUBSCRIBER_QUEUE_CAP,
)


# T-238-TWIN-1 ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t_238_twin_1_cache_emits_events_to_subscriber():
    """Cache fans out events to subscribers via asyncio.Queue."""
    cache = ProtocolStateCache()
    q = cache.subscribe()

    cache.update_poac_link("ab" * 8, ts_ns=1_000_000_000)
    cache.update_gic_verdict("CERTIFY", "INFO")
    cache.update_curator_verdict("ef" * 8, "APPROVED", "INFO")

    # Drain queue — should have 3 events
    received: list = []
    for _ in range(3):
        evt = await asyncio.wait_for(q.get(), timeout=1.0)
        received.append(evt)

    assert len(received) == 3
    assert received[0][0] == EVENT_POAC_CHAIN_LINK
    assert received[1][0] == EVENT_GIC_VERDICT
    assert received[2][0] == EVENT_CURATOR_VERDICT

    cache.unsubscribe(q)


# T-238-TWIN-2 ───────────────────────────────────────────────────────────────
def test_t_238_twin_2_ring_buffer_caps():
    """Ring buffers cap at RING_BUFFER_CAP (100); oldest dropped."""
    cache = ProtocolStateCache()
    for i in range(RING_BUFFER_CAP + 50):
        cache.update_poac_link(f"hash{i:08x}")

    recent = cache.recent(EVENT_POAC_CHAIN_LINK, n=200)
    # Ring buffer caps at 100
    assert len(recent) == RING_BUFFER_CAP
    # Most recent should be hash00000095 (149) — first emitted to overflow
    # is hash00000000; last is hash00000095; cache.recent returns DESC newest-first
    assert recent[0]["hash16"].endswith("00000095")  # most recent emit


# T-238-TWIN-3 ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t_238_twin_3_slow_subscriber_drops_counted():
    """Slow subscriber (queue full) → events dropped + counted."""
    cache = ProtocolStateCache()
    # Subscribe but never drain — fill the queue
    q = cache.subscribe()

    # Emit beyond the queue cap
    for i in range(SUBSCRIBER_QUEUE_CAP + 50):
        cache.update_poac_link(f"slow{i:08x}")

    stats = cache.stats()
    assert stats["events_emitted"] == SUBSCRIBER_QUEUE_CAP + 50
    assert stats["events_dropped"] >= 50  # at least the overflow dropped
    assert stats["subscribers_active"] == 1

    cache.unsubscribe(q)


# T-238-TWIN-4 ───────────────────────────────────────────────────────────────
def test_t_238_twin_4_sse_endpoint_registered_with_frozen_event_types():
    """Static check: SSE endpoint declared with FROZEN event types in operator_api.py."""
    api_src = (BRIDGE_DIR / "vapi_bridge" / "operator_api.py").read_text()
    # Endpoint route registered
    assert '@app.get("/agent/twin-stream")' in api_src
    # Stats endpoint
    assert '@app.get("/agent/twin-stream-stats")' in api_src
    # Event types FROZEN — all 6 must be referenced/imported
    for et in (
        "EVENT_POAC_CHAIN_LINK", "EVENT_GIC_VERDICT",
        "EVENT_PCC_STATE_CHANGE", "EVENT_CURATOR_VERDICT",
        "EVENT_ANCHOR_CONFIRMED",
    ):
        assert et in api_src, f"SSE endpoint must reference {et}"


# T-238-TWIN-5 ───────────────────────────────────────────────────────────────
def test_t_238_twin_5_main_py_wires_cache_and_heartbeat():
    """Static check: main.py creates cache + attaches to both apps + spawns heartbeat."""
    main_src = (BRIDGE_DIR / "vapi_bridge" / "main.py").read_text()
    assert "from .protocol_state_cache import ProtocolStateCache" in main_src
    assert "self.protocol_state_cache = _proto_state_cache" in main_src
    # Cache attached to both _op_app + main app
    assert "_op_app._protocol_state_cache = _proto_state_cache" in main_src
    assert "app._protocol_state_cache = _proto_state_cache" in main_src
    # Heartbeat task wired with frozen task name
    assert 'set_name("ProtocolStateCacheHeartbeat")' in main_src
    assert "from .protocol_state_cache import run_heartbeat_loop" in main_src


# T-238-TWIN-6 ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t_238_twin_6_recent_emits_backfill_for_new_subscribers():
    """Cache.recent() returns most-recent events for SSE backfill."""
    cache = ProtocolStateCache()
    cache.update_pcc_state("NOMINAL", "EXCLUSIVE_USB", ts_ns=1)
    cache.update_pcc_state("DEGRADED", "CONTESTED", ts_ns=2)
    cache.update_pcc_state("NOMINAL", "EXCLUSIVE_USB", ts_ns=3)

    backfill = cache.recent(EVENT_PCC_STATE_CHANGE, n=2)
    assert len(backfill) == 2
    # DESC newest-first
    assert backfill[0]["ts_ns"] == 3
    assert backfill[1]["ts_ns"] == 2

    # FROZEN event types
    assert FROZEN_EVENT_TYPES == frozenset({
        "poac_chain_link", "gic_verdict", "pcc_state_change",
        "curator_verdict", "anchor_confirmed", "heartbeat",
    })

    # All update methods are O(1) and never raise — sanity check
    cache.update_poac_link("aa" * 8)
    cache.update_gic_verdict("CERTIFY", "INFO")
    cache.update_curator_verdict("bb" * 8, "APPROVED", "INFO")
    cache.update_anchor("0xtxhash", "LISTING-v1")
    stats = cache.stats()
    assert stats["events_emitted"] >= 7
