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
# CONTRADICTION_RULES — 29 rules (Phase O5-MYTHOS-MINIMAL M.3 added MYTHOS_FROZEN_REGION_DRIFT + MYTHOS_ASYNC_HAZARD, 27→29; prior: Phase 238 Step I-AUTOLOOP-2 added LISTING_TIER_DRIFT + CONSENT_REVOKED_LISTING_ACTIVE; Phase O1 C6 added BUNDLE_HASH_DRIFT_DETECTED + SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED; Phase O4 27th CFSS_LANE_AUTHORITY_DRIFT)
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

    "ALLOWLIST_CHANGE_WITHOUT_GOVERNANCE": {
        # Phase 224: WIF — invariant drift attack surface closure.
        # Fires when allowlist_change_log contains an entry with reason_from_gate_log IS NULL.
        # This means INVARIANTS_ALLOWLIST.json was modified without a matching governance event
        # in invariant_gate_log within 60 seconds — indicating a direct file edit, git merge,
        # or unlogged --generate bypassing the mandatory --reason flag.
        #
        # Silent allowlist changes are a class of invariant drift attack: a subtle semantic
        # change that passes CI can be introduced without any operator audit trail.
        "query": """
            SELECT id, previous_hash, new_hash, detected_at, reason_from_gate_log
            FROM allowlist_change_log
            WHERE reason_from_gate_log IS NULL
            ORDER BY id DESC LIMIT 1
        """,
        "params": lambda cfg: (),
        "agents_involved": ["ProtocolCoherenceAgent", "VAPIInvariantGate"],
        "severity": "CRITICAL",
        "explanation": (
            "INVARIANTS_ALLOWLIST.json was modified without a matching governance event "
            "in invariant_gate_log within 60 seconds. This means the allowlist was changed "
            "by direct file edit, git merge, or an unlogged --generate. Every allowlist "
            "change must be logged with --reason. Silent allowlist changes are a class of "
            "invariant drift attack: a subtle semantic change that passes CI can be "
            "introduced without any operator audit trail."
        ),
        "resolution": (
            "Investigate git log for allowlist changes without accompanying governance events. "
            "If the change is legitimate, re-run: "
            "python scripts/vapi_invariant_gate.py --generate "
            "--reason '<category>: <description>'"
        ),
    },

    "GOVERNANCE_PROVENANCE_ANCHOR_DRIFT": {
        # Phase 227: On-Chain Anchor Cross-Check — 10th CONTRADICTION rule.
        # Fires when the live SQLite governance_provenance_chain latest hash diverges
        # from the governance_provenance_hash stored in the most recent protocol_coherence_log
        # row (which is written by ProtocolCoherenceAgent._anchor_cycle() on each cycle).
        #
        # This detects direct SQLite writes to governance_provenance_chain: if an adversary
        # with filesystem access inserts a consistently-hashed row, the live chain appears
        # intact (GOVERNANCE_CHAIN_BROKEN won't fire) but the on-chain anchor value won't
        # match — the discrepancy is detected at the next anchor cycle (default every 1h).
        #
        # Only fires when protocol_coherence_log has a non-empty governance_provenance_hash
        # (i.e., Phase 227 anchorCoherenceWithProvenance has been used at least once).
        # Empty governance_provenance_hash in protocol_coherence_log → rule is silent.
        "query": """
            SELECT gpc.governance_provenance_hash AS live_hash,
                   pcl.governance_provenance_hash AS anchored_hash
            FROM governance_provenance_chain gpc
            JOIN protocol_coherence_log pcl
              ON pcl.id = (SELECT MAX(id) FROM protocol_coherence_log
                            WHERE governance_provenance_hash != '')
            WHERE gpc.id = (SELECT MAX(id) FROM governance_provenance_chain)
              AND pcl.governance_provenance_hash != ''
              AND gpc.governance_provenance_hash != pcl.governance_provenance_hash
            LIMIT 1
        """,
        "params": lambda cfg: (),
        "agents_involved": ["ProtocolCoherenceAgent", "VAPIInvariantGate"],
        "severity": "CRITICAL",
        "explanation": (
            "The live governance_provenance_chain latest hash does not match the "
            "governance_provenance_hash stored in the most recent protocol_coherence_log "
            "anchor. This means the SQLite governance chain was modified after the last "
            "on-chain anchor cycle — either by a direct database write (filesystem access "
            "required, no API key needed) or by a race condition in the anchor pipeline. "
            "GOVERNANCE_CHAIN_BROKEN detects broken hash links but cannot detect a "
            "consistently-computed fake insertion. This cross-check closes that gap by "
            "comparing the live SQLite state against the immutable on-chain record."
        ),
        "resolution": (
            "Run GET /agent/allowlist-governance-history to inspect the full chain. "
            "Compare the latest governance_provenance_hash against the on-chain value "
            "from GET /agent/protocol-coherence-status. "
            "If the chain was tampered, trigger an anchor cycle: set "
            "protocol_coherence_enabled=True and wait for the next _anchor_cycle() "
            "to write the current live hash. If the discrepancy is spurious (race condition "
            "during anchor write), it will self-resolve on the next anchor cycle."
        ),
    },

    "AUTO_TRIGGER_RATE_LIMIT_VIOLATION": {
        # Phase 235-AUTO-TRIGGER: 12th CONTRADICTION rule.
        # Fires when more than 12 ruling_request events from
        # source_agent='session_boundary_detector_agent' occur within a
        # rolling 1-hour window.
        #
        # Math: at the steady-state 5-minute trigger interval (matches
        # SessionAdjudicator's poll cadence), the agent fires at most 12
        # times per hour.  Anything above that ceiling indicates either:
        #   (a) auto_trigger_min_interval_s was lowered without updating
        #       this rule (config drift) — operator should restore default
        #       300s, OR
        #   (b) the agent is in a tight retry loop on a malformed event —
        #       investigate logs for write_agent_event errors, OR
        #   (c) an adversary is publishing crafted ruling_request events
        #       to inflate chain_length without genuine gameplay — rotate
        #       OPERATOR_API_KEY and audit /agent/adjudicate access.
        #
        # CRITICAL severity: any of the three causes warrants immediate
        # halt of auto-triggering pending review.  The W1 mitigation for
        # the auto-trigger phase relies on this rate-limit holding.
        "query": """
            SELECT COUNT(*) AS n
            FROM agent_events
            WHERE event_type = 'ruling_request'
              AND source_agent = 'session_boundary_detector_agent'
              AND (CAST(strftime('%s','now') AS REAL)
                   - CAST(created_at AS REAL)) < 3600
        """,
        "params": lambda cfg: (),
        # post_check: COUNT(*) always returns one row; the rule only fires
        # when that count exceeds the steady-state ceiling of 12 events/hour.
        "post_check": lambda row: int(row.get("n", 0)) > 12,
        "agents_involved": ["SessionBoundaryDetectorAgent", "SessionAdjudicator"],
        "severity": "CRITICAL",
        "explanation": (
            "agent_events shows more than 12 ruling_request events from "
            "session_boundary_detector_agent in the last hour. The agent "
            "is throttled to one trigger per auto_trigger_min_interval_s "
            "(default 300s = 12/hr ceiling). Exceeding this indicates "
            "config drift, a tight retry loop, or an adversarial event "
            "injection attempting to inflate chain_length without genuine "
            "gameplay. Auto-triggering should be halted pending review."
        ),
        "resolution": (
            "1. Verify cfg.auto_trigger_min_interval_s == 300 (default). "
            "If lowered, restore to 300 and update this rule's per-hour "
            "ceiling accordingly. "
            "2. Inspect bridge log for SessionBoundaryDetectorAgent "
            "errors around write_agent_event — a tight retry loop will "
            "show repeated 'write_agent_event failed' WARNING entries. "
            "3. Set AUTO_TRIGGER_ENABLED=false in bridge/.env and restart "
            "the bridge to halt auto-triggering. "
            "4. Audit recent /agent/adjudicate access via the operator "
            "audit log (operator_audit_log table); rotate OPERATOR_API_KEY "
            "if suspicious. "
            "5. Review the corresponding ruling_validation_log rows — "
            "GIC stamps from rapid-fire events still chain cryptographically "
            "but the count claim is suspect; the chain may need to be "
            "audited for correlation with actual gameplay records."
        ),
    },
    "INVARIANT_CHANGE_WITHOUT_VHP": {
        # Phase 228: VHP-Gated Invariant Change — 11th CONTRADICTION rule.
        # Fires when an invariant_gate_log row with reason_category='invariant_change'
        # has an empty vhp_token_id within the last 24 hours.
        #
        # The highest-impact governance category (modifying frozen protocol invariant digests)
        # requires biometric presence when vhp_gated_invariant_change_enabled=True.
        # An empty vhp_token_id on an invariant_change row means either: (a) the event
        # was recorded before Phase 228 deployed (expected pre-228), or (b) the gate was
        # bypassed — a direct POST to /agent/allowlist-governance-event without vhp_token_id
        # field when gating was expected to be enforced.
        #
        # Severity HIGH (not CRITICAL) because the default is
        # vhp_gated_invariant_change_enabled=False; absence is expected on new deployments.
        "query": """
            SELECT id, reason_category, reason_text, vhp_token_id, created_at
            FROM invariant_gate_log
            WHERE reason_category = 'invariant_change'
              AND (vhp_token_id IS NULL OR vhp_token_id = '')
              AND (CAST(strftime('%s','now') AS INTEGER)
                   - CAST(created_at AS INTEGER)) < 86400
            ORDER BY id DESC
            LIMIT 1
        """,
        "params": lambda cfg: (),
        "agents_involved": ["VAPIInvariantGate", "BiometricGovernanceAgent"],
        "severity": "HIGH",
        "explanation": (
            "invariant_gate_log has an invariant_change governance event with an empty "
            "vhp_token_id recorded within the last 24 hours. "
            "When vhp_gated_invariant_change_enabled=True, every invariant_change event "
            "must include the operator's live VHP token ID (biometric presence proof). "
            "An empty vhp_token_id means either the gate is not yet enabled (expected), "
            "or the event bypassed the gate (investigate immediately). "
            "The highest-impact governance category (modifying frozen protocol invariant "
            "digests) currently lacks biometric authentication on this event."
        ),
        "resolution": (
            "If vhp_gated_invariant_change_enabled=False (default): enable the gate by "
            "setting VHP_GATED_INVARIANT_CHANGE_ENABLED=true in bridge/.env and restarting "
            "the bridge. Future invariant_change events will require a valid vhp_token_id. "
            "If vhp_gated_invariant_change_enabled=True: the event bypassed the gate — "
            "audit POST /agent/allowlist-governance-event access logs for the unauthorized "
            "request origin. Rotate the operator API key and review the invariant digests "
            "in .github/INVARIANTS_ALLOWLIST.json for tampering. "
            "Run: python scripts/vapi_invariant_gate.py (no --generate) to verify current digests."
        ),
    },

    # Phase 237-EXTEND — CONSENT_REVOKED_BUT_DATA_FLOWING
    # Detects GDPR Art.17 violation candidate: a device has revoked consent
    # in consent_ledger but the records table (PoAC ingestion surface) still
    # contains rows created AFTER the revocation timestamp. This is the
    # cleanest cross-agent contradiction FSCA can catch — bridge says
    # "consent revoked", PoAC ingestion says "record stored", and temporal
    # ordering proves the record post-dates the revocation.
    #
    # records.created_at and consent_ledger.revoked_at are both REAL (unix
    # epoch seconds) so direct comparison is valid.
    "CONSENT_REVOKED_BUT_DATA_FLOWING": {
        "query": """
            SELECT c.device_id,
                   c.consent_type AS category,
                   c.revoked_at,
                   r.record_hash AS record_hash,
                   r.created_at  AS record_created
            FROM consent_ledger c
            LEFT JOIN records r
              ON r.device_id = c.device_id
             AND r.created_at > c.revoked_at
            WHERE c.revoked_at IS NOT NULL
              AND r.record_hash IS NOT NULL
            ORDER BY c.revoked_at DESC LIMIT 5
        """,
        "params": lambda cfg: (),
        "agents_involved": [
            "bridge",
            "BiometricPrivacyComplianceAgent",
            "ConsentLedger",
        ],
        "severity": "HIGH",
        "explanation": (
            "Device has revoked consent (consent_ledger.revoked_at IS NOT NULL) "
            "but PoAC record(s) appear in `records` with created_at AFTER the "
            "revocation timestamp. Under GDPR Art.17 (right to erasure) and "
            "BIPA, biometric data MUST stop flowing the moment consent is "
            "withdrawn. A record post-dating the revocation is an audit-trail "
            "anomaly: either the bridge consent gate did not block ingestion "
            "(Phase 161 gap), or the timestamp ordering is corrupted (clock "
            "skew / NTP backstep), or the operator manually inserted a row. "
            "Phase 237's per-category _check_consent_gate(category=...) gate "
            "should have prevented this."
        ),
        "resolution": (
            "IMMEDIATE: trigger the Phase 160 erasure pipeline for the affected "
            "device_id(s): call store.anonymize_device_records(device_id) to "
            "redact the offending `records` rows. Then audit "
            "consent_gate_violation_log for the same device_id+category pair "
            "to confirm whether the bridge gate fired or was bypassed. If the "
            "gate did not fire, this is a Phase 237 escape and warrants a "
            "hotfix to ensure record-ingestion paths call _check_consent_gate. "
            "If clock skew is suspected, verify session_adjudicator_validator "
            "monotonicity guard."
        ),
    },

    # Phase O1 C6 — FSCA wiring of drift findings.
    # CedarDriftSweeper (Phase O1 C4) writes findings to operator_agent_drift_log.
    # These rules query that log within a 1-hour window. When the sweep stops
    # firing (drift resolved), older rows age out and FSCA stops flagging.
    # When drift persists, FSCA keeps producing the same coherence_id (deterministic
    # from rule_name + agents_involved) so it appears as a single active
    # contradiction in the FSCA output, not many duplicates.
    "BUNDLE_HASH_DRIFT_DETECTED": {
        "query": """
            SELECT id, agent_id, drift_type, expected_value, actual_value,
                   bundle_path, detected_at, evidence_json
            FROM operator_agent_drift_log
            WHERE drift_type = 'BUNDLE_HASH_DRIFT'
              AND detected_at >= ?
            ORDER BY detected_at DESC LIMIT 5
        """,
        "params": lambda cfg: (time.time() - 3600,),
        "agents_involved": [
            "AnchorSentry",
            "Guardian",
            "Curator",
            "CedarDriftSweeper",
        ],
        "severity": "HIGH",
        "explanation": (
            "CedarDriftSweeper detected BUNDLE_HASH_DRIFT — at least one "
            "operator-agent's anchored Cedar bundle file no longer hashes to "
            "the on-chain anchored Merkle root. Possible causes: (a) bundle "
            "JSON edited post-anchor without re-anchoring, (b) bundle file "
            "replaced or corrupted on disk, (c) cedar_parser regression "
            "broke deterministic Merkle root computation. Operator policy "
            "decisions made under this bundle may not match the on-chain "
            "governance record — INV-OPERATOR-AGENT-005 (Merkle recomputed "
            "every evaluation, never cached) means callers will see the "
            "ON-DISK root, not the anchored one."
        ),
        "resolution": (
            "Either restore the bundle to its anchored content (recover from "
            "git history; canonical source is the bundle_path in evidence_json) "
            "OR re-anchor the modified bundle via "
            "POST /operator/anchor-cedar-bundle with reason ≥10 chars. "
            "If cedar_parser regression suspected, run "
            "scripts/cedar_bundle_validate.py against the bundle to compare "
            "computed vs anchored Merkle root."
        ),
    },

    "SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED": {
        "query": """
            SELECT id, agent_id, drift_type, expected_value, actual_value,
                   detected_at, evidence_json
            FROM operator_agent_drift_log
            WHERE drift_type = 'SCOPE_HASH_GOVERNANCE_DRIFT'
              AND detected_at >= ?
            ORDER BY detected_at DESC LIMIT 5
        """,
        "params": lambda cfg: (time.time() - 3600,),
        "agents_involved": [
            "AnchorSentry",
            "Guardian",
            "Curator",
            "CedarDriftSweeper",
        ],
        "severity": "CRITICAL",
        "explanation": (
            "CedarDriftSweeper detected SCOPE_HASH_GOVERNANCE_DRIFT — "
            "AgentScope.scopeRoot != AgentRegistry.getAgent.scopeHash for "
            "this operator agent. The operational and governance views of "
            "the same agent's policy bundle have diverged on-chain. "
            "Possible causes: (a) partial-success deploy where one of the "
            "Phase O1 C1 D4 dual-anchor txs landed but the other did not, "
            "(b) external setAgentScopeRoot or updateAgentScope call by "
            "another contract owner that bypassed the dual-anchor invariant, "
            "(c) chain reorg discarded one of the dual-anchor txs. "
            "CRITICAL severity: agent actions evaluated under operational "
            "scope may be denied or accepted in conflict with governance "
            "intent."
        ),
        "resolution": (
            "Inspect both contracts via cast call AgentScope.getScopeRoot + "
            "AgentRegistry.getAgent. Re-run the dual-anchor via "
            "POST /operator/anchor-cedar-bundle to restore parity. If "
            "governance has the newer value, locate the bundle that produced "
            "the governance hash and re-anchor it to operational. If "
            "operational is newer, governance must catch up via separate "
            "AgentRegistry.updateAgentScope call. Phase O1 C1 D4 dual-anchor "
            "must be re-asserted before any further policy decisions are made."
        ),
    },

    # Phase 238 Step I-AUTOLOOP-2: Curator drift contradiction rules.
    # The Curator (third Operator Initiative agent) writes review verdicts
    # to curator_listing_review_log.  These rules query that log within a
    # 1-hour window and surface specific verdicts as FSCA contradictions.
    # Rule 1 — LISTING_TIER_DRIFT (HIGH): a seller's declared tier
    # disagrees with the cryptographically-derived tier (anchor count on
    # AdjudicationRegistry).  This is detected by Curator's
    # FLAGGED_TIER_MISMATCH verdict + tier_changed=1.
    # Rule 2 — CONSENT_REVOKED_LISTING_ACTIVE (CRITICAL — GDPR Art.17
    # candidate): Curator detected a listing whose MARKETPLACE consent
    # bit (Phase 237 CONSENT bit 3) is cleared, while the listing is still
    # active in marketplace_listing_log.  This is the primary regulatory
    # surveillance primitive — GDPR Art.17 right-to-erasure obligation
    # surfaces here within ≤5 min of consent revocation (Curator
    # autonomous loop cadence) + ≤15 min of FSCA poll cadence.
    "LISTING_TIER_DRIFT": {
        "query": """
            SELECT id, listing_commitment, declared_tier, tier_at_review_time,
                   reason_detail, ts_ns
            FROM curator_listing_review_log
            WHERE verdict = 'FLAGGED_TIER_MISMATCH'
              AND tier_changed = 1
              AND ts_ns >= ?
            ORDER BY ts_ns DESC LIMIT 5
        """,
        "params": lambda cfg: (int((time.time() - 3600) * 1e9),),
        "agents_involved": [
            "Curator",
            "DataMarketplace",
        ],
        "severity": "HIGH",
        "explanation": (
            "Curator detected one or more marketplace listings whose declared "
            "tier (derived from data_class) disagrees with the on-chain anchor "
            "count.  Either the seller over-claimed (declared Premium but "
            "fewer anchors recorded on AdjudicationRegistry) or the seller "
            "under-claimed (declared Basic but all four anchors actually "
            "present).  Tier multiplier (1.0×/1.5×/2.0×/3.0×) is "
            "cryptographically computed from on-chain isRecorded() reads, "
            "not seller-attested.  Operator audit needed to confirm whether "
            "the listing should be re-anchored (anchors missing) or "
            "re-classified (data_class wrong)."
        ),
        "resolution": (
            "Inspect curator_listing_review_log row + "
            "marketplace_listing_log row via "
            "GET /agent/curator-review/{commitment_hex} and "
            "GET /agent/marketplace-listing/{commitment_hex}.  If anchors "
            "missing, advise seller to re-anchor before re-listing.  If "
            "data_class incorrect, listing should be suspended (Phase O3 "
            "ENFORCE — operator-only in O1) and re-created with correct "
            "tier intent."
        ),
    },

    "CONSENT_REVOKED_LISTING_ACTIVE": {
        "query": """
            SELECT id, listing_commitment, reason_detail, ts_ns
            FROM curator_listing_review_log
            WHERE verdict = 'FLAGGED_CONSENT_AMBIGUOUS'
              AND ts_ns >= ?
            ORDER BY ts_ns DESC LIMIT 5
        """,
        "params": lambda cfg: (int((time.time() - 3600) * 1e9),),
        "agents_involved": [
            "Curator",
            "BiometricPrivacyComplianceAgent",
            "ConsentLedger",
        ],
        "severity": "CRITICAL",
        "explanation": (
            "Curator detected listing(s) where the MARKETPLACE consent bit "
            "(Phase 237 CONSENT bit 3) is cleared in consent_bitmask, yet "
            "the listing remains active in marketplace_listing_log.  This "
            "is a candidate GDPR Art.17 (right-to-erasure) violation — the "
            "gamer revoked consent for marketplace data sharing but their "
            "listing has not been suspended.  CRITICAL severity because "
            "regulatory exposure compounds with each subsequent buyer "
            "purchase against the listing.  Phase 160 erasure pipeline + "
            "BiometricPrivacyComplianceAgent (BP-001 + BP-007) provide the "
            "remediation primitives."
        ),
        "resolution": (
            "Operator: (1) verify the consent revocation via "
            "GET /agent/gamer-consent-status?device_id=<seller>&category=3; "
            "(2) if consent IS revoked, suspend the listing on-chain via "
            "VAPIDataMarketplaceListings.suspendListing(commitment) — "
            "Step H deploy required first; (3) trigger Phase 160 "
            "erasure pipeline if any buyer access is recorded; (4) update "
            "operator_audit_log with the resolution.  Curator graduated to "
            "O2_SUGGEST will surface this remediation path automatically; "
            "O3_ENFORCE will execute steps 1-2 autonomously."
        ),
    },

    # Phase O2-FSCA-RULES (2026-05-10) — three new rules surfacing operator-
    # initiative drafting layer health.  Drafts persist in operator_agent_drafts
    # (Phase 1005 schema); these rules query that table + the activation log
    # to detect stalled polling loops, review backlogs, and disagreement-rate
    # trending toward the PHASE_O3_DISAGREEMENT_RATE_MAX=0.05 breach.
    "O2_SUGGEST_NO_DRAFTS_24H": {
        "query": """
            SELECT al.agent_id, al.bundle_path,
                   (SELECT COUNT(*) FROM operator_agent_drafts d
                    WHERE d.agent_id = al.agent_id AND d.created_at >= ?) AS recent_drafts
            FROM operator_agent_activation_log al
            INNER JOIN (
                SELECT agent_id, MAX(id) AS latest_id
                FROM operator_agent_activation_log
                GROUP BY agent_id
            ) latest ON al.id = latest.latest_id
            WHERE al.bundle_path LIKE '%_o2_suggest_%'
              AND (SELECT COUNT(*) FROM operator_agent_drafts d
                   WHERE d.agent_id = al.agent_id AND d.created_at >= ?) = 0
        """,
        "params": lambda cfg: (time.time() - 86400, time.time() - 86400),
        "agents_involved": [
            "anchor_sentry", "guardian", "curator",
            "SentryPollingLoop", "GuardianPollingLoop", "CuratorPollingLoop",
        ],
        "severity": "HIGH",
        "explanation": (
            "An Operator Initiative agent currently anchored at O2_SUGGEST has "
            "produced ZERO drafts in the last 24 hours.  Indicates the polling "
            "loop has stalled OR the agent never received a valid trigger.  "
            "Without drafts, the watcher's PHASE_O3_DRAFT_PAYLOAD_MIN=50 gate "
            "will never clear and O3_ACTING anchor remains blocked indefinitely."
        ),
        "resolution": (
            "Verify the agent's polling loop config flag is True (e.g. "
            "OPERATOR_AGENT_<AGENT>_POLLING_ENABLED=true in bridge/.env).  "
            "Verify the trigger source is wired (Phase O2-AUTONOMOUS-PRELUDE "
            "scaffold-only — live event wiring is a follow-up phase).  "
            "Inspect logs for `<Agent>PollingLoop: get_pending_triggers error` "
            "or `unknown trigger kind` warnings."
        ),
    },

    "DRAFT_UNREVIEWED_72H": {
        "query": """
            SELECT COUNT(*) AS unreviewed_count, MIN(created_at) AS oldest_unreviewed
            FROM operator_agent_drafts
            WHERE operator_decision IS NULL AND created_at < ?
            HAVING COUNT(*) >= 10
        """,
        "params": lambda cfg: (time.time() - 72 * 3600,),
        "agents_involved": [
            "anchor_sentry", "guardian", "curator",
            "OperatorReviewSurface",
        ],
        "severity": "MEDIUM",
        "explanation": (
            "10 or more drafts have been awaiting operator review for over 72 "
            "hours.  Indicates an operator-review backlog.  Drafts left "
            "unreviewed contribute to NEITHER the disagreement_rate numerator "
            "NOR denominator (the helper excludes operator_decision IS NULL "
            "from the reviewed set), so the watcher cannot derive a real signal "
            "until the backlog drains.  Single finding per cycle (not per draft)."
        ),
        "resolution": (
            "Operator: review pending drafts via "
            "GET /operator/operator-agent-drafts?decision=unreviewed and "
            "POST /operator/operator-agent-draft-review per draft.  "
            "Frontend dashboard (deferred phase) will surface these inline."
        ),
    },

    "DISAGREEMENT_RATE_TRENDING": {
        "query": """
            SELECT agent_id,
                   COUNT(*) AS n_reviewed,
                   SUM(CASE WHEN operator_decision = 'reject' THEN 1 ELSE 0 END) AS n_reject
            FROM operator_agent_drafts
            WHERE created_at >= ?
              AND operator_decision IN ('accept', 'reject')
            GROUP BY agent_id
            HAVING n_reviewed > 0
               AND (CAST(n_reject AS FLOAT) / n_reviewed) > 0.04
        """,
        "params": lambda cfg: (time.time() - 30 * 86400,),
        "agents_involved": [
            "anchor_sentry", "guardian", "curator",
            "OperatorReviewSurface",
        ],
        "severity": "CRITICAL",
        "explanation": (
            "Operator-vs-agent disagreement rate over the last 30 days exceeds "
            "0.04 (4%) for at least one Operator Initiative agent.  Trending "
            "toward the 5% PHASE_O3_DISAGREEMENT_RATE_MAX=0.05 breach.  CRITICAL "
            "severity because crossing 5% blocks O3_ACTING anchor (the watcher's "
            "Gate 4 fails on any agent at >= 5% rate).  The agent's draft "
            "generation logic is producing payloads that operators are "
            "rejecting at a rate trending toward the gate threshold."
        ),
        "resolution": (
            "Audit recent reject decisions via "
            "GET /operator/operator-agent-drafts?decision=reject; identify the "
            "shared failure mode in operator_disagreement_reason; either fix "
            "the agent's draft generator OR adjust the trigger source quality."
        ),
    },

    # ---------------------------------------------------------------------
    # Phase O3-ZKBA-TRACK1 Track 2 C6 (commit ships 2026-05-12 per
    # Operator Decision Matrix D-TRACK2-C6 + plan §6 A2) — three new
    # contradiction rules for ZKBA artifact integrity. These rules fire
    # against the zkba_artifact_log table populated by Sentry's
    # zk-artifact-anchor draft generator (C7) + downstream Cedar v2
    # bundle authorizations (C6 A1).
    #
    # Rule 1 — ZKBA_PROOF_WEIGHT_MISMATCH (HIGH): a ZKBA artifact's
    # declared proof_weight in the wrapper manifest disagrees with the
    # ZKBA primitive's actual proof_weight value. This is detected when
    # a VPM wrapper manifest claims a stronger proof_weight than the
    # underlying ZKBA artifact's preimage_json reports. Per Appendix B
    # B.6, proof-weight mismatches MUST fail compilation; this rule
    # surfaces cases where a manifest slipped through with mismatched
    # proof_weight values.
    # ---------------------------------------------------------------------
    "ZKBA_PROOF_WEIGHT_MISMATCH": {
        "query": """
            SELECT id, commitment_hex, zkba_class, proof_weight,
                   preimage_json, ts_ns, manifest_uri, created_at
            FROM zkba_artifact_log
            WHERE manifest_uri IS NOT NULL
              AND created_at >= ?
            ORDER BY created_at DESC LIMIT 5
        """,
        "params": lambda cfg: (time.time() - 3600,),
        "agents_involved": [
            "AnchorSentry",
            "Curator",
        ],
        "severity": "HIGH",
        "explanation": (
            "ZKBA artifact in zkba_artifact_log has a manifest_uri "
            "populated but no integrity check has been run linking the "
            "manifest's declared proof_weight to the artifact's "
            "preimage_json proof_weight value. Possible causes: (a) VPM "
            "wrapper manifest authored with overclaimed proof_weight "
            "(e.g., declared CHAIN_ONLY but wrapping a DEMO artifact), "
            "(b) bridge endpoint POST /operator/zkba-validate-manifest "
            "bypassed at write time, (c) downstream consumer parsing "
            "wrong proof_weight surface. Per VBDIP-0002 Appendix B B.6 "
            "+ §9.3.1, proof-weight visibility is load-bearing for K9 "
            "Anti-Hype Visual Grammar."
        ),
        "resolution": (
            "Run validator over the affected manifest: "
            "POST /operator/zkba-validate-manifest with the manifest "
            "JSON body. If valid=False, fix the manifest. If valid=True, "
            "cross-check that proof_weight field in the manifest matches "
            "the proof_weight in preimage_json of the zkba_artifact_log "
            "row. Discrepancy means the wrapper compiler shipped a "
            "manifest that contradicts the primitive — either the "
            "manifest is fraudulent or the compiler has a bug at the "
            "B.4 wrapper schema layer."
        ),
    },

    # ---------------------------------------------------------------------
    # Rule 2 — ZKBA_LANE_VIOLATION (HIGH): a ZKBA artifact was emitted
    # to a Cedar lane prefix not authorized for the emitting agent. Per
    # Cedar v2 bundles (C6 A1):
    #   - zk_artifacts/   is Sentry's exclusive lane
    #   - zk_verifications/ is Guardian's exclusive lane
    #   - zk_listings/    is Curator's exclusive lane
    # Cross-agent emission into a forbidden lane is a B.6 + K3
    # (Operator Capability Gating) violation.
    # ---------------------------------------------------------------------
    "ZKBA_LANE_VIOLATION": {
        "query": """
            SELECT z.id, z.commitment_hex, z.zkba_class, z.proof_weight,
                   z.manifest_uri, z.created_at, d.agent_id
            FROM zkba_artifact_log z
            LEFT JOIN operator_agent_drafts d
                   ON d.payload_hash = z.commitment_hex
            WHERE z.manifest_uri IS NOT NULL
              AND z.created_at >= ?
              AND (
                   (d.agent_id = 'anchor_sentry' AND z.manifest_uri NOT LIKE '%zk_artifacts/%')
                OR (d.agent_id = 'guardian'      AND z.manifest_uri NOT LIKE '%zk_verifications/%')
                OR (d.agent_id = 'curator'       AND z.manifest_uri NOT LIKE '%zk_listings/%')
              )
            ORDER BY z.created_at DESC LIMIT 5
        """,
        "params": lambda cfg: (time.time() - 3600,),
        "agents_involved": [
            "AnchorSentry",
            "Guardian",
            "Curator",
        ],
        "severity": "HIGH",
        "explanation": (
            "ZKBA artifact emitted to a Cedar lane prefix not authorized "
            "for the emitting agent. Per Cedar v2 bundle policies (Track "
            "2 C6 A1), each agent has exactly ONE zk_* lane prefix it may "
            "write to: Sentry → zk_artifacts/, Guardian → zk_verifications/, "
            "Curator → zk_listings/. Cross-lane emission indicates either "
            "(a) Cedar policy bypass at the bridge endpoint layer, (b) "
            "agent draft generator writing to wrong manifest_uri, or (c) "
            "manifest_uri corrupted after artifact compile. K3 violation."
        ),
        "resolution": (
            "Inspect the offending row's manifest_uri + agent_id. Verify "
            "Cedar v2 bundle anchored for that agent permits the actual "
            "lane (cast call AgentScope.getScopeRoot to confirm anchored "
            "bundle Merkle matches local file). If bundle authorizes the "
            "lane but agent wrote elsewhere, fix the draft generator. If "
            "bundle does NOT authorize, the artifact must be quarantined "
            "AND the Cedar v2 bundle must be re-anchored before further "
            "emissions."
        ),
    },

    # ---------------------------------------------------------------------
    # Rule 3 — ZKBA_VERIFICATION_KEY_STALE (MEDIUM): a ZKBA artifact's
    # manifest references a verification key (e.g., Groth16 proof key
    # for BIOMETRIC-SNAPSHOT-class artifacts) older than the verification
    # key rotation epoch. Per VBDIP-0002 §9.3.8, stale verification key
    # hash MUST render 'warning' state. This rule queries
    # zkba_artifact_log for artifacts whose preimage_json references a
    # verification_key_hash not matching the current ceremony VK hash.
    # Severity is MEDIUM (not HIGH) because the artifact's commitment
    # remains valid; only the verification-key-binding is stale.
    # ---------------------------------------------------------------------
    "ZKBA_VERIFICATION_KEY_STALE": {
        "query": """
            SELECT id, commitment_hex, zkba_class, proof_weight,
                   preimage_json, ts_ns, created_at
            FROM zkba_artifact_log
            WHERE preimage_json LIKE '%verification_key_hash%'
              AND created_at >= ?
            ORDER BY created_at DESC LIMIT 5
        """,
        "params": lambda cfg: (time.time() - 86400,),
        "agents_involved": [
            "AnchorSentry",
            "Guardian",
        ],
        "severity": "MEDIUM",
        "explanation": (
            "ZKBA artifact preimage references a verification_key_hash "
            "that may be older than the current verification-key rotation "
            "epoch. Per VBDIP-0002 §9.3.8, stale verification-key hash "
            "MUST render 'warning' visual state. MEDIUM severity: the "
            "artifact commitment remains cryptographically valid (the "
            "primitive doesn't depend on VK rotation); only the verifier-"
            "binding is stale. Downstream consumers MUST refresh or "
            "reject the verification key per their workflow."
        ),
        "resolution": (
            "Verify current Phase 237-ZK-SEPPROOF ceremony VK hash "
            "(0x32fda2857bdfb0612dd5cb305aa6798fabd64bb3f9362f362c6d73cdc49c4c1f "
            "per CLAUDE.md Sessions 1+2+3 + chain.is_ceremony_recorded "
            "view). Compare against the verification_key_hash field in "
            "the affected artifact's preimage_json. If mismatched, "
            "downstream VPM rendering MUST surface visual_state=warning "
            "per Appendix B B.6. New artifacts emitted under the rotated "
            "VK will not trigger this rule."
        ),
    },

    # ---------------------------------------------------------------------
    # Phase O4-VPM-INT close — 3 new VPM contradiction rules.
    # All three target vpm_artifact_log (Phase 1200 migration; shipped in
    # commit 1b13618d). The rules surface VPM-layer integrity violations
    # within the same FSCA poll cadence (15 min) as the existing ZKBA
    # rules above. agents_involved sets mirror the lane authority for
    # each rule's relevant VPM compiler family.
    # ---------------------------------------------------------------------

    # Rule O4-1 — VPM_VISUAL_STATE_DOM_MISMATCH (HIGH)
    # Detects VPM artifacts in vpm_artifact_log whose stored
    # compiler_output_hash_hex is non-empty (file was emitted on disk)
    # but whose visual_state has no matching audit-time grammar
    # verification record. Used as a structural integrity signal —
    # when the audit harness has flagged Section 6 issues, those rows
    # surface here for operator review. Today the rule fires on rows
    # with NULL compiler_output_hash_hex (which should never happen if
    # the compile path completed); future Phase O5 expansion can join
    # against a vpm_grammar_check_log table.
    "VPM_VISUAL_STATE_DOM_MISMATCH": {
        "query": """
            SELECT id, commitment_hex, vpm_id, visual_state, capture_mode,
                   manifest_uri, ts_ns, created_at
            FROM vpm_artifact_log
            WHERE manifest_uri IS NOT NULL
              AND compiler_output_hash_hex IS NULL
              AND created_at >= ?
            ORDER BY created_at DESC LIMIT 5
        """,
        "params": lambda cfg: (time.time() - 3600,),
        "agents_involved": [
            "AnchorSentry",
            "Guardian",
            "Curator",
        ],
        "severity": "HIGH",
        "explanation": (
            "VPM artifact in vpm_artifact_log has manifest_uri populated "
            "but compiler_output_hash_hex is NULL — implies a partial "
            "compile path or a row inserted without the post-compile "
            "hash. Per Phase O4 plan section 5.2 Layer 1 enforcement, "
            "every emitted VPM HTML must pass the static guard set "
            "(no external URLs / no runtime network / no randomness / "
            "no wall-clock / 9-field Integrity Label DOM) before disk "
            "write. A row with NULL compiler_output_hash_hex is "
            "structurally incomplete. The Layer 3 frontend grammar "
            "verifier (frontend/src/components/VpmGrammarVerifier.jsx) "
            "would surface GRAMMAR FAIL on such a row's served HTML, "
            "but the operator should not wait for browser-side render "
            "to detect the inconsistency."
        ),
        "resolution": (
            "Inspect the affected row's manifest_uri file. If the file "
            "exists, recompute SHA-256 of the HTML bytes and update the "
            "row's compiler_output_hash_hex. If the file is missing, "
            "the row is orphaned and should be deleted by an operator "
            "action (no automatic deletion in O1 SHADOW). For each row "
            "returned, run: python scripts/vpm_audit.py --report and "
            "review Sections 1 + 6. If Section 6 (visual grammar "
            "coverage) FAILs, the corresponding compiler has drifted "
            "from the canonical scripts/vpm_visual_grammar.py imports."
        ),
    },

    # ──────────────────────────────────────────────────────────────
    # SUPERSEDED 2026-05-16 — VPM_MANIFEST_HASH_DRIFT REMOVED (Option B
    # per H-1 investigation; commit see git log around this date).
    # ──────────────────────────────────────────────────────────────
    # Rule O4-2 was DROPPED after Mythos audit 2026-05-16 surfaced 84
    # unresolved findings + investigation found the rule was checking
    # a relationship the production design never honored. The field
    # `zkba_manifest_hash_hex` on vpm_artifact_log is populated by the
    # six MLGA Stage 4-10 emitters with the underlying PRIMITIVE's
    # commitment (dataproof SHA-256 for MLGA, GIC chain head for
    # GIC-LEDGER-BETA, etc.) — these are legitimate cryptographic
    # commitments that simply aren't stored in zkba_artifact_log. The
    # original Phase O3-ZKBA-TRACK1 G5b schema intent (VPM wraps a
    # ZKBA projection) was not honored by the Phase O5-MLGA autonomous-
    # emission arc, which legitimately bypasses the ZKBA wrapping for
    # primitives that already have their own commitment shape.
    #
    # Option B chosen over schema rename + emitter enrichment because:
    #   - the primitive commitments already cryptographically commit
    #     to the data (wrapping them in ZKBA adds a layer without
    #     adding integrity);
    #   - 127/127 vpm_artifact_log rows were orphans (not isolated);
    #   - field rename would touch a PV-CI-pinned schema literal
    #     (governance ceremony) for no semantic gain.
    #
    # If a future architectural decision restores the ZKBA-wrapping
    # invariant (e.g. a new ZKBA-wrapped VPM artifact class is added
    # alongside the existing primitive-direct classes), re-add a
    # narrower variant of this rule scoped to ONLY that class — do
    # not restore the broad cross-table check that was failing on
    # legitimate primitive-direct emissions.
    # ──────────────────────────────────────────────────────────────

    # Rule O4-3 — VPM_LIFECYCLE_REGRESSION (MEDIUM)
    # Detects VPM IDs at Compiler Target lifecycle (DISPUTE-PACKET-v1
    # + MARKET-LISTING-v1 per Phase O4 Stream A.2) that have zero
    # rows in vpm_artifact_log within the trailing 30 days. Today this
    # is a soft signal — Compiler Target VPMs may sit unused while
    # the operator prioritizes Test Fixture surfaces. A non-zero
    # count is the expected state once the Operator Console VPM tab
    # has compiled the canonical fixtures. MEDIUM severity reflects
    # this is not a security event; it's stagnation observation.
    "VPM_LIFECYCLE_REGRESSION": {
        "query": """
            SELECT 'DISPUTE-PACKET-v1' AS vpm_id_check,
                   COUNT(*) AS recent_rows
            FROM vpm_artifact_log
            WHERE vpm_id = 'DISPUTE-PACKET-v1'
              AND created_at >= ?
            HAVING recent_rows = 0
            UNION ALL
            SELECT 'MARKET-LISTING-v1' AS vpm_id_check,
                   COUNT(*) AS recent_rows
            FROM vpm_artifact_log
            WHERE vpm_id = 'MARKET-LISTING-v1'
              AND created_at >= ?
            HAVING recent_rows = 0
        """,
        "params": lambda cfg: (
            time.time() - (30 * 86400.0),
            time.time() - (30 * 86400.0),
        ),
        "agents_involved": [
            "Guardian",
            "Curator",
        ],
        "severity": "MEDIUM",
        "explanation": (
            "VPM IDs at the VBDIP-0002A section 10 'Compiler Target' "
            "lifecycle (DISPUTE-PACKET-v1 Guardian-lane + "
            "MARKET-LISTING-v1 Curator-lane per Phase O4 Stream A.2) "
            "have not produced any rows in vpm_artifact_log within the "
            "last 30 days. Per VBDIP-0002A section 10 the Compiler "
            "Target lifecycle is meant to be exercised continuously by "
            "the bridge POST /operator/vpm-compile endpoint or by the "
            "operator's CLI. Prolonged silence can indicate (a) the "
            "Operator Console VPM Registry tab is unused, (b) the "
            "bridge POST endpoint has a regression preventing dispatch, "
            "or (c) the operator workflow has paused VPM compilation "
            "entirely. Not a security event; surface for stagnation "
            "review."
        ),
        "resolution": (
            "Smoke-test each affected VPM ID by running its CLI "
            "compile: e.g. python scripts/vpm_compile_dispute_packet.py "
            "--help to verify the compiler module imports cleanly. "
            "Then exercise the bridge POST /operator/vpm-compile path "
            "for a representative input. If the compile succeeds + "
            "records a row, the rule resolves on the next FSCA poll. "
            "If the rule persists for a full 30-day window with no "
            "operator response, escalate to a Phase O5 candidate "
            "(deferred or removed lifecycle)."
        ),
    },

    # Rule O4-4 — CFSS_LANE_AUTHORITY_DRIFT (CRITICAL)
    # The 27th FSCA contradiction rule. Closes the data-layer / policy-
    # layer enforcement asymmetry: FSCA's prior 26 rules detect data-
    # layer CFSS violations (e.g. LISTING_TIER_DRIFT / BUNDLE_HASH_DRIFT
    # _DETECTED). CFSS_LANE_AUTHORITY_DRIFT detects Cedar POLICY-layer
    # violations — bundle JSON files mutating to grant one agent
    # authority over another's lane, which would survive bundle-hash
    # invariants if Merkle root was recomputed alongside the mutation.
    #
    # Source: cfss_lane_drift_log table, populated by
    # bridge/vapi_bridge/cfss_drift_sweeper.py on 60s cadence (opt-in
    # via cfg.cfss_drift_sweep_enabled). Each row is one (agent_id,
    # action, resource) tuple where the LIVE bundle evaluates to an
    # effect different from EXPECTED_LANE_MATRIX.
    #
    # CRITICAL severity matches BUNDLE_HASH_DRIFT_DETECTED + ALLOWLIST_
    # CHANGE_WITHOUT_GOVERNANCE — this is protocol-architectural
    # integrity at the Cedar policy layer, not data drift.
    "CFSS_LANE_AUTHORITY_DRIFT": {
        "query": """
            SELECT id, sweep_id, agent_id, action, resource,
                   expected_effect, actual_effect, bundle_path,
                   created_at
            FROM cfss_lane_drift_log
            WHERE created_at >= ?
            ORDER BY created_at DESC LIMIT 5
        """,
        "params": lambda cfg: (time.time() - 3600,),
        "agents_involved": [
            "AnchorSentry",
            "Guardian",
            "Curator",
            "CFSSDriftSweeper",
        ],
        "severity": "CRITICAL",
        "explanation": (
            "Cedar v2 lane authority drift detected at the POLICY layer. "
            "One or more rows of the 12-row EXPECTED_LANE_MATRIX (pinned "
            "in scripts/zkba_post_ceremony_audit.py) evaluate to a "
            "different effect from the FROZEN expected value when the "
            "live bundle JSON is parsed. This is the most security-"
            "relevant CFSS attack pattern: an agent gaining write "
            "authority over another agent's lane (e.g. Curator gaining "
            "tool:zk-artifact-anchor, which belongs exclusively to "
            "Sentry). Bundle hash drift (BUNDLE_HASH_DRIFT_DETECTED) "
            "catches file-content-changed-but-anchored-Merkle-unchanged "
            "drift; this rule catches Merkle-recomputed-alongside-"
            "mutation drift that survives the BUNDLE_HASH check."
        ),
        "resolution": (
            "1) Run scripts/cfss_lane_drift_sweep.py to see the full "
            "12-row matrix evaluation. 2) Run scripts/"
            "zkba_post_ceremony_audit.py to cross-check against the "
            "on-chain AgentScope state — if Cedar policy on-chain "
            "diverges from local bundle, the local file was tampered "
            "post-anchor. 3) If local bundle was tampered, restore "
            "from the architect Ed25519-attested manifest at "
            "vsd-vault/manifests/. 4) If on-chain state diverged "
            "(extremely rare), governance ceremony required to re-"
            "anchor the canonical bundle. DO NOT advance any agent's "
            "lifecycle phase while CFSS_VIOLATION findings are open."
        ),
    },

    # Phase O5-MYTHOS-MINIMAL M.3 — Mythos findings route via FSCA.
    # Mythos variants (M.2) write to mythos_finding_log; these 2 rules
    # poll that table and surface findings as FSCA contradictions, which
    # in turn route to the operator queue. Zero-new-pipeline integration
    # (the plan's W2 opportunity from the Phase O5 proposal).
    "MYTHOS_FROZEN_REGION_DRIFT": {
        "query": """
            SELECT id, variant, coherence_id, severity, description,
                   file_path, line_number, fix_authority_tier,
                   frozen_region, created_at
            FROM mythos_finding_log
            WHERE variant = 'frozen'
              AND frozen_region = 1
              AND resolved = 0
              AND created_at >= ?
            ORDER BY created_at DESC LIMIT 5
        """,
        "params": lambda cfg: (time.time() - 86400,),
        "agents_involved": [
            "AnchorSentry",
            "Guardian",
            "Mythos-Frozen",
        ],
        "severity": "CRITICAL",
        "explanation": (
            "Mythos-Frozen variant (Phase O5 M.2) detected at least one "
            "PV-CI invariant that would FAIL if --report were run now — "
            "pattern unmatched, source file missing, or digest drift vs "
            "the committed allowlist. Every such finding is on a FROZEN "
            "region (fix_authority_tier=3 read-only per INV-MYTHOS-"
            "FROZEN-PROTECTION-001), which means a manual edit has "
            "diverged the source from its allowlist-pinned digest. This "
            "is the most security-relevant Mythos signal: silent "
            "drift in protocol-critical regions."
        ),
        "resolution": (
            "1) Invoke the Mythos-Frozen MCP tool to see the full "
            "drift list: vapi_mythos_frozen_drift. 2) Run `python "
            "scripts/vapi_invariant_gate.py --report` to confirm the "
            "specific failing invariants. 3) Investigate each: if the "
            "drift is INTENTIONAL (a deliberate change to a previously-"
            "pinned region), regenerate the allowlist via the "
            "governance ceremony "
            "`python scripts/vapi_invariant_gate.py --generate "
            "--reason \"<category>: ...\" --confirm-governance` and "
            "type the exact governance phrase. If UNINTENTIONAL, "
            "restore the pinned region from git history. DO NOT auto-"
            "apply Mythos-Frozen recommendations — frozen_region=True "
            "findings are tier 3 (read-only) by INV-MYTHOS-FROZEN-"
            "PROTECTION-001."
        ),
    },
    "MYTHOS_ASYNC_HAZARD": {
        "query": """
            SELECT id, variant, coherence_id, severity, description,
                   file_path, line_number, fix_authority_tier,
                   frozen_region, created_at
            FROM mythos_finding_log
            WHERE variant = 'stability'
              AND resolved = 0
              AND severity IN ('CRITICAL', 'HIGH')
              AND created_at >= ?
            ORDER BY created_at DESC LIMIT 5
        """,
        "params": lambda cfg: (time.time() - 86400,),
        "agents_involved": [
            "Mythos-Stability",
            "Guardian",
        ],
        "severity": "MEDIUM",
        "explanation": (
            "Mythos-Stability variant (Phase O5 M.2) detected a HIGH-"
            "severity async hazard in production code — most commonly "
            "urllib.urlopen() without timeout= argument, which can "
            "starve the bridge ThreadPoolExecutor when peers hang "
            "(precedent: Mythos audit commit 48236084). MEDIUM-severity "
            "findings (silent except:pass without deliberate-fail-open "
            "marker) are deliberately NOT surfaced here — they exceed "
            "manual-review bandwidth; the operator queries them "
            "directly via the MCP tool when bandwidth allows."
        ),
        "resolution": (
            "1) Invoke the Mythos-Stability MCP tool to see all "
            "findings: vapi_mythos_stability_sweep. 2) For urlopen-no-"
            "timeout: add `timeout=<float>` to the urlopen call "
            "(mirror ipfs_pinning.py / ioswarm_live_node_client.py). "
            "3) For subprocess hazards: kill+reap on TimeoutError "
            "(precedent: commit 48236084 operator_api.py + "
            "session_adjudicator.py). 4) Mark resolved in "
            "mythos_finding_log once the fix lands — set resolved=1 "
            "+ resolution_commit=<sha>."
        ),
    },
}

