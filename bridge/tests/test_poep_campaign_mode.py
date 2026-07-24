"""POEP-CAMPAIGN (1b) tests - grok campaign-r02 bars made mechanical (no HID, no rig).

Bars covered: B-FLAGS (config default False + env wiring; l6b_enabled untouched), B-FIRE/B-FIRE-OFF
(endpoint gate accepts campaign OR l6b, refuses both-off), B-L6-ACTIVE/B-L6B-ACTIVE/B-AUTOTICK/R3/C
(source pins on the formula + dispatch + ring-live + policy_ref seams), B-POLICY (campaign policy
counts via the REAL is_usable_reflex; the CCO T0 policy stays denylisted).
"""
import asyncio
import re
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge.vapi_bridge.dualshock_integration import DualShockTransport, PoepFireRefused
from l9_presence.poep_reflex_gate import is_usable_reflex

_ENV = "POEP_LIVE_FIRE_ENABLED"
_SRC = (Path(__file__).resolve().parents[2] / "bridge" / "vapi_bridge" / "dualshock_integration.py"
        ).read_text(encoding="utf-8")


# ── B-FLAGS: config field wiring (campaign never touches l6b_enabled) ─────────
def test_config_campaign_default_false_and_env_wired(monkeypatch):
    monkeypatch.delenv("POEP_CAMPAIGN_MODE", raising=False)
    monkeypatch.delenv("L6B_ENABLED", raising=False)
    from bridge.vapi_bridge.config import Config
    cfg = Config()
    assert cfg.poep_campaign_mode is False          # default OFF
    assert cfg.l6b_enabled is False
    monkeypatch.setenv("POEP_CAMPAIGN_MODE", "true")
    cfg2 = Config()
    assert cfg2.poep_campaign_mode is True          # env lift, process-scoped
    assert cfg2.l6b_enabled is False                # campaign NEVER flips the hard flag


# ── B-FIRE / B-FIRE-OFF: the endpoint gate (unbound-method pattern) ───────────
class _FakeDriver:
    def __init__(self):
        self.calls = []

    async def send_l6b_probe(self, ds, r2_force, mode):
        self.calls.append((int(r2_force), str(mode)))
        return 123.456

    async def clear_triggers(self, ds):
        return None


def _fake(*, l6b=False, campaign=False):
    return SimpleNamespace(
        _l6b_enabled=l6b,
        _poep_campaign_mode=campaign,
        _l6b_analyzer=object(),
        _l6_driver=_FakeDriver(),
        _reader=SimpleNamespace(ds=object()),
        _l6b_pending=None,
        _l6b_post_buffer=[],
        _l6b_pre_buffer=deque([{"ax": 1.0}], maxlen=50),
        _poep_fire_inflight=False,
        _cfg=SimpleNamespace(l6b_probe_mode="pulse", l6b_probe_hold_ms=15),
        _POEP_FIRE_AMP_MAX=80,
    )


def test_fire_gate_accepts_campaign_without_l6b(monkeypatch):
    monkeypatch.setenv(_ENV, "1")
    ns = _fake(l6b=False, campaign=True)

    async def _run():
        fut = await DualShockTransport.request_poep_nonce_probe(ns, "n_campaign", 60)
        assert ns._l6b_pending["poep_nonce"] == "n_campaign"
        assert not fut.done()

    asyncio.run(_run())


def test_fire_gate_refuses_both_off(monkeypatch):
    monkeypatch.setenv(_ENV, "1")
    with pytest.raises(PoepFireRefused) as ei:
        asyncio.run(DualShockTransport.request_poep_nonce_probe(_fake(), "n", 60))
    assert ei.value.status_code == 503
    assert "poep_campaign_mode" in str(ei.value)     # the refusal names both gates


