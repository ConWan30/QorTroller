# PATH-B v2 Live-Write Executor Activation Runbook

**Phase**: Operator Initiative O3_ACTING → autonomous execution
**Ship commit**: `6e4d1e8e` (v2 wire, 2026-05-18)
**State coherence commit**: `45b5b00e` (activation_log reconstruction, 2026-05-19)
**Guardrail commit**: `<this commit>` (mythos_spending_log_drift, 2026-05-19)
**Authority**: Operator-side; bridge restart required

This runbook documents the deterministic operator action sequence to activate the PATH-B v2 live-write executor autoloop. Each step has a clear pre-condition and post-condition gate; if any post-condition fails, halt and investigate before proceeding.

---

## §1 Pre-activation checklist

All five items below MUST be verified before flipping the master enable flag. None require chain operations.

### §1.1 — Verification gates (all must be green)

Run from project root:

```bash
# Gate 1: PV-CI invariants intact
python scripts/vapi_invariant_gate.py
# Expected: "[invariant_gate] PASS — 128 invariants verified"

# Gate 2: mythos post-O3 audit clean
python -c "
import asyncio, sys
sys.path.insert(0, 'bridge')
from vapi_bridge.mythos_variants import mythos_post_o3_ceremony_audit
print(asyncio.run(mythos_post_o3_ceremony_audit(include_chain_reads=True)))
"
# Expected: empty list []

# Gate 3: activation_log has 3 rows (Sentry/Guardian/Curator @ O3_ACTING)
python -c "
import sqlite3
con = sqlite3.connect('bridge/vapi_store.db')
rows = con.execute('SELECT agent_id, to_phase FROM operator_agent_activation_log').fetchall()
print(f'{len(rows)} rows: {rows}')
"
# Expected: 3 rows, all to_phase=O3_ACTING

# Gate 4: spending_log_drift Mythos guardrail returns []
python -c "
import asyncio, sys
sys.path.insert(0, 'bridge')
from vapi_bridge.mythos_variants import mythos_spending_log_drift
print(asyncio.run(mythos_spending_log_drift()))
"
# Expected: empty list []

# Gate 5: bridge tests pass
python -m pytest bridge/tests/test_phase_o1_d_path_b_live_write_executor.py -q
# Expected: 14 passed
```

If any gate is red: **STOP**. Investigate the failure with the relevant Mythos variant before proceeding.

### §1.2 — Five-layer default-deny posture audit

Verify the following state by reading `bridge/.env`:

| Setting | Required Value | Purpose |
|---|---|---|
| `CHAIN_SUBMISSION_PAUSED` | `true` | Final-defense kill-switch at bridge level |
| `PHASE_O3_AUTO_SUPERSEDE_ENABLED` | `true` | Empirical-evidence supersession (504h gate already cleared) |
| `PHASE_O3_GUARDIAN_LIVE_WRITES_ENABLED` | `true` | Guardian opt-in confirmed intentional (LOCAL writes only, 0.0 IOTX budget) |
| `PHASE_O3_ANCHOR_SENTRY_DAILY_IOTX_BUDGET` | `0.05` | 10× tighter than architectural 0.5 default |
| `PHASE_O3_CURATOR_DAILY_IOTX_BUDGET` | `0.05` | 10× tighter than architectural 0.5 default |
| `PHASE_O3_EXECUTOR_KILL_ALL` | `false` | Emergency hatch not engaged |
| `PHASE_O3_EXECUTOR_INTERVAL_S` | `60` | 60s cadence |
| `PHASE_O3_ANCHOR_SENTRY_LIVE_WRITES_ENABLED` | (unset → False) | Sentry chain-write gated off |
| `PHASE_O3_CURATOR_LIVE_WRITES_ENABLED` | (unset → False) | Curator chain-write gated off |

**Critical**: confirm `CHAIN_SUBMISSION_PAUSED=true` remains held. This is the final defense — even if other gates fail, this prevents any actual chain submission.

---

## §2 Activation sequence

### Step 1 — Add the master enable to bridge/.env

Open `bridge/.env` in your editor. Add this line:

```bash
PHASE_O3_EXECUTOR_AUTOLOOP_ENABLED=true
```

Save and close.

### Step 2 — Restart the bridge

```bash
# Terminal 1: stop currently-running bridge (if any) — Ctrl+C
# Then start fresh:
python -m bridge.vapi_bridge.main
```

Wait for startup to complete. Look for this log line confirming v2 wiring picked up the flag:

