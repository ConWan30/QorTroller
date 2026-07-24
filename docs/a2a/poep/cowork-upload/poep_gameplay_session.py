"""GP-1 + GP-2 — gameplay-embedded PoEP session path (A2A-POEP-GAMEPLAY round-01).

The product pivot away from desk-probe VOLUME toward SESSION LIVENESS: sparse, unpredictable,
activity-gated adaptive-trigger challenges DURING real play, joined to a `session_id`. This module is
PURE (no hardware imports); it schedules + records + scores. The live HID fire lives in the CLI/bridge
path, never here.

CLAIM (locked language — candidate, NOT a flip):
    During an active play session on the registered Edge under a TRUSTED capture host, sparse
    unpredictable adaptive-trigger challenges produce live-bound responses under catch rules.
    This is SESSION LIVENESS (FLIP-A, host-trusted) — NOT identity, NOT anti-compromised-PC (FLIP-B).

`poep_enabled` / `L6B_ENABLED` / `L6_CHALLENGES_ENABLED` stay False; every output here carries
`poep_enabled=False` and `is_presence_verdict=False`. Reuses `poep_live_verify` + `poep_catch_trials`
scoring — it does NOT re-implement the crypto or the catch bars.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol

# ── Named constants (no hardcoded magic; all tunable + audited) ───────────────
DEFAULT_MIN_INTERVAL_S = 90.0        # sparse: challenges are rare, not desk-rapid
DEFAULT_MAX_INTERVAL_S = 300.0
GAMEPLAY_ACTIVE_FRACTION_FLOOR = 0.5  # session must be mostly real play, not menu-farmed
# round-04 F-GP-5: a single GO pass is too weak to call a SESSION a presence candidate.
MIN_GO_ISSUED = 2                    # v0.1 floor — named, still candidate (not a flip)
MIN_GO_VERIFY_PASS = 2
# round-04 F-GP-4: activity samples injected by the CLI are UNTRUSTED — a candidate presence
# session needs bridge-attested activity, never free operator JSON.
TRUSTED_ACTIVITY_SOURCE = "bridge"
# In-game amplitude stays LOW so play remains usable — NEVER the desk force=255 default.
# The live fire path reads this; the pure module only records it for honesty.
LOW_AMPLITUDE_FORCE_DEFAULT = 60      # in the 40-80 usable band
LOW_AMPLITUDE_FORCE_MAX = 80         # hard ceiling for the gameplay path (guarded in CLI)

_CLAIM = ("FLIP-A host-trusted session liveness: sparse live nonce-bound challenges during active play. "
          "NOT identity, NOT anti-compromised-PC (FLIP-B). poep_enabled stays False.")


class ActivityState(str, Enum):
    ACTIVE_GAMEPLAY = "ACTIVE_GAMEPLAY"
    MENU = "MENU"
    UNKNOWN = "UNKNOWN"          # fail-closed: never a challenge on UNKNOWN


class ChallengeKind(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"


def classify_activity(sample: dict[str, Any]) -> ActivityState:
    """Pure activity gate: an activity sample -> ACTIVE_GAMEPLAY | MENU | UNKNOWN.

    Fail-closed: anything ambiguous/absent -> UNKNOWN (no challenge). Precedence:
      1. explicit `gameplay_context` (Phase 235-GAD bridge field): ACTIVE_GAMEPLAY / MENU_DETECTED.
      2. `trigger_active_fraction` (float): > 0 -> ACTIVE, == 0 -> MENU.
      3. `trigger_active` (bool) OR `stick_active` (bool): either true -> ACTIVE; both explicitly
         false -> MENU.
      4. otherwise -> UNKNOWN.
    """
    if not isinstance(sample, dict):
        return ActivityState.UNKNOWN

    ctx = sample.get("gameplay_context")
    if isinstance(ctx, str):
        c = ctx.strip().upper()
        if c == "ACTIVE_GAMEPLAY":
            return ActivityState.ACTIVE_GAMEPLAY
        if c in ("MENU_DETECTED", "MENU"):
            return ActivityState.MENU
        # NULL / anything else -> fall through (don't trust an unknown context label)

    taf = sample.get("trigger_active_fraction")
    if isinstance(taf, (int, float)):
        return ActivityState.ACTIVE_GAMEPLAY if taf > 0.0 else ActivityState.MENU

    ta = sample.get("trigger_active")
    sa = sample.get("stick_active")
    if isinstance(ta, bool) or isinstance(sa, bool):
        if ta is True or sa is True:
            return ActivityState.ACTIVE_GAMEPLAY
        if ta is False and sa is False:
            return ActivityState.MENU
        # one present-and-false, other absent -> not enough signal
    return ActivityState.UNKNOWN


@dataclass(frozen=True)
class SessionChallengeEvent:
    """One in-play challenge outcome. `verify` is the dict from poep_live_verify.verify_live_response;
    `catch` is the optional poep_catch_trials.TrialScore rendered to a dict. `live_hardware` marks
    whether a real HID stimulus fired (dry runs are False and can NEVER be mistaken for live)."""
    kind: ChallengeKind
    ts_ns: int
    nonce: str
    verify: dict[str, Any]                 # from verify_live_response (has ok / poep_enabled=False)
    catch: Optional[dict[str, Any]] = None  # from a TrialScore, when a NO_GO catch trial was run
    amplitude_force: int = 0               # the low-amplitude force used (0 for NO_GO / dry)
    live_hardware: bool = False            # True only when a real HID stimulus fired

    @property
    def go_verify_pass(self) -> bool:
        return self.kind == ChallengeKind.GO and bool(self.verify.get("ok"))


@dataclass
class PlaySession:
    session_id: str
    device_id: str
    player_label: str
    t_start_ns: int
    topology_note: str = "dual-connect: USB->PC challenge+IMU, BT->console play (operator topology)"
    activity_samples: list[ActivityState] = field(default_factory=list)
    challenges: list[SessionChallengeEvent] = field(default_factory=list)
    t_stop_ns: Optional[int] = None
    # round-04 F-GP-2/4/5: a session is "dry" (plumbing) unless a real live path opened it, and its
    # activity is "cli_inject" (untrusted) unless bridge-attested. A presence CANDIDATE needs both
    # mode=="live" AND activity_source==TRUSTED_ACTIVITY_SOURCE — the CLI can never mint one.
    mode: str = "dry"                 # "dry" | "live"
    activity_source: str = "cli_inject"  # "cli_inject" | "bridge"

    def record_activity(self, sample: dict[str, Any]) -> ActivityState:
        st = classify_activity(sample)
        self.activity_samples.append(st)
        return st

    def record_challenge(self, ev: SessionChallengeEvent) -> None:
        self.challenges.append(ev)

    def gameplay_active_fraction(self) -> Optional[float]:
        if not self.activity_samples:
            return None
        n_active = sum(1 for s in self.activity_samples if s == ActivityState.ACTIVE_GAMEPLAY)
        return n_active / len(self.activity_samples)


def summarize_session(session: PlaySession) -> dict[str, Any]:
    """GP-1 session score (v0.1 candidate — NOT a flip). Round-04 splits two DISTINCT booleans:

      dry_plumbing_ok — the gates fired correctly (a plumbing/harness result). iff:
        n_go_issued >= MIN_GO_ISSUED AND n_go_verify_pass >= MIN_GO_VERIFY_PASS
        AND (no NO_GO OR human_fa_rate <= HUMAN_FA_BUDGET)
        AND gameplay_active_fraction >= GAMEPLAY_ACTIVE_FRACTION_FLOOR

      presence_session_candidate_ok — a real presence CANDIDATE. iff dry_plumbing_ok AND:
        effective_live  (session.mode=="live" AND every GO event was live_hardware)
        AND activity_source == TRUSTED_ACTIVITY_SOURCE  (bridge-attested, never CLI inject)

    A dry session (the only path shipped this round) can therefore reach `dry_plumbing_ok=True` but
    NEVER `presence_session_candidate_ok=True` — the name can no longer be confused with a verdict
    (round-04 F-GP-2). `effective_live` also DEFEATS the state-file spoof: a dry-mode session reports
    not-live even if a challenge row claims live_hardware=True (round-04 F-GP-4).
    """
    from .poep_catch_trials import HUMAN_FA_BUDGET

    go = [c for c in session.challenges if c.kind == ChallengeKind.GO]
    nogo = [c for c in session.challenges if c.kind == ChallengeKind.NO_GO]
    n_go_issued = len(go)
    n_go_verify_pass = sum(1 for c in go if c.go_verify_pass)

    n_nogo = len(nogo)
    n_nogo_fa = sum(1 for c in nogo if c.catch is not None and c.catch.get("human_ok") is False)
    human_fa_rate = (n_nogo_fa / n_nogo) if n_nogo else None

    active_frac = session.gameplay_active_fraction()

    go_ok = n_go_issued >= MIN_GO_ISSUED and n_go_verify_pass >= MIN_GO_VERIFY_PASS
    nogo_ok = (n_nogo == 0) or (human_fa_rate is not None and human_fa_rate <= HUMAN_FA_BUDGET)
    activity_ok = active_frac is not None and active_frac >= GAMEPLAY_ACTIVE_FRACTION_FLOOR
    dry_plumbing_ok = bool(go_ok and nogo_ok and activity_ok)

    # effective_live: a dry-mode session is NEVER live, regardless of any per-challenge flag
    # (defeats a hand-edited state file claiming live_hardware=True on dry-only sessions).
    all_go_live = bool(go) and all(c.live_hardware for c in go)
    effective_live = (session.mode == "live") and all_go_live
    activity_trusted = session.activity_source == TRUSTED_ACTIVITY_SOURCE
    candidate_ok = bool(dry_plumbing_ok and effective_live and activity_trusted)

    return {
        "schema": "qortroller-poep-gameplay-session-v0.1",
        "session_id": session.session_id,
        "device_id": session.device_id,
        "player_label": session.player_label,
        "t_start_ns": session.t_start_ns,
        "t_stop_ns": session.t_stop_ns,
        "topology_note": session.topology_note,
        "mode": session.mode,                       # "dry" | "live"
        "activity_source": session.activity_source,  # "cli_inject" | "bridge"
        "n_activity_samples": len(session.activity_samples),
        "gameplay_active_fraction": active_frac,
        "gameplay_active_fraction_floor": GAMEPLAY_ACTIVE_FRACTION_FLOOR,
        "n_go_issued": n_go_issued,
        "min_go_issued": MIN_GO_ISSUED,
        "n_go_verify_pass": n_go_verify_pass,
        "min_go_verify_pass": MIN_GO_VERIFY_PASS,
        "n_nogo": n_nogo,
        "n_nogo_human_fa": n_nogo_fa,
        "human_fa_rate": human_fa_rate,
        "human_fa_budget": HUMAN_FA_BUDGET,
        "gates": {"go_ok": go_ok, "nogo_ok": nogo_ok, "activity_ok": activity_ok},
        "effective_live": effective_live,
        "live_hardware": effective_live,   # summary-level: dry-mode is ALWAYS False here
        "activity_trusted": activity_trusted,
        # The two distinct verdicts (round-04 F-GP-2):
        "dry_plumbing_ok": dry_plumbing_ok,                # the gates fired (harness/plumbing)
        "presence_session_candidate_ok": candidate_ok,     # a real candidate — needs live + trusted
        # Structural honesty rails:
        "poep_enabled": False,
        "is_presence_verdict": False,
        "flip": "FLIP-A (host-trusted); NOT FLIP-B (anti-compromised-PC)",
        "claim": _CLAIM,
    }


# ── GP-2 — sparse scheduler (pure logic) ──────────────────────────────────────

class _RngLike(Protocol):
    def uniform(self, a: float, b: float) -> float: ...
    def random(self) -> float: ...


def next_challenge_delay_s(
    rng: _RngLike,
    min_s: float = DEFAULT_MIN_INTERVAL_S,
    max_s: float = DEFAULT_MAX_INTERVAL_S,
) -> float:
    """Draw the next sparse inter-challenge delay from [min_s, max_s].

    Deterministic under a seeded rng (tests); live passes a CSPRNG (random.SystemRandom) so the
    challenge time is UNPREDICTABLE — a fixed-schedule macro cannot pre-arm to the reaction band.
    """
    if min_s <= 0 or max_s < min_s:
        raise ValueError(f"bad interval bounds: min_s={min_s} max_s={max_s}")
    return float(rng.uniform(min_s, max_s))


def should_issue_challenge(
    activity: ActivityState,
    time_since_last_s: float,
    delay_s: float,
) -> bool:
    """Fire a challenge ONLY when gameplay is active AND the sparse delay has elapsed.

    Fail-closed: MENU / UNKNOWN -> never (menu farming cannot mint presence). Never on a
    non-positive delay.
    """
    if activity != ActivityState.ACTIVE_GAMEPLAY:
        return False
    if delay_s <= 0:
        return False
    return time_since_last_s >= delay_s


def plan_catch_kind(go_per_no_go: int, rng: _RngLike) -> ChallengeKind:
    """Pick GO vs NO_GO for the next in-session challenge, reusing the catch ratio philosophy
    (default 4:1 -> ~20% NO_GO). NO_GO fires the same arm/nonce schedule with NO force write."""
    period = max(1, int(go_per_no_go) + 1)
    return ChallengeKind.NO_GO if rng.random() < (1.0 / period) else ChallengeKind.GO


def now_ns() -> int:
    """Monotonic-ish wall clock for session timestamps (ns). Wraps time.time_ns for test seams."""
    return time.time_ns()


# ── Serialization (for the CLI's cross-invocation session state) ──────────────

def session_to_dict(session: PlaySession) -> dict[str, Any]:
    """Serialize a PlaySession to a plain dict (JSON-safe) for the CLI's active-session file."""
    return {
        "schema": "qortroller-poep-gameplay-session-state-v0",
        "session_id": session.session_id,
        "device_id": session.device_id,
        "player_label": session.player_label,
        "t_start_ns": session.t_start_ns,
        "t_stop_ns": session.t_stop_ns,
        "topology_note": session.topology_note,
        "mode": session.mode,
        "activity_source": session.activity_source,
        "activity_samples": [s.value for s in session.activity_samples],
        "challenges": [
            {
                "kind": c.kind.value,
                "ts_ns": c.ts_ns,
                "nonce": c.nonce,
                "verify": c.verify,
                "catch": c.catch,
                "amplitude_force": c.amplitude_force,
                "live_hardware": c.live_hardware,
            }
            for c in session.challenges
        ],
    }


