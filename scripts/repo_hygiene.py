#!/usr/bin/env python3
"""
QorTroller repo hygiene tool
============================
Classifies untracked working-tree noise, proposes/applies .gitignore rules,
archives junk, and guards staged commits against forbidden content.

Design rules (do not weaken these):
  - Default invocation is READ-ONLY. Every mutating action is behind an
    explicit flag (--write-gitignore, --archive-junk).
  - Never delete files. --archive-junk MOVES files into archive/hygiene-*/
    with a JSONL manifest so every move is reversible.
  - Never touch tracked or modified files; only untracked paths are
    classified.
  - Skip files modified within --recent-hours (default 24) during archive
    actions, so live-session artifacts are never moved mid-write.

Modes:
  python scripts/repo_hygiene.py                  # report (read-only)
  python scripts/repo_hygiene.py --json           # machine-readable report
  python scripts/repo_hygiene.py --write-gitignore# append managed ignore block
  python scripts/repo_hygiene.py --archive-junk   # move pip-typo junk to archive/
  python scripts/repo_hygiene.py --check          # hygiene gate (exit 1 on fail)
  python scripts/repo_hygiene.py --check-staged   # pre-commit guard for `git diff --cached`

The --check-staged mode is intended for pre-commit wiring, e.g.:

  # .git/hooks/pre-commit
  python scripts/repo_hygiene.py --check-staged

It deliberately does NOT extend scripts/vapi_invariant_gate.py — the PV-CI
baseline is locked at 188 invariants and this tool keeps a separate failing
surface.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Managed .gitignore block ────────────────────────────────────────────────
# Idempotent: --write-gitignore skips if the begin marker is already present.
# Patterns are root-anchored or audits/-scoped and CANNOT match paths under
# solo/brp-renderer/ or frontend/src/brp/, so the end-of-file BRP
# last-match-wins exceptions in .gitignore remain effective (see the BRP
# comment blocks there for the fc89ae85 / 3dda7ae6 / beta-incorporation
# history). If you add a pattern here that could match a BRP path, move the
# block above those exceptions instead.
GITIGNORE_BEGIN = "# >>> repo-hygiene managed block (scripts/repo_hygiene.py) ---"
GITIGNORE_END = "# <<< repo-hygiene managed block ---"
GITIGNORE_RULES = [
    "# Local-only runtime/scratch artifacts. Root-anchored or audits/-scoped",
    "# by construction; cannot shadow the BRP exceptions above.",
    "/logs/",
    "/archive/",
    "/.qortroller/",
    "/.commit_msg.txt",
    "/.pr_body.txt",
    "/.qcheck.py",
    "/.qnim_final.txt",
    "/.qtemp.txt",
    "/nim_commit_message.txt",
    "/audits/rwm_*",
    "/audits/vss_seat_local_state.json",
    "/cfb_rwm_live_*.jsonl",
    "/ncaa27_live*.jsonl",
    "/session_*.jsonl",
    "/retina_daemon_*_utf8.txt",
    "/bridge/bridge_pid.txt",
]

# ── Classification rules ────────────────────────────────────────────────────
# Each rule: (bucket, regex on posix relative path, human reason).
# Buckets:
#   pip_typo         junk created by pip/install typos -> archive-junk
#   agent_scratch    per-session operator/agent scratch  -> gitignore
#   policy_local     local-only runtime data (AGENTS.md: never commit) -> gitignore
#   scratch_candidate ambiguous scratch code/data       -> report, operator decides
#   review           everything else (real WIP source/docs) -> report only
RULES: list[tuple[str, re.Pattern, str]] = [
    (r"pip_typo", re.compile(r"^=?\d+(\.\d+){1,3}$"), "pip/install typo artifact"),
    (r"agent_scratch", re.compile(
        r"^(\.commit_msg\.txt|\.pr_body\.txt|\.qcheck\.py|\.qnim_final\.txt|"
        r"\.qtemp\.txt|nim_commit_message\.txt|\.qortroller/?)$"),
     "agent/operator session scratch"),
    (r"policy_local", re.compile(
        r"^(audits/rwm_|audits/vss_seat_local_state\.json|cfb_rwm_live_.*\.jsonl|"
        r"ncaa27_live.*\.jsonl|session_\d+.*\.jsonl|retina_daemon_.*_utf8\.txt|"
        r"logs/?|bridge/bridge_pid\.txt)"),
     "local-only runtime data (AGENTS.md: never commit)"),
    (r"scratch_candidate", re.compile(
        r"^(buzz_explore\d?\.py|buzz_search\.json|buzz_meta\.json|mock_bridge\.py|"
        r"check_hw\.py|patch_qortroller\.py|block_repos\.json|test_bridge_load\.py|"
        r"_validate_determinism\.py|a2a_bus\.py|pnpm-lock\.yaml|"
        r"bridge/(fix_\w+\.py|trim_tail\.py)|scripts/_\w+\.py)$"),
     "ambiguous scratch — review before archive/promote"),
]

# Hard-fail staged-commit guard (AGENTS.md + .gitignore secrets policy).
# regex on staged path -> reason. Applied by --check-staged.
STAGED_FORBIDDEN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(^|/)audits/rwm_"), "RWM audit material (AGENTS.md: never commit)"),
    (re.compile(r"(^|/)cfb_rwm_live_.*\.jsonl$"), "live RWM capture"),
    (re.compile(r"(^|/)ea_buzz_bridge\.py$"), "compromised-key scratch file"),
    (re.compile(r"\.pem$"), "private key material"),
    (re.compile(r"accessKeys\.csv$"), "access-keys CSV"),
    (re.compile(r"\.nsec$"), "Nostr secret key"),
    (re.compile(r"(^|/)bridge_config\.json$"), "bridge secrets"),
    (re.compile(r"disaster-recovery-runbook\.private\.md$"), "private DR doc"),
    (re.compile(r"(^|/)(sessions|sessions_l9|poep_l9|bcc_l9|cocapture_l9|"
                r"retina_kf_crops|retina_kf_anchors|retina_kf_archive)/"),
     "local biometric/capture lane"),
    (re.compile(r"\.session\.json$"), "session state file"),
]

# Env-template allowlist mirrors the .gitignore negations.
ENV_TEMPLATE_OK = (".env.example", ".env.template")


def _git(args: list[str]) -> str:
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT)] + args,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def untracked_paths() -> list[str]:
    """Untracked, non-ignored paths from git status (dirs collapsed by git)."""
    out = _git(["status", "--porcelain=v1", "--untracked-files=normal"])
    return [line[3:] for line in out.splitlines() if line.startswith("?? ")]


def classify(path: str) -> tuple[str, str]:
    for bucket, pattern, reason in RULES:
        if pattern.match(path):
            return bucket, reason
    return "review", "unclassified — operator review"


def staged_violations() -> list[tuple[str, str]]:
    try:
        staged = [p for p in _git(["diff", "--cached", "--name-only"]).splitlines() if p]
    except RuntimeError:
        return []
    bad: list[tuple[str, str]] = []
    for p in staged:
        if p.endswith(ENV_TEMPLATE_OK):
            continue
        if re.search(r"(^|/)\.env(\.[^./]+)?$", p) and not p.endswith(ENV_TEMPLATE_OK):
            bad.append((p, "env file with potential secrets"))
            continue
        for pattern, reason in STAGED_FORBIDDEN:
            if pattern.search(p):
                bad.append((p, reason))
                break
    return bad


def _size_kb(path: str) -> int:
    p = REPO_ROOT / path
    try:
        if p.is_dir():
            total = 0
            for f in p.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
            return total // 1024
        return p.stat().st_size // 1024
    except OSError:
        return 0


def _mtime(path: str) -> float:
    try:
        return (REPO_ROOT / path).stat().st_mtime
    except OSError:
        return 0.0


def build_report() -> dict:
    entries = []
    for path in untracked_paths():
        bucket, reason = classify(path)
        entries.append({
            "path": path,
            "bucket": bucket,
            "reason": reason,
            "size_kb": _size_kb(path),
            "mtime": _mtime(path),
        })
    buckets: dict[str, list[dict]] = {}
    for e in entries:
        buckets.setdefault(e["bucket"], []).append(e)
    return {"generated": int(time.time()), "untracked_total": len(entries),
            "buckets": buckets}


def write_gitignore_block() -> int:
    """Append managed block to .gitignore unless marker already present."""
    gi = REPO_ROOT / ".gitignore"
    current = gi.read_text(encoding="utf-8")
    if GITIGNORE_BEGIN in current:
        print("managed block already present in .gitignore — nothing to do")
        return 0
    block = "\n".join([GITIGNORE_BEGIN] + GITIGNORE_RULES + [GITIGNORE_END, ""])
    gi.write_text(current.rstrip("\n") + "\n\n" + block, encoding="utf-8")
    print(f"appended managed block ({len(GITIGNORE_RULES)} comment+rule lines) to .gitignore")
    return 0


def archive_junk(recent_hours: float) -> int:
    """Move pip_typo junk (and nothing else) into archive/hygiene-<ts>/."""
    report = build_report()
    junk = [e["path"] for e in report["buckets"].get("pip_typo", [])]
    if not junk:
        print("no pip-typo junk found — nothing to archive")
        return 0
    cutoff = time.time() - recent_hours * 3600
    stale = [p for p in junk if _mtime(p) < cutoff]
    skipped = [p for p in junk if p not in stale]
    if skipped:
        print(f"skipped (modified within {recent_hours:.0f}h): {', '.join(skipped)}")
    if not stale:
        return 0
    dest_dir = REPO_ROOT / "archive" / f"hygiene-{time.strftime('%Y%m%d-%H%M%S')}"
    manifest = []
    for path in stale:
        src = REPO_ROOT / path
        dst = dest_dir / path.replace("=", "_eq_").lstrip("/")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        manifest.append({"from": path, "to": str(dst.relative_to(REPO_ROOT)),
                         "moved_at": int(time.time())})
        print(f"archived {path} -> {dst.relative_to(REPO_ROOT)}")
    mf = dest_dir / "manifest.jsonl"
    mf.write_text("\n".join(json.dumps(m) for m in manifest) + "\n", encoding="utf-8")
    print(f"manifest: {mf.relative_to(REPO_ROOT)} ({len(manifest)} move(s), reversible)")
    return 0


def run_check(max_untracked: int) -> int:
    """Hygiene gate: exit 1 on pip-typo junk or untracked-count regression."""
    report = build_report()
    failures = []
    for e in report["buckets"].get("pip_typo", []):
        failures.append(f"pip-typo junk present: {e['path']} (run --archive-junk)")
    total = report["untracked_total"]
    if total > max_untracked:
        failures.append(
            f"untracked count {total} exceeds budget {max_untracked} "
            f"(run report mode and archive/promote; then --write-gitignore)")
    if failures:
        print("HYGIENE FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"hygiene OK (untracked={total}, budget={max_untracked})")
    return 0


def run_check_staged() -> int:
    bad = staged_violations()
    if bad:
        print("STAGED-COMMIT GUARD FAIL:")
        for path, reason in bad:
            print(f"  - {path}: {reason}")
        return 1
    print("staged guard OK (no forbidden paths staged)")
    return 0


def print_report(report: dict) -> None:
    print(f"untracked (non-ignored) paths: {report['untracked_total']}")
    order = ["pip_typo", "agent_scratch", "policy_local", "scratch_candidate", "review"]
    for bucket in order:
        items = report["buckets"].get(bucket, [])
        if not items:
            continue
        total_kb = sum(i["size_kb"] for i in items)
        print(f"\n[{bucket}] {len(items)} path(s), {total_kb} KB — {items[0]['reason']}")
        for i in sorted(items, key=lambda x: -x["size_kb"]):
            age = time.strftime("%Y-%m-%d", time.localtime(i["mtime"]))
            print(f"  {i['size_kb']:>7} KB  {age}  {i['path']}")
    print("\nnext steps:")
    print("  --write-gitignore  ignore agent_scratch + policy_local buckets")
    print("  --archive-junk     move pip_typo bucket to archive/ (no deletes)")
    print("  scratch_candidate + review buckets stay untracked for operator review")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1].strip())
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--write-gitignore", action="store_true",
                    help="append managed ignore block for policy_local/agent_scratch")
    ap.add_argument("--archive-junk", action="store_true",
                    help="move pip-typo junk into archive/ (never deletes)")
    ap.add_argument("--check", action="store_true",
                    help="hygiene gate: exit 1 on junk or untracked-budget overrun")
    ap.add_argument("--check-staged", action="store_true",
                    help="pre-commit guard: exit 1 if staged paths are forbidden")
    ap.add_argument("--max-untracked", type=int, default=60,
                    help="untracked budget for --check (default 60; ~47 long-lived "
                         "review/scratch items + headroom for in-flight work)")
    ap.add_argument("--recent-hours", type=float, default=24.0,
                    help="skip files newer than this in archive actions (default 24)")
    args = ap.parse_args(argv)

    if args.write_gitignore:
        return write_gitignore_block()
    if args.archive_junk:
        return archive_junk(args.recent_hours)
    if args.check:
        return run_check(args.max_untracked)
    if args.check_staged:
        return run_check_staged()

    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
