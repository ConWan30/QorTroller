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
DEFAULT_STALL_LIMIT = 3          # G3 match-2 fix: raw-killer-authored crops the CANDIDATE scores sub-floor
                                 # before the cut is declared WEAK -> demote-and-recut (logged, R3-style)


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
    stall_limit: int = DEFAULT_STALL_LIMIT
    _bootstrap_source: Optional[str] = field(default=None, init=False)   # how the anchor was born (provenance):
    _consistent: int = field(default=0, init=False)            # ocr_row_v1 | static_feed_v1 | human_oracle
    _stalls: int = field(default=0, init=False)                # raw-authored crops this candidate missed
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
                          now_ms: float = 0.0, ocr_verified: bool = False,
                          source: str = "static_feed_v1") -> Optional[dict]:
        """In BOOTSTRAP, catch the first real feed kill row and auto-cut. Two catch sources:
          - `ocr_verified=True` (source=ocr_row_v1): the caller READ the literal handle glyphs in the killer
            slot — a strict full-canon read is STRONGER evidence than any template score, so the marginal
            `score >= bootstrap_floor` gate is BYPASSED (feed_v1 maxed 0.566 this session — that gate is the
            defect). This is the rendering-independent cold-start fix.
          - `ocr_verified=False` (source=static_feed_v1): legacy template catch — the lowered floor gate applies.
        BOTH still require the geometry gate AND a FRESH ROW APPEARANCE (R2 — a static patch is not a kill row;
        this preserves the anti-splice discipline regardless of source). cut_fn returns (anchor_obj, sha) or
        None (cut failed -> stay BOOTSTRAP). Returns a transition event or None."""
        if self._regime != BOOTSTRAP:
            return None
        if not self._in_killer_feed(x_frac, y_frac):
            return None
        if not ocr_verified and score < self.bootstrap_floor:   # template path: marginal-score gate applies
            return None
        if not fresh_row:                                   # R2: a static patch is NOT a kill row (both sources)
            return None
        cut = cut_fn()
        self._bootstrap_catches += 1
        if not cut:                                         # cut failed (unreadable crop) -> stay in bootstrap
            self._failures.append({"kind": "cut_failed", "ts_ms": now_ms, "score": round(score, 4)})
            return {"event": "bootstrap_cut_failed", "ts_ms": now_ms, "score": round(score, 4)}
        self._candidate_anchor, self._candidate_sha = cut
        self._bootstrap_source = source
        self._regime = CANDIDATE
        self._consistent = 0
        return {"event": "candidate_cut", "ts_ms": now_ms, "bootstrap_score": round(score, 4),
                "candidate_sha": self._candidate_sha, "session_id": self.session_id,
                "bootstrap_source": source}

    def human_oracle_cut(self, anchor_obj: Any, sha: str, now_ms: float = 0.0) -> dict:
        """STUB (operator-fired, NOT auto-live): inject a manually-identified anchor when both OCR and the
        template miss every early kill. Its input is the audit lane's UNRESOLVED contact sheet
        (killfeed_audit_lane) — the operator eyeballs a crop, cuts it, and hands (anchor, sha) here. Sets the
        candidate directly (source=human_oracle); the SAME K/FP promotion gates then apply. Never called from
        the live worker in this increment — the third fallback in the ocr->template->human ordering."""
        self._candidate_anchor, self._candidate_sha = anchor_obj, sha
        self._bootstrap_source = "human_oracle"
        self._regime = CANDIDATE
        self._consistent = 0
        self._bootstrap_catches += 1
        return {"event": "candidate_cut", "ts_ms": now_ms, "candidate_sha": sha,
                "session_id": self.session_id, "bootstrap_source": "human_oracle"}

    # --- CANDIDATE: self-consistency (K) + zero-FP gate before promotion (R3) ------------------------
    def observe_candidate(self, *, score: float, x_frac: Optional[float], y_frac: Optional[float],
                          is_background: bool, now_ms: float = 0.0,
                          raw_killer_authored: bool = False) -> Optional[dict]:
        """In CANDIDATE, `score` is the CANDIDATE anchor's killer-slot score for THIS crop. A killer-slot
        match >=promote_floor on a BACKGROUND/roster crop is an FP fire -> DEMOTE + log (R3). K consistent
        killer-slot matches >=promote_floor on real feed crops -> PROMOTE.

        `raw_killer_authored` (G3 match-2 stall-recut): the caller saw an INDEPENDENT killer-slot authored
        signal on this crop (feed_v1 raw >=0.66 / OCR read) that the candidate itself scored sub-floor. Each
        such miss is a STALL — evidence the cut row was weak (first-readable-row cuts can be; G2' stride-8 +
        G3 BR both showed it). At stall_limit: demote-and-recut, logged (never silent), so the NEXT catch
        replaces the weak cut instead of the candidate sitting stuck all match while real kills pass by.
        Returns a transition event or None."""
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
                self._stalls = 0
                return {"event": "candidate_demoted_fp", **fail}
            return None                                     # clean background -> no effect
        if raw_killer_authored and not clears:              # a real kill the candidate missed -> stall
            self._stalls += 1
            if self._stalls >= self.stall_limit:
                self._demotions += 1
                fail = {"kind": "candidate_stall", "ts_ms": now_ms, "stalls": self._stalls,
                        "sha": self._candidate_sha}
                self._failures.append(fail)
                self._regime = BOOTSTRAP                    # weak cut -> recut from the next catch (logged)
                self._candidate_anchor, self._candidate_sha, self._consistent = None, None, 0
                self._stalls = 0
                return {"event": "candidate_demoted_stall", **fail}
            return {"event": "candidate_stall", "ts_ms": now_ms, "stalls": self._stalls,
                    "limit": self.stall_limit}
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
            return (f"session anchor promoted (sha {self._candidate_sha}, source {self._bootstrap_source}); "
                    f"kills BEFORE promotion ran at bootstrap floor {self.bootstrap_floor:.2f} and may be "
                    f"missed/low-confidence (coverage gap)")
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
            "bootstrap_source": self._bootstrap_source,
            "failures": list(self._failures),
        }
