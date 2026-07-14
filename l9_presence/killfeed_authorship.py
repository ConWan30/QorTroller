"""QorTroller L9 — Kill-feed Authorship (the anti-spectate differentiator; advisory / design-stage).

Tonight's measured negative ([[s-correlation-channels-refuted-vs-active-spectate]]) proved correlation-based
coupling cannot separate genuine play from active-spectate-spam: spamming R2 at a teammate's combat POV
supplies the same correlation as causation. The ONE signal that distinguishes "I caused this" from "I am
watching and mashing along" is SEMANTIC — a kill-feed entry crediting the player's OWN handle. A spectated
kill credits the teammate; the dead, spectating player never appears in the feed as the killer. No amount of
R2-spam fabricates your name in the kill-feed.

This oracle binds: an OWN-HANDLE kill row appears within the render+OCR latency window AFTER one of your R2
onsets -> AUTHORED. Kill rows crediting OTHER killers, with none crediting you -> SPECTATED.

PURE: the kill-feed OCR lines + R2 trigger onsets are INJECTED (the OCR boundary reuses hud_ocr.py over the
kill-feed ROI; the tesseract binary + per-game ROI are operator-gated). No FROZEN-v1 / 228B PoAC / chain /
IOTX. This is a FUSION input, not a replacement for the coupling channels.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

# OCR-confusion canonicalization: collapse the characters Tesseract routinely swaps so a noisy read of the
# handle still matches. lower(); o->0, i/l/|->1; keep alnum only. "QorTrola30" -> "q0rtr01a30"; a noisy
# "QorTroIa3O" -> "q0rtr01a30" (matches).
_OCR_FOLD = str.maketrans({"o": "0", "i": "1", "l": "1", "|": "1"})


def canon(s: str) -> str:
    """Canonical, OCR-noise-tolerant form of a name/line (pure)."""
    s = (s or "").lower().translate(_OCR_FOLD)
    return "".join(c for c in s if c.isalnum())


def default_handle() -> str:
    return os.getenv("QORTROLLER_HANDLE", "QorTrola30")


def is_own_killer_token(killer_token: str, own_canon: str) -> bool:
    """HARD-1 H1-A2 fix: boundary-aware own-killer match. The KILLER token, canonicalized
    (``canon`` already folds OCR confusables I->1 / O->0 / etc.), must EQUAL the own handle --
    NOT merely contain it. So ``QorTrola30`` still matches its OCR confusables (``QorTroIa3O``
    canonicalizes to the same string), but ``QorTro1a300`` / ``QorTrola300`` / ``xxQorTrola30``
    (longer tokens that merely CONTAIN the handle as a substring) do NOT author. Exact equality
    is the zero-false-read-safe choice: recall on OCR-mangled own tokens is intentionally
    sacrificed and recovered by the fresh-feed trigger's higher read rate (HARD-1 subject #1)."""
    return bool(own_canon) and canon(killer_token) == own_canon


class AuthorshipVerdict(str, Enum):
    AUTHORED_PRESENT = "AUTHORED_PRESENT"            # own-handle kill causally bound to YOUR trigger
    SPECTATED_NOT_AUTHORED = "SPECTATED_NOT_AUTHORED"  # kills seen, none credit you -> watching others
    OWN_KILL_UNBOUND = "OWN_KILL_UNBOUND"            # own-kill seen but not lag-bound to a trigger (edge)
    NO_KILL_EVENTS = "NO_KILL_EVENTS"               # no kill rows in the window
    UNVERIFIABLE = "UNVERIFIABLE"                   # no data


@dataclass
class AuthorshipResult:
    verdict: AuthorshipVerdict
    own_kills: int            # rows crediting your handle as the KILLER
    other_kills: int          # rows crediting a different killer (spectating signal)
    bound_kills: int          # own kills with a preceding R2 onset in the lag window
    lines_seen: int
    own_handle_canon: str
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value, "own_kills": self.own_kills, "other_kills": self.other_kills,
            "bound_kills": self.bound_kills, "lines_seen": self.lines_seen,
            "own_handle_canon": self.own_handle_canon, "evidence": self.evidence,
        }


