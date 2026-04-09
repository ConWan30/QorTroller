"""
vapi_managed_agents.py — VAPI Managed Agent Layer (Phase 177)
=============================================================
Three Claude Managed Agents connected to the existing 26-agent fleet
via a P2P Knowledge Bus built on VAPI's existing SQLite infrastructure.

Architecture:
                        HUMANS
                           ↕
         ┌─────────────────────────────────┐
         │   MANAGED AGENT LAYER (new)     │
         │  EnrollmentCoordinatorAgent (A) │
         │  CohortDefensibilityAgent    (B) │
         │  OperatorOnboardingAgent     (C) │
         └──────────────┬──────────────────┘
                        │ P2P Knowledge Bus
                        │ (agent_bus table in bridge/vapi_store.db)
                        │ + MCP knowledge_server.py
         ┌──────────────┴──────────────────┐
         │   VAPI 26-AGENT FLEET (existing) │
         │  Agent 15: SeparationRatioMonitor│
         │  Agent 20: EnrollmentAutoGuidance│
         │  Agent 21: FleetConsensusSnapshot│
         │  Agent 22: BiometricPrivacy      │
         │  Agent 23: SepRatioRecovery      │
         │  Agent 24: AgeWeightedRatio      │
         │  Agent 25: PoACChainIntegrity    │
         │  Agent 26: ProtocolMaturity      │
         │  ... (18 others)                 │
         └──────────────┬──────────────────┘
                        │
         ┌──────────────┴──────────────────┐
         │   VAPI PROTOCOL (immutable)      │
         │  PoAC 228B · AdjudicationReg    │
         │  PITL L0-L7 · IoTeX Testnet     │
         └─────────────────────────────────┘

P2P Knowledge Bus design:
  - Shared SQLite table: agent_bus (in bridge/vapi_store.db)
  - No central broker. Every agent reads/writes directly.
  - Messages carry VAPI provenance: [VAPI:Phase{N}:{agent_id}:{kind}]
  - Channels: enrollment | separation | defensibility | operator |
               sweep | wiki | alert | maturity
  - TTL: 24 hours (messages expire — privacy compliance)
  - Privacy: no raw biometric data on bus — derived signals only (BP-007)

Phase 177 changes vs Phase 166 version:
  - Agents #23-26 registered on bus (SepRatioRecovery, AgeWeightedRatio,
    PoACChainIntegrity, ProtocolMaturityScoring)
  - "maturity" bus channel added
  - FROZEN dict: bridge_baseline/sdk_baseline/agent_count fields
  - live_tdi() / live_maturity() / live_recovery() / live_integrity() helpers
  - MA-001 system prompt: TDI + age weighting + P1_RE_ENROLLMENT urgency
  - MA-002 system prompt: P1_RE_ENROLLMENT signal + persona break candidates
  - MA-003 system prompt: maturity_score ALPHA + isChainIntegrous() W2
  - CORPUS paths corrected to VAPI-WORKFLOW.v2/ directory
  - Model updated to claude-opus-4-6

Usage:
  # Initialize the bus schema
  python vapi_managed_agents.py init_bus

  # Launch managed agents (requires ANTHROPIC_API_KEY)
  python vapi_managed_agents.py launch enrollment    # Agent A
  python vapi_managed_agents.py launch defensibility # Agent B
  python vapi_managed_agents.py launch operator      # Agent C

  # P2P bus operations
  python vapi_managed_agents.py bus_status           # who's active, message counts
  python vapi_managed_agents.py bus_read enrollment  # read enrollment channel
  python vapi_managed_agents.py bus_publish <channel> <message>

  # Generate Claude Code integration prompt for managed agent setup
  python vapi_managed_agents.py generate_prompt

  # Run as Claude Code brief (no managed infra — local execution mode)
  python vapi_managed_agents.py brief enrollment 177
"""

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────

ROOT       = Path(__file__).resolve().parent
DB_PATH    = ROOT / "bridge" / "vapi_store.db"
BRIDGE_URL = "http://localhost:8080"
MCP_URL    = "http://localhost:8080/mcp"

CORPUS = {
    "memory":     ROOT / "VAPI-WORKFLOW.v2" / "VAPI_MEMORY.md",
    "invariants": ROOT / "VAPI-WORKFLOW.v2" / "VAPI_INVARIANTS.md",
    "what_if":    ROOT / "VAPI-WORKFLOW.v2" / "VAPI_WHAT_IF.md",
    "agents":     ROOT / "VAPI-WORKFLOW.v2" / "VAPI_AGENTS.md",
    "skills":     ROOT / "VAPI-WORKFLOW.v2" / "VAPI_SKILLS.md",
    "context":    ROOT / "VAPI-WORKFLOW.v2" / "VAPI_CONTEXT.md",
}

RUNBOOK = ROOT / "docs" / "operator-onboarding-runbook.md"
WIKI    = ROOT / "wiki"

# ─────────────────────────────────────────────────────────────
# Frozen values (same as vapi_wiki_engine.py) — Phase 177
# ─────────────────────────────────────────────────────────────

FROZEN = {
    "separation_gate":         0.70,
    "epistemic_threshold":     0.65,
    "auto_activate":           False,
    "dry_run":                 True,
    "ioswarm_live_nodes":      0,
    "adjudication_registry":   "0x44CF981f46a52ADE56476Ce894255954a7776fb4",
    "vhp_address":             "0xD3B2E259A4B69EF08e263e3A57B2507B7eac3dcF",
    "enrollment_min_sessions": 10,
    "defensibility_required":  True,   # Phase 157 target (W1 fix)
    "bridge_baseline":         1998,   # Phase 177 bridge test count
    "sdk_baseline":            325,    # Phase 177 SDK test count
    "agent_count":             26,     # Phase 177 fleet size
}

# Managed agent IDs (extend the 26-agent fleet namespace)
MANAGED_AGENTS = {
    "A": {"id": "MA-001", "name": "EnrollmentCoordinatorAgent",  "channel": "enrollment"},
    "B": {"id": "MA-002", "name": "CohortDefensibilityAgent",    "channel": "defensibility"},
    "C": {"id": "MA-003", "name": "OperatorOnboardingAgent",     "channel": "operator"},
}

# Bus channels — each agent subscribes to relevant ones
# Phase 177: "maturity" channel added for ProtocolMaturityScoringAgent (#26)
BUS_CHANNELS = {
    "enrollment":    "Player enrollment status, session counts, urgency levels",
    "separation":    "Separation ratio snapshots from Agent 15 — read-only from fleet",
    "defensibility": "Defensibility scores from separation_defensibility_log",
    "operator":      "Operator onboarding progress, ioSwarm node registration",
    "sweep":         "Skill 14 PostCode sweep results — broadcast from wiki engine",
    "wiki":          "Wiki engine events — brief generated, snapshot taken, sync complete",
    "alert":         "Cross-agent alerts requiring immediate coordination",
    "maturity":      "Protocol maturity score (Agent 26) — ALPHA/BETA/PRODUCTION_CANDIDATE",
}

