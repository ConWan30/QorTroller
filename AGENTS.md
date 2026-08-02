# QorTroller agent verification notes

Local operational memory for agents working in this repo. Prefer project
skills (`.claude/skills/`) for protocol discipline; this file records the
commands that actually keep the system functioning after multi-agent days.

## FIRST STEP on a live-rig session (do this before other work)

**Doc:** `docs/runbook/NEXT_SESSION_FIRST.md`  
**Shortcut:** `scripts/start_ncaa27_dual_path.ps1` (or `.bat`)

Operator rig map locked 2026-08-02 (do **not** rediscover by guessing indices):

| Index | Device | Role |
|------:|--------|------|
| 0 | `720p HD Camera` | House webcam — never for grind |
| 1 | capture card path | Bridge `--uvc-index 1` |
| 2 | `OBS Virtual Camera` | Streamer `--streamer-device 2` (`dshow`) |

```powershell
cd C:\Users\Contr\vapi-pebble-prototype
# Confirm operator ready (capture-rig skill), then:
.\scripts\start_ncaa27_dual_path.ps1
# Eye-check logs/eye_check_streamer_*.png (must be GAME not desk)
# Stop:
python scripts/retina_capture_daemon.py stop
```

Streamer remains advisory — never OR-merge optical activity into `poep_enabled`.

## Baseline health commands (run before merge/push)

```powershell
# 1. Protocol invariants (must stay at 188)
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
| PV-CI gate | `scripts/vapi_invariant_gate.py` | Fail-closed 188-invariant baseline (grew after VSS/Phase-O0 merges) |
| Operator agent routes | `bridge/vapi_bridge/operator_api/agent_misc.py` | Phase 196/203 agent health + registration endpoints |
| QorTroller ACP gateway (Phase 4) | `scripts/qortroller_acp_gateway.py` | `@EA` mention surface in `#rig-ops`; fail-closed operator allow-list, fixed-argv tools (`shell=False`), digest-only replies, local JSONL audit trail; Grok Build primary / Devin for heavy work. Runbook: `docs/design/buzz-phase4-acp-gateway-runbook.md` |
| QorTroller Buzz bot (Phase 1) | `scripts/qortroller_buzz_bot.py` | Buzz-native rig-status + session-digest bot; env-only keys; digest-only posts; wired read path (BridgeClient → `/player/session-status`) + Rust-helper publish (`qortroller-buzz publish` subprocess) |

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

## Buzz integration (Phase 1 — operator greenlight gate)

Full scope: `docs/design/buzz-qortroller-gamer-mvp-v0.md`.

One-line rule: **Buzz is the social/ops plane; QorTroller is the truth plane;
Nostr carries pointers and operator signals, never the biometric substrate.**

Before any live Buzz wiring:

1. Keys are env-only (`BUZZ_PRIVATE_KEY`, `BUZZ_OWNER_PRIVATE_KEY`). Never
   commit an `nsec`. The old `ea_buzz_bridge.py` scratch files are scrubbed
   and the key in them is compromised — rotate it.
2. EA bot key is NOT derived from ioID tokenId 498. Gamer key proves the
   human; EA key proves the operator steward. Compose, never conflate.
3. Use Buzz-correct protocol: kind 9 with `h` tags (NIP-29), kind 9000
   self-add `role=bot`, NIP-42 auth (+ NIP-OA if owner-attested). Local
   relay is `ws://localhost:3000`, not 8080.
4. Digest-only posts: `session_id`, `verdict`, `commitment_root`,
   `poep_enabled`, `l6b_enabled`, `candidate_ok`. Post honesty flags as-is.
   Never post raw HID/IMU/L4/frames, full PoAC payloads, or any key.
5. Bot scaffold: `scripts/qortroller_buzz_bot.py` (+ env template). The
   signing/WS loop is stubbed until Phase 1 is greenlit and a real Nostr
   library (nostr-sdk or python-nostr) is wired in — do NOT hand-roll
   secp256k1; NIP-01 event id is `sha256([0, pubkey, created_at, kind,
   tags, content])`, not sort_keys JSON.
