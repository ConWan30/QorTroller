# VSD Eval Harness — Declarative Invariants (standalone loop core)

The human-readable ground truth enforced by `.vsd/vsd_eval_harness.py` (the executable form).
This is the synthesis-domain twin of `.github/INVARIANTS_ALLOWLIST.json`. The harness is
immutable in spirit; changes to the *enforced* set are methodology changes (VSDIP) — the
unified-gate integration of these into `scripts/vapi_invariant_gate.py` via the
`--confirm-governance` ceremony is a SEPARATE operator-fired step, deferred.

| ID | Invariant | Checked by the harness |
|----|-----------|------------------------|
| VSD-1 | Immutable harness gates an editable orchestrator | `vsd_eval_harness.py` is the checker; `vsd_synthesizer.py` is the only editable layer. |
| VSD-2 | Per-note Ed25519 provenance, deployer-anchored | every routine note (claim/ingredient/synthesis/pbsa) has a manifest that Ed25519-verifies against the architect key; decision notes carry a content-bound STUB manifest `signed:false, pending:operator` (the loop never forges the architect signature). |
| VSD-3 | Honesty fields are harness-checked, not advisory prose | claim/synthesis notes: `confidence` ∈ the 8 estimative words; `effort` integer minutes; `deployer` == bridge wallet. |
| VSD-4 | PBSA as native output | at least one `notes/pbsa/*.md` exists; the loop emits one per cycle. |
| VSD-5 | Corpus = harness-passing notes only | the harness reports the passing-note set; `vsd_synthesizer` regenerates `corpus/snapshot-*/` from passing notes only (drift in the vault deletes drift from the corpus on next regen). |

**The 8 estimative words (VSD-3 confidence domain):** certain · highly-likely · likely · possible ·
unlikely · highly-unlikely · almost-certainly-not · remote.

**Out of scope (operator-fired / deferred):** unified-gate integration (Stream B governance
ceremony), SOF NFT fleet + dual-anchor (Stream C, on-chain), MCP tools, store schema, VRR/CDRR.