# ─────────────────────────────────────────────────────────────
# P2P Knowledge Bus — SQLite schema
# Uses existing vapi_store.db — no new database
# ─────────────────────────────────────────────────────────────

BUS_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_bus (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    expires_at      TEXT NOT NULL,
    from_agent      TEXT NOT NULL,
    to_agent        TEXT,          -- NULL = broadcast to all subscribers
    channel         TEXT NOT NULL,
    message_type    TEXT NOT NULL, -- PUBLISH | REQUEST | RESPONSE | ALERT
    payload         TEXT NOT NULL, -- JSON — never raw biometric data (BP-007)
    provenance      TEXT NOT NULL, -- [VAPI:Phase{N}:{agent_id}:{kind}]
    read_by         TEXT,          -- JSON array of agent IDs that have read this
    acknowledged    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_bus_channel ON agent_bus(channel);
CREATE INDEX IF NOT EXISTS idx_bus_ts      ON agent_bus(ts);
CREATE INDEX IF NOT EXISTS idx_bus_expires ON agent_bus(expires_at);
CREATE INDEX IF NOT EXISTS idx_bus_from    ON agent_bus(from_agent);

-- Agent registry: who is active, last heartbeat
CREATE TABLE IF NOT EXISTS managed_agent_registry (
    agent_id        TEXT PRIMARY KEY,
    agent_name      TEXT NOT NULL,
    agent_type      TEXT NOT NULL,  -- MANAGED | FLEET
    status          TEXT NOT NULL DEFAULT 'OFFLINE',
    last_heartbeat  TEXT,
    subscribed_channels TEXT,       -- JSON array
    capabilities    TEXT,           -- JSON array
    mcp_tools       TEXT            -- JSON array of MCP tools this agent uses
);
"""

def get_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""

def prov(phase: int, agent_id: str, kind: str = "PUBLISH") -> str:
    return f"[VAPI:Phase{phase}:{agent_id}:{kind}]"

def detect_phase() -> int:
    # Try VAPI_MEMORY.md first (Phase 177 — Document Version section)
    mem = read(CORPUS["memory"])
    m = re.search(r"Document Version.*?Phase\s+(\d{2,3})", mem)
    if m:
        return int(m.group(1))
    # Fall back to scanning for highest phase reference
    m = re.search(r"Phase\s+(\d{2,3})\s+COMPLETE", mem)
    if m:
        return int(m.group(1))
    return 177

def live_ratio() -> Optional[float]:
    rows = db_query(
        "SELECT bt_strat_ratio FROM separation_ratio_snapshots ORDER BY created_at DESC LIMIT 1"
    )
    if rows and rows[0]["bt_strat_ratio"] is not None:
        return rows[0]["bt_strat_ratio"]
    # Fall back to pooled_ratio
    rows2 = db_query(
        "SELECT pooled_ratio FROM separation_ratio_snapshots ORDER BY created_at DESC LIMIT 1"
    )
    return rows2[0]["pooled_ratio"] if rows2 else None

def live_tdi() -> Optional[float]:
    """Returns the latest temporal_drift_index from age_weight_analysis_log (Phase 175)."""
    rows = db_query(
        "SELECT temporal_drift_index FROM age_weight_analysis_log ORDER BY created_at DESC LIMIT 1"
    )
    return rows[0]["temporal_drift_index"] if rows else None

def live_tdi_direction() -> str:
    """Returns drift_direction from age_weight_analysis_log (Phase 175)."""
    rows = db_query(
        "SELECT drift_direction FROM age_weight_analysis_log ORDER BY created_at DESC LIMIT 1"
    )
    return rows[0]["drift_direction"] if rows else "UNKNOWN"

def live_maturity() -> Optional[float]:
    """Returns the latest maturity_score from protocol_maturity_log (Phase 177)."""
    rows = db_query(
        "SELECT maturity_score, maturity_tier FROM protocol_maturity_log ORDER BY created_at DESC LIMIT 1"
    )
    return rows[0] if rows else None

def live_recovery() -> Optional[str]:
    """Returns recovery_action from separation_ratio_recovery_log (Phase 173)."""
    rows = db_query(
        "SELECT recovery_action FROM separation_ratio_recovery_log ORDER BY created_at DESC LIMIT 1"
    )
    return rows[0]["recovery_action"] if rows else None

def live_integrity() -> Optional[float]:
    """Returns integrity_score from poac_chain_audit_log (Phase 176)."""
    rows = db_query(
        "SELECT integrity_score FROM poac_chain_audit_log ORDER BY created_at DESC LIMIT 1"
    )
    return rows[0]["integrity_score"] if rows else None

def db_query(sql: str, params=()) -> list[dict]:
    if not DB_PATH.exists():
        return []
    try:
        conn = get_db()
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []

def db_execute(sql: str, params=()):
    conn = get_db()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()

# ─────────────────────────────────────────────────────────────
# Bus operations
# ─────────────────────────────────────────────────────────────

def bus_publish(from_agent: str, channel: str, payload: dict,
                to_agent: str = None, msg_type: str = "PUBLISH",
                phase: int = None) -> int:
    """
    Publishes a message to the P2P bus.
    Payload must never contain raw biometric data (BP-007 enforced).
    TTL: 24 hours.
    """
    if phase is None:
        phase = detect_phase()

    if channel not in BUS_CHANNELS:
        raise ValueError(f"Unknown channel '{channel}'. Valid: {list(BUS_CHANNELS.keys())}")

    # BP-007 check — block raw biometric fields
    raw_fields = {"raw_hid", "sensor_commitment", "feature_vector",
                  "mahalanobis_raw", "touchpad_raw", "gyro_raw", "accel_raw"}
    payload_keys = set(payload.keys())
    if payload_keys & raw_fields:
        raise ValueError(
            f"BP-007 VIOLATION: Raw biometric fields {payload_keys & raw_fields} "
            f"must not be published to agent bus. Use derived signals only."
        )

    expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    provenance = prov(phase, from_agent)

    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO agent_bus
        (expires_at, from_agent, to_agent, channel, message_type, payload, provenance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (expires, from_agent, to_agent, channel,
          msg_type, json.dumps(payload), provenance))
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"  [BUS:PUBLISH] {from_agent} -> {channel} | msg_id={msg_id}")
    return msg_id

def bus_read(agent_id: str, channel: str, limit: int = 10) -> list[dict]:
    """
    Reads messages from a channel that this agent hasn't seen yet.
    Marks them as read.
    Purges expired messages automatically.
    """
    # Purge expired
    db_execute(
        "DELETE FROM agent_bus WHERE expires_at < datetime('now', 'utc')"
    )

    now = datetime.now(timezone.utc).isoformat()
    rows = db_query("""
        SELECT * FROM agent_bus
        WHERE channel = ?
        AND (to_agent IS NULL OR to_agent = ?)
        AND expires_at > ?
        AND (read_by IS NULL OR json_extract(read_by, '$') NOT LIKE ?)
        ORDER BY ts DESC LIMIT ?
    """, (channel, agent_id, now, f"%{agent_id}%", limit))

    # Mark as read
    for row in rows:
        existing = json.loads(row.get("read_by") or "[]")
        if agent_id not in existing:
            existing.append(agent_id)
        db_execute(
            "UPDATE agent_bus SET read_by = ? WHERE id = ?",
            (json.dumps(existing), row["id"])
        )

    return [dict(r) for r in rows]

def heartbeat(agent_id: str, agent_name: str, agent_type: str,
              channels: list[str], capabilities: list[str],
              mcp_tools: list[str]):
    """Registers/updates agent presence in the managed_agent_registry."""
    ts = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO managed_agent_registry
        (agent_id, agent_name, agent_type, status, last_heartbeat,
         subscribed_channels, capabilities, mcp_tools)
        VALUES (?, ?, ?, 'ONLINE', ?, ?, ?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
        status='ONLINE', last_heartbeat=excluded.last_heartbeat,
        subscribed_channels=excluded.subscribed_channels
    """, (agent_id, agent_name, agent_type, ts,
          json.dumps(channels), json.dumps(capabilities), json.dumps(mcp_tools)))
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────────────────────
# INIT BUS
# ─────────────────────────────────────────────────────────────

