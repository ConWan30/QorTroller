# VSD Synthesizer — BOUNDARIES (what the editable orchestrator must never touch)

The loop runs unattended; these are the mechanical guardrails that keep it from running away.

The loop **NEVER**:
- edits `scripts/vapi_invariant_gate.py`, any FROZEN-v1 primitive, or the 228-byte PoAC wire.
- fires the `--confirm-governance` ceremony (unified-gate integration is operator-fired).
- spends IOTX, writes to chain, or mints NFTs (no Stream C / SOF fleet).
- loop-signs `decision` notes or any `eval/` re-freeze — those are operator-signed only.
- rewrites git history.

Reversible by construction: `rm -rf vsd-vault/{.vsd,notes,corpus,manifests/notes}` + `git revert`
returns to the pre-loop state. `eval/INVARIANTS.md` is the only ground truth; changing the
*enforced* invariant set is a methodology change (VSDIP), not an orchestrator edit.

The immutable harness is the checker; the orchestrator may improve HOW it synthesizes, never WHAT
counts as valid.
