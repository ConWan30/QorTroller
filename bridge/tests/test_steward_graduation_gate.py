"""Ceremony A — steward graduation gate tests. Pins grok round-20's footguns:
  F1 wrong-key / mandatory pin (verify against the PINNED Guardian key only, never the embedded pubkey);
  F2 ordering (later REJECT revokes; re-ACCEPT re-graduates);
  F3 threshold-incoherent ACCEPT does not graduate;
  F5 cross-steward / cross-task bleed.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from eth_keys import keys

from bridge.vapi_bridge.steward_sel_attestation import attest_graduation
from bridge.vapi_bridge.steward_sel_cosign import add_operator_cosignature
from bridge.vapi_bridge.steward_graduation_gate import (
    is_task_class_graduated,
    operator_dual_key_cryptographically_demonstrated,
)

_HEAD = "ab" * 32


class _Guardian:
    def __init__(self):
        self._priv = ec.generate_private_key(ec.SECP256K1())

    def sign_digest(self, d):
        return self._priv.sign(d, ec.ECDSA(Prehashed(SHA256())))

    def pubkey_hex(self):
        return self._priv.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo).hex()

    def verify_sig(self, d, der):
        try:
            self._priv.public_key().verify(der, d, ec.ECDSA(Prehashed(SHA256())))
            return True
        except Exception:
            return False


_OP = keys.PrivateKey(bytes.fromhex("55" * 32))
_OP_ADDR = _OP.public_key.to_checksum_address()


def _dual(*, steward="guardian", task_class="PCRA", decision="ACCEPT", ts_ns=1000,
          precision=0.95, n_labels=20, min_samples=20, precision_floor=0.90, guardian=None, op=None):
    g = guardian or _GUARDIAN
    o = op or _OP
    addr = o.public_key.to_checksum_address()
    rec = attest_graduation(steward=steward, task_class=task_class, precision=precision, n_labels=n_labels,
                            min_samples=min_samples, precision_floor=precision_floor, decision=decision,
                            operator_id=addr, ts_ns=ts_ns, sel_chain_head_hex=_HEAD,
                            sign_digest=g.sign_digest, pubkey_hex=g.pubkey_hex(), verify_sig=g.verify_sig)
    return add_operator_cosignature(rec, operator_sign=lambda d: o.sign_msg_hash(d).to_bytes())


_GUARDIAN = _Guardian()
_PIN = _GUARDIAN.pubkey_hex()


# --- happy + ordering (F2) --------------------------------------------------------------------------

def test_single_accept_graduates():
    r = is_task_class_graduated([_dual(decision="ACCEPT")], steward="guardian", task_class="PCRA",
                                guardian_pubkey_hex=_PIN)
    assert r["graduated"] is True and r["reason"] == "graduated" and r["authorizing_digest_hex"]


def test_later_reject_revokes():
    recs = [_dual(decision="ACCEPT", ts_ns=1000), _dual(decision="REJECT", ts_ns=2000)]
    r = is_task_class_graduated(recs, steward="guardian", task_class="PCRA", guardian_pubkey_hex=_PIN)
    assert r["graduated"] is False and r["reason"] == "revoked" and r["revoked_by"]


def test_reaccept_after_reject_regraduates():
    recs = [_dual(decision="ACCEPT", ts_ns=1000), _dual(decision="REJECT", ts_ns=2000),
            _dual(decision="ACCEPT", ts_ns=3000)]
    r = is_task_class_graduated(recs, steward="guardian", task_class="PCRA", guardian_pubkey_hex=_PIN)
    assert r["graduated"] is True and r["reason"] == "graduated"


def test_no_records_fails_closed():
    r = is_task_class_graduated([], steward="guardian", task_class="PCRA", guardian_pubkey_hex=_PIN)
    assert r["graduated"] is False and r["reason"] == "no_valid_record"


# --- F1: pin / wrong Guardian key -------------------------------------------------------------------

def test_wrong_guardian_key_not_graduated():
    # record signed by an ATTACKER Guardian key; gate pinned to the REAL Guardian key -> excluded
    attacker = _Guardian()
    bad = _dual(decision="ACCEPT", guardian=attacker)   # embeds attacker pubkey in the record
    r = is_task_class_graduated([bad], steward="guardian", task_class="PCRA", guardian_pubkey_hex=_PIN)
    assert r["graduated"] is False and r["reason"] == "no_valid_record"
    # and the attacker's own key as the pin WOULD verify — proving the pin is what matters
    r2 = is_task_class_graduated([bad], steward="guardian", task_class="PCRA",
                                 guardian_pubkey_hex=attacker.pubkey_hex())
    assert r2["graduated"] is True


def test_pin_is_mandatory():
    for bad_pin in (None, "", "   "):
        try:
            is_task_class_graduated([_dual()], steward="guardian", task_class="PCRA",
                                    guardian_pubkey_hex=bad_pin)
            assert False, "expected missing pin to raise"
        except ValueError as exc:
            assert "MANDATORY" in str(exc)


# --- F3: threshold-incoherent ACCEPT ----------------------------------------------------------------

def test_incoherent_accept_does_not_graduate():
    # a fully-authorized ACCEPT whose package fails its own thresholds (n < min_samples) is not graduation
    bad = _dual(decision="ACCEPT", n_labels=3, min_samples=20)
    r = is_task_class_graduated([bad], steward="guardian", task_class="PCRA", guardian_pubkey_hex=_PIN)
    assert r["graduated"] is False and r["reason"] == "threshold_incoherent"


def test_below_precision_floor_accept_does_not_graduate():
    bad = _dual(decision="ACCEPT", precision=0.50, precision_floor=0.90)
    r = is_task_class_graduated([bad], steward="guardian", task_class="PCRA", guardian_pubkey_hex=_PIN)
    assert r["graduated"] is False and r["reason"] == "threshold_incoherent"


# --- F5: cross-steward / cross-task bleed -----------------------------------------------------------

def test_cross_task_does_not_bleed():
    recs = [_dual(steward="guardian", task_class="PCRA", decision="ACCEPT")]
    r = is_task_class_graduated(recs, steward="sentry", task_class="MPJA", guardian_pubkey_hex=_PIN)
    assert r["graduated"] is False and r["reason"] == "no_valid_record"


def test_same_steward_different_task_does_not_bleed():
    # grok round-21 residual #3: a graduation of guardian/PCRA must not graduate guardian/OTHERTASK
    recs = [_dual(steward="guardian", task_class="PCRA", decision="ACCEPT")]
    r = is_task_class_graduated(recs, steward="guardian", task_class="OTHERTASK", guardian_pubkey_hex=_PIN)
    assert r["graduated"] is False and r["reason"] == "no_valid_record"


# --- demonstrated() advisory ------------------------------------------------------------------------

def test_operator_dual_key_demonstrated():
    recs = [_dual(decision="ACCEPT")]
    assert operator_dual_key_cryptographically_demonstrated(recs, _OP_ADDR, guardian_pubkey_hex=_PIN) is True
    other = "0x1111111111111111111111111111111111111111"
    assert operator_dual_key_cryptographically_demonstrated(recs, other, guardian_pubkey_hex=_PIN) is False


def test_demonstrated_requires_pin():
    try:
        operator_dual_key_cryptographically_demonstrated([_dual()], _OP_ADDR, guardian_pubkey_hex="")
        assert False, "expected missing pin to raise"
    except ValueError as exc:
        assert "MANDATORY" in str(exc)
