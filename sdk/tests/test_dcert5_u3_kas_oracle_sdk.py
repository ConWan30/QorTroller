"""D-CERT-5 Increment U3 SDK — KAS declared-oracle fields travel with VAPIPresenceProof.

Mirrors sdk/tests/test_dcert1_active_oracles_sdk.py's shape. Additive/null-safe: None mid-session
(KAS issues post-hoc at daemon stop) or on pre-U3 records — same discipline as D-CERT-1/7/8.
"""
import os
import sys

_SDK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SDK not in sys.path:
    sys.path.insert(0, _SDK)

from vapi_sdk import VAPIPresenceProof


def test_default_none():
    p = VAPIPresenceProof(device_id="d", record_hash="r", verdict="X")
    assert p.kas_verdict is None and p.kas_commitment is None
    assert p.kas_events_root is None and p.kas_authored_kills is None


def test_carries_kas_fields_and_roundtrips():
    p = VAPIPresenceProof(device_id="d", record_hash="r", verdict="X",
                          active_oracles={"kas": "contributed"},
                          kas_verdict="AUTHORED_SESSION", kas_commitment="deadbeef" * 8,
                          kas_events_root="ab" * 32, kas_authored_kills=15)
    d = p.to_dict()
    assert d["kas_verdict"] == "AUTHORED_SESSION"
    assert d["kas_commitment"] == "deadbeef" * 8
    assert d["kas_events_root"] == "ab" * 32
    assert d["kas_authored_kills"] == 15
    assert d["active_oracles"] == {"kas": "contributed"}


def test_backward_compat_absent_is_none():
    full = VAPIPresenceProof(device_id="d", record_hash="r", verdict="X",
                             kas_verdict="AUTHORED_SESSION").to_dict()
    old = {k: v for k, v in full.items() if not k.startswith("kas_")}
    assert old.get("kas_verdict") is None            # pre-U3 record -> None, never inferred
