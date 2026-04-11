# VAPI FleetSignalCoherenceAgent — Claude Code Integration Prompt
# Phase 193 — Executes AFTER DataCuratorAgent (Phase 192) is complete
# Authority: FULL — Claude Code may extend any listed file if the
# extension is logically required and preserves all FROZEN invariants.
#
# Save to: VAPI-WORKFLOW.v2/VAPI_FSCA_BRIEF.md
# Then execute: /vapi coherence --init
# ============================================================

/vapi FLEET_SIGNAL_COHERENCE_PHASE_193

READ in this exact sequence before writing a single line of code:
  1. VAPI-WORKFLOW.v2/VAPI_MEMORY.md             — last 5 entries
  2. VAPI-WORKFLOW.v2/VAPI_AGENTS.md             — agents #23–35 (full fleet)
  3. VAPI-WORKFLOW.v2/VAPI_INVARIANTS.md         — all FROZEN values
  4. VAPI-WORKFLOW.v2/VAPI_WHAT_IF.md            — WIF-033 through WIF-035
  5. vapi_wiki_engine.py                         — FROZEN dict, WIKI_CONTRADICT
                                                   path, _locked_append(), log_op()
  6. vapi_managed_agents.py                      — BUS_CHANNELS, BUS_SCHEMA,
                                                   agent_bus table schema
  7. vapi_autoresearch.py                        — CLAUDE-EDITABLE ZONE functions
  8. vapi_eval_harness.py                        — MANDATORY_INVARIANTS (IMMUTABLE)
  9. bridge/vapi_bridge/store.py                 — existing table list for
                                                   schema(N, "table_name") pattern
  10. bridge/vapi_bridge/data_curator_agent.py   — Task 1 data_provenance_dag
                                                   (Phase 192, already complete)

FROZEN value guard — check before every file write:
  record_hash        = SHA-256(raw[:164])   NOT raw[:228]
  auto_activate      = False                PERMANENT — touching = P0 STOP
  separation_gate    = 0.70                 FROZEN
  vhp_expiry_days    = 90                   FROZEN
  epistemic_threshold = 0.65               FROZEN
  ceremony_beacon    = "#41723255"          FROZEN
  l4_anomaly         = 7.009               FROZEN
  l4_continuity      = 5.367              FROZEN

Do NOT proceed to implementation until all 10 files are read.

---
## IDENTITY

