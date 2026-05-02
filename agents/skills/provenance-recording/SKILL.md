---
name: provenance-recording
description: Record provenance attestations via PHYSICAL_DATA_ATTESTATION v1 anchoring. Sentry-specific. Composes event-correlation outputs into on-chain attestations at O2.
---

## Purpose

Sentry's role is to bind off-chain content (wiki, provenance entries, events) to on-chain attestation chains. This skill produces those attestations using the PHYSICAL_DATA_ATTESTATION v1 primitive (Stream 3-prep Session 2, commit `412a6f0e`).

PDA v1 attestations make Sentry's stewardship cryptographically verifiable: any future auditor can replay the attestation and confirm Sentry asserted a specific provenance claim at a specific time.

## Activation phase availability

**O0 (DORMANT)**: Skill defined; AgentAdjudicationRegistry is LIVE (Stream 2-deploy at `0x4767c5Ab7ed705E810903BE764fa4090B639C10A`) but no agent identity is registered yet (Section 6.4 pending).

**O1 (Shadow Mode)**: Skill produces draft attestation tuples (hardware_data_hash, attestation_type, ts_ns) and signs them via [`cryptographic-signing`](../cryptographic-signing/SKILL.md). The signed draft is held in a side-channel artifact (e.g., `provenance/draft-attestations/<id>.json`) for operator review. **No on-chain anchor fires at O1.**

**O2 (Suggestion Mode)**: Approved drafts become PRs that, when merged by the operator, trigger on-chain anchoring via `chain.anchor_pda_attestation()`. The anchor binds (hardware_data_hash, agent_id, attestation_type_hash, ts_ns) on `AgentAdjudicationRegistry`.

## Skill scope

- Compute PHYSICAL_DATA_ATTESTATION v1 hash per the FROZEN-v1 formula:
  `SHA-256("VAPI-PHYSICAL-DATA-ATTESTATION-v1" || hardware_data_hash || agent_id || keccak256(attestation_type) || ts_ns_be)`
- Draft attestation metadata (attestation_type from canonical vocabulary: CORPUS_SNAPSHOT, PoAC_CHAIN_ROOT, FLEET_COHERENCE_OBSERVATION, etc.)
- Sign the hash via `cryptographic-signing` skill
- At O2: invoke [`pda-attestation-anchor`](../../tools/pda-attestation-anchor.md) tool to commit the on-chain anchor

## Skill boundaries

- **Sentry-only.** Guardian does not invoke this skill.
- **No actionType vocabulary expansion.** New attestation_type values require governance event per Pass 2C Section 10 Note 3.
- **No anchoring without operator-approved PR merge.** O2 anchoring fires only when a PR containing the draft attestation has been merged via operator approval.
- **Lane discipline.** Attestations bind content within Sentry's lane (wiki/provenance/events). Cross-lane attestations are out of scope.

## Composing tools

- [`cryptographic-signing`](../cryptographic-signing/SKILL.md) (skill, composed at O1+ for draft signing)
- [`pda-attestation-anchor`](../../tools/pda-attestation-anchor.md) (tool, O2 only) — invokes `chain.anchor_pda_attestation`
- [`git-operations`](../../tools/git-operations.md) (O2 only) — for the PR draft + commit lifecycle
- [`agent-registry-query`](../../tools/agent-registry-query.md) — verify agent_id resolves to a registered agent before producing attestation

## Verification considerations

- The hash formula is INV-PDA-001 + INV-PDA-002 frozen in `.github/INVARIANTS_ALLOWLIST.json`. Drift detected by PV-CI gate.
- Operator can verify any anchor via `AgentAdjudicationRegistry.isRecorded(commitment)` returning `true` and `getAnchor(commitment)` returning the expected metadata tuple.

## Failure modes

- **Anchor reverts (anti-replay)**: attestation hash already recorded. Skill surfaces; usually indicates duplicate draft slipped through review.
- **Lane violation in attestation content**: hardware_data_hash references content outside Sentry's lane. Skill rejects upstream.
- **CHAIN_SUBMISSION_PAUSED engaged**: bridge kill-switch active. Anchor call returns immediately; skill surfaces and waits for operator restoration.
- **Agent not registered**: `agent_id` does not resolve to a registered agent in `AgentRegistry`. Skill surfaces as a Section 6.4 prerequisite finding.
