# LLM Router Modes — Runbook

Three operational modes for the three-tier LLM router.
Each mode is a single config flip. No code changes needed.

---

## Mode 1: Offline (LOCAL only)

**Use case:** No cloud keys configured. Running entirely on local hardware.

```bash
# ── Config (set these in .env or session env) ──
set LOCAL_LLM_ENABLED=true
set LOCAL_LLM_MODEL=deepseek-r1:14b
set LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1

# ── Result ──
# Chain: [local]
# All traffic stays on localhost. No cloud API calls.
# Router returns "no_backends_available" if Ollama isn't running.
```

**Pre-flight check:**

```bash
# Verify Ollama is running
curl http://127.0.0.1:11434/api/tags

# Pull the model if needed
ollama pull deepseek-r1:14b

# Smoke test the router
cd bridge
python -c "
import asyncio
from vapi_bridge.llm_routing import LLMRouter
r = LLMRouter()
print('Chain:', r.chain)
print('Backends:', {b: r._backends[b].configured() for b in r._backends})
result = asyncio.run(r.route(
    task_class='assistant',
    messages=[{'role': 'user', 'content': 'say hello in one word'}],
))
print(f'Backend: {result.backend}')
print(f'Response: {result.content}')
"
```

**What to expect:**
- First response may be slow (model loading into GPU)
- Subsequent responses should be sub-second for small prompts
- `result.live = True`, `result.backend = "local"`, `result.fallback_used = False`

---

## Mode 2: Sovereign (no cloud, enforced)

**Use case:** Guarantee no data leaves the machine. Cloud keys MAY be set — the router ignores them structurally.

```bash
# ── Config ──
set LOCAL_LLM_ENABLED=true
set LOCAL_LLM_MODEL=deepseek-r1:14b
set LLM_REFUSE_CLOUD=true

# Cloud keys are optional — the router blocks them at chain build time
# set QUICKSILVER_API_KEY=sk-...     ← ignored in sovereign mode
# set NIM_API_KEY=nvapi-...           ← ignored in sovereign mode

# ── Result ──
# Chain: [local]
# Cloud backends stripped at chain build, never at request time.
# Even if LOCAL is down, router returns "no_local_backend" — no cloud.
```

**Verification:**

```bash
cd bridge
python -c "
from vapi_bridge.llm_routing.policy import resolve_policy_from_env
p = resolve_policy_from_env()
assert p.refuse_cloud == True
# Chain building strips cloud structurally
chain = ['local']
assert 'quicksilver' not in chain
assert 'nim' not in chain
print('Sovereign mode: cloud excluded at chain build')
"
```

**Key behavioral difference from offline mode:**
- Offline: cloud keys not set, cloud backends simply aren't configured
- Sovereign: cloud keys may be set, but the router **refuses to use them** even as a last resort

---

## Mode 3: NIM-on (full chain)

**Use case:** All three backends active. QuickSilver for assistant traffic, NIM for guardian advisory, LOCAL as the safety net.

```bash
# ── Config ──
set QUICKSILVER_API_KEY=sk-...
set NIM_API_KEY=nvapi-...
set AGENTIC_REASONING_ENABLED=true
set LOCAL_LLM_ENABLED=true
set LOCAL_LLM_MODEL=deepseek-r1:14b

# ── Result ──
# Assistant chain:  [quicksilver, local]       (NIM excluded)
# Guardian chain:   [nim, local, quicksilver]  (NIM primary)
# Default chain:    [quicksilver, local, nim]
```

**Verification:**

```bash
cd bridge
python -c "
import asyncio
from vapi_bridge.llm_routing import LLMRouter
r = LLMRouter()
print('Default chain:', r.chain)
print('Backends:', {b: r._backends[b].configured() for b in r._backends})

# Test assistant task (should prefer quicksilver)
result = asyncio.run(r.route(
    task_class='assistant',
    messages=[{'role': 'user', 'content': 'hello'}],
))
print(f'Assistant served by: {result.backend}')
print(f'Fallback used: {result.fallback_used}')
"
```

---

## Troubleshooting

### "no_backends_available"

**Cause:** No backends are configured. All env vars are either unset or set to disabled.

