# PoSP Assertion-Plane Adversarial Matrix (TRL-1 A3) - 2026-07-11

We forged our own PoSP presence-proof records against the tournament-operator verifier
(`l9_presence/posp_verifier.py`), the same forge-your-own discipline that hardened the WMP
data-economy verifier (AH-1). Two real gaps found and fixed; the deep-verification ceiling
documented. Reproduce: `pytest l9_presence/tests/test_posp_forgery_ah.py -q`.

| id | forgery | before | now | class |
|----|---------|--------|-----|-------|
| P1 | wrong schema | SCHEMA_ERROR | SCHEMA_ERROR | CAUGHT |
| P2 | unknown verdict | FAILED | FAILED | CAUGHT |
| P3 | missing session_id | FAILED | FAILED | CAUGHT |
| P4 | SYNCHRONIZED with only one id-verified surface | FAILED | FAILED | CAUGHT (verdict_consistent) |
| P5 | empty kas.commitment | FAILED | FAILED | CAUGHT |
| **P6** | **bogus non-empty commitment (`'x'`)** | **VERIFIED** | **FAILED** | **GAP-FOUND-AND-FIXED** (`kas_commitment_wellformed`: 64-hex SHA-256) |
| **P7** | **impossible fusion counts (id_verified=True, n_id=0 or n_id>n_rows)** | **VERIFIED** | **FAILED** | **GAP-FOUND-AND-FIXED** (`fusion_counts_sane`) |
| P8 | fully-fabricated but internally-consistent (right booleans, well-formed fake commitment, sane counts) | VERIFIED | VERIFIED | **OUT-OF-SCOPE-DOCUMENTED** |

## The two fixes

The SYNCHRONIZED -> VERIFIED gate now additionally requires **`kas_commitment_wellformed`** (a 64-hex
SHA-256, not merely non-empty) and **`fusion_counts_sane`** (`n_id_verified <= n_rows`, and `> 0` when
the surface claims id-verified). A hand-forged record with the right booleans but a garbage commitment
or impossible counts no longer reaches VERIFIED. Additive: the real M17 record stays VERIFIED
(commitment `4b453dd8…`, counts 462==462), the 6 existing verifier tests stay green, and the merged I1
assertion rung still PASSES.

## The honest ceiling (P8)

The verifier is **structural + consistency**, not deep re-derivation. A record that is internally
consistent and well-formed passes the structural bar; distinguishing it from a real one requires the
deferred artifacts (KAS-file deep re-derivation, on-disk archive SHA-256 cross-referencing) - gated on
those being co-located and `CHAIN_SUBMISSION_PAUSED` lifted. `posp_verifier.py`'s OUT-OF-SCOPE note
says this plainly; test `test_P8_...` pins it so the limitation is never a silent gap.

---

*TRL-1 A3 assertion-plane hardening - 2026-07-11. Loop: `docs/trio-readiness-loop-trl1-2026-07-11.md`.*
