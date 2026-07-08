"""ACT-1 A1 — BCC env-wire tests (F-ACT-1 fix).

Pins: BCC_ENABLED env opts IN; absence = code default OFF (dormant preserved);
sublane B is an independent opt-in; falsy strings stay off.
"""
from __future__ import annotations

from l9_presence.witness_agent import WitnessConfig


def test_default_stays_dormant(monkeypatch):
    monkeypatch.delenv("BCC_ENABLED", raising=False)
    monkeypatch.delenv("BCC_SUBLANE_B_ENABLED", raising=False)
    c = WitnessConfig()
    assert c.bcc_enabled is False and c.bcc_sublane_b_enabled is False


def test_env_opts_in(monkeypatch):
    monkeypatch.setenv("BCC_ENABLED", "true")
    c = WitnessConfig()
    assert c.bcc_enabled is True
    assert c.bcc_sublane_b_enabled is False        # independent opt-in — never implied


def test_sublane_b_independent(monkeypatch):
    monkeypatch.setenv("BCC_ENABLED", "1")
    monkeypatch.setenv("BCC_SUBLANE_B_ENABLED", "true")
    c = WitnessConfig()
    assert c.bcc_enabled is True and c.bcc_sublane_b_enabled is True


def test_falsy_strings_stay_off(monkeypatch):
    for v in ("false", "0", "", "no"):
        monkeypatch.setenv("BCC_ENABLED", v)
        assert WitnessConfig().bcc_enabled is False
