#!/usr/bin/env python3
"""Git helper for Buzz NIP-34 repos.

Wraps `git` with the `git-credential-nostr` helper so a child agent (QorT,
Retina, etc.) can push to Buzz git repos. The caller supplies the agent's
`BUZZ_PRIVATE_KEY` and `BUZZ_AUTH_TAG` via environment.

Credentials:
- `git-credential-nostr` reads `NOSTR_PRIVATE_KEY` and `BUZZ_AUTH_TAG`.
- This helper sets `NOSTR_PRIVATE_KEY` from the `BUZZ_PRIVATE_KEY` env var.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CRED_HELPER = REPO_ROOT / "buzz" / "target" / "debug" / "git-credential-nostr.exe"
DEFAULT_RELAY_HTTP = "https://qortroller.communities.buzz.xyz"


def _buzz_env() -> dict:
    """Build an env dict with NOSTR_PRIVATE_KEY mapped from BUZZ_PRIVATE_KEY."""
    env = os.environ.copy()
    pk = env.get("BUZZ_PRIVATE_KEY", "")
    if pk:
        env["NOSTR_PRIVATE_KEY"] = pk
    if not env.get("BUZZ_AUTH_TAG"):
        raise RuntimeError("BUZZ_AUTH_TAG is required for Buzz git auth")
    if not env.get("NOSTR_PRIVATE_KEY"):
        raise RuntimeError("BUZZ_PRIVATE_KEY is required for Buzz git auth")
    return env


def _sh_path(path: Path) -> str:
    """Convert a Windows path to one Git's `!` shell helper can use: C:\\x -> /c/x."""
    p = str(path).replace("\\", "/")
    if ":" in p and p[1:2] == ":":
        p = f"/{p[0].lower()}{p[2:]}"
    return p


def _is_github(repo_name: str) -> bool:
    return repo_name in ("origin", "QorTroller", "github") or repo_name.startswith(("https://github.com", "github.com"))


