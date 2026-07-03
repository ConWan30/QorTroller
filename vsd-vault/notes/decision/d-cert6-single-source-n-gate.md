---
type: decision
id: d-cert6-single-source-n-gate
title: D-CERT-6 — single-source the developer N-gate on config.developer_self_cert_min_reflex_n; operator-pending signature
created: 2026-07-02T00:00:00Z
phase: VSD-LOOP
status: draft
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["s-dcert-board-clearance", "i-dcert-board-implementation-audit", "i-fcert007-followup-report"]
---

DECISION — OPERATOR CO-SIGNED via git-attestation (loop-drafted; implemented + pushed `654fff3d`).

CO-SIGN NOTE: decision notes are never loop-signed; the manifest stays `signed:false /
pending:operator`. The operator's co-signature is the git-attestation (the operator-authorized commit
under the single-committer's wallet, this ceremony fired via /goal). No forged architect signature.

WHAT IS DECIDED:
1. **D-CERT-6 = YES, wire the config field as THE source** (not delete it). The N>=30 developer gate
   existed as three uncoordinated literals — enroll `--min-n` default, `single_subject_reflex_model`'s
   function default, and `config.developer_self_cert_min_reflex_n` (which was DEAD, defined + documented
   + never read). F-CERT-007 anomaly-2.
2. **`config.developer_self_cert_min_reflex_n` becomes the single source:** enroll reads it for the
   `--min-n` default via `resolve_min_n()`; an explicit CLI `--min-n` still wins (operator intent) but
   is LOGGED when it diverges from config, so a one-off override can never silently become a fourth
   uncoordinated literal. The D-CERT-8 `governing_model` embeds the resolved `min_n` by construction, so
   a future mismatch surfaces on the proof itself, not only in a code audit.
3. **Why config wins over consolidating on the hardcoded literal:** the config field is the
   OPERATOR-FACING surface — F-CERT-007's finding was precisely that the canonical-looking field was the
   dead one. The fix is not "wire the field" but "make the canonical-looking thing actually canonical";
   that is why the fallback literal stays alive as a non-load-bearing pure-function default rather than
   deleted (minimal blast radius; poep_calibration.py untouched).

HONESTY RAILS: additive; no verdict-semantics change; the function default is now provably
non-load-bearing (the enroll call site passes the config-sourced value explicitly).
