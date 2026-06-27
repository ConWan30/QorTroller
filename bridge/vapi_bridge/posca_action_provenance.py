"""
PoVCA (Proof of Verified Causal Authorship) — Cycle 42 minimal slice.
Action detector + binder + structure scorer + recomputable commitment.

Reuses existing QorTroller primitives for seamless interoperability:
- ScreenEvent / is_input_caused from retina_screen_lobe (discrete game-actions: down_advanced, score, ...)
- assess_coherence / TimedEvent / from_screen_events from retina_causal_coherence (L9/PoCP binder)
- input event types (controller.trigger.onset, controller.stick.radial_jump)
- L4 structure check via the existing L4 anomaly threshold (Mahalanobis distance), NOT a skill rank.

Honesty rails (cycle-42 + integration critiques — ENFORCED IN CODE, not just prose):
- structure_ok is TRI-STATE (Optional[bool]): True = L4 evidence + human-structured; False = L4 evidence +
  anomalous; None = ABSTAIN (no L4 evidence). It NEVER returns True without evidence — that would
  manufacture an authorship claim and is the GCAP human-TAR-collapse trap in reverse. "authorship +
  causal structure", never "skill rank".
- Emulated/non-real device -> UNVERIFIABLE (it is the translator cheat vector; only valid as a labeled
  red-team harness, never registered).
- Advisory only. Composes into NQPV as an oracle FIELD; it does NOT influence the certified presence_score
  until a measured RETINA-EXCL-2 study sets a weight under the anti-GCAP rail.
- Per-action binding via existing coherence; recomputable commitment (deterministic byte encoding).

Default-off. No FROZEN PoAC / 228B touch. Live discrete path is dormant until screen_events/input_events
are co-captured live (the capture-rate fix) — until then detect_author_actions returns [] and posca abstains.
"""

from __future__ import annotations

import hashlib
import struct
from typing import Optional

from .retina_causal_coherence import assess_coherence, from_screen_events, TimedEvent
from .retina_screen_lobe import ScreenEvent, is_input_caused

# Reuse existing input event types (controller-side authoring inputs).
INPUT_EVENT_TYPES = frozenset({"controller.trigger.onset", "controller.stick.radial_jump"})

DEFAULT_ACTION_WINDOW_S = 8.0   # play + settle; matches the coherence window in practice
L4_ANOMALY_THRESHOLD = 7.009    # CLAUDE.md L4 anomaly threshold (mean+3σ); dist < thr => human-structured
COUPLING_MIN = 0.2              # min L9/coherence coupling for an AUTHENTIC verdict (provisional; study sets it)


def _check_structure_ok(input_events: list[TimedEvent], l4_features: Optional[dict] = None) -> Optional[bool]:
    """Tri-state structure check on the authoring inputs. NEVER fails open.

    Returns:
      True  -> L4 evidence present AND human-structured (Mahalanobis distance < L4_ANOMALY_THRESHOLD).
      False -> L4 evidence present AND anomalous (>= threshold): NOT human-structured (macro/translator/blind).
      None  -> ABSTAIN: no authoring input, or no usable L4 evidence to judge. The honest default —
               authorship is NEVER asserted without evidence.

    This is structural plausibility (human vs macro), NOT a skill rank (avoids GCAP human-TAR collapse).
    """
    if not input_events:
        return None  # no authoring input in the window -> cannot assess structure -> abstain
    if not l4_features:
        return None  # no L4 evidence -> abstain (do NOT default True; that manufactured authorship)
    dist = l4_features.get("l4_distance")
    if dist is None:
        dist = l4_features.get("distance")
    if not isinstance(dist, (int, float)):
        return None  # malformed/absent distance -> abstain
    return bool(dist < L4_ANOMALY_THRESHOLD)


