"""D-CERT-6 — single-source the developer N-gate (cycle-59).

The N>=30 developer gate existed as three uncoordinated literals (enroll --min-n default;
single_subject_reflex_model(min_n=30) default; the DEAD config.developer_self_cert_min_reflex_n).
This wires the config field as THE source: enroll's --min-n default reads it, an explicit CLI
override still wins but is logged, and the emitted governing_model embeds the config-sourced value
by construction — so any future mismatch is instantly visible on the artifact. Pure code + tests.
"""
from __future__ import annotations

import importlib.util
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "bridge")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_ENROLL = os.path.join(_ROOT, "scripts", "poep_session_enroll.py")
_spec = importlib.util.spec_from_file_location("poep_session_enroll", _ENROLL)
pse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pse)
resolve_min_n = pse.resolve_min_n
compute_evidence_base = pse.compute_evidence_base

from vapi_bridge.config import Config


def test_config_is_the_source_when_no_cli_override():
    val, note = resolve_min_n(None, 42)
    assert val == 42 and note is None            # config value flows through, no noise


def test_cli_override_wins_and_is_flagged():
    val, note = resolve_min_n(25, 30)
    assert val == 25                             # explicit operator intent honored
    assert note is not None and "OVERRIDES" in note and "30" in note and "25" in note


def test_cli_matching_config_is_silent():
    val, note = resolve_min_n(30, 30)
    assert val == 30 and note is None            # no spurious divergence note


def test_config_value_flows_to_governing_model():
    # the emitted governing_model embeds the resolved min_n -> a config change is visible on the artifact
    model = {"n_reactions": 52, "calibration_complete": True, "latency_mean_ms": 200.4,
             "latency_std_ms": 30.2, "band_lo_ms": 124.9, "band_hi_ms": 275.9}
    resolved, _ = resolve_min_n(None, 42)        # config=42, no CLI override
    vf, _disc = compute_evidence_base(model, "DEV", resolved)
    assert vf["governing_model"] == "developer_self:single_subject_reflex_v1:min_n=42"


def test_gate_follows_config_for_any_value():
    # the three-literals regression: change config -> the resolved gate follows (no drift)
    for cfg_val in (10, 30, 50, 99):
        assert resolve_min_n(None, cfg_val)[0] == cfg_val


def test_dead_config_field_is_now_live():
    # the previously-dead field is now consumed by enroll's resolver; confirm it exists + is an int.
    assert isinstance(Config().developer_self_cert_min_reflex_n, int)
