"""QorTroller L9 — Kill-feed RAW-OCR reader (the left-middle-feed bridge to authorship).

Grounded 2026-07-12 on the live capture card. This operator's kill feed renders **left-middle**, not
the Warzone-BR top-right that the legacy `killfeed_ocr_bootstrap.tight_row_ocr` template + top-feed
geometry (`feed_region_max_yfrac≈0.42`) assume — so that path *abstains* here (measured: matched=0/20).
A raw OCR (RapidOCR PP-OCRv6) over the measured left-middle ROI reads the feed cleanly. This module
turns that raw OCR output into kill-feed rows and classifies each with the **token-based** rule proven
live: the killer is the *leftmost token*; author iff `canon(killer)` carries your handle.

Two consumers, both provided:
  * `read_feed_lines` / `read_feed_text` — ordered ``"killer … victim"`` lines that drop into the
    existing `RetinaCaptureCore.feed_killfeed_text` → `KillfeedAuthorshipOracle` path unchanged.
  * `classify_rows` / `own_kill_count` — the **robust token-based** classification (killer = leftmost
    token). This is preferred over feeding raw lines to the oracle's string-offset heuristic
    (`pos/len < killer_max_frac`), which can misread a death with a SHORT killer name (e.g.
    `Efram1 → Qortrola30`, offset 6/16 < 0.5) as a kill. Token-order has no such edge.

Proven live (kill1 burst, 2026-07-12): 2 `Qortrola30` kills authored across 8 frames; 62 teammate-killer
rows (`rosa sparks` / `Deslayer295`) correctly NOT authored; ~98 non-own killer rows across 3 bursts,
**0** false authorships.

PURE: the OCR function is INJECTED (`ocr_fn`; default = RapidOCR, lazily imported). The crop is plain
numpy — no cv2 needed to test. No FROZEN-v1 / 228B PoAC / chain / IOTX. Advisory OBSERVATION-plane only:
it feeds fusion, it never asserts.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from l9_presence.killfeed_authorship import canon, default_handle
from l9_presence.killfeed_ocr_bootstrap import OTHER_ROW, OWN_DEATH, OWN_KILL

# Measured + overlay-verified on the card 2026-07-12 (fx, fy, fw, fh), fractions of the frame.
DEFAULT_KILLFEED_ROI = (0.0, 0.45, 0.26, 0.19)
_ROW_Y_TOL = 18          # px: tokens whose top-y are within this gap belong to the same feed row

# An OCR token is (x_min, y_min, text) in CROP-pixel coordinates.
Token = tuple
OcrFn = Callable[[object], Sequence[Token]]


def crop_roi(frame, roi=DEFAULT_KILLFEED_ROI):
    """Fractional (fx,fy,fw,fh) -> the ROI sub-array of `frame` (H,W,C). Plain numpy slicing, clamped to
    the frame. None if the crop is degenerate."""
    h, w = frame.shape[0], frame.shape[1]
    fx, fy, fw, fh = roi
    x0, x1 = int(w * fx), int(w * min(1.0, fx + fw))
    y0, y1 = int(h * fy), int(h * min(1.0, fy + fh))
    if x1 <= x0 or y1 <= y0:
        return None
    return frame[y0:y1, x0:x1]


def group_rows(tokens: Sequence[Token], y_tol: float = _ROW_Y_TOL) -> list[list[str]]:
    """Cluster OCR tokens into feed rows by y-proximity, each row sorted LEFT->RIGHT (killer first),
    rows ordered top->bottom. Returns rows as lists of token texts."""
    rows: list[dict] = []
    for x, y, text in sorted(tokens, key=lambda t: (t[1], t[0])):
        for r in rows:
            if abs(r["y"] - y) < y_tol:
                r["toks"].append((x, text))
                break
        else:
            rows.append({"y": y, "toks": [(x, text)]})
    return [[t for _, t in sorted(r["toks"])] for r in rows]


def rows_to_lines(rows: Sequence[Sequence[str]]) -> list[str]:
    """Join each row's tokens into one space-separated ``"killer … victim"`` line. Drops empty rows."""
    out = []
    for row in rows:
        line = " ".join(t for t in row if t and str(t).strip())
        if line.strip():
            out.append(line)
    return out


