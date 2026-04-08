# WHAT_IF: WIF-018 + WIF-019 — Consent Gate in Defensibility Pipeline

[VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

## Classification

| Field | Value |
|-------|-------|
| Layer | W1 (WIF-018) + W2 (WIF-019) |
| Status | CLOSED (Phase 160+161) |
| Filed | 2026-04-04 (AutoResearch cycle 7) |

## WIF-018 — W1: Biometric Data After Consent Revocation

`insert_separation_defensibility_log` accepted structured probe sessions for any
device regardless of consent status. A player who revoked consent (GDPR Art.7) or
requested erasure (GDPR Art.17) could still contribute new biometric sessions.

**Regulatory exposure:** €20M or 4% global revenue fines for unlawful biometric
processing after consent revocation (GDPR Art.9 + Art.7(3) + Art.17).

**Closed Phase 160:** `consent_ledger` table + `_check_consent_gate()` in
`insert_validation_record` + `anonymize_device_records()`.

## WIF-019 — W2: Consent as Composable Privacy Primitive

`get_consent_status(device_id)` as a queryable bridge primitive enabling every
data-writing agent to check consent before storing biometric records.

**Composable gate:**
```
consent_given AND defensible AND decay_factor > 0.25
```

Full privacy-compliant enrollment gate:
- Phase 159 BiometricPrivacyComplianceAgent (BP-001 TBD decay)
- Phase 160 consent_ledger
- Phase 161 ruling_validation_log redaction (WIF-020)
- Phase 162 consent-aware corpus (WIF-021)

## WIF-020 — GDPR Art.17 Erasure Gap

Phase 160 `anonymize_device_records()` only redacted `agent_rulings`. The
`ruling_validation_log.divergence_reason` (containing biometric inference reasoning)
remained unredacted — secondary audit trail survives erasure.

**Closed Phase 161:** Extended `anonymize_device_records()` to also redact
`ruling_validation_log.divergence_reason='[redacted - GDPR Art.17 erasure]'`.

## Key APIs (Phase 160+)

- `GET /agent/consent-status/{device_id}` — 7 keys
- `POST /agent/register-consent`
- `POST /agent/revoke-consent` (execute_erasure=True default)
- `GET /agent/consent-gate-status` — 5 keys

## Related Pages

- [[agent_fleet]]
- [[phase_166]]
- [[wif_024_post_erasure_recompute]]
