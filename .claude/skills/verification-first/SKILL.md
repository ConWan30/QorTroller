---
name: verification-first
description: The V-check/P-check/hold discipline this repo uses for consequential work — new primitives, contract changes, invariant edits, multi-step commits. Read when starting architectural work, or when a verification claim is about to go into a commit message.
---

# Verification-first

The pattern that has shaped QorTroller's protocol commits. Six ordered steps:

1. **Pre-implementation verification (V-checks).** Read live state, confirm the
   brief's assumptions, name any drift between what was asked for and what the
   repo actually contains.
2. **Hold for operator review at the checkpoint.** Surface findings *including*
   drift. The operator decides: proceed, revise the brief, or abort.
3. **Implement** against the corrected brief.
4. **Post-implementation verification (P-checks).** Confirm the change matches
   intent and the tree is in the expected shape.
5. **Hold before staging.** No commit without explicit approval.
6. **Atomic commit with the architectural reasoning in the message body.**

The holds are not optional. The pattern fails closed if a checkpoint is skipped.

## Why it exists

Drift correction runs in both directions. V-checks catch a wrong assumption in
the prompt (the brief revises against reality); P-checks catch divergence during
execution (the implementation revises against the brief). Neither direction is
assumed correct by default.

It also puts reasoning somewhere durable. Decision blocks, rejected alternatives,
and "why this and not that" land in commit bodies — not in chat scrollback that
disappears at the next compaction.

## Verification claims are load-bearing

**Do not write a verification claim you did not actually run.** This has bitten
this repo concretely: a commit message claimed "full-suite collection clean
(6352 tests)" when only a narrow repro had been run. A real full-suite run later
showed 17 tests still failing. The fix was correct in shape and wrong in scope,
and the claim made it look settled.

Two habits that prevent it:

- **Force the failure you think you fixed.** Reproduce the actual failure mode
  before and after. For an environment you cannot run directly (a different
  Python version, another OS, a missing dependency), simulate the condition —
  monkeypatch `__import__` to raise, stub the missing module, pin the version.
  "The logic looks right" is weaker than "I made it fail, then made it stop."
- **Say what you ran, not what you believe.** If the full suite did not run, the
  commit says so. "Verified individually; full suite pending" is a fine claim.
  "Full suite clean" when it wasn't is not.

A narrow fix verified against one reproduction of a many-shaped bug can look
correct and still be wrong.

## Where it applies

Consequential architectural work: new primitives, contract changes, agent
additions, invariant edits, multi-step commits where the diff alone doesn't
carry the reasoning.

Where it doesn't: conversation, brainstorming, read-only information gathering,
operational coordination.

## Related

- `protocol-invariants` skill — what counts as a FROZEN surface
- `chain-spend` skill — the equivalent discipline for irreversible spend
- `docs/a2a/ci-debt/backlog.md` — a worked example of honest disclosure, including
  a recorded case of a wrong verification claim being corrected rather than quietly fixed
