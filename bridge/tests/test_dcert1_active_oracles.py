"""D-CERT-1 Phase 1a — active-oracles manifest (cycle-59).

Records per-oracle OUTCOME (contributed / abstained / absent / abstained_or_absent) so two verdicts
resting on DIFFERENT evidence sets are distinguishable (closes F-CERT-005 comparability, incl. the
same-set-different-abstention variant). Derived inside fuse() from the same checks it scores -> the
manifest cannot disagree with the verdict. Null-safe; never inferred retroactively.

Phase-1a FINDING (surfaced, not papered over): poep + l4l5l6 are Optional[bool] inputs, so their
non-contributed state cannot distinguish abstained from absent -> honestly "abstained_or_absent".
retina + cco (report-object inputs) get the full 3-way distinction.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "bridge")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vapi_bridge.novel_presence_fusion import (
    NovelPresenceFusionOrchestrator,
    FusedGamerPresenceProof,
    _oracle_manifest,
)


def _fuse(**kw):
    base = dict(device_id="d", record_hash="r")
    base.update(kw)
    return NovelPresenceFusionOrchestrator().fuse(**base)


def test_all_present_all_contributed():
    p = _fuse(retina_report=SimpleNamespace(verdict="COUPLED_CLEAN"),
              cco_report=SimpleNamespace(tier="PREMIUM_EDGE"), poep_present=True, l4_l5_l6_ok=True)
    # D-CERT-5 U3: kas joins the manifest as a 5th declared oracle; absent here (no kas_report passed).
    assert p.active_oracles == {"retina": "contributed", "cco": "contributed",
                                "poep": "contributed", "l4l5l6": "contributed", "kas": "absent"}


def test_retina_absent_vs_abstained_are_distinct():
    # the subtler F-CERT-005: not-wired (absent) is DIFFERENT evidence from consulted-and-abstained
    absent = _fuse(retina_report=None, poep_present=True).active_oracles["retina"]
    abstained = _fuse(retina_report=SimpleNamespace(verdict="INACTIVE"),
                      poep_present=True).active_oracles["retina"]
    assert absent == "absent" and abstained == "abstained" and absent != abstained


def test_cco_three_way():
    assert _fuse(cco_report=None, poep_present=True).active_oracles["cco"] == "absent"
    assert _fuse(cco_report=SimpleNamespace(tier=None), poep_present=True).active_oracles["cco"] == "abstained"
    assert _fuse(cco_report=SimpleNamespace(tier="MID_TIER"), poep_present=True).active_oracles["cco"] == "contributed"


def test_poep_l4l5l6_conflation_is_honest():
    # Optional[bool] inputs -> non-contributed state honestly NAMES the conflation (the Phase-1a finding)
    p = _fuse(poep_present=None, l4_l5_l6_ok=None, retina_report=SimpleNamespace(verdict="COUPLED_CLEAN"))
    assert p.active_oracles["poep"] == "abstained_or_absent"
    assert p.active_oracles["l4l5l6"] == "abstained_or_absent"
    p2 = _fuse(poep_present=False, l4_l5_l6_ok=True)     # a present bool (even False) is contributed
    assert p2.active_oracles["poep"] == "contributed" and p2.active_oracles["l4l5l6"] == "contributed"


def test_manifest_cannot_disagree_with_score():
    # the contributed set == the oracles that actually moved presence_score
    p = _fuse(retina_report=SimpleNamespace(verdict="PLAUSIBLE"), cco_report=None,
              poep_present=True, l4_l5_l6_ok=None)
    contributed = {k for k, v in p.active_oracles.items() if v == "contributed"}
    assert contributed == {"retina", "poep"}            # cco absent, l4l5l6 conflated -> not contributed


def test_manifest_recorded_on_hard_gate_path():
    # cco FAIL is a hard gate -> the manifest is still recorded, and cco reads contributed (it drove it)
    p = _fuse(cco_report=SimpleNamespace(tier="FAIL"), poep_present=True)
    assert p.verdict.value == "HARDWARE_CLASS_FAIL"
    assert p.active_oracles is not None and p.active_oracles["cco"] == "contributed"


def test_null_safe_backward_compat():
    p = NovelPresenceFusionOrchestrator().fuse(device_id="", record_hash="")   # abstain path
    assert p.active_oracles is None
    old = FusedGamerPresenceProof(verdict=None, device_id="d", record_hash="r")  # pre-cycle-59
    assert old.active_oracles is None


def test_oracle_manifest_pure_helper():
    m = _oracle_manifest(None, None, None, None, None, None)                     # nothing wired
    # D-CERT-5 U3: kas_report/kas_verdict default to None -> "absent", same as every other unwired oracle.
    assert m == {"retina": "absent", "cco": "absent",
                 "poep": "abstained_or_absent", "l4l5l6": "abstained_or_absent", "kas": "absent"}
