# HWFL-1 Sensor A v0.2 — Live-state drift report

- Timestamp: `2026-06-12T22:46:06Z`
- Probes: 3
- Distribution: ALIGNED=2 DRIFTED=0 UNVERIFIABLE=1

## Probes

| Probe | Description | State | Live | Claimed | Evidence |
|-------|-------------|-------|------|---------|----------|
| P-WALLET | Bridge wallet IOTX balance vs CLAUDE.md SENSOR-A-LIVE:WALLET anchor | ALIGNED | 32.078372 IOTX | 32.078372 IOTX as_of=2026-06-12 | \|live - claimed\| = 0.000000 IOTX &lt;= 0.5 IOTX tolerance |
| P-CONTRACT | Deployed contract count vs CLAUDE.md SENSOR-A-LIVE:CONTRACTS anchor | ALIGNED | 66 | 66 as_of=2026-06-12 | exact match |
| P-TESTS | Per-suite test counts vs CLAUDE.md SENSOR-A-LIVE:TESTS anchor | UNVERIFIABLE | (fetch error) | bridge=4330 sdk=604 hardhat=674 as_of=2026-06-10 | live fetch error: skipped via --skip-tests |
