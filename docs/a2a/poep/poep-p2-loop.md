# A2A-POEP-P2 — the reflex-band model loop (build P2 from the existing corpus)

**Chartered 2026-07-15 (operator: build the P2 reflex-band model on the 189 existing reflexes; run
it as an A2A loop with grok throughout).** The PoEP P0 de-risk confirmed the mechanism works; the
N≥50 calibration-capture gate is already MET (189 REFLEX_OBSERVED in `~/.vapi/bridge.db`; CLAUDE.md's
"N=0" is stale). P2's job: turn that raw reflex corpus into a **population reflex-band model** that can
score a future probe response as "consistent with a live human reflex" vs "not" — the thing PoEP needs
before it can issue any liveness verdict.

## Roles (ruling (a) symmetric)
| Agent | Role |
|---|---|
| **grok** | Model designer + data-quality adversary: design the reflex-band model + the honest "calibrated" bar; red-team the corpus (is a latency-only reflex with zero IMU peak valid?). |
| **Claude** | Grounder + builder + verifier: extract the real corpus, ground every claim `⊆ data`, build the model + validation, cross-verify. |
| **Operator** | Arbiter + sole committer; the reflex source; no rig sessions needed for P2 (desk work on existing data). |

## Rails (standing + P2-specific)
Population-level model only (no N-player identity claim — that's L9, banked sub-grade). No liveness
VERDICT ships from this loop — P2 builds + validates the model; activation is P4 (two-key, gated).
Honest data quality: a reflex with no IMU corroboration is a candidate artifact, not silently valid.
`poep_enabled=False` / `L6B_ENABLED=false` untouched. No FROZEN/PoAC/chain edit. Single-committer.

## Stop criterion
A validated reflex-band model exists (band + IMU floor + feature signature), separates real reflexes
from a non-reflex null, with the corpus quality honestly characterized (which of the 189 are usable).
Then P3 (commitment) is a separate loop; P4 (activation) is operator-gated.

---
*POEP-P2 charter — 2026-07-15. Rounds in `docs/a2a/poep/round-*.md`; envelopes on the shared bus.*
