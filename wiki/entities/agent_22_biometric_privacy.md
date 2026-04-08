# ENTITY: Agent #22 — BiometricPrivacyComplianceAgent

[VAPI:Phase166:MEMORY.md:MEASURED]

## Overview

Agent #22, introduced in Phase 159. Monitors Temporal Biometric Decay (BP-001)
across all enrolled devices. Fires `biometric_decay_warning` bus event when the
fleet-average decay factor drops below the warning threshold.

## Temporal Biometric Decay Formula [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

```
TBD(t) = e^(-lambda * t)
lambda = ln(2) / tau_half
tau_half = 90 days
```

- A decay factor of 1.0 = data captured today
- A decay factor of 0.5 = data ~90 days old (one half-life)
- A decay factor of 0.25 = data ~180 days old (two half-lives) — WARNING threshold
- Warning fires when `mean_decay_factor < 0.25`

## Warning Threshold

```
warning_triggered = True when mean_decay_factor < 0.25
~2 half-lives ≈ ~180 days old
```

At this point biometric sessions are considered stale for tournament use.
Operator must recapture calibration sessions to restore data freshness.

## Configuration [VAPI:Phase166:MEMORY.md:MEASURED]

| Config Field | Value | Status |
|-------------|-------|--------|
| biometric_privacy_enabled | True | DEFAULT |
| bp001_half_life_days | 90.0 | FROZEN (GDPR-aligned) |

## Storage

- Table: `privacy_compliance_log`
- Methods: `insert_privacy_compliance_log()` + `get_privacy_compliance_status()`

## API

- `GET /agent/biometric-privacy-status` (8 keys):
  `biometric_privacy_enabled / bp001_half_life_days / records_monitored /
   records_expired / mean_decay_factor / warning_triggered / privacy_budget_epsilon / timestamp`
- Tool #116: `get_biometric_privacy_status`
- SDK: `BiometricPrivacyComplianceResult` (6 slots) + `VAPIBiometricPrivacy`

## Interaction with Consent System

Works alongside Phase 160 `consent_ledger`:
- Decay monitors TIME dimension of biometric data validity
- Consent monitors LEGAL dimension (Art.7 withdrawal, Art.17 erasure)
- Composable gate: `consent_given AND decay_factor > 0.25` = full privacy compliance

## Related Pages

- [[agent_fleet_registry]]
- [[agent_fleet]]
- [[wif_018_consent_revocation]]
- [[phase_166]]
