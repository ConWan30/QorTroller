# Make the governance gates blocking on `main` (DRAFT — operator-applied)

**Status:** DRAFT. This is a proposed repo-admin change, not applied. Changing
branch-protection rules on the public default branch is an operator action.

## Why

The governance gates are **advisory at merge time**, so red PRs have merged into
`main` repeatedly and left the branch red on its own integrity checks:

| PR | What merged red |
|----|-----------------|
| #29 | Mythos gate (2 unregistered crypto tags: `VAPI-RETINA-STATE-v1`, `VAPI-COMPOSABLE-CLAIM-v1`) |
| #41 | Mythos + PV-CI (`INV-W3S-006` digest drift, `VAPI-RETINA-STATE-v2`, `VAPI-RETINA-EVENT-LINE-v1`) |
| #42 | Mythos + PV-CI |
| #43 | Mythos |

Each required a follow-up fix (#30, #46) to re-green `main`. The gate *design* is
sound; the gate *enforcement* is missing. Making the gates **required status
checks** converts catch-and-patch into catch-and-block — the gate stops the merge
instead of recording the breach after the fact.

## What to require

Block merges to `main` unless these checks pass (exact check names as they appear
in CI):

- `PV-CI: 26 Protocol Invariants` — the invariant allowlist gate (digest-pinned)
- `Mythos PR Gate (Frozen + Crypto)` — FROZEN-v1 + crypto-drift audit
- `Path Scope Gate (CODEOWNERS enforcement)`

Plus: require a PR before merging (no direct pushes to `main`), and require the
branch to be up to date before merge (so a check can't pass against stale base).

**Deliberately NOT required yet:** `CI Matrix (...)`. The matrix has an
environmental dependency (the W3bstream AssemblyScript toolchain) that is being
fixed separately; add it as a required check only after it is reliably green, or
red-but-environmental matrix runs will block all merges. Promote it once stable.

## How to apply (operator runs)

```bash
# Requires admin on ConWan30/QorTroller. Review names against a recent PR's
# `gh pr checks <n>` output before applying — check names must match exactly.
gh api -X PUT repos/ConWan30/QorTroller/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -f 'required_status_checks[strict]=true' \
  -f 'required_status_checks[contexts][]=PV-CI: 26 Protocol Invariants' \
  -f 'required_status_checks[contexts][]=Mythos PR Gate (Frozen + Crypto)' \
  -f 'required_status_checks[contexts][]=Path Scope Gate (CODEOWNERS enforcement)' \
  -f 'enforce_admins=false' \
  -f 'required_pull_request_reviews[required_approving_review_count]=0' \
  -f 'restrictions=' \
  -F 'required_linear_history=false' \
  -F 'allow_force_pushes=false' \
  -F 'allow_deletions=false'
```

Notes:
- `enforce_admins=false` lets the operator override in a genuine emergency; set
  `true` to bind admins too (recommended once the workflow is trusted).
- `required_approving_review_count=0` keeps the solo-operator flow but still forces
  the status checks; raise to `1` if a reviewer is added.
- Verify afterward: `gh api repos/ConWan30/QorTroller/branches/main/protection`.

## Expected effect

After this, a PR that trips PV-CI or Mythos **cannot be merged** until reconciled
(register the tag in `_KNOWN_CAPABILITY_TAGS`, or reconcile the allowlist digest
via `--generate`). The red-merge pattern ends structurally rather than by repeated
cleanup PRs.
