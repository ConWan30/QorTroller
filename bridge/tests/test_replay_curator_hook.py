"""Data Economy Arc 5 Commit 4.5 — Curator hook + HTTP endpoint suite.

Covers:
  • CuratorPackagingLoop.on_session_complete_vhr — dormant default + lazy
    pipeline construction when cfg.replay_proof_pipeline_enabled flips.
  • CuratorPackagingLoop.list_pending_replay_proofs pass-through.
  • Existing skill-proof flow (on_session_complete) UNTOUCHED by the hook.
  • Store.get_pending_replay_proofs — outcome filter + ts_ns ordering.
  • GET /curator/pending-replay-proofs — auth gate + shape.

All in-memory / monkeypatched — no chain RPC, no snarkjs.
"""

import asyncio
import time
from dataclasses import dataclass

import pytest

from bridge.vapi_bridge.curator_packaging_loop import CuratorPackagingLoop


@dataclass
class _Cfg:
    curator_packaging_enabled: bool = False
    replay_proof_pipeline_enabled: bool = False
    replay_proof_verifier_address: str = ""
    consent_registry_address: str = ""


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Hook dormancy / activation ──────────────────────────────────────────────

def test_on_session_complete_vhr_dormant_when_pipeline_disabled():
    loop = CuratorPackagingLoop(chain=None, cfg=_Cfg(), store=None)
    out = _run(loop.on_session_complete_vhr("S1"))
    assert out["outcome"] == "vhr_disabled"
    assert "replay_proof_pipeline_enabled=False" in out["reason"]


def test_pipeline_lazy_constructed_on_first_call_when_enabled(monkeypatch):
    """Lazy construction keeps numpy off the hot path until the flag flips."""
    cfg = _Cfg(replay_proof_pipeline_enabled=True)
    loop = CuratorPackagingLoop(chain=None, cfg=cfg, store=None)
    assert loop._vhr_pipeline is None
    # First call instantiates; chain is None → manifest absent → DEFERRED_NO_CONSENT.
    out = _run(loop.on_session_complete_vhr("S1"))
    assert loop._vhr_pipeline is not None
    assert out["outcome"] in ("vhr_deferred_no_consent", "vhr_aborted_no_session")
    # Second call REUSES the pipeline — no fresh instantiation.
    same = loop._vhr_pipeline
    _run(loop.on_session_complete_vhr("S2"))
    assert loop._vhr_pipeline is same


def test_list_pending_replay_proofs_returns_empty_when_dormant():
    loop = CuratorPackagingLoop(chain=None, cfg=_Cfg(), store=None)
    assert loop.list_pending_replay_proofs() == []


# ── Hook does NOT disturb existing skill-proof path ────────────────────────

def test_existing_on_session_complete_unaffected_by_hook():
    """The skill-proof path returns OUTCOME_DISABLED when curator_packaging is
    off; the VHR hook adds nothing to that surface. Regression guard for
    Commit 4.5's lazy-init not leaking imports into the skill flow."""
    loop = CuratorPackagingLoop(chain=None, cfg=_Cfg(), store=None)
    out = _run(loop.on_session_complete("S1"))
    assert out["outcome"] == "DISABLED"
    # The skill flow MUST NOT have constructed a VHR pipeline as a side-effect.
    assert loop._vhr_pipeline is None


# ── Store pending-replay-proofs accessor ───────────────────────────────────

def _fresh_store(tmp_path):
    """Build a real Store on a fresh sqlite file in tmp_path."""
    from bridge.vapi_bridge.store import Store
    db_path = tmp_path / "test_bridge.db"
    return Store(str(db_path))


