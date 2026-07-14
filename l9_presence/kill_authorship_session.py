"""QorTroller L9 — Kill-Authorship Session Record (L4 conjunction verdict, Increment 2 step 1).

THE CLAIM (docs/l4-conjunction-verdict-scope-2026-07-03.md): "a live human, providing real controller input,
authored N kill events in THIS session — each witnessed as own-handle-in-killer-slot DURING a live trigger
window." The per-kill conjunction already exists structurally in the producer (composite AUTHORED resolves
only inside R2 windows); this module folds a session's evidence into ONE tamper-evident record.

LEGS (weights per the measured evidence classes — B2-as-trigger REFUTED 2026-07-03, so coupling is
corroboration ONLY and never required):
  - authored composites (primary semantic leg)  - anchor provenance event trail (cut/promote/demote/source)
  - th2-coupling corroboration (advisory)        - capture hygiene (validity conditions)

VERDICTS (closed enum, fail-closed):
  AUTHORED_SESSION    >= min_kills authored composites AND hygiene clean
  INSUFFICIENT_KILLS  hygiene clean but too few authored composites (incl. zero) — honest, not a failure
  HYGIENE_FAIL        capture validity conditions unmet — NO authorship claim is issued over a dirty capture
  UNVERIFIABLE        malformed/empty inputs — never guessed

COMMITMENT: SHA-256(b"QORTROLLER-KAS-v0" || canonical sorted-key JSON of the body). CANDIDATE domain tag —
NOT FROZEN-v1, NOT registered as a capability tag, NO chain write. Advisory l9_presence artifact feeding
D-CERT-5. PURE: stdlib only; no bridge/session/chain imports.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional

KAS_DOMAIN_TAG = b"QORTROLLER-KAS-v0"        # candidate; a v1 freeze is an explicit future ceremony

AUTHORED_SESSION = "AUTHORED_SESSION"
INSUFFICIENT_KILLS = "INSUFFICIENT_KILLS"
HYGIENE_FAIL = "HYGIENE_FAIL"
UNVERIFIABLE = "UNVERIFIABLE"

DEFAULT_MIN_KILLS = 2                        # pre-registered in the scope doc (set BEFORE G4; not tuned after)
# Hygiene validity conditions (from the RGC diag surface). A certificate is only issued over a clean capture.
DEFAULT_MAX_FRAME_ERRS = 10
DEFAULT_MAX_FRAME_STALL_S = 5.0
ALLOWED_TS_SOURCES = ("timespan",)           # WGC presentation timestamps — the calibrated time base


def _dedup_composites(composites) -> list:
    """Drop double-writes (pre-`63f25aa9` jsonl carries each window's resolution twice — and the two writes
    have DIFFERENT ts_ms, because flush_if_expired resolved at tick time and mark_onset at onset time). The
    stable window identity is window_gate_ms (+ verdict/score defensively): one resolution per window.
    Order-preserving."""
    seen, out = set(), []
    for c in composites:
        k = (c.get("window_gate_ms"), c.get("verdict"), c.get("composite_score"))
        if k in seen:
            continue
        seen.add(k)
        out.append(c)
    return out


@dataclass
class KillAuthorshipSessionRecord:
    """One session's fused kill-authorship verdict + every number it was computed from (re-derivable)."""
    session_label: str
    handle: str
    verdict: str
    authored_kills: int
    authored_scores: list
    anchor_tags: list                       # regime tags carried by the AUTHORED composites (provenance)
    windows_total: int
    composites_total: int
    own_deaths: int
    event_trail: list                       # cut/promote/demote events (sha, source, ts) — the anchor's life
    coupling_corroboration: Optional[dict]  # windowed th2 aggregate (ADVISORY; never gates the verdict)
    hygiene: dict
    span_ms: Optional[list]
    min_kills: int
    notes: list = field(default_factory=list)
    # Increment B B2: the unified events_root binds this session's kill OUTCOMES to the HID commitment chain in
    # this window. When present, the claim upgrades from "authorship evidence existed this session" to "these
    # kill outcomes were bound to this HID commitment in this window." Computed by the caller via the existing
    # retina_state_commitment.compute_events_root (NO new frozen tag). lobes = which lobes contributed.
    events_root: Optional[str] = None
    events_root_scheme: Optional[str] = None
    events_root_lobes: Optional[list] = None
    # Cross-lobe coherence readout (input->outcome causal match + per-outcome latency). ADVISORY: it is a
    # DERIVED view over the events already bound by events_root (retina_session_root.cross_lobe_coherence), so
    # it rides in to_dict ONLY — deliberately NOT in body_dict/commitment (the root already commits the
    # underlying events; recomputing it into the commitment would be redundant and would move existing
    # commitments). UNCALIBRATED; never gates the verdict.
    cross_lobe: Optional[dict] = None
    # U1 (2026-07-04, design doc §2.6): the shared session identifier — SHA-256 of the canonical
    # "{label}_{stamp}" string (l9_presence/session_identity.py, THE one preimage). Rides to_dict ONLY,
    # deliberately NOT body_dict/commitment (same discipline as cross_lobe): it is a JOIN KEY correlating
    # this record with the session's fusion-proof meta + tier-1 archive manifest, not new evidence — and
    # keeping it out of the preimage keeps every pre-U1 commitment byte-stable. D-CERT-9 posture: the
    # stamp pins the ISSUING INSTANCE under label reuse (post-hoc detection, no refusal surface).
    session_id: Optional[str] = None
    session_display: Optional[str] = None
    # WA-R04 (2026-07-14, Q-C2): the middle authorship layer WITNESSED ⊂ BOUND ⊂ AUTHORED. bound_kills =
    # own-kills with a preceding R2 onset in the lag window (the live oracle's kf_bound_kills). Rides to_dict
    # ONLY, deliberately NOT body_dict/commitment (same discipline as session_id/cross_lobe): it is a
    # DERIVED reporting projection over evidence the record already carries, and keeping it out of the
    # preimage keeps every pre-R04 commitment byte-stable. It NEVER gates the verdict; it lets the scorecard
    # show `bound: N [MEASURED]` from a durable source instead of ABSENT. AUTHORED remains the strict tier.
    bound_kills: Optional[int] = None

    def body_dict(self) -> dict:
        d = {k: getattr(self, k) for k in (
            "session_label", "handle", "verdict", "authored_kills", "authored_scores", "anchor_tags",
            "windows_total", "composites_total", "own_deaths", "event_trail", "coupling_corroboration",
            "hygiene", "span_ms", "min_kills", "notes", "events_root", "events_root_scheme",
            "events_root_lobes")}
        return d

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.body_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")

    def commitment(self) -> str:
        return hashlib.sha256(KAS_DOMAIN_TAG + self.canonical_bytes()).hexdigest()

    def to_dict(self) -> dict:
        d = self.body_dict()
        d["kas_domain_tag"] = KAS_DOMAIN_TAG.decode()
        d["commitment"] = self.commitment()
        d["cross_lobe_coherence"] = self.cross_lobe   # advisory readout — NOT in the commitment (see field note)
        d["session_id"] = self.session_id             # U1 join key — metadata, NOT in the commitment
        d["session_display"] = self.session_display
        d["bound_kills"] = self.bound_kills           # WA-R04 middle layer — metadata, NOT in the commitment
        return d


