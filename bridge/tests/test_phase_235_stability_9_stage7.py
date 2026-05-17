"""Phase 235.x-STABILITY-9 stage 7 (2026-05-17) — First-fire cohort
instrumentation tests.

Validates the shared `loop_timing.timed_block` primitive + Stage 7
instrumentation sites (AgentCalibrationMonitor, ProtocolIntelligenceAgent,
AbsorbedAgentTicker). Stage 7 is instrumentation-only — no fix yet —
per operator directive 2026-05-17.
"""
import logging
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge.vapi_bridge.loop_timing import timed_block


_BRIDGE_DIR = Path(__file__).resolve().parents[1] / "vapi_bridge"


def _stub_cfg(**overrides):
    base = {
        "acim_run_warn_duration_s": 5.0,
        "acim_subtest_warn_duration_s": 1.0,
        "protocol_intel_compute_warn_duration_s": 2.0,
        "absorbed_ticker_outer_warn_duration_s": 2.0,
        "absorbed_ticker_per_spec_warn_duration_s": 1.0,
        "curator_task_warn_duration_s": 5.0,
        "curator_db_warn_duration_s": 1.0,
        "startup_jitter_enabled": False,
        "startup_jitter_max_s": 0.0,
        "startup_jitter_seed": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


# ─── Shared helper tests ──────────────────────────────────────────────────


def test_t_235_stab9_7_1_helper_info_default_silent_under(caplog) -> None:
    """always_info=False (default) → silent under threshold."""
    logger = logging.getLogger("test_stab9_7_1")
    with caplog.at_level(logging.DEBUG, logger="test_stab9_7_1"):
        with timed_block("FastSite", warn_s=1.0, logger=logger):
            pass
    msgs = [r.message for r in caplog.records]
    assert not msgs, f"silent-mode helper should not log under threshold: {msgs}"


def test_t_235_stab9_7_2_helper_info_when_always_info(caplog) -> None:
    """always_info=True → INFO line on every exit."""
    logger = logging.getLogger("test_stab9_7_2")
    with caplog.at_level(logging.INFO, logger="test_stab9_7_2"):
        with timed_block("FastSite", warn_s=1.0, logger=logger,
                         always_info=True, prefix="[TestAgent] STAGE-7"):
            pass
    msgs = [r.message for r in caplog.records]
    assert any("STAGE-7" in m for m in msgs)
    assert any("FastSite duration=" in m for m in msgs)


def test_t_235_stab9_7_3_helper_warning_over_threshold(caplog) -> None:
    """duration > warn_s → WARNING with slow_word + hint."""
    logger = logging.getLogger("test_stab9_7_3")
    with caplog.at_level(logging.WARNING, logger="test_stab9_7_3"):
        with timed_block(
            "SlowSite",
            warn_s=0.01,
            logger=logger,
            prefix="[TestAgent] STAGE-7",
            slow_word="SLOW CYCLE",
            hint="test investigation hint",
        ):
            time.sleep(0.05)
    msgs = [r.message for r in caplog.records]
    assert any("SLOW CYCLE: SlowSite took" in m for m in msgs)
    assert any("test investigation hint" in m for m in msgs)
    assert any("tid=" in m for m in msgs)
    assert any("warn_threshold=0.01s" in m for m in msgs)


def test_t_235_stab9_7_4_helper_passthrough_inner_exception() -> None:
    """Helper MUST NOT swallow exceptions from the wrapped body."""
    logger = logging.getLogger("test_stab9_7_4")
    with pytest.raises(ValueError, match="inner-error"):
        with timed_block("RaisingSite", warn_s=1.0, logger=logger):
            raise ValueError("inner-error")


def test_t_235_stab9_7_5_helper_logger_error_silent() -> None:
    """If logger itself errors during the finally block, helper must not
    propagate (loop must not die from logging failure)."""
    class BrokenLogger:
        def info(self, *a, **kw):
            raise RuntimeError("logger broken")
        def warning(self, *a, **kw):
            raise RuntimeError("logger broken")
    # Should NOT raise out:
    with timed_block(
        "Site",
        warn_s=1.0,
        logger=BrokenLogger(),
        always_info=True,
    ):
        pass
    with timed_block(
        "SlowSite",
        warn_s=0.001,
        logger=BrokenLogger(),
    ):
        time.sleep(0.01)


# ─── Cfg field tests ──────────────────────────────────────────────────────


def test_t_235_stab9_7_6_cfg_defaults() -> None:
    """Stage 7 cfg fields ship with correct defaults."""
    for env_var in [
        "ACIM_RUN_WARN_DURATION_S", "ACIM_SUBTEST_WARN_DURATION_S",
        "PROTOCOL_INTEL_COMPUTE_WARN_DURATION_S",
        "ABSORBED_TICKER_OUTER_WARN_DURATION_S",
        "ABSORBED_TICKER_PER_SPEC_WARN_DURATION_S",
    ]:
        os.environ.pop(env_var, None)
    from bridge.vapi_bridge.config import Config
    cfg = Config()
    assert cfg.acim_run_warn_duration_s == 5.0
    assert cfg.acim_subtest_warn_duration_s == 1.0
    assert cfg.protocol_intel_compute_warn_duration_s == 2.0
    assert cfg.absorbed_ticker_outer_warn_duration_s == 2.0
    assert cfg.absorbed_ticker_per_spec_warn_duration_s == 1.0


# ─── Curator stage-6 backward-compat tests ────────────────────────────────


def test_t_235_stab9_7_7_curator_stage6_format_preserved() -> None:
    """Stage 7 refactored curator wrappers to delegate to shared
    loop_timing.timed_block — verify the existing stage 6 grep patterns
    still match verbatim."""
    from bridge.vapi_bridge.corpus_curator_agent import (
        _timed_curator_task, _timed_db_block,
    )
    cfg = _stub_cfg(curator_task_warn_duration_s=0.01,
                    curator_db_warn_duration_s=0.01)
    logger = logging.getLogger("test_stab9_7_7")
    captures = []
    class CapLog:
        def info(self, fmt, *a):
            captures.append(("INFO", fmt % a))
        def warning(self, fmt, *a):
            captures.append(("WARN", fmt % a))
        def debug(self, *a, **kw): pass
    cap = CapLog()
    with _timed_curator_task("SlowTask", cfg, cap):
        time.sleep(0.05)
    with _timed_db_block("SlowDBSite", cfg, cap):
        time.sleep(0.05)
    # Stage 6 grep patterns must still match:
    text = "\n".join(m for _, m in captures)
    assert "[CorpusDataCuratorAgent] STAGE-6" in text
    assert "SLOW TASK: SlowTask took" in text
    assert "SLOW DB: SlowDBSite took" in text


# ─── Instrumentation-site presence tests ──────────────────────────────────


def test_t_235_stab9_7_8_acim_instrumented() -> None:
    """AgentCalibrationMonitor._run_all_tests wraps in timed_block."""
    src = (_BRIDGE_DIR / "agent_calibration_monitor.py").read_text(encoding="utf-8")
    assert "from .loop_timing import timed_block" in src
    assert "ACIM_run_all_tests" in src
    assert "ACIM_test_agent_" in src
    assert "[AgentCalibrationMonitor] STAGE-7" in src
    assert "acim_run_warn_duration_s" in src
    assert "acim_subtest_warn_duration_s" in src


def test_t_235_stab9_7_9_protocol_intel_instrumented() -> None:
    """ProtocolIntelligenceAgent._compute_and_store wraps in timed_block."""
    src = (_BRIDGE_DIR / "protocol_intelligence_agent.py").read_text(encoding="utf-8")
    assert "from .loop_timing import timed_block" in src
    assert "PIA_compute_and_store" in src
    assert "[ProtocolIntelligenceAgent] STAGE-7" in src
    assert "protocol_intel_compute_warn_duration_s" in src


def test_t_235_stab9_7_10_absorbed_ticker_instrumented() -> None:
    """AbsorbedAgentTicker.tick_all wraps outer + per-spec in timed_block."""
    src = (_BRIDGE_DIR / "operator_steward_absorbed_agents.py").read_text(encoding="utf-8")
    assert "from .loop_timing import timed_block" in src
    assert "StewardAbsorbedTicker] STAGE-7" in src
    # Outer label:
    assert '"tick_all"' in src
    # Per-spec label uses dynamic f-string — verify the f-string template:
    assert 'f"spec_{spec.name}"' in src
    assert "absorbed_ticker_outer_warn_duration_s" in src
    assert "absorbed_ticker_per_spec_warn_duration_s" in src


# ─── Behavioral non-regression tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_t_235_stab9_7_11_absorbed_ticker_returns_dict_unchanged() -> None:
    """Stage 7 instrumentation must not alter tick_all's return contract."""
    from bridge.vapi_bridge.operator_steward_absorbed_agents import (
        AbsorbedAgentTicker, AbsorbedAgentSpec,
    )
    cfg = _stub_cfg()

    # Build a fake spec that just counts invocations
    counts = {"n": 0}

    class FakeAgent:
        def __init__(self, *, cfg, store): pass
        def my_method(self):
            counts["n"] += 1

    import sys
    sys.modules["fake_stage7_mod"] = type(sys)("fake_stage7_mod")
    sys.modules["fake_stage7_mod"].FakeAgent = FakeAgent

    spec = AbsorbedAgentSpec(
        name="FakeAgent",
        module_path="fake_stage7_mod",
        class_name="FakeAgent",
        method_name="my_method",
        interval_s=3600,
        is_async=False,
    )
    ticker = AbsorbedAgentTicker(
        steward_name="TestSteward",
        specs=[spec],
        cfg=cfg, store=None,
    )
    result = await ticker.tick_all()
    assert isinstance(result, dict)
    assert "FakeAgent" in result
    assert counts["n"] == 1, "Spec must still fire — instrumentation does not block invocation"


def test_t_235_stab9_7_12_loop_timing_module_self_contained() -> None:
    """loop_timing.py has zero deps on other bridge modules (cycle safety)."""
    src = (_BRIDGE_DIR / "loop_timing.py").read_text(encoding="utf-8")
    # No bridge-relative imports:
    assert "from .config" not in src
    assert "from .store" not in src
    assert "from .chain" not in src
    assert "from .operator_" not in src
    # Only stdlib imports allowed:
    assert "import contextlib" in src
    assert "import logging" in src
    assert "import threading" in src
    assert "import time" in src
