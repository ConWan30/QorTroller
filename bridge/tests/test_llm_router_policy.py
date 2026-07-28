"""R0 pure-policy tests for LLM routing. No network, no env side effects."""

from __future__ import annotations

import pytest

from bridge.vapi_bridge.llm_routing import (
    BackendId,
    Level0RefuseError,
    RouteConfig,
    RouteMode,
    RouteResult,
    TaskClass,
    default_config,
    is_level0_task,
    ordered_candidates,
    refuse_if_level0,
)


# ---------------------------------------------------------------------------
# Level-0 refuse
# ---------------------------------------------------------------------------


def test_level0_task_class_refused():
    with pytest.raises(Level0RefuseError) as ei:
        ordered_candidates(TaskClass.LEVEL0, default_config())
    assert "no_llm_on_level0" in str(ei.value)
    assert ei.value.task_class is TaskClass.LEVEL0


def test_level0_tag_poac_refused_even_on_assistant():
    with pytest.raises(Level0RefuseError) as ei:
        ordered_candidates(
            TaskClass.ASSISTANT,
            default_config(),
            tags=frozenset({"poac"}),
        )
    assert "poac" in str(ei.value)


@pytest.mark.parametrize(
    "tag",
    ["pv_ci", "PV-CI", "invariant_gate", "frozen_v1", "events_root", "kas_commitment", "classify_live"],
)
def test_level0_tag_tokens_refused(tag: str):
    with pytest.raises(Level0RefuseError):
        refuse_if_level0(TaskClass.ASSISTANT, frozenset({tag}))


def test_is_level0_false_for_assistant_without_tags():
    assert is_level0_task(TaskClass.ASSISTANT) is False
    assert is_level0_task(TaskClass.GUARDIAN_ADVISORY) is False


# ---------------------------------------------------------------------------
# Failover defaults
# ---------------------------------------------------------------------------


def test_default_config_shape():
    cfg = default_config()
    assert cfg.mode is RouteMode.FAILOVER
    assert cfg.primary is BackendId.QUICKSILVER
    assert cfg.secondary is BackendId.LOCAL
    assert cfg.tertiary is None
    assert cfg.allow_nim_for_assistant is False


def test_failover_assistant_order():
    got = ordered_candidates(TaskClass.ASSISTANT, default_config())
    assert got == (BackendId.QUICKSILVER, BackendId.LOCAL)


def test_primary_only_returns_single():
    cfg = RouteConfig(
        mode=RouteMode.PRIMARY_ONLY,
        primary=BackendId.QUICKSILVER,
        secondary=BackendId.LOCAL,
    )
    assert ordered_candidates(TaskClass.ASSISTANT, cfg) == (BackendId.QUICKSILVER,)


# ---------------------------------------------------------------------------
# Task-split order
# ---------------------------------------------------------------------------


def test_task_split_assistant():
    cfg = RouteConfig(mode=RouteMode.TASK_SPLIT)
    assert ordered_candidates(TaskClass.ASSISTANT, cfg) == (
        BackendId.QUICKSILVER,
        BackendId.LOCAL,
    )


def test_task_split_guardian_prefers_nim():
    cfg = RouteConfig(mode=RouteMode.TASK_SPLIT)
    assert ordered_candidates(TaskClass.GUARDIAN_ADVISORY, cfg) == (
        BackendId.NIM,
        BackendId.LOCAL,
        BackendId.QUICKSILVER,
    )


def test_task_split_offline_local_only():
    cfg = RouteConfig(mode=RouteMode.TASK_SPLIT)
    assert ordered_candidates(TaskClass.OFFLINE, cfg) == (BackendId.LOCAL,)


def test_task_split_sovereign_local_only():
    cfg = RouteConfig(mode=RouteMode.TASK_SPLIT)
    assert ordered_candidates(TaskClass.SOVEREIGN_STRICT, cfg) == (BackendId.LOCAL,)


# ---------------------------------------------------------------------------
# Rails
# ---------------------------------------------------------------------------


def test_nim_stripped_from_assistant_unless_allowed():
    cfg = RouteConfig(
        mode=RouteMode.FAILOVER,
        primary=BackendId.QUICKSILVER,
        secondary=BackendId.NIM,
        tertiary=BackendId.LOCAL,
        allow_nim_for_assistant=False,
    )
    got = ordered_candidates(TaskClass.ASSISTANT, cfg)
    assert BackendId.NIM not in got
    assert got == (BackendId.QUICKSILVER, BackendId.LOCAL)


def test_nim_allowed_for_assistant_when_flag_set():
    cfg = RouteConfig(
        mode=RouteMode.FAILOVER,
        primary=BackendId.QUICKSILVER,
        secondary=BackendId.NIM,
        tertiary=BackendId.LOCAL,
        allow_nim_for_assistant=True,
    )
    got = ordered_candidates(TaskClass.ASSISTANT, cfg)
    assert got == (BackendId.QUICKSILVER, BackendId.NIM, BackendId.LOCAL)


def test_refuse_cloud_leaves_local_only():
    cfg = RouteConfig(
        mode=RouteMode.FAILOVER,
        primary=BackendId.QUICKSILVER,
        secondary=BackendId.LOCAL,
        refuse_cloud=True,
    )
    assert ordered_candidates(TaskClass.ASSISTANT, cfg) == (BackendId.LOCAL,)


def test_refuse_cloud_empty_when_no_local():
    cfg = RouteConfig(
        mode=RouteMode.PRIMARY_ONLY,
        primary=BackendId.QUICKSILVER,
        secondary=None,
        refuse_cloud=True,
    )
    assert ordered_candidates(TaskClass.ASSISTANT, cfg) == ()


# ---------------------------------------------------------------------------
# Configured / healthy filters
# ---------------------------------------------------------------------------


def test_configured_filter_drops_unconfigured():
    cfg = default_config()
    got = ordered_candidates(
        TaskClass.ASSISTANT,
        cfg,
        configured=frozenset({BackendId.LOCAL}),
    )
    assert got == (BackendId.LOCAL,)


def test_healthy_filter_drops_unhealthy():
    cfg = default_config()
    got = ordered_candidates(
        TaskClass.ASSISTANT,
        cfg,
        healthy=frozenset({BackendId.LOCAL}),
    )
    assert got == (BackendId.LOCAL,)


def test_dedupe_preserves_order():
    cfg = RouteConfig(
        mode=RouteMode.FAILOVER,
        primary=BackendId.LOCAL,
        secondary=BackendId.LOCAL,
        tertiary=BackendId.QUICKSILVER,
    )
    assert ordered_candidates(TaskClass.ASSISTANT, cfg) == (
        BackendId.LOCAL,
        BackendId.QUICKSILVER,
    )


# ---------------------------------------------------------------------------
# Provenance envelope shape
# ---------------------------------------------------------------------------


def test_route_result_provenance_dict():
    rr = RouteResult(
        backend=BackendId.LOCAL,
        model="deepseek-r1:14b",
        content="ok",
        fallback_used=True,
        primary_attempted=BackendId.QUICKSILVER,
        route_mode=RouteMode.FAILOVER,
        task_class=TaskClass.ASSISTANT,
        live=True,
    )
    d = rr.to_provenance_dict()
    assert d["backend"] == "local"
    assert d["fallback_used"] is True
    assert d["primary_attempted"] == "quicksilver"
    assert d["live"] is True
    assert "attempts" in d


def test_claude_not_a_backend_id():
    values = {b.value for b in BackendId}
    assert "claude" not in values
    assert values == {"quicksilver", "nim", "local"}
