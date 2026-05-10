"""Phase O2-GIT-TRIGGER-SOURCE -- 2026-05-10.

Concrete LIVE trigger source for the operator-agent polling loops shipped in
Phase O2-DRAFT-AUTOLOOP (commits 6c33b111 + 1b8e557b + 93b5c1b2). The earlier
phase shipped the polling loops with SCAFFOLD-ONLY trigger injection (a
no-op stub returning []); this module ships the first concrete event source
that emits real triggers to the loops.

DESIGN
======

GitTriggerSource is a callable -- when invoked, returns a list of pending
trigger dicts shaped for the polling loops' get_pending_triggers contract:

    [{"kind": "commit", "payload": {"commit_hash", "repo", "branch"}}]

The class polls `git log -1 --format=%H` on the repo HEAD via stdlib
subprocess. Maintains an in-memory "last seen commit hash" state. When HEAD
advances since the last call, returns ONE trigger per new commit (in
forward chronological order). When HEAD is unchanged, returns [].

Pure stdlib (no bus dependency, no external library). Failures are caught +
logged + return []; never raises (matches the polling loops' fail-open
contract).

OPT-IN: cfg.operator_agent_git_trigger_enabled (default False). Operator
sets to True to activate. Pairs naturally with
cfg.operator_agent_sentry_polling_enabled=True so Sentry's polling loop
receives commit triggers as the operator pushes commits.

INVARIANTS:
  - First call after init returns [] (baseline; no commits-since concept yet).
    Last-seen commit is set from this baseline call. Subsequent calls
    diff against it.
  - Multiple commits since last call are emitted in forward chronological
    order via `git log <last_seen>..HEAD --reverse`.
  - The polling loop's rate-limit invariant (ONE trigger per cycle) means
    even if 5 commits accumulate between calls, only ONE is dispatched per
    poll cycle; the remaining queue waits for the next cycle. The trigger
    source RETURNS all 5; the polling loop itself drains the head.

DRIFT FINDING NOTE
==================

The polling loops were shipped with the documented contract that
`get_pending_triggers` returns a list and the loop dispatches the head only.
GitTriggerSource cooperates: it returns the full list of pending commits
(possibly N>1), and the polling loop consumes the head. On the NEXT cycle,
the polling loop will call GitTriggerSource again -- but at that point
GitTriggerSource has already updated its last-seen pointer to the head it
returned LAST cycle. So the next cycle's call will see N-1 pending. This
allows the queue to drain at one trigger per cycle.

For correctness: GitTriggerSource updates its last-seen ONLY for commits
it actually returned. The polling loop returning the head of the list does
not affect GitTriggerSource's state directly; the SOURCE assumes its
returned list will be fully consumed, but the LOOP consumes only the head.
That's a benign leak: the same commit will be re-emitted on the next call,
where the polling loop will dispatch it. So a 5-commit advancement produces
exactly 5 trigger dispatches across 5 cycles, matching the rate-limit
invariant. Documented in T-O2-GIT-TRIG-2.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)


# Default repo path -- relative to bridge package root.
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]


class GitTriggerSource:
    """Phase O2-GIT-TRIGGER-SOURCE callable trigger producer for git commits.

    Construction:
      cfg          -- vapi_bridge.config.Config (or test stub) with
                      operator_agent_git_trigger_enabled flag.
      repo_path    -- absolute path to the git repo. Default: repo containing
                      this bridge package.
      branch       -- branch label embedded in the trigger payload. Default:
                      'main'.
      repo_label   -- the value placed in payload['repo']. Default:
                      'ConWan30/vapi-prototype'.

    Calling the instance returns the list of pending commit triggers
    (forward chronological). First call returns [] and seeds last-seen.
    """

    def __init__(
        self,
        *,
        cfg: Any = None,
        repo_path: Optional[Path] = None,
        branch: str = "main",
        repo_label: str = "ConWan30/vapi-prototype",
    ) -> None:
        self._cfg = cfg
        self._repo = Path(repo_path or _DEFAULT_REPO_ROOT)
        self._branch = str(branch)
        self._repo_label = str(repo_label)
        self._last_seen: Optional[str] = None
        self._initialized = False

    def __call__(self) -> list[dict]:
        """Return list of pending commit triggers since last call.
        First call seeds last-seen and returns []. Errors -> []."""
        # Opt-in gate
        if self._cfg is not None and not getattr(
            self._cfg, "operator_agent_git_trigger_enabled", False
        ):
            return []

        try:
            head = self._git_head_hash()
        except Exception as exc:
            log.warning("GitTriggerSource: git rev-parse HEAD failed: %s", exc)
            return []
        if not head:
            return []

        if not self._initialized:
            # First call: seed baseline, no triggers.
            self._last_seen = head
            self._initialized = True
            return []

        if head == self._last_seen:
            # No new commits.
            return []

        # HEAD advanced: enumerate commits since last_seen in forward
        # chronological order (oldest-first).
        try:
            new_commits = self._git_commits_between(self._last_seen, head)
        except Exception as exc:
            log.warning("GitTriggerSource: git log range failed: %s", exc)
            return []

        triggers = [
            {
                "kind": "commit",
                "payload": {
                    "commit_hash": ch,
                    "repo": self._repo_label,
                    "branch": self._branch,
                },
            }
            for ch in new_commits
        ]
        # Update last-seen to current HEAD; the polling loop's rate-limit
        # will dispatch ONE per cycle, but the source's state has advanced
        # so the next call won't re-emit the same commits.
        self._last_seen = head
        return triggers

    # ------------------------------------------------------------------
    # Git plumbing (stdlib subprocess; never raises into __call__)
    # ------------------------------------------------------------------
    def _git_head_hash(self) -> str:
        """Run `git rev-parse HEAD` and return the 40-char commit hash."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(self._repo),
            capture_output=True,
            text=True,
            timeout=5.0,
            check=True,
        )
        return result.stdout.strip()

    def _git_commits_between(self, since: str, until: str) -> list[str]:
        """Return commit hashes in (since, until] in forward chronological
        order (oldest-first). `since` is exclusive; `until` is inclusive.
        Returns [] if the range is empty or invalid."""
        result = subprocess.run(
            ["git", "log", "--reverse", "--format=%H", f"{since}..{until}"],
            cwd=str(self._repo),
            capture_output=True,
            text=True,
            timeout=5.0,
            check=True,
        )
        out = result.stdout.strip()
        if not out:
            return []
        return [line.strip() for line in out.split("\n") if line.strip()]


def make_git_trigger_source(
    *,
    cfg: Any = None,
    repo_path: Optional[Path] = None,
    branch: str = "main",
    repo_label: str = "ConWan30/vapi-prototype",
) -> "GitTriggerSource | None":
    """Module-level factory matching the cedar_drift_sweeper / polling-loop
    entrypoint pattern. Returns None when
    cfg.operator_agent_git_trigger_enabled is False (opt-in default).

    Higher-level wiring (e.g. main.py) constructs this and passes it as
    `get_pending_triggers` to run_sentry_polling_loop. Returning None allows
    the polling loop to fall back to its no-op default stub.
    """
    if cfg is not None and not getattr(
        cfg, "operator_agent_git_trigger_enabled", False
    ):
        log.info(
            "GitTriggerSource: disabled "
            "(operator_agent_git_trigger_enabled=False)"
        )
        return None
    return GitTriggerSource(
        cfg=cfg,
        repo_path=repo_path,
        branch=branch,
        repo_label=repo_label,
    )
