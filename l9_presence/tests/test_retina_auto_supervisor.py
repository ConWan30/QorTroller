"""Tests for the pure logic in scripts/retina_auto_supervisor.py (the Remote-Play gate decision + the
daemon-stop corpus parse). Process polling + subprocess orchestration are integration-only."""
from __future__ import annotations

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO, "scripts"))

import retina_auto_supervisor as sup  # noqa: E402


def test_decide_start_when_remoteplay_appears():
    assert sup.decide(running=True, capturing=False, idle_elapsed_s=0, idle_grace_s=30) == "start"


def test_decide_none_while_capturing_and_still_running():
    assert sup.decide(running=True, capturing=True, idle_elapsed_s=0, idle_grace_s=30) == "none"


def test_decide_stop_only_after_idle_grace():
    # closed but within grace -> hold (brief alt-tab / restart); past grace -> stop
    assert sup.decide(running=False, capturing=True, idle_elapsed_s=10, idle_grace_s=30) == "none"
    assert sup.decide(running=False, capturing=True, idle_elapsed_s=31, idle_grace_s=30) == "stop"


def test_decide_none_when_idle_and_not_capturing():
    assert sup.decide(running=False, capturing=False, idle_elapsed_s=999, idle_grace_s=30) == "none"


def test_corpus_from_summary_parses_daemon_stop():
    out = ('[daemon] STOPPED + harvested. SUMMARY: {"label": "forged", "rgc_diag_samples": 200, '
           '"calibration_sessions_ge2ch": 60, "corpus": "forged_123.jsonl"}')
    assert sup._corpus_from_summary(out) == "forged_123.jsonl"
    assert sup._corpus_from_summary("no json here") is None
