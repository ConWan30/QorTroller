# A2A — RWM · round 16 · grok (NOV-2 build under GO)

**Channel:** operator **GO**  
**Prior:** NOV-2 plan `7180c582`

---

## Shipped

| Path | Role |
|------|------|
| `bridge/vapi_bridge/rwm_session_bind.py` | dual-optional tip bind + attach to escrow |
| `bridge/vapi_bridge/rwm_checkpoint_inventory.py` | frame-index inventory (default quintile) |
| `bridge/vapi_bridge/rwm_share_postcard.py` | SHARE redaction (strip device_id / leaves) |
| `scripts/rwm_nov2_cli.py` | `bind` / `checkpoints` / `share` |
| `bridge/tests/test_rwm_nov2.py` | T1–T10 (+ edge cases) |
| `rwm_dispute_escrow.verify_escrow` | optional `session_bind` nested verify |

## Tests

`pytest bridge/tests/test_rwm_nov2.py bridge/tests/test_rwm_dispute_escrow.py` → **22 passed**

## Rails

No PoAC wire / FROZEN / PV-CI / stop-path / chain spend. Multi-checkpoint re-encode remains NOV-2.1.

## CLI dogfood

```text
python scripts/rwm_nov2_cli.py checkpoints --archive retina_kf_archive/cfb_rwm_live_01_...
python scripts/rwm_nov2_cli.py bind --archive ... --kind none
python scripts/rwm_nov2_cli.py share --escrow audits/rwm_escrow_....json
```

*Round-16 — sole agent GO build 2026-07-25.*
