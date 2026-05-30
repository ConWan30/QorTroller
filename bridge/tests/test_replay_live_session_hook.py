"""Data Economy Arc 5 Commit 6 — live-session VHR hook wiring test suite.

Covers:
  • Store.get_curator_session_aggregate: shape, missing ruling -> None,
    unvalidated ruling -> None, fully-validated ruling -> dict with the
    right keys.
  • SessionAdjudicatorValidationAgent._maybe_fire_vhr_hook: dormant-safe
    when cfg flag off, curator_loop None, or session_gamer_address empty;
    fires fire-and-forget task when all three are set.

All in-memory / tempfile / monkeypatch — no chain RPC, no snarkjs.
"""

import asyncio
import time
from dataclasses import dataclass

import pytest


def _fresh_store(tmp_path):
    from bridge.vapi_bridge.store import Store
    return Store(str(tmp_path / "test_bridge.db"))


# ── Store.get_curator_session_aggregate ─────────────────────────────────────

def test_aggregate_returns_none_for_missing_ruling(tmp_path):
    store = _fresh_store(tmp_path)
    assert store.get_curator_session_aggregate(99999) is None


def test_aggregate_returns_none_for_non_numeric_id(tmp_path):
    store = _fresh_store(tmp_path)
    assert store.get_curator_session_aggregate("not-a-number") is None
    assert store.get_curator_session_aggregate(None) is None


def _seed_ruling(store, *, verdict="HUMAN", confidence=0.92, validated=True):
    """Insert one agent_rulings row (+optionally one ruling_validation_log row).

    agent_rulings.device_id has a FK to devices(device_id); seed a stub device
    first or the INSERT fails IntegrityError.
    """
    with store._conn() as con:
        # FK target: seed devices row first.
        con.execute(
            "INSERT OR IGNORE INTO devices"
            " (device_id, pubkey_hex, first_seen, last_seen) VALUES (?, ?, ?, ?)",
            ("dev-stub", "ab" * 33, time.time(), time.time()),
        )
        cur = con.execute(
            "INSERT INTO agent_rulings"
            " (device_id, verdict, confidence, commitment_hash, source_agent, dry_run, created_at)"
            " VALUES (?, ?, ?, ?, 'session_adjudicator', 1, ?)",
            ("dev-stub", "HUMAN", 0.9, "abcd" * 16, time.time()),
        )
        rid = cur.lastrowid
        if validated:
            con.execute(
                "INSERT INTO ruling_validation_log"
                " (ruling_id, device_id, llm_verdict, fallback_verdict, llm_confidence,"
                "  fallback_confidence, divergence, created_at)"
                " VALUES (?, 'dev-stub', 'HUMAN', ?, 0.9, ?, 0, ?)",
                (rid, verdict, confidence, time.time()),
            )
    return rid


def test_aggregate_returns_none_when_ruling_not_yet_validated(tmp_path):
    store = _fresh_store(tmp_path)
    rid = _seed_ruling(store, validated=False)
    assert store.get_curator_session_aggregate(rid) is None


def test_aggregate_returns_full_shape_when_validated(tmp_path):
    store = _fresh_store(tmp_path)
    rid = _seed_ruling(store, verdict="HUMAN", confidence=0.92, validated=True)
    agg = store.get_curator_session_aggregate(rid)
    assert agg is not None
    # Required keys for the orchestrator's package_session call.
    for key in ("session_id", "device_id", "verdict",
                "humanity_probability", "vhp_token_id",
                "session_nonce", "ended_at"):
        assert key in agg, f"aggregate missing required key: {key}"
    assert agg["session_id"] == str(rid)
    assert agg["device_id"] == "dev-stub"
    assert agg["verdict"] == "HUMAN"          # fallback_verdict, not llm
    assert agg["humanity_probability"] == 0.92
    assert agg["vhp_token_id"] == 0           # v1 single-tenant default
    # session_nonce derives deterministically from commitment_hash hex (64 chars
    # of 'a' / 'b' / 'c' / 'd' repeating).
    assert isinstance(agg["session_nonce"], int)
    assert agg["session_nonce"] > 0


