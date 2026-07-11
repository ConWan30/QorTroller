# QorTroller — Session Handoff for grok build (2026-07-09)

**Branch:** `feat/l9-consistency-adversarial-harness` · **Head:** `25037095` · **PV-CI:** 182 throughout · **Wallet:** 29.12 IOTX

---

## 0. Frame

This session built out the **non-rig novelty surface** of the `l9_presence/` sub-project — the
presence/authorship layer that sits **above** the frozen 228-byte PoAC wire and **references** its
commitments (never edits them). Everything is **advisory · `developer_self` ·
`population_certified=False` · `verifier_independence=False`**. No FROZEN-v1 family, domain tag,
contract, or 228B PoAC edit was made. One deliberate on-chain tx (the VHR capstone). Every commit
single-committer-approved (operator commits).

---

## 1. Commit ledger (10 commits; newest → oldest)

| Commit | Arc | What it consists of |
|---|---|---|
| `25037095` | EVENT-BIND inc 2b **prep** | Wires the retina daemon to stamp the live PoAC `record_hash` into both lobes (`qortroller_retina_capture.py::set_record_hash` + `_log_composite` stamp; `dualshock_integration.py` call site). Flag `EVENT_BIND_STAMP_ENABLED` (default-off → byte-identical). `scripts/event_bind_session_check.py` = post-session readout. **This is what the live rig session is validating right now.** |
| `a3454091` | **On-chain capstone** | `scripts/submit_vhr_proof.py` submitted M17's real Groth16 replay proof to `VAPIReplayProofVerifier` v1 `0x5182372d…` → **`ReplayProofVerified` emitted**. tx `0db5faff…`, block 45479067, 0.2833 IOTX. De-risked by a `verifyView` eth_call (0 IOTX) confirming acceptance before spend; calldata built in pure Python (no snarkjs dep). |
| `a81648f5` | EVENT-BIND **inc 3** | `l9_presence/event_bind_recency.py` — `replay_resistance()` composes the crypto binding with the Arc-6 PoSR temporal beacon → `REPLAY_RESISTANT` / `SPLICE_PROOF_ONLY` / `TEMPORAL_ONLY` / `UNVERIFIABLE`. Reference block **injected** (no RPC). Adds a 12th forgery attack (`stale_replay`). 12/12 tests. |
| `21ce61ff` | **ADVERSARY-EXPAND** | `l9_presence/adversarial/presence_forgery.py` — **12 forgeries × 6 verifiers, all rejected by a named rail** (`holds=True`, `audits/presence_forgery_matrix.json`). Machine-checked fail-closed evidence base. |
| `9729e011` | **PORT-CERT** | `l9_presence/port_cert.py` — portable Match Certificate (`qortroller-match-certificate-v0`) + off-rig verifier; snarkjs + chain RPC are **injected** callables. **Demonstrated on real M17** (`audits/match_certificate_m17.json`): anchor-digest match `545f9d44…` = the digest anchored on-chain at block 45447322. |
| `feb81bce` | EVENT-BIND **inc 2** | Capture-path stamping **support**: `hid_onset_event`/`authored_screen_event` take optional `record_hash` (key-only-when-present → `events_root` unchanged when off); `HidOnsetDetector.set_record_hash`; adapter `bind_session_events`; `stamp_enabled()` gate. |
| `2ef36e33` | EVENT-BIND **inc 1** | `l9_presence/event_bind.py` — the binder: `EventBindMode {RECORD_HASH_PRODUCTION, TEMPORAL_PROTOTYPE, UNBOUND}`, crypto-preferred-over-temporal. `scripts/event_bind_splice_demo.py` — two identical-timing corpora separated by anchor, not clock. |
| `0d6fa84b` | A1-b **artifact-v1** | Optional L4 attachment; `L4_SESSION_V13_KEYS` frozen tuple **pinned by guarded test to `BiometricFeatureFrame.to_vector()` field order**. Includes an **audit self-correction** (the §2.4 list was correct; only its attribution was wrong). |
| `3c694c47` | A1-b **v0** | `l9_presence/bcc_match.py` — BCC Match-Lane (`qortroller-bcc-match-artifact-v0`), a sealed gamer-local match-presence corpus. **grok authored the design; Claude audited it (F-A1b-AUDIT-1) then built v0 NONE-only.** Validated on real M14 (deferred coherence 0.75). |
| `8b91bc8e` | VHR-PROOF-2 (predecessor) | The real Groth16 proof over M17's actual sanitized matrix, verified locally — which `a3454091` then put on-chain. |