def detect_author_actions(
    screen_events: list[ScreenEvent],
    input_events: list[TimedEvent],
    window_s: float = DEFAULT_ACTION_WINDOW_S,
    l4_features: Optional[dict] = None,
    device_id: str = "",
    poac_record_hash: str = "",
) -> list[dict]:
    """Detector + binder: find input-caused game-actions and bind them to authoring inputs + structure.

    Reuses assess_coherence (the L9 causal binder) + is_input_caused + the tri-state structure check.
    Each returned action carries a tri-state ``structure_ok`` (may be None = abstain) and, when
    device_id + poac_record_hash are supplied, a recomputable ``commitment``.
    """
    if not screen_events or not input_events:
        return []

    coh_events = input_events + from_screen_events(screen_events)
    report = assess_coherence(coh_events)
    coupling = report.coherence_ratio()

    actions: list[dict] = []
    for match in report.matches:
        if match.matched and is_input_caused(match.outcome.type):
            t = match.outcome.t
            win_inputs = [
                e for e in input_events
                if abs(e.t - t) < window_s and e.type in INPUT_EVENT_TYPES
            ]
            action = {
                "type": match.outcome.type,
                "t": t,
                "structure_ok": _check_structure_ok(win_inputs, l4_features),  # tri-state (may be None)
                "coupling": coupling,
                "n_inputs_in_window": len(win_inputs),
            }
            action["commitment"] = (
                compute_posca_commitment(device_id, action, poac_record_hash, coupling)
                if device_id and poac_record_hash else ""
            )
            actions.append(action)
    return actions


def compute_posca_commitment(
    device_id: str,
    action: dict,
    poac_record_hash: str,
    coupling: Optional[float] = None,
) -> str:
    """Recomputable PoVCA commitment. Deterministic byte encoding (no float repr, no ambiguous joins).

    pre = b"QOR-POVCA-v1" || device_id || US || action_type || US || f64(t) || i32(n_inputs)
          || f64(coupling) || structure_byte || poac_record_hash
    structure_byte: 0x01 True / 0x00 False / 0x02 abstain(None).
    """
    structure_ok = action.get("structure_ok")
    structure_byte = b"\x01" if structure_ok is True else (b"\x00" if structure_ok is False else b"\x02")
    pre = (
        b"QOR-POVCA-v1"
        + device_id.encode("utf-8", "ignore") + b"\x1f"
        + str(action.get("type", "")).encode("utf-8", "ignore") + b"\x1f"
        + struct.pack(">d", float(action.get("t", 0.0) or 0.0))
        + struct.pack(">i", int(action.get("n_inputs_in_window", 0) or 0))
        + struct.pack(">d", float(coupling or 0.0))
        + structure_byte
        + poac_record_hash.encode("utf-8", "ignore")
    )
    return hashlib.sha256(pre).hexdigest()


def is_emulated_or_non_real(cco_tier: Optional[str]) -> bool:
    """Emulated gate: only real, CCO-classified devices may author. Absent/FAIL/EMULATED/VIRTUAL -> emulated."""
    if not cco_tier:
        return True
    t = str(cco_tier).upper()
    return "FAIL" in t or "EMULATED" in t or "VIRTUAL" in t


def posca_verdict_from(
    structure_ok: Optional[bool],
    coupling: Optional[float],
    cco_tier: Optional[str],
) -> str:
    """Single source of truth for the advisory PoVCA verdict (honors the tri-state + emulated gate).

    UNVERIFIABLE   -> emulated/non-real device, OR no structure evidence (abstain). Never claims authentic
                      without evidence.
    AUTHENTIC      -> human-structured authoring input AND sufficient causal coupling.
    ORPHAN_OR_WEAK -> structured-but-weakly-coupled, or structurally anomalous (advisory 'not a clean author').
    """
    if is_emulated_or_non_real(cco_tier):
        return "UNVERIFIABLE"
    if structure_ok is None:
        return "UNVERIFIABLE"  # abstain — no L4 evidence
    if structure_ok and (coupling or 0.0) >= COUPLING_MIN:
        return "AUTHENTIC"
    return "ORPHAN_OR_WEAK"