def test_aggregate_no_gamer_address_field_present(tmp_path):
    """Honest invariant: aggregate has NO gamer_address key. The Arc 5 hook
    supplies it from cfg.session_gamer_address at the call site (single-
    tenant v1). If a future commit adds device->gamer registry, that's where
    gamer_address would be sourced."""
    store = _fresh_store(tmp_path)
    rid = _seed_ruling(store)
    agg = store.get_curator_session_aggregate(rid)
    assert "gamer_address" not in agg


# ── Validator._maybe_fire_vhr_hook ──────────────────────────────────────────

@dataclass
class _Cfg:
    vhr_hook_enabled: bool = False
    session_gamer_address: str = ""
    validation_divergence_threshold: float = 0.3
    validation_gate_n: int = 100
    grind_mode: bool = False


class _LoopRecorder:
    """Stub for CuratorPackagingLoop. Records on_session_complete_vhr calls."""
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def on_session_complete_vhr(self, *, session_id, gamer_address, **kw):
        self.calls.append((session_id, gamer_address))
        return {"outcome": "vhr_disabled", "session_id": session_id}


def _make_validator(*, cfg, store, curator_loop=None):
    from bridge.vapi_bridge.session_adjudicator_validator import SessionAdjudicatorValidationAgent
    return SessionAdjudicatorValidationAgent(
        cfg, store, bus=None, curator_loop=curator_loop,
    )


def test_hook_no_op_when_vhr_hook_enabled_false(tmp_path):
    """Default-OFF posture: nothing fires when the flag is False."""
    store = _fresh_store(tmp_path)
    cfg = _Cfg(vhr_hook_enabled=False, session_gamer_address="0xD222c3fd")
    loop = _LoopRecorder()
    v = _make_validator(cfg=cfg, store=store, curator_loop=loop)
    v._maybe_fire_vhr_hook(ruling_id=1)
    assert loop.calls == []


def test_hook_no_op_when_curator_loop_is_none(tmp_path):
    """Boot wired no curator loop -> hook silently no-ops (defensive)."""
    store = _fresh_store(tmp_path)
    cfg = _Cfg(vhr_hook_enabled=True, session_gamer_address="0xD222c3fd")
    v = _make_validator(cfg=cfg, store=store, curator_loop=None)
    v._maybe_fire_vhr_hook(ruling_id=1)


def test_hook_no_op_when_session_gamer_address_empty(tmp_path):
    """Honest defer: SESSION_GAMER_ADDRESS unset -> no firing (orchestrator
    couldn't look up consent anyway)."""
    store = _fresh_store(tmp_path)
    cfg = _Cfg(vhr_hook_enabled=True, session_gamer_address="")
    loop = _LoopRecorder()
    v = _make_validator(cfg=cfg, store=store, curator_loop=loop)
    v._maybe_fire_vhr_hook(ruling_id=1)
    assert loop.calls == []


def test_hook_fires_when_all_three_conditions_true(tmp_path):
    """All three gates green -> fire-and-forget task created."""
    store = _fresh_store(tmp_path)
    cfg = _Cfg(vhr_hook_enabled=True,
               session_gamer_address="0xD222c3fd467Fa5140b3a81a3541d1a8A6185ed4f")
    loop = _LoopRecorder()
    v = _make_validator(cfg=cfg, store=store, curator_loop=loop)

    async def _run():
        v._maybe_fire_vhr_hook(ruling_id=42)
        # Yield so the fire-and-forget task gets scheduled + executed.
        await asyncio.sleep(0.05)
        assert len(loop.calls) == 1
        sid, gaddr = loop.calls[0]
        assert sid == "42"
        assert gaddr == "0xD222c3fd467Fa5140b3a81a3541d1a8A6185ed4f"

    asyncio.run(_run())


def test_hook_skips_when_no_running_event_loop(tmp_path):
    """Sync test context (no asyncio.run wrapper) — hook should detect the
    missing loop and skip rather than crash. Real bridge always has an
    event loop; this guards future test refactors."""
    store = _fresh_store(tmp_path)
    cfg = _Cfg(vhr_hook_enabled=True, session_gamer_address="0xabc")
    loop = _LoopRecorder()
    v = _make_validator(cfg=cfg, store=store, curator_loop=loop)
    # No asyncio.run wrapping — _maybe_fire_vhr_hook should swallow the
    # RuntimeError from create_task() not finding a running loop.
    v._maybe_fire_vhr_hook(ruling_id=99)
    assert loop.calls == []