```
Phase O1-D-PATH-B v2: live-write executor autoloop started (interval=60s; kill_all=False; per-agent flags: sentry=False/guardian=True/curator=False)
```

If the line does NOT appear after 60 seconds of startup activity: the flag was not picked up. Verify env var is set, restart again.

### Step 3 — Confirm executor is running

In a separate terminal:

```bash
# Verify the bridge process has the o3_executor_autoloop task:
curl -s http://localhost:8080/health | python -m json.tool
# Expected: {"status": "ok"}

# Verify spending_log table was migrated at startup:
python -c "
import sqlite3
con = sqlite3.connect('bridge/vapi_store.db')
n = con.execute('SELECT COUNT(*) FROM operator_agent_chain_spending_log').fetchone()[0]
print(f'spending_log: N={n} events')
"
# Expected: N=0 initially (table migrated; no events yet)
```

### Step 4 — Monitor first cycle (60s)

The executor runs `process_accepted_drafts` every 60 seconds. On its first cycle, it will:
1. Read `operator_agent_drafts` table for any rows with `operator_decision='accept'` not yet executed
2. For each accepted draft, evaluate 4-gate authorization:
   - Gate 1: agent at O3_ACTING ← will PASS for all 3 (activation_log reconstructed)
   - Gate 2: per-agent `live_writes_enabled` flag ← only Guardian PASSES initially
   - Gate 3: daily budget remaining ← all PASS (no spending yet)
   - Gate 4: `kill_all=false` ← PASSES
3. For Guardian's accepted drafts (if any): fires local audit-draft write, records cost_iotx=0 event in spending_log
4. For Sentry/Curator accepted drafts: skip silently (Gate 2 fails)

Watch for spending_log rows accumulating:

```bash
# Every 5 minutes, query:
python -c "
import sqlite3
con = sqlite3.connect('bridge/vapi_store.db')
rows = con.execute('SELECT agent_id, action_name, cost_iotx, tx_hash, error FROM operator_agent_chain_spending_log ORDER BY created_at DESC LIMIT 10').fetchall()
for r in rows:
    agent_short = r[0][:10]+'...'
    print(f'  {agent_short} {r[1]:30s} cost={r[2]:.6f} tx={(r[3] or \"\")[:12]}... err={r[4]}')
"
```

Expected first 24h: only Guardian rows with cost_iotx=0.0 (local writes), all tx_hash empty (no chain).

---

## §3 Baseline monitoring window (24-48 hours)

Continuous monitoring during the first 24-48h baseline period:

### §3.1 — Mythos guardrail every 60 minutes

```bash
python -c "
import asyncio, sys
sys.path.insert(0, 'bridge')
from vapi_bridge.mythos_variants import mythos_spending_log_drift
findings = asyncio.run(mythos_spending_log_drift())
for f in findings: print(f'[{f.severity}] {f.description[:120]}')
print(f'Total: {len(findings)}')
"
```

**Expected**: 0 findings. **If findings surface, see §4 for rollback.**

### §3.2 — Daily budget check

Confirm Guardian remains within its 0.0 IOTX budget (zero spending — local writes only):

```bash
python -c "
import sqlite3
con = sqlite3.connect('bridge/vapi_store.db')
g = '0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1'
row = con.execute('SELECT COALESCE(SUM(cost_iotx), 0.0) FROM operator_agent_chain_spending_log WHERE agent_id=?', (g,)).fetchone()
print(f'Guardian 24h spend: {row[0]:.6f} IOTX (budget 0.0)')
"
```

