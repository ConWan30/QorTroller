"""EVENT-BIND — cryptographic per-event kill-authorship binding (the KAS-lobe generalization
of adversarial/cocapture_binding.py's RECORD_HASH_PRODUCTION closure).

THE GAP (named by the code): KAS authorship today is a TEMPORAL ∩ — a kill's on-screen composite
"resolves only inside an R2 window" (kill_authorship_session), i.e. the outcome timestamp falls
inside a live trigger window. The two lobes (authored_screen_event = OUTCOME on the WGC
frame-capture clock; hid_onset_event = the r2_onset INPUT on the device clock) feed one events_root
but neither carries a PoAC record_hash — so the outcome↔input bind is clock proximity, not a
shared secret. cocapture_binding names the production closure (RECORD_HASH_PRODUCTION) for the
presence↔retina lobe; this module is its KAS-lobe twin.

THE ANCHOR: the PoAC record_hash = SHA-256(raw[:164]) — already per-record, already stamped into
retina_event_log.record_hash_hex. At capture time the host stamps the LIVE record_hash into BOTH
the authored screen event and the co-detected HID onset (increment 2, flagged). A verifier then
checks "these two lobes reference the SAME record_hash" — independent of either clock. Absent
stamping, the binder falls back to the temporal join with an EXPLICIT TEMPORAL_PROTOTYPE downgrade
label (never silently conflated — the cocapture_binding discipline).

HONEST SCOPE (docs/event-bind-design-2026-07-09.md §2):
  - CLOSES cross-source SPLICE: a kill-outcome from capture A and an input-onset from capture B
    cannot share an anchor even with aligned timestamps — the crypto join fails, the pair degrades
    to TEMPORAL_PROTOTYPE (honest), never RECORD_HASH_PRODUCTION. The temporal ∩ cannot resist this.
  - COMPOSES with PoSR recency (Arc 6 temporal_beacon) to add REPLAY resistance — NOT closed by
    EVENT-BIND alone (a faithful replay reproduces self-consistent old anchors).
  - Does NOT close a compromised capture HOST (it stamps both lobes) — the witness-independence
    long arc; verifier_independence=False is inherited.

No new primitive / domain tag / FROZEN-v1: EVENT-BIND REFERENCES the existing PoAC record_hash and
never touches the 228-byte wire. PURE stdlib — no bridge/cv2/DB import (the caller injects rows).
"""
from __future__ import annotations

import html
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Temporal FALLBACK window (ms). The crypto join is time-independent — this bounds only the
# TEMPORAL_PROTOTYPE fallback. 2000 ms mirrors the presence↔retina fusion window
# (cocapture_binding's DEFAULT_WINDOW_NS = 2.0 s) as a documented default; override per caller.
DEFAULT_BIND_WINDOW_MS = 2000.0

BIND_SCHEMA = "qortroller-event-bind-v0"     # schema string — NOT a domain tag, NOT FROZEN-v1


class EventBindMode(str, Enum):
    """How a kill OUTCOME (screen) is tied to its causing INPUT (HID onset)."""
    RECORD_HASH_PRODUCTION = "RECORD_HASH_PRODUCTION"   # SHARED PoAC record_hash — splice-proof
    TEMPORAL_PROTOTYPE = "TEMPORAL_PROTOTYPE"           # ±window timestamp proximity ONLY — splice-vulnerable
    UNBOUND = "UNBOUND"                                 # no onset within the window / no crypto match


@dataclass(frozen=True)
class ScreenOutcome:
    """An authored screen event (authored_screen_event) — the OUTCOME lobe. record_hash populated
    ONLY once capture-path stamping lands (increment 2)."""
    t_ms: float                              # killer_first_ms (frame-capture clock)
    record_hash: Optional[str] = None        # the PoAC anchor live at the kill, or None
    kill_id: Optional[str] = None            # local label (window_gate_ms / row id) — not a claim
    window_gate_ms: Optional[float] = None


@dataclass(frozen=True)
class HidOnset:
    """An r2_onset event (hid_onset_event) — the INPUT lobe (device clock). The live controller
    cause a replay-splice cannot produce on demand."""
    t_ms: float                              # device-clock wall-corrected ms
    record_hash: Optional[str] = None        # the PoAC anchor live at the onset, or None
    device_ts: Optional[int] = None


@dataclass(frozen=True)
class BoundKill:
    outcome: ScreenOutcome
    onset: Optional[HidOnset]
    offset_ms: Optional[float]               # signed: onset.t_ms - outcome.t_ms
    mode: EventBindMode
    cryptographically_bound: bool

    @property
    def bound(self) -> bool:
        return self.onset is not None

    @property
    def anchor_record_hash(self) -> Optional[str]:
        """The PoAC anchor this kill's authorship can claim, if any. Production: the shared
        record_hash confirmed on both lobes. Prototype: the nearest in-window onset's hash — a
        CANDIDATE anchor valid only under the temporal-proximity assumption (often None)."""
        if self.onset is None:
            return None
        if self.cryptographically_bound and self.outcome.record_hash:
            return self.outcome.record_hash
        return self.onset.record_hash


