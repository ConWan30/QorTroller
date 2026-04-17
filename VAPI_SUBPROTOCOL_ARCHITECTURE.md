# VAPI Sub-Protocol Architecture

**Version:** VAPI-EXT Phase 204+  
**Status:** LIVE — gateway open for VAPI_MOBILE and PRAGMA_JUDGE

This document is the canonical architectural reference for the VAPI sub-protocol
extensibility layer. Every future Claude Code session building VAPI_MOBILE, PRAGMA_JUDGE,
or any other sub-protocol should read this document before touching any code.

---

## Section 1 — What This Layer Is and Why It Exists

VAPI (Verified Autonomous Physical Intelligence) was originally built as a self-contained
protocol: a 20-agent fleet, 149 tools, and 43 contracts all wired together as a single
cohesive system. Every feature from Phase 1 through Phase 203 existed inside `bridge/vapi_bridge/`
as first-class VAPI core code. This worked well while VAPI was a single-purpose protocol
(gaming anti-cheat on IoTeX), but it created a structural problem: any new application
domain wanting to share VAPI's infrastructure had to modify core VAPI files, making each
integration a potential source of regressions.

Phase 204 (VAPI-EXT) solves this by adding a formal sub-protocol hosting capability. A
sub-protocol is an isolated application layer that shares VAPI's infrastructure (database,
federation bus, coherence engine, tool catalog) without modifying any core file. Sub-protocols
register their identity once at startup via five integration points, then operate independently
within their declared boundaries. VAPI_CORE continues to own agents 1–36, tools 1–149, and
the canonical `""` event namespace. Sub-protocols own non-overlapping ranges.

Two immediate sub-protocols are planned:

- **VAPI_MOBILE / TouchAC**: Touchpad-native competitive authentication for mobile devices.
  Extends the enrollment protocol to work without a DualShock Edge, targeting smartphones
  and tablets as primary input devices.

- **PragmaJudge**: AI-mediated prompt commitment registry for competitive AI game play.
  Uses `VAPIProtocolLens.isFullyEligible(deviceId)` as its eligibility gate — VAPI proves
  the human is present, PragmaJudge records and enforces their prompt commitments.

The design principle is: **sub-protocols share infrastructure, never modify core**. A future
session building PRAGMA_JUDGE should never need to edit `fleet_signal_coherence_agent.py`,
`bridge_agent.py`, or `store.py`. All integration happens through the five points below.

---

## Section 2 — The Five Integration Points

### (a) SubProtocolRegistry.register() — Identity Declaration

The first thing a sub-protocol startup does is register itself in `SubProtocolRegistry`.
This declares the sub-protocol's identity, owned number ranges, and prefixes. Registration
fails immediately (at startup) if any collision is detected — no silent conflicts.

**File:** `bridge/vapi_bridge/sub_protocol_registry.py`

```python
from vapi_bridge.sub_protocol_registry import SubProtocolRegistry, SubProtocolConfig

SubProtocolRegistry.instance().register(SubProtocolConfig(
    name="PRAGMA_JUDGE",
    event_namespace="pragma.",         # All events must be prefixed "pragma."
    agent_range=(61, 80),              # Agents #61–#80 owned by PRAGMA_JUDGE
                                       # (37–60 reserved for VAPI_MOBILE)
    tool_range=(201, 250),             # Tools #201–#250 owned by PRAGMA_JUDGE
                                       # (150–200 reserved for VAPI_MOBILE)
    table_prefix="pj_",               # All SQLite tables must start "pj_"
    contract_source_type="PRAGMA",    # AdjudicationRegistry sourceType value
    version="0.1",
    dry_run=True,                      # Start in dry_run; disable when live
    permitted_vapi_interfaces=[        # Explicit isolation contract — PRAGMA_JUDGE
        "VAPIProtocolLens.isFullyEligible",       #   may ONLY call these VAPI APIs.
        "AdjudicationRegistry.anchorAdjudication", #  Any call not on this list is a
    ],                                 #   boundary violation (see Section 3, Rule 8).
))
```

Collision detection covers: name, agent_range overlap, tool_range overlap, event_namespace,
table_prefix, and contract_source_type. Any collision raises `SubProtocolConflictError` at
startup — the system refuses to start rather than silently overwrite.

VAPI_CORE is always pre-registered (agents 1–36, tools 1–149, namespace `""`) and cannot
be deactivated.

### (b) FederationBus.register_namespace() — Event Ownership

After registering in SubProtocolRegistry, the sub-protocol claims ownership of its event
namespace in the FederationBus. This ensures that if two sub-protocols accidentally use the
same event prefix, the conflict is detected immediately rather than at runtime.

**File:** `bridge/vapi_bridge/federation_bus.py`

