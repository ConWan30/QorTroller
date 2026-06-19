## Summary

DECON-1 store decomposition (D-DECON-2) + daemon Tier 1–3 self-honesty gates. Draft for **CI full-sweep validation** before further operator_api splits — per F-DECON2-1, local domain-tests gate each commit; this PR's CI run gates the merge.

### Store decomposition — **12/12 domains complete**
`_core.py`: ~18,800 → ~8,659 lines. MRO now:
`Store(ZkbaVpmMixin, MarketplaceMixin, ConsentMixin, SnapshotsGrindMixin, IoswarmMixin, ChainLogMixin, TournamentMixin, OperatorInitiativeMixin, VhpMixin, BiometricMixin, AgentsRulingsMixin, CalibrationMixin)`

- Residues #4–9 (2026-06-18/19): `tournament.py`, `operator_initiative.py`, `vhp.py`, `agents.py`, `biometric.py`, `calibration.py`
- Earlier: `marketplace.py`, `consent.py`, `snapshots_grind.py`, `ioswarm.py`, `chain_log.py`, `zkba_vpm.py`
- Diff-oracle extraction pattern; CREATE TABLE statements stay centralized in `_core._init_schema` per D-DECON-2.
- FROZEN-pinned methods remain in `_core.py` (INV-003/004/025, STRUCTURED_PROBE_TYPES, grind-chain helpers, etc.).

### Operator API — first register-function split (health_gate)
- `operator_api.py` → package: `operator_api/_app.py` + `operator_api/health_gate.py`
- `register_health_gate_routes()` owns `/health`, `/gate/{device_id}`, `POST /gate/batch`
- Public import unchanged: `from vapi_bridge.operator_api import create_operator_app`
- Gate path bookkeeping: INV-VPM-CSP-001 / INV-VPM-COMPILE-ENDPOINT-001 → `operator_api/_app.py`

### Standout: INV-022 multi-file invariant fix
The `chain_log` extraction split a FROZEN region across two files — the gate failed **correctly**. INV-022 extended to a pipe-separated multi-file pattern; digest stayed byte-identical. Invariant count reconciled 174 → 176.

### Daemon Tier 1–3 self-honesty gates
- Post-output `verify_artifact` auto-runs after output-producing tools
- READY/finalize gates block on fabrication + adversarial-verify
- Methodology registry injects failure-class lessons into `task_track`
- `daemon_health_monitor.py` pure-function probes + runner

## Test plan
- [x] PV-CI 176/176 locally (path bookkeeping for operator_api package)
- [ ] CI bridge pytest full sweep green (see F-DECON2-5 — ~96 failures are main-match pre-existing buckets, not store/MRO)
- [ ] CI SDK + Hardhat green
- [x] `test_operator_api`, `test_rate_limiting`, `test_http_cold_start_smoke` pass locally post health_gate split

## Known follow-ups (not blocking store merge classification)
- **F-DECON2-5** (flake-debt): `test_mcp_audit_tool_wrappers` batch import-order pollution — 12 failures when untracked MCP modules present; passes in isolation. Documented in `decon_residue_queue.json`.
- Remaining **operator_api** queue: agent_consent, agent_zkba_vpm, agent_ioswarm, agent_calibration, agent_biometric, agent_marketplace, agent_tournament, agent_operator_initiative, agent_grind, agent_supervisor, agent_misc (11 domains).
- `_core.py` STAY inventory doc (optional).
