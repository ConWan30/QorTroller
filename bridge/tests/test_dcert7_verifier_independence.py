"""D-CERT-7 — explicit verifier_independence rail (cycle-59).

The independence rail was implicit in population_certified=False; a consumer reading only
cert_scope / is_developer_self_certified() could launder developer_self into third-party trust.
This makes it a declarative structural field on the proof:
  None  -> no cert scope (advisory), N/A;
  False -> self-certified (developer_self): verifier == subject, do NOT launder;
  True  -> independent verifier (population/tournament): unreachable today.

Self-describing != more-certified: this ADDS an honesty signal; it changes no verdict. Pure code.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "bridge")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vapi_bridge.novel_presence_fusion import (
    NovelPresenceFusionOrchestrator,
    FusedGamerPresenceProof,
)


def _fuse(developer_self_cert: bool):
    return NovelPresenceFusionOrchestrator().fuse(
        device_id="dev123", record_hash="rec456", poep_present=True,
        developer_self_cert=developer_self_cert,
    )


def test_developer_self_proof_is_explicitly_not_independent():
    p = _fuse(developer_self_cert=True)
    assert p.cert_scope == "developer_self"
    assert p.verifier_independence is False          # explicit: verifier == subject, do not launder
    assert p.population_certified is False            # the old implicit rail is still there, unchanged


def test_advisory_proof_has_na_independence():
    p = _fuse(developer_self_cert=False)
    assert p.cert_scope == "advisory"
    assert p.verifier_independence is None            # no cert scope applies -> N/A, not False


def test_abstain_path_defaults_to_none():
    # missing device_id -> UNVERIFIABLE abstain construction; no cert scope -> None (dataclass default)
    p = NovelPresenceFusionOrchestrator().fuse(device_id="", record_hash="")
    assert p.verifier_independence is None


def test_old_construction_is_backward_compatible():
    # a proof built without the field (old call sites / tests) -> None, never errors.
    p = FusedGamerPresenceProof(verdict=None, device_id="d", record_hash="r")
    assert p.verifier_independence is None


def test_independence_is_never_true_today():
    # The whole point: no path reaches True (independent verifier). False/None only.
    for dsc in (True, False):
        assert _fuse(dsc).verifier_independence is not True


def test_field_is_structural_function_of_scope():
    # verifier_independence is False IFF cert_scope == developer_self (a structural fact, not data).
    for dsc in (True, False):
        p = _fuse(dsc)
        assert (p.verifier_independence is False) == (p.cert_scope == "developer_self")
