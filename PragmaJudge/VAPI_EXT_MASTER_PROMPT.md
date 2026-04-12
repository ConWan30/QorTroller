# VAPI SUB-PROTOCOL EXTENSIBILITY LAYER — CLAUDE CODE MASTER PROMPT
**Phase:** VAPI-EXT (between Phase 204 and Phase 205)
**Repository:** `C:\Users\Contr\vapi-pebble-prototype`
**Chain:** IoTeX Testnet 4690
**VAPI State at prompt creation:** Phase 204 COMPLETE
**Bridge tests at baseline:** 2230 passing
**Coherence rules at baseline:** 18 total (CONTRADICTION=8, ORPHAN=6, INVERSION=4)
**Agents at baseline:** 36
**Tools at baseline:** 149
**Contracts at baseline:** 43 ALL LIVE

---

## MISSION STATEMENT

You are building the sub-protocol extensibility layer for VAPI. This phase transforms
VAPI from a self-contained protocol into a platform capable of hosting isolated
sub-protocols that share its infrastructure without modifying its core. The immediate
future sub-protocols are:

1. **VAPI Mobile (TouchAC)** — already designed in the mobile expansion framework,
   registers as the first sub-protocol consumer of this infrastructure.
2. **PragmaJudge** — a cryptographic AI accountability layer that integrates after
   the mobile expansion is complete, registering as the second sub-protocol.

This phase builds NO PragmaJudge code and NO mobile code. It builds the connective
tissue that both will snap into cleanly. Every file created in this phase is additive.
The only exceptions are five minimal, backward-compatible modifications to existing
files, each called out explicitly below with the label **[PERMITTED MODIFICATION]**.

VAPI's existing 2230 bridge tests must remain green after every single step of this
phase. Run `pytest bridge/` after each step before proceeding to the next.

---

## ABSOLUTE CONSTRAINTS — READ BEFORE WRITING ANY CODE

**CONSTRAINT 1: The following files may NOT be modified** except where explicitly
labeled [PERMITTED MODIFICATION] in the BUILD SEQUENCE below:

```
bridge/vapi_bridge/store.py
bridge/vapi_bridge/chain.py
bridge/vapi_bridge/bridge_agent.py
bridge/vapi_bridge/session_adjudicator.py
bridge/vapi_bridge/config.py
Any existing agent file in bridge/vapi_bridge/agents/
Any existing Solidity contract in contracts/
```

The sole exception to the agent files rule is `fleet_signal_coherence_agent.py`,
which receives one [PERMITTED MODIFICATION] in Step 4 — a single-line change to
its rule initialization, nothing else.

**CONSTRAINT 2: All frozen VAPI invariants remain immutable.** No file created or
modified in this phase may redefine, shadow, or override:

```python
epistemic_consensus_threshold = 0.65   # Phase 147 hardened
BLOCK_QUORUM                  = 0.67   # Phase 109A floor
MINT_QUORUM                   = 0.80   # Phase 110 floor
# PoAC wire format: 228 bytes, SHA-256(raw[:164]), body only
# device_id: keccak256(pubkey)
# Hard cheat codes: {0x28, 0x29, 0x2A}
L4_anomaly_threshold          = 7.009
L4_continuity_threshold       = 5.367
```

**CONSTRAINT 3: Every new Python module includes a module-level docstring** explaining
its role in the sub-protocol architecture. Every new Solidity function includes a
NatSpec comment. This phase creates infrastructure that future Claude Code sessions
must understand without access to this conversation as context. Write documentation
as if the next reader knows VAPI but has never seen this prompt.

**CONSTRAINT 4: Every new file ends with this phase marker comment:**

```python
# VAPI-EXT Phase — Sub-Protocol Extensibility Layer
# Do not modify without reading VAPI_SUBPROTOCOL_ARCHITECTURE.md
```

**CONSTRAINT 5: The guard mechanism from Phase 204 is a first-class concern.**
Phase 204 introduced a `guard` lambda field on coherence rules — a `Callable[[cfg], bool]`
that gates whether a rule fires based on runtime config state. This mechanism exists
because some contradiction rules (specifically IOSWARM_ACTIVE_NO_ADJUDICATIONS) should
only fire when certain config flags are active. Any data structure you define for
coherence rules MUST include this field. Silently dropping it would discard Phase 204's
most architecturally significant innovation.

---

## BUILD SEQUENCE — IMPLEMENT IN ORDER, RUN TESTS AFTER EACH STEP

---

### STEP 1 — Sub-Protocol Registry

**New file:** `bridge/vapi_bridge/sub_protocol_registry.py`

Build a `SubProtocolRegistry` singleton class. This is the central registration point
for every sub-protocol that attaches to VAPI. It is the first thing any sub-protocol
calls when it initializes, making its presence in the system explicit, auditable, and
detectable by monitoring agents.

