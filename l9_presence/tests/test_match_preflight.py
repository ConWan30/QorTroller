"""RP-5 match preflight gate tests.

Pins: heavy-tool process -> BLOCK (M11 lesson); CPU thresholds (M12); DB size warn
(cycle-49); ring freshness (pre-M8); env sanity; gather errors -> UNVERIFIABLE -> NO_GO
(never spurious PASS); self-pid excluded; overall verdict fail-closed.
"""
from __future__ import annotations

from l9_presence.match_preflight import (
    CheckState,
    OverallVerdict,
    PreflightEvidence,
    ProcessInfo,
    evaluate_preflight,
)


def _clean_evidence(**over):
    kw = dict(
        python_processes=[ProcessInfo(pid=100, command_line="python bridge/main.py")],
        cpu_percent=25.0,
        bridge_db_bytes=500 * 1024 ** 2,
        capture_dir_entries=[],
        env={"RETINA_KILLFEED_CAPTURE_MAX": "1800"},
    )
    kw.update(over)
    return PreflightEvidence(**kw)


def _by_name(report, name):
    return next(c for c in report.checks if c.name == name)


def test_clean_evidence_is_go():
    r = evaluate_preflight(_clean_evidence())
    assert r.verdict == OverallVerdict.GO
    assert r.go()
    assert all(c.state == CheckState.PASS for c in r.checks)


def test_zombie_audit_lane_blocks():
    """M11: a stale killfeed_audit_lane.py process must BLOCK, with its pid named."""
    ev = _clean_evidence(python_processes=[
        ProcessInfo(pid=100, command_line="python bridge/main.py"),
        ProcessInfo(pid=4242, command_line="python scripts/killfeed_audit_lane.py --crops x"),
    ])
    r = evaluate_preflight(ev)
    assert r.verdict == OverallVerdict.NO_GO
    c = _by_name(r, "orphaned_processes")
    assert c.state == CheckState.BLOCK and "4242" in c.note


def test_self_pid_excluded():
    """The preflight's own process must never trigger its own BLOCK."""
    ev = _clean_evidence(python_processes=[
        ProcessInfo(pid=7777, command_line="python scripts/match_preflight.py"),
        ProcessInfo(pid=7777, command_line="python -m pytest l9_presence/tests"),
    ])
    r = evaluate_preflight(ev, self_pid=7777)
    assert _by_name(r, "orphaned_processes").state == CheckState.PASS


def test_cpu_thresholds():
    """M12: 94.9% at failure. >=60 BLOCK, >=40 WARN, else PASS."""
    assert _by_name(evaluate_preflight(_clean_evidence(cpu_percent=94.9)),
                    "cpu_baseline").state == CheckState.BLOCK
    assert _by_name(evaluate_preflight(_clean_evidence(cpu_percent=45.0)),
                    "cpu_baseline").state == CheckState.WARN
    assert _by_name(evaluate_preflight(_clean_evidence(cpu_percent=20.0)),
                    "cpu_baseline").state == CheckState.PASS


def test_db_size_warns_above_3gb():
    """cycle-49: 5.4GB DB was the lag source."""
    ev = _clean_evidence(bridge_db_bytes=int(5.4 * 1024 ** 3))
    r = evaluate_preflight(ev)
    assert _by_name(r, "bridge_db_size").state == CheckState.WARN
    assert r.verdict == OverallVerdict.GO_WITH_WARNINGS


def test_missing_db_is_fresh_pass():
    r = evaluate_preflight(_clean_evidence(bridge_db_bytes=None))
    assert _by_name(r, "bridge_db_size").state == CheckState.PASS


def test_stale_capture_dir_warns():
    """pre-M8: ring persists across sessions."""
    ev = _clean_evidence(capture_dir_entries=["crop_001.png", "crop_002.png"])
    r = evaluate_preflight(ev)
    c = _by_name(r, "capture_dir_fresh")
    assert c.state == CheckState.WARN and "2 entries" in c.note


def test_missing_capture_dir_is_fresh_pass():
    r = evaluate_preflight(_clean_evidence(capture_dir_entries=None))
    assert _by_name(r, "capture_dir_fresh").state == CheckState.PASS


def test_missing_env_warns():
    r = evaluate_preflight(_clean_evidence(env={}))
    assert _by_name(r, "env_sanity").state == CheckState.WARN


def test_gather_error_is_unverifiable_never_pass():
    """The never-spurious-PASS rail: a process-gather failure must be UNVERIFIABLE
    and force NO_GO — never silently green."""
    ev = _clean_evidence(python_processes=None)
    ev.errors["processes"] = "PowerShell CIM query failed"
    r = evaluate_preflight(ev)
    c = _by_name(r, "orphaned_processes")
    assert c.state == CheckState.UNVERIFIABLE
    assert r.verdict == OverallVerdict.NO_GO
    assert not r.go()


def test_cpu_gather_error_is_unverifiable():
    ev = _clean_evidence(cpu_percent=None)
    r = evaluate_preflight(ev)
    assert _by_name(r, "cpu_baseline").state == CheckState.UNVERIFIABLE
    assert r.verdict == OverallVerdict.NO_GO
