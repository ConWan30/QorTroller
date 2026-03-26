# Phase 70 Security Audit — VAPIGovernanceTimelock + VAPIProtocolLens + Agent Wiring

**Audit date:** 2026-03-19
**Scope:** Phase 70 additions only
**Auditor:** Claude Code (automated review)
**Files reviewed:**
- `contracts/contracts/VAPIGovernanceTimelock.sol`
- `contracts/contracts/VAPIProtocolLens.sol`
- `bridge/vapi_bridge/main.py` (Phase 70 agent wiring block, lines 508–555)
- `bridge/vapi_bridge/bridge_agent.py` (tools #41–45, lines 816–947 and 1872–1947)
- `bridge/vapi_bridge/store.py` (Phase 69/70 store methods, referenced by tools)

---

## Summary

The Phase 70 additions are substantially sound. The `VAPIGovernanceTimelock` contract correctly implements the CEI pattern for reentrancy safety and enforces operator-only queue/execute with co-signer cancel. Two low-severity issues exist in the timelock: `setCoSigner` accepts `address(0)` without reverting (which would disable the co-signer safety net), and `transferOperator` bypasses the 48-hour queue on the timelock's own operator address. The `VAPIProtocolLens` contract is a clean zero-storage pure-view aggregator with one medium-severity concern: when the `RulingOracle` is unavailable its `isEligible` catch block defaults to `true` (eligible), which is a fail-open posture that may allow suspended devices through in oracle-failure scenarios. Agent wiring in `main.py` is correct — each of the three agents runs in an isolated asyncio task with `_task_done_handler` and a wrapping try/except that prevents an import-time crash from killing other agents. BridgeAgent tools #41–45 correctly validate oracle type (allowlist), use parameterized SQL queries, and handle compute exceptions gracefully. Tool #45's operator auth check is present but relies on the presence of a configured API key rather than verifying the caller identity at the tool level.

---

## Findings

### CRITICAL

None.

### HIGH

None.

### MEDIUM

**M-1: VAPIProtocolLens — `isEligible` fails open when RulingOracle is unreachable**

Location: `VAPIProtocolLens.sol` lines 180–182 and 238.

**STATUS: ✅ FIXED — Phase 71**

When the `RulingOracle` reverts or is unreachable, both `getDeviceState()` and `isFullyEligible()` set `isEligible = true` (eligible). This means a suspended device will pass the `isEligible` gate if the ruling oracle is down at query time. The other two gates (`isNominal` and `passportOnChain`) default to `false`, so the full `fullyEligible` composite gate still returns `false` for a brand-new device that has never been attested — but for a device that has previously passed humanity and passport gates (i.e., a suspended device with valid prior credentials), an oracle outage would temporarily restore eligibility.

This is a conscious design decision noted in the contract NatDoc ("default to eligible when oracle unavailable"), but it is a medium risk given that the ruling oracle tracks active suspensions for detected cheating. The fail-open rationale is to avoid false-positive denials during transient RPC issues, but in a tournament-gate context the safer default for a suspension oracle is `false` (ineligible), not `true`.

**Remediation applied:** `VAPIProtocolLens.sol` catch block for `isEligible` changed from `state.isEligible = true` → `state.isEligible = false`. New `bool oracleAvailable` field added to `DeviceProtocolState` struct — set to `true` on successful oracle call, `false` in the catch block. `isFullyEligible()` default `elig = true` changed to `elig = false`. Verified by test_14 (`MockRevertingRulingOracle` — `state.oracleAvailable == false` && `state.isEligible == false`). Hardhat 396→398 passing.

---

### LOW

**L-1: VAPIGovernanceTimelock — `setCoSigner` accepts `address(0)`, disabling the co-signer safety net**

Location: `VAPIGovernanceTimelock.sol` lines 201–203.

**STATUS: ✅ FIXED — Phase 71**

`setCoSigner` has no zero-address guard. An operator can call `setCoSigner(address(0))`, leaving `coSigner = address(0)`. After this call, `cancelTransition` still requires `msg.sender == operator || msg.sender == coSigner`, but `address(0)` can never be `msg.sender`, so the cancel-only guard is silently disabled. The timelock's security model relies on the co-signer being a live key that can respond within 48 hours; disabling it removes the only check on a compromised operator key during the window.

Compare: `transferOperator` does include a zero-address guard (line 212). The omission in `setCoSigner` appears inadvertent.

**Remediation applied:** `require(_coSigner != address(0), "VAPIGovernanceTimelock: zero co-signer")` added to `setCoSigner()` before the emit. Verified by test_13 (`setCoSigner(ethers.ZeroAddress)` → reverts). Hardhat 396→398 passing.

---

**L-2: VAPIGovernanceTimelock — `transferOperator` bypasses the 48-hour timelock on the timelock contract's own operator**

Location: `VAPIGovernanceTimelock.sol` lines 211–215.

`transferOperator` transfers the timelock contract's own operator role immediately (no queue). The NatDoc acknowledges this as a bootstrap mechanism and advises against it in production. Because a compromised operator key can use this to immediately transfer governance of the timelock itself — and thereby queue any arbitrary operator transition on the 6 Phase 69 contracts with 48-hour delay but under attacker control — this is a meaningful residual risk.

This is a documented design decision for a testnet-phase protocol. Acceptable for Phase 70 given the operational context, but should be addressed before mainnet by routing `transferOperator` through the same 48-hour queue.

---

**L-3: VAPIGovernanceTimelock — co-signer griefing: cancellation before execution**

Location: `VAPIGovernanceTimelock.sol` lines 181–188.

The co-signer can cancel any queued transition at any time before execution, including legitimate transitions. While the operator can re-queue, a hostile co-signer could repeatedly cancel every queued transition, permanently blocking operator changes. This is a known griefing vector in two-party timelock designs.

Acceptable for Phase 70 where the co-signer is a trusted VAPI operator key. On mainnet, consider requiring a time-lock on cancellation (e.g., cannot cancel within last N hours of the eta window) or adding a co-signer rotation cooldown.

---

**L-4: VAPIGovernanceTimelock — no target contract allowlist; any `address` can be targeted**

Location: `VAPIGovernanceTimelock.sol` line 121 (`queueTransition`).

`queueTransition` accepts any non-zero `target` address. There is no on-chain enforcement that `target` is one of the 6 documented Phase 69 contracts. An operator could queue a transition against an arbitrary contract that exposes `setOperator(address)` — including external contracts the operator does not own. In a testnet context with a single-operator model this is acceptable, but on mainnet a target allowlist should be enforced.

---

**L-5: BridgeAgent tool #45 — operator auth relies on API key presence, not caller identity**

Location: `bridge_agent.py` lines 1928–1929.

```python
if not getattr(self._cfg, "operator_api_key", ""):
    return {"error": "Operator auth required — OPERATOR_API_KEY not configured"}
```

This check verifies that an operator API key is _configured_, not that the caller presenting the request to the BridgeAgent has authenticated with that key. BridgeAgent tools are invoked via the Claude agent loop, not directly through the HTTP API layer (where the `x-api-key` header auth is enforced by `operator_api.py`). In the current architecture, any user able to trigger a Claude agent response can invoke tool #45. This is consistent with how other "operator only" actions work elsewhere in the bridge (the BridgeAgent itself is already guarded behind `operator_api_key` configuration), but the comment "OPERATOR ONLY" in the tool description may mislead reviewers.

This is informational given the current deployment model where BridgeAgent is only reachable via the authenticated operator API stream (`GET /operator/agent/stream`, 401-gated). No action required for Phase 70.

---

**L-6: VAPIProtocolLens — redundant oracle calls in `getDeviceState` increase gas and inconsistency window**

Location: `VAPIProtocolLens.sol` lines 159–188.

`getDeviceState()` calls `humanityOracle.isNominal()` and then separately calls `humanityOracle.getHumanityVerdict()` to extract `inferenceCode`. It also calls `rulingOracle.isSuspended()` and separately `rulingOracle.isEligible()` and `rulingOracle.getRulingState()`. Because all calls occur within a single `view` execution (no state writes), block-level consistency is guaranteed. However, these redundant calls add gas overhead in simulation contexts and make the code harder to audit. The `isNominal` return value from `getHumanityVerdict` is derivable from `inferenceCode`, but is fetched via a separate call with a separate try/catch, creating a scenario where one could succeed and the other fail, leaving `isNominal` and `inferenceCode` logically inconsistent (e.g., `isNominal=true` with `inferenceCode=0` because the second call caught an error). This is unlikely in practice but possible.

---

## Detailed Analysis

### VAPIGovernanceTimelock.sol

**Reentrancy on `executeTransition` (CEI pattern):**
PASS. Line 161 sets `t.executed = true` before the external `.call()` on line 164. The NatDoc explicitly documents this: "CEI: set state before external call." Reentrancy into `executeTransition` with the same `queueId` would be blocked by the `!t.executed` check. No reentrancy vulnerability found.

**`eta` overflow (`block.timestamp + TIMELOCK_DELAY`):**
PASS. The contract uses `pragma solidity ^0.8.20`. Solidity 0.8+ has built-in checked arithmetic by default; the addition will revert rather than wrap. With `TIMELOCK_DELAY = 48 hours = 172800 seconds` and `block.timestamp` well within `uint256` range for any foreseeable future, no overflow risk exists.

**Griefing via co-signer front-running `executeTransition`:**
LOW (L-3 above). The co-signer can cancel any pending transition before execution. This is a documented design trade-off, not a bug. The window for griefing is bounded by the 48-hour delay. For a hostile co-signer acting in bad faith, the operator retains the ability to immediately replace the co-signer via `setCoSigner` (see L-1 note about zero-address risk), then re-queue.

**Access control — `queueTransition`/`executeTransition` strictly `onlyOperator`:**
PASS. Both are protected by the `onlyOperator` modifier (line 86–89) which checks `msg.sender == operator`. `cancelTransition` uses `onlyOperatorOrCoSigner` (line 91–97) which allows either operator or co-signer, consistent with the design specification.

**No bypass — `setOperator` on target contracts called directly:**
INFORMATIONAL. The timelock only controls transitions routed through it. Target contracts (Phase 69) can still be called directly if the target contracts' `setOperator()` function does not require the caller to be this timelock. The timelock is a safe wrapper around whatever access control the target contracts already have, not a replacement. If Phase 69 contracts themselves have an `onlyOperator` guard on `setOperator()`, and the current operator is the bridge wallet (not the timelock address), then the timelock cannot be used until the bridge wallet delegates operator to the timelock. Whether this handoff has been done is a deployment-time concern, not a code defect in this file.

**PHGCredential exclusion — enforced vs. documented:**
INFORMATIONAL. The exclusion is documented in the NatDoc (line 16) and the "Supported target contracts" list omits PHGCredential. There is no on-chain enforcement mechanism — the timelock has no allowlist. If the operator queued a transition targeting PHGCredential's address, the timelock would call `setOperator(address)` on it. Whether PHGCredential actually exposes such a function (and the documentation says it does not — "immutable bridge address") means the call would simply revert with `ok=false` and the entire `executeTransition` would revert on line 167 (`require(ok, ...)`). In practice, the exclusion is correctly handled by PHGCredential's own immutability, not by the timelock. This is acceptable and consistent with the design.

---

### VAPIProtocolLens.sol

**Pure view guarantee — no state writes possible:**
PASS. The contract has zero storage state variables (all four addresses are `immutable`, set once in the constructor). The `getDeviceState()` and `isFullyEligible()` functions are marked `external view`. No state-modifying operations exist anywhere in the contract. The compiler would reject any `view` function that attempted to write state.

**Oracle address immutability:**
PASS. All four oracle addresses are declared as `public immutable` (lines 112–115):
```
IHumanityOracle       public immutable humanityOracle;
IRulingOracle         public immutable rulingOracle;
IPassportOracle       public immutable passportOracle;
IVAPIRewardDistributor public immutable rewardDistributor;
```
`immutable` in Solidity 0.8+ means the values are embedded in the bytecode at construction time and cannot be changed afterward. No upgrade path for oracle addresses exists. This is correct and intentional.

**Failed oracle call handling:**
MEDIUM (M-1 above). All oracle sub-calls are wrapped in `try/catch` blocks. The failure modes are:
- `humanityOracle`: defaults to `isNominal=false`, `humanityPct=0`, `inferenceCode=0` — safe, fail-closed.
- `rulingOracle.isSuspended`: defaults to `suspended=false` — ambiguous but recovers conservatively.
- `rulingOracle.isEligible`: defaults to `isEligible=true` — fail-open for suspension checks (see M-1).
- `passportOracle`: defaults to `passportOnChain=false`, `passportIssued=false` — safe, fail-closed.
- `rewardDistributor`: defaults to `multiplierX100=100` (1.0×) — safe neutral default.

The composite `fullyEligible` gate (`isNominal && isEligible && passportOnChain`) is protected by the `isNominal=false` and `passportOnChain=false` defaults, so a device with no prior attestation will still fail the full gate even if the ruling oracle is down. The risk is specific to devices that already have valid humanity attestations and passports on-chain but are under active suspension.

**No biometric raw data exposure:**
PASS. `DeviceProtocolState` contains only derived scalars: `humanityPct` (uint16 percentage), `inferenceCode` (uint8 classification code), `flagStreak` (uint32 count), and boolean gate fields. No raw biometric feature vectors, no raw L4 Mahalanobis distances beyond the inferred outcome, no IBI values. The `l4DistanceX1000` field is present in the `IHumanityOracle.getHumanityVerdict` interface return, but it is not extracted or populated in `DeviceProtocolState` — the corresponding tuple return value is discarded (line 170: `uint8 ic, uint16, uint32, uint32, uint32, uint64`). Correct.

---

### main.py Agent Wiring

**DataCuratorAgent exception isolation:**
PASS. The DataCuratorAgent is wrapped in its own `try/except Exception` block (lines 513–522). If the import fails or the constructor raises, the exception is caught and logged at WARNING level, and execution continues to the SessionAdjudicator block. The SessionAdjudicator is likewise in its own `try/except`. A runtime crash inside the running `DataCuratorAgent.run_poll_loop()` coroutine will only cancel that task; `_task_done_handler` will log it at CRITICAL, but the event loop continues serving all other tasks.

**`_task_done_handler` CRITICAL callback:**
PASS. All three Phase 70 tasks attach `_task_done_handler` immediately after `create_task()`:
- `DataCuratorAgent`: line 518 `_t.add_done_callback(_task_done_handler)`
- `SessionAdjudicator`: line 531 `_t.add_done_callback(_task_done_handler)`
- `RulingEnforcementAgent`: line 549 `_t.add_done_callback(_task_done_handler)`

The handler (lines 75–85) logs CRITICAL with full traceback when a task exits with an unhandled exception. This is consistent with the Phase 54 pattern applied to all other managed tasks.

**Double-start guard:**
INFORMATIONAL. There is no explicit double-start guard (e.g., a flag checking whether an agent instance is already running). However, the current code path only enters the agent wiring block once during `Bridge.run()`, and `Bridge.run()` is called once per process. `asyncio.create_task()` is called once per agent. There is no restart-on-failure loop for these agents — a crash causes `_task_done_handler` to log CRITICAL and the task slot in `self._tasks` is filled by the cancelled task object. Re-invoking `run()` on an already-started `Bridge` is not guarded but is also not a supported operation. Acceptable for Phase 70.

**Task name assignment:**
PASS. All three tasks call `_t.set_name(...)` immediately after creation (lines 517, 530, 548), which makes CRITICAL log messages from `_task_done_handler` identifiable by agent name.

---

### BridgeAgent Tools #41–45

**Tool #45 (`publish_sovereignty_pledge`) — operator auth before queuing:**
LOW (L-5 above). The check on line 1928–1929 validates that `OPERATOR_API_KEY` is configured (i.e., operator mode is active), not that the specific request is authenticated. In the current architecture this is adequate because the BridgeAgent is only reachable via the authenticated `/operator/agent/stream` endpoint. No action required for Phase 70.

**Tool #43 (`get_oracle_state`) — `oracle_type` injection:**
PASS. Lines 1900–1906 apply an explicit allowlist check:
```python
oracle_type = inputs.get("oracle_type", "").upper().strip()
_VALID_ORACLES = {"HUMANITY", "RULING", "PASSPORT"}
if oracle_type not in _VALID_ORACLES:
    return {"error": ...}
```
The validated `oracle_type` string is then passed to `self._store.get_oracle_publications(oracle_type=oracle_type, ...)`, which uses it as a parameterized SQL bind variable (store.py line 2627). Double-protected: allowlist at tool boundary, parameterized query in store. No injection risk.

**Tool #41 (`get_data_lineage`) — device_id SQL injection:**
PASS. The device_id is passed through `device_id.strip()` and then to `self._store.get_data_lineage(device_id.strip(), ...)`. In `store.py` lines 2594–2598, the query uses parameterized binding (`WHERE device_id=?`, `(device_id, limit)`). No string interpolation into SQL is performed. No injection risk.

**Tool #44 (`compute_reward_score`) — exception handling without raising:**
PASS. Lines 1918–1923 wrap the call in a `try/except Exception as exc` block and return `{"error": str(exc), "device_id": device_id}` rather than re-raising. This follows the same pattern as the outer catch on line 1951–1953 (`except Exception as exc: ... return {"error": str(exc), "tool": name}`). The tool cannot raise — it always returns a dict.

**Tool #41 limit input validation:**
PASS. Line 1878 clamps the `limit` parameter: `limit = min(int(inputs.get("limit", 50)), 200)`. If the agent provides a very large limit, it is silently capped at 200. If `inputs.get("limit", 50)` returns a non-integer string, the `int()` conversion would raise `ValueError`, which is caught by the outer exception handler (line 1951) and returned as `{"error": ...}`.

**Tool #44 ephemeral `DataCuratorAgent` instantiation:**
INFORMATIONAL. `compute_reward_score` instantiates a new `DataCuratorAgent(self._cfg, self._store, chain=None)` per call (line 1920). This is a sync computation that reads from the store — the `chain=None` argument means no on-chain calls are made. The instantiation is lightweight. No resource leak was identified, but in high-frequency agent loop scenarios this could produce many short-lived objects. Acceptable for Phase 70.

---

## Known Limitations (Not Bugs)

1. **PHGCredential excluded from timelock scope** — by contract design, PHGCredential's bridge address is immutable. The timelock correctly excludes it. This is documented in the contract NatDoc and MEMORY.md.

2. **`transferOperator` immediate effect** — documented as a bootstrap mechanism. The NatDoc warns against production use. This is a known trade-off, not a defect.

3. **`isEligible` defaults to `true` on oracle failure** — see M-1. This is a documented design decision in the contract NatDoc. The composite `fullyEligible` gate still protects new/unattested devices. The risk is constrained to previously-attested-but-suspended devices during oracle downtime.

4. **Inter-person separation ratio 0.362** — documented in §8.6 of the whitepaper and in MEMORY.md as a hardware recapture blocker. Not a Phase 70 issue.

5. **SessionAdjudicator dry_run=True default** — deliberate; live adjudication requires AGENT_DRY_RUN=false after ≥100 validated sessions. Not a Phase 70 defect.

6. **No target contract allowlist in VAPIGovernanceTimelock** — acceptable for testnet single-operator model. PHGCredential's own immutability is the enforcement mechanism for its exclusion. Revisit before mainnet.

7. **Agent wiring has no double-start guard** — `Bridge.run()` is not designed to be called multiple times; this is acceptable in the current operational model.

---

## Conclusion

**Phase 70 security gate: PASS with one medium finding requiring acknowledgment.**

**CRITICAL/HIGH:** None. The Phase 70 additions do not introduce any critical or high severity vulnerabilities.

**Medium (M-1):** The `isEligible=true` fail-open default in `VAPIProtocolLens` when the `RulingOracle` is unreachable could temporarily grant tournament eligibility to an actively suspended device during oracle downtime. This is a documented design decision and is bounded by the requirement that `isNominal` and `passportOnChain` must also be true. For the current testnet deployment, this is acceptable. A remediation plan (change catch default to `false`, add `oracleAvailable` flag) is recommended for mainnet.

**Low:** Four low-severity items (L-1 through L-4) in the Solidity contracts relate to missing zero-address guard on `setCoSigner`, the immediate `transferOperator` escape hatch, co-signer griefing, and missing target allowlist. Two informational items (L-5, L-6) relate to agent auth model and redundant oracle calls. None block Phase 70 completion.

The agent wiring in `main.py` is correctly isolated, all tasks carry `_task_done_handler`, and the BridgeAgent tools #41–45 use parameterized SQL and validated allowlists throughout. Phase 70 is cleared for deployment pending the Phase 69 prerequisite contracts going live.
