---
name: audit-drafting
description: Draft audit entries documenting findings, contradictions, and operational drift. Guardian-specific. Audit drafts land at O1 in side channel; PRs land at O2.
---

## Purpose

Guardian's role is operational stewardship — observing FSCA contradictions, sweep failures, invariant gate findings, autoresearch evaluations — and producing audit entries that document the protocol's health over time.

This skill produces those audit entries as Markdown documents in `audits/` lane. Each entry has a structured shape: finding category, evidence (file:line citations + on-chain queries), agents involved, reproduction path, resolution status.

## Activation phase availability

**O0 (DORMANT)**: Skill defined, not invoked.

**O1 (Shadow Mode)**: Guardian drafts audit entries as Markdown content held in a side-channel artifact (e.g., `audits/draft/<id>.md` or external review queue). Operator reviews each draft; no commits to `audits/` lane in repo.

**O2 (Suggestion Mode)**: Approved drafts become PRs targeting `audits/<finding-category>/<entry-id>.md`. PR merges (operator-approved) land the audit entry as a permanent record. PHYSICAL_DATA_ATTESTATION v1 anchors the audit's content hash on `AgentAdjudicationRegistry` via `attestation_type=AUDIT_ENTRY` (vocabulary expansion required if not already defined; governance event per Pass 2C Section 10 Note 3).

## Skill scope

- Compose audit entry Markdown per template (finding, evidence, agents, reproduction, resolution).
- Cite file:line evidence with byte-exact source from `repo-inspection` snapshots.
- Cite on-chain state with block number from `on-chain-state-querying` results.
- Reference upstream FSCA contradiction rule names (e.g., `RENEWAL_WITHOUT_ATTESTATION`) when the audit responds to FSCA findings.
- At O2: produce PR draft with appropriate base branch and CODEOWNERS-required reviewers.

## Skill boundaries

- **Guardian-only.** Sentry does not invoke this skill.
- **Lane discipline.** Audit entries land in `audits/`. Cross-lane content (e.g., a wiki/ proposal that triggered the audit) is referenced, not duplicated.
- **No automatic resolution claims.** Audits document findings; resolution decisions remain operator-led. Guardian may *propose* resolution but never *commits* a resolution claim.
- **No PR merge.** Guardian drafts PRs; operators merge.

## Composing tools

- [`repo-inspection`](../repo-inspection/SKILL.md) (composed)
- [`on-chain-state-querying`](../on-chain-state-querying/SKILL.md) (composed)
- [`audit-log-query`](../../tools/audit-log-query.md) (composed at O2 — citing recent AuditLog checkpoints)
- [`audit-entry-draft`](../../tools/audit-entry-draft.md) (tool, O1 + O2)
- [`git-operations`](../../tools/git-operations.md) (O2 only — for PR draft lifecycle)

## Verification considerations

- Each audit entry includes a `_verification` block with the HEAD commit at draft time, the on-chain block number queried, and the reproduction path operator can follow.
- Operator can re-derive the finding by replaying the reproduction path; audits MUST be reproducible.

## Failure modes

- **Evidence file not at cited line**: source has changed since draft was composed. Skill surfaces stale-evidence finding; operator decides whether to refresh draft or note version-skew explicitly.
- **CODEOWNERS reject**: PR targets a path Guardian's lane doesn't cover. Skill surfaces as lane-violation finding pre-PR-creation; suggests cross-lane coordination through operator.
- **FSCA rule not found**: cited contradiction rule name is unrecognized. Skill surfaces (suggests bridge-side schema audit).
