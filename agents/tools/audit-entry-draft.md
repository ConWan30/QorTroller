# audit-entry-draft

## Purpose

Compose audit entry Markdown content per Guardian's audit template. **Guardian-specific.** The drafting tool produces content; commit/PR fires via separate tools.

## Activation phase availability

- **O0**: Tool defined, agents DORMANT.
- **O1**: Active. Produces draft Markdown content held in side-channel artifact for operator review.
- **O2**: Active. Drafted content becomes the body of a PR targeting `audits/<category>/<entry-id>.md`.

## Tool definition

| Operation | Inputs | Outputs | Activation |
|-----------|--------|---------|------------|
| `compose(finding_category, evidence_citations, agents_involved, reproduction_path, recommended_resolution)` | Category string; list of (file, line) tuples; list of agent_ids; reproduction text; resolution text | Markdown body string + suggested filename | O1+ |
| `compose_from_fsca(fsca_rule_name, contradiction_id)` | FSCA rule name; contradiction ID from fleet_coherence_log | Markdown body pre-populated from FSCA finding | O1+ |

## Error handling

- **Evidence citation file not found**: tool refuses to compose; caller must refresh evidence.
- **Lane violation in evidence_citations**: any cited file outside `audits/sweeps/ops/invariants/` lane MUST be cited as cross-lane reference (not as in-lane evidence). Tool enforces.
- **`agents_involved` includes unregistered agent**: surfaces as finding; allows draft to proceed with explicit "unregistered agent" annotation.
- **Recommended resolution exceeds Guardian's authority**: surfaces (Guardian proposes, operator decides; resolutions that imply commit-merge or contract changes are out of Guardian's lane).

## Composability

Composed by:
- [`audit-drafting`](../skills/audit-drafting/SKILL.md) (skill, Guardian)

## Examples

```python
# Guardian drafts an audit entry from a FSCA contradiction
draft_md, filename = compose_from_fsca(
    fsca_rule_name="RENEWAL_WITHOUT_ATTESTATION",
    contradiction_id="coh_a1b2c3d4e5f67890"
)
# draft_md held in side channel at O1; becomes PR body at O2
```
