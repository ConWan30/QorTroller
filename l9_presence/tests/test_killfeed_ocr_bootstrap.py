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


def test_engine_chain_default_v6_only_tesseract_escape_hatch(monkeypatch):
    # D-PKG-1 COMPLETE (2026-07-06): DEFAULT chain is v6-only. Evidence: 2,411-crop parity across all
    # sessions — v6 recall >= tesseract in every session, 100% per-record v6 attribution (tesseract never
    # supplied a read v6 missed). Tesseract fallback removed from default; RETINA_OCR_ENGINE=tesseract is
    # the sole legacy escape hatch for operator override.
    monkeypatch.delenv("RETINA_OCR_ENGINE", raising=False)
    assert ob.engine_chain() == (ob.ENGINE_V6,)
    monkeypatch.setenv("RETINA_OCR_ENGINE", "rapidocr_v6")
    assert ob.engine_chain() == (ob.ENGINE_V6,)
    monkeypatch.setenv("RETINA_OCR_ENGINE", "tesseract")
    assert ob.engine_chain() == (ob.ENGINE_TESS,)


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


def test_strip_scan_fallback_routing_no_match(monkeypatch):
    # T-OCR-8: D-FUSE-loc-v2 routing — when killer_slot_best returns sub-threshold score, tight_row_ocr
    # delegates to _strip_scan_killer_column; when strip-scan returns None, tight_row_ocr returns abstain.
    # Verifies the route exists without needing real OCR.
    panel = np.zeros((200, 400, 3), np.uint8)
    monkeypatch.setattr(ob, "ocr_ready", lambda: True)
    # Make template locate always fail below threshold
    from l9_presence import killfeed_ocr_bootstrap as _ob
    import importlib
    import l9_presence.killfeed_cv as kcv
    monkeypatch.setattr(kcv, "killer_slot_best", lambda *a, **kw: (0.10, None, None))
    # Strip-scan returns None (no handle found on the blank panel)
    monkeypatch.setattr(_ob, "_strip_scan_killer_column", lambda *a, **kw: None)
    r = ob.tight_row_ocr(panel)
    assert r.matched is False and r.taxonomy() == ob.UNRESOLVED


def test_strip_scan_fallback_routing_match_returned(monkeypatch):
    # T-OCR-9: D-FUSE-loc-v2 — when strip-scan finds a match, tight_row_ocr returns that OcrRead unchanged.
    panel = np.zeros((200, 400, 3), np.uint8)
    monkeypatch.setattr(ob, "ocr_ready", lambda: True)
    import l9_presence.killfeed_cv as kcv
    monkeypatch.setattr(kcv, "killer_slot_best", lambda *a, **kw: (0.10, None, None))
    expected = ob.OcrRead(True, "Qortrola30", 95.0, 0.078, 0.15, "killer", ob.MATCH_EXACT, ob.ENGINE_V6)
    import l9_presence.killfeed_ocr_bootstrap as _ob
    monkeypatch.setattr(_ob, "_strip_scan_killer_column", lambda *a, **kw: expected)
    r = ob.tight_row_ocr(panel)
    assert r is expected and r.taxonomy() == ob.OWN_KILL


def test_engine_ids_restricts_strip_scan_to_v6_never_tesseract(monkeypatch):
    # T-OCR-11 (D-BURST-3): with engine_ids=(ENGINE_V6,), the strip-scan must NEVER invoke tesseract —
    # the tesseract-per-strip fallback measured 31.4s on a no-match frame (26 strips x ~1.2s both
    # polarities), which single-flight turned into ~1 classify per 65s live (match 10b). The live
    # bootstrap is v6-only; this pins that the restriction actually reaches _engine_reads.
    calls = []
    def _fake_reads(engine_id, up):
        calls.append(engine_id)
        return iter(())                                     # no reads -> scan continues, returns None
    monkeypatch.setattr(ob, "_engine_reads", _fake_reads)
    panel = np.zeros((300, 600, 3), np.uint8)
    r = ob._strip_scan_killer_column(panel, "q0rtr01a30", engine_ids=(ob.ENGINE_V6,))
    assert r is None
    assert calls and set(calls) == {ob.ENGINE_V6}           # every strip ran v6 ONLY
    # default (engine_ids=None) uses the global engine_chain() — v6-only after D-PKG-1 complete
    calls.clear()
    monkeypatch.delenv("RETINA_OCR_ENGINE", raising=False)
    ob._strip_scan_killer_column(panel, "q0rtr01a30")
    assert set(calls) == {ob.ENGINE_V6}                     # global default is v6-only; tesseract=escape-hatch only


def test_engine_ids_threads_through_tight_row_ocr(monkeypatch):
    # T-OCR-12 (D-BURST-3): tight_row_ocr forwards engine_ids to BOTH its tight-crop chain and the
    # strip-scan fallback (locate-fail path), so the live v6-only bound holds on every branch.
    calls = []
    def _fake_reads(engine_id, up):
        calls.append(engine_id)
        return iter(())
    monkeypatch.setattr(ob, "ocr_ready", lambda: True)
    monkeypatch.setattr(ob, "_engine_reads", _fake_reads)
    import l9_presence.killfeed_cv as kcv
    # locate-FAIL branch -> strip-scan fallback
    monkeypatch.setattr(kcv, "killer_slot_best", lambda *a, **kw: (0.10, None, None))
    ob.tight_row_ocr(np.zeros((300, 600, 3), np.uint8), engine_ids=(ob.ENGINE_V6,))
    assert calls and set(calls) == {ob.ENGINE_V6}
    # locate-PASS branch -> tight-crop chain
    calls.clear()
    monkeypatch.setattr(kcv, "killer_slot_best", lambda *a, **kw: (0.80, 0.15, 0.30))
    ob.tight_row_ocr(np.zeros((300, 600, 3), np.uint8), engine_ids=(ob.ENGINE_V6,))
    assert calls and set(calls) == {ob.ENGINE_V6}


def test_strip_scan_no_false_read_on_noise():
    # T-OCR-10: zero-false-read discipline for the fallback path — random noise must not match the handle.
    # The strip-scan reads 26 strips; none should produce a canon-matching read on random noise.
    if not ob.ocr_ready():
        pytest.skip("tesseract unavailable")
    rng = np.random.default_rng(42)
    noise = rng.integers(0, 255, (300, 600, 3), dtype=np.uint8)
    handle_canon = ob.canon(ob.default_handle())
    r = ob._strip_scan_killer_column(noise, handle_canon)
    # Must abstain (None) — no hallucinated own-kills on noise
    assert r is None or r.taxonomy() != ob.OWN_KILL