def cmd_init_bus():
    """
    Creates agent_bus and managed_agent_registry tables in vapi_store.db.
    Registers the 26 existing fleet agents as FLEET type.
    Phase 177: adds agents #23-26 + maturity channel publish.
    """
    conn = get_db()
    conn.executescript(BUS_SCHEMA)
    conn.commit()

    # Register existing fleet agents as FLEET type (read-only on bus)
    fleet_agents = [
        ("AGENT-15", "SeparationRatioMonitorAgent",
            ["separation"], ["poll_ratio"], ["vapi_separation_analysis"]),
        ("AGENT-16", "TournamentActivationChainAgent",
            ["alert", "enrollment"], ["tournament_gate"], []),
        ("AGENT-20", "EnrollmentAutoGuidanceAgent",
            ["enrollment"], ["enrollment_guidance"], ["vapi_session_start_protocol"]),
        ("AGENT-21", "FleetConsensusSnapshotAgent",
            ["sweep", "wiki"], ["pof_snapshot"], ["vapi_agent_registry"]),
        ("AGENT-22", "BiometricPrivacyComplianceAgent",
            ["alert"], ["privacy_compliance"], ["vapi_privacy_compliance"]),
        # Phase 173-177 agents
        ("AGENT-23", "SeparationRatioRecoveryAgent",
            ["separation", "alert"], ["trend_velocity", "recovery_action"],
            ["vapi_separation_analysis"]),
        ("AGENT-24", "AgeWeightedRatioPersistenceAgent",
            ["separation"], ["temporal_drift_index", "age_weighting"],
            ["vapi_separation_analysis"]),
        ("AGENT-25", "PoACChainIntegrityMonitor",
            ["alert"], ["chain_integrity_audit"],
            ["vapi_corpus_integrity"]),
        ("AGENT-26", "ProtocolMaturityScoringAgent",
            ["maturity", "alert"], ["maturity_score", "maturity_tier"],
            ["vapi_session_start_protocol", "vapi_agent_registry"]),
    ]

    for agent_id, name, channels, caps, tools in fleet_agents:
        conn.execute("""
            INSERT INTO managed_agent_registry
            (agent_id, agent_name, agent_type, status, subscribed_channels,
             capabilities, mcp_tools)
            VALUES (?, ?, 'FLEET', 'ONLINE', ?, ?, ?)
            ON CONFLICT(agent_id) DO NOTHING
        """, (agent_id, name, json.dumps(channels),
              json.dumps(caps), json.dumps(tools)))

    # Register managed agents as MANAGED type (initially OFFLINE)
    for key, ma in MANAGED_AGENTS.items():
        conn.execute("""
            INSERT INTO managed_agent_registry
            (agent_id, agent_name, agent_type, status,
             subscribed_channels, capabilities, mcp_tools)
            VALUES (?, ?, 'MANAGED', 'OFFLINE', ?, ?, ?)
            ON CONFLICT(agent_id) DO NOTHING
        """, (ma["id"], ma["name"],
              json.dumps([ma["channel"], "alert", "separation", "maturity"]),
              json.dumps(["human_coordination", "knowledge_query"]),
              json.dumps(["vapi_session_start_protocol", "vapi_query_what_if",
                          "vapi_separation_analysis", "vapi_corpus_integrity"])))

    conn.commit()
    conn.close()

    phase  = detect_phase()
    ratio  = live_ratio()
    tdi    = live_tdi()
    tdi_dir = live_tdi_direction()
    mat    = live_maturity()
    mat_score = mat["maturity_score"] if mat else None
    mat_tier  = mat["maturity_tier"]  if mat else "UNKNOWN"
    recovery  = live_recovery()

    # Publish initial state to bus for managed agents to read on launch
    bus_publish("SYSTEM", "separation",
                {"ratio": ratio, "gate": FROZEN["separation_gate"],
                 "gap": round(FROZEN["separation_gate"] - (ratio or 0), 3),
                 "phase": phase,
                 "tdi": tdi, "tdi_direction": tdi_dir,
                 "recovery_action": recovery,
                 "message": "Bus initialized — current separation state from Agents 15/23/24"},
                phase=phase)

    bus_publish("SYSTEM", "enrollment",
                {"enrollment_min_sessions": FROZEN["enrollment_min_sessions"],
                 "defensibility_required": FROZEN["defensibility_required"],
                 "message": "Enrollment quality gate: count AND defensible=True required (Phase 157 target)"},
                phase=phase)

    # Phase 177: publish maturity state on init
    bus_publish("SYSTEM", "maturity",
                {"maturity_score": mat_score,
                 "maturity_tier": mat_tier,
                 "phase": phase,
                 "message": f"Bus initialized — protocol maturity tier={mat_tier} "
                             f"(Agent 26 ProtocolMaturityScoringAgent)"},
                phase=phase)

    print(f"[INIT_BUS] P2P Knowledge Bus initialized (Phase 177)")
    print(f"  Schema: agent_bus + managed_agent_registry in {DB_PATH}")
    print(f"  Fleet agents registered: {len(fleet_agents)}")
    print(f"  Managed agents registered (OFFLINE): {len(MANAGED_AGENTS)}")
    print(f"  Initial state: ratio={ratio}, tdi_direction={tdi_dir}, "
          f"maturity_tier={mat_tier}, recovery={recovery}")
    print(f"\nChannels ({len(BUS_CHANNELS)}): {', '.join(BUS_CHANNELS.keys())}")

