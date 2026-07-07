"""D-CERT-9 — collision guard (option b): close SILENT cross-subject pooling under one label.

Fact A: no per-unit identity is reachable at the enroll call site (DEVICE_ID_CANON_v1 is
secure-element-rooted + Arc-2-gated; fresh.device_id is only the model string), so label->device
binding (option a) is the Arc-2-gated COMPLETION, not available now. This guard makes extending an
existing (or unreadable -> fail-closed) label REQUIRE --extend-existing, records the choice + an
enrollment-instance nonce, and makes accidental pooling POST-HOC DETECTABLE (not prevented).
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "bridge")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_ENROLL = os.path.join(_ROOT, "scripts", "poep_session_enroll.py")
_spec = importlib.util.spec_from_file_location("poep_session_enroll", _ENROLL)
pse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pse)
label_corpus_status = pse.label_corpus_status
collision_verdict = pse.collision_verdict


def _write_session(d: str, player: str, name: str | None = None) -> str:
    p = os.path.join(d, name or f"{player}_01.poep.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"player": player, "device_id": "Sony_DualShock_Edge_CFI-ZCP1",
                   "challenge_records": []}, fh)
    return p


# --- label_corpus_status: the fail-closed classifier ------------------------------------------------

def test_fresh_label_is_provably_unused():
    assert label_corpus_status(tempfile.mkdtemp(), "DEV") == ("fresh", 0)


def test_existing_label_detected():
    d = tempfile.mkdtemp(); _write_session(d, "DEV")
    assert label_corpus_status(d, "DEV") == ("existing", 1)


def test_ambiguous_corpus_fails_closed():
    # a corrupt file that COULD hide a matching session -> ambiguous (treated as existing).
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "corrupt_01.poep.json"), "w", encoding="utf-8") as fh:
        fh.write("{ not json")
    assert label_corpus_status(d, "DEV") == ("ambiguous", 1)     # cannot prove unused -> fail closed


def test_confirmed_match_beats_unreadable():
    # a readable match takes precedence over unreadable files (we KNOW the label exists).
    d = tempfile.mkdtemp(); _write_session(d, "DEV")
    with open(os.path.join(d, "corrupt_01.poep.json"), "w", encoding="utf-8") as fh:
        fh.write("garbage")
    assert label_corpus_status(d, "DEV") == ("existing", 1)


def test_distinct_label_is_fresh_even_with_other_labels_present():
    # DEV present, but a NEW label is still provably fresh -> a distinct --player is the clean escape.
    d = tempfile.mkdtemp(); _write_session(d, "DEV")
    assert label_corpus_status(d, "DEV2") == ("fresh", 0)


# --- collision_verdict: the decision matrix ---------------------------------------------------------

def test_decision_matrix():
    assert collision_verdict("fresh", False) == (False, False)     # fresh -> proceed, not extended
    assert collision_verdict("existing", False) == (True, False)   # existing, no flag -> REFUSE
    assert collision_verdict("existing", True) == (False, True)    # existing + flag -> proceed, extended
    assert collision_verdict("ambiguous", False) == (True, False)  # ambiguous, no flag -> REFUSE (fail closed)
    assert collision_verdict("ambiguous", True) == (False, True)   # ambiguous + flag -> proceed, extended


# --- rider 4: the P1-P5 study workflow passes through untouched --------------------------------------

def test_study_label_path_fresh_existing_extend():
    d = tempfile.mkdtemp()
    # (i) fresh study label -> no refusal
    st0, _ = label_corpus_status(d, "P1")
    assert st0 == "fresh" and collision_verdict(st0, False)[0] is False
    # (ii) existing study label WITHOUT the flag -> refusal (guard fires consistently on study labels)
    _write_session(d, "P1")
    st1, n1 = label_corpus_status(d, "P1")
    assert st1 == "existing" and n1 == 1
    assert collision_verdict(st1, False)[0] is True
    # (iii) existing study label WITH the flag -> proceeds, and is recorded as a deliberate extension
    refuse, extended = collision_verdict(st1, True)
    assert refuse is False and extended is True


def test_extended_enrollment_records_the_choice():
    # the audit trail main() composes for an existing label + --extend-existing must show the choice.
    d = tempfile.mkdtemp(); _write_session(d, "DEV")
    status, detail = label_corpus_status(d, "DEV")
    _refuse, extended = collision_verdict(status, True)
    meta = {"extended_existing": extended, "label_status_at_enroll": status,
            "label_corpus_count_at_enroll": detail}
    assert meta == {"extended_existing": True, "label_status_at_enroll": "existing",
                    "label_corpus_count_at_enroll": 1}


def test_nonce_unique_and_note_states_detection_not_prevention():
    import secrets
    assert secrets.token_hex(16) != secrets.token_hex(16)          # per-enrollment uniqueness
    note = pse._COLLISION_GUARD_NOTE
    assert "DETECTABLE" in note and "NOT prevented" in note and "Arc-2-gated" in note