The registry maintains a dictionary of registered sub-protocols keyed by name. Each
entry records the sub-protocol's declared event namespace prefix, agent number range,
table prefix, contract source type, version, and activation status.

Define a `SubProtocolConfig` dataclass with these fields:

```python
@dataclass
class SubProtocolConfig:
    name: str                      # e.g., "VAPI_CORE", "VAPI_MOBILE", "PRAGMA_JUDGE"
    event_namespace: str           # e.g., "", "MOBILE_", "PRAGMA_"
    agent_range: tuple[int, int]   # inclusive both ends, e.g., (1, 36) for VAPI core
    table_prefix: str              # e.g., "", "mobile_", "pragma_"
    contract_source_type: str      # written to AdjudicationRegistry on every anchor
    version: str                   # semver string e.g., "3.0.0-phase204"
    dry_run: bool = True           # mirrors VAPI's dry_run default pattern
```

The `SubProtocolRegistry` class must implement:

`register(config: SubProtocolConfig) → None` — validates that the event namespace
prefix does not collide with any already-registered prefix, and that the agent number
range does not overlap with any already-registered range (including VAPI core's 1–36).
Raises `SubProtocolConflictError` (a new custom exception) on any collision. On success,
writes a row to the `sub_protocol_registry` SQLite table (created in Step 3) and logs
the registration. The call is idempotent for the same name and identical config —
re-registering an identical config is a no-op rather than an error, which supports
clean restart behavior.

`get_registered() → dict[str, SubProtocolConfig]` — returns all registered entries.

`is_registered(name: str) → bool` — simple membership check.

`deactivate(name: str) → None` — marks a sub-protocol inactive without removing its
data. Idempotent. Used for graceful shutdown. Sets `deactivated_at` in the table.

At module import time, pre-register VAPI core so the registry is never empty when
sub-protocols check it:

```python
# This registration happens automatically at module import — no external call needed.
VAPI_CORE_CONFIG = SubProtocolConfig(
    name="VAPI_CORE",
    event_namespace="",            # VAPI owns the unprefixed namespace
    agent_range=(1, 36),
    table_prefix="",
    contract_source_type="VAPI",
    version="3.0.0-phase204",
    dry_run=False,                 # VAPI core is live — not dry run
)
```

**Test file:** `bridge/tests/test_sub_protocol_registry.py` — write 20+ tests covering:
registration success, namespace collision detection, agent range overlap detection,
idempotent re-registration, deactivation, `get_registered()` completeness, and
`is_registered()` accuracy for both present and absent names.

Run `pytest bridge/` after this step. All 2230+ tests must pass before proceeding.

---

### STEP 2 — Federation Bus Namespace Isolation

**[PERMITTED MODIFICATION]:** `bridge/vapi_bridge/federation_bus.py`

The federation bus currently has no namespace validation. Add the following capabilities
with zero change to existing behavior. The modification must be designed so that if no
sub-protocol beyond VAPI core has registered a namespace, the bus behaves identically
to its current state — existing tests pass without any change to test code.

Add `register_namespace(prefix: str, owner: str) → None` to the bus. This stores a
`prefix → owner` mapping in an internal dictionary. VAPI core automatically registers
`prefix=""` (empty string) at module initialization. Raises `NamespaceConflictError`
if a non-empty prefix is already registered by a different owner. Empty string is
special — only VAPI core may own it, and attempting to register it from outside raises
immediately.

Modify `publish(event_name: str, payload: dict) → None` — before the existing publish
logic, insert a validation step:

```
For each registered non-empty prefix in the namespace registry:
    If event_name.startswith(prefix):
        Verify the calling context owns that prefix.
        If not: raise NamespaceViolationError with full context.

If no non-empty prefix matches the event name:
    The event is in VAPI core namespace — allow unconditionally.

If only the empty-string namespace is registered (no sub-protocols active):
    Skip all validation — pure pass-through, identical to current behavior.
```

The key design principle here is that the validation layer is invisible until needed.
Current VAPI events have names like `recalibration_needed`, `enrollment_complete`,
`separation_ratio_breakthrough` — none of these start with any registered sub-protocol
prefix, so they pass through without any computation overhead until a sub-protocol
actually registers.

**Test file:** `bridge/tests/test_federation_bus_namespacing.py` — write 15+ tests
covering: single-namespace state passes all existing event names, second namespace
registration, violation detection when wrong owner publishes a prefixed event, namespace
deregistration, and verification that all existing VAPI event publications remain
unaffected.

Run `pytest bridge/` after this step. All 2230+ tests must pass before proceeding.

---

### STEP 3 — Versioned Migration Framework

**New files:**
```
bridge/vapi_bridge/migrations/__init__.py
bridge/vapi_bridge/migrations/runner.py
bridge/vapi_bridge/migrations/vapi_ext_001_sub_protocol_registry.sql
bridge/vapi_bridge/migrations/vapi_ext_002_agent_manifest.sql
```

**[PERMITTED MODIFICATION]:** `bridge/vapi_bridge/store.py` — one line addition only.

The migration runner is a lightweight versioned schema manager. It must:

On first run, create a `schema_migrations` table if it does not exist:

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    filename     TEXT    UNIQUE NOT NULL,
    applied_hash TEXT    NOT NULL,  -- SHA-256 of the SQL file's content at time of application
    applied_at   INTEGER NOT NULL,  -- nanosecond timestamp
    phase_tag    TEXT                -- e.g., "VAPI-EXT", "PHASE_206", "PRAGMA_201"
);
```

Then scan the `migrations/` directory for `.sql` files in strict alphabetical order.
For each file not yet in `schema_migrations`, execute it against the database and
record it with its content hash. If a file IS already in `schema_migrations` but its
current SHA-256 differs from the stored `applied_hash`, raise `MigrationTamperError`
immediately — a migration file was modified after application, which is a data integrity
violation that must never pass silently.

The runner must be called from `store.py` startup. The [PERMITTED MODIFICATION] to
`store.py` is exactly one addition — call the runner after the database connection
is established:

```python
# Add this line in store.py's __init__ or startup method, after db connection opens:
from .migrations.runner import MigrationRunner
MigrationRunner(self.db_conn).apply_pending()
```

All existing table creation logic in `store.py` remains completely unchanged. The
migration runner supplements it — future sub-protocol tables come via migration files,
not via changes to `store.py`.

**`vapi_ext_001_sub_protocol_registry.sql`** creates the persistence table for the
SubProtocolRegistry built in Step 1:

```sql
CREATE TABLE IF NOT EXISTS sub_protocol_registry (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT    UNIQUE NOT NULL,
    event_namespace      TEXT    NOT NULL,
    agent_range_start    INTEGER NOT NULL,
    agent_range_end      INTEGER NOT NULL,
    table_prefix         TEXT    NOT NULL,
    contract_source_type TEXT    NOT NULL,
    version              TEXT    NOT NULL,
    dry_run              INTEGER NOT NULL DEFAULT 1,
    active               INTEGER NOT NULL DEFAULT 1,
    registered_at        INTEGER NOT NULL,
    deactivated_at       INTEGER
);
```

**`vapi_ext_002_agent_manifest.sql`** creates the canonical agent registry and
immediately populates it with all 36 existing VAPI agents. Read the existing agent
files and `VAPI_PROTOCOL_ASSESSMENT.md` to get accurate class names, module paths,
and phases introduced for each agent. Every future agent added to VAPI or any
sub-protocol inserts a row here — this becomes the single source of truth for what
is running in the fleet:

```sql
CREATE TABLE IF NOT EXISTS agent_manifest (
    agent_number      INTEGER PRIMARY KEY,
    class_name        TEXT    NOT NULL,
    module_path       TEXT    NOT NULL,
    phase_introduced  INTEGER NOT NULL,
    sub_protocol      TEXT    NOT NULL DEFAULT 'VAPI_CORE',
    description       TEXT,
    active            INTEGER NOT NULL DEFAULT 1
);

