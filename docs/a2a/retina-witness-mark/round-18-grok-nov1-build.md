# A2A — RWM · round 18 · grok (NOV-1 build under GO)

**Channel:** operator **GO NOV-1 plan**  
**Prior:** plan `8a5e57b3`

---

## Shipped

| Path | Role |
|------|------|
| `bridge/vapi_bridge/rwm_stranger_pack.py` | `build_stranger_pack` / `verify_stranger_pack` (archive-free) |
| `scripts/rwm_nov1_cli.py` | `build` / `verify` |
| `bridge/tests/test_rwm_nov1.py` | T1–T5 |

Schema: `qortroller-rwm-stranger-pack-v0` · mode `sd1_inline_media_v0`

## Tests

`pytest` NOV-1 + NOV-2 + escrow → **27 passed**

## Dogfood

`live_01` build+verify stranger pack (local audits, not committed).

## Rails

No PoAC / FROZEN / PV-CI / stop-path / chain spend. Merkle = NOV-1.1.

```text
python scripts/rwm_nov1_cli.py build --archive retina_kf_archive/... \
  --reveal 0,10,100 --reason "tournament dispute: sample frames" --case-id X
python scripts/rwm_nov1_cli.py verify --pack audits/rwm_stranger_X.json
```

*Round-18 — sole agent GO build 2026-07-25.*