class KillfeedAuthorshipOracle:
    """Inject R2 onsets (push_trigger) + kill-feed OCR lines (push_killfeed_line); verdict() decides whether a
    kill credited to YOUR handle was causally produced by YOUR trigger (AUTHORED) vs you are watching others'
    kills (SPECTATED). The kill-feed ROI restricts pushed lines to feed rows."""

    def __init__(self, own_handle: Optional[str] = None, *, lag_min_ms: float = 50.0,
                 lag_max_ms: float = 900.0, killer_max_frac: float = 0.5) -> None:
        self.own_canon = canon(own_handle if own_handle is not None else default_handle())
        self.lag_min_ms = float(lag_min_ms)
        self.lag_max_ms = float(lag_max_ms)        # kill row lags the trigger by render + feed-render + OCR
        self.killer_max_frac = float(killer_max_frac)  # own handle left of this fraction = killer position
        self._triggers: list[float] = []
        self._own_kills: list[float] = []
        self._other_kills: int = 0
        self._lines_seen: int = 0

    def push_trigger(self, ts_ms: float) -> None:
        """An R2 fire onset (rising edge over the fire threshold) at ts_ms."""
        self._triggers.append(float(ts_ms))

    def push_killfeed_line(self, ts_ms: float, ocr_line: str) -> None:
        """One OCR'd kill-feed row (killer on the LEFT, victim on the RIGHT in Warzone-class feeds).

        HARD-1 H1-A2/H1-A3 fix: TOKEN-based, not substring-find + offset-fraction. The killer is
        the LEFTMOST token; own-authorship requires boundary-aware equality on that token
        (``is_own_killer_token``). This kills two false-authorship surfaces the old heuristic had:
        (A2) a longer killer that merely CONTAINS the handle (``QorTro1a300``) no longer authors;
        (A3) a SHORT-killer death (``Efram1 QorTrola30`` -> you are the victim) is no longer counted
        as a kill just because your handle fell left of the 0.5 offset fraction. Mirrors the
        ``classify_rows`` token rule so oracle and token/sink paths agree."""
        self._lines_seen += 1
        toks = [t for t in str(ocr_line).split() if t.strip()]
        if not toks or not self.own_canon:
            return
        killer = toks[0]
        if is_own_killer_token(killer, self.own_canon):
            self._own_kills.append(float(ts_ms))                       # your handle IS the killer -> your kill
        elif any(self.own_canon in canon(t) for t in toks[1:]):
            pass                                                       # your handle is a victim -> your death (neutral)
        else:
            self._other_kills += 1                                    # a kill crediting someone else -> spectating

    def _bound_own_kills(self) -> int:
        n = 0
        for kt in self._own_kills:
            if any(self.lag_min_ms <= (kt - tt) <= self.lag_max_ms for tt in self._triggers):
                n += 1
        return n

    def verdict(self) -> AuthorshipResult:
        bound = self._bound_own_kills()

        def _r(v: AuthorshipVerdict, note: str) -> AuthorshipResult:
            return AuthorshipResult(
                verdict=v, own_kills=len(self._own_kills), other_kills=self._other_kills,
                bound_kills=bound, lines_seen=self._lines_seen, own_handle_canon=self.own_canon,
                evidence={"note": note, "n_triggers": len(self._triggers),
                          "lag_window_ms": [self.lag_min_ms, self.lag_max_ms]})

        if self._lines_seen == 0 and not self._triggers:
            return _r(AuthorshipVerdict.UNVERIFIABLE, "no kill-feed lines and no triggers")
        if bound > 0:
            return _r(AuthorshipVerdict.AUTHORED_PRESENT,
                      "own-handle kill causally bound to your R2 onset — you authored a kill in your own game")
        if self._own_kills:
            return _r(AuthorshipVerdict.OWN_KILL_UNBOUND,
                      "own-handle kill row present but not lag-bound to a trigger (timing/OCR gap)")
        if self._other_kills > 0:
            return _r(AuthorshipVerdict.SPECTATED_NOT_AUTHORED,
                      "kill rows credit other killers, none credit you — spectating, not authoring")
        return _r(AuthorshipVerdict.NO_KILL_EVENTS, "no kill rows observed in the window")

    def reset(self) -> None:
        self._triggers.clear(); self._own_kills.clear(); self._other_kills = 0; self._lines_seen = 0
