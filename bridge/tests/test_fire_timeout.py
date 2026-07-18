"""FIRE-TIMEOUT (F-RIG27-6) tests - grok firetimeout-r02 bars, fakes only (no rig, no HID).

The RP capture-drain (5-11s) exceeded the old 5s endpoint / 6s client timeouts, 504-ing every real
fire -> honest IDENTITY_ONLY. This pins the coordinated fix: env-configurable endpoint timeout
(default 20, clamped), client default 25 that OUTLASTS it, the ordering pin client>endpoint>drain,
the honest 504-on-stall (never a synthesized success), and the nonce-bound resolve INFO instrument.
"""
import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from l9_presence.poep_bridge_fire_adapter import (
    CLIENT_DEFAULT_TIMEOUT_S, ENDPOINT_FIRE_TIMEOUT_DEFAULT_S, MAX_OBSERVED_RP_DRAIN_S,
    make_bridge_fire_adapter,
)

_APP = (Path(__file__).resolve().parents[2] / "bridge" / "vapi_bridge" / "operator_api" / "_app.py"
        ).read_text(encoding="utf-8")
_DS = (Path(__file__).resolve().parents[2] / "bridge" / "vapi_bridge" / "dualshock_integration.py"
       ).read_text(encoding="utf-8")
_CLI = (Path(__file__).resolve().parents[2] / "scripts" / "poep_session_identity_attach.py"
        ).read_text(encoding="utf-8")


# ── the ordering pin: client > endpoint > max observed RP drain ───────────────
def test_ordering_pin():
    assert CLIENT_DEFAULT_TIMEOUT_S > ENDPOINT_FIRE_TIMEOUT_DEFAULT_S > MAX_OBSERVED_RP_DRAIN_S
    assert ENDPOINT_FIRE_TIMEOUT_DEFAULT_S == 20.0
    assert CLIENT_DEFAULT_TIMEOUT_S == 25.0


# ── client adapter default outlasts the endpoint ──────────────────────────────
def test_client_default_timeout_outlasts_endpoint():
    sig_default = make_bridge_fire_adapter.__defaults__  # keyword-only -> in __kwdefaults__
    kd = make_bridge_fire_adapter.__kwdefaults__
    assert kd["timeout_s"] == CLIENT_DEFAULT_TIMEOUT_S
    assert kd["timeout_s"] > ENDPOINT_FIRE_TIMEOUT_DEFAULT_S


# ── endpoint uses env POEP_FIRE_TIMEOUT_S, clamped [5,60], default 20 ──────────
def test_endpoint_env_configurable_and_clamped():
    # source pins (the route body is inside a closure; assert the wiring, not a live call)
    assert 'os.environ.get("POEP_FIRE_TIMEOUT_S", "20")' in _APP
    assert "max(5.0, min(60.0, _fire_to))" in _APP
    assert "asyncio.wait_for(fut, timeout=_fire_to)" in _APP
    # the honest 504 on stall is preserved
    assert re.search(r"raise HTTPException\(\s*504,", _APP)
    # the old hardcoded 5.0 is gone
    assert "wait_for(fut, timeout=5.0)" not in _APP


# ── wait-not-fabricate: a Future that resolves late (within timeout) returns the real dict ────
def test_slow_future_resolves_within_timeout():
    async def _run():
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        loop.call_later(0.05, lambda: fut.set_result(
            {"fired": True, "real_hardware": True, "nonce": "n", "t_fire_ns": 1,
             "latency_ms": 250.0, "peak_lsb": 3000.0, "precursor_gap_ms": 5.0, "error": ""}))
        return await asyncio.wait_for(fut, timeout=0.2)
    res = asyncio.run(_run())
    assert res["fired"] is True and res["nonce"] == "n"   # waited, got the REAL resolve


# ── timeout still honest: an unresolved Future raises TimeoutError (endpoint -> 504) ──────────
def test_unresolved_future_times_out_honestly():
    async def _run():
        loop = asyncio.get_event_loop()
        fut = loop.create_future()       # never resolved
        await asyncio.wait_for(fut, timeout=0.05)
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(_run())              # -> the endpoint maps this to 504, never a synthetic success


# ── the resolve INFO instrument: nonce-bound only, includes the analyze-outcome (error) ───────
def test_resolve_info_nonce_bound_only():
    resolve = _DS.split("def _resolve_poep_fire")[1].split("def _poll_frames")[0]
    assert "POEP-HID-RING: resolve nonce=" in resolve      # the INFO line exists
    assert "error=%s" in resolve                            # analyze-outcome (ok vs error) logged
    assert "post_n=%d" in resolve                           # sparsity signal (no buffer math change)
    # auto-tick can't reach here: no poep_future -> early quiet return
    assert "_p.get(\"poep_future\")" in resolve
    assert "if _fut is None:" in resolve
    # r03 residual: the log fires BEFORE the done-check so a post-504 late-complete still records
    assert "[client-gone]" in resolve
    assert resolve.index("log.info") < resolve.index("if _fut.done():")   # log precedes the done-guard


# ── the resolver still packs fired/real_hardware True by construction (rails untouched) ────────
def test_resolver_rails_untouched():
    ns = SimpleNamespace(
        _l6b_pending={"poep_future": None, "poep_nonce": "n", "poep_t_fire_ns": 1},
        _l6b_post_buffer=[])
    # a None future is a no-op (never raises) — the done-check rail
    from bridge.vapi_bridge.dualshock_integration import DualShockTransport
    DualShockTransport._resolve_poep_fire(ns, latency_ms=250.0, peak_lsb=3000.0, precursor_gap_ms=None)
    # honest-null branch still resolves fired=True (a real write happened) with latency None
    async def _run():
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        ns2 = SimpleNamespace(_l6b_pending={"poep_future": fut, "poep_nonce": "n2",
                                            "poep_t_fire_ns": 2}, _l6b_post_buffer=[1, 2, 3])
        DualShockTransport._resolve_poep_fire(ns2, latency_ms=None, peak_lsb=0.0,
                                              precursor_gap_ms=None, error="no clean reflex")
        return await asyncio.wait_for(fut, timeout=1.0)
    res = asyncio.run(_run())
    assert res["fired"] is True and res["real_hardware"] is True    # a real force fired
    assert res["latency_ms"] is None and res["error"] == "no clean reflex"   # honest, not band-filled


# ── CLI wires --fire-timeout into the factory (outlasts endpoint by default) ──────────────────
def test_cli_wires_fire_timeout():
    assert '"--fire-timeout"' in _CLI
    assert "default=25.0" in _CLI
    assert "timeout_s=args.fire_timeout" in _CLI