-- Populate all 36 existing VAPI agents below.
-- Read each agent file to confirm accurate class_name and module_path.
-- Example format (complete for all 36):
INSERT INTO agent_manifest VALUES (1,  'SessionAdjudicator',      'bridge.vapi_bridge.agents.session_adjudicator',       65,  'VAPI_CORE', 'LLM ruling per session', 1);
INSERT INTO agent_manifest VALUES (2,  'RulingEnforcementAgent',  'bridge.vapi_bridge.agents.ruling_enforcement_agent',  66,  'VAPI_CORE', 'Monitors ruling streaks', 1);
-- ... continue for agents 3–36 using accurate data from the codebase
```

**Test file:** `bridge/tests/test_migration_runner.py` — write 20+ tests covering:
first-run table creation, pending migration detection, correct alphabetical ordering,
idempotency (running twice applies nothing the second time), tamper detection when a
migration file's content is modified after application, and the `schema_migrations`
table being populated correctly after each run.

Run `pytest bridge/` after this step. All 2230+ tests must pass before proceeding.

---

### STEP 4 — Coherence Rule Plugin Architecture

**New files:**
```
bridge/vapi_bridge/coherence_rules/__init__.py
bridge/vapi_bridge/coherence_rules/loader.py
bridge/vapi_bridge/coherence_rules/vapi_core_rules.py
```

**[PERMITTED MODIFICATION]:** `bridge/vapi_bridge/agents/fleet_signal_coherence_agent.py`
— one line change to rule initialization only, described precisely below.

The `FleetSignalCoherenceAgent` currently has **18 hardcoded rules** across three
categories: CONTRADICTION (8 rules), ORPHAN (6 rules), INVERSION (4 rules). Phase 204
added the 8th CONTRADICTION rule (IOSWARM_ACTIVE_NO_ADJUDICATIONS) and introduced a
`guard` mechanism — a lambda that gates rule evaluation on runtime config state. This
guard mechanism is architecturally significant and must be preserved as a first-class
field in the rule data structure.

Define a `CoherenceRule` dataclass in `coherence_rules/__init__.py`:

```python
from dataclasses import dataclass, field
from typing import Callable, Optional