def classify_rows(rows: Sequence[Sequence[str]], own_handle: Optional[str] = None):
    """Robust TOKEN-based classification (the rule proven live). For each row the killer is the leftmost
    token; returns ``(verdict, killer_text, row)`` with verdict in {OWN_KILL, OWN_DEATH, OTHER_ROW}:
      * OWN_KILL  — your handle is carried by the killer (leftmost) token,
      * OWN_DEATH — your handle appears only in a later (victim) token (a death, never authored),
      * OTHER_ROW — a kill crediting someone else (the zero-false-read guard set)."""
    own = canon(own_handle if own_handle is not None else default_handle())
    out = []
    for row in rows:
        toks = [t for t in row if t and str(t).strip()]
        if not toks:
            continue
        killer = toks[0]
        if own and own in canon(killer):
            out.append((OWN_KILL, killer, list(toks)))
        elif own and any(own in canon(t) for t in toks[1:]):
            out.append((OWN_DEATH, killer, list(toks)))
        else:
            out.append((OTHER_ROW, killer, list(toks)))
    return out


def read_rows(frame, roi=DEFAULT_KILLFEED_ROI, ocr_fn: Optional[OcrFn] = None,
              y_tol: float = _ROW_Y_TOL) -> list[list[str]]:
    """Frame -> grouped kill-feed rows over the left-middle ROI. `ocr_fn` injected (default RapidOCR).
    Fail-open -> [] on any error / empty read."""
    try:
        crop = crop_roi(frame, roi)
        if crop is None:
            return []
        fn = ocr_fn if ocr_fn is not None else _rapidocr_tokens
        return group_rows(fn(crop) or [], y_tol=y_tol)
    except Exception:  # noqa: BLE001 — OCR must never break capture
        return []


def read_feed_lines(frame, roi=DEFAULT_KILLFEED_ROI, ocr_fn: Optional[OcrFn] = None) -> list[str]:
    """Frame -> ordered ``"killer … victim"`` lines (for the existing `feed_killfeed_text` path)."""
    return rows_to_lines(read_rows(frame, roi=roi, ocr_fn=ocr_fn))


def read_feed_text(frame, roi=DEFAULT_KILLFEED_ROI, ocr_fn: Optional[OcrFn] = None) -> str:
    """Newline-joined `read_feed_lines` — a drop-in for `RetinaCaptureCore.feed_killfeed_text` in place
    of the tesseract `hud_ocr.ocr_frame` read, for feeds the template path abstains on."""
    return "\n".join(read_feed_lines(frame, roi=roi, ocr_fn=ocr_fn))


def own_kill_count(frame, roi=DEFAULT_KILLFEED_ROI, own_handle: Optional[str] = None,
                   ocr_fn: Optional[OcrFn] = None) -> int:
    """End-to-end convenience: read + token-classify a frame, return the count of OWN_KILL rows (the
    robust per-frame recall signal proven live)."""
    return sum(1 for v, _, _ in classify_rows(read_rows(frame, roi=roi, ocr_fn=ocr_fn), own_handle)
               if v == OWN_KILL)


def _rapidocr_tokens(crop) -> list[Token]:
    """Default OCR fn: RapidOCR (PP-OCRv6) -> [(x_min, y_min, text), ...]. Lazy import + cached engine;
    fail-open -> [] (never breaks capture). Mirrors the read proven live on the card 2026-07-12."""
    try:
        from rapidocr import RapidOCR
    except Exception:  # noqa: BLE001
        return []
    try:
        eng = _rapidocr_tokens._engine
    except AttributeError:
        eng = _rapidocr_tokens._engine = RapidOCR()
    try:
        res = eng(crop)
        boxes = getattr(res, "boxes", None)
        txts = getattr(res, "txts", None)
        if boxes is None or txts is None:
            return []
        toks: list[Token] = []
        for b, t in zip(boxes, txts):
            xs = [p[0] for p in b]
            ys = [p[1] for p in b]
            toks.append((float(min(xs)), float(min(ys)), str(t)))
        return toks
    except Exception:  # noqa: BLE001
        return []
