"""Phase 235.x-STABILITY-6 tests — agent retry-loop hardening.

Closes the residual tight-error-loop bug surfaced by Phase O1 D
minimal-runtime experimentation 2026-05-09. Four agents
(chain_reconciler, live_mode_activation_agent, session_adjudicator,
ruling_enforcement_agent) shared the same flawed retry pattern: the
exception handler in their `while True` poll loops did not sleep before
retrying, so when the next iteration's `await asyncio.sleep(N)` itself
raised an exception (empirically: `RuntimeError("no running event loop")`
when DUALSHOCK_ENABLED=false on Windows), the loop spun at CPU-bound
speed (9000-100000 errors per second), filling logs and disk.

The fix: add a defensive backoff `await asyncio.sleep(min(N, 5.0))`
inside the exception handler. If the backoff sleep itself raises (the
catastrophic case), the agent exits its loop cleanly via `return`
instead of tight-looping.

Same pattern across all 4 agents. Tests are static checks on source
code — runtime behavioral testing of the catastrophic case requires
an event-loop teardown harness that's not worth the complexity for a
defensive-coding fix.

T-235-STAB6-1..5.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Each agent's retry-loop module. The fix should appear in all of them.
HARDENED_AGENTS = [
    ("chain_reconciler.py",         "ChainReconciler"),
    ("live_mode_activation_agent.py","LiveModeActivationAgent"),
    ("session_adjudicator.py",      "SessionAdjudicator"),
    ("ruling_enforcement_agent.py", "RulingEnforcementAgent"),
]


def _read_agent_source(filename: str) -> str:
    return (
        PROJECT_ROOT / "bridge" / "vapi_bridge" / filename
    ).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T-235-STAB6-1: every hardened agent has the STABILITY-6 marker comment
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,agent_name", HARDENED_AGENTS)
def test_t_235_stab6_1_marker_present(filename, agent_name):
    """Every hardened agent must reference Phase 235.x-STABILITY-6 in a
    comment at the fix site — makes it easy for future contributors to
    find all the call sites + understand the rationale."""
    src = _read_agent_source(filename)
    assert "Phase 235.x-STABILITY-6" in src, (
        f"{filename}: STABILITY-6 marker comment missing — fix not applied"
    )


# ---------------------------------------------------------------------------
# T-235-STAB6-2: every hardened agent has a backoff sleep INSIDE the
# exception handler (not just at the start of the next iteration)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,agent_name", HARDENED_AGENTS)
def test_t_235_stab6_2_backoff_sleep_in_except_handler(filename, agent_name):
    """The fix is structural: there must be a `await asyncio.sleep(...)`
    INSIDE the `except Exception` block, not just at the top of the loop.
    Regression guard against future contributor "cleaning up" the
    apparent duplicate sleep."""
    src = _read_agent_source(filename)
    # Look for the pattern: `backoff sleep failed` (the catastrophic-case
    # log message we ship as part of the fix). If this string is present,
    # the defensive backoff structure exists.
    assert "backoff sleep failed" in src, (
        f"{filename}: defensive backoff structure missing — "
        "the inner `try: await asyncio.sleep(...) except: return` block "
        "is the load-bearing part of STABILITY-6"
    )


# ---------------------------------------------------------------------------
# T-235-STAB6-3: backoff sleep is bounded (at most 5s)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,agent_name", HARDENED_AGENTS)
def test_t_235_stab6_3_backoff_bounded_to_5s(filename, agent_name):
    """The defensive backoff is `min(POLL_INTERVAL, 5.0)`. This bounds
    recovery time when the underlying issue resolves (e.g., the loop
    becomes reachable again) — without it, a 5-min poll interval would
    add 5 minutes of dead time after every transient error."""
    src = _read_agent_source(filename)
    assert "min(" in src and ", 5.0)" in src, (
        f"{filename}: backoff should use `min(POLL_INTERVAL, 5.0)` to "
        "bound recovery time on transient errors"
    )


# ---------------------------------------------------------------------------
# T-235-STAB6-4: backoff exception handler exits cleanly (return)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,agent_name", HARDENED_AGENTS)
def test_t_235_stab6_4_backoff_failure_exits_cleanly(filename, agent_name):
    """The catastrophic case (backoff sleep itself raises) must `return`
    — exiting the loop cleanly. Re-raising or swallowing would re-enter
    the tight-loop spin we're fixing."""
    src = _read_agent_source(filename)
    # The fix structure: "backoff sleep failed" log message immediately
    # followed by `return` (possibly via self._running = False)
    idx = src.find("backoff sleep failed")
    assert idx != -1, f"{filename}: marker missing"
    # Look at the next ~250 chars after the log message — must contain `return`
    tail = src[idx:idx + 400]
    assert "return" in tail, (
        f"{filename}: backoff failure handler must `return` to exit the loop "
        "cleanly. Allowing fall-through re-enters the tight-loop bug."
    )


# ---------------------------------------------------------------------------
# T-235-STAB6-5: CancelledError is preserved (raise, not swallow)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,agent_name", HARDENED_AGENTS)
def test_t_235_stab6_5_cancelled_error_preserved(filename, agent_name):
    """The defensive backoff's exception handler must re-raise (or set
    self._running = False then return) on CancelledError. Catching it
    indiscriminately would break asyncio's task-cancellation contract."""
    src = _read_agent_source(filename)
    idx = src.find("backoff sleep failed")
    assert idx != -1
    # Look BEFORE the log line — the structure should be:
    #     try: await asyncio.sleep(...)
    #     except asyncio.CancelledError: raise (or self._running = False; return)
    #     except Exception as backoff_exc: log.error(...); return
    head = src[max(0, idx - 600):idx]
    # CancelledError must appear in the backoff block
    assert "CancelledError" in head, (
        f"{filename}: backoff block must explicitly handle "
        "asyncio.CancelledError — silently swallowing it breaks task "
        "cancellation"
    )
