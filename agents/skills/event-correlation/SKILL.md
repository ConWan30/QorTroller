---
name: event-correlation
description: Correlate off-chain events (wiki edits, provenance entries, event log additions) into causal sequences for Sentry's stewardship lane. Sentry-specific.
---

## Purpose

Sentry's stewardship lane (`wiki/`, `provenance/`, `events/`) accumulates discrete events that have causal relationships: a wiki proposal cites a provenance entry which references an event log row which traces back to an on-chain anchor. Event correlation walks these relationships and produces causal chain summaries.

Without correlation, the events are discrete data points; with correlation, they become a navigable provenance graph that downstream skills can attest.

## Activation phase availability

**O0 (DORMANT)**: Skill defined, not invoked.

**O1 (Shadow Mode)**: Active. Sentry walks event sequences and produces correlation graphs in side-channel snapshots. Operator reviews; no commits.

**O2 (Suggestion Mode)**: Active. Correlation graphs become inputs to `provenance-recording` skill which anchors them via PHYSICAL_DATA_ATTESTATION v1. The correlation work happens at draft time; the anchor happens at commit time.

## Skill scope

- Walk wiki/ proposals and identify cross-references (markdown links, line citations).
- Walk provenance/ entries and identify parent-child relationships.
- Walk events/ log rows (when events/ infrastructure exists in P1+) and identify temporal sequences.
- Produce a causal graph (DAG) with nodes = events and edges = "X references Y" / "X causally depends on Y".
- Surface temporal inversions (B references A but B was created before A) as findings.

## Skill boundaries

- **Lane discipline.** Sentry's lane only. Does not correlate events in `audits/`, `sweeps/`, `ops/`, or `invariants/` (those are Guardian's lane).
- **No semantic interpretation.** The skill identifies references and temporal order; it does not infer intent or meaning.
- **No automatic resolution of inconsistencies.** Surfaces inversions and contradictions as findings; operator decides resolution.

## Composing tools

- [`repo-inspection`](../repo-inspection/SKILL.md) (composed; reads wiki/, provenance/, events/ within lane)
- [`iotex-rpc-query`](../../tools/iotex-rpc-query.md) (optional; for events that reference on-chain state)

## Verification considerations

- The correlation graph is reproducible: given the same HEAD commit and the same lane content, the skill produces the same graph.
- Graph nodes include source line citations (`wiki/proposals/X.md:42`) so operator can verify each correlation manually.

## Failure modes

- **Broken reference**: link points to non-existent file or line. Surfaced as finding; correlation graph includes a "broken-edge" annotation.
- **Cyclic dependency**: rare but possible in cross-referenced wiki content. Surfaced as finding; cycle nodes annotated.
- **Cross-lane reference**: a wiki/ proposal cites an audits/ entry. Skill records the cross-lane edge but does not traverse into Guardian's lane content; surfaces as a coordination point for operator review.
