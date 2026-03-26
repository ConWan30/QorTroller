"""
BridgeAgent — Phase 30: Conversational Protocol Intelligence

An LLM-powered autonomous agent that wraps VAPI bridge data sources as tools,
enabling natural-language interaction with the protocol for tournament operators
and developers.

Uses Claude (claude-haiku-4-5-20251001) with tool_use for:
  - Player profile and eligibility queries
  - PITL distribution calibration and interpretation
  - Leaderboard and ranking analysis
  - Identity continuity chain explanation
  - Startup diagnostics and ZK artifact status
  - Recent PoAC record inspection

Sessions are maintained in-memory (dict keyed by session_id). Each session
preserves full conversation history for coherent multi-turn dialogue.

Requires: pip install anthropic
Degrades gracefully to HTTP 503 if anthropic package is not installed.
"""

import dataclasses
import io
import json
import logging
import time
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_AGENT_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """You are the VAPI Bridge Agent — an expert on the Verified Autonomous Physical Intelligence protocol.

You help tournament operators and developers understand player data, eligibility, and system health using real bridge data.

Key VAPI concepts:
- PoAC records: 228-byte cryptographic proofs of controller activity (inference + confidence + biometrics)
- PHG score: cumulative humanity score from NOMINAL (0x20) inference records, confidence-weighted
- L4 Mahalanobis distance: biometric fingerprint distance (lower = closer to the player's own baseline)
- Humanity probability: Bayesian fusion of L4 (biometric) + L5 (rhythm) + E4 (cognitive) signals ∈ [0,1]
- CONTINUITY_THRESHOLD: max L4 distance for biometric identity continuity attestation
- Credential: on-chain PHGCredential minted when a player's PHG score meets the threshold
- Eligibility: device has a committed PHG checkpoint with cumulative score > 0

When answering:
1. Use available tools to fetch real data before drawing conclusions
2. Interpret PITL distributions contextually (high variance = diverse play patterns is normal)
3. Flag anomalies clearly: >20% low humanity_prob, high L4 drift, missing ZK artifacts
4. Be concise and actionable — operators need decisions, not lectures"""

_REACT_SYSTEM = (
    "You are the VAPI Protocol Monitor. A real-time anomaly was detected. "
    "Provide exactly 2 sentences: (1) what this PITL signal means, "
    "(2) what the operator should do. Be specific."
)

# Phase 50: Phase 46 anchor thresholds for drift detection
_PHASE46_ANOMALY_ANCHOR    = 6.726
_PHASE46_CONTINUITY_ANCHOR = 5.097