**Expected**: `0.000000 IOTX` (always zero — Guardian's O3 authority is local audit-drafting only).

If non-zero: Guardian fired a chain operation it shouldn't have. Engage `PHASE_O3_EXECUTOR_KILL_ALL=true` immediately and investigate.

### §3.3 — Bridge health endpoint

```bash
curl -s http://localhost:8080/health
```

**Expected**: `{"status":"ok"}` continuously. Any failure indicates bridge instability — STABILITY-9 residual or new issue.

---

## §4 Rollback procedure (if anything looks wrong)

### §4.1 — Emergency stop (HIGHEST PRIORITY)

Engage emergency kill-all without restarting bridge:

```bash
# In a separate terminal, while bridge still running:
echo "PHASE_O3_EXECUTOR_KILL_ALL=true" >> bridge/.env
# Then restart bridge to pick up:
# (kill current bridge process, then restart)
python -m bridge.vapi_bridge.main
```

This sets Gate 4 to `True` → executor fails authorization for ALL agents → next cycle is a silent no-op for everything.

### §4.2 — Full rollback to v2-dormant state

If kill-all is not sufficient and you want full reversion:

1. Edit `bridge/.env`:
   ```
   # Comment out or remove these two lines:
   # PHASE_O3_EXECUTOR_AUTOLOOP_ENABLED=true
   # PHASE_O3_GUARDIAN_LIVE_WRITES_ENABLED=true
   ```
2. Optionally engage kill-all: `PHASE_O3_EXECUTOR_KILL_ALL=true`
3. Restart bridge
4. Confirm via startup log that the `Phase O1-D-PATH-B v2: live-write executor autoloop` line does NOT appear

### §4.3 — DB inspection if rollback didn't resolve

If kill-all + autoloop disable didn't prevent unexpected behavior:

```bash
# Query last 100 spending events to understand what fired:
python -c "
import sqlite3
con = sqlite3.connect('bridge/vapi_store.db')
rows = con.execute('SELECT * FROM operator_agent_chain_spending_log ORDER BY created_at DESC LIMIT 100').fetchall()
for r in rows: print(r)
"

# Run the spending drift audit for the analysis:
python -c "
import asyncio, sys
sys.path.insert(0, 'bridge')
from vapi_bridge.mythos_variants import mythos_spending_log_drift
print(asyncio.run(mythos_spending_log_drift()))
"
```

---

## §5 Post-baseline next steps

After 24-48h of clean baseline (zero spending drift findings, Guardian local writes only, kill-all not engaged):

### §5.1 — Opt-in Sentry chain writes (when ready)

```bash
# In bridge/.env, add:
PHASE_O3_ANCHOR_SENTRY_LIVE_WRITES_ENABLED=true
# Optionally lift CHAIN_SUBMISSION_PAUSED for actual chain operations:
# CHAIN_SUBMISSION_PAUSED=false
# (But verify wallet balance first — at least 1.0 IOTX recommended)
```

Restart bridge. Sentry's `pda-attestation-anchor` will now fire for accepted drafts at ~0.0008 IOTX per anchor (capped at 0.05 IOTX/day = ~62 anchors/day max per Gate 3).

### §5.2 — Opt-in Curator chain writes

Same pattern as §5.1 but with `PHASE_O3_CURATOR_LIVE_WRITES_ENABLED=true`. Curator's `marketplace-listing-suspend` fires at ~0.001 IOTX per suspension.

### §5.3 — Curator graduation to O2_SUGGEST (different ladder rung)

Independent track from chain writes. Curator's promotion criterion is N≥50 reviews + 0 false-positive rate under shadow data. Pre-authored bundle Merkle `0xeb400a5c9b410c6f3035a595e2c36dee915f6b2447f822c72c46b164ccd5daa9` already exists. Ceremony script: TBD.

---

## §6 Invariants preserved by this activation

| Invariant | Status | Where enforced |
|---|---|---|
| FROZEN-v1 PATTERN-017 primitives | UNCHANGED | All 11 commitment-family + POSEIDON-AS capability |
| PV-CI 128/128 | UNCHANGED | scripts/vapi_invariant_gate.py |
| Cedar bundle Merkles on-chain | UNCHANGED | AgentScope contract `0xc694692a…79FF13` |
| Five-layer default-deny | PARTIALLY LIFTED | autoloop now enabled; per-agent flags still default-False for chain writes |
| Cross-agent skill separation | UNCHANGED | Sentry+Guardian+Curator Cedar policies distinct |
| CHAIN_SUBMISSION_PAUSED final defense | OPERATOR-CHOICE | Held in §1.2 verification; lifted per §5.1 only when ready |

---

## §7 Verification trail

This runbook is anchored to:
- Commit `6e4d1e8e` — PATH-B v2 main.py wire
- Commit `45b5b00e` — activation_log reconstruction primitive
- Commit `<this commit>` — mythos_spending_log_drift guardrail + this runbook
- CLAUDE.md NOTE L39 — 2026-05-17 O3 ceremony tx hashes (Sentry/Guardian/Curator op_tx + gov_tx pairs)
- `vsd-vault/proposals/drafts/qresce-0001-r0-artifacts/trademark_clearance_evidence.md` — brand-discipline trail

---

*Drafted 2026-05-19 during the post-Path-2-verification ship cycle. Update when activation parameters change OR new agents added to the Operator Initiative fleet.*