@dataclass
class CoherenceRule:
    rule_id: str              # e.g., "CONTRADICTION_8", "ORPHAN_3", "INVERSION_2"
    category: str             # "CONTRADICTION" | "ORPHAN" | "INVERSION"
    severity: str             # "INFO" | "WARNING" | "CRITICAL" | "HIGH"
    owner: str                # "VAPI_CORE" or the sub-protocol name that owns this rule
    description: str          # human-readable description for WIF corpus and dashboards
    evaluate: Callable        # the actual detection function — signature matches existing rules
    guard: Optional[Callable] = None
    # guard(cfg) -> bool: if provided, the rule only evaluates when guard returns True.
    # This is Phase 204's config-dependent gating mechanism. Example:
    # guard=lambda cfg: cfg.get("ioswarm_enabled") and cfg.get("ioswarm_adjudication_enabled")
    # If guard is None, the rule always evaluates — backward compatible with all pre-Phase-204 rules.
```

Extract all 18 existing rules from `fleet_signal_coherence_agent.py` into
`vapi_core_rules.py` without changing their logic. Each rule becomes a `CoherenceRule`
instance. Rules that currently use the `guard` mechanism (specifically
IOSWARM_ACTIVE_NO_ADJUDICATIONS) must have their guard lambda preserved in the `guard`
field. Expose the complete list as:

```python
# vapi_core_rules.py
RULES: list[CoherenceRule] = [
    # All 18 rules, in their original order, with guard fields where applicable
]
```

Build `coherence_rules/loader.py` with a `CoherenceRuleLoader` class that exposes:

```python
@staticmethod
def load_all() -> list[CoherenceRule]:
    # Scans bridge/vapi_bridge/coherence_rules/ for all Python files
    # that define a module-level RULES list of CoherenceRule instances.
    # Imports and concatenates all found lists.
    # Validates no rule_id collision across files — raises RuleConflictError on collision.
    # Returns the combined list in deterministic order (core rules first, then sub-protocol
    # rules in alphabetical order by filename).
```

The loader's rule evaluation logic must respect the `guard` field:

```python
def evaluate_rule(rule: CoherenceRule, context: dict, cfg: dict) -> Optional[CoherenceEntry]:
    # Check guard before evaluating
    if rule.guard is not None and not rule.guard(cfg):
        return None  # Guard says skip — this is correct behavior, not an error
    return rule.evaluate(context)
```

The [PERMITTED MODIFICATION] to `fleet_signal_coherence_agent.py` is exactly one
change — replace the hardcoded rule list initialization with the loader call. Find
the line(s) where the agent initializes its internal rules list and replace them with:

```python
from .coherence_rules.loader import CoherenceRuleLoader
self.rules = CoherenceRuleLoader.load_all()
```

No other change to the agent file. All rule evaluation logic in the agent remains
identical — only the source of the rule list changes from hardcoded to loaded.

Future sub-protocols drop a file like `pragma_coherence_rules.py` or
`mobile_coherence_rules.py` into `coherence_rules/` with their own `RULES` list, and
those rules are automatically picked up at next startup. Zero further modification to
`fleet_signal_coherence_agent.py` ever needed for any sub-protocol's rule additions.

**Test file:** `bridge/tests/test_coherence_rule_loader.py` — write 15+ tests covering:
all 18 existing VAPI rules load correctly, rule count is exactly 18, rule_id collision
detection raises correctly, a mock sub-protocol rules file in a temp directory loads
correctly alongside core rules, guard fields are preserved exactly (not dropped), guard
evaluation skips rules correctly when guard returns False, guard evaluation runs rules
correctly when guard returns True, and the FleetSignalCoherenceAgent behaves identically
before and after the refactor for all existing test scenarios.

Run `pytest bridge/` after this step. All 2230+ tests must pass before proceeding.

---

### STEP 5 — Extensible Tool Catalog Registration

**New files:**
```
bridge/vapi_bridge/tool_registry.py
bridge/vapi_bridge/tools/__init__.py
bridge/vapi_bridge/tools/vapi_core_tools.py
```

**[PERMITTED MODIFICATION]:** `bridge/vapi_bridge/bridge_agent.py` — one line addition
to tool initialization only.

Build a `ToolRegistry` singleton that manages tool registration across VAPI core and
sub-protocols. It enforces range ownership — a sub-protocol may only register tool
numbers within the range it declared in its `SubProtocolConfig.agent_range`. This
prevents number collisions at startup rather than at runtime.

Define a `ToolDefinition` dataclass:

```python
@dataclass
class ToolDefinition:
    number: int           # globally unique tool number, e.g., 1–149 for VAPI core
    name: str             # snake_case name, e.g., "get_separation_ratio_status"
    description: str      # human-readable purpose
    handler: Callable     # the actual tool function
    sub_protocol: str     # "VAPI_CORE", "VAPI_MOBILE", "PRAGMA_JUDGE"
    phase_introduced: int # phase number when this tool was added
    schema: dict          # OpenAPI-compatible parameter schema dict
