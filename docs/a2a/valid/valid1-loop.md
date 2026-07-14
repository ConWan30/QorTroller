# A2A-VALID-1 — the self-scoring match (one match → both validations, honestly)

**Chartered 2026-07-13 (operator picked VALID-1).** Sibling of A2A-PKG / A2A-HARD-1, same terminal
bus + mailbox. Turns the operator's NEXT match into a clean self-scoring experiment: at `stop` it
auto-produces **one honest scorecard** carrying BOTH pending validations —
- **HARD-1 recall:** kills authored (measured) / kills scored (operator-reported), never conflated;
- **PKG dogfood:** the setup→play→stop friction log + birth/receipt state —
with zero extra steps from the operator.

## The load-bearing rail (why this loop is hard)
Recall's denominator — **how many kills you actually scored** — CANNOT be measured automatically: the
HID is dual-connection-blind (BT→PS5), so no ground-truth kill count exists on our side. It comes
ONLY from the operator (the "21 kills" of T6.6b). A dishonest scorer would fabricate it. So the whole
loop's discipline: **measure what is measurable, ASK for what is not, mark the provenance of every
number, and never round up.** A match self-score that over-claims is worse than no score.

## Roles
| Agent | Role |
|---|---|
| **grok** | **Honest-score designer + claim adversary**: design the scorecard rubric `{field · source · what-it-MAY-claim · what-it-must-NOT}`; then red-team it for over-claim (does any field imply measured ground truth it doesn't have?). |
| **Claude** | **Grounder + builder + verifier**: audit each proposed field `claim ⊆ real-artifact`; build the scorer (`qortroller score` / `stop` integration) against the REAL KAS / PoSP / v3 / sink / birth / dogfood artifacts; cross-verify per ruling (a). |
| **Operator** | Arbiter + sole committer; supplies the one number only they know (kills scored); the live match is the empirical oracle. |

## Rails (standing + loop-specific)
Every scorecard number is tagged MEASURED / OPERATOR-REPORTED / DERIVED — never blurred. Recall
renders as `authored N / reported D` with D explicitly operator-sourced; **the scorecard never
claims "zero false-authorship proven"** (the match alone can't prove it — it may only state the
structural guards A2/A3 are active + all authored kills are R2-bound). PARTIAL / honest-null / 0
authored render with dignity, never as failure. One scorecard binds ONE session_id (no cross-session
mixing — the §2.3 named-roots discipline). No PoAC / FROZEN / chain / secrets. Additive over the CLI.
Single-committer.

## Stop criterion
The scorecard is built + honest (grok finds no surviving over-claim) + it runs end-to-end on a
past session's real artifacts (desk) → the loop rests; the operator's next match produces the first
LIVE self-score, which is the empirical proof both prior loops were waiting on.

---
*VALID-1 charter — 2026-07-13. Rounds in `docs/a2a/valid/round-*.md`; envelopes on the shared bus.*