def test_fire_gate_still_env_gated_under_campaign(monkeypatch):
    monkeypatch.delenv(_ENV, raising=False)
    with pytest.raises(PoepFireRefused) as ei:
        asyncio.run(DualShockTransport.request_poep_nonce_probe(_fake(campaign=True), "n", 60))
    assert "gated" in str(ei.value)                  # campaign does not bypass POEP_LIVE_FIRE_ENABLED


# ── B-L6-ACTIVE (V3): L6 gates on the ANALYZER, never the driver ──────────────
def test_v3_l6_active_gates_on_analyzer_not_driver():
    assert re.search(r"_l6_active\s*=\s*self\._l6_analyzer is not None", _SRC), \
        "V3 pin missing: _l6_active must gate on the analyzer"
    assert not re.search(r"_l6_active\s*=\s*self\._l6_driver is not None", _SRC), \
        "V3 regression: _l6_active gates on the driver (latent formula bug)"


# ── B-L6B-ACTIVE (V1): the L6b contribution requires l6b_enabled ──────────────
def test_v1_l6b_active_requires_l6b_enabled():
    m = re.search(r"_l6b_active\s*=\s*\((.*?)\)", _SRC, re.DOTALL)
    assert m, "V1 pin missing: _l6b_active block not found"
    assert "self._l6b_enabled" in m.group(1), \
        "V1 regression: _l6b_active does not require l6b_enabled (campaign would leak 0.14 weight)"


# ── B-AUTOTICK (V4): the auto-tick dispatch stays STRICTLY l6b_enabled-gated ──
def test_v4_auto_tick_never_ors_campaign():
    # anchor on the dispatch condition's unique token; take the enclosing condition lines
    idx = _SRC.index("% _l6b_interval == 0")            # first occurrence = the dispatch gate
    start = _SRC.rindex("if (", 0, idx)
    end = _SRC.index("):", idx)
    cond = _SRC[start:end]
    assert "self._l6b_enabled" in cond
    assert "_poep_campaign_mode" not in cond, \
        "V4 regression: campaign mode leaked into the auto-tick dispatch gate"


# ── R3: the ring (buffers+completion) is live under campaign ──────────────────
def test_r3_ring_live_includes_campaign():
    assert re.search(
        r"_l6b_ring_live\s*=\s*\(\s*\(self\._l6b_enabled and _l6b_applicable\)\s*"
        r"or \(self\._poep_campaign_mode and self\._l6b_analyzer is not None\)", _SRC), \
        "R3 pin missing: campaign path absent from the ring-live gate"


# ── C: campaign/nonce-bound fires stamp the allowlisted corpus policy ─────────
def test_c_policy_ref_override_present():
    assert '"edge_operator_reflex_v1"' in _SRC
    m = re.search(r'policy_ref=\(\s*"edge_operator_reflex_v1"\s*if \(self\._l6b_pending\.get\("poep_nonce"\)'
                  r"\s*or self\._poep_campaign_mode\)", _SRC)
    assert m, "C pin missing: policy_ref override for nonce-bound/campaign fires"


# ── B-POLICY: through the REAL usable-reflex gate ─────────────────────────────
def test_b_policy_campaign_rows_count_cco_rows_do_not():
    good = dict(reflex_verdict="REFLEX_OBSERVED", accel_delta_peak=3000.0, latency_ms=250.0)
    assert is_usable_reflex(policy_ref="edge_operator_reflex_v1", **good) is True
    assert is_usable_reflex(policy_ref="CCO_T0_POLICY_v1_OPTION_C", **good) is False   # denylisted
    # and a campaign-policy row still fails on bad physics (the gate is policy AND physics)
    assert is_usable_reflex(policy_ref="edge_operator_reflex_v1",
                            reflex_verdict="REFLEX_OBSERVED",
                            accel_delta_peak=0.0, latency_ms=250.0) is False


# ── T1: campaign state surfaced honestly in pitl_meta (never as enablement) ───
def test_t1_pitl_meta_surfaces_campaign_flag():
    assert '"poep_campaign_mode":   self._poep_campaign_mode,' in _SRC
