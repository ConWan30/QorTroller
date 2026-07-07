---
type: decision
id: d-cert1-active-oracles-manifest
title: D-CERT-1 — declare the oracle set via an active-oracles manifest (option a, one scope); operator-pending signature
created: 2026-07-02T00:00:00Z
phase: VSD-LOOP
status: draft
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["s-dcert-board-clearance", "i-dcert-board-implementation-audit", "d-cert8-emit-evidence-base"]
---

DECISION — OPERATOR CO-SIGNED via git-attestation (loop-drafted; implemented + pushed `6f9fc2a8`).

CO-SIGN NOTE: decision notes are never loop-signed; the manifest stays `signed:false /
pending:operator`. Git-attestation (the operator-authorized commit under the single-committer's wallet,
this ceremony fired via /goal) is the co-sign. No forged architect signature.

WHAT IS DECIDED — **(a) one scope, manifest-differentiated**, NOT (b) scope-per-oracle-set:
1. **D-CERT-1 = YES.** `active_oracles` records per-oracle OUTCOME (contributed / abstained / absent /
   abstained_or_absent) for each proof, so two identical verdicts resting on DIFFERENT evidence sets are
   distinguishable (closes F-CERT-005, including the same-set-different-abstention variant). Derived
   inside `fuse()` from the SAME oracle checks it scores, so the manifest can NEVER disagree with the
   verdict; recorded on every path (hard-gate + scoring); null-safe (None on old records, never inferred
   retroactively).
2. **One scope, not scope-per-oracle-set.** The manifest IS the mechanism that made one-scope safe:
   F-CERT-005's gap was verdicts not declaring their evidence set; the fix is DECLARATION, not scope
   multiplication. (b) would encode the evidence set redundantly into scope strings — every future
   oracle addition minting a label and touching every `== "developer_self"` branch — reintroducing the
   uncoordinated-literal drift D-CERT-6 just closed, at the scope layer. **cert_scope STAYS binary.**
3. **The invariant, stated in-code at the cert fields:** `cert_scope` = who vouches (regime);
   `verifier_independence` = is the voucher independent; `active_oracles` = what evidence backed it.
   Three orthogonal questions, three fields, none doing another's job. Do NOT mint a scope string for a
   new oracle.
4. **SDK propagation is load-bearing under (a)** (not a convenience): the manifest IS the comparability
   mechanism, so `VAPIPresenceProof` carries it — an SDK consumer that could not read it would be back
   in the F-CERT-005 world.

TRACKED + GATED FINDING (not absorbed): poep + l4l5l6 are passed to `fuse()` as `Optional[bool]`, so
their non-contributed state cannot distinguish abstained from absent; the manifest honestly records
`abstained_or_absent`. Distinguishing them needs a richer input type (report object, or (wired, value)).
GATE: resolves when the fusion input schema is next opened.

OUT OF SCOPE (D-CERT-5): retina/authorship oracles JOINING the developer_self fusion stays D-CERT-5's
question; the manifest guarantees that when it happens it is visible on every proof it touches — which
is what makes D-CERT-5 resolvable with live data later.