_TOOLS = [
    {
        "name": "get_player_profile",
        "description": (
            "Get a player's full profile: PHG score, record count, average humanity probability, "
            "L4/L5 biometric signals, and credential status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "get_leaderboard",
        "description": "Get the top players ranked by confirmed PHG humanity score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of leaderboard entries to return (default 10, max 100)",
                }
            },
        },
    },
    {
        "name": "get_leaderboard_rank",
        "description": "Get the 1-based leaderboard rank of a specific device.",
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "run_pitl_calibration",
        "description": (
            "Analyze the L4 Mahalanobis distance and humanity probability distributions "
            "for a device (or all devices). Returns percentile stats (p25/p50/p75/p95) "
            "and a suggested CONTINUITY_THRESHOLD adjustment range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID (optional — omit to analyze all devices)",
                }
            },
        },
    },
    {
        "name": "get_continuity_chain",
        "description": (
            "Get the biometric identity continuity chain for a device — lists all "
            "cross-device attestations (source/destination role, proof hash, timestamp)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "get_recent_records",
        "description": (
            "Get recent PoAC records for a specific device or all devices, "
            "showing inference results, confidence, and PITL signals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of records to return (default 20, max 100)",
                },
            },
        },
    },
    {
        "name": "get_startup_diagnostics",
        "description": (
            "Get system readiness status: ZK proving key artifacts, IoTeX chain RPC URL, "
            "PHG credential contract address, and operator API key configuration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_phg_checkpoints",
        "description": (
            "Get the PHG checkpoint chain for a device — shows score progression, "
            "bio hash, tx hash, and confirmation status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of checkpoints (default 10, max 50)",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "check_eligibility",
        "description": (
            "Check tournament eligibility: device has committed PHG score > 0 "
            "and optionally a minted soulbound credential."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "get_pitl_proof",
        "description": (
            "Get the latest ZK PITL session proof — nullifier hash, feature commitment, "
            "humanity probability integer, on-chain tx hash."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "get_behavioral_report",
        "description": (
            "Get a behavioral archaeology report for a device — drift trend, humanity trend, "
            "warmup attack score, burst farming score, biometric stability."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "get_network_clusters",
        "description": (
            "Detect cross-device correlation clusters that may indicate coordinated bot farms. "
            "Returns clusters with suspicion scores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_suspicion": {
                    "type": "number",
                    "description": "Minimum farm_suspicion_score to include (default 0.3)",
                }
            },
        },
    },
    {
        "name": "get_federation_status",
        "description": (
            "Get cross-bridge federation status: configured peers, local/remote cluster counts, "
            "and cross-confirmed threat hashes seen on ≥2 independent bridge instances."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_peers": {
                    "type": "integer",
                    "description": "Minimum distinct bridges for cross-confirmation (default 2)",
                }
            },
        },
    },
    {
        "name": "get_detection_policy",
        "description": (
            "Query adaptive PITL threshold multipliers derived from device risk labels. "
            "Returns per-device L4 Mahalanobis threshold multipliers set by InsightSynthesizer "
            "Mode 4 — the feedback loop that makes retrospective memory drive forward detection. "
            "Critical devices get multiplier=0.70 (30% tighter threshold); warming=0.85; "
            "cleared/stable=1.00 (baseline). Each policy has a basis_label explaining why it "
            "was set and an expires_at showing when it auto-reverts. "
            "Use this to explain: 'Why is this device failing biometric checks it passed last week?' "
            "or 'Which devices have tightened detection policies active right now?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID to look up (optional; if omitted returns all active policies)",
                },
                "risk_filter": {
                    "type": "string",
                    "description": "Filter policies by basis_label (optional)",
                    "enum": ["critical", "warming", "cleared", "stable", "all"],
                },
            },
        },
    },
    {
        "name": "query_digest",
        "description": (
            "Query synthesized longitudinal insight digests — the protocol's long-term memory. "
            "Returns rolling temporal summaries (24h/7d/30d) of threat pattern counts, "
            "template-generated narrative summaries, and per-device risk trajectory labels "
            "(stable/warming/critical/cleared). "
            "Use this to distinguish persistent vs. transient threats, understand device risk "
            "histories across weeks, and identify whether the same bot farms keep reappearing "
            "across synthesis windows. Digests are synthesized every 6 hours by InsightSynthesizer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "window": {
                    "type": "string",
                    "description": "Time window to query: '24h', '7d', '30d', or 'all' (default) for all windows",
                    "enum": ["24h", "7d", "30d", "all"],
                },
                "include_device_labels": {
                    "type": "boolean",
                    "description": "If true, include per-device risk trajectory labels in the response",
                },
                "risk_filter": {
                    "type": "string",
                    "description": "Filter device labels by risk level (requires include_device_labels=true)",
                    "enum": ["critical", "warming", "cleared", "stable"],
                },
            },
        },
    },
    {
        "name": "get_credential_status",
        "description": (
            "Query a device's PHGCredential enforcement status — the complete evidence chain "
            "from biometric anomaly to trajectory label to enforcement action. "
            "Returns: has_credential, is_active (credential exists and not suspended), "
            "suspended bool, suspended_since/until timestamps, evidence_hash (references "
            "the insight digest that triggered suspension), consecutive_critical_windows count, "
            "current risk label, active detection policy, and reinstatement conditions. "
            "Use to answer: 'Why is this player blocked from the tournament bracket?' "
            "or 'When will this suspension be lifted?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID (required)",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "get_calibration_status",
        "description": (
            "Returns the current living calibration state for the PITL L4 biometric layer: "
            "global thresholds (anomaly + continuity), per-player personal profiles (if any have "
            "accumulated >=30 NOMINAL records), recent threshold evolution history (last 5 "
            "calibration_update insights), and when the next Mode 6 cycle will run. "
            "Use to answer: 'Has the L4 threshold drifted?', 'Does player X have a personal "
            "calibration profile?', or 'When was the threshold last auto-updated?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Phase 50: 3 new tools
    {
        "name": "get_session_narrative",
        "description": (
            "Generate a 3-sentence data-derived narrative summary of a device's most recent "
            "session. No LLM call — purely deterministic data extraction. "
            "sentence_1: PITL layers fired and humanity_prob. "
            "sentence_2: Anomaly vs device history with L4 drift velocity context. "
            "sentence_3: Trend across the last 5 sessions (mean humanity_prob)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "compare_device_fingerprints",
        "description": (
            "Compare two devices' L4 biometric fingerprints via Mahalanobis distance between "
            "their EMA mean vectors from player_calibration_profiles. Uses diagonal covariance "
            "(baseline_std). Verdict: DISTINCT (dist > 6.726) / INDETERMINATE (dist > 5.097) / "
            "SIMILAR (dist <= 5.097). plain_english ALWAYS contains separation ratio 0.362 caveat "
            "because L4 is an intra-player anomaly detector only, not an identity verifier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id_a": {
                    "type": "string",
                    "description": "First 64-character hex device ID",
                },
                "device_id_b": {
                    "type": "string",
                    "description": "Second 64-character hex device ID",
                },
            },
            "required": ["device_id_a", "device_id_b"],
        },
    },
    {
        "name": "get_calibration_agent_status",
        "description": (
            "Get peer CalibrationIntelligenceAgent status: recent unconsumed events from the "
            "peer agent, current PITL L4 thresholds vs Phase 46 anchors (6.726/5.097), "
            "count of pending recalibration flags queued for the peer, and the last "
            "threshold_history entry. Use to understand the autonomous detection-calibration "
            "feedback loop state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    # Phase 51: game-aware profiling
    {
        "name": "get_game_profile",
        "description": (
            "Get the active game profile context. Returns profile ID, display name, "
            "L5 button priority order for this game (e.g. R2=sprint is primary in football "
            "instead of Cross), L6-Passive config (passive sprint-button onset tracking, "
            "no controller writes — safe during PS5 play), and per-session L6-Passive "
            "statistics: total R2 press events scored, resistance events flagged (onset > "
            "1.5x personal baseline = PS5 adaptive trigger resistance likely), and current "
            "EMA baseline onset_ms. Use to answer: 'What game profile is active?', "
            "'Why is R2 the primary L5 signal?', 'Any resistance events this session?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #22 — Phase 55
    {
        "name": "get_ioid_status",
        "description": (
            "Get the ioID device identity status for a specific device. Returns whether "
            "the device is registered in the VAPIioIDRegistry, its W3C DID (did:io:0x...), "
            "derived device address (last 20 bytes of device_id), registration timestamp, "
            "and on-chain transaction hash. Use to answer: 'What is this device's DID?', "
            "'Is this device registered in the ioID registry?', 'When was it registered?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    # Tools #24–27 — Phase 58
    {
        "name": "analyze_threshold_impact",
        "description": (
            "Compute how many sessions would flip NOMINAL→ANOMALY or ANOMALY→NOMINAL "
            "if the L4 Mahalanobis threshold shifted by a given percentage. "
            "Uses pitl_l4_distance from the records table. Never modifies thresholds."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "delta_pct": {"type": "number",
                    "description": "Shift % (negative = tighten, positive = loosen)"},
                "threshold_type": {"type": "string",
                    "description": "'anomaly' or 'continuity' (default: anomaly)"},
            },
            "required": ["delta_pct"],
        },
    },
    {
        "name": "predict_evasion_cost",
        "description": (
            "Given a known attack class (G, H, I, J, K), return structured analysis: "
            "PITL layers to evade, L4 detection rate from validation suite, validation N, "
            "and detection notes. Classes G/H/I are validated (N=5 sessions each)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "attack_class": {"type": "string",
                    "description": "G/H/I (validated) or J/K (macro, unvalidated)"},
            },
            "required": ["attack_class"],
        },
    },
    {
        "name": "get_anomaly_trend",
        "description": (
            "Rolling L4 anomaly and humanity statistics for a device over a time window. "
            "Returns session_count, mean/std L4 distance, mean humanity, trend direction "
            "(IMPROVING/STABLE/DEGRADING), and anomaly spike count above threshold."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "64-character hex device ID"},
                "days": {"type": "integer", "description": "Lookback window in days (default 7)"},
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "generate_incident_report",
        "description": (
            "Full operator-facing audit dump for a device: record history, inference code breakdown, "
            "L4/humanity score timeline, biometric fingerprint, ioID status, tournament passport "
            "status, calibration profile, and recent protocol insights."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "64-character hex device ID"},
            },
            "required": ["device_id"],
        },
    },
    # Tool #23 — Phase 56
    {
        "name": "generate_tournament_passport",
        "description": (
            "Generate or check tournament passport eligibility for a device. "
            "Requires: device must be ioID-registered AND have >= 5 NOMINAL sessions "
            "with humanity_prob >= 0.60 (minHumanityInt >= 600). Returns passport details "
            "if issued (passport_hash, min_humanity_int, issued_at), or status: "
            "'ioid_not_registered', 'pending_sessions' (count/5 complete), "
            "or 'passport_ready' with the passport record."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                },
                "min_humanity": {
                    "type": "number",
                    "description": "Minimum humanity_prob threshold (default 0.60)",
                },
            },
            "required": ["device_id"],
        },
    },
    # Tool #28 — Phase 59
    {
        "name": "get_controller_twin_data",
        "description": (
            "Return the complete My Controller digital twin data for a device: "
            "calibration profile, 12-feature biometric fingerprint EMA means, "
            "ioID DID, tournament passport status, anomaly trend, operator audit log, "
            "and last 20 PoAC chain lock points. Powers the Phase 59 3D visualization."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "64-character hex device ID"},
            },
            "required": ["device_id"],
        },
    },
    # Tool #29 — Phase 61
    {
        "name": "get_session_replay",
        "description": (
            "Return the frame checkpoint window for a specific PoAC record — up to 60 "
            "downsampled InputSnapshot frames (20 Hz) captured around the PoAC commit. "
            "Used for forensic session replay visualization in the My Controller 3D page."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id":   {"type": "string", "description": "64-hex device ID"},
                "record_hash": {"type": "string", "description": "64-hex PoAC record_hash"},
            },
            "required": ["device_id", "record_hash"],
        },
    },
    # Tool #30 — Phase 62
    {
        "name": "get_enrollment_status",
        "description": (
            "Return PHG credential enrollment progress for a device. Shows how many "
            "NOMINAL sessions have been accumulated, average humanity probability, "
            "current enrollment status (pending/eligible/minting/credentialed/failed), "
            "and how many more sessions are needed to qualify for credential minting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    # Tool #31 — Phase 63
    {
        "name": "get_reflex_baseline",
        "description": (
            "Return L6b neuromuscular reflex baseline statistics for a device. "
            "Shows probe count, mean reflex latency (ms), std deviation, "
            "classification distribution (HUMAN/BOT/INCONCLUSIVE/NO_RESPONSE), "
            "and number of BOT-classified events. Requires L6B_ENABLED=true and "
            "at least one completed probe cycle to return meaningful data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    # Tool #32 — Phase 65
    {
        "name": "get_autonomous_rulings",
        "description": (
            "Return autonomous SessionAdjudicator rulings for a device. "
            "Shows verdict (FLAG/HOLD/BLOCK/CERTIFY/CLEAR), confidence (0.0-1.0), "
            "reasoning, evidence record hashes, attestation_hash (trust anchor), "
            "commitment_hash, dry_run flag, and timestamp. "
            "Use this to check whether the autonomous agent has flagged a device."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-char hex device ID",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rulings to return (default 10)",
                },
            },
            "required": ["device_id"],
        },
    },
    # Tool #33 — Phase 65
    {
        "name": "request_adjudication",
        "description": (
            "Queue an autonomous adjudication request for a device. "
            "SessionAdjudicator picks it up within 5 minutes and stores a ruling "
            "in agent_rulings. Include attestation_hash if the SDK was self-verified — "
            "this enables BLOCK/CERTIFY verdicts. Returns event_id for tracking."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string"},
                "attestation_hash": {
                    "type": "string",
                    "description": "SDKAttestation.attestation_hash hex",
                },
                "reason": {
                    "type": "string",
                    "description": "Human context for the request",
                },
            },
            "required": ["device_id"],
        },
    },
    # Tool #34 — Phase 66
    {
        "name": "get_ruling_streak",
        "description": (
            "Return the current verdict streak for a device from the ruling_streaks table. "
            "Shows streak_verdict, current_streak count, escalated_to (if auto-escalated), "
            "and last_ruling_id. "
            "Escalation thresholds: FLAG x5 -> HOLD, HOLD x2 -> BLOCK. "
            "BLOCK streaks trigger PHGCredential.suspend() via RulingEnforcementAgent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "64-char hex device ID"},
            },
            "required": ["device_id"],
        },
    },
    # Tool #35 — Phase 66
    {
        "name": "override_ruling",
        "description": (
            "Issue an operator CLEAR ruling to reset a device's streak and re-enable "
            "tournament eligibility. Use when manual review confirms a false positive. "
            "Inserts a CLEAR agent_ruling with dry_run=False and resets ruling_streaks, "
            "clearing any escalated_to state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "64-char hex device ID"},
                "reason": {
                    "type": "string",
                    "description": "Human explanation for the override",
                },
            },
            "required": ["device_id"],
        },
    },
    # Tool #36 — Phase 68
    {
        "name": "verify_ceremony_integrity",
        "description": (
            "Verify that the embedded PITL verification key matches the on-chain "
            "CeremonyRegistry commitment. Returns {local_hash, on_chain_match, "
            "contributor_count, error}. Use to confirm the MPC ceremony is intact "
            "and at least 2 contributors participated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "circuit_name": {
                    "type": "string",
                    "description": "Circuit name to check (default: PitlSessionProof)",
                },
            },
            "required": [],
        },
    },
    # Tool #37 — Phase 68
    {
        "name": "get_suspension_status",
        "description": (
            "Return the current PHGCredential suspension state for a device. "
            "Includes suspended bool, seconds_remaining, and ruling_streak summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "64-char hex device ID"},
            },
            "required": ["device_id"],
        },
    },
    # Tool #38 — Phase 68
    {
        "name": "get_zk_verifier_stats",
        "description": (
            "Return ZKVerifier proof acceptance/rejection/timeout/error counters. "
            "Shows how many proofs were pre-verified locally since bridge startup. "
            "Use to assess ZK proof validity rates across submissions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #39 — Phase 68
    {
        "name": "get_enrollment_pipeline",
        "description": (
            "Return a summary of all devices grouped by enrollment state: "
            "eligible (≥10 NOMINAL sessions, ≥0.60 avg humanity), "
            "in_progress (enrolled but not yet eligible), "
            "and unenrolled. Use to monitor onboarding pipeline health."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #40 — Phase 68
    {
        "name": "request_live_adjudication",
        "description": (
            "Request a live (non-dry-run) adjudication ruling for a specific device. "
            "Operator-gated: requires the operator to have confirmed the session is "
            "production-ready. Posts a ruling_request event marked live=True. "
            "The SessionAdjudicator processes it with dry_run=False within 5 minutes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "64-char hex device ID"},
                "reason": {
                    "type": "string",
                    "description": "Justification for requesting a live ruling",
                },
            },
            "required": ["device_id"],
        },
    },
    # Tool #41 — Phase 70
    {
        "name": "get_data_lineage",
        "description": (
            "Return the full data lineage graph for a device. "
            "Lineage links: session → proof → ruling → token eligibility. "
            "Each entry has taxonomy_class (SESSION_DATA/PROOF_DATA/etc), "
            "quality_index (0.0–1.0), and curator_note from DataCuratorAgent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "64-char hex device ID"},
                "limit": {
                    "type": "integer",
                    "description": "Max lineage entries to return (default 50)",
                },
            },
            "required": ["device_id"],
        },
    },
    # Tool #42 — Phase 70
    {
        "name": "get_token_eligibility",
        "description": (
            "Return token eligibility score and multiplier breakdown for a device. "
            "Reads from token_eligibility table (updated every 5 min by DataCuratorAgent). "
            "Includes: nominal_sessions, clean_streak, passport_held, enrollment_complete, "
            "mpc_verified, gate_passed, total_multiplier, eligibility_score."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "64-char hex device ID"},
            },
            "required": ["device_id"],
        },
    },
    # Tool #43 — Phase 70
    {
        "name": "get_oracle_state",
        "description": (
            "Return the 10 most recent oracle publications for a given oracle type. "
            "oracle_type must be one of: HUMANITY, RULING, PASSPORT. "
            "Each entry includes device_id, tx_hash, payload, and published_at timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "oracle_type": {
                    "type": "string",
                    "description": "Oracle type: HUMANITY | RULING | PASSPORT",
                },
            },
            "required": ["oracle_type"],
        },
    },
    # Tool #44 — Phase 70
    {
        "name": "compute_reward_score",
        "description": (
            "Compute a full DePIN reward score for a device using the DataCuratorAgent "
            "eligibility engine. Returns multiplier breakdown: passport (1.5×), "
            "enrollment (2.0×), clean_streak (2.5×), mpc_verified (1.25×), "
            "gate_passed (3.0×), and the resulting eligibility_score."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "64-char hex device ID"},
            },
            "required": ["device_id"],
        },
    },
    # Tool #47 — Phase 76
    {
        "name": "get_ruling_provenance",
        "description": (
            "Return the cryptographic provenance anchor for a specific ruling. "
            "The provenance_hash binds three independent evidence streams: the ruling "
            "commitment_hash (on-chain via RulingRegistry), the ceremony integrity data "
            "(CeremonyRegistry beacon + contributor count), and the evidence set presented "
            "to the LLM — into a single SHA-256 fingerprint. This is the first verifiable "
            "AI cognitive audit trail in competitive gaming: any third party can recompute "
            "provenance_hash from the stored components and confirm the ruling was not "
            "post-hoc modified. Returns 404-equivalent dict if not yet anchored."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ruling_id": {
                    "type": "integer",
                    "description": "The agent_rulings.id to retrieve the provenance anchor for",
                },
            },
            "required": ["ruling_id"],
        },
    },
    # Tool #46 — Phase 75
    {
        "name": "get_validation_gate_status",
        "description": (
            "Return the current dry-run enforcement gate status from "
            "SessionAdjudicatorValidationAgent. Shows consecutive_clean ruling count, "
            "divergence count, gate_n threshold, gate_passed flag, and recommended action. "
            "When gate_passed=True, it is safe to enable live enforcement "
            "via POST /agent/config with AGENT_DRY_RUN=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #45 — Phase 70
    {
        "name": "publish_sovereignty_pledge",
        "description": (
            "OPERATOR ONLY — Queue an on-chain data sovereignty pledge to "
            "DataSovereigntyRegistry.sol. Posts a sovereignty_pledge_request event "
            "to agent_events; DataCuratorAgent will process it within 5 minutes. "
            "The pledge commits the VAPI schema hash to IoTeX L1, declaring VAPI "
            "ownership of all data from certified DualShock Edge devices."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #48 — Phase 79
    {
        "name": "get_live_mode_status",
        "description": (
            "Get the current live-mode readiness status for the SessionAdjudicator. "
            "Returns 5-condition checklist (validation_gate_passed, no_recent_operator_overrides, "
            "no_recent_key_rotation, divergence_rate_within_tolerance, consecutive_clean_met), "
            "ready_for_live_mode flag, blocking_conditions list, and recommended_action string. "
            "Use this to evaluate whether it is safe to set AGENT_DRY_RUN=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #49 — Phase 80
    {
        "name": "get_federation_status",
        "description": (
            "Get federation broadcast status for Phase 80 FederationBroadcastAgent. "
            "Returns configured peers, total threat signals broadcast, signals received "
            "from peers, and federation_enabled flag."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #50 — Phase 81
    {
        "name": "get_class_j_assessment",
        "description": (
            "Get the most recent Class J GaussianHMM ML-bot risk assessment for a device. "
            "Returns entropy_variance, risk_level (LOW/MEDIUM/HIGH), and window_count. "
            "HIGH risk (entropy_variance <= 0.05) indicates HMM ML-bot signature — "
            "pathologically uniform temporal state transitions. Phase 81."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID",
                }
            },
            "required": ["device_id"],
        },
    },
    # Tool #51 — Phase 82
    {
        "name": "get_reactive_adjudication_status",
        "description": (
            "Get the reactive adjudication interrupt log — Class J HIGH-risk triggered "
            "out-of-cycle LLM rulings. was_deferred=true entries were suppressed by the "
            "token bucket rate limiter (W1 mitigation: max 2 calls/60s). "
            "Use to audit the reactive Class J → ruling → enforcement chain. Phase 82."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "64-character hex device ID (optional — omit for all devices)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max entries to return (default 20)",
                },
            },
            "required": [],
        },
    },
    # Tool #52 — Phase 83
    {
        "name": "get_agent_supervisor_status",
        "description": (
            "Get the VAPI agent fleet health status from AgentSupervisor. "
            "Reports HEALTHY/STALE/UNKNOWN/ZOMBIE per agent, fleet_health "
            "(ALL_HEALTHY | DEGRADED | CRITICAL), and counts. "
            "ZOMBIE = agent writing rows but to 0 distinct devices (W1 loop detection). "
            "CRITICAL if core agents (session_adjudicator, ruling_enforcement_agent) are "
            "STALE, or ≥3 agents are non-HEALTHY. "
            "Use to audit AGaaS SLA before accepting tournament rulings. Phase 83."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #53 — Phase 84
    {
        "name": "get_gate_readiness",
        "description": (
            "Get composite live-mode gate readiness status (Phase 84). "
            "Aggregates: validation_gate (consecutive_clean progress, gate_passed), "
            "fleet_health (ALL_HEALTHY/DEGRADED/CRITICAL from AgentSupervisor), "
            "gate_attestations_count (on-chain proofs recorded), and overall_ready. "
            "overall_ready=true requires gate_passed=true AND fleet_health != CRITICAL. "
            "Use before setting AGENT_DRY_RUN=false to confirm the fleet is ready. "
            "W1 note: run POST /agent/warm-up first to verify llm_available=true."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #78 — Phase 110
    {
        "name": "get_ioswarm_vhp_mint_status",
        "description": (
            "Return ioSwarm VHP Mint Authorization status (Phase 110). "
            "ioswarm_vhp_mint_enabled=False by default — fail-CLOSED quorum gate for VHP mint; "
            "irreversible soulbound token on-chain — exceptions block mint (opposite of renewal fail-open). "
            "MINT_QUORUM=0.80 (stricter than BLOCK_QUORUM=0.67; matches DUAL_VETO_SCORE from Phase 109C). "
            "W2 swarm_fingerprint = SHA-256(node_verdicts_json) stored in ioswarm_vhp_mint_log — "
            "creates two-era VHP provenance: pre-110 (no fingerprint) vs post-110 (quorum-authorized). "
            "task_spec_registered=True means vapi_vhp_mint_authorization_v1 spec is "
            "available in scripts/vapi-vhp-mint-swarm-agent.json. "
            "Fields: ioswarm_vhp_mint_enabled, mint_quorum, authorized_count, denied_count, "
            "task_spec_registered, swarm_fingerprint_count, timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #77 — Phase 109C
    {
        "name": "get_ioswarm_adjudication_status",
        "description": (
            "Return ioSwarm Adjudication Coordinator status (Phase 109C). "
            "ioswarm_adjudication_enabled=False by default — infrastructure-only; "
            "decentralizes ClassJ+Triage verdicts to N=5 emulator quorum nodes when enabled. "
            "W2 Dual-Quorum Veto: dual_veto fires when BOTH classj_quorum AND triage_quorum "
            "independently reach BLOCK (≥67% agreement each); consensus_score clamped to "
            "max(score, 0.80) > threshold 0.60 → always drives BLOCK. "
            "Fail-open: adjudication errors → CLEAR verdicts (avoid false positives). "
            "task_spec_registered=True means vapi_classj_triage_adjudication_v1 spec is "
            "available in scripts/vapi-adjudication-swarm-agent.json. "
            "Fields: ioswarm_adjudication_enabled, classj_block_quorum, triage_block_quorum, "
            "dual_veto_count, adjudication_count, task_spec_registered, timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #76 — Phase 109B
    {
        "name": "get_ioswarm_renewal_status",
        "description": (
            "Return ioSwarm Renewal Coordinator status (Phase 109B). "
            "ioswarm_renewal_enabled=False by default — infrastructure-only; "
            "ioSwarm quorum guard for VHP renewal is additive and backward-compatible. "
            "Fail-open design: coordinator errors never block VHP renewal. "
            "task_spec_registered=True means vapi_vhp_renewal_v1 spec is available "
            "in scripts/vapi-vhp-renewal-swarm-agent.json. "
            "W2 integration: nodes read consecutive_clean + recent BLOCK count from "
            "ioswarm_consensus_log — clean behavior feeds easier renewal. "
            "Fields: ioswarm_renewal_enabled, min_quorum, renewal_count, "
            "task_spec_registered, recent_approvals, recent_skips, timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #75 — Phase 109A
    {
        "name": "get_ioswarm_status",
        "description": (
            "Return ioSwarm Bridge Adapter status (Phase 109A). "
            "ioswarm_enabled=False by default — infrastructure-only until live ioSwarm "
            "operator nodes are registered. task_spec_registered=True means the "
            "vapi_pitl_adjudication_v1 task spec is available in scripts/vapi-swarm-agent.json. "
            "When enabled, swarm consensus acts as optional 4th epistemic signal "
            "(weights: ClassJ 0.35 + Triage 0.35 + Supervisor 0.15 + Swarm 0.15). "
            "Fields: ioswarm_enabled, quorum_threshold, block_quorum_threshold, "
            "consensus_count, node_count, task_spec_registered, w3bstream_applets, "
            "vhp_auth_gate_address, timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #74 — Phase 108
    {
        "name": "get_tournament_readiness",
        "description": (
            "Return comprehensive tournament readiness scorecard (Phase 108). "
            "fully_ready=True requires ALL 7 conditions: 5 software "
            "(n_tested>=100, false_positive_count=0, activation_committed, "
            "dry_run=False, pmi>=1) AND 2 hardware "
            "(separation_ratio_current>1.0, touchpad_recapture_complete). "
            "CURRENT STATUS: separation_ratio=0.362 — TOURNAMENT BLOCKER. "
            "Software P0 gate (Phase 107) is achievable now; hardware requires "
            "calibration sessions. Use this tool for deployment readiness decisions. "
            "Fields: software_conditions_met/5, hardware_conditions_met/2, "
            "separation_ratio_current, fully_ready, blocking_conditions."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #73 — Phase 107
    {
        "name": "get_live_mode_readiness",
        "description": (
            "Return latest live mode readiness report (Phase 107). "
            "ready_for_live=True requires: n_tested>=100 AND false_positive_count==0 "
            "AND activation_committed=True AND dry_run_active=False AND pmi>=1. "
            "This is the P0 gate for tournament deployment (software conditions only). "
            "Fields: n_tested, false_positive_count, false_positive_rate, "
            "activation_committed, pmi, dry_run_active, ready_for_live, created_at."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #72 — Phase 105
    {
        "name": "get_epistemic_config",
        "description": (
            "Return epistemic consensus config + threshold audit log (Phase 105). "
            "at_risk=True when effective_threshold < 0.65 (Phase 98 W1 — ClassJ alone "
            "can reach 0.60). pmi_triggered=True means PMI>=1 auto-raised threshold "
            "(Phase 104/105 synergy, W2 mitigation active). "
            "Fields: configured_threshold, recommended_threshold, effective_threshold, "
            "pmi_triggered, triage_prereq_required, at_risk, pmi, threshold_history_count, timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #71 — Phase 104
    {
        "name": "get_protocol_maturity",
        "description": (
            "Return ProtocolMaturityIndex (PMI) and persistent activation state (Phase 104). "
            "PMI: 0=uninitiated / 1=simulated / 2=testnet_organic / 3=mainnet. "
            "activation_committed=True means dry_run=False persists across bridge restarts "
            "(W1 mitigation — startup _restore_activation_state auto-restores live mode). "
            "Fields: pmi, pmi_label, activation_committed, committed_at, dry_run_active, "
            "is_simulation, days_until_vhp_expiry, vhp_found, timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #70 — Phase 103
    {
        "name": "run_activation_sequence",
        "description": (
            "Run the Phase 103 live activation simulation sequence. "
            "Seeds ruling_validation_log, gate_attestations, enforcement_cert, "
            "protocol_intelligence_report in correct order, then inserts the first "
            "VHP issuance (simulation, no chain call). "
            "Fields: simulation_sessions, gate_passed, cert_created, dry_run_toggled, "
            "vhp_minted, token_id, tx_hash, fully_activated, elapsed_ms, error."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n_sessions": {
                    "type": "integer",
                    "description": "Simulation sessions to seed (default 110, must exceed gate_n=100).",
                }
            },
            "required": [],
        },
    },
    # Tool #69 — Phase 102
    {
        "name": "get_vhp_renewal_log",
        "description": (
            "Return VHP auto-renewal log summary (Phase 102). "
            "VHPRenewalAgent (14th agent) polls every 6 hours and renews VHP soulbound tokens "
            "expiring within vhp_renewal_warning_days (default 7). "
            "Fields: renewal_count, last_renewal_at, dry_run_only (all renewals were dry_run), "
            "lifecycle_warning (True if no VHPs ever issued — W2 liveness beacon), timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Filter by device_id. Empty = all devices.",
                }
            },
            "required": [],
        },
    },
    # Tool #68 — Phase 101B
    {
        "name": "get_edge_ai_profile",
        "description": (
            "Return the VAPI bridge's Edge AI profile for IoTeX ecosystem positioning (Phase 101B). "
            "Maps the 13-agent autonomous fleet onto IoTeX's three-layer Real-World AI stack: "
            "ioID (Verify — Phase 55 LIVE), W3bstream (Process — Phase 99B LIVE), "
            "Realms (Perceive — deferred until >= 100k daily PoAC). "
            "inference_mode: llm_augmented when Anthropic key available, else local_rule_fallback "
            "(rule_fallback IS a local SLM for human presence verification). "
            "agent_autonomy_level: full when dry_run=False, advisory when dry_run=True. "
            "iotex_layer_integration: dict of {ioID, w3bstream, quicksilver, realms} booleans. "
            "Phase 101B."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #67 — Phase 101
    {
        "name": "get_quicksilver_collateral_status",
        "description": (
            "Return QuickSilver stIOTX collateral status for a VAPI operator (Phase 101). "
            "Phase 101 introduces stIOTX (IoTeX QuickSilver liquid staking token) as an "
            "alternative to VAPI token staking — operators earn IoTeX network staking yield "
            "WHILE their collateral is locked (double-yield position). "
            "Fields: operator_address, found, latest_event_type (lock/unlock_request/slash), "
            "amount_wei, events_count, last_event_at, stiotx_token_address, "
            "quicksilver_collateral_address. "
            "Returns found=false if no events recorded for this operator. Phase 101."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "operator_address": {
                    "type": "string",
                    "description": "Ethereum address of the VAPI operator.",
                },
            },
            "required": ["operator_address"],
        },
    },
    # Tool #66 — Phase 100
    {
        "name": "get_activation_status",
        "description": (
            "Return 5-step live-mode activation checklist (Phase 100). "
            "Shows current blocking step, gate progress, audit status, and dry_run state. "
            "Use to determine the exact next action needed before the first VHP can be minted. "
            "current_blocking_step: 1=need more clean sessions, 2=need enforcement cert, "
            "3=need audit_valid, 4=need dry_run=false, 5=need VHP mint, 6=fully activated. "
            "progress_pct: percentage of gate_n sessions completed (step 1). "
            "Phase 100."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #65 — Phase 99A
    {
        "name": "get_operator_status",
        "description": (
            "Return the latest staking event for a VAPI bridge operator address. "
            "Reflects bridge-side record of on-chain VAPIOperatorRegistry interactions. "
            "Event types: register (stake locked), slash (50% burned/50% claimant), "
            "deregister_request (30-day cooldown started), deregister (stake returned). "
            "Fields: operator_address, event_type, stake_amount (VAPI wei), tx_hash, reason, created_at. "
            "Returns found=false if operator has no recorded events. Phase 99A."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "operator_address": {
                    "type": "string",
                    "description": "Ethereum address of the VAPI bridge operator.",
                },
            },
            "required": ["operator_address"],
        },
    },
    # Tool #64 — Phase 98
    {
        "name": "get_epistemic_consensus_log",
        "description": (
            "Return Phase 98 epistemic consensus decisions. "
            "Every BLOCK verdict passes through a weighted multi-agent consensus gate before "
            "irreversible enforcement: ClassJDetector (0.40 weight), DivergenceTriageAgent (0.40), "
            "AgentSupervisor (0.20). If consensus_score < threshold (default 0.60), "
            "BLOCK is downgraded to HOLD. downgraded_count shows how often this happened. "
            "Use to audit the false-positive protection layer for BLOCK enforcement. "
            "Phase 98."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Filter by device_id (optional).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max entries to return (default 50).",
                },
            },
            "required": [],
        },
    },
    # Tool #63 — Phase 97
    {
        "name": "get_live_mode_guard_log",
        "description": (
            "Return the live-mode guard audit log from Phase 97. "
            "Every attempt to enable live enforcement via POST /agent/config is logged here — "
            "both approved transitions and blocked attempts with blocking_conditions. "
            "Fields: event_type (transition_attempt/transition_approved/dry_run_restored), "
            "gate_passed, cert_valid, audit_valid, blocking_conditions (JSON array), "
            "operator_key_hash (first 16 chars of SHA-256 of api_key), created_at. "
            "Use to audit operator actions and diagnose why live-mode activation was blocked. "
            "Phase 97."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max entries to return (default 50).",
                },
            },
            "required": [],
        },
    },
    # Tool #62 — Phase 96
    {
        "name": "get_enforcement_certificate",
        "description": (
            "Get the latest Enforcement Readiness Certificate (ERC) issued by the operator. "
            "The ERC is a portable HMAC-SHA256-signed proof of audit_valid=True, cryptographically "
            "binding the operator API key to the activation audit summary. Tournament operators "
            "can verify the ERC without VAPI infrastructure. has_certificate=False means no cert "
            "has been issued yet (run POST /agent/enforcement-certificate first). "
            "is_expired=True means the cert TTL (default 24h) has elapsed — renew with POST. "
            "Phase 96."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #61 — Phase 95
    {
        "name": "get_activation_audit",
        "description": (
            "Get the Phase 95 activation audit summary — a tamper-evident cross-reference "
            "of the live_mode_activation_log (Phase 92) and gate_attestations (Phase 84/87). "
            "audit_valid=True confirms: (1) the protocol scored ready_for_live_mode=True, "
            "(2) an on-chain gate attestation subsequently exists, and (3) the chronological "
            "order is intact. This is the cryptographic pre-condition for setting "
            "AGENT_DRY_RUN=false. Callable from tournament CI pipelines."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #60 — Phase 94
    {
        "name": "get_escalation_ruling_log",
        "description": (
            "Get the escalation ruling log from the Phase 94 triage reactive loop. "
            "DivergenceTriageAgent escalates devices via divergence_pattern_detected bus; "
            "SessionAdjudicator fires reactive rulings for each escalated device "
            "(rate-limited to 1/hour per device by default, W1 mitigation). "
            "was_deferred=1 entries were rate-limited and not adjudicated. "
            "Filters by device_id if provided."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Optional 64-char hex device ID filter.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max entries to return (default 50).",
                },
            },
            "required": [],
        },
    },
    # Tool #59 — Phase 92
    {
        "name": "get_activation_log",
        "description": (
            "Get the live mode activation audit log (Phase 92). "
            "Records every readiness_check (5-min automated poll) and "
            "operator_request (POST /agent/request-activation) event with "
            "protocol_health_score, blocking_conditions, bottleneck, and operator_notes. "
            "latest_ready_for_live_mode=true when the most recent entry has "
            "ready_for_live_mode=1. "
            "Use this log to audit the activation decision trail before setting "
            "AGENT_DRY_RUN=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max entries to return (default 50).",
                },
            },
            "required": [],
        },
    },
    # Tool #58 — Phase 91
    {
        "name": "get_triage_report",
        "description": (
            "Get the divergence triage report: per-device adversarial pattern analysis (Phase 91). "
            "DivergenceTriageAgent polls ruling_validation_log divergence_reason fields (Phase 88) "
            "and detects cross-session clusters: ML-bot (>=2 class_j_HIGH divergences), "
            "cheat codes (>=1 hard_cheat_codes divergence), enrollment anomaly (>=3 ineligible). "
            "escalated=1 entries need immediate operator attention. "
            "clean_count = devices with divergences but no detected adversarial pattern. "
            "triage_confidence_score = clean_count / total diverged devices (feeds Phase 89 score)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max device entries to return (default 50).",
                },
            },
            "required": [],
        },
    },
    # Tool #57 — Phase 90
    {
        "name": "get_shadow_enforcement_log",
        "description": (
            "Get the shadow enforcement log: BLOCK actions suppressed by shadow mode (Phase 90). "
            "When ENFORCEMENT_SHADOW_MODE=true, every BLOCK verdict is logged here instead of "
            "calling PHGCredential.suspend(). Review this log to validate false-positive rate "
            "before activating live enforcement (ENFORCEMENT_SHADOW_MODE=false). "
            "stats.pass_rate = fraction of shadow sessions that did NOT result in a block. "
            "Pass rate >= 0.98 across N>=20 sessions is the recommended live-mode precondition."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Optional 64-char hex device ID filter.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max entries to return (default 50).",
                },
            },
            "required": [],
        },
    },
    # Tool #56 — Phase 89
    {
        "name": "get_protocol_intelligence",
        "description": (
            "Get the unified protocol intelligence report: protocol_health_score (0-100) "
            "synthesized from all VAPI agent data streams (Phase 89). "
            "Score = 100*(0.35*gate_progress + 0.25*fleet_health + 0.20*divergence_clarity "
            "+ 0.10*corpus_pass + 0.10*class_j_confidence) + Phase 90/91 bonuses (max 10). "
            "ready_for_live_mode=true when score>=85 AND gate_passed AND fleet!=CRITICAL. "
            "bottleneck = lowest-contributing component (tells operator what to fix next). "
            "estimated_days_to_gate = remaining sessions / current session velocity. "
            "This is the single source of truth for operator go/no-go enforcement decisions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #55 — Phase 88
    {
        "name": "get_campaign_status",
        "description": (
            "Get live adjudication campaign progress toward dry_run=False activation (Phase 88). "
            "Returns consecutive_clean/gate_n progress, progress_pct, estimated_sessions_to_gate, "
            "verdict_breakdown (CERTIFY/FLAG/HOLD/BLOCK counts), divergence_breakdown "
            "(which evidence fields drove LLM↔fallback splits), recent_sessions (last 10), "
            "and campaign_note (operator-readable narrative). "
            "W1: consecutive_clean is atomically computed at call time — never stale. "
            "When gate_passed=true, campaign_note says 'Gate PASSED' — safe to set AGENT_DRY_RUN=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #54 — Phase 86
    {
        "name": "get_corpus_status",
        "description": (
            "Get synthetic validation corpus statistics (Phase 86). "
            "Returns total sessions generated, passed_fallback, failed_fallback, "
            "run_count, and last_run_at. "
            "ISOLATION: synthetic sessions do NOT affect consecutive_clean or gate_passed. "
            "failed_fallback > 0 on a fresh nominal corpus = rule_fallback regression. "
            "Use POST /agent/run-synthetic-corpus to trigger a corpus run."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def _blocks_to_content(blocks) -> list[dict]:
    """Convert anthropic ContentBlock objects to plain dicts for history storage."""
    result = []
    for block in blocks:
        btype = getattr(block, "type", None)
        if btype == "text":
            result.append({"type": "text", "text": block.text})
        elif btype == "tool_use":
            result.append(
                {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                }
            )
    return result


class BridgeAgent:
    """LLM-powered VAPI protocol intelligence agent.

    Wraps bridge data sources as Claude tools, enabling natural-language
    operator queries over PHG scores, PITL distributions, eligibility,
    continuity chains, and system health.

    Session history is maintained in-memory; restarting the bridge
    clears all session context.
    """

    def __init__(self, cfg, store, behavioral_arch=None, network_detector=None):
        self._cfg = cfg
        self._store = store
        self._behavioral_arch = behavioral_arch
        self._network_detector = network_detector
        self._sessions: dict[str, list[dict]] = {}

    # ------------------------------------------------------------------
    # Session persistence helpers (Phase 31)
    # ------------------------------------------------------------------

    def _load_history(self, session_id: str) -> list[dict]:
        """Load from in-memory cache; fall back to store on cache miss."""
        if session_id not in self._sessions:
            self._sessions[session_id] = self._store.get_agent_session(session_id)
        return self._sessions[session_id]

    def _trim_history_if_long(self, history: list[dict], max_messages: int | None = None) -> list[dict]:
        """Keep history bounded with structured tool-inventory summary (Phase 37 enhanced).

        When history exceeds the threshold, compresses all-but-last-20 messages into a
        single summary entry that records which tools were called in the compressed portion.
        This preserves useful context (what the agent was investigating) without consuming
        the full context window.
        """
        threshold = max_messages or int(getattr(self._cfg, "agent_max_history_before_compress", 60))
        if len(history) <= threshold:
            return history
        to_trim = history[:-20]
        recent  = history[-20:]
        # Extract tool use inventory from trimmed portion
        tools_called: dict[str, int] = {}
        for msg in to_trim:
            content = msg.get("content", "")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        t = block.get("name", "unknown")
                        tools_called[t] = tools_called.get(t, 0) + 1
        tool_summary = (
            ", ".join(f"{k}×{v}" for k, v in sorted(tools_called.items()))
            if tools_called else "none"
        )
        summary_entry = {
            "role": "user",
            "content": (
                f"[System: {len(to_trim)} prior messages compressed. "
                f"Tools used in compressed portion: {tool_summary}. "
                f"Continue from the {len(recent)} most recent messages below.]"
            ),
        }
        return [summary_entry] + recent

    def _save_history(self, session_id: str, history: list[dict]) -> None:
        """Write to in-memory cache AND SQLite store (with history trimming, Phase 32)."""
        history = self._trim_history_if_long(history)
        self._sessions[session_id] = history
        try:
            self._store.store_agent_session(session_id, history)
        except Exception as exc:
            log.warning("BridgeAgent: failed to persist session %s: %s", session_id, exc)

    # ------------------------------------------------------------------
    # Tool execution (all deterministic — no LLM calls here)
    # ------------------------------------------------------------------

    def _execute_tool(self, name: str, inputs: dict) -> Any:
        """Execute a named tool and return a JSON-serializable result."""
        try:
            if name == "get_player_profile":
                result = self._store.get_player_profile(inputs["device_id"])
                return result or {"error": "Device not found", "device_id": inputs["device_id"]}

            if name == "get_leaderboard":
                limit = min(int(inputs.get("limit", 10)), 100)
                return self._store.get_leaderboard(limit=limit)

            if name == "get_leaderboard_rank":
                rank = self._store.get_leaderboard_rank(inputs["device_id"])
                return {
                    "device_id": inputs["device_id"],
                    "rank": rank,
                    "ranked": rank is not None,
                }

            if name == "run_pitl_calibration":
                from .pitl_calibration import calibrate  # local import avoids circular dep

                buf = io.StringIO()
                with redirect_stdout(buf):
                    calibrate(self._store, inputs.get("device_id"))
                return {"output": buf.getvalue()}

            if name == "get_continuity_chain":
                chain = self._store.get_continuity_chain(inputs["device_id"])
                return {
                    "device_id": inputs["device_id"],
                    "chain": chain,
                    "length": len(chain),
                }

            if name == "get_recent_records":
                limit = min(int(inputs.get("limit", 20)), 100)
                records = self._store.get_recent_records(
                    device_id=inputs.get("device_id"),
                    limit=limit,
                )
                return {"records": records, "count": len(records)}

            if name == "get_startup_diagnostics":
                circuits_dir = Path(__file__).parents[2] / "contracts" / "circuits"
                return {
                    "zk_artifacts": {
                        circuit: (circuits_dir / f"{circuit}_final.zkey").exists()
                        for circuit in ("TeamProof", "PitlSessionProof")
                    },
                    "chain_rpc": getattr(self._cfg, "iotex_rpc_url", "") or None,
                    "phg_credential_address": getattr(self._cfg, "phg_credential_address", "") or None,
                    "operator_key_configured": bool(getattr(self._cfg, "operator_api_key", "")),
                }

            if name == "get_phg_checkpoints":
                limit = min(int(inputs.get("limit", 10)), 50)
                cps = self._store.get_phg_checkpoints(inputs["device_id"], limit=limit)
                return {
                    "device_id": inputs["device_id"],
                    "checkpoints": cps,
                    "count": len(cps),
                }

            if name == "check_eligibility":
                cp = self._store.get_last_phg_checkpoint(inputs["device_id"])
                cred = self._store.get_credential_mint(inputs["device_id"])
                score = cp["last_committed_score"] if cp else 0
                return {
                    "device_id": inputs["device_id"],
                    "eligible": score > 0,
                    "cumulative_score": score,
                    "has_credential": cred is not None,
                    "credential_id": cred["credential_id"] if cred else None,
                }

            if name == "get_pitl_proof":
                proof = self._store.get_latest_pitl_proof(inputs["device_id"])
                return proof or {
                    "error": "No PITL proof found",
                    "device_id": inputs["device_id"],
                }

            if name == "get_behavioral_report":
                if not self._behavioral_arch:
                    return {"error": "BehavioralArchaeologist not available"}
                report = self._behavioral_arch.analyze_device(inputs["device_id"])
                return dataclasses.asdict(report)

            if name == "get_network_clusters":
                if not self._network_detector:
                    return {"error": "NetworkCorrelationDetector not available"}
                min_s = float(inputs.get("min_suspicion", 0.3))
                clusters = self._network_detector.detect_clusters()
                return {
                    "clusters": [dataclasses.asdict(c) for c in clusters
                                 if c.farm_suspicion_score >= min_s],
                    "flagged_count": sum(1 for c in clusters if c.is_flagged),
                    "total_clusters": len(clusters),
                }

            if name == "get_federation_status":
                peers_raw = getattr(self._cfg, "federation_peers", "")
                peers = [p.strip() for p in peers_raw.split(",") if p.strip()] if peers_raw else []
                min_peers = int(inputs.get("min_peers", 2))
                try:
                    cross_confirmed = self._store.get_cross_confirmed_hashes(min_peers=min_peers)
                except Exception:
                    cross_confirmed = []
                try:
                    all_fed = self._store.get_federation_clusters(limit=20)
                except Exception:
                    all_fed = []
                local_fed = [c for c in all_fed if c.get("is_local")]
                remote_fed = [c for c in all_fed if not c.get("is_local")]
                return {
                    "peer_count": len(peers),
                    "peers_configured": peers,
                    "local_clusters_detected": len(local_fed),
                    "remote_clusters_received": len(remote_fed),
                    "cross_confirmed_hashes": cross_confirmed,
                    "cross_confirmed_count": len(cross_confirmed),
                    "federation_enabled": bool(peers_raw),
                }

            if name == "get_detection_policy":
                device_id = inputs.get("device_id", "").strip()
                risk_filter = inputs.get("risk_filter", "all")
                if device_id:
                    policy = self._store.get_detection_policy(device_id)
                    policies = [policy] if policy else []
                else:
                    policies = self._store.get_all_active_policies()
                if risk_filter and risk_filter != "all":
                    policies = [p for p in policies if p.get("basis_label") == risk_filter]
                return {
                    "policies": policies,
                    "total_count": len(policies),
                    "adaptive_enabled": bool(
                        getattr(self._cfg, "adaptive_thresholds_enabled", True)
                    ),
                    "critical_policy_multiplier": 0.70,
                    "warming_policy_multiplier": 0.85,
                }

            if name == "query_digest":
                window = inputs.get("window", "all")
                include_labels = bool(inputs.get("include_device_labels", False))
                risk_filter = inputs.get("risk_filter", None)

                try:
                    if window == "all":
                        digests = self._store.get_all_latest_digests()
                    elif window in ("24h", "7d", "30d"):
                        d = self._store.get_latest_digest(window)
                        digests = [d] if d else []
                    else:
                        digests = self._store.get_all_latest_digests()
                except Exception as exc:
                    digests = []
                    log.warning("query_digest: store error: %s", exc)

                result: dict = {
                    "synthesis_available": len(digests) > 0,
                    "digests": digests,
                }

                if include_labels or risk_filter:
                    try:
                        if risk_filter:
                            labels = self._store.get_devices_by_risk_label(risk_filter)
                        else:
                            labels = (
                                self._store.get_devices_by_risk_label("critical")
                                + self._store.get_devices_by_risk_label("warming")
                                + self._store.get_devices_by_risk_label("cleared")
                                + self._store.get_devices_by_risk_label("stable")
                            )
                        result["device_labels"] = labels
                        result["critical_device_count"] = len(
                            self._store.get_devices_by_risk_label("critical")
                        )
                        result["warming_device_count"] = len(
                            self._store.get_devices_by_risk_label("warming")
                        )
                    except Exception as exc:
                        result["device_labels"] = []
                        log.warning("query_digest: label fetch error: %s", exc)

                return result

            if name == "get_credential_status":
                device_id = inputs.get("device_id", "").strip()
                if not device_id:
                    return {"error": "device_id is required"}
                credential  = self._store.get_credential_mint(device_id)
                enforcement = self._store.get_credential_enforcement(device_id)
                risk_label  = self._store.get_device_risk_label(device_id)
                policy      = self._store.get_detection_policy(device_id)
                is_suspended = bool((enforcement or {}).get("suspended", False))
                return {
                    "device_id":                    device_id,
                    "has_credential":               credential is not None,
                    "is_active":                    credential is not None and not is_suspended,
                    "suspended":                    is_suspended,
                    "suspended_since":              (enforcement or {}).get("suspended_since"),
                    "suspended_until":              (enforcement or {}).get("suspended_until"),
                    "evidence_hash":                (enforcement or {}).get("evidence_hash"),
                    "consecutive_critical_windows": (enforcement or {}).get("consecutive_critical", 0),
                    "current_risk_label":           (risk_label or {}).get("risk_label", "unknown"),
                    "active_detection_policy":      policy,
                    "credential_minted_at":         (credential or {}).get("minted_at"),
                    "reinstatement_conditions": (
                        "Suspension clears when InsightSynthesizer labels this device 'cleared' "
                        "(requires >= 1 7-day window with zero critical or warming signals)."
                    ),
                    "enforcement_enabled": bool(
                        getattr(self._cfg, "phg_credential_enforcement_enabled", True)
                    ),
                }

            if name == "get_calibration_status":
                profiles = self._store.get_all_player_calibration_profiles()
                live: dict = {}
                try:
                    import json as _json
                    with open("calibration_profile_live.json") as _f:
                        live = _json.load(_f)
                except (FileNotFoundError, ValueError):
                    pass
                # Retrieve recent calibration_update insights (last 5)
                all_updates = self._store.get_insights_since(
                    time.time() - 5 * 21600  # last 5 cycles (30h)
                )
                recent_evolution = [
                    {"timestamp": r.get("created_at"), "narrative": r.get("content")}
                    for r in all_updates
                    if r.get("insight_type") == "calibration_update"
                ][:5]
                return {
                    "global_thresholds": {
                        "l4_anomaly":      getattr(self._cfg, "l4_anomaly_threshold", 7.019),
                        "l4_continuity":   getattr(self._cfg, "l4_continuity_threshold", 5.369),
                        "last_calibration": live.get("generated_at", "never"),
                        "source_records":   live.get("total_records", 0),
                        "confidence":       live.get("confidence", "unknown"),
                    },
                    "player_profiles": profiles,
                    "recent_evolution": recent_evolution,
                    "next_cycle_in": "up to 6h (aligned with InsightSynthesizer cycle)",
                }

            # Phase 50: 3 new tools
            if name == "get_session_narrative":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id is required"}
                recent = self._store.get_recent_records(device_id=device_id, limit=5)
                profile = self._store.get_player_profile(device_id)
                if not recent:
                    return {"error": "No records found for device", "device_id": device_id}
                last = recent[0]
                inference_name = last.get("action_name", "UNKNOWN")
                humanity_prob  = last.get("pitl_humanity_prob")
                l4_dist  = last.get("pitl_l4_distance")
                l5_cv    = last.get("pitl_l5_cv")
                l4_drift = last.get("pitl_l4_drift_velocity")
                # sentence_1
                layers = []
                if l4_dist is not None:
                    layers.append(f"L4={l4_dist:.3f}")
                if l5_cv is not None:
                    layers.append(f"L5_cv={l5_cv:.3f}")
                sent1 = (
                    f"Session inference: {inference_name}; "
                    f"PITL signals: {', '.join(layers) or 'none'}; "
                    f"humanity_prob={humanity_prob}."
                )
                # sentence_2
                total = (profile or {}).get("total_records", 0)
                drift_ctx = (
                    f"L4 drift_velocity={l4_drift:.3f}" if l4_drift is not None
                    else "drift velocity unavailable"
                )
                sent2 = f"Device has {total} total records; {drift_ctx}."
                # sentence_3
                if len(recent) >= 2:
                    avg_h = sum(r.get("pitl_humanity_prob") or 0.5 for r in recent) / len(recent)
                    sent3 = f"Trend across last {len(recent)} sessions: mean humanity_prob={avg_h:.3f}."
                else:
                    sent3 = "Insufficient session history for trend analysis."
                return {
                    "device_id": device_id,
                    "sentence_1": sent1,
                    "sentence_2": sent2,
                    "sentence_3": sent3,
                }

            if name == "compare_device_fingerprints":
                device_a = inputs.get("device_id_a", "")
                device_b = inputs.get("device_id_b", "")
                if not device_a or not device_b:
                    return {"error": "device_id_a and device_id_b are required"}
                profiles = self._store.get_all_player_calibration_profiles()
                profile_a = next((p for p in profiles if p.get("device_id") == device_a), None)
                profile_b = next((p for p in profiles if p.get("device_id") == device_b), None)
                if profile_a is None or profile_b is None:
                    missing = []
                    if profile_a is None:
                        missing.append(device_a[:16])
                    if profile_b is None:
                        missing.append(device_b[:16])
                    return {
                        "error": f"Missing calibration profiles for: {', '.join(missing)} "
                                 f"(need >=30 NOMINAL records each)",
                        "plain_english": (
                            "Cannot compare — calibration data unavailable. "
                            "separation ratio 0.362 (L4 is intra-player anomaly detector only)."
                        ),
                    }
                mean_a = float(profile_a.get("baseline_mean") or 0.0)
                mean_b = float(profile_b.get("baseline_mean") or 0.0)
                std_a  = float(profile_a.get("baseline_std") or 1.0) or 1.0
                dist   = abs(mean_a - mean_b) / std_a
                if dist > _PHASE46_ANOMALY_ANCHOR:
                    verdict = "DISTINCT"
                elif dist > _PHASE46_CONTINUITY_ANCHOR:
                    verdict = "INDETERMINATE"
                else:
                    verdict = "SIMILAR"
                plain_english = (
                    f"Devices are {verdict} (Mahalanobis distance={dist:.3f}). "
                    f"separation ratio 0.362 — L4 is intra-player anomaly detector only; "
                    f"SIMILAR does not confirm same identity."
                )
                return {
                    "device_id_a": device_a,
                    "device_id_b": device_b,
                    "mahalanobis_distance": round(dist, 3),
                    "verdict": verdict,
                    "thresholds": {
                        "distinct_above": _PHASE46_ANOMALY_ANCHOR,
                        "indeterminate_above": _PHASE46_CONTINUITY_ANCHOR,
                    },
                    "plain_english": plain_english,
                }

            if name == "get_calibration_agent_status":
                try:
                    events = self._store.read_unconsumed_events("bridge_agent", limit=5)
                except Exception:
                    events = []
                try:
                    pending = self._store.read_unconsumed_events(
                        "calibration_intelligence_agent", limit=100
                    )
                    pending_count = len(pending)
                except Exception:
                    pending_count = 0
                try:
                    th_history = self._store.get_threshold_history(limit=1)
                    last_history = th_history[0] if th_history else None
                except Exception:
                    last_history = None
                return {
                    "current_thresholds": {
                        "l4_anomaly":    getattr(self._cfg, "l4_anomaly_threshold", 6.726),
                        "l4_continuity": getattr(self._cfg, "l4_continuity_threshold", 5.097),
                        "phase46_anchors": {
                            "anomaly":    _PHASE46_ANOMALY_ANCHOR,
                            "continuity": _PHASE46_CONTINUITY_ANCHOR,
                        },
                    },
                    "recent_events_from_calib_agent": events,
                    "pending_flags_count": pending_count,
                    "last_threshold_history": last_history,
                    "peer_status": (
                        "CalibrationIntelligenceAgent (event-driven peer, 30-min consumer)"
                    ),
                }

            elif name == "get_game_profile":
                _gp_id = getattr(self._cfg, "game_profile_id", "")
                if not _gp_id:
                    result = {
                        "active": False,
                        "message": "No game profile configured. Set GAME_PROFILE_ID in bridge/.env.",
                    }
                else:
                    try:
                        from vapi_bridge.game_profile import get_profile_or_none
                        _gp = get_profile_or_none(_gp_id)
                        if _gp is None:
                            result = {
                                "active": False,
                                "profile_id": _gp_id,
                                "error": f"Profile '{_gp_id}' not found in registry",
                            }
                        else:
                            result = {
                                "active":            True,
                                "profile_id":        _gp.profile_id,
                                "display_name":      _gp.display_name,
                                "platform":          _gp.platform,
                                "l5_button_priority": list(_gp.l5_button_priority),
                                "l6_passive_enabled": _gp.l6_passive_enabled,
                                "l6_passive_button":  _gp.l6_passive_button,
                                "l6_passive_flag_ratio": _gp.l6_passive_flag_ratio,
                                "button_map":        dict(_gp.button_map),
                            }
                    except Exception as _exc:
                        result = {"active": False, "error": str(_exc)}
                return result

            elif name == "get_ioid_status":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                # Derive device address from last 20 bytes of device_id
                try:
                    dev_bytes = bytes.fromhex(device_id.ljust(64, "0"))[:32]
                    device_address = "0x" + dev_bytes[-20:].hex()
                    did = f"did:io:{device_address}"
                except Exception:
                    device_address = ""
                    did = ""
                # Check local store
                ioid_record = self._store.get_ioid_device(device_id)
                if ioid_record:
                    result = {
                        "registered": True,
                        "device_id":       device_id[:16],
                        "did":             ioid_record.get("did", did),
                        "device_address":  ioid_record.get("device_address", device_address),
                        "tx_hash":         ioid_record.get("tx_hash", ""),
                        "registered_at":   ioid_record.get("registered_at", 0),
                        "source":          "local_store",
                    }
                else:
                    result = {
                        "registered": False,
                        "device_id":      device_id[:16],
                        "derived_did":    did,
                        "device_address": device_address,
                        "message": (
                            "Device not yet registered in ioID registry. "
                            "Registration occurs automatically on first PITL proof submission."
                        ),
                    }
                return result

            elif name == "generate_tournament_passport":
                device_id  = inputs.get("device_id", "")
                min_humanity = float(inputs.get("min_humanity", 0.60))
                if not device_id:
                    return {"error": "device_id required"}
                # Check ioID registration
                ioid_record = self._store.get_ioid_device(device_id)
                if not ioid_record:
                    return {
                        "status":     "ioid_not_registered",
                        "device_id":  device_id[:16],
                        "message": (
                            "Device is not in the ioID registry. Cannot issue tournament passport. "
                            "Ensure at least one PITL proof has been submitted."
                        ),
                    }
                # Check for existing passport
                existing_passport = self._store.get_tournament_passport(device_id)
                if existing_passport and existing_passport.get("passport_hash"):
                    return {
                        "status":          "passport_ready",
                        "device_id":       device_id[:16],
                        "did":             ioid_record.get("did", ""),
                        "passport_hash":   existing_passport.get("passport_hash", ""),
                        "min_humanity_int": existing_passport.get("min_humanity_int", 0),
                        "issued_at":       existing_passport.get("issued_at", 0),
                        "on_chain":        bool(existing_passport.get("on_chain", 0)),
                    }
                # Check eligible sessions
                eligible = self._store.get_passport_eligible_sessions(
                    device_id, min_humanity, limit=10
                )
                n_eligible = len(eligible)
                if n_eligible < 5:
                    return {
                        "status":          "pending_sessions",
                        "device_id":       device_id[:16],
                        "did":             ioid_record.get("did", ""),
                        "eligible_sessions": n_eligible,
                        "required":        5,
                        "min_humanity":    min_humanity,
                        "message": (
                            f"Only {n_eligible}/5 eligible sessions (humanity >= {min_humanity:.0%}). "
                            "Continue playing to accumulate NOMINAL sessions."
                        ),
                    }
                # Eligible: return summary
                min_hp = min(s.get("pitl_humanity_prob", 0.0) or 0.0 for s in eligible[:5])
                return {
                    "status":            "eligible",
                    "device_id":         device_id[:16],
                    "did":               ioid_record.get("did", ""),
                    "eligible_sessions": n_eligible,
                    "min_humanity_prob": round(min_hp, 4),
                    "min_humanity_int":  int(min_hp * 1000),
                    "message": (
                        f"{n_eligible} eligible sessions found. "
                        "Passport can be issued on next PITL proof submission."
                    ),
                }

            # Phase 58: Tools #24–27
            if name == "analyze_threshold_impact":
                threshold_type = inputs.get("threshold_type", "anomaly")
                delta_pct = float(inputs.get("delta_pct", 0.0))
                current = (self._cfg.l4_anomaly_threshold if threshold_type == "anomaly"
                           else self._cfg.l4_continuity_threshold)
                proposed = current * (1 + delta_pct / 100.0)
                with self._store._conn() as conn:
                    rows = conn.execute(
                        "SELECT pitl_l4_distance, inference FROM records WHERE pitl_l4_distance IS NOT NULL"
                    ).fetchall()
                if not rows:
                    return {"threshold_type": threshold_type, "current_threshold": current,
                            "proposed_threshold": proposed, "total_sessions": 0,
                            "nominal_to_anomaly": 0, "anomaly_to_nominal": 0, "flip_pct": 0.0}
                nominal_to_anomaly = sum(1 for r in rows
                                         if r["pitl_l4_distance"] < current and r["pitl_l4_distance"] >= proposed)
                anomaly_to_nominal = sum(1 for r in rows
                                         if r["pitl_l4_distance"] >= current and r["pitl_l4_distance"] < proposed)
                return {
                    "threshold_type": threshold_type,
                    "current_threshold": current,
                    "proposed_threshold": round(proposed, 4),
                    "delta_pct": delta_pct,
                    "total_sessions": len(rows),
                    "nominal_to_anomaly": nominal_to_anomaly,
                    "anomaly_to_nominal": anomaly_to_nominal,
                    "flip_pct": round(100.0 * (nominal_to_anomaly + anomaly_to_nominal) / len(rows), 2),
                }

            if name == "predict_evasion_cost":
                _ATTACK_DB = {
                    "G": {"layers_to_evade": ["L4", "L2B"], "l4_detection": "0% (batch), live via grip_variance",
                          "validation_n": 5,
                          "detection_notes": "zeroed accel evades L4 batch; L2B catches IMU-button decoupling"},
                    "H": {"layers_to_evade": ["L4"], "l4_detection": "100%", "validation_n": 5,
                          "detection_notes": "threshold-aware replay still anomalous vs personal Mahalanobis mean"},
                    "I": {"layers_to_evade": ["L4", "L2B", "L5"], "l4_detection": "0% (batch), live L4+L2B",
                          "validation_n": 5,
                          "detection_notes": "spectral mimicry passes L4 batch; live L2B triggers on decoupled IMU"},
                    "J": {"layers_to_evade": ["L4"], "l4_detection": "predicted 100% (jitter_var < 0.00005 s²)",
                          "validation_n": 0,
                          "detection_notes": "AntiMicro constant-interval presses; UNVALIDATED — macro sessions not yet captured"},
                    "K": {"layers_to_evade": ["L4", "L5"], "l4_detection": "unknown", "validation_n": 0,
                          "detection_notes": "reWASD Gaussian-jittered IBIs; UNVALIDATED"},
                }
                cls = inputs.get("attack_class", "").upper()
                rec = _ATTACK_DB.get(cls)
                if not rec:
                    return {"error": f"Unknown attack class '{cls}'. Validated: G, H, I. Hypothesized: J, K."}
                return {
                    "attack_class": cls,
                    **rec,
                    "separation_gap_note": (
                        "Inter-person separation ratio=0.362. Biometric transplant attack "
                        "(P1 uses P2 device) has 0% detection at all layers. Tournament blocker."
                    ),
                }

            if name == "get_anomaly_trend":
                device_id = inputs.get("device_id", "")
                days = int(inputs.get("days", 7))
                cutoff = time.time() - days * 86400
                with self._store._conn() as conn:
                    rows = conn.execute(
                        "SELECT pitl_l4_distance, pitl_humanity_prob, inference, created_at "
                        "FROM records WHERE device_id = ? AND created_at >= ? "
                        "AND pitl_l4_distance IS NOT NULL ORDER BY created_at ASC",
                        (device_id, cutoff),
                    ).fetchall()
                if not rows:
                    return {"device_id": device_id[:16], "session_count": 0, "days": days,
                            "message": "No warmed L4 sessions in window"}
                dists = [r["pitl_l4_distance"] for r in rows]
                hums  = [r["pitl_humanity_prob"] for r in rows if r["pitl_humanity_prob"] is not None]
                thr   = self._cfg.l4_anomaly_threshold
                mean_d = sum(dists) / len(dists)
                mid    = max(1, len(dists) // 2)
                first_h = sum(dists[:mid]) / mid
                second_h = sum(dists[mid:]) / max(len(dists) - mid, 1)
                trend = ("DEGRADING" if second_h > first_h * 1.1
                         else "IMPROVING" if second_h < first_h * 0.9 else "STABLE")
                return {
                    "device_id": device_id[:16], "days": days, "session_count": len(rows),
                    "mean_l4_distance": round(mean_d, 4),
                    "std_l4_distance": round((sum((d-mean_d)**2 for d in dists)/len(dists))**0.5, 4),
                    "mean_humanity": round(sum(hums)/len(hums), 4) if hums else None,
                    "anomaly_threshold": thr,
                    "spike_count": sum(1 for d in dists if d >= thr),
                    "spike_pct": round(100.0 * sum(1 for d in dists if d >= thr) / len(rows), 1),
                    "trend": trend,
                }

            if name == "generate_incident_report":
                device_id = inputs.get("device_id", "")
                dev     = self._store.get_device(device_id) or {}
                profile = self._store.get_player_profile(device_id) or {}
                with self._store._conn() as conn:
                    breakdown = conn.execute(
                        "SELECT inference, COUNT(*) as cnt FROM records WHERE device_id=? GROUP BY inference",
                        (device_id,),
                    ).fetchall()
                    recent = conn.execute(
                        "SELECT pitl_l4_distance, pitl_humanity_prob, inference, created_at "
                        "FROM records WHERE device_id=? ORDER BY created_at DESC LIMIT 10",
                        (device_id,),
                    ).fetchall()
                ioid     = self._store.get_ioid_device(device_id) or {}
                passport = self._store.get_tournament_passport(device_id) or {}
                calib    = self._store.get_player_calibration_profile(device_id) or {}
                insights = self._store.get_recent_insights(limit=5) if hasattr(self._store, "get_recent_insights") else []
                return {
                    "device_id": device_id[:16],
                    "first_seen": dev.get("first_seen"),
                    "last_seen": dev.get("last_seen"),
                    "records_total": dev.get("records_total", 0),
                    "records_verified": dev.get("records_verified", 0),
                    "inference_breakdown": {str(r["inference"]): r["cnt"] for r in breakdown},
                    "humanity_prob": profile.get("humanity_prob"),
                    "phg_score": profile.get("phg_score"),
                    "recent_sessions": [dict(r) for r in recent],
                    "ioid": {
                        "registered": bool(ioid),
                        "did": ioid.get("did"),
                        "tx_hash": ioid.get("tx_hash"),
                    },
                    "tournament_passport": {
                        "issued": bool(passport),
                        "passport_hash": passport.get("passport_hash"),
                        "on_chain": bool(passport.get("on_chain")),
                        "issued_at": passport.get("issued_at"),
                    },
                    "calibration": {
                        "has_profile": bool(calib),
                        "anomaly_threshold": calib.get("anomaly_threshold"),
                        "continuity_threshold": calib.get("continuity_threshold"),
                        "record_count": calib.get("session_count"),
                    },
                    "recent_insights": insights,
                }

            if name == "get_controller_twin_data":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                return self._store.get_controller_twin_snapshot(device_id)

            if name == "get_session_replay":
                device_id   = inputs.get("device_id", "")
                record_hash = inputs.get("record_hash", "")
                if not device_id or not record_hash:
                    return {"error": "device_id and record_hash required"}
                result = self._store.get_frame_checkpoint(device_id, record_hash)
                return result if result is not None else {"frames": [], "frame_count": 0}

            if name == "get_enrollment_status":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                row = self._store.get_enrollment(device_id)
                min_sessions = getattr(self._cfg, "enrollment_min_sessions", 10)
                if not row:
                    nominal, avg_h = self._store.count_nominal_sessions(device_id)
                    return {
                        "device_id":       device_id,
                        "status":          "pending",
                        "sessions_nominal": nominal,
                        "avg_humanity":    round(avg_h, 3),
                        "sessions_needed": max(0, min_sessions - nominal),
                    }
                needed = max(0, min_sessions - row["sessions_nominal"])
                return {**row, "sessions_needed": needed}

            if name == "get_reflex_baseline":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                result = self._store.get_l6b_baseline(device_id)
                if result and result.get("probe_count", 0) == 0:
                    result["l6b_enabled"] = getattr(self._cfg, "l6b_enabled", False)
                    result["status"] = "no_probes_recorded"
                return result

            if name == "get_autonomous_rulings":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                limit = int(inputs.get("limit", 10))
                return {
                    "device_id": device_id,
                    "rulings": self._store.get_agent_rulings(device_id, limit=min(limit, 50)),
                }

            if name == "request_adjudication":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                eid = self._store.write_agent_event(
                    event_type="ruling_request",
                    payload=json.dumps({
                        "device_id":        device_id,
                        "attestation_hash": inputs.get("attestation_hash", ""),
                        "reason":           inputs.get("reason", "bridge_agent_request"),
                    }),
                    source="bridge_agent",
                    target="session_adjudicator",
                    device_id=device_id,
                )
                return {"status": "queued", "event_id": eid}

            if name == "get_ruling_streak":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                streak = self._store.get_ruling_streak(device_id)
                return streak if streak else {"device_id": device_id, "current_streak": 0,
                                              "streak_verdict": "", "escalated_to": None}

            if name == "override_ruling":
                device_id = inputs.get("device_id", "")
                reason    = inputs.get("reason", "bridge_agent_override")
                if not device_id:
                    return {"error": "device_id required"}
                ruling_id = self._store.insert_agent_ruling(
                    device_id=device_id,
                    verdict="CLEAR",
                    confidence=1.0,
                    reasoning=f"Agent override: {reason}",
                    evidence_json="{}",
                    commitment_hash="0" * 64,
                    attestation_hash="",
                    dry_run=False,
                    source_agent="bridge_agent",
                )
                self._store.upsert_ruling_streak(device_id, "CLEAR", ruling_id)
                return {"status": "cleared", "ruling_id": ruling_id, "device_id": device_id}

            # --- Phase 68 Tools (#36-40) ---

            if name == "verify_ceremony_integrity":
                circuit_name = inputs.get("circuit_name", "PitlSessionProof")
                registry_addr = getattr(self._cfg, "ceremony_registry_address", "")
                rpc_url = getattr(self._cfg, "iotex_rpc_url", "")
                try:
                    from .sdk_compat import _get_vkey_dict
                    vkey_dict = _get_vkey_dict()
                except Exception:
                    vkey_dict = {}
                try:
                    from ..sdk.vapi_sdk import VAPIZKProof  # type: ignore[import]
                except Exception:
                    try:
                        import importlib
                        sdk_mod = importlib.import_module("vapi_sdk")
                        VAPIZKProof = sdk_mod.VAPIZKProof
                    except Exception as exc:
                        return {"error": f"SDK not available: {exc}", "on_chain_match": False}
                result = VAPIZKProof.verify_ceremony_integrity(
                    vkey_dict, registry_addr, rpc_url, circuit_name
                )
                return result

            if name == "get_suspension_status":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                import time as _time
                streak = self._store.get_ruling_streak(device_id)
                now = _time.time()
                try:
                    with self._store._conn() as conn:
                        row = conn.execute(
                            "SELECT * FROM credential_enforcement WHERE device_id=?"
                            " ORDER BY rowid DESC LIMIT 1",
                            (device_id,),
                        ).fetchone()
                        susp = dict(row) if row else None
                except Exception:
                    susp = None
                active = bool(
                    susp
                    and susp.get("suspended")
                    and susp.get("suspended_until") is not None
                    and susp["suspended_until"] > now
                    and not susp.get("reinstated")
                )
                return {
                    "device_id": device_id,
                    "suspended": active,
                    "suspended_until": susp["suspended_until"] if active else None,
                    "seconds_remaining": max(0.0, susp["suspended_until"] - now) if active else 0.0,
                    "ruling_streak": streak,
                }

            if name == "get_zk_verifier_stats":
                chain = getattr(self, "_chain", None)
                if chain is None:
                    return {"error": "chain client not available", "enabled": False}
                if hasattr(chain, "get_zk_verifier_stats"):
                    return chain.get_zk_verifier_stats()
                return {"error": "get_zk_verifier_stats not available on chain client"}

            if name == "get_enrollment_pipeline":
                try:
                    all_enrollments = self._store.get_all_enrollments() if hasattr(
                        self._store, "get_all_enrollments"
                    ) else []
                except Exception:
                    all_enrollments = []
                pipeline = {"eligible": [], "in_progress": [], "unenrolled": []}
                for enr in all_enrollments:
                    status = enr.get("status", "unenrolled")
                    device_id = enr.get("device_id", "")
                    entry = {
                        "device_id": device_id,
                        "nominal_sessions": enr.get("nominal_sessions", 0),
                        "avg_humanity": enr.get("avg_humanity", 0.0),
                    }
                    if status == "eligible":
                        pipeline["eligible"].append(entry)
                    elif status in ("enrolled", "in_progress"):
                        pipeline["in_progress"].append(entry)
                    else:
                        pipeline["unenrolled"].append(entry)
                return {
                    "eligible_count": len(pipeline["eligible"]),
                    "in_progress_count": len(pipeline["in_progress"]),
                    "unenrolled_count": len(pipeline["unenrolled"]),
                    "pipeline": pipeline,
                }

            if name == "request_live_adjudication":
                device_id = inputs.get("device_id", "")
                reason    = inputs.get("reason", "bridge_agent_live_request")
                if not device_id:
                    return {"error": "device_id required"}
                eid = self._store.write_agent_event(
                    event_type="ruling_request",
                    payload=json.dumps({
                        "device_id":        device_id,
                        "attestation_hash": "",
                        "reason":           reason,
                        "live":             True,
                    }),
                    source="bridge_agent",
                    target="session_adjudicator",
                    device_id=device_id,
                )
                return {
                    "status": "queued_live",
                    "event_id": eid,
                    "device_id": device_id,
                    "note": "SessionAdjudicator will process this with dry_run=False within 5 minutes",
                }

            # --- Phase 70 Tools (#41-45) ---

            if name == "get_data_lineage":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                limit = min(int(inputs.get("limit", 50)), 200)
                lineage = self._store.get_data_lineage(device_id.strip(), limit=limit)
                return {
                    "device_id":     device_id,
                    "lineage_count": len(lineage),
                    "lineage":       lineage,
                }

            if name == "get_token_eligibility":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                elig = self._store.get_token_eligibility(device_id.strip())
                if not elig:
                    return {
                        "device_id":   device_id,
                        "eligibility": None,
                        "note": "No eligibility record — DataCuratorAgent hasn't processed this device yet",
                    }
                return {"device_id": device_id, "eligibility": elig}

            if name == "get_oracle_state":
                oracle_type = inputs.get("oracle_type", "").upper().strip()
                _VALID_ORACLES = {"HUMANITY", "RULING", "PASSPORT"}
                if oracle_type not in _VALID_ORACLES:
                    return {
                        "error": f"Unknown oracle_type '{oracle_type}'. Use: HUMANITY | RULING | PASSPORT",
                        "valid_types": list(_VALID_ORACLES),
                    }
                pubs = self._store.get_oracle_publications(oracle_type=oracle_type, limit=10)
                return {
                    "oracle_type":       oracle_type,
                    "publication_count": len(pubs),
                    "publications":      pubs,
                }

            if name == "compute_reward_score":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                try:
                    from .data_curator_agent import DataCuratorAgent
                    _curator = DataCuratorAgent(self._cfg, self._store, chain=None)
                    return _curator.compute_reward_score_sync(device_id.strip())
                except Exception as exc:
                    return {"error": str(exc), "device_id": device_id}

            if name == "publish_sovereignty_pledge":
                # Operator auth: this tool queues an event rather than calling chain directly
                # (avoids loop.run_until_complete() in sync _execute_tool context — Phase 70)
                if not getattr(self._cfg, "operator_api_key", ""):
                    return {"error": "Operator auth required — OPERATOR_API_KEY not configured"}
                eid = self._store.write_agent_event(
                    event_type="sovereignty_pledge_request",
                    payload=json.dumps({
                        "requested_by": "bridge_agent",
                        "requested_at": time.time(),
                    }),
                    source="bridge_agent",
                    target="data_curator_agent",
                    device_id="",
                )
                return {
                    "status":  "queued",
                    "event_id": eid,
                    "note": (
                        "DataCuratorAgent will process this within 5 minutes and commit "
                        "the schema hash to DataSovereigntyRegistry.sol on IoTeX."
                    ),
                }

            # Tool #47 — Phase 76
            if name == "get_ruling_provenance":
                ruling_id = int(inputs.get("ruling_id", 0))
                anchor = self._store.get_provenance_anchor(ruling_id)
                if anchor is None:
                    return {
                        "error": "Provenance anchor not yet computed",
                        "ruling_id": ruling_id,
                        "note": "RulingProvenanceAnchorAgent processes anchors every 5 minutes.",
                    }
                return anchor

            # Tool #46 — Phase 75 (updated Phase 78: passes max_divergence_rate)
            if name == "get_validation_gate_status":
                gate_n = int(getattr(self._cfg, "validation_gate_n", 100))
                max_rate = float(getattr(self._cfg, "validation_max_divergence_rate", 1.0))
                return self._store.get_validation_gate_status(gate_n, max_rate)

            # Tool #48 — Phase 79
            if name == "get_live_mode_status":
                try:
                    from .live_mode_activation_agent import LiveModeActivationAgent
                    _lma = LiveModeActivationAgent(self._cfg, self._store, bus=None)
                    return _lma.get_live_mode_status()
                except Exception as exc:
                    return {"error": str(exc)}

            # Tool #49 — Phase 80
            if name == "get_federation_status":
                try:
                    peers_str = getattr(self._cfg, "federation_broadcast_peers", "")
                    peers = (
                        [p.strip() for p in peers_str.split(",") if p.strip()]
                        if peers_str else []
                    )
                    stats = self._store.get_federation_stats()
                    return {
                        "federation_enabled": getattr(
                            self._cfg, "federation_broadcast_enabled", False
                        ),
                        "peers": peers,
                        "peer_count": len(peers),
                        **stats,
                    }
                except Exception as exc:
                    return {"error": str(exc)}

            # Tool #50 — Phase 81
            if name == "get_class_j_assessment":
                device_id = inputs.get("device_id", "")
                if not device_id:
                    return {"error": "device_id required"}
                try:
                    assessment = self._store.get_class_j_assessment(device_id.strip())
                    if not assessment:
                        return {
                            "device_id": device_id,
                            "assessment": None,
                            "note": (
                                "No Class J assessment yet — ClassJDetector has not "
                                "processed this device (requires >=2 session windows)"
                            ),
                        }
                    return {"device_id": device_id, "assessment": assessment}
                except Exception as exc:
                    return {"error": str(exc), "device_id": device_id}

            # Tool #51 — Phase 82
            if name == "get_reactive_adjudication_status":
                device_id = inputs.get("device_id") or None
                limit = int(inputs.get("limit", 20))
                try:
                    entries = self._store.get_reactive_adjudication_log(
                        device_id=device_id, limit=limit
                    )
                    deferred = sum(1 for e in entries if e.get("was_deferred"))
                    return {
                        "entries": entries,
                        "total_returned": len(entries),
                        "deferred_count": deferred,
                        "note": (
                            "was_deferred=1 entries were rate-limited by token bucket "
                            "(REACTIVE_ADJUDICATION_RATE_LIMIT, default 2/60s — W1 mitigation)"
                        ),
                    }
                except Exception as exc:
                    return {"error": str(exc)}

            # Tool #52 — Phase 83
            if name == "get_agent_supervisor_status":
                try:
                    from .agent_supervisor import AgentSupervisor
                    supervisor = AgentSupervisor(self._cfg, self._store)
                    snapshot = supervisor.check_fleet_health()
                    return snapshot
                except Exception as exc:
                    return {"error": str(exc), "fleet_health": "UNKNOWN"}

            # Tool #53 — Phase 84
            if name == "get_gate_readiness":
                import time as _time
                gate_n = int(getattr(self._cfg, "validation_gate_n", 100))
                max_rate = float(getattr(self._cfg, "validation_max_divergence_rate", 1.0))
                dry_run_active = bool(getattr(self._cfg, "agent_dry_run_mode", True))
                try:
                    gate_status = self._store.get_validation_gate_status(gate_n, max_rate)
                except Exception as exc:
                    gate_status = {"gate_passed": False, "error": str(exc)}
                try:
                    from .agent_supervisor import AgentSupervisor
                    fleet = AgentSupervisor(self._cfg, self._store).check_fleet_health()
                except Exception as exc:
                    fleet = {"fleet_health": "UNKNOWN", "error": str(exc)}
                try:
                    att_count = len(self._store.get_gate_attestations(limit=10000))
                except Exception:
                    att_count = 0
                gate_passed = bool(gate_status.get("gate_passed", False))
                fleet_health = fleet.get("fleet_health", "UNKNOWN")
                overall_ready = gate_passed and fleet_health not in ("CRITICAL", "UNKNOWN")
                return {
                    "overall_ready": overall_ready,
                    "dry_run_active": dry_run_active,
                    "gate_attestations_count": att_count,
                    "validation_gate": gate_status,
                    "fleet_health": fleet,
                    "timestamp": _time.time(),
                }

            # Tool #78 — Phase 110
            if name == "get_ioswarm_vhp_mint_status":
                import time as _t110
                try:
                    _mint_logs = self._store.get_ioswarm_vhp_mint_log(limit=100)
                    _auth_count = sum(1 for r in _mint_logs if r.get("authorized"))
                    return {
                        "ioswarm_vhp_mint_enabled":  bool(getattr(self._cfg, "ioswarm_vhp_mint_enabled", False)),
                        "mint_quorum":               float(getattr(self._cfg, "ioswarm_vhp_mint_quorum", 0.80)),
                        "authorized_count":          _auth_count,
                        "denied_count":              len(_mint_logs) - _auth_count,
                        "task_spec_registered":      True,
                        "swarm_fingerprint_count":   sum(1 for r in _mint_logs if r.get("swarm_fingerprint")),
                        "timestamp":                 _t110.time(),
                    }
                except Exception as exc:
                    return {"ioswarm_vhp_mint_enabled": False, "error": str(exc),
                            "timestamp": __import__("time").time()}

            # Tool #77 — Phase 109C
            if name == "get_ioswarm_adjudication_status":
                import time as _t109c
                try:
                    _adj_logs = self._store.get_ioswarm_adjudication_log(limit=100)
                    return {
                        "ioswarm_adjudication_enabled": bool(getattr(self._cfg, "ioswarm_adjudication_enabled", False)),
                        "classj_block_quorum":          float(getattr(self._cfg, "ioswarm_classj_block_quorum", 0.67)),
                        "triage_block_quorum":          float(getattr(self._cfg, "ioswarm_triage_block_quorum", 0.67)),
                        "dual_veto_count":              sum(1 for r in _adj_logs if r.get("dual_veto")),
                        "adjudication_count":           len(_adj_logs),
                        "task_spec_registered":         True,
                        "timestamp":                    _t109c.time(),
                    }
                except Exception as exc:
                    return {"ioswarm_adjudication_enabled": False, "error": str(exc),
                            "timestamp": __import__("time").time()}

            # Tool #76 — Phase 109B
            if name == "get_ioswarm_renewal_status":
                import time as _t109b
                try:
                    _logs_all = self._store.get_ioswarm_renewal_log(limit=100)
                    return {
                        "ioswarm_renewal_enabled": bool(getattr(self._cfg, "ioswarm_renewal_enabled", False)),
                        "min_quorum":              int(getattr(self._cfg, "ioswarm_renewal_min_quorum", 3)),
                        "renewal_count":           len(_logs_all),
                        "task_spec_registered":    True,
                        "recent_approvals":        sum(1 for r in _logs_all if r.get("renewal_approved")),
                        "recent_skips":            sum(1 for r in _logs_all if not r.get("renewal_approved")),
                        "timestamp":               _t109b.time(),
                    }
                except Exception as exc:
                    return {"ioswarm_renewal_enabled": False, "error": str(exc),
                            "timestamp": __import__("time").time()}

            # Tool #75 — Phase 109A
            if name == "get_ioswarm_status":
                import time as _t109
                try:
                    from .ioswarm_task_spec import VAPISwarmTaskSpec as _Spec
                    _spec = _Spec()
                    _logs = self._store.get_ioswarm_consensus_log(limit=1000)
                    return {
                        "ioswarm_enabled":        bool(getattr(self._cfg, "ioswarm_enabled", False)),
                        "quorum_threshold":       float(getattr(self._cfg, "ioswarm_quorum_threshold", 0.60)),
                        "block_quorum_threshold": float(getattr(self._cfg, "ioswarm_block_quorum_threshold", 0.67)),
                        "consensus_count":        len(_logs),
                        "node_count":             int(getattr(self._cfg, "ioswarm_node_count", 5)),
                        "task_spec_registered":   True,
                        "w3bstream_applets":      list(_spec.w3bstream_applets),
                        "vhp_auth_gate_address":  _spec.protocol_lens_address,
                        "timestamp":              _t109.time(),
                    }
                except Exception as exc:
                    return {"ioswarm_enabled": False, "error": str(exc),
                            "timestamp": __import__("time").time()}

            # Tool #74 — Phase 108
            if name == "get_tournament_readiness":
                import time as _t108
                try:
                    snap = self._store.get_latest_tournament_readiness_snapshot()
                    sep  = float(getattr(self._cfg, "separation_ratio_current", 0.362))
                    if snap is None:
                        return {
                            "fully_ready": False, "found": False,
                            "software_conditions_met": 0, "hardware_conditions_met": 0,
                            "separation_ratio_current": sep,
                            "timestamp": _t108.time(),
                        }
                    snap["found"]      = True
                    snap["timestamp"]  = _t108.time()
                    return snap
                except Exception as exc:
                    return {"fully_ready": False, "error": str(exc),
                            "timestamp": __import__("time").time()}

            # Tool #73 — Phase 107
            if name == "get_live_mode_readiness":
                import time as _t107
                try:
                    report = self._store.get_latest_readiness_report()
                    if report is None:
                        return {"ready_for_live": False, "n_tested": 0,
                                "found": False, "timestamp": _t107.time()}
                    report["found"] = True
                    report["timestamp"] = _t107.time()
                    return report
                except Exception as exc:
                    return {"ready_for_live": False, "error": str(exc),
                            "timestamp": __import__("time").time()}

            # Tool #72 — Phase 105
            if name == "get_epistemic_config":
                import time as _t105
                try:
                    curr  = float(getattr(self._cfg, "epistemic_consensus_threshold", 0.60))
                    rec   = float(getattr(self._cfg, "epistemic_recommended_threshold", 0.65))
                    triage= bool(getattr(self._cfg, "epistemic_triage_prereq_required", False))
                    pmi   = self._store.compute_pmi()
                    eff   = rec if (pmi >= 1 and rec > curr) else curr
                    hist  = self._store.get_epistemic_threshold_history(limit=5)
                    return {
                        "configured_threshold": curr, "recommended_threshold": rec,
                        "effective_threshold": eff, "pmi_triggered": pmi >= 1 and rec > curr,
                        "triage_prereq_required": triage, "at_risk": eff < rec,
                        "pmi": pmi, "threshold_history_count": len(hist),
                        "timestamp": _t105.time(),
                    }
                except Exception as exc:
                    return {"error": str(exc), "timestamp": __import__("time").time()}

            # Tool #71 — Phase 104
            if name == "get_protocol_maturity":
                import time as _t104
                try:
                    state = self._store.get_activation_state()
                    pmi   = self._store.compute_pmi()
                    vhp   = self._store.get_first_vhp_status()
                    days  = None
                    if vhp and vhp.get("expires_at"):
                        days = round((vhp["expires_at"] - _t104.time()) / 86400, 1)
                    _lbl = {0: "uninitiated", 1: "simulated", 2: "testnet_organic", 3: "mainnet"}
                    return {
                        "pmi": pmi, "pmi_label": _lbl.get(pmi, "unknown"),
                        "activation_committed": state.get("activation_committed", False),
                        "committed_at": state.get("committed_at"),
                        "dry_run_active": bool(getattr(self._cfg, "agent_dry_run_mode", True)),
                        "is_simulation": vhp.get("is_simulation", True) if vhp else True,
                        "days_until_vhp_expiry": days, "vhp_found": vhp is not None,
                        "timestamp": _t104.time(),
                    }
                except Exception as exc:
                    return {"pmi": 0, "error": str(exc), "timestamp": __import__("time").time()}

            # Tool #70 — Phase 103
            if name == "run_activation_sequence":
                import asyncio as _aio
                import time as _t103
                n = int(inputs.get("n_sessions", 110))
                try:
                    from .activation_runner import ActivationRunner
                    _bus = getattr(self._cfg, "_bus", None)
                    runner = ActivationRunner(self._cfg, self._store, bus=_bus)
                    result = _aio.get_event_loop().run_until_complete(runner.run(n_sessions=n))
                    result["timestamp"] = _t103.time()
                    return result
                except Exception as exc:
                    return {
                        "vhp_minted": False, "fully_activated": False,
                        "error": str(exc), "timestamp": _t103.time(),
                    }

            # Tool #69 — Phase 102
            if name == "get_vhp_renewal_log":
                import time as _t102
                device_id = inputs.get("device_id", "") or None
                try:
                    logs      = self._store.get_vhp_renewal_log(device_id=device_id, limit=10)
                    total_vhp = self._store.get_total_vhp_count()
                    last_at   = logs[0]["created_at"] if logs else None
                    dry_only  = all(r.get("dry_run") for r in logs) if logs else True
                    return {
                        "renewal_count":     len(logs),
                        "last_renewal_at":   last_at,
                        "dry_run_only":      dry_only,
                        "lifecycle_warning": total_vhp == 0,
                        "timestamp":         _t102.time(),
                    }
                except Exception as exc:
                    return {
                        "renewal_count":     0,
                        "lifecycle_warning": True,
                        "error":             str(exc),
                        "timestamp":         __import__("time").time(),
                    }

            # Tool #68 — Phase 101B
            if name == "get_edge_ai_profile":
                try:
                    from .edge_ai_profile import get_edge_ai_profile
                    return get_edge_ai_profile(cfg=self._cfg, store=self._store)
                except Exception as exc:
                    import time as _t101b
                    return {"error": str(exc), "timestamp": _t101b.time()}

            # Tool #67 — Phase 101
            if name == "get_quicksilver_collateral_status":
                import time as _t101
                operator_address = inputs.get("operator_address", "")
                try:
                    record = self._store.get_quicksilver_collateral_status(operator_address)
                    return {
                        **record,
                        "stiotx_token_address": getattr(self._cfg, "stiotx_token_address", ""),
                        "quicksilver_collateral_address": getattr(
                            self._cfg, "quicksilver_collateral_address", ""
                        ),
                        "timestamp": _t101.time(),
                    }
                except Exception as exc:
                    return {
                        "operator_address": operator_address,
                        "found": False,
                        "error": str(exc),
                        "timestamp": _t101.time(),
                    }

            # Tool #66 — Phase 100
            if name == "get_activation_status":
                import time as _t100
                gate_n = int(getattr(self._cfg, "validation_gate_n", 100))
                max_rate = float(getattr(self._cfg, "validation_max_divergence_rate", 1.0))
                dry_run_active = bool(getattr(self._cfg, "agent_dry_run_mode", True))
                try:
                    summary = self._store.get_validation_summary(gate_n, max_rate)
                except Exception:
                    summary = {"consecutive_clean": 0, "gate_passed": False, "divergence_rate": 0.0}
                consecutive_clean = int(summary.get("consecutive_clean", 0))
                gate_passed = bool(summary.get("gate_passed", False))
                progress_pct = round(min(100.0, consecutive_clean / gate_n * 100), 1) if gate_n > 0 else 0.0
                try:
                    audit = self._store.get_activation_audit_summary()
                    audit_valid = bool(audit.get("audit_valid", False))
                except Exception:
                    audit_valid = False
                try:
                    cert = self._store.get_latest_enforcement_certificate()
                    cert_ttl = float(getattr(self._cfg, "enforcement_cert_ttl_s", 86400))
                    cert_valid = cert is not None and (
                        _t100.time() - cert.get("created_at", 0)
                    ) <= cert_ttl
                except Exception:
                    cert_valid = False
                if not gate_passed:
                    blocking_step = 1
                elif not cert_valid:
                    blocking_step = 2
                elif not audit_valid:
                    blocking_step = 3
                elif dry_run_active:
                    blocking_step = 4
                else:
                    blocking_step = 6
                return {
                    "current_blocking_step": blocking_step,
                    "fully_activated": blocking_step == 6,
                    "consecutive_clean": consecutive_clean,
                    "gate_n": gate_n,
                    "progress_pct": progress_pct,
                    "dry_run_active": dry_run_active,
                    "audit_valid": audit_valid,
                    "cert_valid": cert_valid,
                    "timestamp": _t100.time(),
                }

            # Tool #65 — Phase 99A
            if name == "get_operator_status":
                import time as _time99
                operator_address = inputs.get("operator_address", "")
                try:
                    status = self._store.get_operator_status(operator_address)
                    return {
                        "operator_address": operator_address,
                        "found": status is not None,
                        "status": status,
                        "vapi_token_address": getattr(self._cfg, "vapi_token_address", ""),
                        "operator_registry_address": getattr(self._cfg, "operator_registry_address", ""),
                        "timestamp": _time99.time(),
                    }
                except Exception as exc:
                    return {
                        "operator_address": operator_address,
                        "found": False,
                        "status": None,
                        "error": str(exc),
                        "timestamp": _time99.time(),
                    }

            # Tool #64 — Phase 98
            if name == "get_epistemic_consensus_log":
                try:
                    import time as _t
                    device_id = inputs.get("device_id")
                    limit = int(inputs.get("limit", 50))
                    entries = self._store.get_epistemic_consensus_log(
                        device_id=device_id, limit=limit
                    )
                    downgraded = sum(1 for e in entries if e.get("downgraded"))
                    return {
                        "entries": entries,
                        "count": len(entries),
                        "downgraded_count": downgraded,
                        "timestamp": _t.time(),
                    }
                except Exception as exc:
                    return {"entries": [], "count": 0, "downgraded_count": 0, "error": str(exc)}

            # Tool #63 — Phase 97
            if name == "get_live_mode_guard_log":
                try:
                    import time as _t
                    limit = int(inputs.get("limit", 50))
                    entries = self._store.get_live_mode_guard_log(limit=limit)
                    return {
                        "entries": entries,
                        "count": len(entries),
                        "current_dry_run": bool(getattr(self._cfg, "agent_dry_run_mode", True)),
                        "timestamp": _t.time(),
                    }
                except Exception as exc:
                    return {"entries": [], "count": 0, "error": str(exc)}

            # Tool #62 — Phase 96
            if name == "get_enforcement_certificate":
                try:
                    cert = self._store.get_latest_enforcement_certificate()
                    import time as _t
                    expired = cert is not None and _t.time() > cert.get("expires_at", 0)
                    return {
                        "certificate": cert,
                        "has_certificate": cert is not None,
                        "is_expired": expired,
                    }
                except Exception as exc:
                    return {
                        "certificate": None,
                        "has_certificate": False,
                        "is_expired": False,
                        "error": str(exc),
                    }

            # Tool #61 — Phase 95
            if name == "get_activation_audit":
                try:
                    return self._store.get_activation_audit_summary()
                except Exception as exc:
                    return {
                        "first_ready_check_at": None,
                        "gate_attestation_count": 0,
                        "latest_attestation_at": None,
                        "audit_valid": False,
                        "audit_summary": f"Error: {exc}",
                    }

            # Tool #60 — Phase 94
            if name == "get_escalation_ruling_log":
                device_id = inputs.get("device_id")
                limit = int(inputs.get("limit", 50))
                try:
                    entries = self._store.get_escalation_ruling_log(
                        device_id=device_id, limit=limit
                    )
                    deferred_count = sum(1 for e in entries if e.get("was_deferred"))
                    return {
                        "entries": entries,
                        "total_returned": len(entries),
                        "deferred_count": deferred_count,
                    }
                except Exception as exc:
                    return {"error": str(exc), "entries": [], "total_returned": 0}

            # Tool #59 — Phase 92
            if name == "get_activation_log":
                limit = int(inputs.get("limit", 50))
                try:
                    entries = self._store.get_live_mode_activation_log(limit=limit)
                    latest_ready = any(e.get("ready_for_live_mode") for e in entries)
                    return {
                        "entries": entries,
                        "total_returned": len(entries),
                        "latest_ready_for_live_mode": latest_ready,
                    }
                except Exception as exc:
                    return {
                        "error": str(exc),
                        "entries": [],
                        "total_returned": 0,
                        "latest_ready_for_live_mode": False,
                    }

            # Tool #58 — Phase 91
            if name == "get_triage_report":
                limit = int(inputs.get("limit", 50))
                try:
                    entries = self._store.get_divergence_triage_report(limit=limit)
                    escalated_count = sum(1 for e in entries if e.get("escalated"))
                    return {
                        "entries": entries,
                        "total_returned": len(entries),
                        "escalated_count": escalated_count,
                        "clean_count": len(entries) - escalated_count,
                    }
                except Exception as exc:
                    return {"error": str(exc), "entries": [], "escalated_count": 0}

            # Tool #57 — Phase 90
            if name == "get_shadow_enforcement_log":
                device_id = inputs.get("device_id")
                limit = int(inputs.get("limit", 50))
                try:
                    entries = self._store.get_shadow_enforcement_log(
                        device_id=device_id, limit=limit
                    )
                    stats = self._store.get_shadow_enforcement_stats()
                    return {
                        "shadow_mode_active": bool(
                            getattr(self._cfg, "enforcement_shadow_mode", False)
                        ),
                        "entries": entries,
                        "stats": stats,
                    }
                except Exception as exc:
                    return {"error": str(exc), "shadow_mode_active": False, "entries": []}

            # Tool #56 — Phase 89
            if name == "get_protocol_intelligence":
                try:
                    report = self._store.get_latest_protocol_intelligence_report()
                    if report is not None:
                        return report
                    from .protocol_intelligence_agent import ProtocolIntelligenceAgent
                    agent = ProtocolIntelligenceAgent(self._cfg, self._store)
                    return agent.compute_report()
                except Exception as exc:
                    return {
                        "error": str(exc),
                        "protocol_health_score": 0.0,
                        "ready_for_live_mode": False,
                        "bottleneck": "error",
                        "recommendation": f"Error: {exc}",
                    }

            # Tool #55 — Phase 88
            if name == "get_campaign_status":
                gate_n = int(getattr(self._cfg, "validation_gate_n", 100))
                max_rate = float(getattr(self._cfg, "validation_max_divergence_rate", 1.0))
                try:
                    return self._store.get_campaign_status(
                        gate_n=gate_n, max_divergence_rate=max_rate
                    )
                except Exception as exc:
                    return {
                        "error": str(exc), "consecutive_clean": 0,
                        "gate_n": gate_n, "progress_pct": 0.0,
                        "session_count": 0, "gate_passed": False,
                        "campaign_note": f"Error: {exc}",
                    }

            # Tool #54 — Phase 86
            if name == "get_corpus_status":
                try:
                    status = self._store.get_corpus_status()
                except Exception as exc:
                    status = {"error": str(exc), "total": 0, "passed": 0, "failed": 0}
                return status

            return {"error": f"Unknown tool: {name}"}

        except Exception as exc:
            log.warning("BridgeAgent tool %s failed: %s", name, exc)
            return {"error": str(exc), "tool": name}

    # ------------------------------------------------------------------
    # Phase 50: Proactive drift detection (called by InsightSynthesizer Mode 6 callback)
    # ------------------------------------------------------------------

    def check_threshold_drift(self, new_anomaly: float, new_continuity: float) -> None:
        """Called synchronously by InsightSynthesizer Mode 6 post-hook (Phase 50).

        Compares new thresholds against Phase 46 anchors (6.726/5.097).
        Always writes a threshold_history entry.
        Writes threshold_drift_alert insight + agent_events when drift > 10%.
        Writes threshold_stable insight when drift <= 10%.
        """
        drift_a = abs(new_anomaly - _PHASE46_ANOMALY_ANCHOR) / _PHASE46_ANOMALY_ANCHOR * 100
        drift_c = abs(new_continuity - _PHASE46_CONTINUITY_ANCHOR) / _PHASE46_CONTINUITY_ANCHOR * 100

        try:
            self._store.write_threshold_history(
                threshold_type="global_mode6",
                old_value=_PHASE46_ANOMALY_ANCHOR,
                new_value=new_anomaly,
                drift_pct=round(drift_a, 2),
                sessions_used=0,
                phase="mode6_living_calibration",
            )
        except Exception as exc:
            log.debug("check_threshold_drift: write_threshold_history failed: %s", exc)

        if drift_a > 10.0 or drift_c > 10.0:
            content = (
                f"Phase 50 threshold drift alert: "
                f"anomaly {_PHASE46_ANOMALY_ANCHOR:.3f}→{new_anomaly:.3f} ({drift_a:.1f}% drift), "
                f"continuity {_PHASE46_CONTINUITY_ANCHOR:.3f}→{new_continuity:.3f} "
                f"({drift_c:.1f}% drift). Exceeds 10% from Phase 46 anchors."
            )
            try:
                self._store.store_protocol_insight(
                    insight_type="threshold_drift_alert",
                    content=content,
                    device_id="__global__",
                    severity="medium",
                )
            except Exception as exc:
                log.debug("check_threshold_drift: store_protocol_insight failed: %s", exc)
            try:
                self._store.write_agent_event(
                    event_type="threshold_updated",
                    payload=json.dumps({
                        "new_anomaly":         new_anomaly,
                        "new_continuity":      new_continuity,
                        "drift_anomaly_pct":   round(drift_a, 2),
                        "drift_continuity_pct": round(drift_c, 2),
                    }),
                    source="bridge_agent",
                    target="calibration_intelligence_agent",
                )
            except Exception as exc:
                log.debug("check_threshold_drift: write_agent_event failed: %s", exc)
        else:
            content = (
                f"Phase 50 threshold stable: anomaly={new_anomaly:.3f} ({drift_a:.1f}% from anchor), "
                f"continuity={new_continuity:.3f} ({drift_c:.1f}% from anchor). Within 10% bounds."
            )
            try:
                self._store.store_protocol_insight(
                    insight_type="threshold_stable",
                    content=content,
                    device_id="__global__",
                    severity="low",
                )
            except Exception as exc:
                log.debug("check_threshold_drift: store_protocol_insight(stable) failed: %s", exc)

    # ------------------------------------------------------------------
    # Agentic reasoning loop
    # ------------------------------------------------------------------

    def ask(self, session_id: str, message: str) -> dict:
        """Process a natural-language operator query and return a response.

        Args:
            session_id: Conversation session identifier (caller-managed).
                        Re-use the same ID to maintain multi-turn context.
            message:    User's natural-language question or command.

        Returns:
            {"session_id": str, "response": str, "tools_used": list[str]}

        Raises:
            ImportError: if the anthropic package is not installed.
        """
        import anthropic  # Lazy — raises ImportError if package absent

        client = anthropic.Anthropic()
        history = self._load_history(session_id)
        history.append({"role": "user", "content": message})

        tools_used: list[str] = []

        for _ in range(5):  # cap at 5 tool-use rounds
            response = client.messages.create(
                model=_AGENT_MODEL,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                tools=_TOOLS,
                messages=history,
            )

            if response.stop_reason == "end_turn":
                text = "".join(
                    block.text
                    for block in response.content
                    if getattr(block, "type", None) == "text"
                )
                history.append(
                    {"role": "assistant", "content": _blocks_to_content(response.content)}
                )
                self._save_history(session_id, history)
                return {
                    "session_id": session_id,
                    "response": text,
                    "tools_used": tools_used,
                }

            if response.stop_reason == "tool_use":
                history.append(
                    {"role": "assistant", "content": _blocks_to_content(response.content)}
                )
                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        tools_used.append(block.name)
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, default=str),
                            }
                        )
                history.append({"role": "user", "content": tool_results})
                continue

            break  # unexpected stop_reason

        self._save_history(session_id, history)
        return {
            "session_id": session_id,
            "response": "Agent loop ended without a final response.",
            "tools_used": tools_used,
        }

    def react(self, event: dict) -> dict:
        """Autonomously interpret a BIOMETRIC_ANOMALY or TEMPORAL_ANOMALY event (Phase 31).

        Uses an internal session keyed to the device so it never pollutes
        operator chat sessions. Never raises — always returns a dict.
        """
        device_id = event.get("device_id", "")
        inference_name = event.get("inference_name", "UNKNOWN")
        severity = (
            "critical"
            if any(s in inference_name for s in ("INJECT", "AIMBOT", "WALLHACK"))
            else "medium"
            if inference_name in ("BIOMETRIC_ANOMALY", "TEMPORAL_ANOMALY")
            else "low"
        )
        session_id = f"__react_{device_id[:8]}"
        msg = (
            f"Detected {inference_name} for device {device_id[:16]}. "
            f"L4_dist={event.get('pitl_l4_distance')}, "
            f"humanity_prob={event.get('pitl_humanity_prob')}. Explain and recommend."
        )
        try:
            result = self.ask(session_id, msg)
            try:
                self._store.store_protocol_insight(
                    insight_type="anomaly_reaction",
                    device_id=device_id,
                    content=result["response"],
                    severity=severity,
                )
            except Exception as _persist_exc:
                log.warning("react() insight persist failed: %s", _persist_exc)
            # Phase 50: systematic drift → recalibration flag
            if "BIOMETRIC_ANOMALY" in inference_name and self._behavioral_arch:
                try:
                    report = self._behavioral_arch.analyze_device(device_id)
                    drift_v = getattr(report, "drift_velocity", 0.0)
                    if drift_v > 0.6:
                        self._store.write_agent_event(
                            event_type="recalibration_needed",
                            device_id=device_id,
                            payload=json.dumps({
                                "drift_velocity": drift_v,
                                "trigger": "biometric_anomaly_systematic",
                                "session_count_since_last_calibration":
                                    self._store.count_records_since_last_calibration(device_id),
                                "recommendation": "focused_personal_recalibration",
                            }),
                            source="bridge_agent",
                            target="calibration_intelligence_agent",
                        )
                except Exception as _exc:
                    log.debug("Phase 50 recalibration flag failed: %s", _exc)
            return {
                "alert": result["response"],
                "severity": severity,
                "tools_used": result["tools_used"],
                "device_id": device_id,
                "inference": inference_name,
            }
        except (ImportError, Exception) as exc:
            return {
                "alert": f"{inference_name} detected. Agent unavailable: {exc}",
                "severity": severity,
                "tools_used": [],
                "device_id": device_id,
                "inference": inference_name,
            }

    async def stream_ask(self, session_id: str, message: str):
        """Async generator yielding SSE event dicts (Phase 31 streaming).

        Yields: {"type": "text_delta"|"tool_start"|"tool_result"|"done"|"error", ...}
        Raises ImportError if anthropic not installed (caller wraps in try/except).
        """
        import anthropic  # Lazy — raises ImportError if absent

        history = list(self._load_history(session_id))
        history.append({"role": "user", "content": message})
        tools_used: list[str] = []
        client = anthropic.AsyncAnthropic()

        for _ in range(5):
            async with client.messages.stream(
                model=_AGENT_MODEL,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                tools=_TOOLS,
                messages=history,
            ) as stream:
                async for text in stream.text_stream:
                    yield {"type": "text_delta", "text": text}
                final = await stream.get_final_message()

            if final.stop_reason == "end_turn":
                history.append(
                    {"role": "assistant", "content": _blocks_to_content(final.content)}
                )
                self._save_history(session_id, history)
                yield {"type": "done", "tools_used": tools_used}
                return

            if final.stop_reason == "tool_use":
                history.append(
                    {"role": "assistant", "content": _blocks_to_content(final.content)}
                )
                tool_results = []
                for block in final.content:
                    if getattr(block, "type", None) == "tool_use":
                        tools_used.append(block.name)
                        yield {"type": "tool_start", "tool": block.name}
                        result = self._execute_tool(block.name, block.input)
                        yield {
                            "type": "tool_result",
                            "tool": block.name,
                            "preview": str(result)[:120],
                        }
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, default=str),
                            }
                        )
                history.append({"role": "user", "content": tool_results})
                continue

            break  # unexpected stop_reason

        self._save_history(session_id, history)
        yield {"type": "done", "tools_used": tools_used}
