#!/usr/bin/env python3
"""
vapi_path_scope_gate.py — Phase O0 path-scope CI gate

Enforces path-based ownership rules from .github/CODEOWNERS on every
pull request. Reads the PR author identity and modified file list,
matches each modified path against CODEOWNERS rules with last-match-wins
semantics, and rejects any PR where the author lacks scope for one or
more modified paths.

ARCHITECTURAL CONTEXT:

Pass 2A V5 Option B chose a separate focused script over extending the
existing PV-CI gate (vapi_invariant_gate.py). The two gates have different
canonical concerns:

  - vapi_invariant_gate.py — invariant fingerprinting (file-content
    digests against a frozen allowlist; tamper-evident governance event
    chain on changes).
  - vapi_path_scope_gate.py — path-author scope enforcement (which
    identity is authorized to touch which paths, per CODEOWNERS).

Mixing these into one gate would blur their canonical concerns and
increase the blast radius of any path-scope bug. CODEOWNERS at
.github/CODEOWNERS (commit cdfa0ae6) is the source of truth this gate
reads.

PHASE O0 STATUS:

The gate ships and runs in CI from this commit forward, but its
ENFORCEMENT applies vacuously until two activation conditions are met:

  1. GitHub Apps for vapi-anchor-sentry and vapi-guardian register
     (Phase O0 Section 6.3 work). Until then, those identities don't
     exist on GitHub and no PR can be authored under them.
  2. Branch protection on `main` enables CODEOWNERS-required reviewer
     enforcement (per Pass 2C Section 9 Question 4 — defense in depth).

Until activation completes, human operator commits pass via the
catch-all CODEOWNERS rule, and the test cases at
bridge/tests/test_vapi_path_scope_gate.py exercise the post-registration
enforcement scenarios.

USAGE:
    python scripts/vapi_path_scope_gate.py \\
        --pr-author <github-login> \\
        --modified-files <comma-separated-paths>

    # Or read modified files from stdin (one per line):
    git diff --name-only base..head | python scripts/vapi_path_scope_gate.py \\
        --pr-author <github-login>

EXIT CODES:
    0 — all paths in scope (gate passes)
    1 — one or more paths violate scope (gate fails)
    2 — invocation error (missing required argument, malformed input)

PATTERN SEMANTICS (subset of GitHub's CODEOWNERS spec implemented):
    "*"               — matches any path (catch-all)
    "wiki/"           — matches any file under wiki/ recursively
                        (directory shorthand)
    "wiki/**"         — synonym for "wiki/" (recursive glob form)
    "wiki/foo.md"     — exact file match
    Last-match-wins   — when multiple rules match, the latest one in
                        file order takes precedence.

BOT IDENTITY NORMALIZATION:
    GitHub Apps post commits as "<slug>[bot]" (e.g., vapi-anchor-sentry[bot]).
    CODEOWNERS lookup uses the bare slug ("vapi-anchor-sentry"). This
    script normalizes the [bot] suffix away before comparison so PR
    authors and CODEOWNERS owners can be compared directly.

ENFORCEMENT SCOPE — agents constrained, humans bypass:
    The gate enforces path-author scope only for GitHub App authors
    (identities ending in "[bot]"). Human authors bypass the gate's
    enforcement and flow through normal PR review.

    Rationale: per Pass 2A V5 Option B and Pass 2C Section 5.2, the
    gate's stated purpose is constraining agents to their lanes; human
    commits were never the enforcement target. The lane discipline
    encoded in CODEOWNERS reflects what the agents may write; humans
    operate above that discipline (they author CODEOWNERS itself, ship
    the implementation, and review what agents propose).

    During Phase O0 when GitHub Apps for vapi-anchor-sentry and
    vapi-guardian have not yet registered, the gate produces zero
    enforcement actions — every PR's author is a human and bypasses.
    The gate activates as enforcement only after Phase O0 Section 6.3
    completes and agents begin posting commits with the [bot] suffix.

    Branch protection's CODEOWNERS-required-reviewer enforcement
    (Pass 2C Question 4) is a separate layer that operates regardless
    of author and is governed by GitHub's own CODEOWNERS spec, not by
    this gate. The two layers compose: branch protection ensures
    CODEOWNERS-named reviewers approve PRs to their paths; this gate
    additionally constrains agent commit authors to their lanes.
"""

import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).parent.parent
CODEOWNERS_PATH = REPO_ROOT / ".github" / "CODEOWNERS"

_BOT_SUFFIX_RE = re.compile(r"\[bot\]$", re.IGNORECASE)


def normalize_author(author: str) -> str:
    """Strip [bot] suffix and leading @ for CODEOWNERS comparison.

    Examples:
      "vapi-anchor-sentry[bot]" -> "vapi-anchor-sentry"
      "@ConWan30"               -> "ConWan30"
      "ConWan30"                -> "ConWan30"
      ""                        -> ""
    """
    if not author:
        return ""
    s = author.strip()
    if s.startswith("@"):
        s = s[1:]
    s = _BOT_SUFFIX_RE.sub("", s)
    return s