```

The `ToolRegistry` class must implement:

`register_tool(tool: ToolDefinition) → None` — validates the tool number is not
already registered (raises `ToolNumberConflictError`) and falls within a range owned
by the tool's declared sub-protocol as registered in `SubProtocolRegistry` (raises
`ToolRangeViolationError` if not). Stores the tool in the internal registry.

`register_tool_range(tools: list[ToolDefinition]) → None` — batch registration.
Validates all tools before applying any, making the operation atomic — either all
register or none do.

`get_tool(number: int) → ToolDefinition` — retrieves by number.

`get_all_tools() → dict[int, ToolDefinition]` — returns the full registry.

`get_tools_for_protocol(protocol_name: str) → list[ToolDefinition]` — filtered view.

In `tools/vapi_core_tools.py`, register all 149 existing VAPI tools in the VAPI_CORE
range (numbers 1–149). Each tool entry should accurately name the handler it wraps.
You do not need to duplicate handler logic — reference the existing handler functions.

The [PERMITTED MODIFICATION] to `bridge_agent.py` is one addition to its initialization:

```python
# Add to BridgeAgent's __init__ or startup method:
from .tools.vapi_core_tools import VAPI_CORE_TOOLS
from .tool_registry import ToolRegistry
ToolRegistry.instance().register_tool_range(VAPI_CORE_TOOLS)
```

Sub-protocols will later call `register_tool_range()` with their own tool lists. No
further modification to `bridge_agent.py` is ever needed for tool additions from any
sub-protocol.

**Test file:** `bridge/tests/test_tool_registry.py` — write 20+ tests covering:
registration success, number conflict detection, range violation detection, batch
atomicity (partial failure rolls back all), `get_all_tools()` completeness (149 tools
for VAPI core), and `get_tools_for_protocol()` filtering accuracy.

Run `pytest bridge/` after this step. All 2230+ tests must pass before proceeding.

---

### STEP 6 — AdjudicationRegistry Source Type Extension

**[PERMITTED MODIFICATION]:** `contracts/AdjudicationRegistry.sol`

Inspect the current `AdjudicationRegistry.sol` anchoring function. Add `sourceType`
as a parameter if it is not already present. The updated signature should be:

```solidity
/// @notice Anchors an adjudication or verdict hash on-chain with source attribution.
/// @param podHash The SHA-256 hash of the adjudication or verdict record body.
/// @param sourceType The sub-protocol that produced this record.
///        Valid values: "VAPI", "VAPI_MOBILE", "PRAGMA_JUDGE"
function anchorAdjudication(
    bytes32 podHash,
    string memory sourceType
) external;