def test_store_get_pending_replay_proofs_filters_outcomes_and_orders(tmp_path):
    store = _fresh_store(tmp_path)
    # Seed audit log with VHR + non-VHR entries.
    now_ns = time.time_ns()
    rows = [
        ("vhr_packaging", "S1", "vhr_proof_deferred", {"reason": "ceremony"}, now_ns - 300),
        ("vhr_packaging", "S2", "vhr_proof_built_no_verifier", {"reason": "no addr"}, now_ns - 200),
        ("vhr_packaging", "S3", "vhr_proof_built", {"verifier": "0xabc"}, now_ns - 100),
        # Non-pending VHR — must NOT appear.
        ("vhr_packaging", "S4", "vhr_deferred_no_consent", {}, now_ns - 50),
        # Skill-proof flow entries — different action, must NOT appear even
        # though outcome strings are unrelated.
        ("packaging", "S5", "PENDING_APPROVAL", {}, now_ns - 10),
    ]
    for action, sid, outcome, extra, ts in rows:
        store.record_curator_packaging_action({
            "action": action, "session_id": sid, "outcome": outcome,
            "extra": extra, "ts_ns": ts,
        })

    pending = store.get_pending_replay_proofs()
    sids = [r["session_id"] for r in pending]
    # Only the 3 pending VHR outcomes, ordered ts_ns DESC.
    assert sids == ["S3", "S2", "S1"]
    # extra round-trips as a dict (JSON-decoded).
    assert pending[0]["extra"] == {"verifier": "0xabc"}


def test_store_get_pending_replay_proofs_honors_limit(tmp_path):
    store = _fresh_store(tmp_path)
    base_ns = time.time_ns()
    for i in range(5):
        store.record_curator_packaging_action({
            "action": "vhr_packaging", "session_id": f"S{i}",
            "outcome": "vhr_proof_deferred", "extra": {},
            "ts_ns": base_ns + i,
        })
    rows = store.get_pending_replay_proofs(limit=2)
    assert len(rows) == 2


def test_store_get_pending_replay_proofs_empty_when_no_entries(tmp_path):
    store = _fresh_store(tmp_path)
    assert store.get_pending_replay_proofs() == []


# ── HTTP endpoint ──────────────────────────────────────────────────────────

def _make_app(tmp_path, *, api_key="testkey"):
    from bridge.vapi_bridge.operator_api import create_operator_app
    store = _fresh_store(tmp_path)
    cfg = _Cfg()
    cfg.operator_api_key = api_key   # set after construction (dataclass-friendly)
    app = create_operator_app(cfg, store)
    return app, store


def test_endpoint_requires_api_key(tmp_path):
    from fastapi.testclient import TestClient
    app, _ = _make_app(tmp_path)
    client = TestClient(app)
    # No api_key query param → 422 (validation error) per FastAPI Query(...).
    r = client.get("/curator/pending-replay-proofs")
    assert r.status_code == 422


def test_endpoint_rejects_wrong_api_key(tmp_path):
    from fastapi.testclient import TestClient
    app, _ = _make_app(tmp_path, api_key="right")
    client = TestClient(app)
    r = client.get("/curator/pending-replay-proofs?api_key=wrong")
    assert r.status_code in (401, 403)


def test_endpoint_returns_empty_when_no_entries(tmp_path):
    from fastapi.testclient import TestClient
    app, _ = _make_app(tmp_path, api_key="ok")
    client = TestClient(app)
    r = client.get("/curator/pending-replay-proofs?api_key=ok")
    assert r.status_code == 200
    body = r.json()
    assert body == {"count": 0, "pending_replay_proofs": []}


def test_endpoint_returns_pending_entries(tmp_path):
    from fastapi.testclient import TestClient
    app, store = _make_app(tmp_path, api_key="ok")
    store.record_curator_packaging_action({
        "action": "vhr_packaging", "session_id": "S1",
        "outcome": "vhr_proof_deferred",
        "extra": {"reason": "ceremony"}, "ts_ns": time.time_ns(),
    })
    client = TestClient(app)
    r = client.get("/curator/pending-replay-proofs?api_key=ok")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    row = body["pending_replay_proofs"][0]
    assert row["session_id"] == "S1"
    assert row["outcome"] == "vhr_proof_deferred"
    assert row["extra"]["reason"] == "ceremony"