# ─────────────────────────────────────────────────────────────
# MANAGED AGENT DEFINITIONS
# These are the system prompts + tool configurations for each
# managed agent. They are VAPI-aware via the MCP server connection.
# Phase 177: all three prompts updated with Agents #23-26 signals.
# ─────────────────────────────────────────────────────────────

def get_agent_A_definition(phase: int, ratio: Optional[float]) -> dict:
    """
    EnrollmentCoordinatorAgent (MA-001)
    Closes the gap between Agent 20's guidance and actual human action.
    Phase 177: augmented with TDI + age weighting + P1_RE_ENROLLMENT urgency.
    """
    gap = round(FROZEN["separation_gate"] - (ratio or 0), 3) if ratio else "unknown"
    tdi_dir  = live_tdi_direction()
    recovery = live_recovery()

    return {
        "id":   MANAGED_AGENTS["A"]["id"],
        "name": MANAGED_AGENTS["A"]["name"],
        "system_prompt": f"""You are the VAPI EnrollmentCoordinatorAgent (MA-001).

You work at the interface between VAPI's autonomous 26-agent fleet and
the human players who need to complete biometric calibration sessions.

CURRENT PROTOCOL STATE (Phase {phase}):
- Separation ratio: {ratio} (gate: {FROZEN['separation_gate']}, gap: {gap})
- Enrollment quality gate: sessions ≥ {FROZEN['enrollment_min_sessions']} AND defensible=True
- Mixed_biometric_probe: 4 segments × 30s, activates all 13 L4 features
- Temporal drift: {tdi_dir} (Agent 24 AgeWeightedRatioPersistenceAgent signal)
- Recovery action: {recovery} (Agent 23 SeparationRatioRecoveryAgent signal)

CRITICAL — P1 TEMPORAL NON-STATIONARITY (2026-04-05):
Agent 23 has detected a converging-downward trend: N=11→1.261, N=14→0.789, N=20→0.569.
Root cause: P1 intra-player variance from sessions captured across different days.
P1's old sessions cluster near P2's centroid; new sessions cluster near P3's centroid.
Recovery action: P1_RE_ENROLLMENT — P1 needs complete biometric re-enrollment under
controlled conditions to establish a stable centroid.

WHAT THIS MEANS FOR YOUR ROLE:
If recovery_action == "P1_RE_ENROLLMENT":
  1. Schedule P1 for a dedicated 60-minute re-enrollment session
  2. Require 6+ mixed_biometric_probe sessions in a single controlled sitting
  3. Same physical setup: same desk, same grip, same game state (pre-game warmup)
  4. Publish session cluster to enrollment channel with "re_enrollment": true
  5. Do NOT average with old sessions — Agent 23's age weighting will downweight them

If recovery_action == "AGE_WEIGHTING":
  1. Sessions are being collected but old sessions skew the ratio
  2. Normal pace is sufficient — time-based weighting handles the decay
  3. Report to enrollment channel that weighting mitigation is active

AGE WEIGHTING CONTEXT (Agent 24 AgeWeightedRatioPersistenceAgent):
temporal_drift_index (TDI) = raw_ratio - age_weighted_ratio
- TDI > 0.05 → P1_NONSTATIONARITY (old sessions inflating ratio estimate)
- TDI < -0.05 → IMPROVING (new sessions produce stronger separation)
- |TDI| ≤ 0.05 → STABLE (biometrically stationary player)
Current TDI direction: {tdi_dir}

YOUR ROLE:
1. Read the enrollment channel of the P2P agent bus to learn what Agent 20 recommends
2. Translate Agent 20's urgency levels (HIGH/MEDIUM/LOW) into direct player communication
3. Schedule mixed_biometric_probe sessions for players below defensibility threshold
4. Report completion back to the bus so Agent 20 and Agent 16 can update state

WHAT YOU NEVER DO:
- Access raw biometric data (BP-007 — derived signals only)
- Modify the enrollment_min_sessions threshold (FROZEN)
- Trigger enrollment_complete manually — only the fleet can do this
- Share player identity with any external system
- Contact players about anything other than session scheduling

TOOLS AVAILABLE:
- vapi_session_start_protocol(domain="calibration") → current enrollment state
- vapi_corpus_integrity() → session counts per player
- vapi_separation_analysis() → current ratio and gap
- bus_publish(channel="enrollment", payload={{...}}) → signal fleet of completion

When a player completes their sessions:
  Publish to enrollment channel:
  {{"event": "sessions_completed", "player_id": "<hashed>",
    "count": N, "defensible": true/false, "probe_type": "mixed_biometric",
    "re_enrollment": true/false, "tdi_direction": "{tdi_dir}"}}

The fleet agents (Agent 20, Agent 16) will read this and update their state.

COMMUNICATION STYLE:
- Clear, non-technical for players
- Precise about what is needed (specific probe type, duration, setup)
- Never oversell the credential — be honest about testnet status
- Sessions take 2 minutes. Mixed_biometric_probe: 4 segments × 30 seconds each.
- For P1_RE_ENROLLMENT: emphasize same-day, same-setup requirement

INVARIANTS YOU ENFORCE:
- auto_activate_on_breakthrough = False PERMANENT (never suggest self-activation)
- Separation ratio is not a player metric — don't share individual ratios
- All session coordination is voluntary and consent-based""",

        "mcp_tools": [
            "vapi_session_start_protocol",
            "vapi_corpus_integrity",
            "vapi_separation_analysis",
            "vapi_query_what_if",
        ],

        "bus_subscriptions": ["enrollment", "separation", "maturity", "alert"],
        "bus_publishes_to":  ["enrollment", "alert"],

        "initial_bus_read": True,  # reads bus state on launch
    }


