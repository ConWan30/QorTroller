"""QorTroller L9 — per-session feed-cut authorship anchor auto-generation (killer-slot path only).

WHY (evidence base): the killfeed kill-highlight rendering is per-match (team-color assignment). A STATIC
anchor cut from one match's kill fails the next — demonstrated TWICE (roster->teal `2de67543`, teal->yellow
2026-07-03: live 0/20 kills, killer-slot feed_v1 max 0.600 < 0.66 floor). The deciding test: a THIS-SESSION
feed-cut anchor recalls 62 killer-slot crops >=0.66 where feed_v1 (teal) gets 0, and a same-session same-color
ROSTER-cut gets 0 (max 0.607) — proving the roster->feed gap is STRUCTURAL rendering, not a color-variant
treadmill an ensemble could converge on. So: cut the anchor from THIS session's first real feed kill row.

This module is the PURE state machine only (BOOTSTRAP -> CANDIDATE -> PROMOTED). It holds opaque anchor
objects (whatever the caller's cut/match ops produce — this module never imports cv2) and consumes
per-crop RESULTS + an injected `cut_fn`; all image ops (binarize/matchTemplate/crop/frame-diff) live in the
caller (qortroller_retina_capture). This keeps the false-catch and gate-failure paths unit-testable.

SCOPE BOUNDARY: killer-slot / AUTHORED path ONLY. The victim-slot / OWN_DEATH path works on static feed_v1
(4/4 offline, 2 live) and does NOT inherit this bootstrap machinery — if victim rendering later drifts, that
is its own finding.

The four riders (all at the failure seams):
  R1 — bootstrap is a DEAD ZONE: every record carries the regime that scored it (bootstrap_<id>@floor vs
       session_<id>@floor); a 0-kill session never promotes and reads "bootstrap-only, no session anchor".
  R2 — the bootstrap CATCH is FP-risky (0.55 is the floor the offline rework rejected). Before auto-cut the
       caught row must pass the geometry gates AND a FRESH-ROW-APPEARANCE check (frame-diff, caller-supplied)
       — a static background patch scoring 0.55 did not appear as a transient.
  R3 — promotion = K=3 consistent killer-slot matches at 0.66 AND ZERO killer-slot fires at 0.66 on the
       session's accumulated roster/neutral crops. On gate FAILURE: demote to bootstrap, revert, and LOG the
       failure — never silently retry-cut from the next catch (invisible anchor churn otherwise).
  R4 — the promoted anchor is a SESSION ARTIFACT: caller archives its PNG+SHA alongside the corpus (recall
       claims stay re-derivable; the accumulating library is the future Tier-1 recognizer's training set).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Regimes
BOOTSTRAP = "BOOTSTRAP"
CANDIDATE = "CANDIDATE"
PROMOTED = "PROMOTED"

DEFAULT_BOOTSTRAP_FLOOR = 0.55   # lowered floor to CATCH the first feed kill row (gated by R2, never ships a verdict)
DEFAULT_PROMOTE_FLOOR = 0.66     # the frozen killfeed_cv match floor — unchanged; the session anchor runs here
DEFAULT_K_CONSISTENCY = 3        # subsequent killer-slot matches required before promotion (reachable early)


@dataclass
class SessionAnchorGenerator:
    """State machine for per-session feed-cut anchor auto-generation. Pure: holds opaque anchor objects and
    consumes classification RESULTS; the caller performs all cv2 work + supplies `cut_fn`."""
    bootstrap_id: str = "feed_v1"
    bootstrap_floor: float = DEFAULT_BOOTSTRAP_FLOOR
    promote_floor: float = DEFAULT_PROMOTE_FLOOR
    k_consistency: int = DEFAULT_K_CONSISTENCY
    killer_max_frac: float = 0.28          # mirror killfeed_cv.KILLER_MAX_FRAC_PANEL (read-only)
    feed_region_max_yfrac: float = 0.42    # mirror killfeed_cv.FEED_REGION_MAX_YFRAC (read-only)
    session_id: str = "session"            # caller sets a per-session id (date/uuid)

    _regime: str = field(default=BOOTSTRAP, init=False)
    _candidate_anchor: Any = field(default=None, init=False)   # opaque template the caller scores with
    _candidate_sha: Optional[str] = field(default=None, init=False)
    _consistent: int = field(default=0, init=False)
    # accounting
    _fp_fires: int = field(default=0, init=False)
    _demotions: int = field(default=0, init=False)
    _promotions: int = field(default=0, init=False)
    _bootstrap_catches: int = field(default=0, init=False)
    _failures: list = field(default_factory=list, init=False)

    # --- geometry gate (shared) ---------------------------------------------------------------------
    def _in_killer_feed(self, x_frac: Optional[float], y_frac: Optional[float]) -> bool:
        return (x_frac is not None and y_frac is not None
                and x_frac < self.killer_max_frac and y_frac < self.feed_region_max_yfrac)

    @property
    def regime(self) -> str:
        return self._regime

    def active_anchor(self) -> Any:
        """The anchor the caller should SCORE the next crop with: None in BOOTSTRAP (caller uses its own
        bootstrap anchor — feed_v1 or roster), else the candidate/session template this machine holds."""
        return None if self._regime == BOOTSTRAP else self._candidate_anchor

    def effective_floor(self) -> float:
        return self.bootstrap_floor if self._regime == BOOTSTRAP else self.promote_floor

    def active_anchor_tag(self) -> str:
        """Provenance stamp for records scored under the current regime (R1)."""
        if self._regime == BOOTSTRAP:
            return f"bootstrap_{self.bootstrap_id}@{self.bootstrap_floor:.2f}"
        if self._regime == CANDIDATE:
            return f"candidate_{self.session_id}@{self.promote_floor:.2f}"
        return f"session_{self.session_id}@{self.promote_floor:.2f}"

    def is_promoted(self) -> bool:
        return self._regime == PROMOTED

    # --- BOOTSTRAP: catch the first real feed kill row, then auto-cut (R2 gates) ---------------------
    def observe_bootstrap(self, *, score: float, x_frac: Optional[float], y_frac: Optional[float],
                          fresh_row: bool, cut_fn: Callable[[], Optional[tuple]],
                          now_ms: float = 0.0) -> Optional[dict]:
        """In BOOTSTRAP, `score` is the BOOTSTRAP anchor's killer-slot score. If it clears the lowered floor
        AND passes the geometry gate AND the caught location saw a FRESH ROW APPEARANCE (R2), invoke cut_fn
        to auto-cut the candidate anchor. cut_fn returns (anchor_obj, sha) or None (cut failed -> stay
        BOOTSTRAP). Returns a transition event dict or None."""
        if self._regime != BOOTSTRAP:
            return None
        if score < self.bootstrap_floor or not self._in_killer_feed(x_frac, y_frac):
            return None
        if not fresh_row:                                   # R2: a static patch scoring 0.55 is NOT a kill row
            return None
        cut = cut_fn()
        self._bootstrap_catches += 1
        if not cut:                                         # cut failed (unreadable crop) -> stay in bootstrap
            self._failures.append({"kind": "cut_failed", "ts_ms": now_ms, "score": round(score, 4)})
            return {"event": "bootstrap_cut_failed", "ts_ms": now_ms, "score": round(score, 4)}
        self._candidate_anchor, self._candidate_sha = cut
        self._regime = CANDIDATE
        self._consistent = 0
        return {"event": "candidate_cut", "ts_ms": now_ms, "bootstrap_score": round(score, 4),
                "candidate_sha": self._candidate_sha, "session_id": self.session_id}

    # --- CANDIDATE: self-consistency (K) + zero-FP gate before promotion (R3) ------------------------
    def observe_candidate(self, *, score: float, x_frac: Optional[float], y_frac: Optional[float],
                          is_background: bool, now_ms: float = 0.0) -> Optional[dict]:
        """In CANDIDATE, `score` is the CANDIDATE anchor's killer-slot score for THIS crop. A killer-slot
        match >=promote_floor on a BACKGROUND/roster crop is an FP fire -> DEMOTE + log (R3). K consistent
        killer-slot matches >=promote_floor on real feed crops -> PROMOTE. Returns a transition event or
        None."""
        if self._regime != CANDIDATE:
            return None
        clears = score >= self.promote_floor and self._in_killer_feed(x_frac, y_frac)
        if is_background:
            if clears:                                      # R3: the candidate false-fires on neutral content
                self._fp_fires += 1
                self._demotions += 1
                fail = {"kind": "candidate_fp", "ts_ms": now_ms, "score": round(score, 4),
                        "sha": self._candidate_sha}
                self._failures.append(fail)
                self._regime = BOOTSTRAP                    # revert; the NEXT catch is a fresh cut (logged)
                self._candidate_anchor, self._candidate_sha, self._consistent = None, None, 0
                return {"event": "candidate_demoted_fp", **fail}
            return None                                     # clean background -> no effect
        if clears:
            self._consistent += 1
            if self._consistent >= self.k_consistency:
                self._regime = PROMOTED
                self._promotions += 1
                return {"event": "promoted", "ts_ms": now_ms, "sha": self._candidate_sha,
                        "session_id": self.session_id, "consistent": self._consistent}
            return {"event": "candidate_progress", "ts_ms": now_ms, "consistent": self._consistent,
                    "need": self.k_consistency}
        return None

    def coverage_note(self) -> str:
        """R1 session-summary honesty: state the bootstrap dead-zone / no-promote explicitly."""
        if self._regime == PROMOTED:
            return (f"session anchor promoted (sha {self._candidate_sha}); kills BEFORE promotion ran at "
                    f"bootstrap floor {self.bootstrap_floor:.2f} and may be missed/low-confidence (coverage gap)")
        if self._regime == CANDIDATE:
            return ("candidate cut but NOT promoted (K/ FP gate unmet); ran bootstrap-floor all session — "
                    "kill recall is a known coverage gap")
        return "bootstrap-only, no session anchor (0 gate-passing kills caught) — bootstrap-floor all session"

    def status(self) -> dict:
        return {
            "regime": self._regime,
            "anchor_tag": self.active_anchor_tag(),
            "effective_floor": self.effective_floor(),
            "consistent": self._consistent,
            "k_needed": self.k_consistency,
            "bootstrap_catches": self._bootstrap_catches,
            "fp_fires": self._fp_fires,
            "demotions": self._demotions,
            "promotions": self._promotions,
            "candidate_sha": self._candidate_sha,
            "failures": list(self._failures),
        }