**Fix:** Set at least one backend:
- `LOCAL_LLM_ENABLED=true` (requires Ollama running)
- `QUICKSILVER_API_KEY=sk-...`
- `NIM_API_KEY=nvapi-...` + `AGENTIC_REASONING_ENABLED=true`

### "no_llm_on_level0"

**Cause:** A Level 0 protocol task (PoAC, invariant gate, chain write, etc.) was routed through the LLM.

**This is correct behavior.** The router protects deterministic protocol paths from LLM contamination. Route the task through the deterministic protocol handler instead.

### "no_local_backend"

**Cause:** `LLM_REFUSE_CLOUD=true` is set, but LOCAL is not configured or not running.

**Fix:** Enable LOCAL (`LOCAL_LLM_ENABLED=true`) and ensure Ollama is running with the configured model pulled.

### "all_backends_exhausted"

**Cause:** All configured backends were tried and all failed.

**Check:**
1. Is Ollama running? → `curl http://127.0.0.1:11434/api/tags`
2. Is the model pulled? → `ollama list`
3. Are API keys correct? → Check env vars
4. Were there network errors? → Try the API endpoint directly

### "timeout_or_network"

**Cause:** A backend timed out or returned a connection error.

**Behavior:**
- If `LLM_FAILOVER_ON_TIMEOUT=true` (default): Router tries the next backend
- If `LLM_FAILOVER_ON_TIMEOUT=false`: Router returns the error immediately

### Backend is in cooldown

**Cause:** The backend has failed `LLM_ROUTER_MAX_FAILURES` (default: 3) consecutive times.

**Behavior:** The backend is automatically retried after `LLM_ROUTER_COOLDOWN_SECONDS` (default: 300 seconds / 5 minutes). A single success resets the failure counter.

---

## Configuration reference

```bash
# ── Chain ───────────────────────────────────────
LLM_PRIMARY="quicksilver"        # first backend to try
LLM_SECONDARY="local"            # fallback if primary is down
LLM_TERTIARY=""                  # empty = no tertiary

LLM_ROUTE_MODE="failover"        # failover|primary_only|local|cloud|task_split|pin:<id>

# ── Policy rails ────────────────────────────────
LLM_REFUSE_CLOUD="false"         # true = local only, no cloud
LLM_ALLOW_NIM_FOR_ASSISTANT="false"  # true = NIM can serve assistant tasks
LLM_FAILOVER_ON_TIMEOUT="true"   # false = timeout returns error instead of failover
LLM_HEALTH_CACHE_S="30"          # health cache TTL in seconds

# ── QuickSilver ─────────────────────────────────
QUICKSILVER_API_KEY=""           # set to enable
QUICKSILVER_MODEL="deepseek-v4-flash"
QUICKSILVER_API_URL="https://api.quicksilverpro.io/v1/chat/completions"

# ── NIM ─────────────────────────────────────────
NIM_API_KEY=""                   # your NGC CLI key
NIM_MODEL="mistralai/mistral-medium-3.5-128b"
NIM_BASE_URL="https://api.nvidia.com/v1"
AGENTIC_REASONING_ENABLED="false" # set "true" to enable NIM

# ── LOCAL ───────────────────────────────────────
LOCAL_LLM_ENABLED="false"        # set "true" to enable
LOCAL_LLM_BASE_URL="http://127.0.0.1:11434/v1"
LOCAL_LLM_MODEL="deepseek-r1:14b"
LOCAL_LLM_API_KEY=""             # optional bearer for local gateway
LOCAL_LLM_TIMEOUT_SECONDS="120"
LOCAL_LLM_MAX_TOKENS="4096"

# ── Tuning ──────────────────────────────────────
LLM_ROUTER_TIMEOUT_SECONDS="30"
LLM_ROUTER_MAX_FAILURES="3"
LLM_ROUTER_COOLDOWN_SECONDS="300"
LLM_ROUTER_HEALTH_INTERVAL="60"

# ── Cost guards (NIM) ───────────────────────────
NIM_COST_WARN_USD="50"
NIM_COST_CRITICAL_USD="100"

# ── Environment ─────────────────────────────────
QORTROLLER_ENV="dev"
```