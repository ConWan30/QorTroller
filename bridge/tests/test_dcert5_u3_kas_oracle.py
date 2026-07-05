"""D-CERT-5 Increment U3 — KAS joins FusedGamerPresenceProof as a declared oracle (option a).

Per docs/d-cert5-unified-presence-design-2026-07-04.md §8: fuse() gains optional KAS inputs
(verdict, commitment, events_root, authored_kills); active_oracles gains a "kas" entry; the KAS
commitment joins the commitments dict. Mirrors bridge/tests/test_dcert1_active_oracles.py's shape
(that file is the template named in the roadmap's own Verify step) but is its own file since KAS is
a new finding, not an amendment to D-CERT-1's closed scope.

KAS is advisory-only (like PoVCA): "contributed" means "declared a real per-session outcome", NOT
"moved presence_score" — kill_authorship_session.py's AUTHORED_SESSION / INSUFFICIENT_KILLS /
HYGIENE_FAIL are all honest per-session results (never a failure to produce a reading), so all three
count as contributed; only UNVERIFIABLE (malformed/empty inputs, never guessed) is abstained.
kas_report=None (mid-session; KAS issues post-hoc at daemon stop) is absent.
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


def _kas(verdict, authored_kills=0, events_root=None, commitment=None):
    return SimpleNamespace(verdict=verdict, authored_kills=authored_kills,
                           events_root=events_root, commitment=commitment)


def test_kas_absent_mid_session():
    # the doc's own validation clause: "mid-session proof shows kas: absent" — no kas_report passed.
    p = _fuse(poep_present=True)
    assert p.active_oracles["kas"] == "absent"
    assert p.kas_verdict is None and p.kas_commitment is None
    assert p.kas_events_root is None and p.kas_authored_kills is None
    assert "kas" not in p.commitments


def test_kas_contributed_post_stop_authored_session():
    # the doc's own validation clause: "post-stop re-issue shows contributed"
    kas = _kas("AUTHORED_SESSION", authored_kills=15, events_root="ab" * 32, commitment="deadbeef" * 8)
    p = _fuse(poep_present=True, kas_report=kas)
    assert p.active_oracles["kas"] == "contributed"
    assert p.kas_verdict == "AUTHORED_SESSION"
    assert p.kas_authored_kills == 15
    assert p.kas_events_root == "ab" * 32
    assert p.commitments["kas"] == "deadbeef" * 8


def test_kas_insufficient_kills_is_contributed_not_a_failure():
    # kill_authorship_session.py: "hygiene clean but too few authored composites -- honest, not a failure"
    kas = _kas("INSUFFICIENT_KILLS", authored_kills=1)
    p = _fuse(kas_report=kas)
    assert p.active_oracles["kas"] == "contributed"
    assert p.kas_verdict == "INSUFFICIENT_KILLS"


def test_kas_hygiene_fail_is_contributed_not_a_failure():
    # a dirty-capture result is still an informative, real outcome -- not "no usable signal"
    kas = _kas("HYGIENE_FAIL", authored_kills=0)
    p = _fuse(kas_report=kas)
    assert p.active_oracles["kas"] == "contributed"
    assert p.kas_verdict == "HYGIENE_FAIL"


def test_kas_unverifiable_is_abstained():
    # UNVERIFIABLE = malformed/empty inputs, never guessed -- consulted, no usable signal
    kas = _kas("UNVERIFIABLE", authored_kills=0)
    p = _fuse(kas_report=kas)
    assert p.active_oracles["kas"] == "abstained"


def test_kas_never_moves_presence_score():
    # advisory-only, like PoVCA: identical inputs except kas_report must yield identical presence_score
    base_kw = dict(retina_report=SimpleNamespace(verdict="COUPLED_CLEAN"), poep_present=True, l4_l5_l6_ok=True)
    without_kas = _fuse(**base_kw)
    with_kas = _fuse(**base_kw, kas_report=_kas("AUTHORED_SESSION", authored_kills=20))
    assert without_kas.presence_score == with_kas.presence_score
    assert without_kas.disagreement_index == with_kas.disagreement_index
    assert without_kas.verdict == with_kas.verdict


def test_manifest_never_disagrees_with_kas_fields():
    # the doc's own validation clause: "manifest never disagrees with inputs"
    absent = _fuse()
    assert absent.active_oracles["kas"] == "absent" and absent.kas_verdict is None
    contributed = _fuse(kas_report=_kas("AUTHORED_SESSION", authored_kills=5))
    assert contributed.active_oracles["kas"] == "contributed" and contributed.kas_verdict is not None
    abstained = _fuse(kas_report=_kas("UNVERIFIABLE"))
    assert abstained.active_oracles["kas"] == "abstained" and abstained.kas_verdict == "UNVERIFIABLE"


def test_null_safe_backward_compat():
    old = FusedGamerPresenceProof(verdict=None, device_id="d", record_hash="r")  # pre-U3 record
    assert old.kas_verdict is None and old.kas_commitment is None
    assert old.kas_events_root is None and old.kas_authored_kills is None


def test_oracle_manifest_pure_helper_kas_cases():
    # _oracle_manifest is the pure helper both fuse() and this test drive directly (D-CERT-1 template)
    assert _oracle_manifest(None, None, None, None, None, None)["kas"] == "absent"
    assert _oracle_manifest(None, None, None, None, None, None,
                            kas_report=object(), kas_verdict="AUTHORED_SESSION")["kas"] == "contributed"
    assert _oracle_manifest(None, None, None, None, None, None,
                            kas_report=object(), kas_verdict="UNVERIFIABLE")["kas"] == "abstained"
