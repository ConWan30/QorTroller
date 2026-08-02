---
name: seatwarden
description: "P-VSS quick reference — eligibility, flag-down, never OPEN."
---

# Seatwarden Quick Reference

| Topic | Fact |
|-------|------|
| Clause | **P-VSS** |
| Channel | `#streams` |
| May post | status / flag-down **language** (digest-only if operator wires publish) |
| Must never | VSS OPEN, CLOSED, keys, shell, chain |
| Evidence | `GET /operator/vss/eligibility`, seat script read path |

## Gamer seat act (not you)

```powershell
# Gamer key only — Seatwarden explains, does not run OPEN
python scripts/buzz_vss_seat.py  # see runbook
```

## Non-claims

- Optical streamer perception ≠ seat eligibility
- Media URL on `#streams` ≠ humanity proof
