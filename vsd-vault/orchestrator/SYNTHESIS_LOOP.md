# VSD Synthesis Loop — orchestrator skill

The editable layer (`.vsd/vsd_synthesizer.py`). One cycle is an OODA pass gated by the immutable
harness — the synthesis-domain twin of the autoresearch loop and the GIC-stamped grind run.

## One cycle
1. **Observe** — ensure canonical seeds exist (purpose synthesis + loop-authorization decision); read prior ledger / SIC head.
2. **Orient** — emit a Phase-Boundary State Assessment (PBSA) for this cycle (VSD-4).
3. **Decide** — sign routine notes with the architect Ed25519 key; leave decision notes operator-pending (split-signing).
4. **Act + verify (the deterministic checker)** — run, in order:
   - `vsd_eval_harness.py` (synthesis invariants over `notes/`)
   - `scripts/vapi_invariant_gate.py` (PV-CI, must stay 179 — never edited)
   - best-effort `mythos_methodology_drift` + `mythos_frozen_drift`
5. **Commit provenance** — on PASS: `compute_sic(...)` stamps the Synthesis Integrity Chain, append `eval/synthesis_ledger.jsonl`, regenerate `corpus/` from passing notes only.

## Run
```
python vsd-vault/.vsd/vsd_synthesizer.py --cycle N      # run a cycle
python vsd-vault/.vsd/vsd_synthesizer.py --report       # ledger tail + chain head
python vsd-vault/.vsd/vsd_eval_harness.py --report      # the checker, standalone
```

## /goal stop condition (verifiable)
harness exit 0 · PV-CI exit 0 (179) · mythos drift 0 · required seeds present + verifying ·
decision note `signed:false/pending:operator` · SIC chain re-verifies · ledger has ≥1 cycle.

See `BOUNDARIES.md` for what this orchestrator must never touch.