def get_agent_B_definition(phase: int, ratio: Optional[float]) -> dict:
    """
    CohortDefensibilityAgent (MA-002)
    Monitors separation_defensibility_log and coordinates remediation.
    Phase 177: adds P1_RE_ENROLLMENT signal + persona break candidate detection.
    """
    tdi_dir  = live_tdi_direction()
    recovery = live_recovery()

    return {
        "id":   MANAGED_AGENTS["B"]["id"],
        "name": MANAGED_AGENTS["B"]["name"],
        "system_prompt": f"""You are the VAPI CohortDefensibilityAgent (MA-002).

You are the guardian of the biometric quality gate — the Phase 157 fix for
the W1 enrollment count-gate spoofing vulnerability.

CONTEXT:
The current protocol has a known W1 vulnerability: enrollment_complete fires
when session COUNT ≥ {FROZEN['enrollment_min_sessions']}, without checking that
those sessions are biometrically defensible. A player could complete 10
low-quality sessions in non-standard conditions and trigger the activation chain.

Your role is to enforce the dual-condition gate at the coordination layer:
  BOTH: session_count ≥ {FROZEN['enrollment_min_sessions']}
  AND:  defensible = True from separation_defensibility_log

CURRENT STATE (Phase {phase}):
- Separation ratio: {ratio} (gate: {FROZEN['separation_gate']})
- TDI direction: {tdi_dir} (Agent 24 signal)
- Recovery action: {recovery} (Agent 23 signal)
- defensibility_required = {FROZEN['defensibility_required']} (FROZEN)

ROOT CAUSE ANALYSIS (Phase 173-175 agents):
The current ratio is below gate due to P1 temporal non-stationarity.
P1's biometric centroid has drifted across capture days — old sessions cluster
near P2, new sessions cluster near P3. This is a PERSONA BREAK scenario.

PERSONA BREAK INDICATORS (watch for these in separation_defensibility_log):
1. P1's intra-player variance > 2.0 Mahalanobis (Phase 143: P1 mean=2.963)
2. LOO classification < 30% for P1 (below random chance for 3 classes)
3. TDI > 0.05 (old sessions inflate the ratio estimate)
4. recovery_action == "P1_RE_ENROLLMENT" from Agent 23

When you detect a persona break for a player:
  Publish to defensibility channel:
  {{"event": "persona_break_detected",
    "player_hash": "<keccak256>",
    "indicator": "intra_player_variance > 2.0",
    "recommended_action": "re_enrollment",
    "session_staleness_days": N,
    "tdi_direction": "{tdi_dir}"}}

YOUR WORKFLOW:
1. Query separation_defensibility_log via vapi_separation_analysis()
2. Identify players with count ≥ {FROZEN['enrollment_min_sessions']} but defensible=False
3. Distinguish: (a) insufficient sessions vs (b) persona break (existing sessions invalid)
4. For persona break: flag for re-enrollment rather than more sessions
5. Publish remediation plan to defensibility channel
6. Coordinate with EnrollmentCoordinatorAgent (MA-001) via bus

DEFENSIBILITY CRITERIA (from separation_defensibility_log):
A player's sessions are defensible when:
- N ≥ {FROZEN['enrollment_min_sessions']} sessions with mixed_biometric_probe
- touch_position_variance > 0 (touchpad contacted during sessions)
- All 13 L4 features have non-zero variance across sessions
- Mahalanobis distance from enrolled centroid < L4 anomaly threshold (7.009)
- Intra-player variance consistent (no persona break)

WHAT YOU PUBLISH TO BUS (defensibility channel):
{{"player_hash": "<keccak256>",
  "count": N,
  "defensible": true/false,
  "blocking_features": ["feature_name"],
  "recommended_probe": "mixed_biometric_probe",
  "sessions_remaining": N,
  "persona_break": true/false,
  "tdi_direction": "{tdi_dir}",
  "message": "human-readable remediation step"}}

WHAT YOU NEVER DO:
- Manually mark defensible=True without actual session measurement
- Access individual biometric feature values (only aggregate defensibility score)
- Bypass the fleet's enrollment_complete gate
- Lower the defensibility threshold

FLEET COMMUNICATION:
When a player achieves defensible=True AND count ≥ {FROZEN['enrollment_min_sessions']}:
  Publish BOTH conditions to enrollment channel.
  Agent 20 (EnrollmentAutoGuidanceAgent) reads the bus and updates its
  overall_ready signal. Agent 16 (TournamentActivationChainAgent) then
  evaluates whether to fire the activation chain.
  auto_activate_on_breakthrough = False PERMANENT — operator always confirms.""",

        "mcp_tools": [
            "vapi_separation_analysis",
            "vapi_session_start_protocol",
            "vapi_corpus_integrity",
            "vapi_validate_proposal",
        ],

        "bus_subscriptions": ["defensibility", "enrollment", "separation", "maturity", "alert"],
        "bus_publishes_to":  ["defensibility", "enrollment", "alert"],

        "initial_bus_read": True,
    }


