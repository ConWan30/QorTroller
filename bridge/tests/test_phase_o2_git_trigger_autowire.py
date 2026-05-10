"""Phase O2-GIT-TRIGGER-AUTOWIRE tests.

Verifies the bridge boot path automatically constructs GitTriggerSource
and passes it to SentryPollingLoop when both cfg flags are True.

  T-O2-GIT-AUTOWIRE-1: factory returns LIVE GitTriggerSource when
                        operator_agent_git_trigger_enabled=True
  T-O2-GIT-AUTOWIRE-2: factory returns None when flag=False (scaffold-only
                        fallback preserved)
  T-O2-GIT-AUTOWIRE-3: end-to-end -- main.py-style construction wires
                        GitTriggerSource into a SentryPollingLoop and
                        commit triggers drive drafts into operator_agent_drafts
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import types
from pathlib import Path

import pytest

BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True,
    ).stdout.strip()


@pytest.fixture
def fresh_repo(tmp_path):
    repo = tmp_path / "test_repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "README.md").write_text("# initial\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial commit")
    return repo


def _make_cfg(**overrides):
    cfg = types.SimpleNamespace()
    cfg.operator_agent_sentry_polling_enabled = True
    cfg.operator_agent_sentry_polling_interval_s = 1
    cfg.operator_agent_git_trigger_enabled = True
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# T-O2-GIT-AUTOWIRE-1: factory returns LIVE source when flag=True
def test_T_O2_GIT_AUTOWIRE_1_live_source_when_flag_true(fresh_repo):
    from vapi_bridge.operator_agent_git_trigger_source import (
        GitTriggerSource, make_git_trigger_source,
    )
    cfg = _make_cfg(operator_agent_git_trigger_enabled=True)
    src = make_git_trigger_source(cfg=cfg, repo_path=fresh_repo)
    assert src is not None
    assert isinstance(src, GitTriggerSource)
    # Smoke: callable returns a list (baseline call -> [])
    assert isinstance(src(), list)


# T-O2-GIT-AUTOWIRE-2: factory returns None when flag=False
def test_T_O2_GIT_AUTOWIRE_2_none_when_flag_false(fresh_repo):
    from vapi_bridge.operator_agent_git_trigger_source import make_git_trigger_source
    cfg = _make_cfg(operator_agent_git_trigger_enabled=False)
    assert make_git_trigger_source(cfg=cfg, repo_path=fresh_repo) is None


# T-O2-GIT-AUTOWIRE-3: end-to-end main.py-style construction
def test_T_O2_GIT_AUTOWIRE_3_main_py_pattern_e2e(fresh_repo, tmp_path):
    """Mirrors main.py boot path: factory constructs source, run_sentry_polling_loop
    receives it via get_pending_triggers kwarg. Verify the trigger source is
    wired through (commit -> drafts in store)."""
    from vapi_bridge.operator_agent_git_trigger_source import make_git_trigger_source
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_agent_sentry_polling import SentryPollingLoop
    from vapi_bridge.store import Store

    store = Store(str(tmp_path / "autowire_e2e.db"))
    cfg = _make_cfg()
    gen = SentryDraftGenerator(cfg=cfg, store=store)

    # Factory pattern as main.py uses it
    src = make_git_trigger_source(cfg=cfg, repo_path=fresh_repo)
    assert src is not None
    src()  # seed baseline

    # Construct loop with the source as get_pending_triggers (matches the
    # main.py kwarg passed to run_sentry_polling_loop)
    loop = SentryPollingLoop(
        cfg=cfg, store=store, draft_generator=gen,
        get_pending_triggers=src,
    )

    # Make a commit -- triggers should be ready next call
    (fresh_repo / "f.txt").write_text("autowire test")
    _git(fresh_repo, "add", "f.txt")
    _git(fresh_repo, "commit", "-m", "feat: autowire test")

    # One dispatch cycle -- should consume the commit trigger and produce
    # both kms-sign + provenance-recording drafts
    asyncio.run(loop._dispatch_one_cycle())

    rows = store.get_operator_agent_drafts(agent_id="anchor_sentry", limit=10)
    actions = sorted(r["action_name"] for r in rows)
    assert actions == ["kms-sign", "provenance-recording"]
