# QorTroller agent verification notes

Local operational memory for agents working in this repo. Prefer project
skills (`.claude/skills/`) for protocol discipline; this file records the
commands that actually keep the system functioning after multi-agent days.

## Baseline health commands (run before merge/push)

```powershell
# 1. Protocol invariants (must stay at 184)
python scripts/vapi_invariant_gate.py

# 2. Critical component smoke imports
python -c "import qortroller, qortroller_daemon; print('EA OK')"
python -c "import sys; sys.path.insert(0,'bridge'); from vapi_bridge.retina_visual_oracle import VisualOracleConfig; print('oracle', VisualOracleConfig().nim_model)"

# 3. Engineering Assistant shell hardening still in place
python -c "import inspect, qortroller; s=inspect.getsource(qortroller); assert 'shell=False' in s; print('shell-False OK')"

# 4. Retina Visual Oracle unit tests (16)
python bridge/vapi_bridge/retina_visual_oracle.py
# or via pytest collection
python -m pytest bridge/tests/test_retina_visual_oracle.py -q

# 5. Recently merged zero-coverage suites
python -m pytest bridge/tests/test_vapi_llm_client.py bridge/tests/test_retina_session_root.py bridge/tests/test_age_weight_analysis_agent.py bridge/tests/test_passport_prover.py bridge/tests/test_ioswarm_specs.py bridge/tests/test_mcp_server.py bridge/tests/test_poac_chain_integrity_monitor.py bridge/tests/test_protocol_intelligence_record_agent.py -q

# 6. Collection baseline (expect ~6748 collected; 4 pre-existing import
#    errors for quantcrypt / llm_routing.local_client are known local env debt)
python -m pytest bridge/tests --collect-only -q
```

## Components that must stay green

| Component | Path | Why |
|---|---|---|
| QorTroller Engineering Assistant | `qortroller.py`, `qortroller_daemon.py` | Operator TUI/REPL/daemon; shell tools must stay `shell=False` + `shlex.split` |
| Retina Visual Oracle | `bridge/vapi_bridge/retina_visual_oracle.py` | Game-aware VLM (football/shooter); cross-modal verify feeds PoAC |
| PV-CI gate | `scripts/vapi_invariant_gate.py` | Fail-closed 184-invariant baseline |
| Operator agent routes | `bridge/vapi_bridge/operator_api/agent_misc.py` | Phase 196/203 agent health + registration endpoints |

## Working-tree hygiene (multi-agent)

- Do not commit `QorTroller/` (duplicate tree), `_dl_ngc.py`, `_download_ngc.py` — gitignored.
- Do not commit `.env`, wallet keys, `sessions/`, biometric dumps, `audits/rwm_*`, `cfb_rwm_live_*.jsonl`.
- Uncommitted WIP that must be eye-checked before commit: large `wiki/contradictions.md` expansions, live calibration JSON, retina/EA local experiments.
- Long-lived branches (`feat/l9-*`, `fix/ci-debt-backlog`, `feat/rwm-*`) are 1000+ commits diverged — merge one-by-one with `git merge-tree` dry-run first.

## Hermes / multi-agent commit notes

- Hermes VHR stability commit `f97331f3` is already on `main`.
- Sibling hash `1e79ae78` is byte-identical (`git diff` empty); no cherry-pick needed.
- Prefer attributing agent merges in the commit body; never claim full-suite green unless the full suite was actually run.

## Dirty-tree rule of thumb

If `git status` shows modified production files (`retina_visual_oracle.py`,
`agent_misc.py`, pytest config, router tests):

1. Smoke-import the module.
2. Run its local tests.
3. Restore accidental import-path rewrites that break CI (`from vapi_bridge...` is the bridge-test convention; `from bridge.vapi_bridge...` is wrong when cwd=`bridge`).
4. Keep `bridge/pytest.ini` `asyncio_mode = strict`.
