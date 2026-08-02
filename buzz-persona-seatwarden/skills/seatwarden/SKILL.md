---
name: seatwarden
description: "P-VSS quick reference — real eligibility shape, never OPEN, no fabricated fields."
---

# Seatwarden Quick Reference (v1.1)

| Topic | Fact |
|-------|------|
| Clause | **P-VSS** |
| Channel | `#streams` |
| Eligibility route | `GET /operator/vss/eligibility` |
| OPEN actor | **Gamer key** + `scripts/buzz_vss_seat.py` only |
| Agent power | Explain / summarize / flag-down language — **never OPEN** |

## Eligibility fields (truth)

| Field | Meaning |
|-------|---------|
| `eligible` | capture_up **AND** retina_oracle_running |
| `capture_up` | Capture monitor not down |
| `retina_oracle_running` | Retina policy/oracle effective |
| `reason_if_closed` | Why closed (fail-closed) |
| `honesty.poep_enabled` | Honesty ribbon — as-is |
| `honesty.l6b_enabled` | Honesty ribbon — as-is |
| `honesty.candidate_ok` | Honesty ribbon — as-is |

## Not eligibility

- NIP-01 signature theater
- Fabricated flag enums
- Streamer optical activity
- “Human proven”

## Gamer commands (gamer key)

```powershell
python scripts/buzz_vss_seat.py --dry-run
# live OPEN path requires eligible rising edge + media URL + gamer key
```
