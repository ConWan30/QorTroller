"""Tests for the HUD OCR pass (pure parts; OCR itself is pytesseract-guarded)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from l9_presence.hud_ocr import (  # noqa: E402
    dumps_hud_texts,
    loads_hud_texts,
    ocr_available,
    ocr_frame,
)


def test_ocr_available_is_bool():
    assert isinstance(ocr_available(), bool)


def test_ocr_frame_none_is_safe():
    assert ocr_frame(None) is None
    assert ocr_frame(None, region=(0, 0, 10, 10)) is None


def test_hud_texts_roundtrip():
    hud = [(2000.0, "1ST & 10"), (3000.0, "2ND & 6")]
    blob = dumps_hud_texts(hud)
    assert loads_hud_texts(blob) == hud


def test_loads_hud_texts_tolerant():
    assert loads_hud_texts(None) == []
    assert loads_hud_texts("") == []
    assert loads_hud_texts("not json") == []


def test_dumps_coerces_types():
    blob = dumps_hud_texts([(1, 7)])  # int t, int text -> coerced
    assert loads_hud_texts(blob) == [(1.0, "7")]