```python
from vapi_bridge.federation_bus import FederationBus, register_namespace

# Claim the "pragma." namespace for PRAGMA_JUDGE
register_namespace("pragma.", "PRAGMA_JUDGE")

# Publish a namespaced event — validates ownership before publish
await FederationBus().publish_namespaced(
    "pragma.commitment_registered",
    {"device_id": device_id, "commitment_hash": h},
    owner="PRAGMA_JUDGE",
)
```

VAPI_CORE events use the empty prefix (`""`) and are always allowed through without
namespace validation — backward compatibility with all pre-Phase-204 events is preserved.
Existing VAPI agents continue using `AgentMessageBus.publish()` unchanged.

### (c) Migration Runner — Schema Management

Sub-protocols that need new SQLite tables drop a `.sql` file into
`bridge/vapi_bridge/migrations/` named with the sub-protocol prefix. The MigrationRunner
(integrated into `Store.__init__`) applies all pending migrations in alphabetical order
at startup, with SHA-256 tamper detection for already-applied files.

**Naming convention:** `{sub_protocol_prefix}_{number}_{description}.sql`  
Example: `pragma_001_commitment_registry.sql`

```sql
-- pragma_001_commitment_registry.sql
CREATE TABLE IF NOT EXISTS pj_commitment_registry (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT NOT NULL,
    commitment_hash TEXT NOT NULL UNIQUE,
    block_number    INTEGER NOT NULL,
    created_at      REAL NOT NULL
);
```

The MigrationRunner tracks applied migrations in `schema_migrations(filename, sha256, applied_at)`.
Applying the same file twice is idempotent. Modifying an applied file raises `MigrationTamperError`.

**File:** `bridge/vapi_bridge/migrations/runner.py`

### (d) CoherenceRuleLoader — Rule Plugin Architecture

Sub-protocols that need coherence rules (contradiction detection, orphan detection,
temporal inversion detection) drop a `*_rules.py` file into `bridge/vapi_bridge/coherence_rules/`.
The file must define a `RULES: list[CoherenceRule]` variable. The loader discovers and
injects these rules at startup.

**File:** `bridge/vapi_bridge/coherence_rules/pragma_rules.py`

```python
from vapi_bridge.coherence_rules.base import CoherenceRule

RULES: list[CoherenceRule] = [
    CoherenceRule(
        name="COMMITMENT_WITHOUT_ELIGIBILITY",
        category="CONTRADICTION",
        severity="CRITICAL",
        agents_involved=["PromptCommitmentAgent", "EnrollmentAutoGuidanceAgent"],
        explanation="A prompt commitment was recorded for a device that is not fully eligible.",
        resolution="Verify isFullyEligible() before accepting any commitment.",
        rule_dict={
            "query": "SELECT COUNT(*) FROM pj_commitment_registry cr "
                     "LEFT JOIN device_enrollments de ON cr.device_id=de.device_id "
                     "WHERE de.status IS NULL OR de.status != 'credentialed'",
            "params": lambda cfg: (),
            "threshold": 0,
        },
        guard=lambda cfg: getattr(cfg, "pragma_judge_enabled", False),
        sub_protocol="PRAGMA_JUDGE",
        phase_introduced=205,
    ),
]
```

The guard lambda (`guard: Optional[Callable]`) is Phase 204's config-dependent gating
mechanism — see Section 4 for full details. Rules are injected into FSCA's runtime dicts
at startup; FSCA picks them up on the next poll cycle without any modification to FSCA.

**Inject at sub-protocol startup:**
```python
from vapi_bridge.coherence_rules.loader import CoherenceRuleLoader
from .pragma_rules import RULES as PRAGMA_RULES

CoherenceRuleLoader.inject_rules(PRAGMA_RULES)
```

### (e) ToolRegistry.register_tool_range() — Tool Catalog Registration

Sub-protocols register their tools in ToolRegistry at startup. This prevents number
collisions between sub-protocols — if PRAGMA_JUDGE tries to claim tool #50 (owned by
VAPI_CORE), it raises `ToolRangeViolationError` at startup.

**File:** `bridge/vapi_bridge/tool_registry.py`

```python
from vapi_bridge.tool_registry import ToolDefinition, ToolRegistry
from vapi_bridge._noop_handler import _noop

PRAGMA_JUDGE_TOOLS = [
    ToolDefinition(
        number=201,
        name="get_commitment_status",
        description="Get the prompt commitment status for a device.",
        handler=_noop,                 # Real handler wired in PragmaJudgeAgent
        sub_protocol="PRAGMA_JUDGE",
        phase_introduced=205,
    ),
    # ... more tools up to the declared tool_range upper bound (201–250)
]

ToolRegistry.instance().register_tool_range(PRAGMA_JUDGE_TOOLS)
```