def session_from_dict(d: dict[str, Any]) -> PlaySession:
    """Reconstruct a PlaySession from `session_to_dict` output (fail-closed on bad enums)."""
    s = PlaySession(
        session_id=str(d["session_id"]),
        device_id=str(d["device_id"]),
        player_label=str(d.get("player_label", "")),
        t_start_ns=int(d["t_start_ns"]),
        topology_note=str(d.get("topology_note", "")),
        t_stop_ns=(int(d["t_stop_ns"]) if d.get("t_stop_ns") is not None else None),
        mode=("live" if str(d.get("mode", "dry")) == "live" else "dry"),  # fail-closed to dry
        activity_source=str(d.get("activity_source", "cli_inject")),
    )
    for a in d.get("activity_samples", []):
        try:
            s.activity_samples.append(ActivityState(a))
        except ValueError:
            s.activity_samples.append(ActivityState.UNKNOWN)  # fail-closed
    for c in d.get("challenges", []):
        s.challenges.append(SessionChallengeEvent(
            kind=ChallengeKind(c["kind"]),
            ts_ns=int(c["ts_ns"]),
            nonce=str(c["nonce"]),
            verify=dict(c.get("verify", {})),
            catch=(dict(c["catch"]) if c.get("catch") is not None else None),
            amplitude_force=int(c.get("amplitude_force", 0)),
            live_hardware=bool(c.get("live_hardware", False)),
        ))
    return s
