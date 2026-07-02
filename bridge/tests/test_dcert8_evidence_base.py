"""D-CERT-8 — self-describing proof evidence base (cycle-58).

Covers the four pieces of the co-signed decision (d-cert8-emit-evidence-base):
  1. the reflex-band commitment adapter (thin F=1/N=1 reuse of FROZEN BIOMETRIC-SNAPSHOT-v1);
  2. the enrollment-side mint (compute_evidence_base: commitment in the verdict, raw band held apart);
  3. the fusion carry-through (fuse() -> FusedGamerPresenceProof carries the 4 fields, null-safe);
  4. the live-verdict evidence-base reader (fresh/stale gated, commitment only);
plus the NEGATIVE-PRESENCE guard: raw band values (mu, sigma, salt) NEVER reach the proof / API dict.

No FROZEN-v1 / 228B PoAC / chain / rig / gameplay. Pure code + tempfiles.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# repo root (for the scripts/ enrollment importlib load) + bridge/ (house convention: `vapi_bridge`)
for _p in (_ROOT, os.path.join(_ROOT, "bridge")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vapi_bridge.reflex_band_commitment import (
    reflex_band_commitment,
    verify_reflex_band_commitment,
)
from vapi_bridge.novel_presence_fusion import (
    NovelPresenceFusionOrchestrator,
    FusedGamerPresenceProof,
)
from vapi_bridge.poep_activation import read_session_evidence_base

# poep_session_enroll lives in scripts/ — load it by path (it is not an installed module).
_ENROLL_PATH = os.path.join(_ROOT, "scripts", "poep_session_enroll.py")
_spec = importlib.util.spec_from_file_location("poep_session_enroll", _ENROLL_PATH)
poep_session_enroll = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(poep_session_enroll)
compute_evidence_base = poep_session_enroll.compute_evidence_base


# --- 1. adapter: the crypto core ------------------------------------------------------------------

def test_adapter_deterministic_and_hex_shape():
    c1 = reflex_band_commitment(200.4, 30.2, 123456789)
    c2 = reflex_band_commitment(200.4, 30.2, 123456789)
    assert c1 == c2 and len(c1) == 64          # 32-byte digest, hex; mint == mint (bit-identical)
    int(c1, 16)                                # valid hex


def test_adapter_salt_hides_low_entropy_band():
    # Same band, different salt -> different commitment. Without this a low-entropy band would be
    # brute-forceable from the public commitment (the whole reason ts_ns carries a salt).
    assert reflex_band_commitment(200.4, 30.2, 1) != reflex_band_commitment(200.4, 30.2, 2)


def test_adapter_band_drift_changes_commitment():
    # Different mu OR sigma, same salt -> different commitment: each proof pins its authorizing band
    # (closes F-CERT-007). Physiological sigma survives 1e9 fixed-point (no underflow collapse).
    base = reflex_band_commitment(200.0, 30.0, 7)
    assert base != reflex_band_commitment(200.1, 30.0, 7)
    assert base != reflex_band_commitment(200.0, 30.1, 7)
    assert reflex_band_commitment(200.0, 55.0, 7) != reflex_band_commitment(200.0, 55.1, 7)


def test_adapter_audit_roundtrip_and_fail_closed():
    c = reflex_band_commitment(200.4, 30.2, 123456789)
    assert verify_reflex_band_commitment(200.4, 30.2, 123456789, c) is True
    assert verify_reflex_band_commitment(200.4, 30.2, 123456789, c.upper()) is True   # case-insensitive
    assert verify_reflex_band_commitment(201.0, 30.2, 123456789, c) is False          # wrong mu
    assert verify_reflex_band_commitment(200.4, 30.2, 999, c) is False                # wrong salt
    assert verify_reflex_band_commitment(200.0, 0.0, 1, c) is False                   # degenerate -> closed


def test_adapter_guards_raise():
    for sd in (0.0, -5.0):
        with pytest.raises(ValueError):
            reflex_band_commitment(200.0, sd, 1)
    with pytest.raises(ValueError):
        reflex_band_commitment(200.0, 30.0, 2 ** 64)      # salt out of uint64 range


# --- 2. enrollment mint: compute_evidence_base ----------------------------------------------------

def _model(mu=200.4, sd=30.2, n=52, complete=True):
    return {
        "n_reactions": n, "min_n": 30, "calibration_complete": complete,
        "latency_mean_ms": mu, "latency_std_ms": sd,
        "band_lo_ms": round(mu - 2.5 * sd, 1), "band_hi_ms": round(mu + 2.5 * sd, 1),
    }


def test_mint_verdict_fields_carry_commitment_not_raw():
    vf, disc = compute_evidence_base(_model(), "DEV", 30)
    assert vf["governing_model"] == "developer_self:single_subject_reflex_v1:min_n=30"
    assert vf["calibration_n"] == 52
    assert vf["calibration_player_scope"] == "DEV"
    assert isinstance(vf["calibration_band_commitment"], str) and len(vf["calibration_band_commitment"]) == 64
    # verdict_fields is what rides outward: it must NOT contain raw band keys.
    assert "latency_mean_ms" not in vf and "latency_std_ms" not in vf and "salt" not in vf


def test_mint_disclosure_holds_raw_and_recomputes_commitment():
    vf, disc = compute_evidence_base(_model(), "DEV", 30, enrollment_ts_ns=1234567890)
    assert disc is not None
    # the operator-held disclosure holds the raw band + salt ...
    assert disc["latency_mean_ms"] == 200.4 and disc["latency_std_ms"] == 30.2 and "salt" in disc
    # ... and those raw values recompute the exact commitment the verdict carries (mint<->audit).
    assert verify_reflex_band_commitment(
        disc["latency_mean_ms"], disc["latency_std_ms"], disc["salt"],
        vf["calibration_band_commitment"],
    ) is True


def test_disclosure_self_describes_salt_and_timestamp_honestly():
    # Rider 1: the disclosure record names the hiding secret `salt` (NOT ts_ns), keeps the real
    # enrollment timestamp as its own field, and carries a recompute note -> zero docstring archaeology.
    vf, disc = compute_evidence_base(_model(), "DEV", 30, enrollment_ts_ns=1234567890)
    assert "salt" in disc and "ts_ns" not in disc            # slot repurposing is not mislabeled
    assert disc["enrollment_ts_ns"] == 1234567890            # real time kept, distinct from the salt
    assert disc["salt"] != disc["enrollment_ts_ns"]          # they are different values
    assert "verify_reflex_band_commitment" in disc["_commitment_scheme"]


def test_mint_degenerate_band_abstains():
    # std == 0 (degenerate) -> commitment None, no disclosure (null-safe abstain, never a fake hash).
    vf, disc = compute_evidence_base(_model(sd=0.0), "DEV", 30)
    assert vf["calibration_band_commitment"] is None and disc is None
    assert vf["governing_model"] and vf["calibration_n"] == 52    # non-sensitive fields still emitted


def test_mint_salt_is_fresh_per_enrollment():
    # Two enrollments of the same band produce different salts -> different commitments (per-enrollment
    # hiding; also means the same band is not linkable across enrollments by commitment equality).
    c1 = compute_evidence_base(_model(), "DEV", 30)[0]["calibration_band_commitment"]
    c2 = compute_evidence_base(_model(), "DEV", 30)[0]["calibration_band_commitment"]
    assert c1 != c2


# --- 3. fusion carry-through ----------------------------------------------------------------------

def _fuse(**kw):
    return NovelPresenceFusionOrchestrator().fuse(
        device_id="dev123", record_hash="rec456", poep_present=True,
        developer_self_cert=True, **kw,
    )


def test_fuse_carries_evidence_base_onto_proof():
    p = _fuse(
        governing_model="developer_self:single_subject_reflex_v1:min_n=30",
        calibration_band_commitment="ab" * 32, calibration_n=52, calibration_player_scope="DEV",
    )
    assert p.governing_model == "developer_self:single_subject_reflex_v1:min_n=30"
    assert p.calibration_band_commitment == "ab" * 32
    assert p.calibration_n == 52 and p.calibration_player_scope == "DEV"


def test_fuse_defaults_null_safe_when_absent():
    p = _fuse()          # no evidence base passed (advisory / stale-verdict path)
    assert p.governing_model is None and p.calibration_band_commitment is None
    assert p.calibration_n is None and p.calibration_player_scope is None


def test_proof_dataclass_has_no_raw_band_field():
    # slots=True dataclass: assert there is simply no attribute that could hold raw mu/sigma/salt.
    fields = set(FusedGamerPresenceProof.__dataclass_fields__)
    assert {"governing_model", "calibration_band_commitment", "calibration_n",
            "calibration_player_scope"} <= fields
    for forbidden in ("latency_mean_ms", "latency_std_ms", "calibration_band", "band_lo_ms",
                      "band_hi_ms", "salt"):
        assert forbidden not in fields


# --- 4. live-verdict evidence-base reader ---------------------------------------------------------

def _write_verdict(tmp, obj):
    p = os.path.join(tmp, "poep_session_verdict.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return p


def test_reader_returns_evidence_base_from_fresh_verdict():
    import time
    tmp = tempfile.mkdtemp()
    p = _write_verdict(tmp, {
        "verdict": "PRESENT", "ts_ns": time.time_ns(),
        "governing_model": "developer_self:single_subject_reflex_v1:min_n=30",
        "calibration_band_commitment": "cd" * 32, "calibration_n": 52, "calibration_player_scope": "DEV",
    })
    eb = read_session_evidence_base(p)
    assert eb == {
        "governing_model": "developer_self:single_subject_reflex_v1:min_n=30",
        "calibration_band_commitment": "cd" * 32, "calibration_n": 52, "calibration_player_scope": "DEV",
    }


def test_reader_abstains_on_stale_and_missing():
    import time
    tmp = tempfile.mkdtemp()
    stale = _write_verdict(tmp, {"ts_ns": time.time_ns() - 3 * 3600 * 10 ** 9,
                                 "governing_model": "x", "calibration_n": 52})
    assert read_session_evidence_base(stale) == {}                       # stale -> abstain
    assert read_session_evidence_base(os.path.join(tmp, "nope.json")) == {}   # missing -> abstain


def test_reader_never_surfaces_raw_band_keys():
    import time
    tmp = tempfile.mkdtemp()
    # Even if a verdict were mistakenly to carry raw band keys, the reader whitelists 4 keys only.
    p = _write_verdict(tmp, {
        "ts_ns": time.time_ns(), "governing_model": "x", "calibration_n": 1,
        "latency_mean_ms": 200.4, "latency_std_ms": 30.2, "salt": 123,
    })
    eb = read_session_evidence_base(p)
    assert "latency_mean_ms" not in eb and "latency_std_ms" not in eb and "salt" not in eb


# --- 5. NEGATIVE-PRESENCE: raw band never reaches the outward surfaces -----------------------------

def test_raw_band_never_appears_in_proof_or_api_dict():
    # Mint a real commitment for a known raw band, carry it through the proof + the API-shaped dict,
    # and assert the raw (mu, sigma, salt) strings appear NOWHERE outward — commitment only.
    mu, sd, salt = 200.4, 30.2, 424242424242
    commitment = reflex_band_commitment(mu, sd, salt)
    p = _fuse(governing_model="m", calibration_band_commitment=commitment,
              calibration_n=52, calibration_player_scope="DEV")

    # (a) the proof object, serialized wholesale
    from dataclasses import asdict
    proof_blob = json.dumps(asdict(p), default=str)
    # (b) the API response shape (the getattr keys the endpoint emits for the evidence base)
    api_blob = json.dumps({
        "governing_model": getattr(p, "governing_model", None),
        "calibration_band_commitment": getattr(p, "calibration_band_commitment", None),
        "calibration_n": getattr(p, "calibration_n", None),
        "calibration_player_scope": getattr(p, "calibration_player_scope", None),
    })
    for blob in (proof_blob, api_blob):
        assert commitment in blob                        # the commitment DOES travel
        assert "200.4" not in blob                       # raw mu does NOT
        assert "30.2" not in blob                        # raw sigma does NOT
        assert "424242424242" not in blob                # raw salt does NOT
