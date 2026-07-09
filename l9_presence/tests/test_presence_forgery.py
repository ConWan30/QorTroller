"""ADVERSARY-EXPAND tests — the presence-forgery attack -> rail matrix must HOLD.

Each attack forges/tampers a real artifact and asserts the targeted verifier REJECTS it. A single
un-rejected attack is a real finding (holds=False) — this suite fails loudly if any rail opens.
"""
from __future__ import annotations

from l9_presence.adversarial.presence_forgery import ATTACKS, run_forgery_matrix


def test_matrix_holds_every_attack_rejected():
    r = run_forgery_matrix()
    unrejected = [a.name for a in r.results if not a.rejected]
    assert r.holds is True, f"open rails: {unrejected}"
    assert len(r.results) == len(ATTACKS) >= 11


def test_every_attack_names_a_rail_and_target():
    for a in run_forgery_matrix().results:
        assert a.rail and a.target and a.name
        assert isinstance(a.rejected, bool)


def test_five_verifiers_covered():
    targets = {a.target for a in run_forgery_matrix().results}
    assert {"posp_verifier", "kas_deferred", "bcc_match", "port_cert", "event_bind"}.issubset(targets)


def test_markdown_banner_reflects_hold():
    md = run_forgery_matrix().to_markdown()
    assert "ALL FORGERIES REJECTED" in md
    assert "**NO**" not in md               # no open rail rendered


def test_each_attack_individually_rejects():
    for atk in ATTACKS:
        res = atk()
        assert res.rejected, f"{res.name} did NOT reject ({res.rail}): {res.detail}"
