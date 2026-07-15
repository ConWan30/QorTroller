# A2A-POEP-P3P4 — the presence-activation loop (earn the flip, don't assume it)

**Chartered 2026-07-15 (operator: complete P3+P4 and flip PoEP to true).** The operator's read is
right: this is the novel capability — *a cryptographic proof that a live human is physically on the
certified controller now.* But a presence proof is only a proof if it **defeats the thing that tries
to fake it.** RBM-v0 today separates the operator's reflexes from NO_RESPONSE — it has NOT faced a
bot / replay / macro. So this loop does not flip a flag on hope; it **earns** the flip:

1. **P3 — commitment (buildable now):** bind the RBM-v0 boolean decision + challenge records into a
   `QORTROLLER-POEP-v0` born-PQ commitment + a gamer-facing verification card. Candidate, default-OFF.
2. **The presence gate (the real P4 prerequisite):** grok designs an ADVERSARIAL null (constant-latency
   macros, replayed reflex traces, random-in-band, timing-jitter bots); Claude builds the harness and
   measures RBM-v0's false-accept rate AGAINST the adversary. This is what turns "reflex-consistency"
   into "presence."
3. **P4 — governed flip:** a two-key, evidence-gated activation function (checks N≥50 ∧ RBM-v0 STABLE ∧
   adversarial-FAR ≤ bar ∧ Stage-A ∧ PV-CI ceremony). Claude builds the gate + the check; **the operator
   fires the flip** (like the on-chain anchor — agent never flips presence to true autonomously).

## Roles (ruling (a))
grok = adversary (design the presence-faking attacks + the readiness bar) + verifier. Claude =
grounder + builder (harness, gate, commitment) + cross-verifier. Operator = arbiter + the ONLY hand
that fires the flip.

## The honest possible outcomes (both are wins)
- **RBM-v0 survives the adversary (FAR ≤ bar):** presence is genuinely earned; P4 flip is warranted +
  operator-fired with real evidence. QorTroller proves something only it can.
- **RBM-v0 fails the adversary:** the honest finding — reflex-consistency ≠ presence yet; the loop
  reports exactly what's missing (richer features / Stage-A / more data). No flip on a claim the data
  won't back. This is the protocol's whole discipline.

## Rails (hard)
poep_enabled / L6B_ENABLED / L6_CHALLENGES_ENABLED stay False until the operator two-key-fires, and
only if the adversarial bar is met. No liveness verdict shipped before the flip is earned. No
FROZEN/PoAC/chain edit without ceremony. The commitment is candidate (not anchored) until P4. Agent
never flips presence true autonomously — evidence-gated + operator-fired, down to the human hand.

---
*P3P4 charter — 2026-07-15. Rounds in `docs/a2a/poep/round-*.md`. The flip is earned against an
adversary + operator-fired, or it does not happen.*