/// @notice Overload for backward compatibility — existing VAPI call sites unchanged.
function anchorAdjudication(bytes32 podHash) external {
    anchorAdjudication(podHash, "VAPI");
}
```

The `sourceType` must be emitted in the `AdjudicationAnchored` event and stored in
the contract mapping alongside the pod hash and block number. The overload ensures
that `chain.py` and all existing VAPI call sites require zero modification —
backward compatibility is mandatory.

Deploy the updated contract to IoTeX Testnet (chain ID 4690). If the contract address
changes, update the reference in `config.py`. Update Hardhat tests to cover the
`sourceType` parameter in both the overloaded and explicit forms.

Run `pytest bridge/` and the full Hardhat suite (482+ tests) after this step. All
must pass before proceeding.

---

### STEP 7 — isFullyEligible External Call Validation Suite

**New file:** `bridge/tests/test_isfullyeligible_external.py`

Write integration tests that simulate an external contract calling
`VAPIProtocolLens.isFullyEligible(deviceId)` — exactly as `PragmaJudge`'s
`PromptCommitmentRegistry.sol` will do in production. Test all four device states
that PragmaJudge will encounter:

**State 1 — Enrolled, credential active, no active BLOCK ruling:**
Expected: `isFullyEligible()` returns `True`. Verify gas cost is within acceptable
range for an external contract call (document the measured gas cost in the test).

**State 2 — Credential exists but `expiresAt < block.timestamp`:**
Expected: `isFullyEligible()` returns `False`. This is the expired credential path
that `BiometricCredentialTTLAgent` (Phase 178) manages.

**State 3 — Credential suspended (active BLOCK ruling in RulingRegistry):**
Expected: `isFullyEligible()` returns `False`. This is the enforcement path from
`RulingEnforcementAgent` (Phase 66).

**State 4 — Device never enrolled (deviceId not in VAPIioIDRegistry):**
Expected: `isFullyEligible()` returns `False`. This is the unenrolled device path.

For each state, also verify: the return value is deterministic (same inputs produce
same output across multiple calls), and no unexpected reverts occur. If any state
produces unexpected behavior, document it immediately in a new file:

`bridge/vapi_bridge/KNOWN_EXTERNAL_BEHAVIORS.md`

This file becomes the contract that PragmaJudge's build is allowed to depend on.
Its existence and accuracy are more important than any single test passing.

Run `pytest bridge/` after this step. All 2230+ tests must pass before proceeding.

---

### STEP 8 — Cross-Protocol Test Suite Isolation

**New or updated files:**
```
pytest.ini  (root level)
bridge/pytest.ini
scripts/check_vapi_health.sh
```

Configure pytest so that test suites are cleanly isolated by sub-protocol:

```ini
# Root pytest.ini
[pytest]
testpaths = bridge pragmajudge mobile
# Running pytest with no arguments runs all suites.
# Missing directories (pragmajudge/, mobile/) produce "no tests found" — correct behavior.
```

```ini
# bridge/pytest.ini
[pytest]
testpaths = bridge/tests
# Running pytest bridge/ runs ONLY VAPI core tests.
# This is the canonical VAPI health signal. It must always be green.
```

Create `scripts/check_vapi_health.sh`:

```bash
#!/bin/bash
# ============================================================
# VAPI Core Health Check — must always pass
# Run this before every commit during sub-protocol development.
# If this fails, nothing else proceeds — fix VAPI first.
# ============================================================
set -e
echo "Running VAPI core health check (bridge/ tests only)..."
pytest bridge/ -v --tb=short
echo "VAPI core health check PASSED"
```

Make the script executable. This script becomes the mandatory gate before every
commit during the mobile expansion and PragmaJudge development phases.

Run `bash scripts/check_vapi_health.sh` as the verification for this step.

---

### STEP 9 — Sub-Protocol Architecture Documentation

**New file:** `VAPI_SUBPROTOCOL_ARCHITECTURE.md` (root of repository)

Write the canonical documentation file that every future Claude Code session reads
to understand the sub-protocol extensibility layer. This document is the architectural
memory of this phase — it must be complete enough that a future session can correctly
build VAPI_MOBILE or PRAGMA_JUDGE using only this document and the codebase,
without access to this conversation.

Structure the document as follows:

**Section 1 — What this layer is and why it exists.** Explain in 3–4 paragraphs that
VAPI was originally a self-contained protocol and this phase adds a formal sub-protocol
hosting capability. Describe the two immediate sub-protocols (TouchAC mobile and
PragmaJudge) and the design principle that sub-protocols share infrastructure without
modifying core.

**Section 2 — The five integration points.** For each of the five mechanisms through
which a sub-protocol connects to VAPI, provide both a description and a working code
example:

- (a) `SubProtocolRegistry.register()` — declares the sub-protocol's identity, ranges, and prefixes
- (b) `FederationBus.register_namespace()` — claims ownership of an event prefix
- (c) Migration runner — drop a `.sql` file in `migrations/` named with the sub-protocol prefix
- (d) Coherence rule loader — drop a `_rules.py` file in `coherence_rules/` with a `RULES` list
- (e) `ToolRegistry.register_tool_range()` — batch-registers tools in the declared number range

**Section 3 — What sub-protocols are forbidden from doing.** Enumerate clearly: no
modification to any file in `bridge/vapi_bridge/` except via the five integration
points, no redefinition of frozen invariants, no publishing events without namespace
registration, no registering tool numbers outside the declared range.

**Section 4 — The guard mechanism.** Dedicate a section specifically to Phase 204's
`guard: Optional[Callable]` field on `CoherenceRule`. Explain what it does, when to
use it, and provide an example showing a config-gated rule. This section exists because
the guard mechanism is easily missed but critically important for rules that should only
fire under specific runtime conditions.

**Section 5 — Currently registered sub-protocols.** A table with one row per
registered sub-protocol. Initially:

| Name | Namespace | Agent Range | Tool Range | Source Type | Status |
|------|-----------|-------------|------------|-------------|--------|
| VAPI_CORE | (none) | 1–36 | 1–149 | "VAPI" | LIVE |

When VAPI_MOBILE registers, add its row. When PRAGMA_JUDGE registers, add its row.

**Section 6 — The AdjudicationRegistry sourceType convention.** Document what source
type strings are valid, which sub-protocol owns each, and how to query records by
source type for analytics and monitoring purposes.

---

### STEP 10 — VAPI-EXT Phase Verification

Run this complete verification sequence after all prior steps are complete. Do not
proceed to any next phase until every check passes.

```bash
# Health check first — if this fails, nothing else matters
bash scripts/check_vapi_health.sh