def _hygiene_ok(h: dict, notes: list) -> bool:
    ok = True
    if int(h.get("frame_errs", 0) or 0) > DEFAULT_MAX_FRAME_ERRS:
        notes.append(f"hygiene: frame_errs {h.get('frame_errs')} > {DEFAULT_MAX_FRAME_ERRS}")
        ok = False
    if float(h.get("frame_stall_s", 0.0) or 0.0) > DEFAULT_MAX_FRAME_STALL_S:
        notes.append(f"hygiene: frame_stall_s {h.get('frame_stall_s')} > {DEFAULT_MAX_FRAME_STALL_S}")
        ok = False
    if h.get("ts_source") not in ALLOWED_TS_SOURCES:
        notes.append(f"hygiene: ts_source {h.get('ts_source')!r} not in {ALLOWED_TS_SOURCES}")
        ok = False
    return ok


def build_session_record(*, session_label: str, handle: str, composites, event_trail=None,
                         hygiene: Optional[dict] = None, coupling: Optional[dict] = None,
                         min_kills: int = DEFAULT_MIN_KILLS, events_root: Optional[str] = None,
                         events_root_scheme: Optional[str] = None,
                         events_root_lobes: Optional[list] = None,
                         cross_lobe: Optional[dict] = None,
                         session_id: Optional[str] = None,
                         session_display: Optional[str] = None,
                         bound_kills: Optional[int] = None) -> KillAuthorshipSessionRecord:
    """Fold one session's evidence into a KillAuthorshipSessionRecord. FAIL-CLOSED: malformed inputs ->
    UNVERIFIABLE; dirty capture -> HYGIENE_FAIL (no authorship claim over a dirty capture, regardless of
    kill count); too few authored -> INSUFFICIENT_KILLS. Coupling NEVER gates the verdict (advisory).
    events_root (B2, caller-computed via retina_state_commitment.compute_events_root) binds the outcomes to the
    HID commitment; it rides INTO the commitment (body_dict) but does NOT gate the verdict."""
    notes: list = []
    try:
        # None = MISSING input (unverifiable); [] = a real session that simply had no windows (honest zero).
        comps = None if composites is None else _dedup_composites(list(composites))
    except Exception:
        comps = None
    if comps is None or hygiene is None:
        return KillAuthorshipSessionRecord(
            session_label=str(session_label), handle=str(handle), verdict=UNVERIFIABLE,
            authored_kills=0, authored_scores=[], anchor_tags=[], windows_total=0, composites_total=0,
            own_deaths=0, event_trail=list(event_trail or []), coupling_corroboration=coupling,
            hygiene=dict(hygiene or {}), span_ms=None, min_kills=int(min_kills),
            notes=notes + ["unverifiable: missing composites or hygiene inputs"],
            events_root=events_root, events_root_scheme=events_root_scheme, events_root_lobes=events_root_lobes,
            cross_lobe=cross_lobe, session_id=session_id, session_display=session_display,
            bound_kills=bound_kills)

    authored = [c for c in comps if c.get("verdict") == "AUTHORED_PRESENT"]
    deaths = sum(1 for c in comps if c.get("verdict") == "OWN_DEATH")
    tss = [c.get("ts_ms") for c in comps if isinstance(c.get("ts_ms"), (int, float))]
    span = [min(tss), max(tss)] if tss else None

    h_ok = _hygiene_ok(dict(hygiene), notes)
    if not h_ok:
        verdict = HYGIENE_FAIL
    elif len(authored) >= int(min_kills):
        verdict = AUTHORED_SESSION
    else:
        verdict = INSUFFICIENT_KILLS
        notes.append(f"authored {len(authored)} < min_kills {min_kills}")

    return KillAuthorshipSessionRecord(
        session_label=str(session_label), handle=str(handle), verdict=verdict,
        authored_kills=len(authored),
        authored_scores=[round(float(c.get("composite_score", 0.0)), 4) for c in authored],
        anchor_tags=sorted({str(c.get("anchor")) for c in authored}),
        windows_total=len(comps), composites_total=len(comps), own_deaths=deaths,
        event_trail=list(event_trail or []), coupling_corroboration=coupling,
        hygiene=dict(hygiene), span_ms=span, min_kills=int(min_kills), notes=notes,
        events_root=events_root, events_root_scheme=events_root_scheme, events_root_lobes=events_root_lobes,
        cross_lobe=cross_lobe, session_id=session_id, session_display=session_display,
        bound_kills=bound_kills)
