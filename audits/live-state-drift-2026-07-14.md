# HWFL-1 Sensor A v0.2 — Live-state drift report

- Timestamp: `2026-07-14T00:18:54Z`
- Probes: 3
- Distribution: ALIGNED=3 DRIFTED=0 UNVERIFIABLE=0

## Probes

| Probe | Description | State | Live | Claimed | Evidence |
|-------|-------------|-------|------|---------|----------|
| P-WALLET | Bridge wallet IOTX balance vs CLAUDE.md SENSOR-A-LIVE:WALLET anchor | ALIGNED | 28.441474 IOTX | 28.441474 IOTX as_of=2026-07-13 | \|live - claimed\| = 0.000000 IOTX &lt;= 0.5 IOTX tolerance |
| P-CONTRACT | Deployed contract count vs CLAUDE.md SENSOR-A-LIVE:CONTRACTS anchor | ALIGNED | 69 | 69 as_of=2026-07-13 | exact match |
| P-TESTS | Per-suite test counts vs CLAUDE.md SENSOR-A-LIVE:TESTS anchor | ALIGNED | bridge=5795 sdk=647 hardhat_regex_scan=781 | bridge=5795 sdk=647 hardhat_regex_scan=781 as_of=2026-07-13 | all suites exact match |