VAPI_CORE tools (numbers 1–149) are registered at BridgeAgent startup via the
[PERMITTED MODIFICATION] in `bridge_agent.py`.

---

## Section 3 — What Sub-Protocols Are Forbidden From Doing

These rules are not suggestions. Violating them creates regression risk for VAPI_CORE
and breaks the isolation contract that makes sub-protocols safe to deploy.

1. **No modification to any file in `bridge/vapi_bridge/`** except via the five integration
   points above. No new imports added to existing files. No new functions added to store.py.
   No new routes added to operator_api.py. If you think you need to modify a core file,
   you are probably missing an integration point.

2. **No redefinition of VAPI_CORE frozen invariants.** The PoAC wire format (228 bytes),
   chain hash formula (SHA-256(raw[0:164])), L4 thresholds (7.009/5.367), ZK circuit
   invariants, and epistemic consensus threshold (0.65) are frozen. Sub-protocols may not
   propose or implement changes to these values.

3. **No publishing events without namespace registration.** All events published via
   `FederationBus.publish_namespaced()` must first register their namespace via
   `register_namespace()`. Events without a registered namespace prefix are VAPI_CORE
   events and are owned by VAPI_CORE exclusively.

4. **No registering tool numbers outside the declared range.** If SubProtocolConfig declares
   `tool_range=(150, 200)`, then only tool numbers 150–200 may be registered. Numbers
   1–149 are VAPI_CORE property. `ToolRangeViolationError` is raised at startup if violated.

5. **No claiming VAPI_CORE agent numbers.** Agent numbers 1–36 are owned by VAPI_CORE.
   Sub-protocol agents must be numbered above 36 within the declared `agent_range`.

6. **No shared table names without `table_prefix`.** All SQLite tables created by a
   sub-protocol must begin with the `table_prefix` declared in SubProtocolConfig. This
   prevents accidental table collision with VAPI_CORE tables or other sub-protocols.

7. **No registering sourceType strings that conflict with registered sub-protocols.**
   The `AdjudicationRegistry.anchorAdjudication(podHash, sourceType)` `sourceType` parameter

8. **No calling VAPI APIs not listed in `permitted_vapi_interfaces`.** The
   `SubProtocolConfig.permitted_vapi_interfaces` field is the explicit isolation contract
   for each sub-protocol. When Claude Code builds a new sub-protocol feature, it must
   verify that any VAPI API call it writes appears in the sub-protocol's
   `permitted_vapi_interfaces` list. If it does not appear there, do NOT call it —
   instead, either (a) add it to the list explicitly with justification, or (b) find
   an integration-point-based solution (migration, coherence rule, bus event) that does
   not require a direct VAPI API call. The most common violation is calling `store.py`
   methods directly to query enrollment status — the correct path is publishing a
   `pragma.eligibility_check_requested` bus event and consuming the
   `enrollment_complete` response, or reading the VHP credential via
   `isFullyEligible()` which is already permitted. This rule is enforced by code
   review and architecture doc reference, not at runtime.
   must match the `contract_source_type` declared in SubProtocolConfig.

---

## Section 4 — The Guard Mechanism (Phase 204 Innovation)

`CoherenceRule` has an optional `guard: Optional[Callable]` field. When present, the guard
is a lambda that receives the bridge config object and returns a boolean. If it returns
`False`, the rule is **silently skipped** — this is correct behavior, not an error. If it
returns `True` (or is `None`), the rule evaluates normally.

**Why it exists:** Some coherence rules should only fire when a specific feature is enabled.
Before Phase 204, ALL rules fired on every poll cycle regardless of config state. This
meant rules for disabled features would generate false-positive violations. The guard
mechanism gates rule evaluation behind a config check.

**The canonical example — `IOSWARM_ACTIVE_NO_ADJUDICATIONS`:**

```python
CoherenceRule(
    name="IOSWARM_ACTIVE_NO_ADJUDICATIONS",
    category="CONTRADICTION",
    # ... other fields ...
    guard=lambda cfg: (
        bool(getattr(cfg, "ioswarm_enabled", False)) and
        bool(getattr(cfg, "ioswarm_adjudication_enabled", False))
    ),
    sub_protocol="VAPI_CORE",
    phase_introduced=204,
)
```

This rule only fires when `ioswarm_enabled=True` AND `ioswarm_adjudication_enabled=True`.
When either flag is False (the default), the guard returns False and the rule is skipped.

**How FSCA handles it:** FSCA's `_check_contradictions()` reads `rule_dict["guard"]` and
calls it before evaluating the SQL query. The `CoherenceRuleLoader.inject_rules()` method
preserves the guard by copying it into `rule_dict["guard"]` when injecting into FSCA's
runtime dicts.