---

## 2. The four arcs, conceptually

### A1-b — BCC Match-Lane (`bcc_match.py`)
A **second** sealed BCC family (separate store `bcc_match/`, own candidate genesis tag, own typed
payload) that accumulates match-bound multi-surface presence sessions. Fail-closed admission G1–G8:
PoSP **SYNCHRONIZED**-only + authorship non-empty + **coherence ≥ 0.50** (pre-registered) + no
inherited HYGIENE_FAIL + session-id anti-assertion. NONE-only by default (assertion-plane, zero
biometrics); optional L4 vector additive. *Reference-and-bind — mints no primitive.*

### EVENT-BIND (`event_bind.py` + `event_bind_recency.py`)
The seam it closes — **presence binds by identifier (session_id) but per-event authorship still binds
by clock** (KAS "kill resolves inside an R2 window" = temporal ∩). EVENT-BIND gives the on-screen
**outcome** and its causing **HID onset** a shared PoAC `record_hash` anchor.
- **Honest scope (pinned):** closes cross-source **SPLICE**; **composes with PoSR recency** (inc 3)
  for **replay** resistance; does **NOT** close a compromised host, and **can't bind per-record**
  (228B PoAC body is FROZEN) so recency is session-scoped.
- inc 1 = binder + splice proof; inc 2 = schema stamping support; inc 3 = recency compose;
  inc 2b = daemon live wiring (**in rig validation now**).

### PORT-CERT (`port_cert.py`)
Composes PoSP + KAS/deferred + VHR proof + on-chain anchor + consent into **one bundle a third party
re-verifies against public parameters, without the rig or raw data**. Verifier checks: session-join
(anti-splice) · PoSP SYNCHRONIZED · **anchor-digest match** (published PoSP file SHA-256 ==
on-chain-anchored digest) · VHR Groth16 (injected snarkjs) · on-chain anchor (injected RPC).
**VERIFIED requires actually reading the chain** (a forger can fabricate an anchor ref); missing
snarkjs/RPC → honest **PARTIAL**, never a false VERIFIED. Scope: makes the **proofs** portable, not
the capture trustless.

### ADVERSARY-EXPAND (`adversarial/presence_forgery.py`)
Turns "we assert fail-closed" into "we demonstrate it" — 12 forgeries (forged-SYNCHRONIZED→S6,
replayed-crop→sha-poison, coherence-gaming→G4, hygiene-bypass→G6, digest-tamper→C4, zk-false→C5,
session-splice→C2, event-splice→crypto-join, stale-replay→recency, …) each hitting a **named rail**
across posp_verifier · kas_deferred · bcc_match · port_cert · event_bind · event_bind_recency.
`holds=True`; a single open rail fails the suite loudly.

---

## 3. How it composes (the whole picture)

**A gamer hands someone a portable Match Certificate. That third party — not the rig — re-runs the
Groth16 replay proof (now witnessed on-chain via `ReplayProofVerified`), confirms the exact PoSP
record was anchored on IoTeX, and checks the session-join. Per-event authorship inside it is bound by
a shared cryptographic anchor (splice-proof) and, with the PoSR beacon, replay-resistant. And the
12-attack matrix proves every one of those checks fails closed against forgery.** Local verification
→ on-chain witness → independently re-verifiable.

---

## 4. Design patterns grok should mirror

- **Reference-and-bind:** new capability = schema string + (optional) candidate chain tag; integrity
  derives from *referenced* commitments. No new FROZEN-v1.
