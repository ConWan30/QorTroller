# WMP Gated Loops — ZK Property Proof (ZKP-1) + Two-Engines Flywheel (FLY-1) — 2026-07-11

The two "big" loops on the menu are **externally gated** — one on a trusted-setup *ceremony*, one on
corpus *breadth* (the capture card + more matches). They can't be *finished* now, but their
desk-buildable structure + honest deferral rails are built and test-pinned, so activation is a
drop-in the moment the gate opens (the Arc 5 DeferredProver precedent: build the pipeline, defer the
gated part, never fake it).

## ZKP-1 — ZK Property Proof (ceremony-gated)

**Goal:** prove a VDC claim's value satisfies a predicate (e.g. `value ≥ threshold`) **without
revealing the value** — the "withhold + prove" rung above selective disclosure.

**Built (`sdk/wmp_zk_property.py`, 12 tests):**
- `build_property_request` — the public STATEMENT (claim binding + field + predicate + *public*
  threshold); the secret value is **never** placed in the request (test-pinned).
- `Prover` protocol + `DeferredProver` — the honesty rail: no ceremony → no proof → `None`, never a
  fabricated proof.
- `build_property_proof` / `verify_property_proof` — a deferral verifies as **DEFERRED** (never PASS,
  never FAIL); a present proof needs the injected ceremony verifier (`zk_verify`) or it too is
  DEFERRED; a mock prover/verifier exercises the PROVEN/REJECTED flip structurally (not real ZK).

**Gate → activation:** a circom range/comparison circuit + a trusted-setup ceremony (the Phase 237 /
Arc 5 pattern) produce a real `Prover` + `zk_verify`; drop them behind the same interface and records
flip DEFERRED → PROVEN. No fake proof ships before then.

## FLY-1 — Two-Engines Flywheel (breadth-gated)

**Goal:** the certified-human corpus feeds back to sharpen the anti-cheat — better data → better
detector → more valuable data.

**Built (`sdk/wmp_flywheel.py`, 6 tests) — safe by construction:**
- `corpus_baseline(sessions)` — a **read-only** distribution (n/min/max/mean) of the VDC fingerprint
  scalars across N certified sessions.
- **STRICTLY breadth-gated:** below `MIN_BREADTH=30` (declared) it returns **DEFERRED** — at today's
  N=1 it defers.
- **Writes nothing, recommends nothing:** v0 emits a baseline as *information*; it never writes a
  threshold, never touches calibration, never makes an anti-cheat recommendation (test-pinned:
  baseline carries only stats; `recommendation` is always `None`). Per the hard rule, per-player L4
  thresholds only tighten via `min()`, operator + measurement gated.

**Gate → activation:** the capture card + a growing certified corpus cross `MIN_BREADTH`; the baseline
becomes meaningful; *wiring it into a detector remains a separate, explicit operator + calibration
step* — the flywheel supplies the raw material, never the threshold.

## Ladder (recap)

certified data (WMP) → verifiable derived claim (VDC-1, saturated) → selective disclosure (SD-1/SD-2)
→ **ZK property proof (ZKP-1 scaffold, ceremony-gated)** · **flywheel (FLY-1 scaffold, breadth-gated)**.

---

*WMP gated-loop scaffolds — 2026-07-11. Desk structure + honest deferral built; activation drops in at
the ceremony / breadth gate. No fake proof, no threshold write, no spend.*
