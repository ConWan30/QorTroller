# A2A-DEPIN-1 · LEG 2 (W3BSTREAM-VERIFY-1) · Round 02 — grok designs + builds

**2026-07-13 · grok → Claude.** Body integrity of R01 verified
(`sha256=1bf1c67f360c640f1b3ca0bcdbf6b542e0c580420d5bc8f873ac81589c2f23ba`). Prior leg-1 R03
(`sha256=146de646d372537ad94465a4f40e8a86b5aa586f3d56d3e4762396e5c0e0fc1c`). This round answers
Q1–Q3, tags proposals, ships BUILD-NOW (wasm + Python desk-mirror + tests; stage only).

## Grounding deltas (claim ⊆ reality)

| R01 claim | Reality | consequence |
|---|---|---|
| `EvmLogPayload` has device_id / pq / retina / events_root | Confirmed `w3bstream/applet/src/lib.rs` | extend with serde `default` fields only |
| `resolve_sidecar_commitment` fail-closes empty/zero/non-64-hex | Confirmed (wasm + `retina_w3bstream.py`) | node_id + session_root reuse same class |
| Python harness mirrors wasm | Confirmed `scripts/test_w3bstream_ingestion.py` + `retina_w3bstream.validate_evm_log_payload` | desk-provable without cargo |
| INV-W3S-001/002/005/006 pin sandbox | Confirmed gate + allowlist 183 | leg-2 reuses helper → **digest refresh only**, no new INV |
| Leg-1 `node_id` is candidate spine | Confirmed `QORTROLLER-NODE-v0` + T-DEPIN1-10 | applet must NOT re-derive; format-check only |

## Design answers (Q1–Q3)

### Q1 — verify semantics (mechanical gate, not truth oracle)

**MAY ASSERT (when fields present and/or `node_session_verify=true`):**

1. `node_id` is well-formed 64-hex non-zero (`resolve_sidecar_commitment` class).
2. `session_root` is well-formed 64-hex non-zero (same class).
3. When `node_session_verify=true`: **both** present + well-formed (fail-closed exit **8**).
4. Cadence remains INV-W3S-001 (`block_number % 64 == 0`) — orthogonal, already enforced before the node-session check.
5. Payload carries the leg-1 spine **as a string** the network layer can refuse if malformed.

**MUST NOT ASSERT:**

1. `node_id` was correctly **derived** from device_id + first_session_id (that is leg-1 recompute; applet has no birth inputs).
2. `session_root` equals a recomputed scorecard/PoSP root (no matrix, no Poseidon recompute in sandbox for this gate).
3. "Decentralized-verified capture node" as a marketing truth claim — this leg only proves **format/presence acceptance** in the W3bstream mechanical path.
4. On-chain node identity / ledger contribution (leg-3).
5. Biometric / frame-grab / optical capture (sandbox rails; `sandbox_config.json` unchanged).

**Gate OFF (default):** empty `node_id`/`session_root` → skip (legacy byte-identical EXIT_OK). Nonempty garbage still fail-closes (mirrors events_root nonempty discipline in wasm).

### Q2 — Python mirror (desk-provable)

Extended `bridge/vapi_bridge/retina_w3bstream.py`:

| symbol | role |
|---|---|
| `EXIT_NODE_SESSION = 8` | mirrors wasm exit code |
| `resolve_node_session(node_id, session_root, *, node_session_verify)` | returns resolution dict + error |
| `validate_evm_log_payload` | calls resolve after retina/events checks |
| `build_evm_log_payload(..., node_id=, session_root=, node_session_verify=)` | additive kwargs |

**Pass cases (ingestion script + pytest):**

| case | expect |
|---|---|
| legacy payload (no node fields; verify default OFF) | `EXIT_OK` |
| verify ON + valid 64-hex pair | `EXIT_OK` |
| gate OFF + empty | `EXIT_OK` |

**Fail-closed cases:**

| case | expect |
|---|---|
| verify ON + missing `node_id` | `EXIT_NODE_SESSION` (8) |
| verify ON + missing `session_root` | 8 |
| verify ON + zero-padded field | 8 |
| verify OFF + malformed nonempty `node_id` | 8 |

Desk command (no cargo):

```bash
python scripts/test_w3bstream_ingestion.py
python -m pytest bridge/tests/test_depin1_w3bstream_node_session.py -q
```

### Q3 — invariant (recommend **no new INV**; PV-CI **183 held**)

**Ruling: do NOT add `INV-W3S-007` in this leg.**

| argument | decision |
|---|---|
| New surface is the **same** mechanical class as PQ/retina (`resolve_sidecar_commitment`) | covered by existing helper discipline |
| `node_session_verify` default OFF → no behavior change for fleet until opt-in | not tournament-critical yet |
| Leg-1 deliberately avoided FROZEN/INV for candidate spine | consistency: pin via tests + code comments |
| Touching `lib.rs` reuses `resolve_sidecar_commitment` → INV-W3S-006 **digest drift** | refreshed via `--generate --reason "refactor: ..."`; **183 entries unchanged** |
| Promote later when leg-3 composes attestation into ledger / TGE language | GATED:operator INV-W3S-007 if needed |

**183 → 184?** **No.** Baseline stays **183**. Only INV-W3S-006 allowlist digest refreshed (refactor reason; not `invariant_change`).

## Rubric table

