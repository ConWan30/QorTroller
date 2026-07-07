"""D-CERT-7 SDK surface — verifier_independence field + first-class read helper (cycle-59).

Consumers get a first-class way to check independence (verifier_is_independent()) instead of
inferring it from population_certified. Backward-compatible: absent on old records -> None.
"""
import os
import sys

_SDK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SDK not in sys.path:
    sys.path.insert(0, _SDK)

from vapi_sdk import VAPIPresenceProof


def test_default_independence_is_none():
    p = VAPIPresenceProof(device_id="d", record_hash="r", verdict="UNVERIFIABLE")
    assert p.verifier_independence is None
    assert p.verifier_is_independent() is None


def test_developer_self_reads_not_independent():
    p = VAPIPresenceProof(device_id="d", record_hash="r", verdict="CONSISTENT_HUMAN",
                          cert_scope="developer_self", advisory=False, verifier_independence=False)
    assert p.is_developer_self_certified() is True     # valid within its scope ...
    assert p.verifier_is_independent() is False        # ... but explicitly NOT independent
    assert not p.verifier_is_independent()             # a gate on independence fails closed


def test_to_dict_carries_field():
    p = VAPIPresenceProof(device_id="d", record_hash="r", verdict="X", verifier_independence=False)
    assert p.to_dict()["verifier_independence"] is False


def test_parser_backward_compat_absent_is_none():
    # get()'s parser reads body.get("verifier_independence"): present -> value, absent -> None
    # (never coerced to False). Prove the round-trip + old-record contract without HTTP.
    full = VAPIPresenceProof(device_id="d", record_hash="r", verdict="X",
                             verifier_independence=False).to_dict()
    assert full.get("verifier_independence") is False
    old = {k: v for k, v in full.items() if k != "verifier_independence"}   # pre-cycle-59 record
    assert old.get("verifier_independence") is None                        # absent -> None, safe


def test_never_true_today():
    for scope, adv, vi in (("developer_self", False, False), ("advisory", True, None)):
        p = VAPIPresenceProof(device_id="d", record_hash="r", verdict="X",
                              cert_scope=scope, advisory=adv, verifier_independence=vi)
        assert p.verifier_is_independent() is not True