@dataclass(frozen=True)
class EventBindReport:
    pairs: list
    window_ms: float

    @property
    def n_outcomes(self) -> int:
        return len(self.pairs)

    @property
    def n_bound(self) -> int:
        return sum(1 for p in self.pairs if p.bound)

    @property
    def n_crypto(self) -> int:
        return sum(1 for p in self.pairs if p.cryptographically_bound)

    @property
    def n_temporal(self) -> int:
        return sum(1 for p in self.pairs if p.mode == EventBindMode.TEMPORAL_PROTOTYPE)

    def coverage(self) -> float:
        return self.n_bound / self.n_outcomes if self.n_outcomes else 0.0

    def crypto_coverage(self) -> float:
        return self.n_crypto / self.n_outcomes if self.n_outcomes else 0.0

    def offset_stats_ms(self) -> dict:
        offs = sorted(abs(p.offset_ms) for p in self.pairs if p.offset_ms is not None)
        if not offs:
            return {"n": 0, "min_ms": None, "median_ms": None, "max_ms": None}
        mid = offs[len(offs) // 2]
        return {"n": len(offs), "min_ms": round(offs[0], 1),
                "median_ms": round(mid, 1), "max_ms": round(offs[-1], 1)}

    @property
    def binding_is_cryptographic(self) -> bool:
        """True only when EVERY outcome is crypto-bound — the strong claim, or nothing."""
        return self.n_outcomes > 0 and self.n_crypto == self.n_outcomes

    def to_dict(self) -> dict:
        return {"schema": BIND_SCHEMA, "window_ms": self.window_ms,
                "n_outcomes": self.n_outcomes, "n_bound": self.n_bound,
                "n_crypto_bound": self.n_crypto, "n_temporal": self.n_temporal,
                "coverage": round(self.coverage(), 4),
                "crypto_coverage": round(self.crypto_coverage(), 4),
                "offset_stats_ms": self.offset_stats_ms(),
                "binding_is_cryptographic": self.binding_is_cryptographic}

    def to_markdown(self) -> str:
        d = self.to_dict()
        banner = (
            "**CRYPTOGRAPHIC BINDING (production).** Every authored kill shares a PoAC "
            "`record_hash` across both lobes — a splice-proof, clock-independent bind."
            if d["binding_is_cryptographic"] else
            "**TEMPORAL CORRELATION (prototype) — NOT a cryptographic proof.** Pairs are joined by "
            "±window timestamp proximity only. A temporal pair shows a kill outcome and a trigger "
            "onset CO-OCCURRED; it does NOT prove the input caused THAT kill, and a timestamp-"
            "aligned splice would pass. Production closure = stamp the live `record_hash` into both "
            "lobes at capture time (see docs/event-bind-design-2026-07-09.md)."
        )
        off = d["offset_stats_ms"]
        lines = [
            "# EVENT-BIND — Kill Authorship Binding Report", "", banner, "",
            f"- Temporal fallback window: ±{d['window_ms']:.0f} ms",
            f"- Authored kills (outcomes): {d['n_outcomes']}",
            f"- Bound: {d['n_bound']} ({d['coverage'] * 100:.1f}%)",
            f"- Cryptographically bound (splice-proof): {d['n_crypto_bound']} "
            f"({d['crypto_coverage'] * 100:.1f}%)",
            f"- Temporal-only (splice-vulnerable): {d['n_temporal']}",
            f"- Bound-pair offset |Δt|: min={off['min_ms']}ms median={off['median_ms']}ms "
            f"max={off['max_ms']}ms (n={off['n']})", "",
            "| outcome t_ms | mode | crypto | Δt ms | anchor record_hash |",
            "|---|---|---|---|---|",
        ]
        for p in self.pairs:
            anchor = p.anchor_record_hash
            anchor_s = html.escape(anchor[:16] + "..") if anchor else "(none)"
            dt = round(p.offset_ms, 1) if p.offset_ms is not None else ""
            lines.append(f"| {p.outcome.t_ms} | {p.mode.value} "
                         f"| {'yes' if p.cryptographically_bound else 'no'} | {dt} | {anchor_s} |")
        return "\n".join(lines)


def stamp_enabled() -> bool:
    """EVENT-BIND increment 2 daemon gate: whether the capture path stamps the live record_hash into
    events. Default OFF (env EVENT_BIND_STAMP_ENABLED unset) -> events byte-identical to pre-EVENT-BIND.
    The schema always ACCEPTS a record_hash; this only gates whether the daemon SUPPLIES one."""
    return os.environ.get("EVENT_BIND_STAMP_ENABLED", "").strip().lower() in ("1", "true", "yes", "on")


def screen_outcome_from_event(ev) -> Optional[ScreenOutcome]:
    """authored_screen_event dict -> ScreenOutcome row (or None if no numeric t_ms). Fail-open."""
    if not isinstance(ev, dict):
        return None
    t = ev.get("t_ms")
    if not isinstance(t, (int, float)):
        return None
    return ScreenOutcome(t_ms=float(t), record_hash=ev.get("record_hash"),
                         kill_id=(str(ev["window_gate_ms"]) if ev.get("window_gate_ms") is not None else None),
                         window_gate_ms=ev.get("window_gate_ms"))


def hid_onset_from_event(ev) -> Optional[HidOnset]:
    """hid_onset_event dict -> HidOnset row (or None if no numeric t_ms). Fail-open."""
    if not isinstance(ev, dict):
        return None
    t = ev.get("t_ms")
    if not isinstance(t, (int, float)):
        return None
    return HidOnset(t_ms=float(t), record_hash=ev.get("record_hash"), device_ts=ev.get("device_ts"))


def bind_session_events(screen_events, hid_events, *,
                        window_ms: float = DEFAULT_BIND_WINDOW_MS) -> EventBindReport:
    """Convenience: adapt canonical session event dicts (authored_screen_event / hid_onset_event, e.g. from
    session_screen_events / session_hid_events or the archived JSONL) into binder rows and bind. Rows with no
    numeric t_ms are dropped (fail-open). Today (pre-stamping) this reports TEMPORAL_PROTOTYPE on real
    sessions; once the daemon stamps record_hash it upgrades to RECORD_HASH_PRODUCTION with no code change."""
    outcomes = [o for o in (screen_outcome_from_event(e) for e in (screen_events or [])) if o is not None]
    onsets = [o for o in (hid_onset_from_event(e) for e in (hid_events or [])) if o is not None]
    return bind_events(outcomes, onsets, window_ms=window_ms)


def _crypto_match(outcome: ScreenOutcome, onsets: list) -> Optional[HidOnset]:
    """An onset sharing the outcome's record_hash, regardless of time — the PRODUCTION bind
    (needs no temporal assumption). Closest-in-time if several share the hash."""
    if not outcome.record_hash:
        return None
    cands = [o for o in onsets if o.record_hash and o.record_hash == outcome.record_hash]
    if not cands:
        return None
    return min(cands, key=lambda o: abs(o.t_ms - outcome.t_ms))


def _nearest_in_window(outcome: ScreenOutcome, onsets: list, window_ms: float) -> Optional[HidOnset]:
    """Nearest onset within ±window_ms — the TEMPORAL fallback."""
    best: Optional[HidOnset] = None
    best_abs = window_ms + 1.0
    for o in onsets:
        d = abs(o.t_ms - outcome.t_ms)
        if d <= window_ms and d < best_abs:
            best, best_abs = o, d
    return best


def bind_events(outcomes: list, onsets: list, *,
                window_ms: float = DEFAULT_BIND_WINDOW_MS) -> EventBindReport:
    """Bind each kill OUTCOME to its causing INPUT onset. Crypto-preferred over temporal:
      1. shared record_hash onset (time-independent) -> RECORD_HASH_PRODUCTION, crypto=True.
      2. else nearest onset within ±window_ms -> TEMPORAL_PROTOTYPE, crypto=False.
      3. else -> UNBOUND.
    Fail-open: malformed/empty inputs yield an empty/UNBOUND report, never an error. Note (§2):
    a shared record_hash makes the bind SPLICE-PROOF, not replay-proof (compose with PoSR recency)
    and not host-proof (verifier_independence stays False)."""
    outcomes = list(outcomes or [])
    onsets = list(onsets or [])
    pairs: list = []
    for outcome in outcomes:
        crypto = _crypto_match(outcome, onsets)
        if crypto is not None:
            pairs.append(BoundKill(outcome=outcome, onset=crypto,
                                   offset_ms=crypto.t_ms - outcome.t_ms,
                                   mode=EventBindMode.RECORD_HASH_PRODUCTION,
                                   cryptographically_bound=True))
            continue
        near = _nearest_in_window(outcome, onsets, window_ms)
        if near is not None:
            pairs.append(BoundKill(outcome=outcome, onset=near,
                                   offset_ms=near.t_ms - outcome.t_ms,
                                   mode=EventBindMode.TEMPORAL_PROTOTYPE,
                                   cryptographically_bound=False))
            continue
        pairs.append(BoundKill(outcome=outcome, onset=None, offset_ms=None,
                               mode=EventBindMode.UNBOUND, cryptographically_bound=False))
    return EventBindReport(pairs=pairs, window_ms=window_ms)
