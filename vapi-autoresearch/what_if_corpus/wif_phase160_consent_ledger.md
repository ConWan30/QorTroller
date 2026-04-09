# WHAT_IF Entry — AutoResearch Cycle 7 (2026-04-04)

**Source**: AutoResearch cycle 7, score=1.000
**Phase**: 159 → 160 candidates

---

## WIF-018 — Biometric Data Used After Consent Revocation: No Gate in Defensibility Pipeline (Phase 160 candidate)

**W1 — Failure mode**: `insert_separation_defensibility_log` accepts structured probe sessions for any device regardless of consent status. A player who revokes consent (GDPR Art.7) or requests erasure (GDPR Art.17) can still have new biometric sessions inserted into the separation defensibility log — their biometric features continue contributing to the live separation ratio measurement.

**Implication**: Phase 151 frozenset whitelist (`STRUCTURED_PROBE_TYPES`) enforces session type purity but does NOT check consent. `BiometricPrivacyComplianceAgent` (Phase 159) tracks decay but has no consent query interface. The `privacy_compliance_log` is write-only — no agent can ask "has device X consented?" before accepting a session. Any agent writing to `separation_defensibility_log` operates without a consent gate.

**Cryptographic grounding**: Under GDPR Art.7(3), withdrawal of consent must be as easy as giving it. Under GDPR Art.17 (Right to Erasure), personal data must be erased without undue delay on request. Since PoAC records are biometric data (GDPR Art.9, special category), the processing basis for any continued analysis is the player's active consent. No consent ledger → no processing lawfulness audit trail → regulatory exposure for tournament operators.

**Economically motivated failure**: Tournament operators face €20M or 4% global revenue GDPR fines for unlawful biometric processing. A single erasure request not honored within 30 days creates liability that exceeds token launch revenue. Phase 159 monitoring without enforcement is legally insufficient.

**Mitigation (Phase 160)**:
1. `consent_ledger` table: per-device consent record with `consent_given`, `revoked_at`, `erasure_requested`, `erasure_completed`
2. `insert_separation_defensibility_log` gains consent guard: raises `ValueError("device_not_consented")` when `consent_given=False` or `revoked=True`
3. `anonymize_device_records()` soft-deletes biometric fields (NULL) in `pitl_session_proofs` and `separation_defensibility_log` on erasure request
4. `right_to_erasure_log` table captures each erasure action with timestamp + fields_anonymized count

**Status**: OPEN — Phase 160 candidate. Filed 2026-04-04 (AutoResearch cycle 7).

---

## WIF-019 — Consent Ledger as Composable Privacy Primitive (Phase 160 candidate)

**W2 — Opportunity**: A `ConsentLedgerAgent` exposes `consent_given` status as a queryable bridge primitive, enabling every data-writing agent to check consent before storing biometric records — without hard-coding consent logic in each agent.

**Mechanism**:
1. `consent_ledger` table: `device_id / consent_type / consent_given / consent_ts / revoked_at / revocation_reason / erasure_requested / erasure_completed / created_at`
2. `right_to_erasure_log` table: `device_id / requested_at / fields_anonymized / completed_at / created_at`
3. `get_consent_status(device_id)` → `{consent_given, consent_ts, revoked, erasure_requested, erasure_completed, error}` — callable from any agent
4. `POST /agent/register-consent` + `POST /agent/revoke-consent` REST endpoints for operator tooling
5. `GET /agent/consent-status/{device_id}` — privacy compliance dashboard
6. `insert_separation_defensibility_log` reads consent_given via `get_consent_status()` before each insert — **composable gate**
7. `anonymize_device_records()` soft-deletes `pitl_session_proofs.humanity_score/evidence_json` + NULLs `separation_defensibility_log.ratio/n_per_player_json` for erased devices

**Why VAPI-Only**:
- Requires Phase 151 structured probe session pipeline (consent gate must respect STRUCTURED_PROBE_TYPES whitelist)
- Requires Phase 159 BiometricPrivacyComplianceAgent decay monitoring (consent ledger and decay monitoring are complementary BP-001/BP-002 primitives)
- Requires Phase 159 `privacy_compliance_log` as the decay audit trail (consent ledger is the second compliance audit trail)
- No competing gaming DePIN protocol has per-device biometric consent as a queryable on-chain-adjacent primitive
- Composable: `consent_given AND defensible AND decay_factor > 0.25` = full privacy-compliant enrollment gate

**Phase candidate**: Phase 160 (~3h effort) — `consent_ledger` + `right_to_erasure_log` tables + `get_consent_status` + `anonymize_device_records` + 3 REST endpoints + Tool #117 + `ConsentLedgerResult` SDK

**Exclusive because**:
- Consent gate integrated into `insert_separation_defensibility_log` — requires Phase 151 STRUCTURED_PROBE_TYPES whitelist infrastructure
- Composable with TBD decay monitoring (Phase 159 BP-001) and separation defensibility gate (Phase 150)
- anonymize_device_records() requires Phase 99B `pitl_session_proofs` schema knowledge

**Status**: NEW — Phase 160 candidate.
