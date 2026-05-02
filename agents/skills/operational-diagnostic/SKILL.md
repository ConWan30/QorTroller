---
name: operational-diagnostic
description: Diagnose operational health signals — FSCA contradictions, sweep results, invariant gate failures, capture metrics. Guardian-specific. Read-only at O1; report inputs to audit-drafting at O2.
---

## Purpose

Operational stewardship requires continuously diagnosing the protocol's health: which FSCA rules are firing, which sweeps are stale, which invariants are at risk, what the live grind metrics show. This skill performs those diagnostics by reading from bridge endpoints, store tables, and on-chain state.

The output is a diagnostic report that informs `audit-drafting` and that operators consult for situational awareness.

## Activation phase availability

**O0 (DORMANT)**: Skill defined; bridge endpoints exist (Stream 4-prep Session 2 added 5 audit endpoints) but no agent token issued.

**O1 (Shadow Mode)**: Guardian queries the 5 read-only audit endpoints (`/agent/agent-*` per Stream 4-prep) and produces structured diagnostic reports in side-channel artifacts. Operator reviews. No writes.

**O2 (Suggestion Mode)**: Diagnostic reports become inputs to `audit-drafting` PRs. The diagnostic skill itself remains read-only; the audit-drafting skill consumes diagnostic output and produces the PR.

## Skill scope

- Query bridge audit endpoints (`/agent/agent-*` paths) for FSCA contradictions, sweep status, autoresearch evaluations, capture-health summaries.
- Query on-chain state via [`audit-log-query`](../../tools/audit-log-query.md) for AuditLog checkpoint freshness.
- Cross-reference findings: e.g., FSCA `RENEWAL_WITHOUT_ATTESTATION` rule fired N times in past 24h, AuditLog checkpoint frozen at age T → diagnostic flag.
- Produce structured report: finding category, severity, evidence pointers, recommended next action.

## Skill boundaries

- **Guardian-only.** Sentry does not invoke.
- **Read-only.** Diagnostics produce reports; resolution actions are downstream skills + operator decisions.
- **No FSCA rule modification.** This skill consumes FSCA outputs; FSCA rule definition remains in `bridge/vapi_bridge/fleet_signal_coherence_agent.py` and is governed by PV-CI gate.
- **Lane discipline.** Diagnostic report scope is `audits/sweeps/ops/invariants/` lane content + bridge operational state. Sentry lane content is referenced as cross-lane only.

## Composing tools

- [`iotex-rpc-query`](../../tools/iotex-rpc-query.md) (for on-chain state checks)
- [`audit-log-query`](../../tools/audit-log-query.md)
- HTTP client for bridge audit endpoints (introduced via tools at P1+; Phase O0 ships endpoints but no agent-side client wrapper)

## Verification considerations

- Diagnostic report includes timestamp + bridge endpoint version per response so operator can replay queries.
- Report's recommended next actions cite specific FSCA rule names + AuditLog checkpoint IDs for reproducibility.

## Failure modes

- **Bridge endpoint unreachable**: skill surfaces; report degrades gracefully (continues with on-chain-only diagnostics if possible).
- **Token missing or expired**: agent doesn't have OAuth token (P1 prep work pending). Skill surfaces explicitly rather than silent-failing.
- **FSCA rule output schema drift**: skill detects schema mismatch and surfaces as finding (suggests bridge-side schema audit).
- **All diagnostic sources unreachable**: skill produces an explicit "no diagnostic data" report rather than silently empty output.