# ---------------------------------------------------------------------------
# ORPHAN_RULES — 7 rules
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

    "PER_PAIR_GAP_BLOCKER_UNRESOLVED": {
        # Phase 217: PerPairGapTrend — 7th ORPHAN rule.
        # Fires when per_pair_gap_log has a blocker entry (above_1_0=0) that is
        # older than 24 hours without any subsequent entry showing above_1_0=1.
        # This means a known tournament blocker pair (e.g. P1vP3=0.032) has gone
        # unresolved for at least a full day with no corrective capture session.
        "trigger_table":         "per_pair_gap_log",
        "trigger_column":        "above_1_0",
        "trigger_value":         0,
        "trigger_ts_col":        "created_at",
        "response_table":        "per_pair_gap_log",
        "response_filter":       "above_1_0 = 1",
        "orphan_window_seconds": 86400,  # 24 hours
        "trigger_agent":         "PerPairGapLog (Phase 216)",
        "response_agent":        "CorpusDataCuratorAgent (new capture session resolving blocker pair)",
        "severity": "HIGH",
        "explanation": (
            "per_pair_gap_log has a blocker pair (above_1_0=0) entry more than 24 hours "
            "old with no subsequent entry showing above_1_0=1 for any pair. This means a "
            "known tournament blocker — e.g. P1vP3=0.032 or P2vP3=0.401 on touchpad_corners "
            "— has not been resolved by new capture sessions. Tournament gate (all_pairs_p0_ok) "
            "will remain blocked. Phase 217 trend analysis may show WORSENING velocity. "
            "TGE gate requires ALL pairs above 1.0 before dry_run=False authorization."
        ),
        "resolution": (
            "Capture additional structured probe sessions (touchpad_corners or tremor_resting) "
            "for the blocker players. Run analyze_interperson_separation.py --session-consistency "
            "and call insert_per_pair_gap() with updated distances. "
            "G-001 (P1vP3 tremor_resting) requires hardware re-capture sessions. "
            "G-002 (touchpad_corners ratio=0.728) requires more P1 corner-tap sessions. "
            "Do NOT advance dry_run=False while any pair remains below 1.0."
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

    "GOVERNANCE_CHAIN_BROKEN": {
        # Phase 225: Provenance Chain Integrity — 4th INVERSION rule.
        # Fires when governance_provenance_chain has a non-genesis entry whose
        # previous_provenance_hash does NOT match the governance_provenance_hash
        # of the next-older entry.  This is a causal inversion: if an operator
        # inserts a governance event that claims to chain from hash X, but the
        # stored chain shows the preceding event had hash Y ≠ X, the audit trail
        # has been tampered with — either by retroactive insertion, log replay, or
        # direct DB edit.
        #
        # The genesis entry (previous_provenance_hash = '0'*64) is always valid.
        # Only non-genesis entries are checked.
        "dag_query": """
            SELECT newer.id         AS newer_id,
                   newer.governance_provenance_hash  AS newer_hash,
                   newer.previous_provenance_hash    AS newer_prev,
                   older.governance_provenance_hash  AS older_hash
            FROM governance_provenance_chain newer
            JOIN governance_provenance_chain older
              ON older.id = (
                  SELECT MAX(id) FROM governance_provenance_chain
                  WHERE id < newer.id
              )
            WHERE newer.previous_provenance_hash != '0000000000000000000000000000000000000000000000000000000000000000'
              AND newer.previous_provenance_hash != older.governance_provenance_hash
            LIMIT 1
        """,
        "agents_involved": ["VAPIInvariantGate", "ProtocolCoherenceAgent"],
        "severity": "CRITICAL",
        "explanation": (
            "governance_provenance_chain contains a broken link: a governance entry's "
            "previous_provenance_hash does not match the governance_provenance_hash of "
            "the preceding entry. This means the tamper-evident audit trail for allowlist "
            "governance events has been corrupted — either by retroactive log insertion, "
            "replay of a stale governance event, or direct database modification. "
            "Every --generate event chains cryptographically to the prior event; a broken "
            "link proves the chain has been altered since the governance events were written."
        ),
        "resolution": (
            "Run GET /agent/allowlist-governance-history to inspect the full chain. "
            "Identify the broken link and investigate git log / SQLite write-ahead log "
            "for unauthorized DB modifications. If the chain was corrupted by a replay "
            "attack, re-run: python scripts/vapi_invariant_gate.py --generate "
            "--reason '<category>: chain repair after tamper investigation' and document "
            "the incident in VAPI_WHAT_IF.md."
        ),
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
        # Phase 235.x-STABILITY-2 2026-05-08: delegate to sync inner via to_thread.
        # Original body ran 14+ SQL queries SYNCHRONOUSLY on the event loop thread
        # per 15-min poll cycle; empirically this contributed to bridge zombie
        # windows (WIF-064). Pushing the entire iteration to a worker thread yields
        # the event loop so uvicorn can keep serving HTTP throughout the FSCA scan.
        return await asyncio.to_thread(self._check_contradictions_sync)

    def _check_contradictions_sync(self) -> list:
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
        # Phase 235.x-STABILITY-2 2026-05-08: delegate to sync inner via to_thread (WIF-064).
        return await asyncio.to_thread(self._check_orphans_sync)

    def _check_orphans_sync(self) -> list:
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
        # Phase 235.x-STABILITY-2 2026-05-08: delegate to sync inner via to_thread (WIF-064).
        return await asyncio.to_thread(self._check_inversions_sync)

    def _check_inversions_sync(self) -> list:
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
            import sys as _sys228; _sys228.path.insert(0, str(Path(__file__).parents[2]))
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
            import sys as _sys228; _sys228.path.insert(0, str(Path(__file__).parents[2]))
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
                        }, source=self.NAME)
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
                        # Rule-level dedup: skip if any row for this rule is already promoted
                        rule_promoted = self._db_query(
                            "SELECT COUNT(*) as n FROM fleet_coherence_log "
                            "WHERE rule_name=? AND promoted_to_wif=1",
                            (entry["rule_name"],),
                        )
                        if not (rule_promoted and rule_promoted[0].get("n", 0) > 0):
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
                }, source=self.NAME)
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
