"""Tests for scripts/vapi_path_scope_gate.py — Phase O0 path-scope CI gate.

Covers the V5 scenarios from Pass 2C Section 5.2 + the gate-internal
unit checks (normalize_author, path_matches_pattern, parse_codeowners
rule count) called out by the implementation prompt.

The tests exercise the gate against the actual CODEOWNERS file at
.github/CODEOWNERS (commit cdfa0ae6). If CODEOWNERS structure changes
in a future phase, these tests must be updated to match.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add scripts/ to sys.path so we can import the gate module directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import vapi_path_scope_gate as gate  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Fixture helper
# ─────────────────────────────────────────────────────────────────

def _rules():
    """Parse the live CODEOWNERS file each test references."""
    return gate.parse_codeowners()


# ─────────────────────────────────────────────────────────────────
# V5 test scenarios — author-vs-path scope checks
# ─────────────────────────────────────────────────────────────────

def test_human_operator_bypasses_gate():
    """Human authors (no [bot] suffix) bypass enforcement entirely.

    Phase O0 semantic per Pass 2A V5 Option B and Pass 2C Section 5.2:
    the gate constrains agents only. ConWan30 is a human; no [bot]
    suffix; bypass triggers and produces zero violations regardless of
    which paths the commit touches — INCLUDING paths in agent lanes
    that would otherwise be violations under strict enforcement.

    The test deliberately includes wiki/phases/p1.md (Sentry's lane)
    and audits/foo.md (Guardian's lane) to prove the bypass triggers
    BEFORE CODEOWNERS lookup, not because catch-all wins (catch-all
    no longer wins for those paths under the corrected CODEOWNERS).
    """
    rules = _rules()
    paths = [
        "bridge/main.py",                 # catch-all path
        "wiki/phases/p1.md",              # Sentry's lane (would violate if enforced)
        "audits/foo.md",                  # Guardian's lane (would violate if enforced)
        "contracts/contracts/Foo.sol",    # catch-all path
        "some/random/new/path.txt",       # catch-all path
    ]
    violations = gate.check_scope("ConWan30", paths, rules)
    assert violations == [], (
        f"human bypass should produce zero violations, got: {violations}"
    )


def test_unknown_bot_still_enforced():
    """Authors with [bot] suffix that aren't in CODEOWNERS get enforced.

    A bot identity unknown to CODEOWNERS (e.g., a malicious or
    misconfigured bot) ends in [bot] so bypass does NOT trigger. The
    gate runs enforcement; since the unknown bot is in no owners list,
    every modified path violates.
    """
    rules = _rules()
    violations = gate.check_scope(
        "random-stranger-bot[bot]",
        ["wiki/phases/p1.md"],
        rules,
    )
    assert len(violations) == 1
    assert violations[0]["author"] == "random-stranger-bot"


def test_sentry_can_commit_to_wiki_phases():
    """Sentry's lane includes wiki/ recursively. Uses [bot] suffix so
    enforcement runs (without it, the human-bypass would short-circuit)."""
    rules = _rules()
    violations = gate.check_scope(
        "vapi-anchor-sentry[bot]",
        ["wiki/phases/p1.md", "wiki/proposals/foo.md"],
        rules,
    )
    assert violations == []


def test_sentry_rejected_from_audits():
    """audits/ is Guardian's lane; Sentry must be rejected."""
    rules = _rules()
    violations = gate.check_scope(
        "vapi-anchor-sentry[bot]", ["audits/foo.md"], rules,
    )
    assert len(violations) == 1
    assert violations[0]["path"] == "audits/foo.md"
    assert violations[0]["matched_pattern"] == "audits/"
    assert violations[0]["author"] == "vapi-anchor-sentry"
    assert "vapi-guardian" in violations[0]["expected_owners"]


def test_guardian_can_commit_to_audits():
    """Guardian's lane includes audits/, sweeps/, ops/, invariants/."""
    rules = _rules()
    violations = gate.check_scope(
        "vapi-guardian[bot]",
        ["audits/foo.md", "sweeps/bar.md", "ops/baz.md", "invariants/qux.md"],
        rules,
    )
    assert violations == []


def test_guardian_rejected_from_wiki_phases():
    """wiki/ is Sentry's lane; Guardian must be rejected."""
    rules = _rules()
    violations = gate.check_scope(
        "vapi-guardian[bot]", ["wiki/phases/p1.md"], rules,
    )
    assert len(violations) == 1
    assert violations[0]["matched_pattern"] == "wiki/"
    assert violations[0]["author"] == "vapi-guardian"


def test_bot_identity_normalization_resolves_to_slug():
    """vapi-anchor-sentry[bot] should normalize to vapi-anchor-sentry."""
    rules = _rules()
    violations = gate.check_scope(
        "vapi-anchor-sentry[bot]", ["wiki/phases/p1.md"], rules,
    )
    assert violations == []


def test_guardian_bot_identity_normalization():
    """vapi-guardian[bot] should normalize to vapi-guardian."""
    rules = _rules()
    violations = gate.check_scope(
        "vapi-guardian[bot]", ["audits/foo.md"], rules,
    )
    assert violations == []


def test_multi_file_mixed_scope_rejected_when_any_out_of_scope():
    """One in-scope file + one out-of-scope file = reject (any violation fails)."""
    rules = _rules()
    violations = gate.check_scope(
        "vapi-anchor-sentry[bot]",
        ["wiki/phases/p1.md", "audits/foo.md"],
        rules,
    )
    assert len(violations) == 1
    assert violations[0]["path"] == "audits/foo.md"


def test_engine_managed_special_case_overrides_sentry_lane():
    """wiki/contradictions.md is in the special-case block (last-match-wins).

    Sentry would own it under the wiki/ rule, but the later
    wiki/contradictions.md @ConWan30 rule overrides. Sentry rejected.
    """
    rules = _rules()
    violations = gate.check_scope(
        "vapi-anchor-sentry[bot]", ["wiki/contradictions.md"], rules,
    )
    assert len(violations) == 1
    assert violations[0]["matched_pattern"] == "wiki/contradictions.md"
    assert violations[0]["expected_owners"] == ["ConWan30"]


def test_engine_managed_special_case_owned_by_human():
    """ConWan30 owns all 6 special-case engine-managed wiki files."""
    rules = _rules()
    paths = [
        "wiki/contradictions.md",
        "wiki/log.md",
        "wiki/index.md",
        "wiki/blocked_updates.md",
        "wiki/snapshots.md",
        "wiki/lint_report.md",
    ]
    violations = gate.check_scope("ConWan30", paths, rules)
    assert violations == []


def test_catch_all_routes_uncategorized_paths_to_human():
    """Paths under no explicit lane fall through to '*' @ConWan30."""
    rules = _rules()
    violations = gate.check_scope(
        "ConWan30",
        ["bridge/some/path.py", "contracts/Foo.sol", "scripts/util.py"],
        rules,
    )
    assert violations == []


def test_sentry_rejected_from_catch_all_path():
    """Catch-all assigns to ConWan30; Sentry has no scope on bridge/."""
    rules = _rules()
    violations = gate.check_scope(
        "vapi-anchor-sentry[bot]", ["bridge/some/path.py"], rules,
    )
    assert len(violations) == 1
    assert violations[0]["matched_pattern"] == "*"


# ─────────────────────────────────────────────────────────────────
# normalize_author unit tests
# ─────────────────────────────────────────────────────────────────

def test_normalize_author_strips_bot_suffix():
    assert gate.normalize_author("vapi-anchor-sentry[bot]") == "vapi-anchor-sentry"
    assert gate.normalize_author("vapi-guardian[bot]") == "vapi-guardian"


def test_normalize_author_case_insensitive_bot_suffix():
    assert gate.normalize_author("foo[BOT]") == "foo"
    assert gate.normalize_author("foo[Bot]") == "foo"


def test_normalize_author_strips_at_prefix():
    assert gate.normalize_author("@ConWan30") == "ConWan30"


def test_normalize_author_leaves_plain_username():
    assert gate.normalize_author("ConWan30") == "ConWan30"


def test_normalize_author_handles_empty_input():
    assert gate.normalize_author("") == ""


def test_normalize_author_strips_at_prefix_and_bot_suffix():
    """Belt-and-suspenders: @vapi-anchor-sentry[bot] -> vapi-anchor-sentry."""
    assert gate.normalize_author("@vapi-anchor-sentry[bot]") == "vapi-anchor-sentry"


# ─────────────────────────────────────────────────────────────────
# path_matches_pattern unit tests
# ─────────────────────────────────────────────────────────────────

def test_path_matches_pattern_directory_shorthand():
    assert gate.path_matches_pattern("wiki/phases/p1.md", "wiki/")
    assert gate.path_matches_pattern("wiki/foo.md", "wiki/")
    assert not gate.path_matches_pattern("audits/foo.md", "wiki/")


def test_path_matches_pattern_exact_file():
    assert gate.path_matches_pattern("wiki/contradictions.md", "wiki/contradictions.md")
    assert not gate.path_matches_pattern(
        "wiki/contradictions_v2.md", "wiki/contradictions.md",
    )


def test_path_matches_pattern_recursive_glob():
    assert gate.path_matches_pattern("wiki/phases/p1.md", "wiki/**")
    assert gate.path_matches_pattern("wiki/foo.md", "wiki/**")
    assert not gate.path_matches_pattern("audits/foo.md", "wiki/**")


def test_path_matches_pattern_wildcard_catch_all():
    assert gate.path_matches_pattern("any/path/here.txt", "*")
    assert gate.path_matches_pattern("a", "*")


# ─────────────────────────────────────────────────────────────────
# CODEOWNERS structure assertion
# ─────────────────────────────────────────────────────────────────

def test_codeowners_parses_14_rules():
    """CODEOWNERS at cdfa0ae6 has 14 rules (3 Sentry + 4 Guardian + 6 special-case + 1 catch-all)."""
    rules = _rules()
    assert len(rules) == 14, f"expected 14 rules, got {len(rules)}"


def test_codeowners_first_rule_is_catch_all():
    """Catch-all '*' must be FIRST so subsequent specific rules override
    it under GitHub's last-match-wins semantics.

    Per the corrected CODEOWNERS structure (commit 90c410d5 onward),
    the catch-all is intentionally placed first so agent lane rules
    that follow can take precedence for paths under their lanes.
    Reversing this ordering would defeat the entire lane-discipline
    system (the bug fixed in commit 90c410d5).
    """
    rules = _rules()
    first_pattern, first_owners = rules[0]
    assert first_pattern == "*"
    assert first_owners == ["ConWan30"]


def test_codeowners_special_cases_after_sentry_lane():
    """Special-case wiki/contradictions.md must come AFTER wiki/ Sentry lane.

    This ordering is what makes last-match-wins correctly assign the
    engine-managed file to ConWan30 instead of Sentry.
    """
    rules = _rules()
    patterns = [p for p, _ in rules]
    sentry_wiki_idx = patterns.index("wiki/")
    special_case_idx = patterns.index("wiki/contradictions.md")
    assert special_case_idx > sentry_wiki_idx, (
        f"wiki/contradictions.md (idx={special_case_idx}) must come after "
        f"wiki/ (idx={sentry_wiki_idx}) for last-match-wins to apply"
    )
