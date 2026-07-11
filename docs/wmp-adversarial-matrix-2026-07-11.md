# WMP Adversarial Matrix (AH-1) — Public Living Doc

**What this is:** we try to forge our own certified-human WMP provenance bundles and record,
publicly, which forgeries the zero-trust consumer verifier catches, which gaps we found and
fixed, and which attacks are out of scope (and why). Anyone can reproduce every CAUGHT row.

**Claim ceiling (carry with every external mention):** AH-1 hardens the WMP consumer verifier
against an **enumerated** set of **logic-level** forgeries. It does **not** claim field-security,
complete attack coverage, or that no attack exists. Honest statement: *these vectors are caught;
these gaps are documented; these assumptions are relied upon.*

Design + taxonomy + acceptance bars: `docs/wmp-adversarial-hardening-ah1-design-2026-07-11.md`
(§9 = auditor addendum). Attack base = the published `wmp_corpus_real/wmp_corpus.jsonl` (UC-1).

Reproduce the whole matrix (pure, offline, CI-fast):

```bash
python scripts/run_wmp_adversarial_matrix.py          # exit 0 iff holds
pytest bridge/tests/test_wmp_adversarial_ah1.py -q     # the pinning tests
```

---

## Banked rows

| id | vector | target check | expected | result | evidence | notes |
|----|--------|--------------|----------|--------|----------|-------|
| **A1** | matrix-swap (flip one matrix nibble; keep proof + public inputs) | `matrix_root_rehash` | REJECTED — Poseidon recompute ≠ the root the proof verified against | **CAUGHT** | `test_A1_matrix_swap_rejected` (+ control `test_A1_control_base_verifies_rehash`, all-channel `test_A1_swap_each_channel_caught`); full-crypto kill already banked in `audits/wmp-phase2-first-real-bundle-2026-07-11.md` L25 | pure test injects an honest Poseidon mock (real root only for the base matrix) — models collision-resistance; the real BN254 Poseidon is exercised by `wmp_full_verify.py`. Forgery is surgical: humanity/consent/scope still pass, only the matrix↔root binding catches it |
| **A3** | gamer-address swap (repoint `consent_gamer_address` to a non-consenter) | `consent` | REJECTED — on-chain `isWorldModelConsentGranted` false for the swapped gamer | **CAUGHT** | `test_A3_gamer_swap_rejected` (+ surgical `test_A3_swap_is_surgical_only_consent_fails`, gap-watch `test_A3_gap_watch_stub_not_at_bar`) | oracle must be injected: with `consent_lookup=None` the `GRANTED` bundle passes as an HONEST stub (`stubbed=True`) → excluded by the zero-stub bar (`wmp_full_verify.py` L205), so a runner without `--consent-registry` is misconfiguration, never CAUGHT. Surgical: matrix/humanity/scope still pass |
| **A15** | forbidden-key smuggle (inject a raw biometric key top-level / in `extra_metadata` / as a channel) | `scope_honesty` | REJECTED — post-φ data-floor breach: the payload carries a forbidden biometric key | **GAP-FOUND-AND-FIXED** | probe 2026-07-11 confirmed the gap (raw key → VERIFIED); fixed by the payload forbidden-key scan in `check_scope_honesty`; `test_A15_forbidden_key_smuggle_rejected[top/extra_metadata/channel]` + `test_A15_clean_bundle_still_verifies` + `test_A15_representative_forbidden_columns_caught` | the loop's first real gap: scope-honesty was **asserted, not enforced**. Fix is additive — clean bundles unaffected (40+ WMP tests green). The verifier is zero-trust, so the forbidden list is a FROZEN published copy of `FORBIDDEN_COLUMNS`, not a bridge import |

**holds = True** — 3/3 banked.

---

## Findings resolved

| id | finding | resolution |
|----|---------|------------|
| **F-AH1-A15** | Forbidden-key smuggle — scope-honesty was **asserted, not enforced**: a raw biometric key (`l4_mahalanobis_distance` top-level; `ait_rms` + `micro_tremor_variance` in `extra_metadata`) rode through to VERIFIED (probe 2026-07-11). | **FIXED (cycle C3b, 2026-07-11):** `check_scope_honesty` now scans top-level keys + `extra_metadata` (recursively) + `action_trace_channels` names against a FROZEN consumer-side mirror of `FORBIDDEN_COLUMNS` (the verifier is zero-trust — no bridge import); any hit → REJECTED. Additive (40+ existing WMP tests green; PV-CI 182). Banked as A15 above. |

---

## Backlog (queued vectors — each becomes one cycle → one row + one pinning test)

Order per design §5.4: **A15 → A2**, then A4, A6a, A8, A9, A11, A14, A10/A12, A7, A13. (A1, A3 banked.)

| id | vector | expected class | notes |
|----|--------|----------------|-------|
| A4 | consent GRANTED but gamer never signed | CAUGHT @ `consent` | forging the true grant needs the gamer key → that half is CRYPTO/CHAIN out-of-scope |
| A2 | stale-proof replay (old proof + new session matrix) | CAUGHT @ `matrix_root_rehash` (+ humanity) | pure tests MUST inject poseidon (unpaired structural path passes, `wmp_verify.py` L198-205) |
| A6a | fake/invented beacons | CAUGHT @ `recency` | full runner hits the LIVE registry; UC-1 recency stays honest-deferred — never "prove recency" on UC-1 |
| A8 | schema / circuit / truncated-proof downgrade | CAUGHT @ `schema` / `humanity` | — |
| A9 | synthetic bundle without flag | CAUGHT @ `synthetic_gate` (+ humanity/rehash) | — |
| A11 | scope overclaim (flip observation channel / POMDP flag) | CAUGHT @ `scope_honesty` | — |
| A14 | public-input swap without proof | CAUGHT @ `humanity` | subset of A2 |
| A10 / A12 | humanity/consent deferred-lie or stub theater | CAUGHT @ full-verify bar (L205) | pure `verify_bundle` alone can VERIFIED with a deferral — the **bar** is the consumer path |
| A16 | `sanitized_trace_root_ref` fallback abuse (`wmp_verify.py` L229) | CAUGHT @ full bar | runner's groth16 raises on empty public inputs (L81-83); rail encoded in `honest_kwargs` |
| A17 | corpus N-inflation (duplicate JSONL) | OUT-OF-SCOPE-DOCUMENTED | statistics claim, not per-bundle; N=1 ceiling / future corpus linter |
| A7 | strata-band inflation | OUT-OF-SCOPE-DOCUMENTED | not in the five checks; re-derive lives in `l9_presence/skill_strata.py` |
| A13 | bundle-hash / manifest games | OUT-OF-SCOPE-DOCUMENTED | `_bundle_hash` recomputed each verify; manifest integrity = exporter/CI concern |

## Relied-upon assumptions (documented, never "proven" in AH-1)

ZK soundness · vkey authenticity (consumer pins the published vkey) · chain integrity (view-calls
reflect real on-chain state) · gamer-key secrecy · no malicious RPC MITM (out of AH-1 v0).

## Saturation tracker

- **Banked:** 3 (A1, A3, A15)
- **Open findings:** 0 — **F-AH1-A15** found **and fixed** this session (1 gap → 1 fix, verifier hardened)
- **Backlog:** A2, A4, A6a, A7, A8, A9, A10, A11, A12, A13, A14, A16, A17
- **Saturation:** a full pass adds no new vector and no new gap. Not reached.

---

*WMP AH-1 matrix — opened 2026-07-11 (cycles C1 A1, C2 A3, C3 A15 gap-found-and-fixed). Living doc; one row per banked cycle.*
