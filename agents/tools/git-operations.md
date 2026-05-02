# git-operations

## Purpose

Read git state and (at O2) produce git commits via the agent's GitHub App identity. Composes signing capability ([`kms-sign`](kms-sign.md)) with git plumbing.

## Activation phase availability

- **O0**: Tool defined, agents DORMANT, no invocations.
- **O1**: Read subset only — `git log`, `git diff`, `git status`, `git show`, `git rev-parse`. No `git add`, `git commit`, `git push`.
- **O2**: Read subset + `git add` (lane-scoped) + `git commit` (signed via `kms-sign` + GitHub App auth) + PR creation via `gh pr create`. Direct push to `main` is NEVER permitted; merges happen via operator-approved PRs.

## Tool definition

| Operation | Inputs | Outputs | Activation |
|-----------|--------|---------|------------|
| `git_log(path, n)` | Lane-scoped path; entry count | Commit list (sha, author, message, timestamp) | O1+ |
| `git_diff(ref_a, ref_b, path)` | Two refs; lane-scoped path | Unified diff text | O1+ |
| `git_status()` | None | Working tree status (porcelain format) | O1+ |
| `git_show(commit, path)` | Commit SHA; lane-scoped path | File content at commit | O1+ |
| `git_add(path)` | Lane-scoped path | None (side effect: stage file) | O2 only |
| `git_commit(message, signing_key_alias)` | Commit message; KMS key alias | Commit SHA | O2 only |
| `gh_pr_create(base, title, body)` | Base branch (always main); PR title + body | PR URL | O2 only |

## Error handling

- **Lane violation**: any operation on a path outside the agent's CODEOWNERS lane returns explicit error rather than executing. Sentry lane: `wiki/`, `provenance/`, `events/`. Guardian lane: `audits/`, `sweeps/`, `ops/`, `invariants/`.
- **Working tree dirty for read ops**: not an error; surfaced in result metadata.
- **Working tree dirty for write ops at O2**: ERROR — agent must not commit on top of unstaged operator work.
- **KMS sign fails (commit ops)**: commit aborts; agent surfaces.
- **Push attempt to main**: REFUSED; tool returns error explaining PR-only flow.
- **gh CLI not authenticated as the bot**: tool surfaces with hint to verify GitHub App installation token.

## Composability

Composed by:
- [`repo-inspection`](../skills/repo-inspection/SKILL.md) (read ops at O1+)
- [`audit-drafting`](../skills/audit-drafting/SKILL.md) at O2 (commit + PR ops)
- [`provenance-recording`](../skills/provenance-recording/SKILL.md) at O2 (commit + PR ops)

## Examples

```
# O1 read example
git_log(path="wiki/proposals/", n=10) → [(sha, author, message, ts), ...]

# O2 commit example (Sentry, after operator-approved draft)
git_add(path="provenance/sentry-attestations/SE-001.json")
git_commit(message="provenance(sentry): SE-001 attestation...", signing_key_alias="alias/vapi-anchor-sentry-signing")
gh_pr_create(base="main", title="provenance(sentry): SE-001", body="...")
```
