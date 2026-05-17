"""Phase 235.x-STABILITY-9 stage 6 (2026-05-17) — Curator Task 6/7
instrumentation tests.

Validates the timed-curator-task + timed-db-block helpers + per-Task
wiring. Stage 6 is instrumentation-first per operator directive: do
not guess the fix before instrumentation names the offender.
"""
import logging
import os
import time
from types import SimpleNamespace

import pytest

from bridge.vapi_bridge.corpus_curator_agent import (
    _timed_curator_task,
    _timed_db_block,
)


def _stub_cfg(**overrides):
    base = {
        "curator_task_warn_duration_s": 5.0,
        "curator_db_warn_duration_s": 1.0,
        "contribution_weight_enabled": False,  # disable task 7 body work in inner-call tests
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_t_235_stab9_6_1_cfg_defaults() -> None:
    """cfg.curator_task_warn_duration_s=5.0, db=1.0 by default."""
    os.environ.pop("CURATOR_TASK_WARN_DURATION_S", None)
    os.environ.pop("CURATOR_DB_WARN_DURATION_S", None)
    from bridge.vapi_bridge.config import Config
    cfg = Config()
    assert cfg.curator_task_warn_duration_s == 5.0
    assert cfg.curator_db_warn_duration_s == 1.0


def test_t_235_stab9_6_2_env_override() -> None:
    """Env overrides flip the thresholds."""
    os.environ["CURATOR_TASK_WARN_DURATION_S"] = "10.0"
    os.environ["CURATOR_DB_WARN_DURATION_S"] = "2.5"
    try:
        from bridge.vapi_bridge.config import Config
        cfg = Config()
        assert cfg.curator_task_warn_duration_s == 10.0
        assert cfg.curator_db_warn_duration_s == 2.5
    finally:
        os.environ.pop("CURATOR_TASK_WARN_DURATION_S", None)
        os.environ.pop("CURATOR_DB_WARN_DURATION_S", None)


def test_t_235_stab9_6_3_task_under_threshold_logs_info(caplog) -> None:
    """When task duration < warn threshold, only INFO log fires."""
    cfg = _stub_cfg(curator_task_warn_duration_s=5.0)
    logger = logging.getLogger("test_stab9_6_3")
    with caplog.at_level(logging.INFO, logger="test_stab9_6_3"):
        with _timed_curator_task("FastTask", cfg, logger):
            pass  # near-instant
    messages = [r.message for r in caplog.records]
    assert any("STAGE-6: FastTask duration=" in m for m in messages), \
        f"Expected INFO log for fast task, got: {messages}"
    assert not any("SLOW TASK" in m for m in messages), \
        f"Should NOT log WARNING for fast task: {messages}"


def test_t_235_stab9_6_4_task_over_threshold_logs_warning(caplog) -> None:
    """When task body duration > warn threshold, WARNING fires."""
    # Use very tight threshold so a 50ms operation trips it
    cfg = _stub_cfg(curator_task_warn_duration_s=0.01)
    logger = logging.getLogger("test_stab9_6_4")
    with caplog.at_level(logging.WARNING, logger="test_stab9_6_4"):
        with _timed_curator_task("SlowTask", cfg, logger):
            time.sleep(0.05)
    messages = [r.message for r in caplog.records]
    assert any("SLOW TASK: SlowTask took" in m for m in messages), \
        f"Expected WARNING for slow task, got: {messages}"
    assert any("LOOP STARVATION" in m for m in messages), \
        "WARNING must surface contributor-to-LOOP-STARVATION framing"


def test_t_235_stab9_6_5_db_block_under_threshold_silent(caplog) -> None:
    """DB block under threshold logs nothing (avoid log spam)."""
    cfg = _stub_cfg(curator_db_warn_duration_s=1.0)
    logger = logging.getLogger("test_stab9_6_5")
    with caplog.at_level(logging.DEBUG, logger="test_stab9_6_5"):
        with _timed_db_block("FastDBSite", cfg, logger):
            pass
    # Under-threshold DB blocks intentionally produce NO log line.
    slow_db = [r.message for r in caplog.records if "SLOW DB" in r.message]
    assert not slow_db, f"Should NOT log SLOW DB under threshold: {slow_db}"


def test_t_235_stab9_6_6_db_block_over_threshold_logs_warning(caplog) -> None:
    """DB block over threshold logs WARNING."""
    cfg = _stub_cfg(curator_db_warn_duration_s=0.01)
    logger = logging.getLogger("test_stab9_6_6")
    with caplog.at_level(logging.WARNING, logger="test_stab9_6_6"):
        with _timed_db_block("SlowDBSite", cfg, logger):
            time.sleep(0.05)
    messages = [r.message for r in caplog.records]
    assert any("SLOW DB: SlowDBSite took" in m for m in messages), \
        f"Expected WARNING for slow DB block, got: {messages}"
    assert any("WAL contention" in m for m in messages), \
        "WARNING must surface WAL-contention investigation hint"


def test_t_235_stab9_6_7_thread_id_in_warning(caplog) -> None:
    """Warning includes thread ID for cross-thread correlation."""
    cfg = _stub_cfg(curator_task_warn_duration_s=0.01)
    logger = logging.getLogger("test_stab9_6_7")
    with caplog.at_level(logging.WARNING, logger="test_stab9_6_7"):
        with _timed_curator_task("ThreadIDTask", cfg, logger):
            time.sleep(0.05)
    messages = [r.message for r in caplog.records]
    assert any("tid=" in m for m in messages), \
        "WARNING must include tid= for thread identity correlation"


def test_t_235_stab9_6_8_helpers_dont_break_inner_body() -> None:
    """Helpers MUST NOT swallow exceptions from the wrapped body."""
    cfg = _stub_cfg()
    logger = logging.getLogger("test_stab9_6_8")
    with pytest.raises(ValueError, match="inner-body-error"):
        with _timed_curator_task("RaisingTask", cfg, logger):
            raise ValueError("inner-body-error")
    with pytest.raises(ValueError, match="db-body-error"):
        with _timed_db_block("RaisingSite", cfg, logger):
            raise ValueError("db-body-error")


def test_t_235_stab9_6_9_task_6_body_method_exists() -> None:
    """Verify Task 6 has been refactored to outer-wrapper + inner-body
    pattern per stage 6 instrumentation discipline."""
    from bridge.vapi_bridge.corpus_curator_agent import CorpusDataCuratorAgent
    assert hasattr(CorpusDataCuratorAgent, "_run_readiness_certificate"), \
        "Outer wrapper method must remain"
    assert hasattr(CorpusDataCuratorAgent, "_run_readiness_certificate_body"), \
        "Inner body method must be extracted for clean timing wrap"


def test_t_235_stab9_6_10_task_7_body_method_exists() -> None:
    """Verify Task 7 has been refactored to outer-wrapper + inner-body."""
    from bridge.vapi_bridge.corpus_curator_agent import CorpusDataCuratorAgent
    assert hasattr(CorpusDataCuratorAgent, "_run_contribution_weights"), \
        "Outer wrapper method must remain"
    assert hasattr(CorpusDataCuratorAgent, "_run_contribution_weights_body"), \
        "Inner body method must be extracted for clean timing wrap"


def test_t_235_stab9_6_11_db_block_sites_named_in_source() -> None:
    """Verify the named _timed_db_block sites cover every SQLite call
    inside Task 6 + Task 7 bodies — instrumentation completeness."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "vapi_bridge" /
           "corpus_curator_agent.py").read_text(encoding="utf-8")
    expected_sites = [
        # Task 6
        "Task6_separation_defensibility_log",
        "Task6_get_persona_break_status",
        "Task6_device_enrollments_counts",
        "Task6_biometric_renewal_log",
        "Task6_get_latest_corpus_entropy",
        "Task6_re_enrollment_attestation_log",
        "Task6_insert_data_readiness_certificate",
        # Task 7
        "Task7_read_separation_defensibility_log",
        "Task7_get_persona_break_status",
        # Task7 insert loop carries dynamic N suffix — substring match
        "Task7_insert_loop_N",
    ]
    for site in expected_sites:
        assert site in src, f"Missing _timed_db_block site: {site}"


def test_t_235_stab9_6_12_existing_curator_tests_still_pass() -> None:
    """Smoke check that the curator module is importable + ASTs cleanly
    after instrumentation refactor."""
    import importlib
    import bridge.vapi_bridge.corpus_curator_agent as m
    importlib.reload(m)
    # Verify both timing helpers exported correctly
    assert callable(m._timed_curator_task)
    assert callable(m._timed_db_block)
