"""Phase O2-GIT-TRIGGER-SOURCE tests.

Verifies GitTriggerSource produces correct commit triggers from a fresh
git repo fixture.

  T-O2-GIT-TRIG-1: first call returns [] (baseline seeding); subsequent
                    no-op when HEAD unchanged
  T-O2-GIT-TRIG-2: HEAD advances by 1 commit -> returns 1 trigger; next
                    call returns [] (last-seen advanced)
  T-O2-GIT-TRIG-3: HEAD advances by N commits -> returns N triggers in
                    forward chronological order
  T-O2-GIT-TRIG-4: opt-in default -- cfg.operator_agent_git_trigger_enabled=False
                    causes __call__ to return [] without invoking git
  T-O2-GIT-TRIG-5: git failure (broken repo path) returns [] without raising
  T-O2-GIT-TRIG-6: factory make_git_trigger_source returns None when
                    flag=False; returns instance when flag=True
"""
from __future__ import annotations

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


def _make_cfg(**overrides):
    cfg = types.SimpleNamespace()
    cfg.operator_agent_git_trigger_enabled = True  # default ENABLED for tests
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _git(repo: Path, *args: str) -> str:
    """Run git command in repo; return stdout."""
    result = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def fresh_repo(tmp_path):
    """A fresh git repo with one initial commit. Yields the repo Path."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "README.md").write_text("# initial\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial commit")
    return repo


def _commit_file(repo: Path, name: str, content: str, msg: str) -> str:
    """Add a file + commit it; return the new commit hash."""
    (repo / name).write_text(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


# T-O2-GIT-TRIG-1: first call seeds baseline + no-op when HEAD unchanged
def test_T_O2_GIT_TRIG_1_first_call_seeds_baseline(fresh_repo):
    from vapi_bridge.operator_agent_git_trigger_source import GitTriggerSource
    src = GitTriggerSource(cfg=_make_cfg(), repo_path=fresh_repo)
    # First call: baseline (no commits-since concept yet)
    assert src() == []
    # Second call: HEAD unchanged -> still []
    assert src() == []


# T-O2-GIT-TRIG-2: HEAD advances by 1 commit -> 1 trigger; next call empty
def test_T_O2_GIT_TRIG_2_one_commit_one_trigger(fresh_repo):
    from vapi_bridge.operator_agent_git_trigger_source import GitTriggerSource
    src = GitTriggerSource(cfg=_make_cfg(), repo_path=fresh_repo)
    src()  # seed baseline

    # Advance HEAD by 1 commit
    new_hash = _commit_file(fresh_repo, "a.txt", "a", "feat: add a")

    triggers = src()
    assert len(triggers) == 1
    t = triggers[0]
    assert t["kind"] == "commit"
    assert t["payload"]["commit_hash"] == new_hash
    assert t["payload"]["repo"] == "ConWan30/vapi-prototype"
    assert t["payload"]["branch"] == "main"

    # Next call -- last-seen advanced; no new commits
    assert src() == []


# T-O2-GIT-TRIG-3: HEAD advances by N commits -> N triggers in forward order
def test_T_O2_GIT_TRIG_3_multiple_commits_chronological_order(fresh_repo):
    from vapi_bridge.operator_agent_git_trigger_source import GitTriggerSource
    src = GitTriggerSource(cfg=_make_cfg(), repo_path=fresh_repo)
    src()  # seed

    # Make 3 commits
    h1 = _commit_file(fresh_repo, "1.txt", "1", "feat: 1")
    h2 = _commit_file(fresh_repo, "2.txt", "2", "feat: 2")
    h3 = _commit_file(fresh_repo, "3.txt", "3", "feat: 3")

    triggers = src()
    assert len(triggers) == 3
    hashes = [t["payload"]["commit_hash"] for t in triggers]
    # Forward chronological: oldest first
    assert hashes == [h1, h2, h3]
    # All same kind
    assert all(t["kind"] == "commit" for t in triggers)


# T-O2-GIT-TRIG-4: opt-in default -- flag=False short-circuits
def test_T_O2_GIT_TRIG_4_opt_in_default(fresh_repo):
    from vapi_bridge.operator_agent_git_trigger_source import GitTriggerSource
    cfg = _make_cfg(operator_agent_git_trigger_enabled=False)
    src = GitTriggerSource(cfg=cfg, repo_path=fresh_repo)

    # Even after committing, returns [] because flag is False
    _commit_file(fresh_repo, "x.txt", "x", "feat: x")
    assert src() == []
    assert src() == []


# T-O2-GIT-TRIG-5: git failure (broken repo path) returns [] without raising
def test_T_O2_GIT_TRIG_5_broken_repo_returns_empty(tmp_path):
    from vapi_bridge.operator_agent_git_trigger_source import GitTriggerSource
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    src = GitTriggerSource(cfg=_make_cfg(), repo_path=not_a_repo)
    # Must not raise; git rev-parse HEAD fails on non-repo
    result = src()
    assert result == []


# T-O2-GIT-TRIG-6: factory returns None when flag=False; instance when True
def test_T_O2_GIT_TRIG_6_factory_opt_in(fresh_repo):
    from vapi_bridge.operator_agent_git_trigger_source import (
        GitTriggerSource,
        make_git_trigger_source,
    )
    # Flag False -> None
    cfg_off = _make_cfg(operator_agent_git_trigger_enabled=False)
    assert make_git_trigger_source(cfg=cfg_off, repo_path=fresh_repo) is None

    # Flag True -> instance
    cfg_on = _make_cfg(operator_agent_git_trigger_enabled=True)
    src = make_git_trigger_source(cfg=cfg_on, repo_path=fresh_repo)
    assert isinstance(src, GitTriggerSource)
    # Smoke: callable returns list
    assert isinstance(src(), list)


# T-O2-GIT-TRIG-7: integration with SentryPollingLoop -- end-to-end
def test_T_O2_GIT_TRIG_7_integration_with_sentry_polling_loop(fresh_repo, tmp_path):
    """End-to-end: GitTriggerSource feeds SentryPollingLoop; commit triggers
    drive draft_kms_sign + draft_provenance_record into operator_agent_drafts."""
    from vapi_bridge.operator_agent_git_trigger_source import GitTriggerSource
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    from vapi_bridge.operator_agent_sentry_polling import SentryPollingLoop
    from vapi_bridge.store import Store

    store = Store(str(tmp_path / "git_trig_e2e.db"))
    cfg = _make_cfg()
    cfg.operator_agent_sentry_polling_enabled = False  # unused in direct dispatch
    cfg.operator_agent_sentry_polling_interval_s = 1
    gen = SentryDraftGenerator(cfg=cfg, store=store)
    src = GitTriggerSource(cfg=cfg, repo_path=fresh_repo)
    src()  # seed

    loop = SentryPollingLoop(
        cfg=cfg, store=store, draft_generator=gen,
        get_pending_triggers=src,
    )

    # Make 1 commit, run one dispatch cycle
    _commit_file(fresh_repo, "feat.txt", "feat", "feat: ship feature X")
    import asyncio
    asyncio.run(loop._dispatch_one_cycle())

    # Sentry's commit handler invokes BOTH kms-sign AND provenance-recording
    rows = store.get_operator_agent_drafts(agent_id="anchor_sentry", limit=10)
    actions = sorted(r["action_name"] for r in rows)
    assert actions == ["kms-sign", "provenance-recording"]
