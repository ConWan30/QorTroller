"""Arc 6/7 Phase 1 — PoSR session-recency wiring tests.

Covers the recency DATA PATH (open capture -> persist -> close read ->
strictly-after -> chained close commitment) without the heavy full
package_session setup. The proof itself stays v1 in Phase 1; these tests
validate the recency metadata + the honesty rails (INV-POSR-WIRING-001/002/003).
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.store import Store  # noqa: E402
from vapi_bridge.config import Config  # noqa: E402
from vapi_bridge.curator_packaging_loop import CuratorPackagingLoop  # noqa: E402
from vapi_bridge.replay_proof_pipeline.pipeline import VAPIReplayProofPipeline  # noqa: E402
from vapi_bridge.replay_proof_pipeline.posr import compute_close_beacon_commitment  # noqa: E402


_OPEN_BLOCK = 45008576
_OPEN_HASH = "0x" + "ab" * 32
_OPEN_COMMIT = "0x" + "cd" * 32


class _FakeChain:
    """Minimal chain stub: get_latest_temporal_beacon returns (block, hash) or
    None. Counts calls so we can assert the flag-off path never touches it."""

    def __init__(self, beacon):
        self._beacon = beacon
        self.calls = 0

    async def get_latest_temporal_beacon(self):
        self.calls += 1
        return self._beacon


class _Cfg:
    def __init__(self, *, enabled=True, gsid="grind_test"):
        self.posr_recency_enabled = enabled
        self.grind_session_id = gsid


def _store():
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "t.db"))


def _pipeline(chain, cfg, store):
    return VAPIReplayProofPipeline(chain=chain, cfg=cfg, store=store)


# ── C5.1 — INV-POSR-WIRING-003: default-OFF flag ────────────────────────────

def test_config_default_posr_recency_disabled():
    """INV-POSR-WIRING-003 — posr_recency_enabled defaults False."""
    os.environ.pop("POSR_RECENCY_ENABLED", None)
    assert Config().posr_recency_enabled is False


@pytest.mark.asyncio
async def test_flag_off_no_recency_and_no_chain_touch():
    """Flag OFF -> blank recency AND the binder/chain is never read."""
    chain = _FakeChain((_OPEN_BLOCK + 100, bytes.fromhex("ee" * 32)))
    store = _store()
    store.insert_posr_session_open("grind_test", _OPEN_BLOCK, _OPEN_HASH, _OPEN_COMMIT, "")
    pl = _pipeline(chain, _Cfg(enabled=False), store)
    r = await pl._compute_recency("42", "devid")
    assert r["recency_bound"] is False
    assert chain.calls == 0  # flag-off must not touch the chain


# ── C5.2 — no-beacon -> v1 fallback (INV-POSR-WIRING-001) ───────────────────

@pytest.mark.asyncio
async def test_no_open_row_falls_back():
    """No captured open beacon -> recency_bound False (never fabricated)."""
    chain = _FakeChain((_OPEN_BLOCK + 100, bytes.fromhex("ee" * 32)))
    pl = _pipeline(chain, _Cfg(), _store())  # empty store
    r = await pl._compute_recency("42", "devid")
    assert r["recency_bound"] is False


@pytest.mark.asyncio
async def test_no_close_beacon_falls_back():
    """Open captured but registry has no beacon (None) -> v1 fallback."""
    store = _store()
    store.insert_posr_session_open("grind_test", _OPEN_BLOCK, _OPEN_HASH, _OPEN_COMMIT, "")
    pl = _pipeline(_FakeChain(None), _Cfg(), store)
    r = await pl._compute_recency("42", "devid")
    assert r["recency_bound"] is False


# ── C5.3 — same-beacon (open==close) -> no spurious recency (INV-002) ───────

@pytest.mark.asyncio
async def test_same_block_no_spurious_recency():
    """close.block == open.block must NOT bind recency (strictly-after rail)."""
    store = _store()
    store.insert_posr_session_open("grind_test", _OPEN_BLOCK, _OPEN_HASH, _OPEN_COMMIT, "")
    pl = _pipeline(_FakeChain((_OPEN_BLOCK, bytes.fromhex("ee" * 32))), _Cfg(), store)
    r = await pl._compute_recency("42", "devid")
    assert r["recency_bound"] is False


@pytest.mark.asyncio
async def test_close_before_open_no_recency():
    """close.block < open.block (reorg/regression) -> no recency."""
    store = _store()
    store.insert_posr_session_open("grind_test", _OPEN_BLOCK, _OPEN_HASH, _OPEN_COMMIT, "")
    pl = _pipeline(_FakeChain((_OPEN_BLOCK - 64, bytes.fromhex("ee" * 32))), _Cfg(), store)
    r = await pl._compute_recency("42", "devid")
    assert r["recency_bound"] is False


# ── C5.4 — genuine open<close -> recency bound + chained close commitment ────

@pytest.mark.asyncio
async def test_genuine_recency_binds_and_chains():
    """open<close -> recency_bound True; close commitment == the FROZEN
    compute_close_beacon_commitment over (close, open_commitment, poac_final)."""
    close_block = _OPEN_BLOCK + 128
    close_hash = bytes.fromhex("ee" * 32)
    store = _store()
    store.insert_posr_session_open("grind_test", _OPEN_BLOCK, _OPEN_HASH, _OPEN_COMMIT, "")
    pl = _pipeline(_FakeChain((close_block, close_hash)), _Cfg(), store)
    r = await pl._compute_recency("42", "devid")
    assert r["recency_bound"] is True
    assert r["open_beacon_block"] == _OPEN_BLOCK
    assert r["close_beacon_block"] == close_block

    import hashlib
    expected = compute_close_beacon_commitment(
        close_block_number=close_block,
        close_block_hash=close_hash,
        open_beacon_commitment=bytes.fromhex("cd" * 32),
        poac_final_link=hashlib.sha256(b"VAPI-POSR-FINAL:42").digest(),
    )
    assert r["close_beacon_commitment"] == "0x" + expected.hex()


# ── C5.5 — on_session_open_vhr capture + idempotency + honest no-op ─────────

@pytest.mark.asyncio
async def test_open_capture_persists_and_is_idempotent():
    store = _store()
    loop = CuratorPackagingLoop(
        chain=_FakeChain((_OPEN_BLOCK, bytes.fromhex("11" * 32))),
        cfg=_Cfg(), store=store,
    )
    r1 = await loop.on_session_open_vhr("grind_test", device_id="dev")
    assert r1["outcome"] == "posr_open_captured"
    assert r1["open_block"] == _OPEN_BLOCK
    row = store.get_posr_session_open("grind_test")
    assert row is not None and row["open_block"] == _OPEN_BLOCK
    # second call -> already captured (first wins)
    r2 = await loop.on_session_open_vhr("grind_test", device_id="dev")
    assert r2["outcome"] == "posr_open_already_captured"


@pytest.mark.asyncio
async def test_open_capture_no_beacon_is_honest_noop():
    store = _store()
    loop = CuratorPackagingLoop(chain=_FakeChain(None), cfg=_Cfg(), store=store)
    r = await loop.on_session_open_vhr("grind_test", device_id="dev")
    assert r["outcome"] == "posr_open_no_beacon"
    assert store.get_posr_session_open("grind_test") is None  # nothing fabricated


@pytest.mark.asyncio
async def test_open_capture_disabled_flag():
    loop = CuratorPackagingLoop(
        chain=_FakeChain((_OPEN_BLOCK, bytes.fromhex("11" * 32))),
        cfg=_Cfg(enabled=False), store=_store(),
    )
    r = await loop.on_session_open_vhr("grind_test", device_id="dev")
    assert r["outcome"] == "posr_disabled"
