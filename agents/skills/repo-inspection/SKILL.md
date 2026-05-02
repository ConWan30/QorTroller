---
name: repo-inspection
description: Read-only inspection of the VAPI repository contents, git history, and file state. Both Sentry and Guardian invoke this skill when establishing context for any other skill.
---

## Purpose

Repo inspection is the foundational read-only skill that establishes situational awareness for all other agent operations. Before drafting an audit, recording provenance, or correlating events, the agent must know the current state of the repository: HEAD commit, modified files, lane-relevant content, recent commits in scope.

This skill does not write. It produces a situational snapshot that other skills consume.

## Activation phase availability

**O0 (DORMANT)**: Skill defined, not invoked. Agents do not run.

**O1 (Shadow Mode)**: Read-only invocation. Agent enumerates repo state and produces a side-channel snapshot (JSON or structured text) captured for operator inspection. No commits, no writes.

**O2 (Suggestion Mode)**: Same read-only invocation. Snapshots become inputs to draft-PR composition. The skill itself does not change behavior between O1 and O2; downstream skills change behavior.

## Skill scope

- Walk the working tree at HEAD; enumerate files within the agent's lane (Sentry: `wiki/`, `provenance/`, `events/`; Guardian: `audits/`, `sweeps/`, `ops/`, `invariants/`).
- Read git metadata: HEAD commit SHA, branch tracking state, recent commit log within lane.
- Read file content for files relevant to the current task; never read outside the agent's lane unless the task explicitly requires cross-lane context (which itself should be surfaced as a finding).
- Produce a structured snapshot the agent can reason over.

## Skill boundaries

- **No writes.** No `git add`, no `git commit`, no file edits. Pure read.
- **Lane discipline.** Sentry does not read Guardian's lane content for stewardship purposes; Guardian does not read Sentry's lane content for stewardship purposes. Cross-lane reads are surfaced explicitly when a finding spans both lanes (coordinated through the operator, not through agent-to-agent communication).
- **No external services.** This skill does not query GitHub APIs, IoTeX RPC, or any other off-machine service. Those are separate skills/tools.

## Composing tools

- [`git-operations`](../../tools/git-operations.md) (read subset only: `git log`, `git diff`, `git status`, `git show`)
- File read primitives (Glob, Grep, Read) — Phase O0 baseline tools per `.claude/agents/<agent>.md` definitions

## Verification considerations

- The snapshot's accuracy is verifiable by comparing the snapshot's HEAD commit SHA against `git rev-parse HEAD` at snapshot time.
- File content snippets included in the snapshot should preserve byte-exact source so downstream verification can re-read and confirm.

## Failure modes

- **Working tree dirty**: snapshot includes uncommitted modifications. Agent surfaces this as a finding rather than silently treating dirty state as canonical.
- **Lane boundary violation**: agent attempts to read outside its CODEOWNERS lane. Skill MUST refuse and surface the violation rather than silently proceed.
- **File read error**: large file or permission issue. Skill records the error in the snapshot rather than retrying or aborting.