# Individual new test suites
pytest bridge/tests/test_sub_protocol_registry.py -v
pytest bridge/tests/test_federation_bus_namespacing.py -v
pytest bridge/tests/test_migration_runner.py -v
pytest bridge/tests/test_coherence_rule_loader.py -v
pytest bridge/tests/test_tool_registry.py -v
pytest bridge/tests/test_isfullyeligible_external.py -v

# Full Hardhat suite (must remain at 482+ passing)
cd contracts && npx hardhat test
```

Then run this Python verification script to confirm the registry state is correct:

```python
# Run as: python -c "$(cat scripts/verify_vapi_ext.py)"
# Or create scripts/verify_vapi_ext.py and run: python scripts/verify_vapi_ext.py

from bridge.vapi_bridge.sub_protocol_registry import SubProtocolRegistry
from bridge.vapi_bridge.coherence_rules.loader import CoherenceRuleLoader
from bridge.vapi_bridge.tool_registry import ToolRegistry

reg = SubProtocolRegistry.instance()
rules = CoherenceRuleLoader.load_all()
tools = ToolRegistry.instance().get_all_tools()

print(f"Registered protocols: {list(reg.get_registered().keys())}")
print(f"Loaded coherence rules: {len(rules)}")
print(f"Registered tools: {len(tools)}")

# Assertions — all must pass
assert "VAPI_CORE" in reg.get_registered(), "VAPI_CORE not registered"
assert len(rules) == 18, f"Expected 18 coherence rules, got {len(rules)}"
assert len(tools) == 149, f"Expected 149 tools, got {len(tools)}"

# Verify guard fields are present on all rules (not silently dropped)
rules_with_guard = [r for r in rules if r.guard is not None]
print(f"Rules with guard lambdas: {len(rules_with_guard)}")
assert len(rules_with_guard) >= 1, "At least one rule should have a guard (Phase 204 IOSWARM rule)"

# Verify rule categories
contradiction_rules = [r for r in rules if r.category == "CONTRADICTION"]
orphan_rules = [r for r in rules if r.category == "ORPHAN"]
inversion_rules = [r for r in rules if r.category == "INVERSION"]
assert len(contradiction_rules) == 8, f"Expected 8 CONTRADICTION rules, got {len(contradiction_rules)}"
assert len(orphan_rules) == 6, f"Expected 6 ORPHAN rules, got {len(orphan_rules)}"
assert len(inversion_rules) == 4, f"Expected 4 INVERSION rules, got {len(inversion_rules)}"

print("\nVAPI-EXT verification PASSED — gateway open for VAPI_MOBILE and PRAGMA_JUDGE")
```

When the verification script prints **VAPI-EXT verification PASSED**, commit with:

```
git commit -m "VAPI-EXT: Sub-protocol extensibility layer — gateway open for VAPI_MOBILE and PRAGMA_JUDGE

- SubProtocolRegistry: central registration with namespace + range collision detection
- FederationBus: namespace isolation with backward-compatible validation
- MigrationRunner: versioned SQLite schema management with tamper detection
- CoherenceRuleLoader: plugin architecture preserving Phase 204 guard mechanism
- ToolRegistry: range-validated tool registration across sub-protocols
- AdjudicationRegistry: sourceType parameter for multi-protocol record isolation
- isFullyEligible() external validation suite: 4-state coverage for PragmaJudge gate
- Test isolation: bridge/ runs independently as canonical VAPI health signal
- VAPI_SUBPROTOCOL_ARCHITECTURE.md: self-documenting integration guide