def parse_codeowners(path: Path = CODEOWNERS_PATH) -> list[tuple[str, list[str]]]:
    """Parse CODEOWNERS into ordered list of (pattern, [normalized_owners]) tuples.

    Skips comment lines (starting with #) and blank lines. Preserves
    source order so callers can apply last-match-wins by iterating
    forward and keeping the latest match.

    Lines with a path but no owner (which GitHub treats as "clear
    ownership") are skipped silently — they are not present in the
    Phase O0 CODEOWNERS file.
    """
    if not path.exists():
        return []
    rules: list[tuple[str, list[str]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue  # malformed line or ownership-cleared line; skip
        pattern = parts[0]
        owners = [normalize_author(o) for o in parts[1:]]
        rules.append((pattern, owners))
    return rules


def path_matches_pattern(path: str, pattern: str) -> bool:
    """Determine whether a file path matches a CODEOWNERS pattern.

    Implements the subset of GitHub's CODEOWNERS pattern syntax that
    Phase O0 CODEOWNERS uses:
      "*"          — matches any path
      "wiki/"      — directory shorthand (matches recursively)
      "wiki/**"    — recursive glob (synonym for directory shorthand)
      "wiki/foo.md" — exact file path match
    """
    p = pattern.strip()
    fp = path.strip().lstrip("/")
    if p == "*":
        return True
    if p.endswith("/**"):
        prefix = p[:-3].rstrip("/") + "/"
        return fp.startswith(prefix)
    if p.endswith("/"):
        return fp.startswith(p)
    return fp == p


def find_owner(
    path: str,
    rules: list[tuple[str, list[str]]],
) -> Optional[tuple[str, list[str]]]:
    """Apply last-match-wins to find the owning rule for a path.

    Iterates rules in source order; the LAST matching rule wins per
    GitHub's CODEOWNERS spec. Returns (pattern, [owners]) tuple, or
    None if no rule matched (which should not happen when a catch-all
    rule is present).
    """
    matched: Optional[tuple[str, list[str]]] = None
    for pattern, owners in rules:
        if path_matches_pattern(path, pattern):
            matched = (pattern, owners)
    return matched


def check_scope(
    pr_author: str,
    modified_paths: list[str],
    rules: list[tuple[str, list[str]]],
) -> list[dict]:
    """Check each modified path against the CODEOWNERS rules.

    Returns a list of violation dicts. Empty list means all paths in
    scope. Each violation dict carries the path, normalized author,
    matched pattern, expected owners, and a short reason string.

    Phase O0 semantic: gate enforces agent constraints only. Human
    authors (no [bot] suffix) bypass — they flow through normal PR
    review per Pass 2A V5 Option B and Pass 2C Section 5.2. See the
    module docstring's ENFORCEMENT SCOPE section for the rationale.
    """
    if not pr_author.strip().endswith("[bot]"):
        return []

    author_norm = normalize_author(pr_author)
    violations: list[dict] = []
    for path in modified_paths:
        rule = find_owner(path, rules)
        if rule is None:
            violations.append({
                "path": path,
                "author": author_norm,
                "expected_owners": [],
                "matched_pattern": None,
                "reason": "no matching CODEOWNERS rule (missing catch-all?)",
            })
            continue
        pattern, expected_owners = rule
        if author_norm not in expected_owners:
            violations.append({
                "path": path,
                "author": author_norm,
                "expected_owners": expected_owners,
                "matched_pattern": pattern,
                "reason": f"author '@{author_norm}' not in owners {expected_owners}",
            })
    return violations


def format_violations(violations: list[dict]) -> str:
    """Format violations as a human-readable failure report."""
    lines = ["[path-scope-gate] VIOLATIONS:"]
    for v in violations:
        lines.append(f"  {v['path']}")
        lines.append(f"    matched pattern: {v['matched_pattern']}")
        lines.append(f"    expected owners: {v['expected_owners']}")
        lines.append(f"    actual author:   @{v['author']}")
        lines.append(f"    reason:          {v['reason']}")
        lines.append(
            f"    remediation:     revert this change OR update "
            f".github/CODEOWNERS to grant @{v['author']} access "
            f"(governance review required)"
        )
    return "\n".join(lines)


def main() -> int:
    pr_author = ""
    modified_files_raw = ""
    codeowners_path = CODEOWNERS_PATH

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--pr-author":
            if i + 1 >= len(args):
                print(
                    "[path-scope-gate] ERROR: --pr-author requires a value",
                    file=sys.stderr,
                )
                return 2
            pr_author = args[i + 1]
            i += 2
        elif args[i] == "--modified-files":
            if i + 1 >= len(args):
                print(
                    "[path-scope-gate] ERROR: --modified-files requires a value",
                    file=sys.stderr,
                )
                return 2
            modified_files_raw = args[i + 1]
            i += 2
        elif args[i] == "--codeowners-path":
            if i + 1 >= len(args):
                print(
                    "[path-scope-gate] ERROR: --codeowners-path requires a value",
                    file=sys.stderr,
                )
                return 2
            codeowners_path = Path(args[i + 1])
            i += 2
        elif args[i] in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            print(
                f"[path-scope-gate] ERROR: unknown argument: {args[i]}",
                file=sys.stderr,
            )
            return 2

    if not pr_author:
        print(
            "[path-scope-gate] ERROR: --pr-author is required",
            file=sys.stderr,
        )
        return 2

    if modified_files_raw:
        modified_paths = [
            p.strip() for p in modified_files_raw.split(",") if p.strip()
        ]
    else:
        modified_paths = [line.strip() for line in sys.stdin if line.strip()]

    if not modified_paths:
        print("[path-scope-gate] PASS — no modified files (empty diff)")
        return 0

    rules = parse_codeowners(codeowners_path)
    if not rules:
        print(
            f"[path-scope-gate] ERROR: no rules parsed from {codeowners_path}",
            file=sys.stderr,
        )
        return 2

    violations = check_scope(pr_author, modified_paths, rules)
    author_norm = normalize_author(pr_author)

    if violations:
        print(format_violations(violations))
        print(
            f"\n[path-scope-gate] FAIL — "
            f"{len(violations)} path-scope violation(s) for @{author_norm}"
        )
        return 1

    print(
        f"[path-scope-gate] PASS — "
        f"{len(modified_paths)} file(s) all in scope for @{author_norm}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
