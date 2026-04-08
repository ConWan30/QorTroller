# WHAT_IF: WIF-024 — Post-Erasure Separation Ratio Recompute

[VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

## Classification

| Field | Value |
|-------|-------|
| Layer | W1 (Protocol Risk) |
| Status | CLOSED (Phase 165) |
| Filed | Phase 165 planning (2026-04-04) |

## W1 — Failure Mode

When a player with multiple `device_id`s (e.g., P1 registers device_A for sessions
1–5 then device_B for sessions 6–11) revokes consent on device_A, the consent gate
blocks only device_A's future inserts. Existing sessions from device_A already
contributed to `n_per_player` counts and Mahalanobis centroid computation in
`get_separation_defensibility_status()`.

**Implication:** The separation ratio on-chain (e.g., ratio=1.261, N=11) may include
centroid contributions from device_A even after GDPR Art.17 erasure. The committed
ratio is no longer honest — it overstates the consented corpus.

## Mitigation — CLOSED (Phase 165)

`anonymize_device_records()` gains `post_erasure_recompute:bool=False` parameter.

When `True`:
1. Snapshots current separation ratio into `post_erasure_ratio_log` before erasure
2. Sets `recompute_needed=True` (operator must re-run `analyze_interperson_separation.py`)
3. Records `ratio_after=NULL` (pending re-analysis)

**New table:** `post_erasure_ratio_log`:
- `device_id / n_anonymized / ratio_before / ratio_after / recompute_needed`
- `triggered_by / consent_type / recompute_ts / created_at`

## API

- `GET /agent/post-erasure-recompute-status` (7 keys: `consent_ledger_enabled /
  total_recomputes / pending_recomputes / latest_recompute_ts / latest_ratio_before /
  recompute_needed / timestamp`)
- Tool #122 `trigger_post_erasure_recompute (device_id, dry_run)`
- `PostErasureRecomputeResult` (6 slots) + `VAPIPostErasureRecompute` SDK

## Protocol After GDPR Erasure

```
1. POST /agent/revoke-consent (execute_erasure=True)
2. anonymize_device_records(device_id, post_erasure_recompute=True)
3. Check GET /agent/post-erasure-recompute-status → recompute_needed=True
4. Run: python scripts/analyze_interperson_separation.py --session-type mixed_biometric_probe
5. Update separation_defensibility_log with new ratio
6. POST /agent/commit-separation-ratio (new ratio)
```

## Related Pages

- [[separation_ratio]]
- [[wif_018_consent_revocation]]
- [[phase_166]]
