# VSD synthesis loop skill (`/vsd-loop`, `@vsd-synthesis-loop`)

Editable orchestrator for the self-verifying methodology loop. The **immutable** checker is
`vsd-vault/.vsd/vsd_eval_harness.py`; mutation runs through `vsd_synthesizer.py` only.

## When to use

- Ingest protocol architecture into the vault (claim → synthesis notes + PBSA).
- Run a numbered cycle after adding notes under `vsd-vault/notes/`.
- Verify stop condition before marking a /goal complete.

## Cycle 3+ ingest pattern (example: Trio-Retina)

1. Add `ingredient/` + `claim/` + `synthesis/` notes with honest frontmatter (VSD-3 estimative words).
2. Run (requires `vsd-vault/architect_key.pem`, gitignored):

   ```bash
   python vsd-vault/.vsd/vsd_synthesizer.py --cycle 3
   python vsd-vault/.vsd/vsd_eval_harness.py --report
   python scripts/vapi_invariant_gate.py
   ```

3. Confirm: harness exit 0 · PV-CI 179 · decision note `pending:operator` · SIC chain intact.

The synthesizer signs **all** routine notes each cycle; decision notes stay operator-pending.

## Read-only MCP (when Stream E shipped on PR #51)

`vsd_state`, `vsd_harness_report`, `vsd_verify_chain`, `vsd_session_attestation` on vapi-unified —
**read-only**; never run cycles via MCP.

## Boundaries

See `BOUNDARIES.md`. Never edit `vapi_invariant_gate.py`, FROZEN-v1, PoAC wire, or loop-sign decisions.