You are implementing the VAPI FleetSignalCoherenceAgent (Agent #36, Phase 193).

This agent is the first in the VAPI fleet whose PRIMARY OUTPUT is new
WHAT_IF corpus entries rather than operational signals. Every other agent
monitors a protocol domain. This one monitors the fleet itself — detecting
when agents are simultaneously correct in isolation but contradictory as
a set, and converting those contradictions into permanent protocol knowledge.

The architectural insight driving every decision in this brief:

  A 30-agent fleet with 8 bus channels and causal dependencies 9 phases
  deep produces emergent contradiction states that no single agent can
  detect because each agent only knows its own output. Contradictions are
  fleet-level phenomena. They require a fleet-level observer.

  The DataCuratorAgent (Phase 192, already complete) built the Provenance
  DAG that maps causal relationships between tables. FleetSignalCoherenceAgent
  uses that DAG to detect when the live signal topology violates the
  causal graph — when downstream agents report states that are inconsistent
  with what their upstream agents produced.

This agent closes the RSI loop at the fleet level: detected contradiction
→ wiki/contradictions.md → sync_what_if() promotion → WIF entry filed →
AutoResearch cycle scores against it → skill.md updated → ACIM verifies
invariants preserved. That is VAPI's genuine multi-agent RSI contribution.
It does not exist in any other gaming or DePIN protocol.

---
## SYSTEM STATE AT PHASE 193

```
Bridge:    2096  |  SDK: 374  |  Hardhat: 498
Agents:    35    |  Tools: #144  |  Contracts: 43 LIVE
DataCuratorAgent (Phase 192): COMPLETE
  — data_provenance_dag table: LIVE (Task 1)
  — corpus_entropy_log table: LIVE (Task 2)
  — data_readiness_certificate_log table: LIVE (Task 6)
  — session_contribution_weight_log table: LIVE (Task 7)
  — "curator" bus channel: ACTIVE
  — knowledge_server.py: vapi_corpus_entropy + vapi_data_readiness_certificate
    + vapi_provenance_chain MCP tools: LIVE

WIKI_CONTRADICT path: wiki/contradictions.md
  Already declared in vapi_wiki_engine.py line 112.
  File may or may not exist on disk — cmd_init() creates it if absent.
  FleetSignalCoherenceAgent writes to this path via _locked_append().

Tournament ratio: 0.569 (N=20, BLOCKER — gate=0.70 FROZEN)
P1 temporal non-stationarity: CONFIRMED
  tremor_peak_hz drift: -0.346/snapshot
  PersonaBreakDetectorAgent (#27): persona_break_detected=True for P1
  Re-enrollment status: PENDING (hardware action required)
```

---
## THE THREE COHERENCE FAILURE MODES

Implement detection for exactly these three modes. No others.
Each has a precisely defined detection logic, evidence set, and severity.

---
### MODE 1 — CONTRADICTION

**Definition**: Two agents report states that are logically incompatible.
One of them is operating on stale data or has a computation error.
The contradiction is deterministic — not probabilistic, not ambiguous.

**Detection pattern**: For each CONTRADICTION rule, query two or more
tables simultaneously. If the logical condition evaluates to True,
a contradiction exists.

**Contradiction rules to implement** (wire all of these):

```python
CONTRADICTION_RULES = {

    "TTL_COMMITTED_AT_MISMATCH": {
        # BiometricCredentialTTLAgent says expired=False
        # but committed_at_ts shows age > vhp_expiry_days (FROZEN=90)
        "query": """
            SELECT t.id, t.age_days, t.expired, t.ttl_days,
                   t.commitment_hash, t.checked_at_ts
            FROM biometric_credential_ttl_log t
            WHERE t.expired = 0
              AND t.age_days > ?
            ORDER BY t.created_at DESC LIMIT 1
        """,
        "params": lambda cfg: (cfg.biometric_credential_ttl_days,),
        "agents_involved": ["BiometricCredentialTTLAgent", "TournamentActivationChainAgent"],
        "severity": "HIGH",
        "explanation": (
            "TTL agent reports credential not expired but age_days exceeds "
            "vhp_expiry_days (FROZEN=90). TTL gate cannot be trusted. "
            "TournamentActivationChainAgent may pass ttl_gate incorrectly."
        ),
        "resolution": "Force BiometricCredentialTTLAgent recompute via trigger_ttl_recheck()",
    },

    "DEFENSIBILITY_N_MISMATCH": {
        # separation_defensibility_log says defensible=True
        # but n_per_player shows at least one player below min_n=10
        "query": """
            SELECT id, defensible, n_per_player_json, ratio
            FROM separation_defensibility_log
            WHERE defensible = 1
            ORDER BY created_at DESC LIMIT 1
        """,
        "params": lambda cfg: (),
        "post_check": lambda row: (
            # Parse n_per_player_json and check all >= 10
            any(v < 10 for v in json.loads(row["n_per_player_json"]).values())
            if row else False
        ),
        "agents_involved": ["SeparationRatioMonitorAgent", "EnrollmentAutoGuidanceAgent"],
        "severity": "CRITICAL",
        "explanation": (
            "defensibility_log reports defensible=True but n_per_player shows "
            "at least one player below min_n=10. This is a hard invariant violation — "
            "defensible=True requires ALL players >= min_n=10 AND ratio > 1.0. "
            "Tournament activation chain reads this and may incorrectly pass the gate."
        ),
        "resolution": "Recompute separation_defensibility_log via POST /agent/recompute-defensibility",
    },

    "CEREMONY_PARTICIPANT_MISMATCH": {
        # ceremony_audit_log shows participant_count < 3 for a circuit
        # but CeremonyAuditGate endpoint reports ceremony_gate_ok=True
        "query": """
            SELECT circuit_name, COUNT(DISTINCT participant_address) as n
            FROM ceremony_audit_log
            GROUP BY circuit_name
            HAVING n < 3
        """,
        "params": lambda cfg: (),
        "cross_check_endpoint": "GET /agent/ceremony-audit-status",
        "cross_check_key": "ceremony_gate_ok",
        "cross_check_expected": False,  # should be False if any circuit < 3
        "agents_involved": ["AttestationBoundRenewalAgent", "TournamentActivationChainAgent"],
        "severity": "HIGH",
        "explanation": (
            "ceremony_audit_log has circuit(s) with < 3 distinct participants "
            "(MIN_PARTICIPANTS=3 FROZEN), but ceremony-audit-status reports "
            "ceremony_gate_ok=True. This means the ceremony gate check is "
            "reading from a stale cache or incorrect query."
        ),
        "resolution": "Invalidate CeremonyAuditGate cache and force re-query from ceremony_audit_log",
    },

    "MATURITY_ELEVATION_READINESS_INVERSION": {
        # MaturityElevationGateAgent reports elevation_available=True
        # but DataReadinessCertificate reports certification_status=BLOCKED
        # on a blocking dimension — elevation cannot be available if data is blocked
        "query": """
            SELECT e.elevation_available, e.gap_to_target, e.current_tier,
                   r.certification_status, r.blocking_failures
            FROM maturity_elevation_log e
            CROSS JOIN data_readiness_certificate_log r
            WHERE e.elevation_available = 1
              AND r.certification_status = 'BLOCKED'
            ORDER BY e.created_at DESC, r.created_at DESC
            LIMIT 1
        """,
        "params": lambda cfg: (),
        "agents_involved": ["MaturityElevationGateAgent", "DataCuratorAgent"],
        "severity": "MEDIUM",
        "explanation": (
            "MaturityElevationGateAgent reports elevation_available=True (gap < 0.05 "
            "to next tier) while DataReadinessCertificate shows BLOCKED on a blocking "
            "dimension. Maturity elevation cannot be available if the data readiness "
            "gate has blocking failures. MaturityElevationGateAgent is reading from a "
            "stale protocol_maturity_log row that predates the blocking condition."
        ),
        "resolution": "Trigger MaturityElevationGateAgent recompute after DataCuratorAgent readiness cycle",
    },

    "RENEWAL_WITHOUT_ATTESTATION": {
        # biometric_renewal_log has a recent renewal entry
        # but re_enrollment_attestation_log has NO consumed token for that renewal
        # A renewal must be bound to an attestation — no attestation = unauthorized renewal
        "query": """
            SELECT r.new_commitment_hash, r.renewal_reason, r.triggered_by,
                   r.ttl_reset_at_ts,
                   a.id as attestation_id, a.used as attestation_used
            FROM biometric_renewal_log r
            LEFT JOIN re_enrollment_attestation_log a
              ON a.used = 1
             AND a.player_id = r.player_id
             AND ABS(a.expires_at - r.ttl_reset_at_ts) < 86400
            WHERE a.id IS NULL
              AND r.renewal_reason != 'MANUAL'
            ORDER BY r.created_at DESC LIMIT 5
        """,
        "params": lambda cfg: (),
        "agents_involved": ["BiometricRenewalFlow", "ReEnrollmentAttestationAgent",
                            "AttestationBoundRenewalAgent"],
        "severity": "CRITICAL",
        "explanation": (
            "biometric_renewal_log contains renewal(s) with no matching consumed "
            "attestation token in re_enrollment_attestation_log. Every non-manual "
            "renewal must be bound to a HMAC attestation token (WIF-032 W1). "
            "An unattested renewal bypasses the Phase 185 security gate entirely. "
            "This is the highest-severity contradiction the fleet can produce."
        ),
        "resolution": (
            "IMMEDIATE: Verify AttestationBoundRenewalAgent (#30) is correctly "
            "consuming tokens before renewals. Check chain.py attestedRenewCommit() "
            "anti-replay enforcement. File incident to alert channel."
        ),
    },

    "PERSONA_BREAK_ENROLLMENT_CONFLICT": {
        # PersonaBreakDetectorAgent reports persona_break_detected=True for P1
        # but EnrollmentAutoGuidanceAgent reports overall_ready=True
        # A player with a confirmed persona break cannot be enrollment-ready
        "query": """
            SELECT pb.player_id, pb.persona_break_detected, pb.loo_accuracy_trend,
                   ea.overall_ready, ea.sessions_needed_total
            FROM persona_break_log pb
            CROSS JOIN enrollment_auto_guidance_log ea
            WHERE pb.persona_break_detected = 1
              AND ea.overall_ready = 1
            ORDER BY pb.created_at DESC, ea.created_at DESC
            LIMIT 1
        """,
        "params": lambda cfg: (),
        "agents_involved": ["PersonaBreakDetectorAgent", "EnrollmentAutoGuidanceAgent"],
        "severity": "HIGH",
        "explanation": (
            "PersonaBreakDetectorAgent reports persona_break_detected=True for a player "
            "while EnrollmentAutoGuidanceAgent reports overall_ready=True. A confirmed "
            "persona break means the player's biometric centroid has migrated beyond "
            "re-enrollment viability with old-pattern sessions — enrollment cannot be "
            "complete. EnrollmentAutoGuidanceAgent is not reading PersonaBreakDetectorAgent "
            "output before evaluating overall_ready."
        ),
        "resolution": "EnrollmentAutoGuidanceAgent must gate overall_ready=True on persona_break_detected=False",
    },

    "SEPARATION_GATE_ACTIVATION_CONFLICT": {
        # TournamentActivationChainAgent reports any gate passing
        # while separation_ratio is below FROZEN gate (0.70)
        # The activation chain cannot proceed if separation is below gate
        "query": """
            SELECT t.gate_open_notified, t.last_ratio,
                   s.pooled_ratio
            FROM tournament_activation_chain_log t
            CROSS JOIN separation_ratio_snapshots s
            WHERE t.gate_open_notified = 1
              AND s.pooled_ratio < 0.70
            ORDER BY t.created_at DESC, s.created_at DESC
            LIMIT 1
        """,
        "params": lambda cfg: (),
        "agents_involved": ["TournamentActivationChainAgent", "SeparationRatioMonitorAgent"],
        "severity": "CRITICAL",
        "explanation": (
            "TournamentActivationChainAgent has gate_open_notified=True while "
            "separation_ratio_snapshots shows current ratio below the FROZEN gate (0.70). "
            "The activation chain notified of a gate open on a sub-gate ratio. "
            "This could permit unauthorized tournament activation. "
            "FROZEN: separation_gate=0.70 — this invariant cannot be relaxed."
        ),
        "resolution": (
            "IMMEDIATE: Invalidate the gate_open_notified entry. Verify "
            "SeparationRatioMonitorAgent poll interval did not miss a ratio "
            "update between activation chain evaluation and snapshot write."
        ),
    },
}
```

---
### MODE 2 — SIGNAL ORPHANING

**Definition**: An agent publishes a bus event that requires a downstream
agent to respond within an expected window. If no response appears within
`orphan_window_seconds`, the signal is orphaned — published but never acted on.

**Why this matters**: An orphaned signal means part of the fleet's causal
chain is silently broken. The upstream agent believes the signal was handled.
The downstream agent never received it or ignored it. No error is raised.
The system degrades silently.

**Orphan rules to implement**:

```python
ORPHAN_RULES = {

    "PERSONA_BREAK_UNATTESTED": {
        # PersonaBreakDetectorAgent fires persona_break_detected
        # ReEnrollmentAttestationAgent must issue HMAC token within window
        "trigger_table":   "persona_break_log",
        "trigger_column":  "persona_break_detected",
        "trigger_value":   1,
        "trigger_ts_col":  "created_at",
        "response_table":  "re_enrollment_attestation_log",
        "response_ts_col": "created_at",
        "join_column":     "player_id",
        "orphan_window_seconds": 3600,   # 1 hour — attestation should fire within poll cycle
        "trigger_agent":   "PersonaBreakDetectorAgent",
        "response_agent":  "ReEnrollmentAttestationAgent",
        "severity": "HIGH",
        "explanation": (
            "PersonaBreakDetectorAgent fired persona_break_detected=True more than "
            "1 hour ago but ReEnrollmentAttestationAgent has issued no HMAC token "
            "for this player. Either: (a) REAUTH_ATTESTATION_SECRET is missing from "
            "env (Agent #29 fail-closed would produce no token), or (b) Agent #29 "
            "is not subscribed to the 'defensibility' bus channel for this player_id, "
            "or (c) Agent #29 failed silently on HMAC computation."
        ),
        "resolution": "Check REAUTH_ATTESTATION_SECRET env var. Verify Agent #29 bus subscription.",
    },

    "MATURITY_ELEVATION_UNACKNOWLEDGED": {
        # MaturityElevationGateAgent fires elevation_available=True
        # MA-003 OperatorOnboardingAgent should acknowledge via operator channel
        # within its next poll cycle (600s = 10 min)
        "trigger_table":   "maturity_elevation_log",
        "trigger_column":  "elevation_available",
        "trigger_value":   1,
        "trigger_ts_col":  "created_at",
        "response_table":  "agent_bus",
        "response_filter": "channel = 'operator' AND from_agent = 'MA-003'",
        "orphan_window_seconds": 900,    # 15 min
        "trigger_agent":   "MaturityElevationGateAgent",
        "response_agent":  "MA-003 OperatorOnboardingAgent",
        "severity": "MEDIUM",
        "explanation": (
            "MaturityElevationGateAgent reported elevation_available=True but "
            "MA-003 OperatorOnboardingAgent has published nothing to the operator "
            "channel in the 15 minutes following the trigger. "
            "Operators are not being notified of protocol maturity progression."
        ),
        "resolution": "Verify MA-003 is subscribed to 'maturity' bus channel and polls elevation_log.",
    },

    "BIOMETRIC_EXPIRED_GATE_NOT_UPDATED": {
        # BiometricCredentialTTLAgent fires biometric_credential_expired event
        # TournamentActivationChainAgent must update its ttl_gate to False
        # The activation chain log should show a new row with ttl_gate=False
        "trigger_table":   "biometric_credential_ttl_log",
        "trigger_column":  "expired",
        "trigger_value":   1,
        "trigger_ts_col":  "created_at",
        "response_table":  "tournament_activation_chain_log",
        "response_filter": "ttl_gate = 0",
        "orphan_window_seconds": 7200,   # 2 hours — activation chain polls hourly
        "trigger_agent":   "BiometricCredentialTTLAgent",
        "response_agent":  "TournamentActivationChainAgent",
        "severity": "HIGH",
        "explanation": (
            "BiometricCredentialTTLAgent flagged credential as expired more than "
            "2 hours ago but tournament_activation_chain_log still shows no row "
            "with ttl_gate=False. The biometric_credential_expired bus event was "
            "either not consumed or TournamentActivationChainAgent did not recompute "
            "the activation chain after receiving it."
        ),
        "resolution": "Verify TournamentActivationChainAgent bus subscription to 'biometric_credential_expired'.",
    },

    "ERASURE_CERT_NOT_ANCHORED": {
        # DataCuratorAgent issued an erasure_certificate_log entry
        # on-chain anchoring (anchored=True) should happen within 1 poll cycle
        "trigger_table":   "erasure_certificate_log",
        "trigger_column":  "anchored",
        "trigger_value":   0,
        "trigger_ts_col":  "created_at",
        "response_table":  "erasure_certificate_log",
        "response_filter": "anchored = 1",  # same table — check if any later row anchored
        "orphan_window_seconds": 5400,      # 90 min — 3× DataCuratorAgent poll interval
        "trigger_agent":   "DataCuratorAgent",
        "response_agent":  "DataCuratorAgent (chain.py anchor_erasure_certificate)",
        "severity": "MEDIUM",
        "explanation": (
            "DataCuratorAgent generated an erasure certificate but did not anchor it "
            "to AdjudicationRegistry.sol within 90 minutes. Either the wallet has "
            "insufficient IOTX for the transaction, the bridge is in dry_run=True mode "
            "(which blocks on-chain calls), or the chain.py anchor call failed silently."
        ),
        "resolution": "Check wallet IOTX balance. Verify dry_run=False for on-chain anchoring. Check chain.py logs.",
    },

    "CORPUS_ENTROPY_WARNING_NO_AUTORESEARCH": {
        # DataCuratorAgent logs clustering_warning=True in corpus_entropy_log
        # AutoResearch should have filed a new cycle addressing corpus_entropy_health
        # If no cycle filed within 24 hours, the warning is orphaned
        "trigger_table":   "corpus_entropy_log",
        "trigger_column":  "clustering_warning",
        "trigger_value":   1,
        "trigger_ts_col":  "created_at",
        "response_path":   "vapi-autoresearch/experiments/log.jsonl",
        "response_key":    "priority",
        "response_value":  "corpus_entropy_health",
        "orphan_window_seconds": 86400,  # 24 hours
        "trigger_agent":   "DataCuratorAgent",
        "response_agent":  "vapi_autoresearch.py",
        "severity": "LOW",
        "explanation": (
            "DataCuratorAgent detected a corpus entropy CLUSTERING_WARNING "
            "more than 24 hours ago but no AutoResearch cycle with priority "
            "'corpus_entropy_health' has been run. The wiki engine is not "
            "triggering AutoResearch after entropy warnings."
        ),
        "resolution": "Run: python vapi_autoresearch.py --cycle 1 --priority corpus_entropy_health",
    },
}
```

---
### MODE 3 — CAUSAL INVERSION

**Definition**: Agent outputs are individually valid and recent, but the
causal ordering encoded in the DataCurator's Provenance DAG is violated —
a downstream artifact claims a state that contradicts what its upstream
nodes produced. The Provenance DAG is the ground truth for causal ordering.

**Detection pattern**: For each inversion rule, query `data_provenance_dag`
for the relevant node chain. Compare the state embedded in the downstream
node against what the upstream node produced. If they are causally inconsistent,
an inversion exists.

**Inversion rules to implement**:

```python
INVERSION_RULES = {

    "COMMITMENT_PREDATES_CONSENT": {
        # A SeparationRatioRegistry commitment node in the DAG
        # has a created_at timestamp BEFORE its parent consent_snapshot node
        # A ratio commitment cannot precede the consent that authorized it
        "dag_query": """
            SELECT child.node_id, child.node_type, child.created_at as commit_ts,
                   parent.node_type as parent_type, parent.created_at as consent_ts
            FROM data_provenance_dag child
            JOIN data_provenance_dag parent ON child.parent_node_id = parent.node_id
            WHERE child.node_type = 'COMMITMENT_HASH'
              AND parent.node_type = 'CONSENT_SNAPSHOT'
              AND child.created_at < parent.created_at
        """,
        "agents_involved": ["SeparationRatioRecoveryAgent", "BiometricPrivacyComplianceAgent"],
        "severity": "CRITICAL",
        "explanation": (
            "data_provenance_dag shows a COMMITMENT_HASH node with an earlier "
            "timestamp than its parent CONSENT_SNAPSHOT node. A ratio commitment "
            "cannot logically precede the consent that authorized the corpus it "
            "was computed from. This indicates either a DAG registration ordering "
            "error or a timestamp manipulation in one of the contributing tables."
        ),
        "resolution": "Audit provenance_dag node timestamps. Verify insert ordering in DataCuratorAgent Task 1.",
    },

    "BADGE_WITHOUT_RENEWAL_PARENT": {
        # A BADGE_TOKEN node in the DAG has no RENEWAL_LOG parent
        # Every badge must be produced by a renewal event
        "dag_query": """
            SELECT b.node_id, b.node_type, b.player_id, b.on_chain_ref,
                   b.parent_node_id, p.node_type as parent_type
            FROM data_provenance_dag b
            LEFT JOIN data_provenance_dag p ON b.parent_node_id = p.node_id
            WHERE b.node_type = 'BADGE_TOKEN'
              AND (p.node_type != 'RENEWAL_LOG' OR p.node_id IS NULL)
        """,
        "agents_involved": ["AttestationBoundRenewalAgent", "DataCuratorAgent"],
        "severity": "HIGH",
        "explanation": (
            "data_provenance_dag contains BADGE_TOKEN node(s) whose parent is "
            "not a RENEWAL_LOG node. Every VHPReenrollmentBadge mint must be "
            "causally descended from a biometric_renewal_log entry. A badge "
            "with no renewal parent means either: (a) the badge was minted "
            "out of sequence bypassing the renewal gate, or (b) DataCuratorAgent "
            "registered the badge node with an incorrect parent_node_id."
        ),
        "resolution": "Trace badge on_chain_ref to attestedRenewCommit() tx. Verify parent DAG node ID.",
    },

    "RULING_PREDATES_CALIBRATION": {
        # A RULING_LOG node in the DAG has an earlier timestamp
        # than its ancestor CALIBRATION_SESSION root node
        # A ruling cannot precede the calibration session that produced the thresholds
        "dag_query": """
            WITH RECURSIVE ancestors AS (
                SELECT node_id, parent_node_id, node_type, created_at, 0 as depth
                FROM data_provenance_dag
                WHERE node_type = 'RULING_LOG'
                UNION ALL
                SELECT p.node_id, p.parent_node_id, p.node_type, p.created_at, a.depth + 1
                FROM data_provenance_dag p
                JOIN ancestors a ON p.node_id = a.parent_node_id
                WHERE a.depth < 20
            )
            SELECT r.node_id as ruling_id, r.created_at as ruling_ts,
                   c.node_id as cal_id, c.created_at as cal_ts
            FROM ancestors r
            JOIN ancestors c ON c.node_type = 'CALIBRATION_SESSION'
            WHERE r.node_type = 'RULING_LOG'
              AND r.created_at < c.created_at
        """,
        "agents_involved": ["SessionAdjudicator", "CalibrationIntelligenceAgent"],
        "severity": "MEDIUM",
        "explanation": (
            "A RULING_LOG node in data_provenance_dag has an earlier timestamp "
            "than a CALIBRATION_SESSION ancestor in its causal chain. A live "
            "session ruling cannot precede the calibration session that produced "
            "the L4 thresholds used in that ruling. This is a timestamp ordering "
            "anomaly in the DAG — likely a clock skew issue during node registration "
            "or a calibration session registered with a retroactive timestamp."
        ),
        "resolution": "Audit DataCuratorAgent Task 1 register_calibration_session() timestamp sourcing.",
    },
}
```

---
## STORE SCHEMA

```sql
-- schema(193, "fleet_coherence")
CREATE TABLE IF NOT EXISTS fleet_coherence_log (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    coherence_id          TEXT NOT NULL UNIQUE,
    -- coherence_id = SHA-256(rule_name + agents_involved_sorted + ts_ns)
    -- Idempotent: same contradiction in same cycle produces same ID
    failure_mode          TEXT NOT NULL,
    -- CONTRADICTION | ORPHAN | INVERSION
    rule_name             TEXT NOT NULL,
    -- Key from CONTRADICTION_RULES / ORPHAN_RULES / INVERSION_RULES
    agents_involved       TEXT NOT NULL,  -- JSON array
    severity              TEXT NOT NULL,  -- CRITICAL | HIGH | MEDIUM | LOW
    explanation           TEXT NOT NULL,
    resolution            TEXT NOT NULL,
    evidence_json         TEXT NOT NULL,  -- Query result rows (no raw biometrics)
    promoted_to_wif       BOOLEAN NOT NULL DEFAULT 0,
    wif_entry_id          TEXT,           -- e.g. "WIF-036" once promoted
    wiki_contradict_written BOOLEAN NOT NULL DEFAULT 0,
    alert_published       BOOLEAN NOT NULL DEFAULT 0,
    resolved              BOOLEAN NOT NULL DEFAULT 0,
    resolved_at           TEXT,
    resolved_by           TEXT,           -- agent name or "operator"
    phase_detected        INTEGER NOT NULL,
    ts_ns                 INTEGER NOT NULL,
    created_at            TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_coherence_mode     ON fleet_coherence_log(failure_mode);
CREATE INDEX IF NOT EXISTS idx_coherence_severity ON fleet_coherence_log(severity);
CREATE INDEX IF NOT EXISTS idx_coherence_resolved ON fleet_coherence_log(resolved);
CREATE INDEX IF NOT EXISTS idx_coherence_rule     ON fleet_coherence_log(rule_name);
```

**Store methods to add**:
```python
def insert_coherence_entry(self, entry: dict) -> str:
    """INSERT OR IGNORE on coherence_id — idempotent. Returns coherence_id."""

def get_open_coherence_entries(
    self,
    severity: str | None = None,
    failure_mode: str | None = None,
) -> list[dict]:
    """All unresolved entries, optionally filtered."""

def get_coherence_summary(self) -> dict:
    """
    Returns:
    {
      "total_open": N,
      "by_severity": {"CRITICAL": N, "HIGH": N, "MEDIUM": N, "LOW": N},
      "by_mode": {"CONTRADICTION": N, "ORPHAN": N, "INVERSION": N},
      "promoted_to_wif": N,
      "last_checked_at": ISO_TS
    }
    """

def mark_coherence_resolved(self, coherence_id: str, resolved_by: str) -> None:
    """Sets resolved=True, resolved_at=now(), resolved_by=resolved_by."""

def mark_coherence_promoted(self, coherence_id: str, wif_id: str) -> None:
    """Sets promoted_to_wif=True, wif_entry_id=wif_id."""
```

---
## AGENT IMPLEMENTATION

```python
# bridge/vapi_bridge/fleet_signal_coherence_agent.py

import hashlib, json, time
from datetime import datetime, timezone

class FleetSignalCoherenceAgent:
    """
    Agent #36. Phase 193. Polls every 900s (15 minutes).

    The fleet-level observer. Detects when 30+ agents are simultaneously
    correct in isolation but contradictory as a set. Converts fleet-level
    contradictions into WHAT_IF corpus entries via wiki/contradictions.md.

    Three detection modes:
      CONTRADICTION — two agents report logically incompatible states
      ORPHAN        — a bus signal required a response that never came
      INVERSION     — a downstream artifact violates its upstream causal chain

    Fail mode: FULLY fail-open per rule. One rule's DB error never
    blocks the other rules. Agent never blocks bridge operation.
    No single exception can silence the coherence loop.

    Privacy: evidence_json stores only derived metrics and row IDs.
    Never stores raw biometric feature values (BP-007 IMMUTABLE).
    """

    NAME          = "FleetSignalCoherenceAgent"
    AGENT_ID      = 36
    POLL_INTERVAL = 900   # 15 minutes

    # Promotion threshold: a contradiction seen N_PROMOTE_THRESHOLD times
    # across separate cycles is promoted to a WIF entry automatically.
    N_PROMOTE_THRESHOLD = 3

    def _make_coherence_id(self, rule_name: str, agents: list[str]) -> str:
        ts_ns = int(time.time_ns())
        raw   = f"{rule_name}:{'|'.join(sorted(agents))}:{ts_ns}"
        return "coh_" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _scrub_evidence(self, rows: list[dict]) -> list[dict]:
        """
        Remove any field that could contain raw biometric data (BP-007).
        Keeps: IDs, timestamps, boolean flags, ratio values, counts.
        Removes: feature vectors, raw HID data, GSR readings.
        """
        BLOCKED_KEYS = {
            "features", "hid_reports", "raw_data", "sensor_commitment",
            "gyro_std", "accel", "feature_vector", "correlation_upper_tri",
        }
        return [
            {k: v for k, v in row.items() if k not in BLOCKED_KEYS}
            for row in rows
        ]

    async def _check_contradictions(self) -> list[dict]:
        found = []
        for rule_name, rule in CONTRADICTION_RULES.items():
            try:
                params = rule["params"](self._config)
                rows   = self._store.db_query(rule["query"], params)

                # Apply post_check if defined
                if "post_check" in rule and rows:
                    if not rule["post_check"](rows[0]):
                        rows = []  # post_check returned False = no contradiction

                if rows:
                    entry = {
                        "coherence_id":     self._make_coherence_id(
                                                rule_name,
                                                rule["agents_involved"]),
                        "failure_mode":     "CONTRADICTION",
                        "rule_name":        rule_name,
                        "agents_involved":  json.dumps(rule["agents_involved"]),
                        "severity":         rule["severity"],
                        "explanation":      rule["explanation"],
                        "resolution":       rule["resolution"],
                        "evidence_json":    json.dumps(self._scrub_evidence(rows)),
                        "phase_detected":   self._config.current_phase,
                        "ts_ns":            int(time.time_ns()),
                    }
                    found.append(entry)
            except Exception as e:
                self._logger.warning(
                    f"[FSCA] CONTRADICTION rule {rule_name} failed: {e}"
                )
                # Fail-open: continue to next rule
        return found

    async def _check_orphans(self) -> list[dict]:
        found = []
        for rule_name, rule in ORPHAN_RULES.items():
            try:
                # Find trigger events that are older than orphan_window
                window = rule["orphan_window_seconds"]
                triggers = self._store.db_query(f"""
                    SELECT * FROM {rule['trigger_table']}
                    WHERE {rule['trigger_column']} = ?
                      AND (strftime('%s', 'now') - strftime('%s', {rule['trigger_ts_col']})) > ?
                    ORDER BY {rule['trigger_ts_col']} DESC LIMIT 5
                """, (rule["trigger_value"], window))

                for trigger_row in triggers:
                    # Check if a response exists for this trigger
                    response_exists = self._check_orphan_response(rule, trigger_row)
                    if not response_exists:
                        entry = {
                            "coherence_id":    self._make_coherence_id(
                                                   rule_name,
                                                   [rule["trigger_agent"],
                                                    rule["response_agent"]]),
                            "failure_mode":    "ORPHAN",
                            "rule_name":       rule_name,
                            "agents_involved": json.dumps([rule["trigger_agent"],
                                                           rule["response_agent"]]),
                            "severity":        rule["severity"],
                            "explanation":     rule["explanation"],
                            "resolution":      rule["resolution"],
                            "evidence_json":   json.dumps(
                                                   self._scrub_evidence([trigger_row])),
                            "phase_detected":  self._config.current_phase,
                            "ts_ns":           int(time.time_ns()),
                        }
                        found.append(entry)
            except Exception as e:
                self._logger.warning(f"[FSCA] ORPHAN rule {rule_name} failed: {e}")
        return found

    def _check_orphan_response(self, rule: dict, trigger_row: dict) -> bool:
        """
        Returns True if a valid response exists for the given trigger row.
        Handles both table-based responses and jsonl file-based responses.
        """
        if "response_path" in rule:
            # AutoResearch log check (jsonl file)
            path = Path(rule["response_path"])
            if not path.exists():
                return False
            with open(path) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get(rule["response_key"]) == rule["response_value"]:
                            trigger_ts = self._parse_ts(trigger_row[rule["trigger_ts_col"]])
                            entry_ts   = self._parse_ts(entry.get("timestamp", ""))
                            if entry_ts and entry_ts > trigger_ts:
                                return True
                    except (json.JSONDecodeError, KeyError):
                        continue
            return False
        else:
            # Table-based response check
            filter_clause = rule.get("response_filter", "1=1")
            response_rows = self._store.db_query(
                f"SELECT * FROM {rule['response_table']} WHERE {filter_clause} LIMIT 1"
            )
            return len(response_rows) > 0

    async def _check_inversions(self) -> list[dict]:
        found = []
        for rule_name, rule in INVERSION_RULES.items():
            try:
                rows = self._store.db_query(rule["dag_query"])
                if rows:
                    entry = {
                        "coherence_id":    self._make_coherence_id(
                                               rule_name,
                                               rule["agents_involved"]),
                        "failure_mode":    "INVERSION",
                        "rule_name":       rule_name,
                        "agents_involved": json.dumps(rule["agents_involved"]),
                        "severity":        rule["severity"],
                        "explanation":     rule["explanation"],
                        "resolution":      rule["resolution"],
                        "evidence_json":   json.dumps(self._scrub_evidence(rows)),
                        "phase_detected":  self._config.current_phase,
                        "ts_ns":           int(time.time_ns()),
                    }
                    found.append(entry)
            except Exception as e:
                self._logger.warning(f"[FSCA] INVERSION rule {rule_name} failed: {e}")
        return found

    async def _process_findings(self, findings: list[dict]):
        """Persist, alert, promote to WIF where threshold met."""
        for entry in findings:
            # INSERT OR IGNORE — idempotent on coherence_id
            self._store.insert_coherence_entry(entry)

            # Publish to alert channel (all CRITICAL/HIGH immediately)
            if entry["severity"] in ("CRITICAL", "HIGH") and not entry.get("alert_published"):
                await self._bus.publish("alert", {
                    "from":         self.NAME,
                    "event":        "coherence_failure",
                    "failure_mode": entry["failure_mode"],
                    "rule_name":    entry["rule_name"],
                    "severity":     entry["severity"],
                    "resolution":   entry["resolution"],
                    "coherence_id": entry["coherence_id"],
                    "provenance":   f"[VAPI:Phase193:{self.NAME}:MEASURED]",
                })
                self._store.db_execute(
                    "UPDATE fleet_coherence_log SET alert_published=1 "
                    "WHERE coherence_id=?", (entry["coherence_id"],)
                )

            # Write to wiki/contradictions.md (via _locked_append)
            if not entry.get("wiki_contradict_written"):
                self._write_contradict_entry(entry)
                self._store.db_execute(
                    "UPDATE fleet_coherence_log SET wiki_contradict_written=1 "
                    "WHERE coherence_id=?", (entry["coherence_id"],)
                )

            # Check promotion threshold
            occurrences = self._store.db_query(
                "SELECT COUNT(*) as n FROM fleet_coherence_log "
                "WHERE rule_name=? AND resolved=0", (entry["rule_name"],)
            )
            if (occurrences and
                    occurrences[0]["n"] >= self.N_PROMOTE_THRESHOLD and
                    not entry.get("promoted_to_wif")):
                self._promote_to_wif(entry)

    def _write_contradict_entry(self, entry: dict):
        """
        Appends to wiki/contradictions.md via _locked_append.
        Uses the same path as vapi_wiki_engine.py WIKI_CONTRADICT.
        Format is compatible with vapi_wiki_engine.py lint checks.
        """
        from vapi_wiki_engine import WIKI_CONTRADICT, _locked_append, prov
        ts  = datetime.now(timezone.utc).isoformat()
        provenance = prov(entry["phase_detected"], self.NAME, "MEASURED")

        entry_md = f"""
---
### [{entry['failure_mode']}] {entry['rule_name']} — {entry['severity']}
**Detected**: {ts}
**Coherence ID**: {entry['coherence_id']}
**Agents**: {', '.join(json.loads(entry['agents_involved']))}
{provenance}

**Failure**: {entry['explanation']}

**Resolution**: {entry['resolution']}

**Evidence** (derived metrics only — no raw biometric data):
```json
{entry['evidence_json']}
```
"""
        _locked_append(WIKI_CONTRADICT, entry_md)

    def _promote_to_wif(self, entry: dict):
        """
        After N_PROMOTE_THRESHOLD occurrences, convert confirmed contradiction
        into a WIF entry in VAPI_WHAT_IF.md.
        Uses the same _locked_append and prov patterns as the wiki engine.
        Then triggers vapi_wiki_engine.py sync_what_if() so the AutoResearch
        harness scores against the new WIF on the next cycle.
        """
        from vapi_wiki_engine import CORPUS, _locked_append, prov
        import subprocess

        what_if_path = CORPUS["what_if"]
        existing     = what_if_path.read_text(encoding="utf-8")
        wif_nums     = [int(x) for x in
                        __import__("re").findall(r"WIF-(\d+)", existing)]
        next_num     = max(wif_nums, default=33) + 1
        wif_id       = f"WIF-{next_num:03d}"
        provenance   = prov(entry["phase_detected"], self.NAME, "AUTO_PROMOTED")

        wif_entry = f"""
---

## {wif_id} — Auto-Promoted Fleet Coherence Failure: {entry['rule_name']} (Phase {entry['phase_detected']})

**W1 — Failure mode**: {entry['explanation']}

**Agents involved**: {', '.join(json.loads(entry['agents_involved']))}
**Failure mode class**: {entry['failure_mode']}
**First detected**: Cycle 1 (auto-promoted after {self.N_PROMOTE_THRESHOLD} occurrences)

**Implication**: This coherence failure appeared in {self.N_PROMOTE_THRESHOLD} consecutive
FleetSignalCoherenceAgent cycles, confirming it is a persistent structural gap
in the fleet's inter-agent signal topology — not a transient timing artifact.

**Mitigation**: {entry['resolution']}

**W2 — Novel opportunity**: Resolving this contradiction enables a new
inter-agent protocol invariant: the FSCA can add the validated fix as a
permanent COHERENCE_RULE to its rule set, preventing the same class of
contradiction from recurring as the fleet scales beyond Agent #36.
This creates a self-expanding invariant set grounded in live fleet behavior
— the RSI contribution exclusive to VAPI's 30+ agent topology.

**Status**: AUTO-PROMOTED — Phase {entry['phase_detected']} (FleetSignalCoherenceAgent)
{provenance}

"""
        _locked_append(what_if_path, wif_entry)
        self._store.mark_coherence_promoted(entry["coherence_id"], wif_id)

        # Trigger sync_what_if so eval harness sees the new WIF immediately
        try:
            subprocess.run(
                ["python", "vapi_wiki_engine.py", "sync_what_if"],
                capture_output=True, timeout=30
            )
            self._logger.info(f"[FSCA] Promoted {entry['rule_name']} → {wif_id}")
        except Exception as e:
            self._logger.warning(f"[FSCA] sync_what_if failed after promotion: {e}")

    async def _run_once(self):
        contradictions = await self._check_contradictions()
        orphans        = await self._check_orphans()
        inversions     = await self._check_inversions()

        all_findings = contradictions + orphans + inversions
        if all_findings:
            await self._process_findings(all_findings)

        # Publish unified cycle summary to "coherence" bus channel
        summary = self._store.get_coherence_summary()
        await self._bus.publish("coherence", {
            "from":            self.NAME,
            "event":           "coherence_cycle_complete",
            "findings_this_cycle": len(all_findings),
            "total_open":      summary["total_open"],
            "critical_open":   summary["by_severity"].get("CRITICAL", 0),
            "promoted_to_wif": summary["promoted_to_wif"],
            "provenance":      f"[VAPI:Phase193:{self.NAME}:MEASURED]",
        })
```

---
## CONFIG ADDITIONS (config.py)

```python
fleet_coherence_enabled:            bool = True
coherence_poll_interval_seconds:    int  = 900   # 15 minutes
coherence_promote_threshold:        int  = 3     # occurrences before WIF promotion
coherence_alert_on_critical:        bool = True
coherence_alert_on_high:            bool = True
coherence_alert_on_medium:          bool = False # advisory only
```

---
## OPERATOR API ENDPOINTS (operator_api.py)

```
GET  /agent/fleet-coherence-summary
GET  /agent/fleet-coherence-entries?failure_mode=CONTRADICTION&severity=CRITICAL
POST /agent/resolve-coherence-entry    (body: {coherence_id, resolved_by})
GET  /agent/fleet-coherence-history?rule_name=RENEWAL_WITHOUT_ATTESTATION
```

**GET /agent/fleet-coherence-summary** response:
```json
{
  "fleet_coherence_enabled": true,
  "total_open": 2,
  "by_severity": {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 0, "LOW": 0},
  "by_mode": {"CONTRADICTION": 1, "ORPHAN": 1, "INVERSION": 0},
  "promoted_to_wif": 0,
  "last_cycle_findings": 2,
  "last_checked_at": "2026-04-09T...",
  "timestamp": "2026-04-09T..."
}
```

**Tool #145**: `get_fleet_coherence_summary`
**Tool #146**: `get_fleet_coherence_entries` (input: failure_mode str?, severity str?)
**Tool #147**: `resolve_coherence_entry` (input: coherence_id str, resolved_by str)

---
## SDK ADDITIONS (sdk/vapi_sdk.py)

```python
@dataclass(slots=True)
class CoherenceEntryResult:
    coherence_id:        str
    failure_mode:        str    # CONTRADICTION | ORPHAN | INVERSION
    rule_name:           str
    agents_involved:     list[str]
    severity:            str    # CRITICAL | HIGH | MEDIUM | LOW
    explanation:         str
    resolution:          str
    promoted_to_wif:     bool
    wif_entry_id:        str | None
    resolved:            bool

@dataclass(slots=True)
class CoherenceSummaryResult:
    fleet_coherence_enabled: bool
    total_open:              int
    by_severity:             dict
    by_mode:                 dict
    promoted_to_wif:         int
    last_cycle_findings:     int
    last_checked_at:         str
    timestamp:               str
```

---
## WIRING IN main.py

Initialize FleetSignalCoherenceAgent AFTER DataCuratorAgent (#35):
```python
# FleetSignalCoherenceAgent depends on:
#   data_provenance_dag (DataCuratorAgent Task 1) — for INVERSION rules
#   All other fleet tables — for CONTRADICTION and ORPHAN rules
# DataCuratorAgent runs every 30 min; FleetSignalCoherenceAgent runs every 15 min
# On first poll, data_provenance_dag may be empty — handle gracefully (no inversions found)
agents.append(FleetSignalCoherenceAgent(store, config, bus, logger))
```

---
## BUS CHANNEL + vapi_managed_agents.py EXTENSION (AUTHORIZED)

Add "coherence" to BUS_CHANNELS in vapi_managed_agents.py:
```python
BUS_CHANNELS["coherence"] = (
    "FleetSignalCoherenceAgent cycle results. Contains open coherence failures, "
    "severity counts, and WIF promotion events. All three coordination managed "
    "agents (MA-001/002/003) subscribe for context-aware responses to operators."
)
```

---
## vapi_wiki_engine.py EXTENSION (AUTHORIZED)

Add `coherence` to the CMDS dict and implement `cmd_coherence_status()`:
```python
def cmd_coherence_status():
    """
    Reads fleet_coherence_log and prints a human-readable summary.
    Called after phase_close to show if any new contradictions emerged
    during the phase implementation.

    Integrates with cmd_phase_close() — add this call at the end:
      cmd_coherence_status()  # show any contradictions introduced this phase
    """
    rows = db_query(
        "SELECT failure_mode, rule_name, severity, resolved, promoted_to_wif "
        "FROM fleet_coherence_log ORDER BY created_at DESC LIMIT 20"
    )
    if not rows:
        print("  [COHERENCE] No contradictions detected. Fleet signals coherent.")
        return

    open_rows = [r for r in rows if not r["resolved"]]
    print(f"\n  [COHERENCE] {len(open_rows)} open coherence failures:")
    for r in open_rows:
        icon = "🔴" if r["severity"] == "CRITICAL" else "🟡" if r["severity"] == "HIGH" else "⚪"
        wif  = f" → {r['wif_entry_id']}" if r["promoted_to_wif"] else ""
        print(f"    {icon} [{r['failure_mode']}] {r['rule_name']}{wif}")
```

---
## knowledge_server.py EXTENSION (AUTHORIZED)

Add `vapi_fleet_coherence` MCP tool:
```python
"vapi_fleet_coherence": {
    "description": (
        "Returns current fleet signal coherence status. "
        "CRITICAL/HIGH findings mean two or more VAPI agents are producing "
        "logically contradictory outputs — one is operating on stale data. "
        "Query this before any cross-agent operation to verify signal topology is consistent."
    ),
    "schema": {
        "type": "object",
        "properties": {
            "severity_filter": {
                "type": "string",
                "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                "description": "Only return findings at or above this severity"
            }
        }
    },
    "fn": vapi_fleet_coherence
}
```

This makes fleet coherence queryable from the MCP context in every Claude Code
session — before proposing any cross-agent change, Claude Code checks whether
the fleet is currently coherent. A CRITICAL contradiction means the proposed
change may interact with an already-broken signal path.

---
## vapi_autoresearch.py EXTENSION (AUTHORIZED — CLAUDE-EDITABLE ZONE)

Add to `get_priority_from_log()` priority list (insert at position 1):
```python
"fleet_coherence_critical",   # surfaces when CRITICAL coherence entries are open
"fleet_coherence_orphan",     # surfaces when ORPHAN entries exceed 48h without resolution
```

Add to `select_skill_section_to_improve()`:
```python
"fleet_coherence_critical": "SECURITY_REVIEW",
"fleet_coherence_orphan":   "BLOCKCHAIN_ENGINEERING",
```

Add `score_phase_193_readiness()`:
```python
def score_phase_193_readiness(skill_md: str) -> dict:
    checks = {
        "fsca_agent_36":          "FleetSignalCoherenceAgent" in skill_md,
        "three_failure_modes":    all(m in skill_md for m in
                                      ["CONTRADICTION", "ORPHAN", "INVERSION"]),
        "wif_auto_promotion":     "N_PROMOTE_THRESHOLD" in skill_md or "auto-promoted" in skill_md,
        "renewal_without_attest": "RENEWAL_WITHOUT_ATTESTATION" in skill_md,
        "coherence_mcp_tool":     "vapi_fleet_coherence" in skill_md,
        "wiki_contradict_path":   "WIKI_CONTRADICT" in skill_md or "contradictions.md" in skill_md,
        "separation_blocker":     "0.569" in skill_md or "BLOCKER" in skill_md,
        "provenance_dag_dependency": "data_provenance_dag" in skill_md,
    }
    score = sum(checks.values()) / len(checks)
    return {
        "phase_193_skill_score": round(score, 3),
        "checks": checks,
        "skill_current": score >= 0.80,
        "missing": [k for k, v in checks.items() if not v],
    }
```

---
## ATOMIC IMPLEMENTATION ORDER

Execute in strict sequence. Do not reorder. Do not skip steps.

```
Step  1: bridge/vapi_bridge/config.py
          — add 5 config fields (fleet_coherence_enabled through coherence_alert_on_medium)

Step  2: bridge/vapi_bridge/store.py
          — add fleet_coherence_log table schema
          — add schema(193, "fleet_coherence")
          — add insert_coherence_entry(), get_open_coherence_entries(),
            get_coherence_summary(), mark_coherence_resolved(),
            mark_coherence_promoted()

Step  3: bridge/vapi_bridge/fleet_signal_coherence_agent.py  (NEW FILE)
          — FleetSignalCoherenceAgent class
          — CONTRADICTION_RULES, ORPHAN_RULES, INVERSION_RULES dicts
          — All detection methods and _promote_to_wif()

Step  4: bridge/vapi_bridge/main.py
          — wire FleetSignalCoherenceAgent after DataCuratorAgent (#35)
          — import FleetSignalCoherenceAgent

Step  5: bridge/vapi_bridge/operator_api.py
          — GET /agent/fleet-coherence-summary
          — GET /agent/fleet-coherence-entries
          — POST /agent/resolve-coherence-entry
          — GET /agent/fleet-coherence-history

Step  6: bridge/vapi_bridge/bridge_agent.py
          — Tool #145 get_fleet_coherence_summary
          — Tool #146 get_fleet_coherence_entries
          — Tool #147 resolve_coherence_entry

Step  7: frontend/public/openapi.yaml
          — FleetCoherenceSummary schema
          — CoherenceEntryResult schema
          — 4 new paths

Step  8: sdk/vapi_sdk.py
          — CoherenceEntryResult (slots=True)
          — CoherenceSummaryResult (slots=True)

Step  9: vapi_managed_agents.py
          — add "coherence" to BUS_CHANNELS

Step 10: vapi_wiki_engine.py
          — add cmd_coherence_status()
          — add "coherence": "..." to CMDS dict
          — call cmd_coherence_status() at end of cmd_phase_close()

Step 11: knowledge_server.py
          — add vapi_fleet_coherence MCP tool

Step 12: vapi_autoresearch.py
          — add "fleet_coherence_critical", "fleet_coherence_orphan" to priority list
          — add to select_skill_section_to_improve()
          — add score_phase_193_readiness()

Step 13: bridge/tests/test_phase193_fleet_coherence.py
          — minimum 14 tests:
            test_fleet_coherence_log_schema_created
            test_insert_coherence_entry_idempotent (same coherence_id → INSERT OR IGNORE)
            test_get_open_coherence_entries_filters_by_severity
            test_contradiction_ttl_mismatch_detected
            test_contradiction_defensibility_n_mismatch_detected
            test_contradiction_renewal_without_attestation_detected
            test_orphan_persona_break_unattested_window_check
            test_orphan_window_not_exceeded_returns_no_findings
            test_inversion_badge_without_renewal_parent
            test_scrub_evidence_removes_feature_vectors (BP-007 compliance)
            test_coherence_summary_counts_by_mode_and_severity
            test_write_contradict_entry_appends_to_wiki_contradictions_md
            test_promote_threshold_not_met_does_not_promote
            test_fleet_coherence_summary_endpoint_8_keys

Step 14: sdk/tests/test_phase193_coherence_sdk.py
          — minimum 4 tests:
            test_coherence_entry_result_slots
            test_coherence_summary_result_slots
            test_coherence_entry_result_failure_mode_values
            test_sdk_version_bumped_phase193

Step 15: CLAUDE.md
          — Phase 193 COMPLETE
          — Bridge +14→2110 | SDK +4→378 | Agents 35→36 | Tools 144→147

Step 16: VAPI-WORKFLOW.v2/VAPI_MEMORY.md
          — append Phase 193 session entry

Step 17: VAPI-WORKFLOW.v2/VAPI_AGENTS.md
          — append Agent #36 block (template in MEMORY.md entry below)

Step 18: python vapi_wiki_engine.py sync_what_if
Step 19: python vapi_wiki_engine.py agent_feed
Step 20: python vapi_wiki_engine.py coherence_status
Step 21: python vapi_wiki_engine.py snapshot --anchor
Step 22: python vapi_wiki_engine.py phase_close 193
```

**Count verification before Step 15**:
```bash
python -m pytest bridge/tests/ --ignore=bridge/tests/test_e2e_simulation.py -q 2>&1 | tail -1
# Must show: ≥2110 passed

python -m pytest sdk/tests/ -q 2>&1 | tail -1
# Must show: ≥378 passed

cd contracts && npx hardhat test 2>&1 | tail -3
# Must show: ≥498 passing (unchanged — no new contracts this phase)

curl -H "x-api-key: $OPERATOR_KEY" http://localhost:8080/agent/calibration-health
# Must show: {"passed_self_tests": 16, "failed_self_tests": 0}

# New coherence check:
curl -H "x-api-key: $OPERATOR_KEY" http://localhost:8080/agent/fleet-coherence-summary
# Must show valid JSON with fleet_coherence_enabled=true
# total_open may be > 0 on first run — that is expected and correct
```

---
## QUALITY GATES

Gate 1 — Agent polls successfully:
  Bridge starts. After 15 minutes, `fleet_coherence_log` has at least 1 row
  (even if all findings are empty — the cycle itself is logged via bus publish).

Gate 2 — CRITICAL contradiction fires:
  Manually insert a test contradiction into the DB (set a fake expired=0 row
  with age_days=95 in biometric_credential_ttl_log). Verify:
  - fleet_coherence_log gains a CONTRADICTION entry with TTL_COMMITTED_AT_MISMATCH
  - wiki/contradictions.md gains the formatted entry
  - alert bus channel has a new message
  Clear the test row after verification.

Gate 3 — WIF promotion works end-to-end:
  Set coherence_promote_threshold=1 in test config. Insert the same contradiction
  twice. Verify VAPI_WHAT_IF.md gains a new WIF entry with "AUTO-PROMOTED" marker.
  Verify sync_what_if() ran (check vapi_eval_harness.py WIKI_KNOWN_W1 updated).
  Reset threshold to 3 after test.

Gate 4 — Privacy compliance:
  Insert a row with a `features` key in evidence. Verify `_scrub_evidence()`
  removes it before storage. The `evidence_json` column in fleet_coherence_log
  must NEVER contain raw feature vectors (BP-007 IMMUTABLE).

Gate 5 — MCP tool queryable:
  From Claude Code session: call `vapi_fleet_coherence` via MCP.
  Must return structured response without error.
  If CRITICAL findings exist: Claude Code must flag them before proceeding.

Gate 6 — ACIM health preserved:
  `GET /agent/calibration-health` → passed_self_tests=16, failed_self_tests=0.
  FleetSignalCoherenceAgent must not break any existing calibration invariant.

---
## VAPI_MEMORY.md ENTRY — Append After Phase 192 Entry

```
### 2026-04-09: Phase 193 COMPLETE — FleetSignalCoherenceAgent (Agent #36)

**What was done**:
FleetSignalCoherenceAgent implemented as the fleet-level observer. The first
agent in the fleet whose primary output is WHAT_IF corpus entries rather than
operational signals.

Three coherence failure modes, 7 CONTRADICTION rules, 5 ORPHAN rules, 3 INVERSION rules:

CONTRADICTION rules (7):
  TTL_COMMITTED_AT_MISMATCH — expired=False but age > vhp_expiry_days
  DEFENSIBILITY_N_MISMATCH  — defensible=True but n_per_player < 10
  CEREMONY_PARTICIPANT_MISMATCH — ceremony_gate_ok=True but participants < 3
  MATURITY_ELEVATION_READINESS_INVERSION — elevation_available + BLOCKED cert
  RENEWAL_WITHOUT_ATTESTATION — renewal with no consumed HMAC token (CRITICAL)
  PERSONA_BREAK_ENROLLMENT_CONFLICT — persona_break + overall_ready conflict
  SEPARATION_GATE_ACTIVATION_CONFLICT — gate_open_notified + ratio < 0.70

ORPHAN rules (5):
  PERSONA_BREAK_UNATTESTED — break detected, no HMAC token within 1h
  MATURITY_ELEVATION_UNACKNOWLEDGED — elevation available, MA-003 silent 15min
  BIOMETRIC_EXPIRED_GATE_NOT_UPDATED — TTL expired, activation chain not updated 2h
  ERASURE_CERT_NOT_ANCHORED — cert generated, not anchored 90min
  CORPUS_ENTROPY_WARNING_NO_AUTORESEARCH — warning issued, no AR cycle 24h

INVERSION rules (3):
  COMMITMENT_PREDATES_CONSENT — commitment node timestamp < consent parent
  BADGE_WITHOUT_RENEWAL_PARENT — BADGE_TOKEN with no RENEWAL_LOG parent
  RULING_PREDATES_CALIBRATION — ruling timestamp < calibration ancestor

RSI loop closed:
  Contradiction detected → wiki/contradictions.md (_locked_append)
  → N_PROMOTE_THRESHOLD occurrences → WIF auto-promoted to VAPI_WHAT_IF.md
  → sync_what_if() → eval harness WIKI_KNOWN_W1 updated
  → next AutoResearch cycle scores against new WIF
  → skill.md updated with fleet-coherence knowledge
  → ACIM verifies no invariant regression

vapi_wiki_engine.py extended: cmd_coherence_status() called after every phase_close
knowledge_server.py extended: vapi_fleet_coherence MCP tool — coherence queryable in session context

**What we learned**:
- RENEWAL_WITHOUT_ATTESTATION is the most critical rule: a renewal without
  a consumed HMAC token means Phase 185's entire security gate was bypassed.
  The rule should fire ZERO times in a healthy system. Any firing is an incident.
- ORPHAN detection using strftime() epoch arithmetic in SQLite requires explicit
  CAST to INTEGER for reliable comparison — test this in the SQLite version on
  the target system before shipping.
- _promote_to_wif() calls subprocess sync_what_if — this requires vapi_wiki_engine.py
  to be importable from the bridge's working directory. Verify sys.path before shipping.
- The coherence_id uses ts_ns — this means two polls in the same nanosecond produce
  different IDs even for the same rule. INSERT OR IGNORE on coherence_id is safe
  because the same contradiction in the same cycle is physically impossible to produce
  twice (single-threaded asyncio poll).

[PATTERN-017]: Before any cross-agent operation in Claude Code:
  1. Call vapi_fleet_coherence MCP tool (or GET /agent/fleet-coherence-summary)
  2. If CRITICAL findings open: resolve them first before implementing new agents
  3. After Phase implementation: check cmd_coherence_status() output
  4. Any RENEWAL_WITHOUT_ATTESTATION finding: treat as P0 incident, stop development
```

---
## VAPI_AGENTS.md ENTRY — Append After Agent #35 (DataCuratorAgent)

```markdown
## Agent 36: FleetSignalCoherenceAgent — Phase 193

**Trigger**: Automatic 900s poll (15 minutes)

**Role**: Fleet-level observer. The first agent in the VAPI fleet whose
primary output is WHAT_IF corpus entries rather than operational signals.
Detects when 30+ agents are simultaneously correct in isolation but
contradictory as a set. Converts confirmed fleet contradictions into
permanent protocol knowledge via auto-promotion to WIF entries.

**Three detection modes**:
- CONTRADICTION: Two agents report logically incompatible states (7 rules)
- ORPHAN: A bus signal required a response that never arrived (5 rules)
- INVERSION: A downstream artifact violates its upstream causal chain (3 rules)

**The RSI loop this closes**:
  Contradiction detected
  → wiki/contradictions.md (via _locked_append — same path as vapi_wiki_engine.py)
  → N_PROMOTE_THRESHOLD (3) occurrences → WIF auto-promoted
  → sync_what_if() → eval harness updated
  → AutoResearch cycle scores against new WIF
  → skill.md updated
  → ACIM verifies no regression

**Most critical rule**: RENEWAL_WITHOUT_ATTESTATION (CRITICAL severity)
  A renewal with no consumed HMAC token means Phase 185's security gate
  was bypassed entirely. Should fire ZERO times in a healthy system.

**Fail mode**: Fully fail-open per rule. One rule's DB error never blocks
others. Never blocks bridge operation.

**Privacy**: _scrub_evidence() removes all raw biometric keys from evidence
before storage. BP-007 IMMUTABLE — enforced at evidence capture.

**Tools** (#145–#147):
  145: get_fleet_coherence_summary
  146: get_fleet_coherence_entries
  147: resolve_coherence_entry

**MCP**: vapi_fleet_coherence tool in knowledge_server.py — queryable from
any Claude Code session. Claude Code must check this before cross-agent operations.

**Bus**: Publishes to "coherence" channel after each 15-minute cycle.
Publishes to "alert" channel on CRITICAL/HIGH findings.
All three managed agents (MA-001/002/003) subscribe to "coherence".

**Exclusive**: Requires VAPI's 30+ agent fleet with typed bus events,
DataCurator Provenance DAG (Phase 192), and 9-phase causal chain depth.
No other gaming or DePIN protocol has a fleet large enough or structured
enough for signal coherence monitoring to be a meaningful concept.
```