Phase 204 state preserved: CONTRADICTION=8 ORPHAN=6 INVERSION=4, guard mechanism intact
Bridge: 2230+ passing | Hardhat: 482+ passing"
```

---

## SUCCESS CRITERIA — ALL 13 MUST BE TRUE BEFORE PHASE 205 BEGINS

This phase is complete when every one of the following is confirmed:

1. All 2230+ existing bridge tests pass without any modification to existing test code.
2. All 482+ existing Hardhat tests pass without any modification to existing contract logic.
3. `SubProtocolRegistry` is live with `VAPI_CORE` pre-registered and accessible.
4. `FederationBus` namespace validation is active but transparent to all existing events.
5. `MigrationRunner` is integrated into `store.py` startup and has applied both migration files.
6. All 36 existing agents appear correctly in the `agent_manifest` table with accurate class names.
7. All 149 existing tools appear in `ToolRegistry` under the `VAPI_CORE` sub-protocol.
8. `CoherenceRuleLoader` loads all **18** existing VAPI rules (CONTRADICTION=8, ORPHAN=6, INVERSION=4).
9. All rules with guard lambdas have those lambdas preserved in the `guard` field — not dropped.
10. `AdjudicationRegistry.sol` accepts `sourceType` parameter with backward-compatible overload.
11. `isFullyEligible()` external validation suite passes all four device states.
12. `pytest bridge/` runs independently as the canonical VAPI health signal.
13. `VAPI_SUBPROTOCOL_ARCHITECTURE.md` documents all five integration points at the repository root.

When all 13 are true, VAPI is a platform. VAPI_MOBILE registers as sub-protocol one.
PRAGMA_JUDGE registers as sub-protocol two. Neither requires any further modification
to VAPI core infrastructure.

---

## CONTEXT FOR CLAUDE CODE — WHY EACH COMPONENT EXISTS

Understanding the purpose behind each component prevents misimplementation. Read this
before writing any code.

**SubProtocolRegistry** exists because without it, VAPI has no formal concept of what
is attached to it. A future session building PragmaJudge needs to call `register()` as
its first action so that its presence is explicit, auditable, and detectable by
monitoring agents. The registry also prevents silent number and namespace collisions
that would only manifest as mysterious runtime failures.

**FederationBus namespace isolation** exists because the bus is shared infrastructure.
Without namespace isolation, two sub-protocols could accidentally publish the same event
name, creating undetectable handler collisions that would be nearly impossible to debug
in a 36+ agent concurrent asyncio environment.

**MigrationRunner** exists because VAPI's store will grow with every sub-protocol.
Without versioned migrations, table additions risk schema conflicts across protocol
boundaries, and there is no audit trail of what was added when and by whom. The tamper
detection exists because a modified migration represents a data integrity violation —
the same philosophy as VAPI's PoAC chain link integrity.

**CoherenceRuleLoader** exists because `FleetSignalCoherenceAgent` is the system's
integrity monitor and must remain sub-protocol-agnostic. Without a plugin architecture,
adding PragmaJudge's three coherence rules (PRAGMA-C1, PRAGMA-C2, PRAGMA-C3) would
require modifying an agent that has no business knowing about PragmaJudge. The guard
mechanism from Phase 204 is preserved here because config-dependent rule gating is
architecturally necessary for rules that should only fire under specific operational
conditions — discarding it would be a regression.

**ToolRegistry** exists because tool number collisions between sub-protocols are a
startup validation error, not a runtime mystery. Without range ownership enforcement,
VAPI_MOBILE adding tool #150 and PRAGMA_JUDGE also adding tool #150 would produce
undefined behavior. With the registry, the second registration raises immediately.

**AdjudicationRegistry sourceType** exists because PragmaJudge verdicts and VAPI
adjudications will share the same registry. Without source type isolation, analytics
cannot distinguish them, and a monitoring query for VAPI adjudications would return
PragmaJudge verdicts as false positives.

**isFullyEligible() validation suite** exists because PragmaJudge's economic safety
depends on this call behaving correctly from an external contract. The vault
disbursement logic in `PragmaVault.sol` gates every reimbursement on this returning
`True`. Discovering an edge case after PragmaJudge is deployed is catastrophically
more expensive than discovering it during this phase.

**Test suite isolation** exists because VAPI's health must be verifiable independently
of sub-protocol development state at all times. During PragmaJudge's build, some
`pragmajudge/` tests may be intentionally failing. This must never obscure whether
VAPI core itself is healthy.

**VAPI_SUBPROTOCOL_ARCHITECTURE.md** exists because this conversation will not be
available to future Claude Code sessions. The document is the architectural memory
that makes the extensibility layer self-documenting and self-preserving across sessions.

---

*VAPI-EXT Master Prompt · Phase 204 COMPLETE baseline · 2230 bridge tests · 18 coherence rules*
*Prepared for Claude Code — do not modify this prompt before giving it to Claude Code*
*Next phase after VAPI-EXT: Phase 205 AccelTremorFFT (hardware gate)*
*First sub-protocol after VAPI-EXT: VAPI_MOBILE (TouchAC mobile expansion)*
*Second sub-protocol: PRAGMA_JUDGE (after mobile expansion complete)*

# VAPI-EXT Phase — Sub-Protocol Extensibility Layer
# Do not modify without reading VAPI_SUBPROTOCOL_ARCHITECTURE.md
