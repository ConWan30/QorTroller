"""D-CERT-8 SDK self-description — the evidence base travels with the SDK proof (cycle-59).

The API emits governing_model / calibration_band_commitment / calibration_n /
calibration_player_scope; the SDK proof now parses + carries them, so an external auditor reading
via the SDK does NOT need filesystem/poep_l9 access (closes F-CERT-008 one layer up, for exactly
the audience the fix was aimed at). Commitment only — calibration_band_commitment is a hash,
never raw band values.
"""
import os
import sys

_SDK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SDK not in sys.path:
    sys.path.insert(0, _SDK)

from vapi_sdk import VAPIPresenceProof

_EB_KEYS = ("governing_model", "calibration_band_commitment", "calibration_n", "calibration_player_scope")


def test_evidence_base_defaults_none():
    p = VAPIPresenceProof(device_id="d", record_hash="r", verdict="X")
    assert p.evidence_base() == {k: None for k in _EB_KEYS}          # advisory / old record -> all None


def test_evidence_base_carries_values():
    p = VAPIPresenceProof(
        device_id="d", record_hash="r", verdict="X",
        governing_model="developer_self:single_subject_reflex_v1:min_n=30",
        calibration_band_commitment="ab" * 32, calibration_n=52, calibration_player_scope="DEV",
    )
    eb = p.evidence_base()
    assert eb["governing_model"].endswith("min_n=30")
    assert eb["calibration_band_commitment"] == "ab" * 32 and len(eb["calibration_band_commitment"]) == 64
    assert eb["calibration_n"] == 52 and eb["calibration_player_scope"] == "DEV"


def test_to_dict_and_parser_roundtrip():
    p = VAPIPresenceProof(
        device_id="d", record_hash="r", verdict="X",
        governing_model="m", calibration_band_commitment="cd" * 32, calibration_n=52,
        calibration_player_scope="DEV",
    )
    d = p.to_dict()
    for k in _EB_KEYS:
        assert k in d                                               # to_dict emits every evidence field
    # the get() parser reads body.get(k) for each -> a present body round-trips onto the proof
    assert all(d.get(k) == getattr(p, k) for k in _EB_KEYS)


def test_backward_compat_absent_evidence_base_is_none():
    full = VAPIPresenceProof(device_id="d", record_hash="r", verdict="X",
                             governing_model="m", calibration_n=52).to_dict()
    old = {k: v for k, v in full.items() if k not in _EB_KEYS}       # pre-cycle-58 record shape
    for k in _EB_KEYS:
        assert old.get(k) is None                                   # absent -> None, never errors


def test_commitment_only_no_raw_band_field():
    # the SDK carries the COMMITMENT; there is no raw-band field on the proof to leak.
    fields = set(VAPIPresenceProof.__dataclass_fields__)
    assert "calibration_band_commitment" in fields
    for raw in ("latency_mean_ms", "latency_std_ms", "salt", "calibration_band", "band_lo_ms"):
        assert raw not in fields
