---
type: decision
id: d-cert8-emit-evidence-base
title: D-CERT-8 — emit the calibration evidence base inline on FusedGamerPresenceProof (governing_model, calibration_band, calibration_n, calibration_player_scope) to close F-CERT-008 recomputability; operator-pending signature
created: 2026-07-02T00:00:00Z
phase: VSD-LOOP
status: draft
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["s-cert8-self-describing-proof", "i-cert8-proof-schema-audit", "c-proof-not-self-auditable", "s-devcert-investigation-synthesis"]
---

DECISION — OPERATOR CO-SIGNED 2026-07-02 (loop-drafted; operator-accepted in-session, deployer
0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692). Resolves the open block D-CERT-8 from
[[s-devcert-investigation-synthesis]]. Recommendation + rationale in [[s-cert8-self-describing-proof]].

CO-SIGN NOTE (honest crypto status): decision notes are never loop-signed, and this vault has no
separate operator-key ceremony — like every prior decision (`d-vsd-loop-authorization`,
`d-developer-self-cert`), the cryptographic manifest stays `signed:false / pending:operator`. The
operator's co-signature is expressed by **git-attestation**: this operator-authorized commit under the
single-committer's wallet is the attestation. The manifest's `pending:operator` is therefore the
honest state (no forged architect signature), and the git history is the co-sign of record.

WHAT IS DECIDED (pending operator signature):
1. **D-CERT-8 = YES.** `FusedGamerPresenceProof` emits its calibration evidence base inline so the
   proof stream alone is self-describing (closes F-CERT-008, [[c-proof-not-self-auditable]]).
2. **Fields** (names/placement operator-fixable at sign time): `governing_model` (certifying regime +
   model id), `calibration_band` (the reflex-band that defined "in-band" — see FIELD REPRESENTATION),
   `calibration_n` (the band's calibration N — the 52 — distinct from the session `n_in_band`),
   `calibration_player_scope` (the single-subject player label the band was fit on). Emitted on the
   proof + its `to_dict`.

   **FIELD REPRESENTATION — `calibration_band` is a COMMITMENT, not raw values** (resolved 2026-07-02
   against `VAPI_BIOMETRIC_PRIVACY.md`, the authority — NOT a lean): single-subject reflex timing
   (the [159.5, 429.3]-class band) is biometric-adjacent, and the doc's line is consistent — "only
   derived thresholds and ZK-proofs survive" (L231), "only thresholds stored, not raw data" (L330),
   `Biometric_secret = hash(features)` (L203), "right to know → ZK proof of data usage, not raw data"
   (L339). So `calibration_band` emits a **domain-tagged commitment** (BIOMETRIC-SNAPSHOT-family hash
   of the band spec), with the raw band values **held, disclosable on audit** — never broadcast inline.
   The F-CERT-008 auditability survives: the commitment binds *which* band authorized *which* proof
   (an auditor with the disclosed band recomputes it), and it **incidentally closes the F-CERT-007
   band-drift anomaly** — each proof pins its authorizing band even as the corpus grows. The other
   three fields (`governing_model`, `calibration_n`, `calibration_player_scope`) carry no equivalent
   sensitivity and are emitted raw.
3. **Sequencing:** D-CERT-8 lands FIRST of the open set, per the architect note — it is the substrate
   D-CERT-1 (`active_oracles`), D-CERT-6 (constant consolidation), D-CERT-7 (`verifier_independence`),
   and D-CERT-9 (player-scope identity) each write onto, turning them from reverse-engineering into
   field-checks.

HONESTY RAILS (carried from the synthesis):
- Self-describing ≠ more-certified. `population_certified` stays `False`; this closes an AUDITABILITY
  gap, not a certification gap. `cert_scope=developer_self` is unchanged.
- The evidence-base value is honestly low-entropy at N=1 (one regime, one player); its worth is
  forward — it stops being trivial the moment a second regime/oracle-set/developer exists.
- Missing evidence must emit as an explicit null/abstain, never a fabricated value (the anti-GCAP
  discipline of the fusion applies to its self-description too).

OUT OF SCOPE: no FROZEN-v1 / 228B PoAC / chain / IOTX; no threshold or weight change; D-CERT-5 (does
authorship bind to the cert) is untouched — it stays gated on the l2_ads RP-reliable-L2 finding, and
D-CERT-8 was chosen precisely because it does NOT depend on that parked channel.

IMPLEMENTATION (follows signature, separate commit): add the four fields to `FusedGamerPresenceProof`
(novel_presence_fusion.py:45–75) with null-safe defaults + thread them through the build site (:281,
:306–307) and `to_dict`; source them from the live PoEP band/verdict rather than the filesystem so the
proof stream is self-sufficient. Then D-CERT-1/6/7/9 become field-level follow-ups.
