# Demo Spec — `posr.cadence_aligned_block()` helper

**Status:** EXECUTABLE — small concrete spec used to prove the
`spec-to-ship` agent's loop end-to-end on a real change.

---

## Goal

Add a pure-function helper `cadence_aligned_block(block_number)` to
`bridge/vapi_bridge/replay_proof_pipeline/posr.py` that returns the
largest cadence-aligned (multiple of `ANCHOR_CADENCE_BLOCKS=64`) block
number that is `<= block_number`. Used by the keeper (`scripts/anchor_beacon.py`)
and by any off-chain verifier needing to determine "which cadence block
should this session's open beacon be bound to." Zero deploy, zero IOTX,
no FROZEN-v1 modification. Self-contained.

---

## Acceptance Tests

- [T-CADENCE-1: aligned_input_returns_self] — `cadence_aligned_block(64)` returns `64`; `cadence_aligned_block(128)` returns `128`
- [T-CADENCE-2: rounds_down_to_nearest] — `cadence_aligned_block(100)` returns `64`; `cadence_aligned_block(63)` returns `0`
- [T-CADENCE-3: zero_input_returns_zero] — `cadence_aligned_block(0)` returns `0`
- [T-CADENCE-4: large_block_realistic] — `cadence_aligned_block(44188831)` returns `44188800` (the actual cadence block used in Arc 5 ceremony beacon)
- [T-CADENCE-5: rejects_negative] — `cadence_aligned_block(-1)` raises `ValueError`
- [T-CADENCE-6: rejects_non_int] — `cadence_aligned_block("64")` raises `TypeError`

---

## Files Touched

**MODIFIED:**
- `bridge/vapi_bridge/replay_proof_pipeline/posr.py` — add the helper function below existing pure-function math
- `bridge/vapi_bridge/replay_proof_pipeline/__init__.py` — re-export `cadence_aligned_block`
- `bridge/tests/test_replay_posr.py` — add 6 test cases per Acceptance Tests
- `CLAUDE.md` — append one-line NOTE

---

## Regression Surfaces

- `bridge/tests/test_replay_posr.py` : 15 passing (pre-change baseline — must reach 21 after)
- PV-CI gate : 167 invariants pass — no new invariant added; pure utility function
- No Hardhat / no chain — Python-only

---

## CLAUDE.md Note

NOTE: 🧮 ARC 6 ADDITIVE — `posr.cadence_aligned_block(N)` helper landed 2026-05-30 — pure function returning largest `≤N` block that's a multiple of `ANCHOR_CADENCE_BLOCKS=64`; consumed by `scripts/anchor_beacon.py` keeper + any off-chain verifier reconciling session boundaries with registry cadence; 6 tests (T-CADENCE-1..6); 0 IOTX, no FROZEN edits, no deploys. Spec-to-ship agent demo run.

---

## Honesty Rails

- Pure function — no I/O, no state, no chain.
- Strict input validation: negative → `ValueError`; non-int → `TypeError`.
- No new FROZEN-v1 surface; cadence constant `ANCHOR_CADENCE_BLOCKS=64`
  is already pinned by `INV-TBR-002`.

---

## Operator-Fired Steps (OUT of agent scope)

None. Pure code change; ships in one commit.