- **Injected-check verifiers:** pure modules never shell out or hit the network —
  `groth16_verify`/`chain_lookup`/fetchers are injected; the runner owns the blast radius. Keeps
  modules deterministic + testable.
- **Flag-gated, default-off, byte-identical:** every capture-path change is off by default and
  provably unchanged when off (e.g., `record_hash` key-only-when-present so `events_root` is
  untouched).
- **Honest-scope + self-correction:** every design doc has a §"honest limits"; when the audit
  overstated a defect (F-A1b-AUDIT-1), it was corrected in the permanent record.
- **Fail-closed admission / verifier verdicts:** closed enums (`SYNCHRONIZED`/`PARTIAL`/`UNVERIFIABLE`,
  `VERIFIED`/`PARTIAL`/`FAILED`/`SCHEMA_ERROR`), UNCHECKED → PARTIAL, never a false pass.

---

## 5. Test surface

l9_presence suite grew **608 → 667 passing** (2 pre-existing `test_cocapture` env-import failures,
unrelated). New: `test_bcc_match` 35 · `test_event_bind` 35 · `test_event_bind_recency` 12 ·
`test_port_cert` 14 · `test_presence_forgery` 5. PV-CI 182 every commit.

---

## 6. Live rig state (Session 1, in progress)

Validating EVENT-BIND inc 2b (Match 18). **Result so far: stamping wiring VALIDATED live**
(record_hash reaches both lobes). **Blocker:** the killfeed authorship anchor OCR-misread the handle
`QorTrola30` → `q0rtr01a30`, so the 3 kills read as `own_kills=0` (`KAS = INSUFFICIENT_KILLS`) — no
authored input→outcome pairs to complete the crypto-join. PoSP still came out SYNCHRONIZED; 600-crop
archive + KAS + PoSP records written. Deferred re-scan of the archive with the correct handle is
running (recover the kills post-hoc vs. quick re-run).

---

## 7. Invariants held

228B PoAC + chain-hash SHA-256(164B) untouched · PV-CI 182 · `CHAIN_SUBMISSION_PAUSED=true` held (the
one tx used a process-scoped override) · no contract/Solidity/firmware edit · single-committer ·
biometric/raw-session data never committed (gitignored).

---

## 8. Open / next (all rig- or operator-gated)

EVENT-BIND inc 2b clean re-validation (fix killfeed anchor) · RP-4 latency calibration → unlocks
LUMEN-3 inc 2 · RP-6 adversarial replay corpus · PORT-CERT full-VERIFIED (needs snarkjs + a chain RPC
read, both free) · A5 two-key autonomy.

---

## 9. Module map (the verifier / primitive surface)

| Module | Role |
|---|---|
| `l9_presence/bcc_match.py` | BCC Match-Lane corpus + admission gate + optional L4 |
| `l9_presence/event_bind.py` | per-event cryptographic authorship binder + adapters |
| `l9_presence/event_bind_recency.py` | PoSR recency compose (replay resistance) |
| `l9_presence/port_cert.py` | portable Match Certificate build + off-rig verify |
| `l9_presence/adversarial/presence_forgery.py` | attack → rail matrix (12 attacks, 6 verifiers) |
| `l9_presence/posp.py` / `posp_verifier.py` | PoSP (synchronized presence) + its verifier |
| `l9_presence/kas_deferred.py` | RP-2d deferred authorship tier |
| `scripts/submit_vhr_proof.py` | on-chain VHR proof submission (triple-gated, estimate-first) |
| `scripts/match_certificate.py` | PORT-CERT build/verify runner |
| `scripts/run_forgery_matrix.py` | emit the forgery matrix |
| `scripts/event_bind_session_check.py` | post-rig-session binding readout |

*Design docs:* `docs/a1b-bcc-match-lane-design-2026-07-08.md` · `docs/event-bind-design-2026-07-09.md`
· `docs/port-cert-design-2026-07-09.md`. *Running ledger:* `audits/rp-close-1-ledger-2026-07-07.md`.
