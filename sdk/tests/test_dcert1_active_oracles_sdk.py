"""D-CERT-1 SDK — the active-oracles manifest travels with VAPIPresenceProof (cycle-59).

Under one-scope manifest-differentiation (D-CERT-1 (a)), the manifest IS the comparability mechanism;
an SDK consumer that cannot read it is back in the F-CERT-005 world. Null-safe on old records.
"""
import os
import sys

_SDK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SDK not in sys.path:
    sys.path.insert(0, _SDK)

from vapi_sdk import VAPIPresenceProof


def test_default_none():
    assert VAPIPresenceProof(device_id="d", record_hash="r", verdict="X").active_oracles is None


def test_carries_manifest_and_roundtrips():
    m = {"retina": "contributed", "cco": "absent", "poep": "abstained_or_absent", "l4l5l6": "contributed"}
    p = VAPIPresenceProof(device_id="d", record_hash="r", verdict="X", active_oracles=m)
    assert p.active_oracles == m
    d = p.to_dict()
    assert d["active_oracles"] == m                       # to_dict carries it
    assert d.get("active_oracles") == m                   # parser (body.get) round-trips


def test_backward_compat_absent_is_none():
    full = VAPIPresenceProof(device_id="d", record_hash="r", verdict="X",
                             active_oracles={"retina": "contributed"}).to_dict()
    old = {k: v for k, v in full.items() if k != "active_oracles"}
    assert old.get("active_oracles") is None              # pre-cycle-59 record -> None


def test_comparability_same_verdict_different_evidence_is_distinguishable():
    # the F-CERT-005 point closed at the SDK layer: same verdict, different evidence set -> the
    # manifest makes them distinguishable (retina contributed vs abstained is different evidence).
    a = VAPIPresenceProof(device_id="d", record_hash="r", verdict="CONSISTENT_HUMAN",
                          active_oracles={"retina": "contributed", "poep": "contributed"})
    b = VAPIPresenceProof(device_id="d", record_hash="r", verdict="CONSISTENT_HUMAN",
                          active_oracles={"retina": "abstained", "poep": "contributed"})
    assert a.verdict == b.verdict and a.active_oracles != b.active_oracles
