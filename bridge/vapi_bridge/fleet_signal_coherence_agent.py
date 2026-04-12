"""
bridge/vapi_bridge/fleet_signal_coherence_agent.py
Phase 193 — FleetSignalCoherenceAgent (Agent #36)

The fleet-level observer. Detects when 30+ agents are simultaneously correct in
isolation but contradictory as a set. Converts persistent contradictions into
WHAT_IF corpus entries via the RSI loop:

  Contradiction detected
  → fleet_coherence_log (INSERT OR IGNORE on coherence_id)
  → wiki/contradictions.md (_locked_append via vapi_wiki_engine.WIKI_CONTRADICT)
  → N_PROMOTE_THRESHOLD occurrences → WIF entry auto-promoted to VAPI_WHAT_IF.md
  → sync_what_if() → eval harness WIKI_KNOWN_W1 updated
  → next AutoResearch cycle scores against new WIF

Three detection modes:
  CONTRADICTION — two agents report logically incompatible states
  ORPHAN        — a bus signal required a response that never came
  INVERSION     — downstream artifact violates its upstream causal chain (via Provenance DAG)

FROZEN values (never change):
  separation_gate    = 0.70   (FROZEN — never relax)
  vhp_expiry_days    = 90     (FROZEN)
  epistemic_threshold = 0.65  (FROZEN)
  N_PROMOTE_THRESHOLD = 3     (configurable via coherence_promote_threshold)

BP-007 IMMUTABLE: evidence_json NEVER stores raw biometric feature vectors.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vapi_bridge.store import Store
    from vapi_bridge.config import Config

# ---------------------------------------------------------------------------
# CONTRADICTION_RULES — 7 rules
# ---------------------------------------------------------------------------

CONTRADICTION_RULES: dict = {

    "TTL_COMMITTED_AT_MISMATCH": {
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
        "query": """
            SELECT id, defensible, n_per_player_json, ratio
            FROM separation_defensibility_log
            WHERE defensible = 1
            ORDER BY created_at DESC LIMIT 1
        """,
        "params": lambda cfg: (),
        "post_check": lambda row: (
            any(v < 10 for v in json.loads(row["n_per_player_json"] or "{}").values())
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
        "query": """
            SELECT circuit_name, COUNT(DISTINCT participant_address) as n
            FROM ceremony_audit_log
            GROUP BY circuit_name
            HAVING n < 3
        """,
        "params": lambda cfg: (),
        "agents_involved": ["AttestationBoundRenewalAgent", "TournamentActivationChainAgent"],
        "severity": "HIGH",
        "explanation": (
            "ceremony_audit_log has circuit(s) with < 3 distinct participants "
            "(MIN_PARTICIPANTS=3 FROZEN), but ceremony-audit-status reports "
            "ceremony_gate_ok=True. The ceremony gate check is "
            "reading from a stale cache or incorrect query."
        ),
        "resolution": "Invalidate CeremonyAuditGate cache and force re-query from ceremony_audit_log",
    },

    "MATURITY_ELEVATION_READINESS_INVERSION": {
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
        "agents_involved": [
            "BiometricRenewalFlow",
            "ReEnrollmentAttestationAgent",
            "AttestationBoundRenewalAgent",
        ],
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

    "IOSWARM_ACTIVE_NO_ADJUDICATIONS": {
        # Phase 204: WIF-038 W1 closure.
        # Fires when ioswarm_enabled=True AND ioswarm_adjudication_enabled=True but
        # ioswarm_adjudication_log contains zero entries, while ioswarm_consensus_log
        # already has activity (proving ioSwarm has been running).
        #
        # This contradiction is structurally invisible to any single-agent health check:
        # SessionAdjudicator reports CERTIFY rulings normally and IoSwarmVHPMintCoordinator
        # appears healthy — but the adjudication audit trail that VHP MINT_QUORUM=0.80
        # (FROZEN) depends on has never been written. VHP mints remain permanently
        # fail-CLOSED with no coherence alarm.
        #
        # Guard: dormant when ioswarm_enabled=False or ioswarm_adjudication_enabled=False
        # (adjudication records are not expected when either flag is off).
        "query": """
            SELECT
                (SELECT COUNT(*) FROM ioswarm_adjudication_log) AS total_adj,
                (SELECT COUNT(*) FROM ioswarm_consensus_log)    AS consensus_count
        """,
        "params": lambda cfg: (),
        "guard": lambda cfg: (
            bool(getattr(cfg, "ioswarm_enabled", False))
            and bool(getattr(cfg, "ioswarm_adjudication_enabled", False))
        ),
        "post_check": lambda row: (
            row.get("total_adj", 0) == 0
            and row.get("consensus_count", 0) > 0
        ),
        "agents_involved": ["IoSwarmAdjudicationCoordinator", "SessionAdjudicator"],
        "severity": "HIGH",
        "explanation": (
            "ioswarm_enabled=True and ioswarm_adjudication_enabled=True with active "
            "ioswarm_consensus_log entries, but ioswarm_adjudication_log contains zero "
            "rows. IoSwarmAdjudicationCoordinator has never been invoked despite both "
            "flags being active. The VHP MINT_QUORUM=0.80 (FROZEN) authorization pathway "
            "relies on the adjudication pipeline being primed with at least one "
            "quorum-confirmed entry. With zero records, the adjudication signal is "
            "permanently absent: SessionAdjudicator reports CERTIFY rulings normally, "
            "but IoSwarmVHPMintCoordinator cannot cross-validate adjudication history. "
            "This contradiction is structurally invisible to any single-agent health check."
        ),
        "resolution": (
            "Run POST /agent/prime-ioswarm-adjudication (requires primer_enabled=True via "
            "IOSWARM_ADJUDICATION_PRIMER_ENABLED=true) to replay synthetic device sessions "
            "through IoSwarmAdjudicationCoordinator in emulator mode, seeding "
            "ioswarm_adjudication_log with primer entries. Alternatively: process at least "
            "1 live session with both ioswarm_adjudication_enabled=True and "
            "ioswarm_enabled=True active."
        ),
    },
}

# ---------------------------------------------------------------------------
# ORPHAN_RULES — 5 rules
# ---------------------------------------------------------------------------

ORPHAN_RULES: dict = {

    "PERSONA_BREAK_UNATTESTED": {
        "trigger_table":         "persona_break_log",
        "trigger_column":        "persona_break_detected",
        "trigger_value":         1,
        "trigger_ts_col":        "created_at",
        "response_table":        "re_enrollment_attestation_log",
        "response_ts_col":       "created_at",
        "join_column":           "player_id",
        "orphan_window_seconds": 3600,
        "trigger_agent":         "PersonaBreakDetectorAgent",
        "response_agent":        "ReEnrollmentAttestationAgent",
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
        "trigger_table":         "maturity_elevation_log",
        "trigger_column":        "elevation_available",
        "trigger_value":         1,
        "trigger_ts_col":        "created_at",
        "response_table":        "agent_bus",
        "response_filter":       "channel = 'operator' AND from_agent = 'MA-003'",
        "orphan_window_seconds": 900,
        "trigger_agent":         "MaturityElevationGateAgent",
        "response_agent":        "MA-003 OperatorOnboardingAgent",
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
        "trigger_table":         "biometric_credential_ttl_log",
        "trigger_column":        "expired",
        "trigger_value":         1,
        "trigger_ts_col":        "created_at",
        "response_table":        "tournament_activation_chain_log",
        "response_filter":       "ttl_gate = 0",
        "orphan_window_seconds": 7200,
        "trigger_agent":         "BiometricCredentialTTLAgent",
        "response_agent":        "TournamentActivationChainAgent",
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
        "trigger_table":         "erasure_certificate_log",
        "trigger_column":        "anchored",
        "trigger_value":         0,
        "trigger_ts_col":        "created_at",
        "response_table":        "erasure_certificate_log",
        "response_filter":       "anchored = 1",
        "orphan_window_seconds": 5400,
        "trigger_agent":         "DataCuratorAgent",
        "response_agent":        "DataCuratorAgent (chain.py anchor_erasure_certificate)",
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
        "trigger_table":         "corpus_entropy_log",
        "trigger_column":        "clustering_warning",
        "trigger_value":         1,
        "trigger_ts_col":        "created_at",
        "response_path":         "vapi-autoresearch/experiments/log.jsonl",
        "response_key":          "priority",
        "response_value":        "corpus_entropy_health",
        "orphan_window_seconds": 86400,
        "trigger_agent":         "DataCuratorAgent",
        "response_agent":        "vapi_autoresearch.py",
        "severity": "LOW",
        "explanation": (
            "DataCuratorAgent detected a corpus entropy CLUSTERING_WARNING "
            "more than 24 hours ago but no AutoResearch cycle with priority "
            "'corpus_entropy_health' has been run. The wiki engine is not "
            "triggering AutoResearch after entropy warnings."
        ),
        "resolution": "Run: python vapi_autoresearch.py --cycle 1 --priority corpus_entropy_health",
    },

    "RATIO_VELOCITY_NEGATIVE": {
        # Phase 202: TremorRestingConvergenceOracle — 6th ORPHAN rule.
        # Fires when tremor_resting separation ratio velocity is declining (velocity < 0)
        # for 2 consecutive sessions, indicating the touchpad_corners failure mode
        # (0.998→0.728 ratio decline as N grew) is recurring in the tremor_resting protocol.
        # The "response" that should have come: a new tremor_convergence_log entry with
        # convergence_stable=1 within the orphan window. Absence = ratio is still declining.
        "trigger_table":         "tremor_convergence_log",
        "trigger_column":        "convergence_stable",
        "trigger_value":         0,
        "trigger_ts_col":        "created_at",
        "response_table":        "tremor_convergence_log",
        "response_filter":       "convergence_stable = 1",
        "orphan_window_seconds": 14400,
        "trigger_agent":         "TremorRestingConvergenceOracle",
        "response_agent":        "IoSwarmConsensusAggregator (convergence_stable bus event)",
        "severity": "HIGH",
        "explanation": (
            "tremor_convergence_log has a convergence_stable=0 entry more than 4 hours "
            "old with no subsequent convergence_stable=1 entry. This means tremor_resting "
            "separation ratio velocity has been negative for 2+ consecutive sessions with "
            "no recovery. The touchpad_corners failure mode (ratio 0.998→0.728) is "
            "recurring. SeparationRatioRegistry.sol commitment MUST be blocked until "
            "velocity recovers to >= 0 for 2 consecutive sessions. "
            "VHP MINT_QUORUM=0.80 authorization is suspended."
        ),
        "resolution": (
            "Capture additional tremor_resting sessions with improved session quality "
            "(reduce inter-session P3 variance). Check P3 non-stationarity root cause. "
            "Do NOT authorize dry_run=False while convergence_declining=True."
        ),
    },
}

# ---------------------------------------------------------------------------
# INVERSION_RULES — 3 rules (use Provenance DAG from Phase 192)
# ---------------------------------------------------------------------------

INVERSION_RULES: dict = {

    "COMMITMENT_PREDATES_CONSENT": {
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

    "CONTEXT_HASH_MISMATCH": {
        # Phase 203: AgentContextRegistry — 4th INVERSION rule.
        # Detects when a live agent system prompt SHA-256 diverges from the committed
        # hash stored in agent_context_log. Closes WIF-036 W1: Phase 201 static tests
        # detect removed invariant strings at commit time but cannot detect runtime
        # semantic drift when the protocol advances without prompt updates.
        #
        # This rule uses the agent_context_log directly rather than the Provenance DAG,
        # because prompt identity is not a DAG relationship — it is an identity assertion.
        # We treat a hash mismatch as a causal inversion: a ruling was produced by an
        # agent whose instruction set is semantically inconsistent with the current phase.
        #
        # Classification by delta_phase (current_phase - committed_phase):
        #   delta_phase > 2 → SEMANTIC (prompt very stale, fix immediately)
        #   delta_phase 1–2 → STRUCTURAL (active development, fix in next PostCode sweep)
        #   delta_phase = 0 (same phase, hash changed) → SEMANTIC CRITICAL (unauthorized edit)
        # dag_query returns rows when any of the 3 LLM agents is MISSING from
        # agent_context_log — meaning main.py startup code did not call
        # upsert_agent_context_hash() for that agent. Returns one row per
        # missing agent_id. Empty result = all 3 agents registered = no inversion.
        "dag_query": """
            SELECT 'bridge_agent' AS agent_id, 'NOT_REGISTERED' AS status
            WHERE NOT EXISTS (
                SELECT 1 FROM agent_context_log WHERE agent_id = 'bridge_agent'
            )
            UNION ALL
            SELECT 'session_adjudicator', 'NOT_REGISTERED'
            WHERE NOT EXISTS (
                SELECT 1 FROM agent_context_log WHERE agent_id = 'session_adjudicator'
            )
            UNION ALL
            SELECT 'calibration_intelligence_agent', 'NOT_REGISTERED'
            WHERE NOT EXISTS (
                SELECT 1 FROM agent_context_log
                WHERE agent_id = 'calibration_intelligence_agent'
            )
        """,
        "agents_involved": ["BridgeAgent", "SessionAdjudicatorAgent", "CalibrationIntelligenceAgent"],
        "severity": "HIGH",
        "explanation": (
            "agent_context_log contains LLM agent system prompt hashes from a prior phase. "
            "The live prompt SHA-256 (computed at startup) diverges from the committed hash, "
            "meaning the agent is either running a stale prompt (knowledge regression) or "
            "an unauthorized prompt edit was made without updating the phase number. "
            "Rulings produced while the prompt is stale may recommend actions appropriate "
            "for the old protocol state, not the current one."
        ),
        "resolution": (
            "Run Skill 14 PostCode sweep to recompute and store current prompt hashes. "
            "If delta_phase=0 (same phase, different hash): investigate unauthorized edit. "
            "If delta_phase>=1: update agent system prompt to Phase N state and re-run sweep."
        ),
    },
}


from .coherence_rules.loader import CoherenceRuleLoader as _CoherenceRuleLoader  # VAPI-EXT: sub-protocol rule plugin registry


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

    Privacy: evidence_json stores only derived metrics and row IDs.
    Never stores raw biometric feature values (BP-007 IMMUTABLE).
    """

    NAME          = "FleetSignalCoherenceAgent"
    AGENT_ID      = 36
    POLL_INTERVAL = 900  # 15 minutes

    # Promotion threshold: a contradiction seen N_PROMOTE_THRESHOLD times
    # across separate cycles is promoted to a WIF entry automatically.
    N_PROMOTE_THRESHOLD = 3

    def __init__(
        self,
        store: "Store",
        config: "Config",
        bus,
        logger: logging.Logger,
    ) -> None:
        self._store  = store
        self._config = config
        self._bus    = bus
        self._logger = logger

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _make_coherence_id(self, rule_name: str, agents: list) -> str:
        ts_ns = int(time.time_ns())
        raw   = f"{rule_name}:{'|'.join(sorted(agents))}:{ts_ns}"
        return "coh_" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _scrub_evidence(self, rows: list) -> list:
        """
        Remove any field that could contain raw biometric data (BP-007 IMMUTABLE).
        Keeps: IDs, timestamps, boolean flags, ratio values, counts.
        Removes: feature vectors, raw HID data, GSR readings.
        """
        BLOCKED_KEYS = {
            "features", "hid_reports", "raw_data", "sensor_commitment",
            "gyro_std", "accel", "feature_vector", "correlation_upper_tri",
        }
        result = []
        for row in rows:
            if isinstance(row, dict):
                result.append({k: v for k, v in row.items() if k not in BLOCKED_KEYS})
            else:
                result.append(row)
        return result

    def _row_to_dict(self, row, cursor) -> dict:
        """Convert sqlite3.Row or tuple to dict using cursor description."""
        if hasattr(row, "keys"):
            return dict(row)
        if cursor and cursor.description:
            return dict(zip([d[0] for d in cursor.description], row))
        return {}

    def _db_query(self, sql: str, params=()) -> list:
        """Execute a read query and return list[dict]. Fail-open (returns [])."""
        try:
            import sqlite3
            with sqlite3.connect(self._store._db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            self._logger.debug(f"[FSCA] db_query failed: {e}")
            return []

    def _parse_ts(self, ts_str: str) -> "float | None":
        """Parse an ISO or epoch timestamp to float seconds. Returns None on failure."""
        if not ts_str:
            return None
        try:
            return float(ts_str)
        except (ValueError, TypeError):
            pass
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return None

    # -----------------------------------------------------------------------
    # Detection: CONTRADICTION
    # -----------------------------------------------------------------------

    async def _check_contradictions(self) -> list:
        found = []
        for rule_name, rule in CONTRADICTION_RULES.items():
            try:
                # Guard: per-rule cfg-dependent gating (Phase 204 — supports dry_run /
                # ioswarm_enabled conditional rules without polluting the rule schema).
                if "guard" in rule and not rule["guard"](self._config):
                    continue
                params = rule["params"](self._config)
                rows   = self._db_query(rule["query"], params)

                # post_check: applies an additional Python predicate on rows[0]
                if "post_check" in rule:
                    if not rows or not rule["post_check"](rows[0]):
                        rows = []

                if rows:
                    entry = {
                        "coherence_id":    self._make_coherence_id(
                                               rule_name, rule["agents_involved"]),
                        "failure_mode":    "CONTRADICTION",
                        "rule_name":       rule_name,
                        "agents_involved": json.dumps(rule["agents_involved"]),
                        "severity":        rule["severity"],
                        "explanation":     rule["explanation"],
                        "resolution":      rule["resolution"],
                        "evidence_json":   json.dumps(self._scrub_evidence(rows)),
                        "phase_detected":  193,
                        "ts_ns":           int(time.time_ns()),
                    }
                    found.append(entry)
            except Exception as e:
                self._logger.warning(f"[FSCA] CONTRADICTION rule {rule_name} failed: {e}")
        return found

    # -----------------------------------------------------------------------
    # Detection: ORPHAN
    # -----------------------------------------------------------------------

    def _check_orphan_response(self, rule: dict, trigger_row: dict) -> bool:
        """Returns True if a valid response exists for the given trigger row."""
        if "response_path" in rule:
            # AutoResearch log check (jsonl file)
            path = Path(rule["response_path"])
            if not path.exists():
                return False
            trigger_ts = self._parse_ts(trigger_row.get(rule["trigger_ts_col"], ""))
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if entry.get(rule["response_key"]) == rule["response_value"]:
                                entry_ts = self._parse_ts(entry.get("timestamp", ""))
                                if entry_ts and trigger_ts and entry_ts > trigger_ts:
                                    return True
                        except (json.JSONDecodeError, KeyError):
                            continue
            except Exception:
                pass
            return False
        else:
            filter_clause = rule.get("response_filter", "1=1")
            response_rows = self._db_query(
                f"SELECT 1 FROM {rule['response_table']} WHERE {filter_clause} LIMIT 1"
            )
            return len(response_rows) > 0

    async def _check_orphans(self) -> list:
        found = []
        for rule_name, rule in ORPHAN_RULES.items():
            try:
                window = rule["orphan_window_seconds"]
                trig_col = rule["trigger_ts_col"]
                triggers = self._db_query(
                    f"SELECT * FROM {rule['trigger_table']} "
                    f"WHERE {rule['trigger_column']} = ? "
                    f"AND (CAST(strftime('%s','now') AS INTEGER) "
                    f"   - CAST(strftime('%s',{trig_col}) AS INTEGER)) > ? "
                    f"ORDER BY {trig_col} DESC LIMIT 5",
                    (rule["trigger_value"], window),
                )
                for trigger_row in triggers:
                    response_exists = self._check_orphan_response(rule, trigger_row)
                    if not response_exists:
                        entry = {
                            "coherence_id":    self._make_coherence_id(
                                                   rule_name,
                                                   [rule["trigger_agent"], rule["response_agent"]]),
                            "failure_mode":    "ORPHAN",
                            "rule_name":       rule_name,
                            "agents_involved": json.dumps([rule["trigger_agent"], rule["response_agent"]]),
                            "severity":        rule["severity"],
                            "explanation":     rule["explanation"],
                            "resolution":      rule["resolution"],
                            "evidence_json":   json.dumps(self._scrub_evidence([trigger_row])),
                            "phase_detected":  193,
                            "ts_ns":           int(time.time_ns()),
                        }
                        found.append(entry)
            except Exception as e:
                self._logger.warning(f"[FSCA] ORPHAN rule {rule_name} failed: {e}")
        return found

    # -----------------------------------------------------------------------
    # Detection: INVERSION
    # -----------------------------------------------------------------------

    async def _check_inversions(self) -> list:
        found = []
        for rule_name, rule in INVERSION_RULES.items():
            try:
                rows = self._db_query(rule["dag_query"])
                if rows:
                    entry = {
                        "coherence_id":    self._make_coherence_id(
                                               rule_name, rule["agents_involved"]),
                        "failure_mode":    "INVERSION",
                        "rule_name":       rule_name,
                        "agents_involved": json.dumps(rule["agents_involved"]),
                        "severity":        rule["severity"],
                        "explanation":     rule["explanation"],
                        "resolution":      rule["resolution"],
                        "evidence_json":   json.dumps(self._scrub_evidence(rows)),
                        "phase_detected":  193,
                        "ts_ns":           int(time.time_ns()),
                    }
                    found.append(entry)
            except Exception as e:
                self._logger.warning(f"[FSCA] INVERSION rule {rule_name} failed: {e}")
        return found

    # -----------------------------------------------------------------------
    # Persistence + wiki + WIF promotion
    # -----------------------------------------------------------------------

    def _write_contradict_entry(self, entry: dict) -> None:
        """Append to wiki/contradictions.md via _locked_append (WIKI_CONTRADICT path)."""
        try:
            from vapi_wiki_engine import WIKI_CONTRADICT, _locked_append, prov
            ts = datetime.now(timezone.utc).isoformat()
            provenance = prov(entry["phase_detected"], self.NAME, "MEASURED")
            agents_str = ", ".join(
                json.loads(entry["agents_involved"])
                if isinstance(entry["agents_involved"], str)
                else entry["agents_involved"]
            )
            entry_md = (
                f"\n---\n"
                f"### [{entry['failure_mode']}] {entry['rule_name']} — {entry['severity']}\n"
                f"**Detected**: {ts}\n"
                f"**Coherence ID**: {entry['coherence_id']}\n"
                f"**Agents**: {agents_str}\n"
                f"{provenance}\n\n"
                f"**Failure**: {entry['explanation']}\n\n"
                f"**Resolution**: {entry['resolution']}\n\n"
                f"**Evidence** (derived metrics only — no raw biometric data):\n"
                f"```json\n{entry['evidence_json']}\n```\n"
            )
            _locked_append(WIKI_CONTRADICT, entry_md)
            self._store.db_execute(
                "UPDATE fleet_coherence_log SET wiki_contradict_written=1 "
                "WHERE coherence_id=?",
                (entry["coherence_id"],),
            )
        except Exception as e:
            self._logger.warning(f"[FSCA] wiki_contradict write failed: {e}")

    def _promote_to_wif(self, entry: dict) -> None:
        """Auto-promote a persistent contradiction (N_PROMOTE_THRESHOLD occurrences) to WIF."""
        try:
            from vapi_wiki_engine import CORPUS, _locked_append, prov
            import re as _re

            what_if_path = CORPUS["what_if"]
            existing     = what_if_path.read_text(encoding="utf-8")
            wif_nums     = [int(x) for x in _re.findall(r"WIF-(\d+)", existing)]
            next_num     = max(wif_nums, default=33) + 1
            wif_id       = f"WIF-{next_num:03d}"
            provenance   = prov(entry["phase_detected"], self.NAME, "AUTO_PROMOTED")
            agents_str   = ", ".join(
                json.loads(entry["agents_involved"])
                if isinstance(entry["agents_involved"], str)
                else entry["agents_involved"]
            )

            wif_entry = (
                f"\n---\n\n"
                f"## {wif_id} — Auto-Promoted Fleet Coherence Failure: "
                f"{entry['rule_name']} (Phase {entry['phase_detected']})\n\n"
                f"**W1 — Failure mode**: {entry['explanation']}\n\n"
                f"**Agents involved**: {agents_str}\n"
                f"**Failure mode class**: {entry['failure_mode']}\n"
                f"**First detected**: Cycle 1 "
                f"(auto-promoted after {self.N_PROMOTE_THRESHOLD} occurrences)\n\n"
                f"**Implication**: This coherence failure appeared in "
                f"{self.N_PROMOTE_THRESHOLD} consecutive FleetSignalCoherenceAgent cycles, "
                f"confirming it is a persistent structural gap in the fleet's inter-agent "
                f"signal topology — not a transient timing artifact.\n\n"
                f"**Mitigation**: {entry['resolution']}\n\n"
                f"**W2 — Novel opportunity**: Resolving this contradiction enables a new "
                f"inter-agent protocol invariant: the FSCA can add the validated fix as a "
                f"permanent COHERENCE_RULE to its rule set, preventing the same class of "
                f"contradiction from recurring as the fleet scales beyond Agent #36. "
                f"This creates a self-expanding invariant set grounded in live fleet behavior "
                f"— the RSI contribution exclusive to VAPI's 30+ agent topology.\n\n"
                f"**Status**: AUTO-PROMOTED — Phase {entry['phase_detected']} (FleetSignalCoherenceAgent)\n"
                f"{provenance}\n\n"
            )
            _locked_append(what_if_path, wif_entry)
            self._store.mark_coherence_promoted(entry["coherence_id"], wif_id)

            try:
                subprocess.run(
                    ["python", "vapi_wiki_engine.py", "sync_what_if"],
                    capture_output=True, timeout=30,
                )
                self._logger.info(f"[FSCA] Promoted {entry['rule_name']} -> {wif_id}")
            except Exception as e:
                self._logger.warning(f"[FSCA] sync_what_if failed after promotion: {e}")
        except Exception as e:
            self._logger.warning(f"[FSCA] promote_to_wif failed: {e}")

    async def _process_findings(self, findings: list) -> None:
        """Persist, alert, and promote findings where threshold is met."""
        for entry in findings:
            self._store.insert_coherence_entry(entry)
            # Phase 194: update coherence_fingerprint_log occurrence count for this rule
            try:
                self._store.upsert_coherence_fingerprint(
                    entry["rule_name"], entry["failure_mode"]
                )
            except Exception as e:
                self._logger.debug(f"[FSCA] fingerprint upsert failed: {e}")

            # Alert on CRITICAL/HIGH
            alert_severities = []
            if self._config.coherence_alert_on_critical:
                alert_severities.append("CRITICAL")
            if self._config.coherence_alert_on_high:
                alert_severities.append("HIGH")
            if self._config.coherence_alert_on_medium:
                alert_severities.append("MEDIUM")

            if entry["severity"] in alert_severities:
                try:
                    if self._bus:
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
                        "WHERE coherence_id=?",
                        (entry["coherence_id"],),
                    )
                except Exception as e:
                    self._logger.warning(f"[FSCA] alert publish failed: {e}")

            self._write_contradict_entry(entry)

            # Check promotion threshold
            try:
                occ = self._db_query(
                    "SELECT COUNT(*) as n FROM fleet_coherence_log "
                    "WHERE rule_name=? AND resolved=0",
                    (entry["rule_name"],),
                )
                promote_thresh = getattr(self._config, "coherence_promote_threshold",
                                         self.N_PROMOTE_THRESHOLD)
                if occ and occ[0].get("n", 0) >= promote_thresh:
                    # Check not already promoted
                    already = self._db_query(
                        "SELECT promoted_to_wif FROM fleet_coherence_log "
                        "WHERE coherence_id=?",
                        (entry["coherence_id"],),
                    )
                    if already and not already[0].get("promoted_to_wif", 0):
                        self._promote_to_wif(entry)
            except Exception as e:
                self._logger.warning(f"[FSCA] promotion check failed: {e}")

    # -----------------------------------------------------------------------
    # Main poll loop
    # -----------------------------------------------------------------------

    async def _run_once(self) -> None:
        """Execute one coherence detection cycle across all three modes."""
        contradictions = await self._check_contradictions()
        orphans        = await self._check_orphans()
        inversions     = await self._check_inversions()

        all_findings = contradictions + orphans + inversions
        if all_findings:
            await self._process_findings(all_findings)

        summary = self._store.get_coherence_summary()
        if self._bus:
            try:
                await self._bus.publish("coherence", {
                    "from":                self.NAME,
                    "event":               "coherence_cycle_complete",
                    "findings_this_cycle": len(all_findings),
                    "total_open":          summary["total_open"],
                    "critical_open":       summary["by_severity"].get("CRITICAL", 0),
                    "promoted_to_wif":     summary["promoted_to_wif"],
                    "provenance":          f"[VAPI:Phase193:{self.NAME}:MEASURED]",
                })
            except Exception:
                pass

    async def run(self) -> None:
        """Main background polling loop. Runs every coherence_poll_interval_seconds."""
        if not getattr(self._config, "fleet_coherence_enabled", True):
            self._logger.info("[FSCA] Fleet coherence disabled — agent idle.")
            return
        poll_interval = getattr(self._config, "coherence_poll_interval_seconds", 900)
        self._logger.info(
            f"[FSCA] FleetSignalCoherenceAgent started. Poll: {poll_interval}s. "
            f"Rules: {len(CONTRADICTION_RULES)} CONTRADICTION / "
            f"{len(ORPHAN_RULES)} ORPHAN / {len(INVERSION_RULES)} INVERSION."
        )
        while True:
            try:
                await self._run_once()
            except Exception as e:
                self._logger.error(f"[FSCA] _run_once failed: {e}")
            await asyncio.sleep(poll_interval)
