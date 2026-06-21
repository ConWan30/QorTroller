"""QorTroller L9 — HUD OCR pass for the recorder (pure, pytesseract-guarded).

Captures raw on-screen HUD text from frames the recorder already grabs, so a recorded
session carries `hud_texts = [(t_ms, text), ...]`. The bridge oracle panel parses that text
(retina_screen_lobe.parse_hud / diff_hud) into outcome events — this module only OCRs; it
does NOT parse or classify, keeping l9_presence standalone (no bridge import).

Degrades gracefully: if pytesseract (or the Tesseract binary) is absent, ocr_frame returns
None and the recorder simply stores no HUD text — the discrete-coherence channel then reads
INSUFFICIENT and the continuous coupling channel carries the verdict, exactly as before.
"""
from __future__ import annotations

import json
import os
from typing import Optional

try:
    import pytesseract  # type: ignore
    _TESS = True
except Exception:  # pragma: no cover - env without pytesseract
    _TESS = False


def _locate_tesseract() -> Optional[str]:
    """Find tesseract.exe when it isn't on PATH (the UB-Mannheim Windows installer doesn't add
    it). Returns the path to set on pytesseract, or None if PATH already resolves it."""
    import shutil
    if shutil.which("tesseract"):
        return None
    for c in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
    ):
        if os.path.exists(c):
            return c
    return None


if _TESS:  # point pytesseract at the binary so fresh processes work without a PATH edit
    try:
        _cmd = _locate_tesseract()
        if _cmd:
            pytesseract.pytesseract.tesseract_cmd = _cmd
    except Exception:  # pragma: no cover
        pass


def ocr_available() -> bool:
    """True only if pytesseract is importable AND the Tesseract engine binary resolves."""
    if not _TESS:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_frame(frame_bgr, region: Optional[tuple[int, int, int, int]] = None) -> Optional[str]:
    """OCR a HUD region (x, y, w, h) of a BGR frame. None if pytesseract/Tesseract is absent,
    the frame is None, or OCR raises (never breaks a live capture)."""
    if not _TESS or frame_bgr is None:
        return None
    try:
        img = frame_bgr
        if region:
            x, y, w, h = region
            img = frame_bgr[y:y + h, x:x + w]
        text = pytesseract.image_to_string(img)
        return text.strip() or None
    except Exception:
        return None


def dumps_hud_texts(hud_texts: list[tuple[float, str]]) -> str:
    """Serialize [(t_ms, text), ...] for the .npz sidecar."""
    return json.dumps([[float(t), str(s)] for t, s in hud_texts])


def loads_hud_texts(blob: Optional[str]) -> list[tuple[float, str]]:
    """Parse the .npz hud_json blob back to [(t_ms, text), ...] (empty on any error)."""
    if not blob:
        return []
    try:
        return [(float(t), str(s)) for t, s in json.loads(blob)]
    except Exception:
        return []