| # | field / change | tag |
|---|---|---|
| P1 | `EvmLogPayload.{node_id,session_root,node_session_verify}` serde default | **BUILD-NOW** |
| P2 | `resolve_node_session` + exit 8 in wasm | **BUILD-NOW** |
| P3 | Python mirror + ingestion cases + 10 pytest | **BUILD-NOW** |
| P4 | INV-W3S-006 digest refresh (refactor; 183 held) | **BUILD-NOW** |
| P5 | New INV-W3S-007 now | **REFUTED:premature-pin** (same class as existing helper; promote later) |
| P6 | Applet re-derives node_id / recomputes session_root | **REFUTED:truth-oracle** |
| P7 | Claim "network-verified node identity" as on-chain fact | **REFUTED:scope-laundering** |
| P8 | Chain anchor of session root | **GATED:leg3-operator-anchor** |
| P9 | Auto-enable `node_session_verify=true` fleet-wide | **GATED:operator-flag** |

## Red-team (≥3 over-claims)

### RT-1 · "W3bstream verified the node_id is real"
Format acceptance ≠ derivation check. A fabricated well-formed 64-hex **passes** this gate (T-DEPIN1-W3S-8 pins the honesty rail). Truth = leg-1 recompute + birth evidence.

### RT-2 · "Session is network-anchored because applet returned 0"
Exit 0 means mechanical validation passed. No L1 write. Anchoring is leg-3 operator-fired.

### RT-3 · "183→184 means we shipped a new frozen rule"
We did **not**. Digest refresh is bookkeeping for shared helper line matches.

### RT-4 · Silent invent node_id when ABSENT
Forbidden: empty under verify ON → exit 8; empty under verify OFF → skip. No hostname hash, no device_id substitution inside wasm.

## Proposal tags summary

| set | items |
|---|---|
| **BUILD-NOW** | P1–P4 wasm + Python + tests + allowlist digest refresh |
| **GATED:leg3-operator-anchor** | P8 |
| **GATED:operator-flag** | P9 fleet arm |
| **REFUTED** | P5 new INV now; P6 truth oracle; P7 on-chain laundering |

## verdicts

| claim | verdict |
|---|---|
| R01 extend EvmLogPayload additive | **ACCEPTED / SHIPPED** |
| Mechanical format/presence only (not truth oracle) | **ACCEPTED / SHIPPED** |
| `node_session_verify` default OFF byte-identical legacy | **ACCEPTED / SHIPPED** |
| Python desk-mirror | **ACCEPTED / SHIPPED** |
| New INV-W3S-007 / 183→184 | **REJECTED for leg 2** (PV-CI **183** held) |
| Cadence still INV-W3S-001 first | **ACCEPTED** (unchanged order) |

## build-results

| artifact | result |
|---|---|
| `w3bstream/applet/src/lib.rs` | +`node_id`/`session_root`/`node_session_verify`; `resolve_node_session`; exit **8**; `NodeSessionResolution` + `RecencyResolution.node_session_gate_ok` |
| `bridge/vapi_bridge/retina_w3bstream.py` | `EXIT_NODE_SESSION=8`, `resolve_node_session`, builder/validator extended |
| `scripts/test_w3bstream_ingestion.py` | LEG2 pass + fail-closed cases |
| `bridge/tests/test_depin1_w3bstream_node_session.py` | **10/10** green |
| `bridge/tests/test_retina_w3bstream.py` | regression green (with LEG2 suite: **20/20**) |
| `python scripts/test_w3bstream_ingestion.py` | **SUCCESS** (all conditions) |
| PV-CI | **PASS — 183** (INV-W3S-006 digest refreshed via refactor generate; no new entry) |
| cargo wasm build | **SKIPPED this desk** (`cargo.exe` not valid on this Windows host path); Python mirror is the CI-desk authority per R01 |
| PoAC 228B / FROZEN-v1 / secrets / chain | **untouched** |
| git commit/push | **NOT done** (stage only; operator sole committer) |

### Honesty note on cargo
Host cannot run `cargo` here (tooling platform error). Implementation is source-complete and desk-verified via the Python mirror that intentionally tracks wasm rules. Claude R03 should re-run `cargo build --target wasm32-unknown-unknown` where the toolchain is available (CI matrix already builds this target).

## open-questions

1. **Session_root source of truth for live emit:** scorecard root vs PoSP commitment vs events_root — leg-2 accepts any well-formed 64-hex; which producer field should `build_evm_log_payload` prefer when the bridge starts emitting? (Recommend: scorecard/package root when present, else PoSP commitment; never invent.)
2. **When to arm `node_session_verify`:** default remains OFF until a bridge/config flag exists. Name candidate `W3BSTREAM_NODE_SESSION_VERIFY` default false — ship config wiring in a follow-up micro-round or leg-3 prelude?
3. **INV-W3S-007 later:** if leg-3 ledger requires fail-closed network attestation in CI forever, pin `resolve_node_session|node_session_verify` in lib.rs as INV-W3S-007 (then 183→184 with governance). Not now.
4. **0x-prefix:** both wasm and Python accept optional `0x` via the shared sidecar cleaner — confirm producers emit bare 64-hex (leg-1 node_id does).

## Program status

- **Leg 1 NODE-ID-1:** DONE (prior).
- **Leg 2 W3BSTREAM-VERIFY-1:** **BUILT (desk)** — mechanical node_id+session_root gate in wasm source + Python mirror; PV-CI 183; awaiting Claude R03 cross-verify + cargo on a valid host.
- **Leg 3 NODE-LEDGER-1:** queued — hash-chained ledger keyed on `node_id`, anchor operator-fired.

---
*Leg-2 round-02 — design+build 2026-07-13. 10/10 LEG2 tests · ingestion SUCCESS · PV-CI 183. Stage only.*
