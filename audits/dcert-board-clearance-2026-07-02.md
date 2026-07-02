# D-CERT Board Clearance — 2026-07-02

Status of the developer-self-cert design-table (D-CERT-*) after the board-clearance arc. Four
field-level blocks were resolved-and-implemented this session; D-CERT-8 landed just prior. **The only
open cert-path item is D-CERT-5.**

Branch `feat/l9-consistency-adversarial-harness`. All commits below are pushed. No FROZEN-v1 / 228B
PoAC / chain / IOTX / l2_ads / loop-1/2 / vsd-vault touched by any of them; PV-CI 182 throughout.

## Board

| Block | Question | Status | Commit |
|-------|----------|--------|--------|
| D-CERT-1 | what the cert attests / oracle-set comparability (F-CERT-005) | **RESOLVED (a) + IMPLEMENTED** | `6f9fc2a8` |
| D-CERT-5 | does per-action AUTHORED presence bind to the cert | **OPEN — gated** (see below) | — |
| D-CERT-6 | single-source the developer N-gate (F-CERT-007 anomaly-2) | **RESOLVED + IMPLEMENTED** | `654fff3d` |
| D-CERT-7 | explicit `verifier_independence` rail (cycle-57 Confirm-3) | **RESOLVED + IMPLEMENTED** | `fc58a7b9` |
| D-CERT-8 | self-describing proof evidence base (F-CERT-008) | **RESOLVED (cycle 58) + IMPLEMENTED** | `71b87410` |
| D-CERT-9 | shared-label identity hazard (F-CERT-007 anomaly-4) | **RESOLVED (b) + IMPLEMENTED** | `71779014` |

**SDK self-description** (`deed6dee`, + fields in `fc58a7b9`/`6f9fc2a8`): `VAPIPresenceProof` now
carries the evidence base + `verifier_independence` + `active_oracles`, closing the F-CERT-008/005
gaps one layer up (an SDK consumer no longer needs filesystem access to audit the basis).

Self-describing ≠ more-certified held throughout: `population_certified=False`, `cert_scope` binary,
`certified:False`, the two-key gate — all unchanged. Every field is additive + null-safe (`None` on
old records, never inferred retroactively).

## The only open cert-path item: D-CERT-5

D-CERT-5 (does per-action AUTHORED presence bind to the developer-self cert) is the sole remaining
cert-path decision. It is **not resolvable today** — its evidence channel is neither calibrated nor
adversarially validated, and nothing routes an authorship verdict into the cert until it is. Its
critical path (what unblocks it), now the single thing standing between the current state and a
calibrated, adversarially-pairable second channel:

1. **l2_ads calibration — RP-session-gated.** The second anti-splice channel (ADS → center-ROI
   coupling) is parked on the RP-reliable-L2-source finding: under Remote Play the raw interface-3 L2
   sticks 255 on release (crosscheck 113/113 disagreements). Run the dual-L2 diagnostic
   (`RETINA_ADS_RP_DIAG=true` → `scripts/analyze_rp_l2_diag.py`) on a live RP session to establish an
   RP-reliable L2 source, then the 8×→3×→1× calibration protocol.
2. **Adversarial pairing debt.** The composite AUTHORED path needs its splice-forgery pairing measured
   (splice-FAR): authorship-alone is not cert-grade (one real death spliced under the deployed window).
   The l2_ads second channel is what makes the pairing adversarially sound.
3. **Range→match transfer check.** Firing-range calibration must transfer to live match conditions
   (the range→match separability question) before an AUTHORED verdict can bind to the cert.

Until (1)–(3) land, D-CERT-5 stays gated and **no authorship verdict routes into the cert**. The
D-CERT-1 `active_oracles` manifest guarantees that when retina/authorship *does* join the fusion, it
is visible on every proof it touches — which is precisely what makes D-CERT-5 resolvable with live
data later.

## Vault recording — DRAFTS, pending next-session VSD ceremony

Cycle 57 opened these blocks with Ed25519-signed notes and a stamped ledger. Closing them must be
symmetric: signed notes riding a proper VSD cycle — **not** an unsigned drop. The four resolutions are
drafted below in cycle-58 decision shape, `status: draft — pending VSD ceremony`; they are **not
signed** and **not in `vsd-vault/`**. Next session: run a VSD cycle that lifts these into
`vsd-vault/notes/` (implementation commits as ingredient refs, the resolution reasoning as synthesis,
decisions signed on the rig). Until then, an unsigned note here is never mistakable for a landed one.

---

### DRAFT — d-cert7-verifier-independence
`type: decision · status: draft — pending VSD ceremony · deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`
`ingredient: commit fc58a7b9 · basis: cycle-57 Confirm-3`

**Decided:** make the verifier-independence rail an explicit field (`None`=advisory N/A / `False`=
developer_self self-cert / `True`=independent verifier, unreachable today). Derived structurally in
`fuse()` from `cert_scope` (a param could be set by a caller; a derivation cannot lie). Rationale: the
rail was implicit in `population_certified=False`; a consumer reading only `cert_scope` could launder
`developer_self` into third-party trust. `True` is unreachable by construction — the slot a future
independent-verification path fills, not dead code.

### DRAFT — d-cert6-single-source-n-gate
`type: decision · status: draft — pending VSD ceremony · ingredient: commit 654fff3d · basis: F-CERT-007 anomaly-2`

**Decided:** wire `config.developer_self_cert_min_reflex_n` as THE source for the developer N-gate
(was three uncoordinated `30` literals; the operator-facing config field was the dead one). Enroll's
`--min-n` default reads it; an explicit CLI override wins but is logged on divergence. Rationale: the
fix is not "wire the field" but "make the canonical-looking thing actually canonical" — hence the
fallback literal stays alive as a non-load-bearing pure-function default rather than deleted.

### DRAFT — d-cert9-collision-guard
`type: decision · status: draft — pending VSD ceremony · ingredient: commit 71779014 · basis: F-CERT-007 anomaly-4`

**Decided (b):** collision guard, NOT (a) label→device binding. Fact A: no per-unit identity is
reachable at the enroll call site (`DEVICE_ID_CANON_v1` is secure-element-rooted + Arc-2-gated; the
only `device_id` is the model string). Fact B: the label-as-sole-scope mechanism is already live
across six labels, so (c) defer is not honest deferral. The guard closes the *silent* path (fail-
closed on ambiguity; `--extend-existing` required + logged; enrollment-instance nonce). **detection ≠
prevention:** the nonce makes accidental pooling post-hoc detectable, not prevented. **(a) is the
Arc-2-gated COMPLETION** of this arc, not a rejected alternative.

### DRAFT — d-cert1-active-oracles-manifest
`type: decision · status: draft — pending VSD ceremony · ingredient: commit 6f9fc2a8 · basis: F-CERT-005`

**Decided (a):** one scope, manifest-differentiated. `active_oracles` records per-oracle outcome
(contributed/abstained/absent/abstained_or_absent) so two verdicts on different evidence sets are
distinguishable; `cert_scope` stays binary. Rationale: (b) scope-per-oracle-set would reintroduce the
uncoordinated-literal drift D-CERT-6 just closed, at the scope layer. **Invariant:** `cert_scope`=who
vouches / `verifier_independence`=is the voucher independent / `active_oracles`=what evidence backed
it — three orthogonal questions, three fields. **Tracked+gated finding:** poep/l4l5l6 abstained-vs-
absent conflation (Optional[bool] inputs) → honest `abstained_or_absent`; resolves when the fusion
input schema is next opened.