def get_agent_C_definition(phase: int, ratio: Optional[float]) -> dict:
    """
    OperatorOnboardingAgent (MA-003)
    Guides prospective operators through VAPISwarmOperatorGate registration.
    Phase 177: adds maturity_score ALPHA context + isChainIntegrous() W2 framing.
    """
    runbook  = read(RUNBOOK)[:2000] if RUNBOOK.exists() else "(runbook not found at docs/operator-onboarding-runbook.md)"
    mat      = live_maturity()
    mat_score = mat["maturity_score"] if mat else None
    mat_tier  = mat["maturity_tier"]  if mat else "UNKNOWN"
    integrity = live_integrity()

    return {
        "id":   MANAGED_AGENTS["C"]["id"],
        "name": MANAGED_AGENTS["C"]["name"],
        "system_prompt": f"""You are the VAPI OperatorOnboardingAgent (MA-003).

You guide prospective tournament operators through VAPI operator registration.
This directly unblocks ioSwarm live node activation — currently at 0 nodes
against a requirement of ≥ 3 distinct stakers for VAPISwarmOperatorGate.sol.

CURRENT PROTOCOL STATE (Phase {phase}):
- ioSwarm: emulator_only — 0 live nodes registered
- VAPISwarmOperatorGate.sol: deployed, pending operator staking
- Wallet funding needed: ~0.05 IOTX for deploy tx
- BLOCK_QUORUM: 0.67 (requires ≥ 3 distinct operators for anti-whale protection)
- MINT_QUORUM: 0.80 (fail-CLOSED — VHP mint blocked without quorum)
- Operator stake: 10,000 VAPI minimum in VAPIOperatorRegistry.sol
- Slash mechanism: 50% burned / 50% to claimant

PROTOCOL MATURITY STATUS (Phase 177 ProtocolMaturityScoringAgent):
- maturity_score: {mat_score} | tier: {mat_tier}
- ALPHA tier (<0.50) is expected — separation ratio is still below gate
- Target for BETA: maturity_score ≥ 0.50 (requires separation_ratio > 0.70)
- PRODUCTION_CANDIDATE (≥0.85): requires separation_ratio > 1.0 + all gates met
- The maturity_score is designed as a trustworthiness signal for DePIN marketplace

CHAIN INTEGRITY STATUS (Phase 176 PoACChainIntegrityMonitor):
- Latest integrity_score: {integrity}
- integrity_score = valid_links / total_records (1.0 = fully intact SHA-256 chain)
- W2 opportunity: isChainIntegrous() as a third composable primitive alongside
  isFullyEligible() and isRecorded() — creates a triple-primitive tournament gate
- Operators can use this primitive in their smart contract logic

WHAT TO TELL PROSPECTIVE OPERATORS ABOUT MATURITY SCORE:
"The protocol maturity score is a 0.0-1.0 signal that synthesizes 6 sub-metrics
into a single composable trustworthiness indicator. When maturity_score ≥ 0.85,
the protocol emits PRODUCTION_CANDIDATE status — designed as the gateway condition
for DePIN data marketplace listing. Your ioSwarm node contributes to this score
via the agent_calibration_component."

ONBOARDING SEQUENCE:
1. Explain what operators do (run adjudication nodes, earn staking rewards)
2. Check their technical readiness (Python, bridge, IoTeX wallet)
3. Walk them through VAPIOperatorRegistry.sol staking
4. Guide wallet funding (IOTX testnet faucet if needed)
5. Verify ioID device registration
6. Run the bootstrap sequence (from operator-onboarding-runbook.md)
7. Publish registration event to operator bus channel
8. Confirm node appears in ioSwarm emulator registry

RUNBOOK EXCERPT:
{runbook}

WHAT YOU QUERY:
- vapi_corpus_integrity() → see current ioSwarm node count
- vapi_session_start_protocol(domain="general") → full protocol state
- vapi_agent_registry() → confirm fleet is healthy before onboarding

WHAT YOU PUBLISH (operator channel):
{{"event": "operator_registered",
  "operator_address": "0x...",
  "stake_amount": 10000,
  "node_type": "adjudication",
  "ioswarm_registered": true/false,
  "maturity_tier": "{mat_tier}",
  "phase": {phase}}}

The fleet agents (ioSwarm coordinators, Agents 13-16) read the operator
channel and update their quorum calculations when new operators register.

ECONOMIC CLARITY (be honest with candidates):
- Testnet only — no real economic value yet
- TGE blocked until separation_ratio ≥ {FROZEN['separation_gate']} + N≥100 adjudications
- VHPs are testnet credentials — not production tournament eligibility yet
- ioSwarm rewards are designed; not active until mainnet
- maturity_tier={mat_tier} means the protocol is in active development,
  not yet production-ready (PRODUCTION_CANDIDATE requires maturity_score≥0.85)

INVARIANTS:
- auto_activate_on_breakthrough = False PERMANENT
- Operator stakes are slashable — explain the slash mechanism clearly
- Min 3 distinct staker addresses (WIF-001 anti-homogeneity protection)
- 1.5× stake cap per operator (whale capture prevention)
- Never promise token price or TGE timing""",

        "mcp_tools": [
            "vapi_corpus_integrity",
            "vapi_session_start_protocol",
            "vapi_agent_registry",
            "vapi_knowledge_query",
        ],

        "bus_subscriptions": ["operator", "alert", "wiki", "maturity"],
        "bus_publishes_to":  ["operator", "alert"],

        "initial_bus_read": True,
    }

# ─────────────────────────────────────────────────────────────
# LAUNCH — runs a managed agent with Anthropic SDK
# ─────────────────────────────────────────────────────────────

def cmd_launch(agent_key: str):
    """
    Launches a managed agent. Requires ANTHROPIC_API_KEY.
    Reads the bus on launch to get current VAPI state.
    Runs an initial protocol assessment and publishes its findings.
    """
    import anthropic

    if agent_key not in MANAGED_AGENTS:
        print(f"ERROR: Agent key must be one of: {list(MANAGED_AGENTS.keys())}")
        return

    ma     = MANAGED_AGENTS[agent_key]
    phase  = detect_phase()
    ratio  = live_ratio()
    client = anthropic.Anthropic()

    defs = {
        "A": get_agent_A_definition,
        "B": get_agent_B_definition,
        "C": get_agent_C_definition,
    }
    defn = defs[agent_key](phase, ratio)

    print(f"\n[LAUNCH] {defn['name']} ({defn['id']})")
    print(f"  Phase: {phase} | Ratio: {ratio} | Gate: {FROZEN['separation_gate']}")

    # Register as ONLINE on the bus
    heartbeat(
        agent_id   = defn["id"],
        agent_name = defn["name"],
        agent_type = "MANAGED",
        channels   = defn["bus_subscriptions"],
        capabilities = ["human_coordination", "knowledge_synthesis"],
        mcp_tools  = defn["mcp_tools"],
    )

    # Read current bus state for this agent's channels
    bus_context = []
    for channel in defn["bus_subscriptions"]:
        messages = bus_read(defn["id"], channel, limit=5)
        if messages:
            bus_context.append(
                f"Channel '{channel}' ({len(messages)} messages):\n" +
                "\n".join(f"  [{m['from_agent']}] {m['payload'][:200]}" for m in messages)
            )

    bus_context_str = "\n\n".join(bus_context) if bus_context else "(No messages yet — bus is fresh)"

    mat = live_maturity()
    mat_info = f"maturity_score={mat['maturity_score']} tier={mat['maturity_tier']}" if mat else "maturity=UNKNOWN"

    # Initial assessment call
    initial_prompt = f"""You have just come online as {defn['name']}.

Current P2P bus state (messages you haven't read yet):
{bus_context_str}

Current VAPI protocol state (Phase {phase}):
- Separation ratio: {ratio} (gate: {FROZEN['separation_gate']},
  gap: {round(FROZEN["separation_gate"] - (ratio or 0), 3)})
- TDI direction: {live_tdi_direction()}
- Recovery action: {live_recovery()}
- Protocol maturity: {mat_info}
- Chain integrity: {live_integrity()}
- ioSwarm live nodes: {FROZEN['ioswarm_live_nodes']}
- dry_run: {FROZEN['dry_run']}
- auto_activate: {FROZEN['auto_activate']} PERMANENT

Perform your initial protocol assessment:
1. What is the current state relevant to your role?
2. What is your immediate priority action?
3. What will you publish to the bus?

Be precise and concise. Reference invariants correctly."""

    response = client.messages.create(
        model      = "claude-opus-4-6",
        max_tokens = 800,
        system     = defn["system_prompt"],
        messages   = [{"role": "user", "content": initial_prompt}],
    )

    assessment = response.content[0].text
    print(f"\n[{defn['name']}] Initial Assessment:\n{assessment}")

    # Publish assessment to bus
    bus_publish(
        from_agent = defn["id"],
        channel    = defn["bus_publishes_to"][0],
        payload    = {
            "event":      "agent_online",
            "assessment": assessment[:400],
            "phase":      phase,
            "ratio":      ratio,
        },
        msg_type = "PUBLISH",
        phase    = phase,
    )

    print(f"\n[BUS] {defn['name']} published 'agent_online' to {defn['bus_publishes_to'][0]} channel")
    print(f"  Fleet agents (Agent 20, Agent 16) will read this on their next poll.")