**When to use guard on sub-protocol rules:**
- Use a guard when the rule depends on a feature flag that defaults to disabled.
- Use a guard when the rule requires data that may not exist yet (e.g., only when a
  specific agent is active).
- Do NOT use a guard to make a critical safety rule optional. Rules at CRITICAL severity
  should not be gated — they should always fire.

**Guard preservation invariant:** Guards must never be silently dropped. `CoherenceRuleLoader`
preserves guards. If you see a rule that had a guard in its source but shows `guard=None`
after loading, that is a regression. The test `test_ioswarm_rule_has_guard` in
`test_coherence_rule_loader.py` verifies this invariant.

---

## Section 5 — Currently Registered Sub-Protocols

| Name | Namespace | Agent Range | Tool Range | Source Type | Status |
|------|-----------|-------------|------------|-------------|--------|
| VAPI_CORE | (none) | 1–36 | 1–149 | "VAPI" | LIVE (Phase 1–204) |

When VAPI_MOBILE registers, add its row here. When PRAGMA_JUDGE registers, add its row.

**Planned (not yet registered):**

| Name | Planned Namespace | Planned Agent Range | Planned Tool Range | Source Type | Status |
|------|-------------------|--------------------|--------------------|-------------|--------|
| VAPI_MOBILE | `mobile.` | 37–60 | 150–200 | "VAPI_MOBILE" | PLANNED |
| PRAGMA_JUDGE | `pragma.` | 61–80 | 201–250 | "PRAGMA" | PLANNED |

---

## Section 6 — AdjudicationRegistry sourceType Convention

`AdjudicationRegistry.sol` (Phase 111 + VAPI-EXT) records adjudication and verdict hashes
on-chain. As of VAPI-EXT Phase 204, it supports a `sourceType` parameter that identifies
which sub-protocol produced each record.

**Functions:**

```solidity
// New API: explicit source attribution (VAPI-EXT)
function anchorAdjudication(bytes32 podHash, string memory sourceType) external onlyOwner

// Backward-compat overload: defaults to "VAPI" (existing chain.py unchanged)
function anchorAdjudication(bytes32 podHash) external onlyOwner

// Legacy API: full VAPI_CORE record with deviceIdHash and dualVeto
function recordAdjudication(bytes32 deviceIdHash, bytes32 poadHash, bool dualVeto) external onlyOwner
```

**Valid sourceType strings and their owners:**

| sourceType | Owner Sub-Protocol | Description |
|------------|--------------------|-------------|
| `"VAPI"` | VAPI_CORE | Standard PoAd adjudication (Phase 112 bridge path) |
| `"VAPI_MOBILE"` | VAPI_MOBILE | Mobile touchpad session adjudication |
| `"PRAGMA_JUDGE"` | PRAGMA_JUDGE | Prompt commitment registry verdicts |
| `""` | VAPI_CORE legacy | Records created via `recordAdjudication()` (empty string) |

**Querying by sourceType:**

```solidity
// On-chain: check source type of a recorded hash
string memory src = registry.getSourceType(podHash);

// Off-chain analytics: filter by source in bridge store (future)
// SELECT * FROM poad_registry_log WHERE source_type = 'PRAGMA_JUDGE'
```

**Anti-replay guarantee:** The `poadRecorded` mapping is shared across ALL sourceTypes.
A hash recorded by VAPI cannot be re-recorded by PRAGMA_JUDGE, and vice versa. This
prevents hash-grinding attacks where an attacker re-anchors a known hash under a different
source type to create a misleading on-chain record.

---

## Quick-Start: Adding a New Sub-Protocol

1. Register in SubProtocolRegistry at startup (Section 2a)
2. Register event namespace in FederationBus (Section 2b)  
3. Drop migration files in `bridge/vapi_bridge/migrations/` (Section 2c)
4. Drop coherence rules in `bridge/vapi_bridge/coherence_rules/` (Section 2d)
5. Register tools in ToolRegistry at startup (Section 2e)
6. Add a row to Section 5 of this document
7. Run `bash scripts/check_vapi_health.sh` — all bridge/ tests must pass

If any step fails at startup (collision, range violation, namespace conflict), the system
refuses to start with a clear error message identifying the collision. Fix the conflict
before proceeding.

---

*Maintained by VAPI_CORE. Last updated: VAPI-EXT Phase 204, 2026-04-12.*  
*Test authority: `bridge/tests/test_sub_protocol_registry.py` (32 tests), `test_federation_bus_namespacing.py` (20 tests), `test_migration_runner.py` (18 tests), `test_coherence_rule_loader.py` (22 tests), `test_tool_registry.py` (32 tests), `test_isfullyeligible_external.py` (25 tests).*
