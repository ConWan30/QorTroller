"""Unit tests for qortroller_memory (extracted persistent-memory module).

Stdlib-only on purpose so this suite runs in CI without bridge deps.
The façade-identity test imports the canonical repo-root qortroller
explicitly (heavy deps are guarded there, so it imports on CI too).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import qortroller_memory as qm


@pytest.fixture
def registry(tmp_path):
    return qm.MethodologyRegistry(path=str(tmp_path / "methodology.json"))


@pytest.fixture
def history(tmp_path):
    return qm.SessionHistory(db_path=str(tmp_path / "sessions.db"))


class TestMethodologyRegistry:
    def test_seeds_present_on_fresh_path(self, registry):
        assert registry.count() == 8
        assert "HALLUCINATED_COMPLETION" in registry.all()

    def test_add_then_query(self, registry):
        assert registry.add("NEW_CLASS", "avoid this", "do that", agent_commit="t")
        assert registry.count() == 9
        assert "NEW_CLASS" in registry.query("avoid this")
        entry = registry.all()["NEW_CLASS"]
        assert entry["anti_pattern"] == "avoid this"
        assert entry["correct_pattern"] == "do that"

    def test_query_empty_keywords_returns_all(self, registry):
        assert registry.query() == registry.all()

    def test_query_for_task_keyword_match(self, registry):
        hits = registry.query_for_task("tune the rate limit burst window")
        assert "RATE_LIMITER_BURST" in hits

    def test_query_for_task_always_includes_core(self, registry):
        hits = registry.query_for_task("completely unrelated text")
        assert "VERBATIM_RELOCATION" in hits
        assert "HALLUCINATED_COMPLETION" in hits

    def test_format_for_prompt(self, registry):
        text = qm.MethodologyRegistry.format_for_prompt(
            {"X": {"anti_pattern": "a" * 300, "correct_pattern": "b",
                   "agent_commit": "c", "discovered": "2026-01-01"}})
        assert "[X]" in text and "AVOID:" in text and "DO:" in text
        assert "a" * 300 not in text  # truncated to 240

    def test_persistence_roundtrip(self, registry, tmp_path):
        registry.add("PERSISTENT", "a", "c", agent_commit="t")
        again = qm.MethodologyRegistry(path=str(tmp_path / "methodology.json"))
        assert "PERSISTENT" in again.all()


class TestSessionHistory:
    def test_session_created(self, history):
        assert len(history.session_id) == 12

    def test_message_roundtrip(self, history):
        history.add_message("user", "hello")
        history.add_message("assistant", "hi", tool_calls=[{"name": "x"}])
        msgs = history.get_recent_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"

    def test_decision_roundtrip(self, history):
        history.add_decision("title", "decision", "context")
        assert len(history.get_decisions()) == 1
        assert len(history.get_all_decisions()) == 1

    def test_end_session_summary_excludes_current(self, history, tmp_path):
        history.end_session("wrap-up")
        # get_last_session_summary is cross-session continuity: it deliberately
        # excludes the CURRENT session, so a fresh SessionHistory on the same
        # db sees the ended one (as a dict, not a bare string).
        nxt = qm.SessionHistory(db_path=str(tmp_path / "sessions.db"))
        row = nxt.get_last_session_summary()
        assert row is not None and row["summary"] == "wrap-up"

    def test_all_sessions_lists_session(self, history):
        sessions = history.get_all_sessions()
        assert any(s["id"] == history.session_id for s in sessions)


def test_facade_identity():
    # Import the CANONICAL repo-root qortroller, not the lighter
    # scripts/qortroller.py CLI variant. Earlier test modules (e.g.
    # test_cfss_lane_drift_sweep) prepend other source dirs to sys.path,
    # which otherwise shadows root modules by name (found via CI failure:
    # 'module qortroller has no attribute MethodologyRegistry').
    import importlib
    import sys

    root = str(Path(__file__).resolve().parents[2])
    saved_path = sys.path[:]
    sys.path.insert(0, root)
    try:
        sys.modules.pop("qortroller", None)
        qortroller = importlib.import_module("qortroller")
        assert str(Path(qortroller.__file__).resolve()) == str(
            Path(root, "qortroller.py").resolve()
        ), f"imported {qortroller.__file__}, expected repo-root qortroller.py"
        assert qortroller.MethodologyRegistry is qm.MethodologyRegistry
        assert qortroller.SessionHistory is qm.SessionHistory
    finally:
        sys.path[:] = saved_path
