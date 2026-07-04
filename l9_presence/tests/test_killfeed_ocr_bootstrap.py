"""Tests for l9_presence.killfeed_ocr_bootstrap — the shared tight-row OCR bootstrap engine.

Covers the FAIL-OPEN discipline (None input / engine-absent / no-handle noise -> ABSTAIN, never a guessed
OWN_KILL — a hallucinated handle corrupts the corpus worse than a missed bootstrap), the taxonomy mapping
(killer-slot read -> OWN_KILL / victim-slot -> OWN_DEATH / abstain -> UNRESOLVED), and — skip-gated on a real
tesseract + a gitignored ground-truth crop — the proven live read that made the engine the rendering-
independent bootstrap (12-13/25 on this session's kills where the static feed_v1 template scored max 0.566).
"""
from __future__ import annotations

import os

import pytest

from l9_presence import killfeed_ocr_bootstrap as ob

cv2 = pytest.importorskip("cv2")
import numpy as np  # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_KNOWN_CROP = os.path.join(_REPO, "retina_kf_crops", "panel_1783086326328232800.png")


def test_ocr_ready_returns_bool():
    # T-OCR-1: never raises; returns a bool whether or not tesseract is installed.
    assert isinstance(ob.ocr_ready(), bool)


def test_none_input_abstains():
    # T-OCR-2: fail-open on a null panel.
    r = ob.tight_row_ocr(None)
    assert r.matched is False and r.slot is None and r.taxonomy() == ob.UNRESOLVED


def test_engine_absent_abstains(monkeypatch):
    # T-OCR-3: engine unavailable -> abstain even on a real ndarray (no crash, no guess).
    monkeypatch.setattr(ob, "ocr_ready", lambda: False)
    r = ob.tight_row_ocr(np.zeros((100, 100, 3), np.uint8))
    assert r.matched is False and r.taxonomy() == ob.UNRESOLVED


def test_taxonomy_mapping():
    # T-OCR-4: killer-slot x_frac -> OWN_KILL; victim-slot -> OWN_DEATH; unmatched -> UNRESOLVED.
    assert ob.OcrRead(True, "q", 100.0, 0.15, 0.30, "killer").taxonomy() == ob.OWN_KILL
    assert ob.OcrRead(True, "q", 100.0, 0.44, 0.30, "victim").taxonomy() == ob.OWN_DEATH
    assert ob.OcrRead(False, "", 0.0, None, None, None).taxonomy() == ob.UNRESOLVED


def test_abstain_shape():
    # T-OCR-5: the canonical abstain record.
    r = ob._abstain()
    assert (r.matched, r.conf, r.x_frac, r.y_frac, r.slot) == (False, 0.0, None, None, None)


def test_noise_image_no_false_read():
    # T-OCR-6: zero-false-read discipline — random noise has no handle; the strict full-canon match must NOT
    # fire OWN_KILL (fail-open abstain). Runs the REAL engine when tesseract is present.
    if not ob.ocr_ready():
        pytest.skip("tesseract unavailable")
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 255, (200, 200, 3), dtype=np.uint8)
    r = ob.tight_row_ocr(noise)
    assert r.matched is False or r.taxonomy() != ob.OWN_KILL     # never a fabricated own-kill on noise


def test_c2_match_kind_exact_vs_fuzzy_vs_reject():
    # C2 (A3-closure): exact = handle is its OWN whitespace token; fuzzy = substring of a longer token
    # (weapon-artifact bleed OR extension-name); None = no match. The load-bearing case: the hostile
    # extension-name QorTro1a300 is FUZZY (flagged), never EXACT — so a certificate path can reject it, while
    # a real spaced kill row exact-matches.
    h = ob.canon(ob.default_handle())                      # q0rtr01a30
    assert ob.match_kind(h, "Qortrola30") == ob.MATCH_EXACT
    assert ob.match_kind(h, "Qortrola30 mamahefen1234") == ob.MATCH_EXACT   # handle is its own token
    assert ob.match_kind(h, "Qortrola30Tca") == ob.MATCH_FUZZY              # fused weapon-artifact (real, flagged)
    assert ob.match_kind(h, "QorTro1a300") == ob.MATCH_FUZZY                # hostile extension -> NOT exact
    assert ob.match_kind(h, "TeckMirage") is None                          # different name -> no match
    assert ob.match_kind(h, "") is None and ob.match_kind("", "Qortrola30") is None


def test_engine_chain_default_tesseract_v6_when_flagged(monkeypatch):
    # A1: default chain is tesseract-only (byte-identical live path); RETINA_OCR_ENGINE=rapidocr_v6 puts v6
    # FIRST with tesseract as fallback (provenance flip stays behind the flag until the C1 gate passes).
    monkeypatch.delenv("RETINA_OCR_ENGINE", raising=False)
    assert ob.engine_chain() == (ob.ENGINE_TESS,)
    monkeypatch.setenv("RETINA_OCR_ENGINE", "rapidocr_v6")
    assert ob.engine_chain() == (ob.ENGINE_V6, ob.ENGINE_TESS)


def test_c2_matched_set_unchanged_flag_added():
    # matched set = exact ∪ fuzzy = the OLD substring set (no recall regression); only the flag + engine add.
    r = ob.OcrRead(True, "Qortrola30", 100.0, 0.16, 0.30, "killer", ob.MATCH_EXACT, "tesseract_row_v1")
    assert r.taxonomy() == ob.OWN_KILL and r.match_kind == ob.MATCH_EXACT and r.engine == "tesseract_row_v1"
    # positional back-compat: old 6-arg construction still valid (new fields default None)
    r2 = ob.OcrRead(True, "q", 100.0, 0.15, 0.30, "killer")
    assert r2.match_kind is None and r2.engine is None and r2.taxonomy() == ob.OWN_KILL


@pytest.mark.skipif(not os.path.exists(_KNOWN_CROP), reason="ground-truth crop is gitignored/local-only")
def test_known_crop_reads_own_kill():
    # T-OCR-7: the proven live read — the crop where the tight-row recipe reads 'Qortrola30'. Documents the
    # rendering-independent bootstrap that the static feed_v1 template missed (max 0.566 this session).
    if not ob.ocr_ready():
        pytest.skip("tesseract unavailable")
    r = ob.tight_row_ocr(cv2.imread(_KNOWN_CROP))
    assert r.matched is True and r.slot == "killer" and r.taxonomy() == ob.OWN_KILL