# ─────────────────────────────────────────────────────────────
# BUS STATUS — shows who is active and message counts
# ─────────────────────────────────────────────────────────────

def cmd_bus_status():
    """Shows the current P2P bus state — all agents, channels, message counts."""
    print("\n[BUS STATUS] VAPI P2P Knowledge Bus (Phase 177)")
    print("=" * 60)

    # Agent registry
    agents = db_query(
        "SELECT * FROM managed_agent_registry ORDER BY agent_type, agent_id"
    )
    if agents:
        print("\nAgent Registry:")
        print(f"  {'ID':<12} {'Name':<38} {'Type':<8} {'Status'}")
        print(f"  {'-'*12} {'-'*38} {'-'*8} {'-'*8}")
        for a in agents:
            print(f"  {a['agent_id']:<12} {a['agent_name']:<38} "
                  f"{a['agent_type']:<8} {a['status']}")
    else:
        print("\n  No agents registered. Run: python vapi_managed_agents.py init_bus")

    # Message counts per channel
    print("\nChannel Message Counts (active, not expired):")
    for channel, desc in BUS_CHANNELS.items():
        rows = db_query(
            "SELECT COUNT(*) as n FROM agent_bus WHERE channel=? AND expires_at > datetime('now','utc')",
            (channel,)
        )
        n = rows[0]["n"] if rows else 0
        print(f"  {channel:<15} {n:>3} messages  {desc[:40]}")

    # Recent messages
    recent = db_query(
        "SELECT from_agent, channel, message_type, payload, ts FROM agent_bus "
        "ORDER BY ts DESC LIMIT 5"
    )
    if recent:
        print("\nRecent Messages (last 5):")
        for m in recent:
            payload_preview = m["payload"][:60].replace("\n", " ")
            print(f"  [{m['ts'][:16]}] {m['from_agent']:<12} -> {m['channel']:<15} {payload_preview}")

    # Separation ratio + maturity
    ratio  = live_ratio()
    gate   = FROZEN["separation_gate"]
    tdi_d  = live_tdi_direction()
    tdi_v  = live_tdi()
    rec    = live_recovery()
    mat    = live_maturity()
    integ  = live_integrity()

    print(f"\nSeparation Ratio:  {ratio} (gate: {gate}) — "
          f"{'ABOVE GATE' if ratio and ratio >= gate else 'BELOW GATE — TOURNAMENT BLOCKER'}")
    print(f"TDI Direction:     {tdi_d} | TDI value: {tdi_v}")
    print(f"Recovery Action:   {rec}")
    print(f"Chain Integrity:   {integ}")
    if mat:
        print(f"Maturity Score:    {mat['maturity_score']} ({mat['maturity_tier']})")

# ─────────────────────────────────────────────────────────────
# BRIEF — generates Claude Code brief for managed agent
# Local execution mode — no Anthropic API needed
# ─────────────────────────────────────────────────────────────

def cmd_brief(agent_key: str, phase: int):
    """
    Generates a Claude Code brief for a managed agent.
    Claude Code reads the brief and acts as the agent.
    No managed infra required — local execution mode.
    """
    if agent_key not in MANAGED_AGENTS:
        print(f"ERROR: Agent key must be: {list(MANAGED_AGENTS.keys())}")
        return

    ma    = MANAGED_AGENTS[agent_key]
    ratio = live_ratio()
    defs  = {
        "A": get_agent_A_definition,
        "B": get_agent_B_definition,
        "C": get_agent_C_definition,
    }
    defn = defs[agent_key](phase, ratio)

    # Read bus state
    bus_context = []
    for channel in defn["bus_subscriptions"]:
        messages = bus_read(defn["id"], channel, limit=3)
        for m in messages:
            bus_context.append(
                f"Channel '{channel}' from {m['from_agent']}: "
                f"{json.loads(m['payload']).get('message', str(m['payload'])[:100])}"
            )

    brief_path = WIKI / "briefs" / f"brief_{ma['id']}_{phase}.md"
    brief_path.parent.mkdir(parents=True, exist_ok=True)

    mat    = live_maturity()
    mat_info = f"maturity_score={mat['maturity_score']} tier={mat['maturity_tier']}" if mat else "maturity=UNKNOWN"

    brief = f"""# Managed Agent Brief: {defn['name']}
Agent ID: {defn['id']} | Phase {phase} | {datetime.now(timezone.utc).isoformat()}

## INSTRUCTION TO CLAUDE CODE
You are acting as {defn['name']} in local execution mode.
Read the system prompt below and perform the initial assessment.
Then use the bus tools below to publish your findings.

## System Prompt
{defn['system_prompt']}

## Current Bus State
{chr(10).join(bus_context) if bus_context else '(bus is empty — first launch)'}

## Phase 177 State Summary
- Separation ratio: {ratio} | TDI: {live_tdi_direction()} | Recovery: {live_recovery()}
- {mat_info}
- Chain integrity: {live_integrity()}
- Agent fleet: {FROZEN['agent_count']} agents (bridge: {FROZEN['bridge_baseline']}, sdk: {FROZEN['sdk_baseline']})

## Your Tasks
1. Read the bus context above
2. Assess current protocol state using vapi_session_start_protocol()
3. Identify your top priority action
4. Publish to the bus: python vapi_managed_agents.py bus_publish {defn['bus_publishes_to'][0]} '<json>'
5. Update wiki if relevant: python vapi_wiki_engine.py agent_feed

## Bus Publish Command
python vapi_managed_agents.py bus_publish {defn['bus_publishes_to'][0]} '{{
  "event": "agent_assessment",
  "agent": "{defn['id']}",
  "priority_action": "<your priority>",
  "phase": {phase},
  "tdi_direction": "{live_tdi_direction()}",
  "recovery_action": "{live_recovery()}"
}}'
"""

    brief_path.write_text(brief, encoding="utf-8")
    print(f"[BRIEF] {brief_path}")
    print(f"  Claude Code reads this and acts as {defn['name']}")
    print(f"  No Anthropic API required — local execution mode")

# ─────────────────────────────────────────────────────────────
# BUS PUBLISH (CLI) — publish a message to the bus
# ─────────────────────────────────────────────────────────────

