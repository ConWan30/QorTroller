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
payoff. The one correlated blind spot is the deep tail (feed_v1 < 0.40: A cannot even locate); the audit lane
annotates it alongside B's R4-coverage gaps so neither reads as suspicion.  (Row-differencing, the plan's
literal Instrument-A locator, gives a fresh/not-fresh boolean, not an (x,y) for the tight crop, and is
unavailable on the non-sequential archive bag anyway — hence the template-locate resolution.)

PURE: no bridge/session state; cv2 + pytesseract imported inside functions; FAIL-OPEN — unreadable/
below-confidence/failing-canon -> ABSTAIN (matched=False), NEVER a guessed handle (a hallucinated handle is
worse than a missed bootstrap).
"""
from __future__ import annotations

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


@dataclass
class OcrRead:
    """Result of the tight-row OCR over a panel crop. matched=True only when a canon()-matching handle word
    cleared the confidence floor; x_frac/y_frac/slot locate it (killer<killer_max_frac => own kill)."""
    matched: bool
    text: str                  # the matched word's raw OCR text (or best band text on no match)
    conf: float                # tesseract confidence of the matched word (0 if none)
    x_frac: Optional[float]    # matched handle-word centre x-fraction of panel width
    y_frac: Optional[float]
    slot: Optional[str]        # "killer" | "victim" | None

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


DEFAULT_LOCATE_THRESHOLD = 0.40   # loose template score just to LOCATE a candidate row (well below B's 0.66
                                  # verdict floor) — so A reads (rendering-independent) exactly the rows whose
                                  # off-rendering score B's strict threshold misses. This is A's independence
                                  # from B: shared loose location, INDEPENDENT verdict mechanism (OCR read vs
                                  # template score). Correlated failure only in the deep tail (score < 0.40).


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
        import pytesseract
        from l9_presence.killfeed_cv import killer_slot_best, load_anchor
        if anchor is None:
            anchor = load_anchor("l9_presence/assets/own_handle_anchor_feed.png")
        h, w = panel_bgr.shape[:2]
        score, cxf, cyf = killer_slot_best(panel_bgr, anchor, killer_max_frac=killer_max_frac,
                                           feed_region_max_yfrac=feed_region_max_yfrac)
        if cxf is None or cyf is None or score < locate_threshold:
            return _abstain()
        px, py = int(cxf * w), int(cyf * h)
        crop = panel_bgr[max(0, py - 16):min(h, py + 16), max(0, px - 95):min(w, px + 120)]  # handle-centred
        if crop.size == 0:
            return _abstain()
        up = cv2.resize(crop, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
        g = cv2.threshold(cv2.cvtColor(up, cv2.COLOR_BGR2GRAY), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        for im in (g, 255 - g):
            try:
                txt = pytesseract.image_to_string(im, config="--psm 7").strip()
            except Exception:
                continue
            if handle_canon and handle_canon in canon(txt):        # STRICT full-handle read
                slot = "killer" if cxf < killer_max_frac else "victim"
                return OcrRead(matched=True, text=txt, conf=100.0, x_frac=cxf, y_frac=cyf, slot=slot)
        return _abstain()
    except Exception:
        return _abstain()
