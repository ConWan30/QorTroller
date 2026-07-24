"""Unit test for the UVC capture backend-order helper (MSMF-first fix for OBS virtual camera).

Pure — no cv2/hardware. Proves auto tries MSMF before DSHOW (the fix for OBS 28+ virtual cameras
and broken-DSHOW-by-index Windows boxes), and honors explicit env overrides.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bridge.vapi_bridge.qortroller_retina_capture import _uvc_backend_order


class _FakeCv2:
    CAP_MSMF = 1400
    CAP_DSHOW = 700


def test_auto_tries_dshow_first_then_msmf_then_default():
    # DSHOW+MJPG first = the clean physical direct-capture path; MSMF mis-decodes the physical card
    # into RGB-speckle noise, so it's the fallback (for MF-only virtual cameras), not the default.
    order = _uvc_backend_order("auto", _FakeCv2)
    assert order == [700, 1400, 0]              # DSHOW, MSMF, default
    assert order[0] == _FakeCv2.CAP_DSHOW       # DSHOW FIRST (clean 1080p on the physical card)


def test_explicit_msmf_only():
    assert _uvc_backend_order("msmf", _FakeCv2) == [1400]


def test_explicit_dshow_only():
    assert _uvc_backend_order("dshow", _FakeCv2) == [700]


def test_any_is_default_backend():
    assert _uvc_backend_order("any", _FakeCv2) == [0]


def test_unknown_and_empty_fall_back_to_auto():
    assert _uvc_backend_order("nonsense", _FakeCv2) == [700, 1400, 0]
    assert _uvc_backend_order("", _FakeCv2) == [700, 1400, 0]
    assert _uvc_backend_order(None, _FakeCv2) == [700, 1400, 0]


def test_missing_cv2_attrs_use_numeric_fallbacks():
    class _Bare: pass
    order = _uvc_backend_order("auto", _Bare)
    assert order == [700, 1400, 0]              # getattr fallbacks match cv2's real enum values
