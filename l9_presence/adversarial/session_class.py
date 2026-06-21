"""Class taxonomy + labeled-session data model for the consistency experiment.

The five classes are the doc's section-5 capture matrix. A LabeledWindow carries
the per-window oracle INPUTS (presence reaction features, retina trajectory state,
L4 distance) plus its ground-truth class and provenance. The harness converts
these to typed signals (signal_adapter) and runs the fusion engine over them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SessionClass(str, Enum):
    HUMAN_CLEAN = "HUMAN_CLEAN"            # genuine play -> expect CONSISTENT_HUMAN
    BOT_FULL = "BOT_FULL"                  # scripted, no human -> no presence
    HUMAN_AIM_ASSIST = "HUMAN_AIM_ASSIST"  # live human + machine-corrected trajectory (the catch)
    HUMAN_RELAY = "HUMAN_RELAY"            # human passes challenges, bot plays between
    PRO_SKILL = "PRO_SKILL"               # elite human, fast-but-genuine (the false-positive risk)


class Provenance(str, Enum):
    SYNTHETIC = "synthetic"   # parameterised model of oracle behaviour -- provisional
    REAL = "real"             # real co-capture (Phase 2 only)


@dataclass(frozen=True)
class LabeledWindow:
    """One cognition-window's ground-truth oracle inputs for the experiment.

    presence_reacted / presence_in_band / device_auth_pass feed classify_presence
    (via a poep_verify-shaped dict). retina_anomaly_count feeds classify_trajectory.
    l4_distance is the optional third oracle. session_id binds the triple.
    """
    session_id: str
    ts_ns: int
    presence_challenged: bool   # was a presence challenge issued+bound to this window?
    presence_reacted: bool
    presence_in_band: bool
    device_auth_pass: bool
    retina_anomaly_count: int
    l4_distance: Optional[float]
    # ground truth + provenance
    class_label: SessionClass = SessionClass.HUMAN_CLEAN
    provenance: Provenance = Provenance.SYNTHETIC
    # PRO_SKILL synthetic is the weakest proxy -- carried so the report can flag it.
    provisional: bool = True


@dataclass(frozen=True)
class LabeledSession:
    session_id: str
    class_label: SessionClass
    provenance: Provenance
    windows: list = field(default_factory=list)  # list[LabeledWindow]
    provisional: bool = True
