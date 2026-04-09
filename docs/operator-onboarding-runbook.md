# VAPI Operator Onboarding Runbook

**Phase 106 — Operator Bootstrapping and Live Mode Certification**

This runbook covers the end-to-end process for bringing a VAPI bridge deployment from
initial setup to a certified live mode state ready for tournament deployment.

---

## Prerequisites

1. **Bridge running**: `python -m uvicorn vapi_bridge.main:app --host 0.0.0.0 --port 8080`
2. **API key configured**: `OPERATOR_API_KEY=<your-key>` in `bridge/.env`
3. **Wallet funded**: `~4.6 IOTX` for testnet transactions
4. **Contracts live**: All 38 contracts deployed (see `contracts/deployed-addresses.json`)

---

## Step 1 — One-Call SDK Bootstrap

The fastest path to a bootstrapped operator state uses `VAPIOperatorOnboarding.bootstrap()`:

```python
from sdk.vapi_sdk import VAPIOperatorOnboarding

onboarding = VAPIOperatorOnboarding(
    base_url="http://localhost:8080",
    api_key="your-operator-api-key"
)
result = onboarding.bootstrap()

print(f"fully_bootstrapped: {result.fully_bootstrapped}")
print(f"pmi: {result.pmi} ({result.pmi_label})")
print(f"activation_committed: {result.activation_committed}")
print(f"dry_run_active: {result.dry_run_active}")
```

`bootstrap()` performs the following sequence automatically:
1. `GET /agent/protocol-maturity` — reads current PMI state
2. If `activation_committed=False`: runs `POST /agent/run-activation-simulation` (n=110 sessions)
3. `POST /agent/commit-activation` — persists dry_run=False to activation_state store
4. `GET /agent/protocol-maturity` — verifies final state

`bootstrap()` is idempotent — safe to call multiple times.

**Expected output on success:**
```
fully_bootstrapped: True
pmi: 1 (simulated)
activation_committed: True
dry_run_active: False
```

---

## Step 2 — Verify Protocol Maturity

Confirm bridge is in live mode:

```bash
curl "http://localhost:8080/agent/protocol-maturity?api_key=<key>"
```

Expected:
```json
{
  "pmi": 1,
  "pmi_label": "simulated",
  "activation_committed": true,
  "dry_run_active": false,
  "vhp_found": true
}
```

---

## Step 3 — Run Live Mode Readiness Validation (Phase 107)

This is the **P0 gate** for tournament deployment (software conditions only):

```bash
curl -X POST "http://localhost:8080/agent/run-readiness-validation?api_key=<key>&n=100"
```

The validator runs 100 synthetic NOMINAL sessions through `SessionAdjudicator._rule_fallback()`.
A BLOCK on a nominal session = false positive. Zero false positives are required.

**`ready_for_live=True` requires all five conditions:**

| Condition | Check |
|-----------|-------|
| `n_tested >= 100` | 100 nominal sessions run |
| `false_positive_count == 0` | No nominal sessions blocked |
| `activation_committed == True` | Live mode persisted to store |
| `dry_run_active == False` | Agent not in dry run |
| `pmi >= 1` | Protocol Maturity Index ≥ 1 |

Expected output:
```json
{
  "n_tested": 100,
  "false_positive_count": 0,
  "false_positive_rate": 0.0,
  "activation_committed": true,
  "pmi": 1,
  "dry_run_active": false,
  "ready_for_live": true
}
```

Retrieve the latest report at any time:
```bash
curl "http://localhost:8080/agent/live-mode-readiness?api_key=<key>"
```

---

## Step 4 — Security Verification (Phase 105)

Check epistemic consensus configuration for Phase 98 W1 exposure:

```bash
curl "http://localhost:8080/agent/epistemic-config?api_key=<key>"
```

**Secure state:**
- `at_risk: false` — effective threshold ≥ 0.65
- `pmi_triggered: true` — PMI≥1 auto-raised threshold from 0.60 to 0.65
- `effective_threshold: 0.65` — ClassJ alone (0.40+0.20=0.60) cannot reach consensus

**If `at_risk: true`:** set `EPISTEMIC_RECOMMENDED_THRESHOLD=0.65` in `bridge/.env` and restart.

---

## Step 5 — Ongoing Monitoring

### VHP 90-Day TTL

VHP soulbound tokens expire 90 days after issuance. Monitor via Tool #73:

```python
# Via BridgeAgent
agent._execute_tool("get_live_mode_readiness", {})
```

Or via the API:
```bash
curl "http://localhost:8080/agent/live-mode-readiness?api_key=<key>"
```

### Lifecycle Checks

| Tool | Purpose |
|------|---------|
| Tool #71 `get_protocol_maturity` | PMI + activation state |
| Tool #73 `get_live_mode_readiness` | P0 tournament readiness gate |
| Tool #70 `run_activation_sequence` | Re-run activation if needed |
| Tool #66 `get_activation_status` | 5-step activation checklist |

---

## Known Blockers (Hardware)

The following conditions cannot be satisfied in software alone:

| Blocker | Requirement |
|---------|-------------|
| Inter-person separation ratio = 1.261 (Phase 143, classification 63.6%) | Classification ≥80% requires ≥10 touchpad_corners sessions/player |
| Tournament deployment | `ready_for_live=True` AND separation ratio > 1.0 |

Until separation ratio > 1.0 is empirically confirmed: **"production protocol architecture
with AGaaS-ready agent fleet, pre-calibration deployment"** — honest, strong, and accurate.