def cmd_bus_publish(channel: str, payload_str: str, from_agent: str = "OPERATOR"):
    if channel not in BUS_CHANNELS:
        print(f"ERROR: Channel must be one of: {list(BUS_CHANNELS.keys())}")
        return
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        payload = {"message": payload_str}

    msg_id = bus_publish(from_agent, channel, payload, phase=detect_phase())
    print(f"[BUS:PUBLISH] msg_id={msg_id} → {channel}")

# ─────────────────────────────────────────────────────────────
# GENERATE PROMPT — complete Claude Code integration prompt
# ─────────────────────────────────────────────────────────────

def cmd_generate_prompt():
    """Generates the Claude Code integration prompt for all three managed agents."""
    phase = detect_phase()
    ratio = live_ratio()

    prompt = f"""# VAPI Managed Agents — Claude Code Integration (Phase 177)
# Three managed agents + P2P bus connecting to the 26-agent fleet
# Phase {phase} | Ratio: {ratio} | Gate: {FROZEN['separation_gate']}
# Bridge: {FROZEN['bridge_baseline']} | SDK: {FROZEN['sdk_baseline']} | Agents: {FROZEN['agent_count']}

```
Read VAPI-WORKFLOW.v2/VAPI_MEMORY.md to confirm Phase {phase} state.
Confirm vapi_managed_agents.py is in the project root.

STEP 1 — INIT BUS
python vapi_managed_agents.py init_bus

Creates agent_bus + managed_agent_registry tables in bridge/vapi_store.db.
Registers existing fleet agents (15, 16, 20, 21, 22, 23, 24, 25, 26) as FLEET type.
Registers MA-001, MA-002, MA-003 as MANAGED (OFFLINE).
Phase 177: maturity channel initialised on startup.

STEP 2 — VERIFY BUS STATE
python vapi_managed_agents.py bus_status

Confirm all 9 fleet agents show ONLINE.
Confirm 3 managed agents show OFFLINE (they haven't launched yet).
Confirm separation + maturity channels have initial state messages.

STEP 3 — LAUNCH ENROLLMENT COORDINATOR (MA-001)
# With Anthropic API (full managed mode):
python vapi_managed_agents.py launch A

# Without API (local Claude Code mode):
python vapi_managed_agents.py brief A {phase}
# Claude Code reads wiki/briefs/brief_MA-001_{phase}.md and acts as the agent

STEP 4 — LAUNCH COHORT DEFENSIBILITY (MA-002)
python vapi_managed_agents.py launch B
# or: python vapi_managed_agents.py brief B {phase}

STEP 5 — LAUNCH OPERATOR ONBOARDING (MA-003)
python vapi_managed_agents.py launch C
# or: python vapi_managed_agents.py brief C {phase}

STEP 6 — VERIFY P2P BUS ACTIVITY
python vapi_managed_agents.py bus_status

Confirm: all 3 managed agents now show ONLINE
Confirm: enrollment and defensibility channels have 'agent_online' messages
Confirm: fleet agents (20, 16) will read these on their next poll

STEP 7 — TEST CROSS-AGENT COMMUNICATION
# Simulate a player completing mixed_biometric_probe sessions
python vapi_managed_agents.py bus_publish enrollment '{{
  "event": "sessions_completed",
  "player_hash": "0xabc123",
  "count": 12,
  "defensible": true,
  "probe_type": "mixed_biometric_probe",
  "re_enrollment": false,
  "tdi_direction": "STABLE",
  "message": "Player completed 12 sessions with all 13 features active"
}}'

# Then check defensibility agent read it
python vapi_managed_agents.py bus_status

STEP 8 — WIRE WIKI ENGINE → BUS
After every wiki engine operation, publish to wiki channel:
python vapi_managed_agents.py bus_publish wiki '{{
  "event": "wiki_snapshot",
  "ratio": {ratio},
  "phase": {phase},
  "message": "wiki snapshot taken"
}}'

STEP 9 — ADD SKILL 16 TO VAPI_SKILLS.md
Add the skill block below to VAPI_SKILLS.md above Skill Proposal Template.

STEP 10 — COMMIT
git add vapi_managed_agents.py VAPI_SKILLS.md
git commit -m "Phase {phase}: Managed Agent Layer (Skill 16)
- MA-001 EnrollmentCoordinatorAgent + P1_RE_ENROLLMENT urgency
- MA-002 CohortDefensibilityAgent + persona break detection
- MA-003 OperatorOnboardingAgent + maturity_score framing
- P2P Knowledge Bus: 8 channels incl. maturity
- Fleet agents 15/16/20/21/22/23/24/25/26 on bus
- Phase 177: bridge={FROZEN['bridge_baseline']} sdk={FROZEN['sdk_baseline']} agents={FROZEN['agent_count']}"
```
"""

    prompt_path = ROOT / "VAPI_ManagedAgents_Claude_Code_Prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"[GENERATE_PROMPT] {prompt_path}")

# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

CMDS = {
    "init_bus":        "Create bus schema + register all 26+3 agents",
    "launch":          "Launch managed agent A|B|C (requires ANTHROPIC_API_KEY)",
    "brief":           "Generate local execution brief for A|B|C <phase>",
    "bus_status":      "Show agent registry + channel message counts + maturity",
    "bus_publish":     "Publish message: <channel> '<json>'",
    "generate_prompt": "Generate Claude Code integration prompt",
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("VAPI Managed Agents — P2P Knowledge Bus (Phase 177)\n")
        print(f"Fleet: {FROZEN['agent_count']} agents | Bridge: {FROZEN['bridge_baseline']} | SDK: {FROZEN['sdk_baseline']}\n")
        print("Commands:")
        for c, d in CMDS.items():
            print(f"  {c:<20} {d}")
        return

    cmd = sys.argv[1].lower()

    if cmd == "init_bus":
        cmd_init_bus()
    elif cmd == "launch":
        if len(sys.argv) < 3:
            print("Usage: python vapi_managed_agents.py launch A|B|C")
        else:
            cmd_launch(sys.argv[2].upper())
    elif cmd == "brief":
        if len(sys.argv) < 4:
            print("Usage: python vapi_managed_agents.py brief A|B|C <phase>")
        else:
            cmd_brief(sys.argv[2].upper(), int(sys.argv[3]))
    elif cmd == "bus_status":
        cmd_bus_status()
    elif cmd == "bus_publish":
        if len(sys.argv) < 4:
            print("Usage: python vapi_managed_agents.py bus_publish <channel> '<json>'")
        else:
            from_agent = sys.argv[4] if len(sys.argv) > 4 else "OPERATOR"
            cmd_bus_publish(sys.argv[2], sys.argv[3], from_agent)
    elif cmd == "generate_prompt":
        cmd_generate_prompt()
    else:
        print(f"Unknown command: {cmd}. Run --help")

if __name__ == "__main__":
    main()
