"""Tests for the PoEP verification card (no hardware)."""
from l9_presence.poep_card import render_poep_card


def test_card_present_verdict_contains_fields():
    html = render_poep_card(player="P1", device_id="Edge", verdict="PRESENT",
                            latency_ms=290, band=[231.5, 349.0], liveness_pass=True,
                            device_auth_pass=True, device_auth_score=1.0,
                            commitment="54730b5b", ts_iso="2026-05-22T00:00:00+00:00")
    assert "PRESENT" in html and "54730b5b" in html and "Embodied Presence" in html


def test_card_honest_disclaimers_present():
    html = render_poep_card(player="P1", device_id="Edge", verdict="REJECT",
                            latency_ms=45, band=[231.5, 349.0], liveness_pass=False,
                            device_auth_pass=True, device_auth_score=1.0,
                            commitment="abc", ts_iso="2026-05-22T00:00:00+00:00")
    low = html.lower()
    assert "not" in low and "zero-knowledge" in low      # not a ZK proof
    assert "not activated" in low                          # governance/L6B gate stated
    assert "post-quantum" in low                           # born-PQ stated
