"""QorTroller L9 — tight-row killfeed OCR bootstrap engine (SHARED ENGINE, dual-consumer).

Consumers: live session-anchor bootstrap (_session_anchor_fold) and the audit lane
(scripts/killfeed_audit_lane.py). Behavior changes require BOTH consumers' tests green — one implementation,
so live bootstrap and the offline audit cannot drift apart.

WHY: the static feed_v1 template bootstrap is marginal per-rendering (kill-highlight color is per-match/team;
live max 0.566 vs the 0.55 catch-floor -> the producer failed live 0/23). Tight single-row OCR reads the
INVARIANT handle glyphs regardless of color (validated 12-13/25 live), so it is the rendering-INDEPENDENT
bootstrap. Full-panel OCR is mojibake; the tight-row + upscale + Otsu + psm-7 pipeline is what makes it read.

LOCATE vs READ (independence decision, D-FUSE-loc): a clean OCR read needs a TIGHT crop CENTRED on the handle,
which needs the handle's (x,y). Two locators were tried: (a) template-free horizontal-edge-density banding —
scene-robust but the resulting FIXED-region crop misframes the glyphs (reads "Qortaa30" not "Qortrola30", so
strict canon fails); (b) a LOOSE feed_v1 template match (score >= 0.40) to centre the crop -> the proven read.
We take (b). Independence from Instrument B (template_ensemble_v1) is therefore at the VERDICT MECHANISM, not
location: A returns OWN_KILL by READING the literal handle glyphs; B by SCORING template correlation >= 0.66.
A resolves rows in the 0.40-0.66 band that B's verdict floor rejects — that disagreement is the independence
payoff. The prior correlated blind spot (feed_v1 < 0.40: A could not locate) is CLOSED by D-FUSE-loc-v2
(2026-07-05): when the template scores below locate_threshold, _strip_scan_killer_column scans the killer
column in 32px horizontal strips, reading glyphs directly on each — template-free, rendering-agnostic.
(Row-differencing gives a fresh/not-fresh boolean, not an (x,y) for the tight crop — hence the strip-scan.)

PURE: no bridge/session state; cv2 + pytesseract imported inside functions; FAIL-OPEN — unreadable/
below-confidence/failing-canon -> ABSTAIN (matched=False), NEVER a guessed handle (a hallucinated handle is
worse than a missed bootstrap).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from l9_presence.killfeed_authorship import canon, default_handle

# --- shared taxonomy vocabulary (both audit-lane instruments map their raw output to this) ---------
OWN_KILL = "OWN_KILL"          # own handle in the KILLER slot -> authored kill (a bootstrap source)
OWN_DEATH = "OWN_DEATH"        # own handle in the VICTIM slot -> your death (neutral, NOT a bootstrap source)
OTHER_ROW = "OTHER_ROW"        # a feed row present but not crediting/killing your handle
NO_ROW = "NO_ROW"             # no feed row detected in this crop
UNRESOLVED = "UNRESOLVED"      # below-confidence / sub-floor — honest abstain, never a forced verdict

DEFAULT_UPSCALE = 4
DEFAULT_KILLER_MAX_FRAC = 0.28
DEFAULT_FEED_REGION_MAX_YFRAC = 0.42

# C2 match kinds (the A3-closure the bake-off proved off-the-shelf recall could not deliver alone):
MATCH_EXACT = "exact"    # handle canon EQUALS a whitespace token of the read -> clean own-kill
MATCH_FUZZY = "fuzzy"    # handle canon is a SUBSTRING of a longer token (weapon-icon bleed OR an extension-
                         # name like QorTro1a300) -> accepted for RECALL but FLAGGED so the certificate path
                         # treats it cautiously. exact vs fuzzy is the honest signal, carried on every record.


def match_kind(handle_canon: str, raw_text: str) -> Optional[str]:
    """C2: classify a canon match as EXACT (handle == some whitespace token) vs FUZZY (substring of a longer
    token) vs None. Exact-token distinguishes a real `Qortrola30 [icon] victim` (handle is its own token ->
    exact) from a hostile extension-name `QorTro1a300` (one longer token, handle a strict prefix -> fuzzy) and
    from a fused weapon-artifact read `Qortrola30Tca` (one token -> fuzzy: a real kill, but flagged, not
    silently trusted). Parity note: the shipped/bake-off match was bare `handle in canon(text)` (= fuzzy for
    all three) with NO exact/reject distinction; this adds it."""
    if not handle_canon:
        return None
    for tok in (raw_text or "").split():
        if canon(tok) == handle_canon:
            return MATCH_EXACT
    return MATCH_FUZZY if handle_canon in canon(raw_text or "") else None


@dataclass
class OcrRead:
    """Result of the tight-row OCR over a panel crop. matched=True only when a canon()-matching handle word
    cleared the confidence floor; x_frac/y_frac/slot locate it (killer<killer_max_frac => own kill).
    C3 provenance: text is the RAW pre-canon read; match_kind is exact|fuzzy; engine is the recognizer id."""
    matched: bool
    text: str                  # RAW pre-canon read (the matched word's text, or best band text on no match)
    conf: float                # recognizer confidence of the matched word (0 if none)
    x_frac: Optional[float]    # matched handle-word centre x-fraction of panel width
    y_frac: Optional[float]
    slot: Optional[str]        # "killer" | "victim" | None
    match_kind: Optional[str] = None   # C2/C3: exact | fuzzy | None (the A3-assurance signal)
    engine: Optional[str] = None       # C3: recognizer id (paddle_svtr_v1 | tesseract_row_v1 | ...)

    def taxonomy(self, killer_max_frac: float = DEFAULT_KILLER_MAX_FRAC) -> str:
        """Map this OCR read to the shared taxonomy (ocr_row_v1 labeler)."""
        if not self.matched:
            return UNRESOLVED
        return OWN_KILL if (self.x_frac is not None and self.x_frac < killer_max_frac) else OWN_DEATH


def ocr_ready() -> bool:
    """True if the tesseract engine is available (hud_ocr's import sets pytesseract.tesseract_cmd)."""
    try:
        from l9_presence import hud_ocr
        return hud_ocr.ocr_available()
    except Exception:
        return False


def _abstain(text: str = "") -> OcrRead:
    return OcrRead(matched=False, text=text, conf=0.0, x_frac=None, y_frac=None, slot=None)


def _strip_scan_killer_column(panel_bgr, handle_canon: str,
                               killer_max_frac: float = DEFAULT_KILLER_MAX_FRAC,
                               feed_region_max_yfrac: float = DEFAULT_FEED_REGION_MAX_YFRAC,
                               upscale: int = DEFAULT_UPSCALE,
                               strip_h: int = 32, stride: int = 16) -> Optional[OcrRead]:
    """Rendering-agnostic locate fallback (D-FUSE-loc-v2, 2026-07-05): scan the killer column in
    horizontal strips when killer_slot_best scores below locate_threshold.

    Template-free — reads handle glyphs directly on each strip so it works on any map/rendering
    family regardless of kill-highlight colour. Kill rows are ~32px tall; stride=16 (50% overlap)
    ensures a row spanning a strip boundary is fully captured in at least one strip.

    x_frac returned is the approximate centre of the scanned column (not OCR-position-derived).
    The session-anchor cut quality gate (cut_killer_name_anchor column-clustering) handles small
    offsets; a rejected cut leaves the generator in BOOTSTRAP and waits for the next kill row.

    Returns an OcrRead(matched=True) on the first canon-matching strip, None if no match found."""
    import cv2
    h, w = panel_bgr.shape[:2]
    feed_h = int(h * feed_region_max_yfrac)
    # Cap x-range at 300px — killer name appears in the leftmost portion of the killer column
    kw = min(int(w * killer_max_frac), 300)
    if kw <= 0 or feed_h <= strip_h:
        return None
    for sy in range(0, feed_h - strip_h, stride):
        strip = panel_bgr[sy:sy + strip_h, 0:kw]
        if strip.size == 0:
            continue
        up = cv2.resize(strip, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
        for engine_id in engine_chain():
            for txt, conf in _engine_reads(engine_id, up):
                mk = match_kind(handle_canon, txt)
                if mk is not None:
                    cxf = (kw / 2) / w            # approximate centre of scanned column
                    cyf = (sy + strip_h / 2) / h  # strip midpoint in panel coordinates
                    return OcrRead(matched=True, text=txt, conf=conf, x_frac=cxf, y_frac=cyf,
                                   slot="killer", match_kind=mk, engine=engine_id)
    return None


# --- engine chain (A1 wiring, D-PKG-1 = PP-OCRv6_rec_small via rapidocr/onnxruntime) -----------------
# DEFAULT FLIPPED 2026-07-04 (D-PKG-1 parity recheck PASSED, operator-adopted): v6 PRIMARY with tesseract
# FALLBACK is now the default chain. Evidence (docs/dpkg1-v6-parity-2026-07-04.md): full 1,800-crop archive
# both-engine comparison — v6 recall >= tesseract in ALL sessions (seg3 13v5 +160% on the rendering
# tesseract was 99.2% blind to; sess_ab 141v134; sess_hid 110v100); zero false reads (2 candidates both
# visually adjudicated TRUE with preserved evidence); per-record engine attribution 100% v6 on all 264 kill
# reads (no fallback contamination). RETINA_OCR_ENGINE=tesseract forces the legacy tesseract-only chain
# (the pre-flip escape hatch). v6 (onnxruntime) is contamination-safe with the tesseract fallback
# in-process (verified) — no paddlepaddle, no subprocess. B8 posture unchanged: v6 CAN read recaptured
# splice content tesseract was blind to — the accepted mitigations (fresh-row diff + cut-quality gate +
# K=3 promotion + R2 gating) remain the wall, re-verified per the splice-lane run.
ENGINE_V6 = "rapidocr_ppocrv6_small"       # sha 6f327246b50388f3 (PP-OCRv6_rec_small.onnx)
ENGINE_TESS = "tesseract_row_v1"
_UNSET = object()
_V6 = _UNSET


def _v6_engine():
    """Lazy-load the rapidocr PP-OCRv6_rec_small recognizer (onnxruntime). None if rapidocr/onnxruntime absent
    -> the chain silently falls to tesseract (no hard dependency on the ONNX stack)."""
    global _V6
    if _V6 is _UNSET:
        try:
            from rapidocr import RapidOCR
            _V6 = RapidOCR()
        except Exception:  # noqa: BLE001
            _V6 = None
    return _V6


def engine_chain():
    """The ordered recognizer chain per RETINA_OCR_ENGINE. DEFAULT (unset) = v6 primary -> tesseract
    fallback (D-PKG-1 parity-adopted 2026-07-04); "tesseract" forces the legacy tesseract-only chain."""
    pref = os.environ.get("RETINA_OCR_ENGINE", "rapidocr_v6").strip().lower()
    if pref in ("tesseract", ENGINE_TESS):
        return (ENGINE_TESS,)              # legacy escape hatch — the pre-flip live path
    return (ENGINE_V6, ENGINE_TESS)        # v6 primary -> tesseract fallback (human_oracle is caller-side)


def _engine_reads(engine_id, up):
    """Yield (raw_text, conf) candidate reads from one engine over the upscaled crop."""
    import cv2
    if engine_id == ENGINE_V6:
        eng = _v6_engine()
        if eng is None:
            return
        try:
            res = eng(up, use_det=False, use_cls=False, use_rec=True)
            txts, scores = getattr(res, "txts", None), getattr(res, "scores", None)
            if txts:
                yield str(txts[0]), (float(scores[0]) * 100.0 if scores else 0.0)
        except Exception:  # noqa: BLE001
            return
    else:  # tesseract_row_v1 — Otsu + psm7, both polarities (the shipped recipe)
        import pytesseract
        g = cv2.threshold(cv2.cvtColor(up, cv2.COLOR_BGR2GRAY), 0, 255,
                          cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        for im in (g, 255 - g):
            try:
                yield pytesseract.image_to_string(im, config="--psm 7").strip(), 100.0
            except Exception:  # noqa: BLE001
                continue


DEFAULT_LOCATE_THRESHOLD = 0.40   # loose template score just to LOCATE a candidate row (well below B's 0.66
                                  # verdict floor) — so A reads (rendering-independent) exactly the rows whose
                                  # off-rendering score B's strict threshold misses. This is A's independence
                                  # from B: shared loose location, INDEPENDENT verdict mechanism (OCR read vs
                                  # template score). Score < 0.40 falls through to _strip_scan_killer_column
                                  # (D-FUSE-loc-v2) — rendering-agnostic; the prior correlated blind spot CLOSED.


def tight_row_ocr(panel_bgr, *, handle: Optional[str] = None, anchor=None, prev_gray=None,
                  locate_threshold: float = DEFAULT_LOCATE_THRESHOLD,
                  killer_max_frac: float = DEFAULT_KILLER_MAX_FRAC,
                  feed_region_max_yfrac: float = DEFAULT_FEED_REGION_MAX_YFRAC,
                  upscale: int = DEFAULT_UPSCALE) -> OcrRead:
    """THE shared bootstrap read (live bootstrap + audit-lane Instrument A). Locate the candidate killer-slot
    row via a LOOSE template match (score >= locate_threshold, below B's verdict floor), then read a TIGHT
    handle-CENTRED crop with the proven recipe (upscale + Otsu + image_to_string, both polarities) and STRICT
    full-canon match. matched=True only on a full 10-glyph read (the zero-false-read control). FAIL-OPEN:
    engine absent / no located row / no read -> abstain (matched=False)."""
    if panel_bgr is None or not ocr_ready():
        return _abstain()
    handle_canon = canon(handle) if handle is not None else canon(default_handle())
    try:
        import cv2
        from l9_presence.killfeed_cv import killer_slot_best, load_anchor
        if anchor is None:
            anchor = load_anchor("l9_presence/assets/own_handle_anchor_feed.png")
        h, w = panel_bgr.shape[:2]
        score, cxf, cyf = killer_slot_best(panel_bgr, anchor, killer_max_frac=killer_max_frac,
                                           feed_region_max_yfrac=feed_region_max_yfrac)
        if cxf is None or cyf is None or score < locate_threshold:
            # D-FUSE-loc-v2 (2026-07-05): strip-scan fallback — rendering-agnostic locate when the
            # template anchor scores below threshold (non-FK maps, different kill-highlight colour).
            # "It shouldn't matter which map whatsoever" — operator mandate 2026-07-05.
            fb = _strip_scan_killer_column(panel_bgr, handle_canon, killer_max_frac,
                                           feed_region_max_yfrac, upscale)
            return fb if fb is not None else _abstain()
        px, py = int(cxf * w), int(cyf * h)
        crop = panel_bgr[max(0, py - 16):min(h, py + 16), max(0, px - 95):min(w, px + 120)]  # handle-centred
        if crop.size == 0:
            return _abstain()
        up = cv2.resize(crop, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
        # engine chain (v6 primary -> tesseract fallback per RETINA_OCR_ENGINE); first canon-matching read wins,
        # stamped with its engine id + C2 match_kind (C3 provenance).
        for engine_id in engine_chain():
            for txt, conf in _engine_reads(engine_id, up):
                mk = match_kind(handle_canon, txt)   # C2: exact (own token) | fuzzy (substring) | None
                if mk is not None:                   # matched set = exact ∪ fuzzy = the old substring set
                    slot = "killer" if cxf < killer_max_frac else "victim"
                    return OcrRead(matched=True, text=txt, conf=conf, x_frac=cxf, y_frac=cyf, slot=slot,
                                   match_kind=mk, engine=engine_id)
        return _abstain()
    except Exception:
        return _abstain()
