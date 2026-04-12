-- vapi_ext_001_sub_protocol_registry.sql
-- VAPI-EXT Phase 204+ — Sub-Protocol Registry meta-table
--
-- Records every sub-protocol registered with VAPI infrastructure.
-- Populated at startup by SubProtocolRegistry.instance().register() calls.
-- VAPI_CORE is the baseline entry (agent_range 1-36, tool_range 1-149).
--
-- This table is an audit log — it never drives runtime decisions.
-- Runtime decisions use SubProtocolRegistry (in-memory singleton).

CREATE TABLE IF NOT EXISTS vapi_ext_sub_protocol_registry (
    name                  TEXT PRIMARY KEY,
    event_namespace       TEXT NOT NULL DEFAULT '',
    agent_range_first     INTEGER NOT NULL,
    agent_range_last      INTEGER NOT NULL,
    tool_range_first      INTEGER NOT NULL,
    tool_range_last       INTEGER NOT NULL,
    table_prefix          TEXT NOT NULL DEFAULT '',
    contract_source_type  TEXT NOT NULL,
    version               TEXT NOT NULL,
    dry_run               INTEGER NOT NULL DEFAULT 1,  -- boolean: 1=True
    active                INTEGER NOT NULL DEFAULT 1,  -- boolean: 1=True
    registered_at         REAL NOT NULL
);

-- Bootstrap: insert VAPI_CORE baseline (idempotent)
INSERT OR IGNORE INTO vapi_ext_sub_protocol_registry (
    name, event_namespace, agent_range_first, agent_range_last,
    tool_range_first, tool_range_last, table_prefix, contract_source_type,
    version, dry_run, active, registered_at
) VALUES (
    'VAPI_CORE', '', 1, 36, 1, 149, '', 'VAPI', 'phase204', 1, 1,
    strftime('%s', 'now')
);
