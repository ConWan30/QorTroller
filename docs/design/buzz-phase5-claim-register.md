# Buzz × QorTroller — Phase 5 Claim Register

**Canonical document:** [`docs/design/buzz-phase5-claim-register-v0.md`](./buzz-phase5-claim-register-v0.md)

This path is a **redirect only**. Do not maintain a second phrase table here.

## Why this file exists

An earlier design commit landed a phrase table at this path before G5-VER
closed. PR #103 closed G5-VER for the M17 sealed match and published the
graded register (G0–G4, row IDs R-01…R-12) at `buzz-phase5-claim-register-v0.md`.

Keeping two tables would allow stale language (e.g. "G5-VER open") to be
cited after the gate closed. All public / organizer / Buzz claim language
must resolve to a row in the **v0** register.

## Current honest ceiling (snapshot)

| What | Status |
|---|---|
| Permitted ceiling | **G1** (candidate / advisory), plus **G2 only for R-06** |
| R-06 / G5-VER | **Closed for M17** (and later certs that exit 0 the same way) |
| G5-OPS | Open — operator-local (`--preflight` → dry-run → live `#rig-ops`) |
| G5-MULTI / SEP / L6 / L6B / FRR | Open |

Full rows, never-sayable list, and honesty flags:
[`buzz-phase5-claim-register-v0.md`](./buzz-phase5-claim-register-v0.md)
and the WP-C rehearsal
[`buzz-phase5-wpc-verifier-rehearsal.md`](./buzz-phase5-wpc-verifier-rehearsal.md).