def _github_env() -> dict:
    """Env for GitHub: make sure git does not hang and GCM does not popup."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    return env


def _github_cmd(cwd: Path, *args: str, extra_env: dict | None = None) -> str:
    """Run a git command for github.com using `gh` as the credential helper.

    Disables the global Git Credential Manager (`credential.helper=`) and sets
    a per-URL `gh auth git-credential` helper, so no GUI prompt appears.
    """
    env = _github_env()
    if extra_env:
        env.update(extra_env)
    cmd = [
        "git",
        "-c", "credential.helper=",
        "-c", "credential.https://github.com.helper=!gh auth git-credential",
        *args,
    ]
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        shell=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def _git_cmd(cwd: Path, *args: str, extra_env: dict | None = None) -> str:
    """Run git with the NIP-98 credential helper."""
    if not CRED_HELPER.exists():
        raise RuntimeError(f"git-credential-nostr not found at {CRED_HELPER}. Build it with: cargo build -p git-credential-nostr")

    env = _buzz_env()
    if extra_env:
        env.update(extra_env)

    host = env.get("BUZZ_RELAY_HTTP", DEFAULT_RELAY_HTTP).rstrip("/")
    if not host.startswith("http"):
        # git-credential-nostr needs https; convert wss->https if needed
        host = host.replace("wss://", "https://").replace("ws://", "http://")

    # Prevent git from asking interactively, disable the bundled GCM, and wire our helper.
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["GCM_PROVIDER"] = "generic"
    env["BUZZ_RELAY_URL"] = env.get("BUZZ_RELAY_URL", _raw_to_ws(host))

    helper = f"!{_sh_path(CRED_HELPER)}"
    cmd = [
        "git",
        "-c", "credential.helper=",
        "-c", f"credential.{host}.helper={helper}",
        "-c", "credential.useHttpPath=true",
        *args,
    ]
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        shell=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def _raw_to_ws(url: str) -> str:
    if url.startswith("http://"):
        return "ws://" + url[len("http://"):]
    if url.startswith("https://"):
        return "wss://" + url[len("https://"):]
    return url


def _pubkey_hex(private_key: str) -> str:
    """Derive hex pubkey from nsec or hex private key."""
    try:
        from nostr_sdk import Keys
        k = Keys.parse(private_key)
        return k.public_key().to_hex()
    except Exception as e:
        raise RuntimeError(f"could not derive pubkey: {e}")


def _ensure_remote(cwd: Path, repo_name: str, owner_hex: str | None = None) -> str:
    """Ensure the 'buzz' remote exists and points at the Buzz repo."""
    env = _git_env()
    if owner_hex is None:
        owner_hex = os.environ.get("BUZZ_REPO_OWNER_HEX", "")
    if not owner_hex:
        owner_hex = _pubkey_hex(env["NOSTR_PRIVATE_KEY"])
    remote_url = f"{DEFAULT_RELAY_HTTP}/git/{owner_hex}/{repo_name}"

    try:
        _git_cmd(cwd, "remote", "get-url", "buzz")
        _git_cmd(cwd, "remote", "set-url", "buzz", remote_url)
    except RuntimeError:
        _git_cmd(cwd, "remote", "add", "buzz", remote_url)
    return remote_url


def _github_branch() -> str:
    proc = subprocess.run(["git", "branch", "--show-current"], cwd=REPO_ROOT, capture_output=True, text=True)
    return proc.stdout.strip() or "main"


def git_push(cwd: Path, repo_name: str, owner_hex: str | None = None, branch: str = "main") -> str:
    """Push the current branch to a Buzz or GitHub remote."""
    if _is_github(repo_name):
        branch = branch if branch and branch != "main" else _github_branch()
        _github_cmd(cwd, "push", "origin", branch)
        return f"pushed to GitHub origin/{branch}"
    _ensure_remote(cwd, repo_name, owner_hex)
    _git_cmd(cwd, "push", "buzz", branch)
    return f"pushed to buzz/{branch}"


def _has_staged_changes(cwd: Path, env: dict) -> bool:
    """Return True if there are staged changes ready to commit."""
    proc = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=cwd,
        env=env,
    )
    return proc.returncode != 0


def git_commit_and_push(cwd: Path, repo_name: str, message: str, owner_hex: str | None = None, branch: str = "main") -> str:
    """Stage tracked changes, commit, and push to Buzz or GitHub."""
    if _is_github(repo_name):
        branch = branch if branch and branch != "main" else _github_branch()
        _github_cmd(cwd, "add", "-u")
        env = _github_env()
        if _has_staged_changes(cwd, env):
            _github_cmd(cwd, "commit", "-m", message)
            _github_cmd(cwd, "push", "origin", branch)
            return f"committed and pushed to GitHub origin/{branch}"
        _github_cmd(cwd, "push", "origin", branch)
        return f"no changes to commit; pushed to GitHub origin/{branch}"

    _ensure_remote(cwd, repo_name, owner_hex)
    _git_cmd(cwd, "add", "-u")
    env = _buzz_env()
    if _has_staged_changes(cwd, env):
        _git_cmd(cwd, "commit", "-m", message)
        _git_cmd(cwd, "push", "buzz", branch)
        return f"committed and pushed to buzz/{branch}"
    _git_cmd(cwd, "push", "buzz", branch)
    return f"no changes to commit; pushed to buzz/{branch}"


def buzz_merge_pr(pr_event_id: str) -> str:
    """Merge a Buzz or GitHub PR."""
    # GitHub PR numbers are just integers; Buzz PRs are hex event ids (64 chars).
    if pr_event_id.isdigit():
        result = subprocess.run(
            ["gh", "pr", "merge", pr_event_id, "--merge", "--admin"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gh pr merge failed: {result.stderr.strip() or result.stdout.strip()}")
        return f"GitHub PR #{pr_event_id} merged"

    env = _buzz_env()
    cli = env.get("BUZZ_CLI_PATH", str(REPO_ROOT / "buzz" / "target" / "debug" / "buzz.exe"))
    result = subprocess.run(
        [cli, "pr", "status", pr_event_id, "--status", "merged"],
        env=env,
        capture_output=True,
        text=True,
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"buzz pr status failed: {result.stderr.strip() or result.stdout.strip()}")
    return f"PR {pr_event_id} marked merged"


def buzz_pr_open(repo_name: str, title: str, body: str, source_branch: str = "main", target_branch: str = "main") -> str:
    """Open a Buzz or GitHub PR."""
    if _is_github(repo_name):
        source = source_branch if source_branch and source_branch != "main" else _github_branch()
        result = subprocess.run(
            ["gh", "pr", "create", "--title", title, "--body", body, "--base", target_branch, "--head", source],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            shell=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gh pr create failed: {result.stderr.strip() or result.stdout.strip()}")
        return result.stdout.strip()

    env = _buzz_env()
    owner_hex = _pubkey_hex(env["NOSTR_PRIVATE_KEY"])
    repo_url = f"{DEFAULT_RELAY_HTTP}/git/{owner_hex}/{repo_name}"
    cli = env.get("BUZZ_CLI_PATH", str(REPO_ROOT / "buzz" / "target" / "debug" / "buzz.exe"))
    result = subprocess.run(
        [cli, "pr", "open", "--repo", repo_url, "--title", title, "--body", body,
         "--source", source_branch, "--target", target_branch],
        env=env,
        capture_output=True,
        text=True,
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"buzz pr open failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: buzz_git.py <push|commit|merge|pr-open> ...")
        return 1

    action = sys.argv[1]
    try:
        if action == "push":
            repo = sys.argv[2]
            branch = sys.argv[3] if len(sys.argv) > 3 else "main"
            print(git_push(REPO_ROOT, repo, branch=branch))
        elif action == "commit":
            repo = sys.argv[2]
            message = sys.argv[3]
            branch = sys.argv[4] if len(sys.argv) > 4 else "main"
            print(git_commit_and_push(REPO_ROOT, repo, message, branch=branch))
        elif action == "merge":
            pr_event_id = sys.argv[2]
            print(buzz_merge_pr(pr_event_id))
        elif action == "pr-open":
            repo = sys.argv[2]
            title = sys.argv[3]
            body = sys.argv[4]
            print(buzz_pr_open(repo, title, body))
        else:
            print(f"unknown action: {action}")
            return 1
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
