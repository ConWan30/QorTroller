# Tri-Plane Splice Matrix (TPF-1 F4) — forge-your-own against the fusion verifier

**2026-07-11.** The forge-your-own discipline (AH-1 A15 / PoSP A3) applied to the tri-plane
fusion (`l9_presence/tri_plane_manifest.py`). We forge cross-plane mismatches, prove what the
verifier catches, **fix the gap we found**, and **pin the one splice it cannot catch yet** — the
meaning plane, which F3 closes — instead of rounding it up.

Reproduce: `python -m pytest l9_presence/tests/test_tri_plane_splice_ah.py -q`

## The gap F4 found and fixed

Before F4, a manifest whose **top-level `session_id` disagreed with its own assertion/observation
planes** was NOT caught when verified *without* the PoSP artifact — `assertion_binds_posp` only
fires when the artifact is supplied. F4 adds the **`session_consistency` rail**: the manifest's
join key must equal the assertion + observation planes' own `session_id`, checked with **no
artifacts required**. An internal splice now fails on a bare `verify_tri_plane_manifest(m)`.

## The matrix

| # | forged splice | verifier response | rail |
|---|---------------|-------------------|------|
| **S1** | assertion plane from session B, top-level key session A (rehashed clean) | **CAUGHT — no artifacts needed** | `session_consistency` *(the gap F4 closed)* |
| **S2** | observation plane from session C, top-level key session A (rehashed) | **CAUGHT — no artifacts needed** | `session_consistency` |
| **S3** | verify a valid manifest against a *different* session's PoSP | **CAUGHT** | `assertion_binds_posp` |
| **S4** | MEANING splice — a bundle from a different session, bound `attested=True` | **NOT caught — the honest ceiling** | *(see below)* |
| **S5** | asserting field (`claim`) smuggled into the meaning plane, rehashed | **CAUGHT** | `separation_law` (holds under rehash) |
| **S6** | mutate a plane field without rehashing | **CAUGHT** | `manifest_hash` |

## S4 — the honest ceiling (why it is NOT a fix-it-now gap)

The WMP bundle (the MEANING plane) **carries no `session_id`**. So a manifest that federates a real
M17 presence proof with a bundle from a *different* session — under `attested_same_session=True` —
**verifies**, because no cryptographic cross-check between the meaning plane and the session exists.

This is not a bug to patch; it is the exact boundary the loop has named from F0:

- The manifest **never overclaims** it. `join_status.meaning_session` is `REFERENCE_ATTESTED`, never
  `CRYPTOGRAPHIC` — machine-checked by `meaning_join_honest`. An outsider is told, in the record, that
  the meaning join rests on an operator attestation, not a proof. No one is misled.
- **F3 is what upgrades attestation to proof:** surface `poac_chain_root` on the PoSP side to match the
  WMP bundle's existing `poacChainRoot` (its FROZEN Groth16 public input). Then the meaning plane binds
  to the same PoAC records the KAS already commits — a cryptographic session cross-check S4 would fail.
  F3 is an **operator decision** (it reshapes the PoSP schema); it is held for explicit GO.

## What this hardens

The separation law survives an adversary who rehashes to look internally clean (S5): the machine-check
is on *structure* (no asserting field in observation/meaning), not on the hash. And the fusion now
rejects internal join-key splices offline, with nothing but the manifest in hand (S1/S2) — the property
a cold reviewer relies on when they have the manifest but not both artifacts.

**Ceiling:** N=1, developer_self, IoTeX testnet; S4 is F3-gated by design; federation, not conflation;
no PoAC / 228B / FROZEN-v1 / chain contact; PV-CI 182.
