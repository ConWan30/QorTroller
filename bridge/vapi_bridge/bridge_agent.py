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
            "SIMILAR (dist <= 5.097). plain_english ALWAYS contains separation ratio 1.261 caveat "
            "(Phase 143 diagonal, N=11 touchpad_corners) because L4 is an intra-player anomaly detector only, not an identity verifier."
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
    # Tool #144 — Phase 192
    {
        "name": "get_session_contribution_weights",
        "description": (
            "Phase 192 DataCuratorAgent — Session Contribution Weight Table (Task 7). "
            "Returns TBD-decay contribution weights per session: "
            "effective_weight = tbd_weight x type_multiplier x stationarity_multiplier. "
            "FROZEN: lambda=ln(2)/90 (BP-001 TBD half-life=vhp_expiry_days=90 days). "
            "Type multipliers (FROZEN): touchpad_corners=1.0, mixed_biometric_probe=0.9, "
            "touchpad_freeform=0.7, resting_grip=0.5, gameplay=0.3. "
            "Powers --weighted-centroid flag in analyze_interperson_separation.py. "
            "P1 old sessions (>60 days) receive tbd_weight<0.3, reducing centroid contamination. "
            "Returns: player_id/tbd_lambda/tbd_halflife_days/weight_count/weights/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "player_id": {"type": "string", "description": "Player ID filter (P1/P2/P3) or empty for all"},
            },
            "required": [],
        },
    },
    # Tool #143 — Phase 192
    {
        "name": "anchor_data_readiness_certificate",
        "description": (
            "Phase 192 DataCuratorAgent — Anchor Data Readiness Certificate on-chain (Task 6). "
            "Anchors the 8-dimension pre-tournament certification artifact to "
            "AdjudicationRegistry.sol as a pre-tournament checkpoint. "
            "When a ruling is later challenged, the operator can prove data was certified "
            "to a specific standard before the tournament began. "
            "dry_run=True: records anchor, no chain call. "
            "Returns: anchored/certificate_hash/tx_hash/dry_run/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "certificate_hash": {"type": "string", "description": "SHA-256 certificate hash to anchor"},
                "tx_hash":          {"type": "string", "description": "Optional: IoTeX tx hash (dry_run if omitted)"},
            },
            "required": ["certificate_hash"],
        },
    },
    # Tool #142 — Phase 192
    {
        "name": "get_data_readiness_certificate",
        "description": (
            "Phase 192 DataCuratorAgent — Data Readiness Certificate status (Task 6). "
            "Returns 8-dimension pre-tournament certification: "
            "separation_ratio_above_gate (FROZEN gate=0.70, BLOCKING), "
            "corpus_age_tbd_compliant (FROZEN 90 days, advisory), "
            "session_type_mix_adequate (advisory), "
            "centroid_stability_ok (persona_break_detected=False, BLOCKING), "
            "consent_coverage_complete (n_consented==n_enrolled, BLOCKING), "
            "biometric_ttl_valid (commitment_age<90d, BLOCKING), "
            "corpus_entropy_adequate (score>=1.5, advisory), "
            "attestation_status_clean (active_attestations==0, advisory). "
            "certification_status: CERTIFIED|BLOCKED|ADVISORY_ONLY. "
            "Returns: certificate_found/certification_status/certificate_hash/separation_ratio/"
            "blocking_failures/advisory_warnings/dimension_results/anchored/valid_until_ts/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #141 — Phase 192
    {
        "name": "get_feature_correlation_status",
        "description": (
            "Phase 192 DataCuratorAgent — Cross-Feature Temporal Correlation status (Task 5). "
            "Returns per-player 13x13 feature correlation matrix (upper triangle, 91 values) "
            "and Frobenius distances between players. "
            "correlation_separable=True when min(frobenius_distances) > "
            "correlation_separability_threshold (FROZEN=0.5). "
            "Frobenius distance measures correlation-structure separability independent of "
            "Mahalanobis distance. A player pair with ratio=0.8 AND frobenius_distance=0.9 "
            "is MORE defensible than ratio=1.2 AND frobenius_distance=0.1. "
            "Returns: player_id/correlation_found/correlation_separable/separability_threshold/"
            "frobenius_vs_p1/frobenius_vs_p2/frobenius_vs_p3/n_sessions_used/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "player_id": {"type": "string", "description": "Player to query (P1/P2/P3 or empty for latest)"},
            },
            "required": [],
        },
    },
    # Tool #140 — Phase 192
    {
        "name": "get_federated_corpus_quality",
        "description": (
            "Phase 192 DataCuratorAgent — Federated Corpus Quality Aggregator (Task 4). "
            "Returns anonymized corpus quality statistics for cross-bridge comparison. "
            "BP-007 constraint: ONLY derived metrics — never raw biometric data. "
            "Contents: N_sessions, entropy_score, stationarity_score, centroid_velocity_mean. "
            "federation_outlier=True when local corpus is >corpus_outlier_sigma_threshold (2.0) "
            "sigma from federation mean. Disabled until 2+ bridges active. "
            "Returns: federated_corpus_quality_enabled/record_count/records/privacy_constraint/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #139 — Phase 192
    {
        "name": "anchor_erasure_certificate",
        "description": (
            "Phase 192 DataCuratorAgent — Anchor Erasure Certificate on-chain (Task 3). "
            "Anchors GDPR Art.17 erasure proof to AdjudicationRegistry.sol "
            "(same contract as PoAd — zero new infrastructure). "
            "After anchoring, regulators can query the full erasure lifecycle from "
            "VAPI bridge to IoTeX L1 as a single verifiable artifact. "
            "dry_run=True: records anchor, no chain call. "
            "Returns: anchored/certificate_hash/tx_hash/dry_run/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "certificate_hash": {"type": "string", "description": "SHA-256 erasure certificate hash"},
                "tx_hash":          {"type": "string", "description": "Optional: IoTeX tx hash"},
            },
            "required": ["certificate_hash"],
        },
    },
    # Tool #138 — Phase 192
    {
        "name": "get_erasure_certificate",
        "description": (
            "Phase 192 DataCuratorAgent — GDPR Art.17 Proof-of-Erasure Certificate (Task 3). "
            "Returns cryptographic certificate proving biometric data erasure happened correctly. "
            "certificate_hash = SHA-256(device_id + sorted_table_row_hashes + ratio + ts_ns). "
            "Anchored to AdjudicationRegistry.sol (same as PoAd — zero new infra). "
            "Returns: device_id/certificate_found/certificate_hash/player_id/"
            "post_erasure_ratio/anchored/on_chain_tx_hash/ts_ns/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Device ID to retrieve erasure cert for"},
            },
            "required": ["device_id"],
        },
    },
    # Tool #137 — Phase 192
    {
        "name": "get_corpus_entropy_status",
        "description": (
            "Phase 192 DataCuratorAgent — Corpus Entropy Monitor status (Task 2). "
            "Returns Shannon entropy of the 13-dimensional feature space per player. "
            "Score range: 0.0 (all sessions identical) to 3.32 (uniform over 10 bins). "
            "CLUSTERING_WARNING when score < 1.5 — sessions are not sampling the feature space "
            "well; centroid will be brittle under small perturbation. "
            "WELL_SAMPLED when score > 2.5 — safe to report separation ratio as trustworthy. "
            "A ratio of 0.9 with entropy 2.8 is MORE defensible than ratio 1.1 with entropy 0.8. "
            "Returns: corpus_entropy_score/clustering_warning/status/per_player_entropy/"
            "low_entropy_features/n_sessions_analyzed/session_type_filter/warning_threshold/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #136 — Phase 192
    {
        "name": "get_data_provenance_chain",
        "description": (
            "Phase 192 DataCuratorAgent — Provenance DAG chain walk (Task 1). "
            "Walks from a leaf_node_id to root(s) via parent_node_id relationships. "
            "Full causal chain: calibration_session -> separation_snapshot -> "
            "defensibility_log -> commitment_hash -> renewal_log -> attestation -> badge_token. "
            "This is the forensic lineage answer to 'what data produced this credential'. "
            "Regulators can traverse the full chain from consent snapshot to ratio commitment "
            "as a single DAG traversal — no manual table joins needed. "
            "Max depth: provenance_max_chain_depth (FROZEN=20, prevents infinite loop). "
            "Returns: leaf_node_id/chain_length/chain/forensic_summary/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "leaf_node_id": {"type": "string", "description": "Node ID to trace from (SHA-256 hex)"},
            },
            "required": [],
        },
    },
    # Tools #145–#147 — Phase 193 FleetSignalCoherenceAgent
    {
        "name": "get_fleet_coherence_summary",
        "description": (
            "Phase 193 FleetSignalCoherenceAgent — Fleet-level signal coherence summary (Tool #145). "
            "Detects contradictory, orphaned, or inverted signals across the 35-agent fleet. "
            "Three failure modes: CONTRADICTION (7 rules — e.g. RENEWAL_WITHOUT_ATTESTATION CRITICAL), "
            "ORPHAN (5 rules — unacknowledged signals from an agent not consumed by its downstream), "
            "INVERSION (3 rules — Provenance DAG walk shows temporal inversion). "
            "fleet_coherence_enabled=True by default (unlike most agents which default False). "
            "promoted_to_wif: count auto-promoted to VAPI_WHAT_IF.md (N_PROMOTE_THRESHOLD=3 occurrences). "
            "Returns: fleet_coherence_enabled/total_open/by_severity/by_mode/"
            "promoted_to_wif/last_cycle_findings/last_checked_at/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_fleet_coherence_entries",
        "description": (
            "Phase 193 FleetSignalCoherenceAgent — Open coherence failures detail (Tool #146). "
            "Returns open (unresolved) coherence entries, filterable by failure_mode and severity. "
            "failure_mode: CONTRADICTION | ORPHAN | INVERSION (empty=all). "
            "severity: CRITICAL | HIGH | MEDIUM (empty=all). "
            "CRITICAL entries (RENEWAL_WITHOUT_ATTESTATION) indicate a bypass of Phase 185/186 chain. "
            "Each entry includes: coherence_id, rule_name, agents_involved, explanation, resolution, promoted_to_wif. "
            "Returns: entry_count/entries/failure_mode/severity/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "failure_mode": {"type": "string", "description": "CONTRADICTION|ORPHAN|INVERSION or empty for all"},
                "severity":     {"type": "string", "description": "CRITICAL|HIGH|MEDIUM or empty for all"},
            },
            "required": [],
        },
    },
    {
        "name": "resolve_coherence_entry",
        "description": (
            "Phase 193 FleetSignalCoherenceAgent — Mark a coherence entry as resolved (Tool #147). "
            "Marks a coherence failure as resolved by the specified operator identity. "
            "CRITICAL entries (RENEWAL_WITHOUT_ATTESTATION) should only be resolved after "
            "the underlying attestation chain gap has been verified as a false positive or fixed. "
            "Returns: resolved/coherence_id/resolved_by/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "coherence_id": {"type": "string", "description": "Coherence entry ID (coh_<16 hex chars>)"},
                "resolved_by":  {"type": "string", "description": "Operator identity resolving this entry"},
            },
            "required": ["coherence_id", "resolved_by"],
        },
    },
    # Tool #129 — Phase 180
    {
        "name": "trigger_renewal_commitment",
        "description": (
            "Phase 180 Biometric Renewal Engine — trigger consent-bound separation ratio renewal. "
            "When the biometric credential TTL is expired (age_days > biometric_credential_ttl_days), "
            "computes a new commit_hash linked to prev_commit_hash via consent-bound SHA-256 preimage: "
            "SHA-256(prev_hash + ratio_str + N + N_consented + players + ttl_days + ts_ns). "
            "n_consented read live from consent corpus (Phase 163 pattern). "
            "dry_run=True (default): records renewal chain entry, no chain call. "
            "dry_run=False: calls SeparationRatioRegistry.renewCommit() on IoTeX testnet "
            "when renewal_enabled=True in config. "
            "Returns: renewal_enabled/prev_commit_hash/new_commit_hash/ttl_days/dry_run/total_renewals/n_consented/error."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ratio":   {"type": "number",  "description": "New separation ratio (e.g. 1.261)"},
                "n_sessions": {"type": "integer", "description": "Number of calibration sessions used"},
                "n_players":  {"type": "integer", "description": "Number of players in corpus"},
                "dry_run": {"type": "boolean", "description": "If true, no chain call (default: true)"},
            },
            "required": ["ratio", "n_sessions", "n_players"],
        },
    },
    # Tool #128 — Phase 179
    {
        "name": "get_ceremony_audit_status",
        "description": (
            "Phase 179 ZK Ceremony Audit Gate status (WIF-030 W1 closure). "
            "Returns ceremony participant audit summary for all registered VAPI ZK circuits. "
            "Infrastructure-first: ceremony_audit_enabled=False by default — zero behavior change. "
            "When enabled: audit_passed=True only when each circuit has >= min_participants "
            "(default 3) distinct participant_address entries in ceremony_audit_log. "
            "Single-operator Groth16 trusted setup = toxic waste known to one party = "
            "forgeable ZK proofs undetected (WIF-030 W1). "
            "Returns: ceremony_audit_enabled/total_entries/distinct_participants/"
            "circuits_audited/min_participants/audit_passed/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #127 — Phase 178
    {
        "name": "get_biometric_credential_age",
        "description": (
            "Phase 178 Biometric Credential TTL Gate status (WIF-029 W1 closure). "
            "Checks whether the latest SeparationRatioRegistry.sol commitment has exceeded "
            "the 90-day biometric credential TTL. Expired credentials block tournament "
            "authorization and require operator-triggered recalibration. "
            "age_days is computed live from the most recent separation_ratio_registry_log "
            "commit timestamp. ttl_expired=True when age_days > biometric_credential_ttl_days "
            "(default 90). Each check is logged to biometric_renewal_log for audit trail. "
            "Returns: ttl_enabled/commit_hash/commit_ts/age_days/ttl_days/"
            "ttl_expired/recalibration_required/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #126 — Phase 177
    {
        "name": "get_protocol_maturity_score",
        "description": (
            "Phase 177 ProtocolMaturityScoringAgent status (agent #26). "
            "Synthesizes 6 agent signals into a unified maturity_score (0.0-1.0). "
            "Component weights: separation(0.25) + chain_integrity(0.20) + consent(0.15) "
            "+ biometric_freshness(0.15) + agent_calibration(0.15) + enrollment(0.10). "
            "maturity_tier: ALPHA (<0.50) | BETA (0.50-0.85) | PRODUCTION_CANDIDATE (>=0.85). "
            "PRODUCTION_CANDIDATE requires maturity_score>=0.85 which is only achievable "
            "when separation_ratio>1.0 (tournament gate), chain integrity 1.0, consent "
            "corpus defensible, biometric freshness above decay threshold, all 26 agents "
            "calibrated, and enrollment complete. "
            "Returns: protocol_maturity_enabled/maturity_score/maturity_tier/"
            "separation_component/chain_integrity_component/consent_component/"
            "biometric_freshness_component/agent_calibration_component/enrollment_component/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #125 — Phase 176
    {
        "name": "get_poac_chain_integrity",
        "description": (
            "Phase 176 PoACChainIntegrityMonitor status (agent #25). "
            "Audits SHA-256 chain linkage across PoAC records for a device. "
            "integrity_score = valid_links / total_records (1.0 = fully intact chain). "
            "W1 mitigation: only aggregate counts returned — no broken record IDs exposed "
            "(exposing broken record IDs would reveal injection windows to adversaries). "
            "audit_passed=True when broken_links==0. "
            "Returns: chain_integrity_enabled/device_id/total_records/valid_links/"
            "broken_links/integrity_score/audit_passed/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Filter to a specific device_id (optional; omit for latest overall).",
                }
            },
            "required": [],
        },
    },
    # Tool #124 — Phase 175
    {
        "name": "get_age_weight_analysis_status",
        "description": (
            "Phase 175 AgeWeightedRatioPersistenceAgent status (agent #24). "
            "Returns the latest age-weighted separation ratio analysis result persisted "
            "from a --session-age-weight analysis run (Phase 174 script). "
            "temporal_drift_index = raw_ratio - age_weighted_ratio: "
            "positive (P1_NONSTATIONARITY) = old sessions inflate ratio; "
            "negative (IMPROVING) = new sessions are biometrically stronger; "
            "near-zero (STABLE) = player biometrically stationary (ideal for tournament). "
            "Returns: age_weight_analysis_enabled/raw_ratio/age_weighted_ratio/"
            "temporal_drift_index/halflife_days/n_sessions_used/drift_direction/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #123 — Phase 173
    {
        "name": "get_separation_ratio_recovery_status",
        "description": (
            "Phase 173 SeparationRatioRecoveryAgent status (agent #23). "
            "Returns the latest recovery assessment: current separation ratio, "
            "trend_velocity (dRatio/dSnapshot — negative means converging downward), "
            "recovery_needed flag, and recommended action. "
            "Recovery actions: STABLE (no action needed) | AGE_WEIGHTING (apply "
            "--session-age-weight 30 flag to mitigate P1 temporal non-stationarity) | "
            "P1_RE_ENROLLMENT (P1 biometric fingerprint drifting — re-capture >=10 fresh "
            "touchpad_corners sessions) | MORE_SESSIONS (capture more structured probe data). "
            "Returns: separation_recovery_enabled/current_ratio/trend_velocity/"
            "n_snapshots_used/recovery_needed/recovery_action/recommendation/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #122 — Phase 165
    {
        "name": "trigger_post_erasure_recompute",
        "description": (
            "Phase 165 WIF-024 closure: trigger a post-erasure separation ratio recompute "
            "audit for a device. When a device's biometric records are erased (GDPR Art.17), "
            "the stored separation ratio becomes stale — this tool snapshots the current "
            "ratio before erasure and writes to post_erasure_ratio_log, flagging that "
            "analyze_interperson_separation.py must be re-run. "
            "dry_run=True (default) returns current status without executing erasure. "
            "dry_run=False calls anonymize_device_records(post_erasure_recompute=True). "
            "Returns: consent_ledger_enabled/total_recomputes/pending_recomputes/"
            "latest_recompute_ts/latest_ratio_before/recompute_needed/triggered/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type":        "string",
                    "description": "Device ID to trigger post-erasure recompute for.",
                },
                "dry_run": {
                    "type":        "boolean",
                    "description": "When True (default), only reads status. When False, executes erasure+recompute.",
                },
            },
            "required": [],
        },
    },
    # Tool #121 — Phase 164
    {
        "name": "get_consent_snapshot_delta",
        "description": (
            "Return Phase 164 WIF-023 ConsentSnapshotAnchor delta. "
            "Compares N_consented bound into the on-chain SHA-256 hash at the last "
            "separation ratio commit against the current live consent count. "
            "delta > 0 means the chain attestation overstates current consent coverage "
            "(post-commit revocations occurred — GDPR Art.7(3) / Art.17(3)(e) exposure). "
            "delta == 0 means consent state unchanged since commit. "
            "Returns: consent_ledger_enabled/found/commit_hash/n_consented_at_commit/"
            "n_consented_live/delta/revoked_since_commit/snapshot_ts/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #120 — Phase 163
    {
        "name": "commit_separation_ratio",
        "description": (
            "Phase 163 WIF-022 closure: commit a consent-bound separation ratio to "
            "SeparationRatioRegistry.sol (or dry-run store when chain disabled). "
            "commit_hash = SHA-256(ratio_str + N + N_consented + players_sorted + ts_ns). "
            "N_consented = active_consent_count from consent_ledger — cryptographically binds "
            "consent filtering into the on-chain proof. "
            "separation_ratio_on_chain_enabled=False → dry_run=True, hash computed+stored in "
            "SQLite but no chain tx. "
            "Returns: committed/commit_hash/n_consented/n_sessions/n_players/on_chain_tx/"
            "dry_run/separation_ratio_on_chain_enabled/timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ratio":          {"type": "number",  "description": "Separation ratio (float)"},
                "n_sessions":     {"type": "integer", "description": "Total sessions in corpus"},
                "n_players":      {"type": "integer", "description": "Player count"},
                "players_sorted": {"type": "string",  "description": "Comma-joined sorted player IDs"},
            },
            "required": ["ratio", "n_sessions", "n_players", "players_sorted"],
        },
    },
    # Tool #119 — Phase 162
    {
        "name": "get_consent_aware_corpus_status",
        "description": (
            "Return Phase 162 Consent-Aware Corpus Status (WIF-021 closure). "
            "Reports active_consent_count, revoked_count, erasure_requested_count, and "
            "consent_corpus_defensible flag. A defensible corpus has zero revoked/erasure "
            "devices — required for legally defensible on-chain separation ratio commitment. "
            "WIF-021: consent-unaware corpus contamination from GDPR-revoked devices. "
            "Returns: consent_ledger_enabled/active_consent_count/revoked_count/"
            "erasure_requested_count/consent_corpus_defensible/timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #118 — Phase 161
    {
        "name": "get_consent_gate_status",
        "description": (
            "Return Phase 161 Consent Gate enforcement status (BP-002 WIF-018/020 closure). "
            "Reports violations_total, gate_active, last_violation_ts. "
            "Gate blocks insert_validation_record for devices with revoked consent or "
            "pending erasure_requested. Gate fails open for unknown devices (no consent "
            "record = allowed). WIF-020: anonymize_device_records now covers "
            "ruling_validation_log (GDPR Art.17 full closure). "
            "Returns: consent_ledger_enabled, gate_active, violations_total, "
            "last_violation_ts, timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Tool #117 — Phase 160
    {
        "name": "get_consent_status",
        "description": (
            "Return Phase 160 Consent Ledger status for a device (BP-002, WIF-018/019). "
            "Consent Ledger is the GDPR Art.7/17 compliance primitive: "
            "consent_given=True is required before biometric data is processed. "
            "revoked=True + erasure_completed=True = full GDPR Art.17 erasure honored. "
            "anonymize_device_records() NULLs humanity_score + evidence_json in pitl_session_proofs. "
            "Returns: consent_ledger_enabled, consent_given, consent_ts, revoked, "
            "erasure_requested, erasure_completed, timestamp. "
            "consent_ledger_enabled=True default. "
            "Use POST /agent/register-consent to give consent; POST /agent/revoke-consent to revoke."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Device ID to query consent status for.",
                },
            },
            "required": ["device_id"],
        },
    },
    # Tool #116 — Phase 159
    {
        "name": "get_biometric_privacy_status",
        "description": (
            "Return Phase 159 BiometricPrivacyComplianceAgent (agent #22) BP-001 status. "
            "BP-001 Temporal Biometric Decay: TBD(t) = e^(-λt), λ = ln(2)/τ_half, τ_half=90d. "
            "Monitors enrolled player record ages — mean_decay_factor tracks fleet-wide decay. "
            "warning_triggered=True when mean_decay_factor < 0.25 (≈2 half-lives ≈180 days). "
            "privacy_budget_epsilon is advisory (ε = oldest_age_days / half_life_days). "
            "Returns: biometric_privacy_enabled, bp001_half_life_days, records_monitored, "
            "records_expired, mean_decay_factor, warning_triggered, privacy_budget_epsilon, timestamp. "
            "biometric_privacy_enabled=True default; polls every 21600s (6h). "
            "BP-001 is IMMUTABLE per VAPI_INVARIANTS.md §6."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #115 — Phase 158
    {
        "name": "get_pohbg_status",
        "description": (
            "Return Phase 158 PoHBG (Proof of Hardware Biometric Grip) status (WIF-015). "
            "PoHBG hash = SHA-256(device_id_bytes + pack('>IIIQ', arousal_millis, "
            "correlation_millis, conductance_raw_int, ts_ns)). "
            "Extends the composable proof triple (PoAC + PoAd + PoFC) with grip hardware proof. "
            "Returns: pohbg_enabled, total_pohbg, latest_pohbg_hash (64-char hex), "
            "latest_device_id, latest_ts_ns, timestamp. "
            "pohbg_enabled=False default (infrastructure-first)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #114 — Phase 158
    {
        "name": "get_gsr_hmac_validation_status",
        "description": (
            "Return Phase 158 GSR Class K HMAC frame authentication status (WIF-014). "
            "Class K anti-spoofing: validates incoming 80-byte GSR frames carry correct "
            "HMAC-SHA256 tag over [magic+arousal+correlation+conductance+ts_ns+device_id]. "
            "Rejects synthetic EDA generators (no session key). "
            "Returns: gsr_hmac_enabled, gsr_hmac_key_configured, total_validations, "
            "valid_count, rejected_count, timestamp. "
            "gsr_hmac_enabled=False default (infrastructure-first). "
            "Requires GSR_HMAC_KEY_HEX env var (64-char hex, 32-byte session key)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #113 — Phase 157
    {
        "name": "get_fleet_consensus_snapshot",
        "description": (
            "Return Phase 157 FleetConsensusSnapshotAgent (agent #21) status. "
            "Computes PoFC (Proof of Fleet Consensus): SHA-256 hash of the sorted agent verdict "
            "state + separation_ratio + ts_ns — the third composable proof primitive alongside "
            "PoAC (physiological) and PoAd (adjudication). "
            "Returns: fleet_consensus_enabled, total_snapshots, latest_pofc_hash (64-char hex), "
            "latest_agent_count, latest_separation_ratio, timestamp. "
            "fleet_consensus_enabled=True default (poll every 1800s)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #112 — Phase 156
    {
        "name": "get_enrollment_auto_guidance_status",
        "description": (
            "Return Phase 156 EnrollmentAutoGuidanceAgent synthesis: reads Phase 151 capture guidance, "
            "Phase 154 stagnation status, Phase 152 centroid velocity, and Phase 155 controller status, "
            "then emits a unified recommended_action with urgency_level. "
            "Returns: sessions_needed_total, overall_ready, recommended_action, urgency_level, "
            "estimated_days, stagnant_probes (list), activation_chain_event, timestamp. "
            "urgency_level: HIGH (stagnant+not ready), MEDIUM (velocity low), LOW (on track). "
            "This agent coordinates with TournamentActivationChainAgent (#16) when overall_ready=True. "
            "enrollment_auto_guidance_enabled=True default (poll every 3600s)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #111 — Phase 155
    {
        "name": "get_controller_hardware_status",
        "description": (
            "Return Phase 155 ControllerHardwareIntelligenceAgent status: registered controller profiles "
            "split by tier (Attested=DualShock Edge L0-L6 / Standard=Xbox/Switch L0-L5). "
            "Returns: controller_intelligence_enabled, multi_controller_enabled, attested_count, "
            "standard_count, active_composite_key (profile_hash:battery:transport), profiles (list), "
            "timestamp. "
            "multi_controller_enabled=False default — never change without N≥50 per-controller calibration. "
            "Composite key format: profile_hash:battery_type:transport_type for per-controller routing. "
            "Default Attested profile: DualShock Edge, anomaly=7.009, continuity=5.367."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #110 — Phase 154
    {
        "name": "get_capture_stagnation_status",
        "description": (
            "Return Phase 154 capture stagnation monitor status for a structured probe type. "
            "Computes sessions/day rolling rate from separation_defensibility_log over window_days. "
            "stagnant=True when sessions_per_day < stagnation_threshold (default 0.5/day). "
            "Returns: probe_type, sessions_per_day, stagnant, sessions_in_window, window_days, "
            "stagnation_threshold, notes, timestamp. "
            "Use to detect when capture progress has plateaued and intervention is needed. "
            "Feeds into Phase 156 EnrollmentAutoGuidanceAgent for urgency escalation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "probe_type": {
                    "type": "string",
                    "description": "Probe type to check (default: touchpad_corners).",
                },
            },
            "required": [],
        },
    },
    # Tool #109 — Phase 153
    {
        "name": "get_separation_ratio_registry_status",
        "description": (
            "Return Phase 153 on-chain separation ratio registry status. "
            "commit_hash = SHA-256(ratio_str + N + players_sorted + ts_ns). "
            "Returns: committed, commit_hash, ratio_millis (int(ratio*1000)), n_sessions, "
            "n_players, on_chain_tx, total_commits, separation_ratio_on_chain_enabled, timestamp. "
            "separation_ratio_on_chain_enabled=False default (infrastructure-first). "
            "SeparationRatioRegistry.sol: commitRatio(bytes32, uint256, uint32, uint32) onlyOwner; "
            "anti-replay via UNIQUE commitHash; converts trust-me calibration to verifiable on-chain proof."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #108 — Phase 152
    {
        "name": "get_centroid_velocity_status",
        "description": (
            "Return Phase 152 centroid velocity monitor: rate of change of separation ratio between "
            "consecutive defensibility log snapshots. velocity = |ratio_curr - ratio_prev| / dt_seconds. "
            "velocity_per_day = velocity * 86400. "
            "stagnant=True when velocity_per_day < 0.001 (plateau threshold). "
            "Returns: probe_type, velocity, velocity_per_day, stagnant, n_snapshots_used, "
            "ratio_prev, ratio_curr, timestamp. "
            "Use to detect when the calibration corpus is plateauing vs actively improving. "
            "Feeds into Phase 156 EnrollmentAutoGuidanceAgent for urgency classification."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "probe_type": {
                    "type": "string",
                    "description": "Probe type to check (default: touchpad_corners).",
                },
            },
            "required": [],
        },
    },
    # Tool #107 — Phase 151 P1
    {
        "name": "get_enrollment_capture_guidance",
        "description": (
            "Return Phase 151 per-player capture guidance for structured probe types. "
            "For each probe type (touchpad_corners / touchpad_freeform / touchpad_swipes), "
            "reports how many more sessions each player needs to reach min_n_per_player (default 10). "
            "Returns: min_n_per_player, probe_types (list), guidance (per-probe breakdown), "
            "sessions_needed_total, overall_ready, timestamp. "
            "guidance[probe_type] contains: found, current_ratio, n_per_player, gap (sessions needed "
            "per player), all_players_ready. "
            "Current state (Phase 143): P1=3, P2=4, P3=4 touchpad_corners — gap={P1:7,P2:6,P3:6}. "
            "overall_ready=True when ALL players >= min_n in ALL probe types AND ratio > 1.0. "
            "Use this to plan capture sessions — each gameplay session with structured probe adds "
            "to one probe type per player."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "min_n": {
                    "type": "integer",
                    "description": "Minimum sessions per player per probe type (default 10).",
                },
            },
            "required": [],
        },
    },
    # Tool #106 — Phase 150
    {
        "name": "get_separation_defensibility_status",
        "description": (
            "Return Phase 150 separation ratio defensibility status (WIF-010 closure). "
            "Reports whether the current per-player touchpad_corners session counts meet "
            "the minimum required (default N=10/player) for a legally defensible "
            "separation ratio claim. "
            "Returns 6 keys: defensible (bool), ratio (float), n_per_player (dict), "
            "min_n_per_player (int), all_pairs_above_1 (bool), found (bool). "
            "Current state: P1=3, P2=4, P3=4 — all below target=10; defensible=False. "
            "Ratio=1.261 (touchpad_corners, Phase 143 diagonal+LOO) is above the 1.0 "
            "tournament gate but N=11 is legally thin. "
            "W1 (WIF-010): single outlier session could reverse ratio below 1.0 at N=11. "
            "Pair distances: P1vP2=2.868, P1vP3=3.276, P2vP3=2.243 — all above 1.0."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_type": {
                    "type": "string",
                    "description": (
                        "Probe session type to query (default: 'touchpad_corners'). "
                        "Filters the defensibility log by session_type."
                    ),
                },
            },
            "required": [],
        },
    },
    # Tool #105 — Phase 148
    {
        "name": "get_agent_calibration_health",
        "description": (
            "Return Phase 148 AgentCalibrationMonitor (ACIM, agent #18) health summary. "
            "Returns 6 keys: agent_count (16), healthy_count, degraded_count, "
            "failed_agents (list of agent names that failed their self-test), "
            "mcp_server_enabled, timestamp. "
            "ACIM runs every 15 minutes and cross-validates each of the 16 agents' "
            "core calibration invariants independently (W1: breaks single-validator "
            "anti-pattern where CIA validates its own thresholds). "
            "mcp_server_enabled=False default — enable with MCP_SERVER_ENABLED=true."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "integer",
                    "description": "Optional: filter results to a specific agent (1-16).",
                },
            },
            "required": [],
        },
    },
    # Tool #104 — Phase 135
    {
        "name": "get_tournament_activation_chain",
        "description": (
            "Return Phase 135 TournamentActivationChainAgent status (7 keys): "
            "gate_open_notified, auto_activate_on_breakthrough (PERMANENT False — "
            "tournament activation ALWAYS requires explicit operator action), "
            "operator_action_required, last_ratio, last_notification_ts, "
            "notification_count, timestamp. "
            "Subscribes to separation_ratio_breakthrough bus event — fires once "
            "when pooled separation ratio >= 1.0 for 2 consecutive snapshots. "
            "Current ratio: 0.474 — TOURNAMENT BLOCKER (target >= 1.0)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #103 — Phase 134
    {
        "name": "run_l4_recalibration",
        "description": (
            "Trigger a background L4 recalibration pipeline job (Phase 134) and return status. "
            "Returns 7 keys: in_progress, last_run_ts, sessions_processed, "
            "new_anomaly_threshold, new_continuity_threshold, stale, timestamp. "
            "Returns 409 if a job is already running (< 10 min old). "
            "stale=True when live_feature_dim != calibration_feature_dim (13 vs 12). "
            "auto_separation_snapshot_enabled=False default — snapshot triggered after each live session when True."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #102 — Phase 133
    {
        "name": "get_ioswarm_poad_anchor_status",
        "description": (
            "Return Phase 133 IoSwarm PoAd auto-anchor status (7 keys): "
            "poad_auto_anchor_enabled, anchored_count, pending_count, last_anchor_tx, "
            "dual_veto_count, anchor_failure_count, timestamp. "
            "ioswarm_poad_auto_anchor_enabled=False default — infrastructure-first, zero behavior change. "
            "When dual_veto fires and anchor enabled, SHA-256 swarm fingerprint is anchored on-chain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #101 — Phase 132
    {
        "name": "ping_ioswarm_nodes",
        "description": (
            "Poll GET /status on all configured live ioSwarm nodes and return a health summary "
            "(Phase 132). Reports nodes_configured, nodes_healthy, emulator_mode, avg_latency_ms, "
            "health_log_count. When ioswarm_node_urls is empty, emulator_mode=True is returned "
            "with all counts at zero — zero behavior change from current emulated state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #100 — Phase 131B
    {
        "name": "get_usb_stability_status",
        "description": (
            "Return USB stability monitor status for PS5 coexistence (Phase 131B). "
            "VAPI-exclusive: DualShock Edge simultaneously streams live PoAC biometrics "
            "via USB reads AND writes HID output (LED/haptic). When the controller is "
            "also BT-paired to a PS5, those HID output writes cause USB micro-drops that "
            "trigger the PS5 reconnect notification. "
            "This tool reports disconnect_count, last_disconnect_ts, ps5_compat_mode "
            "(True = HID writes suppressed, no more PS5 notifications), and timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #99 — Phase 131
    {
        "name": "get_ioswarm_node_registry_status",
        "description": (
            "Return IoSwarm live-node registry status (Phase 131). "
            "Reports whether real HTTP ioSwarm nodes are configured or the emulator "
            "is active, the number of registered nodes, per-node timeout, and the "
            "timestamp of the last quorum validation. "
            "Returns: live_nodes, emulator_mode, registry_count, node_timeout_s, "
            "last_quorum_ts, error."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #98 — Phase 130A
    {
        "name": "get_swarm_operator_gate_status",
        "description": (
            "Return VAPISwarmOperatorGate.sol status (Phase 130A, WIF-001 mitigation). "
            "Reports whether the gate is configured, total on-chain quorum validations, "
            "last validation result, and last node count. "
            "Returns: gate_configured, valid, node_count, timestamp, error."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #97 — Phase 129
    {
        "name": "get_separation_ratio_breakthrough",
        "description": (
            "Return the latest separation ratio breakthrough event (Phase 129). "
            "A breakthrough is recorded when pooled_ratio crosses >= 1.0 from below "
            "on 2 consecutive monitoring snapshots (W1 mitigation: avoids false "
            "positives from a single outlier snapshot). "
            "Returns: breakthrough_detected, breakthrough_ratio, breakthrough_ts, "
            "n_players, error."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #96 — Phase 128
    {
        "name": "get_tournament_readiness_score",
        "description": (
            "Compute the tournament readiness score (Phase 128) — a weighted composite "
            "of 6 signals synthesizing all protocol monitoring endpoints into a single "
            "0.0–1.0 readiness score. Weights: separation_ratio=0.30, l4_freshness=0.20, "
            "dual_primitive_gate=0.15, epoch_window=0.15, ioswarm=0.10, dry_run=0.10. "
            "separation_score=min(1.0, pooled_ratio); l4_score=1.0 if live_dim==calib_dim; "
            "dual_gate_score=1.0 if >=1 eligible mint in last 24h; epoch_score from p95 analytics; "
            "ioswarm_score from last mint consensus; dry_run_score=1.0 if dry_run=False. "
            "Persists result to protocol_intelligence_reports for audit trail. "
            "Returns: score, separation_score, l4_score, dual_gate_score, epoch_score, "
            "ioswarm_score, dry_run_score, conditions_met, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #95 — Phase 127
    {
        "name": "run_tournament_preflight",
        "description": (
            "Run the tournament pre-launch preflight validation suite (Phase 127). "
            "Evaluates 5 P0 conditions (block activation if ANY fails): "
            "separation_ok (pooled_ratio>=1.0), l4_ok (live_dim==calib_dim), "
            "gate_ok (consecutive_clean>=gate_n), cert_ok, audit_ok. "
            "Also evaluates 3 P1 warnings: dual_primitive_gate_enabled, "
            "epoch_window_enabled, ioswarm_vhp_mint_enabled. "
            "Persists result to tournament_preflight_log for audit trail. "
            "POST /agent/commit-activation reads latest preflight to enforce P0 gates. "
            "Returns: run_id, separation_ok, l4_ok, gate_ok, cert_ok, audit_ok, "
            "dual_gate_warned, epoch_window_warned, ioswarm_warned, overall_pass, "
            "conditions, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #94 — Phase 126
    {
        "name": "get_l4_router_status",
        "description": (
            "Return L4 per-battery threshold router status (Phase 126). "
            "When l4_battery_threshold_enabled=True, the router selects battery-specific "
            "anomaly/continuity thresholds from l4_threshold_tracks instead of global defaults "
            "(7.009/5.367). Falls back to global thresholds with WARNING log when no active "
            "track matches the session battery type. "
            "Phase 126 also promotes BehavioralArchaeologist magic numbers to named constants: "
            "_WARMUP_COEFF=20_000 and _BURST_CV_DIVISOR=2.0. "
            "Fields: l4_battery_threshold_enabled, total_lookups, per_battery_lookups, "
            "global_fallback_count, last_battery_type, last_source, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #93 — Phase 125
    {
        "name": "apply_l4_battery_calibration",
        "description": (
            "Apply a per-battery L4 Mahalanobis threshold calibration result (Phase 125). "
            "Inserts a calibrated (anomaly_threshold, continuity_threshold) pair for a specific "
            "battery_type into l4_threshold_tracks and logs the run for audit traceability. "
            "Also clears the Phase 123 staleness flag by updating calibration_feature_dim "
            "to match live_feature_dim (13) when calibration was run on 13-feature corpus. "
            "W1 protection: anomaly [5.0, 15.0] and continuity [3.0, 10.0] bounds enforced; "
            "raises ValueError on violation. "
            "Returns: track_id, run_id, battery_type, anomaly_threshold, continuity_threshold, "
            "n_sessions, calibration_feature_dim, stale, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "battery_type": {
                    "type": "string",
                    "description": "Battery type: touchpad, trigger, button, gameplay, motion, or other",
                },
                "anomaly_threshold": {
                    "type": "number",
                    "description": "L4 anomaly threshold [5.0, 15.0] (e.g. 7.009)",
                },
                "continuity_threshold": {
                    "type": "number",
                    "description": "L4 continuity threshold [3.0, 10.0] (e.g. 5.367)",
                },
                "n_sessions": {
                    "type": "integer",
                    "description": "Number of calibration sessions used (e.g. 74)",
                },
                "calibration_feature_dim": {
                    "type": "integer",
                    "description": "Feature dimension used for calibration (default: 13 = current live_feature_dim)",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional operator notes for audit trail",
                },
            },
            "required": ["battery_type", "anomaly_threshold", "continuity_threshold"],
        },
    },
    # Tool #92 — Phase 124
    {
        "name": "get_l4_threshold_tracks",
        "description": (
            "Return L4 per-battery threshold track registry (Phase 124). "
            "Operators register per-battery calibrated threshold pairs after running "
            "threshold_calibrator.py per battery type on 13-feature corpus. "
            "Default global thresholds anomaly=7.009/continuity=5.367 (Phase 57) apply "
            "when no per-battery track is active. "
            "W1 protection: insert bounds [5.0–15.0] anomaly / [3.0–10.0] continuity enforced. "
            "Infrastructure-first: l4_battery_threshold_enabled=False default. "
            "Fields: l4_battery_threshold_enabled, track_count, active_count, "
            "battery_types_tracked, tracks, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "battery_type": {
                    "type": "string",
                    "description": "Optional filter by battery type (touchpad/trigger/button/gameplay/motion/other)",
                },
                "active_only": {
                    "type": "boolean",
                    "description": "If true, return only active=1 tracks",
                },
            },
            "required": [],
        },
    },
    # Tool #91 — Phase 123
    {
        "name": "get_l4_calibration_status",
        "description": (
            "Return L4 Mahalanobis threshold calibration staleness status (Phase 123). "
            "stale=True when live_feature_dim (13, Phase 121) != calibration_feature_dim (12, Phase 57). "
            "Thresholds anomaly=7.009/continuity=5.367 were calibrated on 12-feature space (N=74). "
            "Impact is bounded: touchpad_spatial_entropy (index 12) is zero-variance in hw_* corpus "
            "(auto-excluded from Mahalanobis), but will drift once touchpad calibration sessions added. "
            "Recalibration path: scripts/threshold_calibrator.py → update CALIBRATION_FEATURE_DIM=13. "
            "Fields: current_feature_dim, calibration_feature_dim, stale, anomaly_threshold, "
            "continuity_threshold, calibration_n_sessions, calibration_timestamp, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #90 — Phase 122
    {
        "name": "get_confidence_score_multiplier_status",
        "description": (
            "Return VHP confidence_score separation ratio multiplier status (Phase 122). "
            "When multiplier_enabled=True, confidence_score minted on-chain is scaled by "
            "min(1.0, bt_strat_ratio) — ensures VHP credential reflects actual biometric "
            "identity-discrimination confidence. Example: bt_strat_ratio=0.62 → "
            "confidence_score 9000 → 5580 on-chain (60% of raw). "
            "Infrastructure-first: multiplier_enabled=False default (zero behavior change). "
            "Fields: multiplier_enabled, current_bt_strat_ratio, effective_multiplier, "
            "floor, log_count, recent_applications, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #89 — Phase 121
    {
        "name": "get_separation_ratio_status",
        "description": (
            "Return biometric inter-person separation ratio status (Phase 121). "
            "TOURNAMENT BLOCKER: ratio must be > 1.0 for live deployment (current ~0.474 pooled). "
            "touchpad_spatial_entropy (feature index 12) is the primary new signal for improving separation. "
            "battery_stratified_ratio reflects same-battery pairwise ratio (~0.60-0.65 touchpad battery). "
            "Fields: pooled_ratio, battery_stratified_ratio, tournament_blocker, "
            "target_ratio, gap_to_target, tournament_ready, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #88 — Phase 120
    {
        "name": "get_bt_transport_status",
        "description": (
            "Return Bluetooth transport foundation status (Phase 120). "
            "DualShock Edge BLE at 250 Hz (vs USB 1000 Hz). "
            "W1 INVARIANT: BT sessions must NOT use USB L4 thresholds (7.009/5.367) — "
            "separate BT threshold track required (not yet calibrated). "
            "bt_transport_enabled=False default (infrastructure-only). "
            "Fields: bt_transport_enabled, device_address, sampling_rate_hz, "
            "frames_received, frames_dropped, avg_interval_ms, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max recent sessions to return (default 10)"},
            },
            "required": [],
        },
    },
    # Tool #87 — Phase 119
    {
        "name": "revoke_device_epoch_override",
        "description": (
            "Revoke a per-device epoch window override (Phase 119). "
            "Deletes the override for the given device_id; Gate-5 for that device reverts "
            "to the global cfg.epoch_window_seconds. "
            "Returns device_id, revoked (True/False), and timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Device whose override to revoke"},
            },
            "required": ["device_id"],
        },
    },
    # Tool #86 — Phase 119
    {
        "name": "get_epoch_window_override_status",
        "description": (
            "List all per-device epoch window overrides with lifecycle fields (Phase 119). "
            "Returns override_count, overrides_with_max_uses, and the full lifecycle list "
            "including max_uses, use_count, expires_at — so operators can audit which "
            "overrides are ephemeral (auto-graduating) vs permanent. "
            "Fields: override_count, overrides_with_max_uses, overrides, "
            "epoch_window_enabled, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    # Tool #85 — Phase 118
    {
        "name": "set_device_epoch_override",
        "description": (
            "Set a per-device epoch window override (Phase 118). "
            "Upserts an entry in per_device_epoch_overrides so Gate-5 uses "
            "override_window_seconds instead of the global epoch_window_seconds for this device. "
            "Use for cold-start devices or high-latency adjudication nodes to avoid false-positive blocks. "
            "Fields returned: device_id, override_window_seconds, reason, row_id, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id":       {"type": "string",  "description": "Device to override"},
                "window_seconds":  {"type": "number",  "description": "Override epoch window in seconds"},
                "reason":          {"type": "string",  "description": "Reason for the override (optional)"},
            },
            "required": ["device_id", "window_seconds"],
        },
    },
    # Tool #84 — Phase 118
    {
        "name": "get_epoch_window_auto_tune",
        "description": (
            "Return epoch-window auto-tune advisor results (Phase 118). "
            "Compares fleet p95 against current window, recommends global window, "
            "and surfaces top devices needing per-device overrides (cold-start W1 mitigation). "
            "Fields: epoch_window_enabled, current_window_seconds, recommended_window_seconds, "
            "fleet_p95_age_seconds, override_count, override_candidates, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "top_n_overrides": {"type": "integer", "description": "Max override candidates to return (default 5)"},
            },
            "required": [],
        },
    },
    # Tool #83 — Phase 117
    {
        "name": "get_epoch_window_device_heatmap",
        "description": (
            "Return per-device epoch freshness heatmap sorted by p95 DESC (Phase 117). "
            "Identifies which devices have the stalest PoAd anchors in Gate-5 logs. "
            "Each entry: device_id, check_count, blocked_count, p50_age_seconds, "
            "p95_age_seconds, last_check_ts. "
            "epoch_window_enabled=False by default (infrastructure-only). "
            "Fields: epoch_window_enabled, epoch_window_seconds, total_devices, devices, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit_per_device": {"type": "integer", "description": "Max rows per device (default 100)"},
                "top_n":            {"type": "integer", "description": "Max devices to return (default 20)"},
            },
            "required": [],
        },
    },
    # Tool #82 — Phase 116
    {
        "name": "get_epoch_window_analytics",
        "description": (
            "Return epoch-window analytics over Gate-5 poad_age_seconds (Phase 116). "
            "Computes p50/p95/p99/max age distribution from vhp_dual_gate_log and "
            "provides a recommended epoch_window_seconds (2× p95, floored 1h, capped 7d). "
            "staleness_blocked_count = rows where epoch_window_ok=False. "
            "epoch_window_enabled=False by default (infrastructure-only). "
            "Fields: epoch_window_enabled, epoch_window_seconds, total_gate5_checks, "
            "staleness_blocked_count, checked_count, p50_age_seconds, p95_age_seconds, "
            "recommended_window_seconds, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max rows to analyse (default 1000)"},
            },
            "required": [],
        },
    },
    # Tool #81 — Phase 114
    {
        "name": "get_vhp_dual_gate_log",
        "description": (
            "Return VHP mint dual-primitive gate log (Phase 114). "
            "5th gate in POST /agent/mint-vhp — fires when dual_primitive_gate_enabled=True. "
            "Requires BOTH PoAC (isFullyEligible via VAPIProtocolLens) AND "
            "PoAd (isRecorded via AdjudicationRegistry) before VHP can be minted. "
            "dual_primitive_gate_enabled=False by default (infrastructure-only). "
            "Fields: dual_primitive_gate_enabled, total_checks, eligible_count, "
            "mint_allowed_count, recent_logs, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Optional device_id filter"},
                "limit":     {"type": "integer", "description": "Max results (default 20)"},
            },
            "required": [],
        },
    },
    # Tool #80 — Phase 113
    {
        "name": "check_dual_eligibility",
        "description": (
            "Check dual-primitive tournament eligibility for a device+poad pair (Phase 113). "
            "Requires BOTH PoAC (isFullyEligible via VAPIProtocolLens) AND "
            "PoAd (isRecorded via AdjudicationRegistry) to return true. "
            "First on-chain dual-proof composability gate — exclusive to VAPI protocol. "
            "dual_primitive_gate_enabled=False by default (infrastructure-only). "
            "Fields: eligible, poac_valid, poad_valid, device_id, timestamp."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "Device identifier string"},
                "poad_hash": {"type": "string", "description": "64-char hex PoAd hash from poad_registry_log"},
            },
            "required": ["device_id", "poad_hash"],
        },
    },
    # Tool #79 — Phase 111
    {
        "name": "get_adjudication_registry_status",
        "description": (
            "Return PoAd Registry status (Phase 111). "
            "poad_registry_enabled=False by default — infrastructure-only; "
            "on-chain anchoring deferred to Phase 112. "
            "PoAd hash = SHA-256(sorted classj+triage verdicts + quorum + ts_ns) stored locally. "
            "W2 dual-primitive composability: Phase 113 tournaments require BOTH isFullyEligible() "
            "(PoAC) AND isRecorded(poadHash) (PoAd) — no single-operator system can replicate. "
            "is_composable=True when poad_registry_enabled=True AND adjudication_registry_address set. "
            "Fields: poad_registry_enabled, total_poad_count, dual_veto_poad_count, "
            "on_chain_anchor_count, adjudication_registry_address, is_composable, timestamp."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
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
            "CURRENT STATUS: separation_ratio=1.261 (Phase 143 diagonal LOO, N=11) — "
            "classification 63.6%, TOURNAMENT BLOCKER until classification ≥80%. "
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
                            "separation ratio 1.261 (Phase 143 diagonal, N=11 touchpad_corners; "
                            "L4 is intra-player anomaly detector only)."
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
                    f"separation ratio 1.261 (Phase 143, N=11) — L4 is intra-player anomaly detector only; "
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
                        "Inter-person separation ratio=1.261 (Phase 143 diagonal, N=11 touchpad_corners; "
                        "classification 63.6%). Biometric transplant attack "
                        "(P1 uses P2 device) has 0% detection at L4 in gameplay sessions. "
                        "Tournament blocker: classification <80%."
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

            # Tools #136–#144 — Phase 192 DataCuratorAgent
            if name in ("get_data_provenance_chain", "get_corpus_entropy_status",
                        "get_erasure_certificate", "anchor_erasure_certificate",
                        "get_federated_corpus_quality", "get_feature_correlation_status",
                        "get_data_readiness_certificate", "anchor_data_readiness_certificate",
                        "get_session_contribution_weights"):
                import time as _t192, math as _m192
                try:
                    if name == "get_data_provenance_chain":
                        leaf_id = str(tool_input.get("leaf_node_id", ""))
                        max_depth = getattr(self._cfg, "provenance_max_chain_depth", 20)
                        if not leaf_id:
                            try:
                                with self._store._conn() as _conn192:
                                    _row192 = _conn192.execute(
                                        "SELECT node_id FROM data_provenance_dag "
                                        "ORDER BY id DESC LIMIT 1"
                                    ).fetchone()
                                    leaf_id = _row192[0] if _row192 else "none"
                            except Exception:
                                leaf_id = "none"
                        _chain = self._store.get_provenance_chain(leaf_id, max_depth=max_depth)
                        _summary = (
                            f"{len(_chain)}-hop chain from "
                            f"{_chain[0].get('node_type', '?')} to "
                            f"{_chain[-1].get('node_type', '?')}"
                            if _chain else "No chain found"
                        )
                        return {"leaf_node_id": leaf_id, "chain_length": len(_chain),
                                "chain": _chain, "forensic_summary": _summary,
                                "timestamp": _t192.time()}

                    if name == "get_corpus_entropy_status":
                        _row = self._store.get_latest_corpus_entropy()
                        _thr = getattr(self._cfg, "corpus_entropy_warning_threshold", 1.5)
                        if _row is None:
                            return {"corpus_entropy_score": 0.0, "clustering_warning": True,
                                    "status": "NO_DATA", "per_player_entropy": "{}",
                                    "n_sessions_analyzed": 0, "warning_threshold": _thr,
                                    "timestamp": _t192.time()}
                        return {"corpus_entropy_score": float(_row["corpus_entropy_score"]),
                                "clustering_warning": bool(_row["clustering_warning"]),
                                "status": "CLUSTERING_WARNING" if _row["clustering_warning"] else "WELL_SAMPLED",
                                "per_player_entropy": _row["per_player_entropy"],
                                "low_entropy_features": _row["low_entropy_features"],
                                "n_sessions_analyzed": int(_row["n_sessions_analyzed"]),
                                "session_type_filter": _row["session_type_filter"],
                                "warning_threshold": _thr, "timestamp": _t192.time()}

                    if name == "get_erasure_certificate":
                        _did = str(tool_input.get("device_id", ""))
                        if not _did:
                            return {"error": "device_id required"}
                        _cert = self._store.get_erasure_certificate(_did)
                        return {"device_id": _did, "certificate_found": _cert is not None,
                                "certificate_hash": _cert["certificate_hash"] if _cert else None,
                                "post_erasure_ratio": float(_cert["post_erasure_ratio"]) if _cert else None,
                                "anchored": bool(_cert["anchored"]) if _cert else False,
                                "timestamp": _t192.time()}

                    if name == "anchor_erasure_certificate":
                        _ch = str(tool_input.get("certificate_hash", ""))
                        if not _ch:
                            return {"error": "certificate_hash required"}
                        _tx = str(tool_input.get("tx_hash", f"dry_run_{int(_t192.time_ns())}"))
                        self._store.anchor_erasure_certificate(_ch, _tx)
                        return {"anchored": True, "certificate_hash": _ch, "tx_hash": _tx,
                                "dry_run": getattr(self._cfg, "agent_dry_run_mode", True),
                                "timestamp": _t192.time()}

                    if name == "get_federated_corpus_quality":
                        _recs = self._store.get_federated_corpus_quality(limit=10)
                        return {"federated_corpus_quality_enabled": getattr(
                                    self._cfg, "federated_corpus_quality_enabled", False),
                                "record_count": len(_recs), "records": _recs,
                                "privacy_constraint": "BP-007: no raw biometric data",
                                "timestamp": _t192.time()}

                    if name == "get_feature_correlation_status":
                        _pid = str(tool_input.get("player_id", ""))
                        _row_c = self._store.get_feature_correlation(player_id=_pid)
                        _thr_c = getattr(self._cfg, "correlation_separability_threshold", 0.5)
                        if _row_c is None:
                            return {"player_id": _pid or "all", "correlation_found": False,
                                    "correlation_separable": False,
                                    "separability_threshold": _thr_c,
                                    "timestamp": _t192.time()}
                        return {"player_id": _row_c["player_id"],
                                "correlation_found": True,
                                "correlation_separable": bool(_row_c["correlation_separable"]),
                                "separability_threshold": _thr_c,
                                "frobenius_vs_p1": _row_c["frobenius_vs_p1"],
                                "frobenius_vs_p2": _row_c["frobenius_vs_p2"],
                                "frobenius_vs_p3": _row_c["frobenius_vs_p3"],
                                "n_sessions_used": int(_row_c["n_sessions_used"]),
                                "timestamp": _t192.time()}

                    if name == "get_data_readiness_certificate":
                        _cert_r = self._store.get_latest_data_readiness_certificate()
                        if _cert_r is None:
                            return {"certificate_found": False,
                                    "certification_status": "NO_CERTIFICATE",
                                    "separation_ratio": 0.0,
                                    "timestamp": _t192.time()}
                        return {"certificate_found": True,
                                "certification_status": _cert_r["certification_status"],
                                "certificate_hash": _cert_r["certificate_hash"],
                                "separation_ratio": float(_cert_r["separation_ratio"]),
                                "blocking_failures": _cert_r["blocking_failures"],
                                "advisory_warnings": _cert_r["advisory_warnings"],
                                "anchored": bool(_cert_r["anchored"]),
                                "timestamp": _t192.time()}

                    if name == "anchor_data_readiness_certificate":
                        _ch_r = str(tool_input.get("certificate_hash", ""))
                        if not _ch_r:
                            return {"error": "certificate_hash required"}
                        _tx_r = str(tool_input.get("tx_hash", f"dry_run_{int(_t192.time_ns())}"))
                        self._store.anchor_data_readiness_certificate(_ch_r, _tx_r)
                        return {"anchored": True, "certificate_hash": _ch_r, "tx_hash": _tx_r,
                                "dry_run": getattr(self._cfg, "agent_dry_run_mode", True),
                                "timestamp": _t192.time()}

                    if name == "get_session_contribution_weights":
                        _pid_w = str(tool_input.get("player_id", ""))
                        _wts = self._store.get_session_weights(player_id=_pid_w, limit=30)
                        _lam = _m192.log(2) / 90  # FROZEN: BP-001
                        return {"player_id": _pid_w or "all", "tbd_lambda": round(_lam, 8),
                                "tbd_halflife_days": 90, "weight_count": len(_wts),
                                "weights": _wts, "timestamp": _t192.time()}

                except Exception as _exc192:
                    return {"error": str(_exc192), "tool": name}

            # Tools #145–#147 — Phase 193 FleetSignalCoherenceAgent
            if name in ("get_fleet_coherence_summary", "get_fleet_coherence_entries",
                        "resolve_coherence_entry"):
                import time as _t193
                try:
                    if name == "get_fleet_coherence_summary":
                        _sum193 = self._store.get_coherence_summary()
                        _en193  = getattr(self._cfg, "fleet_coherence_enabled", True)
                        return {
                            "fleet_coherence_enabled": _en193,
                            "total_open":        _sum193.get("total_open", 0),
                            "by_severity":       _sum193.get("by_severity", {}),
                            "by_mode":           _sum193.get("by_mode", {}),
                            "promoted_to_wif":   _sum193.get("promoted_to_wif", 0),
                            "last_cycle_findings": _sum193.get("last_cycle_findings", 0),
                            "last_checked_at":   _sum193.get("last_checked_at"),
                            "timestamp":         _t193.time(),
                        }

                    if name == "get_fleet_coherence_entries":
                        _fm193  = str(tool_input.get("failure_mode", ""))
                        _sev193 = str(tool_input.get("severity", ""))
                        _ents193 = self._store.get_open_coherence_entries(
                            severity=_sev193 or None,
                            failure_mode=_fm193 or None,
                        )
                        return {
                            "entry_count": len(_ents193),
                            "entries":     _ents193,
                            "failure_mode": _fm193 or "all",
                            "severity":    _sev193 or "all",
                            "timestamp":   _t193.time(),
                        }

                    if name == "resolve_coherence_entry":
                        _cid193 = str(tool_input.get("coherence_id", ""))
                        _by193  = str(tool_input.get("resolved_by", "operator"))
                        if not _cid193:
                            return {"error": "coherence_id required"}
                        self._store.mark_coherence_resolved(_cid193, _by193)
                        return {"resolved": True, "coherence_id": _cid193,
                                "resolved_by": _by193, "timestamp": _t193.time()}

                except Exception as _exc193:
                    return {"error": str(_exc193), "tool": name}

            # Tool #129 — Phase 180
            if name == "trigger_renewal_commitment":
                import hashlib as _hl180, time as _t180
                try:
                    _ratio180       = float(tool_input.get("ratio", 0.0))
                    _n_sess180      = int(tool_input.get("n_sessions", 0))
                    _n_play180      = int(tool_input.get("n_players",  0))
                    _dry180         = bool(tool_input.get("dry_run", True))
                    _ttl180         = float(getattr(self._cfg, "biometric_credential_ttl_days", 90.0))
                    _renew_en180    = bool(getattr(self._cfg, "renewal_enabled", False))
                    _age180         = self._store.get_biometric_credential_age_status(ttl_days=_ttl180)
                    _prev_hash180   = str(_age180.get("commit_hash", ""))
                    _consent180     = self._store.get_consent_corpus_coverage()
                    _n_con180       = int(_consent180.get("active_consent_count", 0))
                    _ts_ns180       = _t180.time_ns()
                    _preimage180 = (
                        _prev_hash180
                        + f"{_ratio180:.6f}"
                        + str(_n_sess180)
                        + str(_n_con180)
                        + f"{_ttl180:.1f}"
                        + str(_ts_ns180)
                    ).encode()
                    _new_hash180    = "sha256:" + _hl180.sha256(_preimage180).hexdigest()
                    self._store.insert_biometric_renewal_chain_log(
                        prev_commit_hash=_prev_hash180,
                        new_commit_hash=_new_hash180,
                        n_consented=_n_con180,
                        n_sessions=_n_sess180,
                        ttl_days=_ttl180,
                        dry_run=_dry180,
                    )
                    _cs180 = self._store.get_biometric_renewal_chain_status()
                    return {
                        "renewal_enabled":  _renew_en180,
                        "prev_commit_hash": _prev_hash180,
                        "new_commit_hash":  _new_hash180,
                        "ttl_days":         _ttl180,
                        "dry_run":          _dry180,
                        "total_renewals":   int(_cs180.get("total_renewals", 0)),
                        "n_consented":      _n_con180,
                        "error":            None,
                    }
                except Exception as _e180:
                    return {
                        "renewal_enabled": False,
                        "prev_commit_hash": "",
                        "new_commit_hash":  "",
                        "ttl_days":         90.0,
                        "dry_run":          True,
                        "total_renewals":   0,
                        "n_consented":      0,
                        "error":            str(_e180),
                    }

            # Tool #128 — Phase 179
            if name == "get_ceremony_audit_status":
                import time as _t179
                try:
                    _enabled179 = bool(getattr(self._cfg, "ceremony_audit_enabled", False))
                    _min_p179   = int(getattr(self._cfg, "ceremony_audit_min_participants", 3))
                    _status179  = self._store.get_ceremony_audit_status()
                    if _enabled179:
                        _circuits179 = int(_status179.get("circuits_audited", 0))
                        if _circuits179 == 0:
                            _audit_passed = False
                        else:
                            with self._store._conn() as _c179:
                                _rows179 = _c179.execute(
                                    "SELECT circuit_name, COUNT(DISTINCT participant_address) "
                                    "AS n FROM ceremony_audit_log GROUP BY circuit_name"
                                ).fetchall()
                            _audit_passed = all(int(r[1]) >= _min_p179 for r in _rows179)
                    else:
                        _audit_passed = True
                    return {
                        "ceremony_audit_enabled":  _enabled179,
                        "total_entries":           int(_status179.get("total_entries",         0)),
                        "distinct_participants":   int(_status179.get("distinct_participants",  0)),
                        "circuits_audited":        int(_status179.get("circuits_audited",       0)),
                        "min_participants":        _min_p179,
                        "audit_passed":            _audit_passed,
                        "timestamp":               _t179.time(),
                    }
                except Exception as _e179:
                    return {
                        "ceremony_audit_enabled": False,
                        "audit_passed":           True,
                        "error":                  str(_e179),
                    }

            # Tool #127 — Phase 178
            if name == "get_biometric_credential_age":
                try:
                    from .tournament_activation_chain_agent import TournamentActivationChainAgent as _TACA178
                    _taca178 = _TACA178(cfg=self._cfg, store=self._store, bus=None)
                    return _taca178.check_biometric_credential_ttl()
                except Exception as _e178:
                    import time as _t178e
                    return {
                        "ttl_enabled":            True,
                        "commit_hash":            "",
                        "commit_ts":              0.0,
                        "age_days":               0.0,
                        "ttl_days":               90.0,
                        "ttl_expired":            False,
                        "recalibration_required": False,
                        "timestamp":              _t178e.time(),
                        "error":                  str(_e178),
                    }

            # Tool #126 — Phase 177
            if name == "get_protocol_maturity_score":
                import time as _t177
                try:
                    _rows177   = self._store.get_protocol_maturity_status(limit=1)
                    _latest177 = _rows177[0] if _rows177 else {}
                    return {
                        "protocol_maturity_enabled":      getattr(self._cfg, "protocol_maturity_enabled", True),
                        "maturity_score":                 float(_latest177.get("maturity_score",                0.0)),
                        "maturity_tier":                  str(_latest177.get("maturity_tier",                   "ALPHA")),
                        "separation_component":           float(_latest177.get("separation_component",          0.0)),
                        "chain_integrity_component":      float(_latest177.get("chain_integrity_component",     0.0)),
                        "consent_component":              float(_latest177.get("consent_component",             0.0)),
                        "biometric_freshness_component":  float(_latest177.get("biometric_freshness_component", 0.0)),
                        "agent_calibration_component":    float(_latest177.get("agent_calibration_component",   0.0)),
                        "enrollment_component":           float(_latest177.get("enrollment_component",          0.0)),
                        "timestamp":                      _t177.time(),
                    }
                except Exception as _e177:
                    return {"error": str(_e177), "maturity_tier": "ALPHA", "maturity_score": 0.0}

            # Tool #125 — Phase 176
            if name == "get_poac_chain_integrity":
                import time as _t176
                _dev176 = (args.get("device_id") or "").strip() or None
                try:
                    _rows176   = self._store.get_poac_chain_audit_status(device_id=_dev176, limit=1)
                    _latest176 = _rows176[0] if _rows176 else {}
                    return {
                        "chain_integrity_enabled": getattr(self._cfg, "chain_integrity_enabled", True),
                        "device_id":       str(_latest176.get("device_id",       "")),
                        "total_records":   int(_latest176.get("total_records",   0)),
                        "valid_links":     int(_latest176.get("valid_links",     0)),
                        "broken_links":    int(_latest176.get("broken_links",    0)),
                        "integrity_score": float(_latest176.get("integrity_score", 1.0)),
                        "audit_passed":    bool(_latest176.get("audit_passed",   True)),
                        "timestamp":       _t176.time(),
                    }
                except Exception as _e176:
                    return {"error": str(_e176), "audit_passed": True, "integrity_score": 1.0}

            # Tool #124 — Phase 175
            if name == "get_age_weight_analysis_status":
                import time as _t175
                try:
                    _rows175   = self._store.get_age_weight_analysis_status(limit=1)
                    _latest175 = _rows175[0] if _rows175 else {}
                    return {
                        "age_weight_analysis_enabled": getattr(self._cfg, "age_weight_analysis_enabled", True),
                        "raw_ratio":            float(_latest175.get("raw_ratio",            0.0)),
                        "age_weighted_ratio":   float(_latest175.get("age_weighted_ratio",   0.0)),
                        "temporal_drift_index": float(_latest175.get("temporal_drift_index", 0.0)),
                        "halflife_days":        float(_latest175.get("halflife_days",        90.0)),
                        "n_sessions_used":      int(_latest175.get("n_sessions_used",        0)),
                        "drift_direction":      str(_latest175.get("drift_direction",        "STABLE")),
                        "timestamp":            _t175.time(),
                    }
                except Exception as _e175:
                    return {"error": str(_e175), "drift_direction": "STABLE", "temporal_drift_index": 0.0}

            # Tool #123 — Phase 173
            if name == "get_separation_ratio_recovery_status":
                import time as _t173
                try:
                    _rows173   = self._store.get_separation_ratio_recovery_status(limit=1)
                    _latest173 = _rows173[0] if _rows173 else {}
                    return {
                        "separation_recovery_enabled": getattr(self._cfg, "separation_recovery_enabled", True),
                        "current_ratio":    float(_latest173.get("current_ratio",  0.0)),
                        "trend_velocity":   float(_latest173.get("trend_velocity", 0.0)),
                        "n_snapshots_used": int(_latest173.get("n_snapshots_used", 0)),
                        "recovery_needed":  bool(_latest173.get("recovery_needed", False)),
                        "recovery_action":  str(_latest173.get("recovery_action",  "STABLE")),
                        "recommendation":   str(_latest173.get("recommendation",   "")),
                        "timestamp":        _t173.time(),
                    }
                except Exception as _exc173:
                    return {"error": str(_exc173), "timestamp": _t173.time()}

            # Tool #122 — Phase 165
            if name == "trigger_post_erasure_recompute":
                import time as _t165
                try:
                    _dev165  = str(inputs.get("device_id", "")).strip()
                    _dry165  = bool(inputs.get("dry_run", True))
                    _triggered165 = False
                    if _dev165 and not _dry165:
                        self._store.anonymize_device_records(
                            _dev165, post_erasure_recompute=True
                        )
                        _triggered165 = True
                    _st165 = self._store.get_post_erasure_recompute_status(
                        device_id=_dev165 if _dev165 else None
                    )
                    return {
                        "consent_ledger_enabled": getattr(self._cfg, "consent_ledger_enabled", True),
                        "total_recomputes":       _st165["total_recomputes"],
                        "pending_recomputes":     _st165["pending_recomputes"],
                        "latest_recompute_ts":    _st165["latest_recompute_ts"],
                        "latest_ratio_before":    _st165["latest_ratio_before"],
                        "recompute_needed":       _st165["recompute_needed"],
                        "triggered":              _triggered165,
                        "timestamp":              _t165.time(),
                    }
                except Exception as exc:
                    return {
                        "consent_ledger_enabled": True,
                        "total_recomputes": 0, "pending_recomputes": 0,
                        "latest_recompute_ts": None, "latest_ratio_before": None,
                        "recompute_needed": False, "triggered": False,
                        "timestamp": _t165.time(), "error": str(exc),
                    }

            # Tool #121 — Phase 164
            if name == "get_consent_snapshot_delta":
                import time as _t164
                try:
                    _snap164 = self._store.get_consent_snapshot_delta()
                    return {
                        "consent_ledger_enabled": getattr(self._cfg, "consent_ledger_enabled", True),
                        "found":                  _snap164["found"],
                        "commit_hash":            _snap164["commit_hash"],
                        "n_consented_at_commit":  _snap164["n_consented_at_commit"],
                        "n_consented_live":       _snap164["n_consented_live"],
                        "delta":                  _snap164["delta"],
                        "revoked_since_commit":   _snap164["revoked_since_commit"],
                        "snapshot_ts":            _snap164["snapshot_ts"],
                        "timestamp":              _t164.time(),
                    }
                except Exception as exc:
                    return {
                        "consent_ledger_enabled": True, "found": False,
                        "commit_hash": None, "n_consented_at_commit": 0,
                        "n_consented_live": 0, "delta": 0,
                        "revoked_since_commit": 0, "snapshot_ts": None,
                        "timestamp": _t164.time(), "error": str(exc),
                    }

            # Tool #120 — Phase 163
            if name == "commit_separation_ratio":
                import time as _t163, hashlib as _hl163
                try:
                    _ratio163  = float(inputs.get("ratio", 1.261))
                    _n_sess163 = int(inputs.get("n_sessions", 0))
                    _n_play163 = int(inputs.get("n_players", 3))
                    _players163 = str(inputs.get("players_sorted", "P1,P2,P3"))
                    _ts_ns163  = _t163.time_ns()
                    _chash163, _n_cons163 = self._store.compute_separation_ratio_commit_hash(
                        ratio=_ratio163,
                        n_sessions=_n_sess163,
                        players_sorted=_players163,
                        ts_ns=_ts_ns163,
                    )
                    _enabled163 = getattr(self._cfg, "separation_ratio_on_chain_enabled", False)
                    self._store.insert_separation_ratio_registry_log(
                        commit_hash=_chash163,
                        ratio_millis=int(_ratio163 * 1000),
                        n_sessions=_n_sess163,
                        n_players=_n_play163,
                        on_chain_tx=None,
                        committed=False,
                        n_consented=_n_cons163,
                    )
                    return {
                        "separation_ratio_on_chain_enabled": bool(_enabled163),
                        "commit_hash":  _chash163,
                        "n_consented":  _n_cons163,
                        "n_sessions":   _n_sess163,
                        "n_players":    _n_play163,
                        "committed":    False,
                        "on_chain_tx":  None,
                        "dry_run":      not bool(_enabled163),
                        "timestamp":    _t163.time(),
                    }
                except Exception as exc:
                    return {
                        "separation_ratio_on_chain_enabled": False,
                        "commit_hash": "", "n_consented": 0,
                        "n_sessions": 0, "n_players": 0,
                        "committed": False, "on_chain_tx": None,
                        "dry_run": True, "timestamp": _t163.time(), "error": str(exc),
                    }

            # Tool #119 — Phase 162
            if name == "get_consent_aware_corpus_status":
                import time as _t162
                try:
                    _cov162 = self._store.get_consent_corpus_coverage()
                    return {
                        "consent_ledger_enabled":    getattr(self._cfg, "consent_ledger_enabled", True),
                        "active_consent_count":      _cov162["active_consent_count"],
                        "revoked_count":             _cov162["revoked_count"],
                        "erasure_requested_count":   _cov162["erasure_requested_count"],
                        "consent_corpus_defensible": _cov162["consent_corpus_defensible"],
                        "timestamp":                 _t162.time(),
                    }
                except Exception as exc:
                    return {
                        "consent_ledger_enabled": True,
                        "active_consent_count": 0, "revoked_count": 0,
                        "erasure_requested_count": 0, "consent_corpus_defensible": False,
                        "timestamp": _t162.time(), "error": str(exc),
                    }

            # Tool #118 — Phase 161
            if name == "get_consent_gate_status":
                import time as _t161
                try:
                    _gdata161 = self._store.get_consent_gate_status()
                    return {
                        "consent_ledger_enabled": getattr(self._cfg, "consent_ledger_enabled", True),
                        "gate_active":            getattr(self._cfg, "consent_ledger_enabled", True),
                        "violations_total":       _gdata161["violations_total"],
                        "last_violation_ts":      _gdata161["last_violation_ts"],
                        "timestamp":              _t161.time(),
                    }
                except Exception as exc:
                    return {
                        "consent_ledger_enabled": True, "gate_active": False,
                        "violations_total": 0, "last_violation_ts": None,
                        "timestamp": _t161.time(), "error": str(exc),
                    }

            # Tool #117 — Phase 160
            if name == "get_consent_status":
                import time as _t160
                _device_id160 = inputs.get("device_id", "")
                try:
                    _cstatus160 = self._store.get_consent_status(_device_id160)
                    return {
                        "consent_ledger_enabled": getattr(self._cfg, "consent_ledger_enabled", True),
                        "consent_given":          _cstatus160["consent_given"],
                        "consent_ts":             _cstatus160["consent_ts"],
                        "revoked":                _cstatus160["revoked"],
                        "erasure_requested":      _cstatus160["erasure_requested"],
                        "erasure_completed":      _cstatus160["erasure_completed"],
                        "timestamp":              _t160.time(),
                    }
                except Exception as exc:
                    return {
                        "consent_ledger_enabled": getattr(self._cfg, "consent_ledger_enabled", True),
                        "consent_given":          False,
                        "consent_ts":             None,
                        "revoked":                False,
                        "erasure_requested":      False,
                        "erasure_completed":      False,
                        "error":                  str(exc),
                        "timestamp":              _t160.time(),
                    }

            # Tool #116 — Phase 159
            if name == "get_biometric_privacy_status":
                import time as _t159
                try:
                    _priv159 = self._store.get_privacy_compliance_status()
                    return {
                        "biometric_privacy_enabled": getattr(self._cfg, "biometric_privacy_enabled", True),
                        "bp001_half_life_days":      getattr(self._cfg, "bp001_half_life_days", 90.0),
                        "records_monitored":         _priv159["records_monitored"],
                        "records_expired":           _priv159["records_expired"],
                        "mean_decay_factor":         _priv159["mean_decay_factor"],
                        "warning_triggered":         _priv159["warning_triggered"],
                        "privacy_budget_epsilon":    _priv159["privacy_budget_epsilon"],
                        "timestamp":                 _t159.time(),
                    }
                except Exception as _exc159:
                    return {
                        "biometric_privacy_enabled": getattr(self._cfg, "biometric_privacy_enabled", True),
                        "bp001_half_life_days":      90.0,
                        "records_monitored":         0,
                        "records_expired":           0,
                        "mean_decay_factor":         1.0,
                        "warning_triggered":         False,
                        "privacy_budget_epsilon":    0.0,
                        "error":                     str(_exc159),
                        "timestamp":                 _t159.time(),
                    }

            # Tool #115 — Phase 158
            if name == "get_pohbg_status":
                import time as _t158p
                try:
                    _pohbg158 = self._store.get_pohbg_status(limit=1)
                    _latest158p = _pohbg158["recent_hashes"][0] if _pohbg158["recent_hashes"] else None
                    return {
                        "pohbg_enabled":    getattr(self._cfg, "pohbg_enabled", False),
                        "total_pohbg":      _pohbg158["total_pohbg"],
                        "latest_pohbg_hash": _latest158p["pohbg_hash"] if _latest158p else None,
                        "latest_device_id": _latest158p["device_id"] if _latest158p else None,
                        "latest_ts_ns":     _latest158p["ts_ns"] if _latest158p else None,
                        "timestamp":        _t158p.time(),
                    }
                except Exception as _exc158p:
                    return {
                        "pohbg_enabled":    getattr(self._cfg, "pohbg_enabled", False),
                        "total_pohbg":      0,
                        "latest_pohbg_hash": None,
                        "latest_device_id": None,
                        "latest_ts_ns":     None,
                        "error":            str(_exc158p),
                        "timestamp":        _t158p.time(),
                    }

            # Tool #114 — Phase 158
            if name == "get_gsr_hmac_validation_status":
                import time as _t158h
                try:
                    _hmac158 = self._store.get_gsr_hmac_validation_status(limit=5)
                    return {
                        "gsr_hmac_enabled":        getattr(self._cfg, "gsr_hmac_enabled", False),
                        "gsr_hmac_key_configured": bool(getattr(self._cfg, "gsr_hmac_key_hex", "")),
                        "total_validations":       _hmac158["total_validations"],
                        "valid_count":             _hmac158["valid_count"],
                        "rejected_count":          _hmac158["rejected_count"],
                        "timestamp":               _t158h.time(),
                    }
                except Exception as _exc158h:
                    return {
                        "gsr_hmac_enabled":        getattr(self._cfg, "gsr_hmac_enabled", False),
                        "gsr_hmac_key_configured": False,
                        "total_validations":       0,
                        "valid_count":             0,
                        "rejected_count":          0,
                        "error":                   str(_exc158h),
                        "timestamp":               _t158h.time(),
                    }

            # Tool #113 — Phase 157
            if name == "get_fleet_consensus_snapshot":
                import time as _t157
                try:
                    _snaps157 = self._store.get_fleet_consensus_snapshot(limit=1)
                    _latest157 = _snaps157[0] if _snaps157 else None
                    _total157 = 0
                    try:
                        with self._store._conn() as _c157:
                            _total157 = _c157.execute(
                                "SELECT COUNT(*) FROM fleet_consensus_snapshot_log"
                            ).fetchone()[0]
                    except Exception:
                        pass
                    return {
                        "fleet_consensus_enabled": getattr(self._cfg, "fleet_consensus_enabled", True),
                        "total_snapshots":         _total157,
                        "latest_pofc_hash":        _latest157["pofc_hash"] if _latest157 else None,
                        "latest_agent_count":      _latest157["agent_count"] if _latest157 else 0,
                        "latest_separation_ratio": _latest157["separation_ratio"] if _latest157 else 0.0,
                        "timestamp":               _t157.time(),
                    }
                except Exception as _exc157:
                    return {
                        "fleet_consensus_enabled": getattr(self._cfg, "fleet_consensus_enabled", True),
                        "total_snapshots":         0,
                        "latest_pofc_hash":        None,
                        "latest_agent_count":      0,
                        "latest_separation_ratio": 0.0,
                        "error":                   str(_exc157),
                        "timestamp":               _t157.time(),
                    }

            # Tool #112 — Phase 156
            if name == "get_enrollment_auto_guidance_status":
                import time as _t156
                try:
                    _s156 = self._store.get_enrollment_guidance_status()
                    _s156["timestamp"] = _t156.time()
                    return _s156
                except Exception as _exc156:
                    return {
                        "sessions_needed_total": 0,
                        "overall_ready":         False,
                        "recommended_action":    "Run EnrollmentAutoGuidanceAgent",
                        "urgency_level":         "UNKNOWN",
                        "estimated_days":        -1.0,
                        "stagnant_probes":       [],
                        "activation_chain_event": None,
                        "error":                 str(_exc156),
                        "timestamp":             _t156.time(),
                    }

            # Tool #111 — Phase 155
            if name == "get_controller_hardware_status":
                import time as _t155
                try:
                    _profiles155 = self._store.get_controller_hardware_profiles(active_only=False)
                    _attested = sum(1 for p in _profiles155 if p.get("tier") == "Attested")
                    _standard = sum(1 for p in _profiles155 if p.get("tier") == "Standard")
                    _ck = _profiles155[0].get("composite_key", "") if _profiles155 else ""
                    return {
                        "controller_intelligence_enabled": getattr(self._cfg, "controller_intelligence_enabled", True),
                        "multi_controller_enabled":        getattr(self._cfg, "multi_controller_enabled", False),
                        "attested_count":                  _attested,
                        "standard_count":                  _standard,
                        "active_composite_key":            _ck,
                        "profiles":                        _profiles155,
                        "timestamp":                       _t155.time(),
                    }
                except Exception as _exc155:
                    return {
                        "controller_intelligence_enabled": getattr(self._cfg, "controller_intelligence_enabled", True),
                        "multi_controller_enabled":        getattr(self._cfg, "multi_controller_enabled", False),
                        "attested_count":                  0,
                        "standard_count":                  0,
                        "active_composite_key":            "",
                        "profiles":                        [],
                        "error":                           str(_exc155),
                        "timestamp":                       _t155.time(),
                    }

            # Tool #110 — Phase 154
            if name == "get_capture_stagnation_status":
                import time as _t154
                _pt154 = (inputs.get("probe_type", "touchpad_corners") if isinstance(inputs, dict) else "touchpad_corners")
                try:
                    _r154 = self._store.get_capture_stagnation_status(probe_type=_pt154)
                    if not _r154:
                        _r154 = self._store.compute_capture_stagnation(
                            probe_type=_pt154,
                            window_days=float(getattr(self._cfg, "capture_stagnation_window_days", 7.0)),
                            threshold=float(getattr(self._cfg, "capture_stagnation_threshold", 0.5)),
                        )
                    _r154["timestamp"] = _t154.time()
                    return _r154
                except Exception as _exc154:
                    return {
                        "probe_type":         _pt154,
                        "sessions_per_day":   0.0,
                        "stagnant":           True,
                        "sessions_in_window": 0,
                        "window_days":        7.0,
                        "stagnation_threshold": 0.5,
                        "notes":              "",
                        "error":              str(_exc154),
                        "timestamp":          _t154.time(),
                    }

            # Tool #109 — Phase 153
            if name == "get_separation_ratio_registry_status":
                import time as _t153
                try:
                    _r153 = self._store.get_separation_ratio_registry_status()
                    _r153["separation_ratio_on_chain_enabled"] = getattr(self._cfg, "separation_ratio_on_chain_enabled", False)
                    _r153["timestamp"] = _t153.time()
                    return _r153
                except Exception as _exc153:
                    return {
                        "committed":   False,
                        "commit_hash": "",
                        "ratio_millis": 0,
                        "n_sessions":  0,
                        "n_players":   0,
                        "on_chain_tx": None,
                        "total_commits": 0,
                        "separation_ratio_on_chain_enabled": getattr(self._cfg, "separation_ratio_on_chain_enabled", False),
                        "error":       str(_exc153),
                        "timestamp":   _t153.time(),
                    }

            # Tool #108 — Phase 152
            if name == "get_centroid_velocity_status":
                import time as _t152
                _pt152 = (inputs.get("probe_type", "touchpad_corners") if isinstance(inputs, dict) else "touchpad_corners")
                try:
                    _r152 = self._store.get_centroid_velocity_status(probe_type=_pt152)
                    if not _r152:
                        _r152 = self._store.compute_centroid_velocity(probe_type=_pt152)
                    _r152["probe_type"]       = _r152.get("probe_type", _pt152)
                    _r152["velocity_per_day"] = float(_r152.get("velocity", 0.0)) * 86400
                    _r152["timestamp"] = _t152.time()
                    return _r152
                except Exception as _exc152:
                    return {
                        "probe_type":        _pt152,
                        "velocity":          0.0,
                        "velocity_per_day":  0.0,
                        "stagnant":          True,
                        "n_snapshots_used":  0,
                        "ratio_prev":        None,
                        "ratio_curr":        None,
                        "error":             str(_exc152),
                        "timestamp":         _t152.time(),
                    }

            # Tool #107 — Phase 151 P1
            if name == "get_enrollment_capture_guidance":
                import time as _t151
                try:
                    _min_n151 = int(inputs.get("min_n", 10)) if isinstance(inputs, dict) else 10
                    _min_n151 = int(getattr(self._cfg, "min_touchpad_sessions_per_player", _min_n151))
                    _guidance = self._store.get_enrollment_capture_guidance(min_n=_min_n151)
                    _guidance["timestamp"] = _t151.time()
                    return _guidance
                except Exception as _exc151:
                    return {
                        "min_n_per_player":      _min_n151 if "_min_n151" in dir() else 10,
                        "probe_types":           sorted(["touchpad_corners", "touchpad_freeform", "touchpad_swipes"]),
                        "guidance":              {},
                        "sessions_needed_total": 0,
                        "overall_ready":         False,
                        "error":                 str(_exc151),
                        "timestamp":             _t151.time(),
                    }

            # Tool #106 — Phase 150
            if name == "get_separation_defensibility_status":
                import time as _t150
                try:
                    _stype150 = inputs.get("session_type", "touchpad_corners") if isinstance(inputs, dict) else "touchpad_corners"
                    _min_n150 = int(getattr(self._cfg, "min_touchpad_sessions_per_player", 10))
                    _row150 = self._store.get_separation_defensibility_status(session_type=_stype150)
                    if _row150 is None:
                        return {
                            "defensible":        False,
                            "ratio":             0.0,
                            "n_per_player":      {},
                            "min_n_per_player":  _min_n150,
                            "all_pairs_above_1": False,
                            "found":             False,
                        }
                    return {
                        "defensible":        bool(_row150.get("defensible")),
                        "ratio":             float(_row150.get("ratio", 0.0)),
                        "n_per_player":      _row150.get("n_per_player", {}),
                        "min_n_per_player":  int(_row150.get("min_n_per_player", _min_n150)),
                        "all_pairs_above_1": bool(_row150.get("all_pairs_above_1")),
                        "found":             True,
                    }
                except Exception as _exc150:
                    return {
                        "defensible":        False,
                        "ratio":             0.0,
                        "n_per_player":      {},
                        "min_n_per_player":  10,
                        "all_pairs_above_1": False,
                        "error":             str(_exc150),
                    }

            # Tool #105 — Phase 148
            if name == "get_agent_calibration_health":
                import time as _t148
                try:
                    _agent_id_filter = inputs.get("agent_id") if isinstance(inputs, dict) else None
                    _agent_id_int = int(_agent_id_filter) if _agent_id_filter is not None else None
                    _rows148 = self._store.get_agent_calibration_health(limit=32, agent_id=_agent_id_int)
                    _seen148: dict = {}
                    for _row148 in _rows148:
                        _aid = _row148.get("agent_id", 0)
                        if _aid not in _seen148:
                            _seen148[_aid] = _row148
                    _healthy148  = sum(1 for r in _seen148.values() if r.get("result") == "PASS")
                    _degraded148 = sum(1 for r in _seen148.values() if r.get("result") != "PASS")
                    _failed148   = [r.get("agent_name") for r in _seen148.values() if r.get("result") != "PASS"]
                    return {
                        "agent_count":        16,
                        "healthy_count":      _healthy148,
                        "degraded_count":     _degraded148,
                        "failed_agents":      _failed148,
                        "mcp_server_enabled": bool(getattr(self._cfg, "mcp_server_enabled", False)),
                        "timestamp":          _t148.time(),
                    }
                except Exception as exc:
                    return {
                        "agent_count":        16,
                        "healthy_count":      0,
                        "degraded_count":     0,
                        "failed_agents":      [],
                        "mcp_server_enabled": False,
                        "error":              str(exc),
                        "timestamp":          0.0,
                    }

            # Tool #104 — Phase 135
            if name == "get_tournament_activation_chain":
                import time as _t135
                try:
                    _log135 = self._store.get_tournament_activation_chain(limit=10)
                    _gate_open = any(e.get("gate_open_notified") for e in _log135)
                    _last_ratio = _log135[0].get("separation_ratio", 0.0) if _log135 else 0.0
                    _last_ts = _log135[0].get("created_at", 0.0) if _log135 else 0.0
                    return {
                        "gate_open_notified": _gate_open,
                        "auto_activate_on_breakthrough": False,
                        "operator_action_required": True,
                        "last_ratio": _last_ratio,
                        "last_notification_ts": _last_ts,
                        "notification_count": len(_log135),
                        "timestamp": _t135.time(),
                    }
                except Exception as _e135:
                    return {
                        "gate_open_notified": False,
                        "auto_activate_on_breakthrough": False,
                        "operator_action_required": True,
                        "last_ratio": 0.0,
                        "last_notification_ts": 0.0,
                        "notification_count": 0,
                        "error": str(_e135),
                        "timestamp": 0.0,
                    }

            # Tool #103 — Phase 134
            if name == "run_l4_recalibration":
                import time as _t134
                try:
                    _jobs134 = self._store.get_l4_recalibration_jobs(limit=1)
                    _stale134 = (
                        getattr(self._cfg, "live_feature_dim", 13)
                        != getattr(self._cfg, "calibration_feature_dim", 12)
                    )
                    if not _jobs134:
                        return {
                            "in_progress": False,
                            "last_run_ts": 0.0,
                            "sessions_processed": 0,
                            "new_anomaly_threshold": getattr(self._cfg, "l4_anomaly_threshold", 7.009),
                            "new_continuity_threshold": getattr(self._cfg, "l4_continuity_threshold", 5.367),
                            "stale": _stale134,
                            "timestamp": _t134.time(),
                        }
                    _j134 = _jobs134[0]
                    return {
                        "in_progress": _j134.get("status") == "running",
                        "last_run_ts": _j134.get("completed_at") or _j134.get("started_at", 0.0),
                        "sessions_processed": _j134.get("sessions_processed", 0),
                        "new_anomaly_threshold": _j134.get("anomaly_result") or getattr(self._cfg, "l4_anomaly_threshold", 7.009),
                        "new_continuity_threshold": _j134.get("continuity_result") or getattr(self._cfg, "l4_continuity_threshold", 5.367),
                        "stale": _stale134,
                        "timestamp": _t134.time(),
                    }
                except Exception as _e134:
                    return {
                        "in_progress": False,
                        "last_run_ts": 0.0,
                        "sessions_processed": 0,
                        "new_anomaly_threshold": 7.009,
                        "new_continuity_threshold": 5.367,
                        "stale": True,
                        "error": str(_e134),
                        "timestamp": 0.0,
                    }

            # Tool #102 — Phase 133
            if name == "get_ioswarm_poad_anchor_status":
                import time as _t133
                try:
                    _enabled133 = bool(getattr(self._cfg, "ioswarm_poad_auto_anchor_enabled", False))
                    _log133 = self._store.get_ioswarm_poad_anchor_log(limit=50)
                    _anchored133 = sum(1 for e in _log133 if e.get("anchor_status") == "anchored")
                    _pending133  = sum(1 for e in _log133 if e.get("anchor_status") == "pending")
                    _dv133       = sum(1 for e in _log133 if e.get("dual_veto"))
                    _failed133   = sum(1 for e in _log133 if e.get("anchor_status") == "failed")
                    _ltx133      = next((e.get("on_chain_tx") for e in _log133 if e.get("on_chain_tx")), None)
                    return {
                        "poad_auto_anchor_enabled": _enabled133,
                        "anchored_count":           _anchored133,
                        "pending_count":            _pending133,
                        "last_anchor_tx":           _ltx133,
                        "dual_veto_count":          _dv133,
                        "anchor_failure_count":     _failed133,
                        "timestamp":                _t133.time(),
                    }
                except Exception as _e133:
                    return {
                        "poad_auto_anchor_enabled": False,
                        "anchored_count":           0,
                        "pending_count":            0,
                        "last_anchor_tx":           None,
                        "dual_veto_count":          0,
                        "anchor_failure_count":     0,
                        "error":                    str(_e133),
                        "timestamp":                0.0,
                    }

            # Tool #101 — Phase 132
            if name == "ping_ioswarm_nodes":
                import time as _t132
                try:
                    from .ioswarm_live_node_client import IoSwarmLiveNodeClient
                    _client132 = IoSwarmLiveNodeClient(cfg=self._cfg, store=self._store)
                    _emulator_mode = _client132.is_emulator_mode()
                    # poll_node_health() is async; run it in its own event loop since
                    # _execute_tool is a sync method called from a thread pool
                    import asyncio as _aio132
                    if not _emulator_mode:
                        try:
                            _loop132 = _aio132.get_event_loop()
                            if _loop132.is_running():
                                import concurrent.futures as _cf132
                                _fut132 = _cf132.Future()
                                async def _poll132():
                                    return await _client132.poll_node_health()
                                _task132 = _aio132.ensure_future(_poll132())
                                _health_list = []  # async poll deferred to background
                            else:
                                _health_list = _loop132.run_until_complete(_client132.poll_node_health())
                        except RuntimeError:
                            _health_list = []
                        _nodes_healthy = sum(1 for n in _health_list if n.get("healthy"))
                        _latencies = [n.get("latency_ms", -1) for n in _health_list if n.get("latency_ms", -1) >= 0]
                        _avg_lat = (sum(_latencies) / len(_latencies)) if _latencies else -1.0
                        # persist health results
                        for _n in _health_list:
                            try:
                                self._store.insert_ioswarm_node_health(
                                    node_url=_n.get("node_url", ""),
                                    healthy=bool(_n.get("healthy", False)),
                                    latency_ms=float(_n.get("latency_ms", -1)),
                                    staker_address=_n.get("staker_address", ""),
                                    error_msg=_n.get("error_msg", ""),
                                )
                            except Exception:
                                pass
                    else:
                        _health_list = []
                        _nodes_healthy = 0
                        _avg_lat = -1.0
                    _url_raw = getattr(self._cfg, "ioswarm_node_urls", "") or ""
                    _nodes_configured = len([u for u in _url_raw.split(",") if u.strip()])
                    _log_count = len(self._store.get_ioswarm_node_health(limit=100))
                    return {
                        "nodes_configured": _nodes_configured,
                        "nodes_healthy":    _nodes_healthy,
                        "emulator_mode":    _emulator_mode,
                        "avg_latency_ms":   round(_avg_lat, 2),
                        "health_log_count": _log_count,
                        "error":            None,
                        "timestamp":        _t132.time(),
                    }
                except Exception as _e132:
                    return {
                        "nodes_configured": 0,
                        "nodes_healthy":    0,
                        "emulator_mode":    True,
                        "avg_latency_ms":   -1.0,
                        "health_log_count": 0,
                        "error":            str(_e132),
                        "timestamp":        0.0,
                    }

            # Tool #100 — Phase 131B
            if name == "get_usb_stability_status":
                import time as _t131b
                try:
                    summary = self._store.get_usb_stability_status(limit=100)
                    ps5_compat = bool(getattr(self._cfg, "ps5_compat_mode", False))
                    return {
                        "disconnect_count":                summary.get("disconnect_count", 0),
                        "last_disconnect_ts":              summary.get("last_disconnect_ts", 0.0),
                        "ps5_compat_mode":                 ps5_compat,
                        "consecutive_fb_timeouts_threshold": 6,
                        "timestamp":                       _t131b.time(),
                    }
                except Exception as _e131b:
                    return {
                        "disconnect_count":                0,
                        "last_disconnect_ts":              0.0,
                        "ps5_compat_mode":                 False,
                        "consecutive_fb_timeouts_threshold": 6,
                        "timestamp":                       0.0,
                        "error":                           str(_e131b),
                    }

            # Tool #99 — Phase 131
            if name == "get_ioswarm_node_registry_status":
                import time as _t131ba
                try:
                    from .ioswarm_live_node_client import IoSwarmLiveNodeClient
                    _client131 = IoSwarmLiveNodeClient(cfg=self._cfg, store=self._store)
                    _node_urls_raw = getattr(self._cfg, "ioswarm_node_urls", "") or ""
                    _emulator_mode = _client131.is_emulator_mode()
                    _timeout_s = float(getattr(self._cfg, "ioswarm_node_timeout_seconds", 5.0))
                    _regs = self._store.get_ioswarm_node_registry(active_only=False)
                    _active = [r for r in _regs if r.get("active")]
                    _quorum = self._store.get_swarm_quorum_validation_log(limit=1)
                    _last_q_ts = float(_quorum[0].get("created_at", 0.0)) if _quorum else 0.0
                    return {
                        "live_nodes":     len(_active),
                        "emulator_mode":  _emulator_mode,
                        "registry_count": len(_regs),
                        "node_timeout_s": _timeout_s,
                        "last_quorum_ts": _last_q_ts,
                        "timestamp":      _t131ba.time(),
                        "error":          None,
                    }
                except Exception as _e131:
                    return {
                        "live_nodes":     0,
                        "emulator_mode":  True,
                        "registry_count": 0,
                        "node_timeout_s": 5.0,
                        "last_quorum_ts": 0.0,
                        "timestamp":      __import__("time").time(),
                        "error":          str(_e131),
                    }

            # Tool #98 — Phase 130A
            if name == "get_swarm_operator_gate_status":
                import time as _t130ba
                try:
                    _rows130 = self._store.get_swarm_quorum_validation_log(limit=1)
                    _gate_addr = getattr(self._cfg, "swarm_operator_gate_address", "")
                    _last_valid = False
                    _last_nc = 0
                    if _rows130:
                        _last_valid = bool(_rows130[0].get("quorum_valid", 0))
                        _last_nc = int(_rows130[0].get("node_count", 0))
                    return {
                        "gate_configured": bool(_gate_addr),
                        "valid":           _last_valid,
                        "node_count":      _last_nc,
                        "timestamp":       _t130ba.time(),
                        "error":           None,
                    }
                except Exception as _exc130:
                    return {
                        "gate_configured": False,
                        "valid":           False,
                        "node_count":      0,
                        "timestamp":       0.0,
                        "error":           str(_exc130),
                    }

            # Tool #97 — Phase 129
            if name == "get_separation_ratio_breakthrough":
                import time as _t129ba
                try:
                    _rows129 = self._store.get_separation_ratio_breakthrough(limit=5)
                    if _rows129:
                        _latest129 = _rows129[0]
                        return {
                            "breakthrough_detected": True,
                            "breakthrough_ratio":    float(_latest129.get("after_ratio", 0.0)),
                            "breakthrough_ts":       float(_latest129.get("breakthrough_at", 0.0)),
                            "n_players":             int(_latest129.get("n_players", 0)),
                            "error":                 None,
                        }
                    return {
                        "breakthrough_detected": False,
                        "breakthrough_ratio":    0.0,
                        "breakthrough_ts":       0.0,
                        "n_players":             0,
                        "error":                 None,
                    }
                except Exception as _exc129:
                    return {
                        "breakthrough_detected": False,
                        "breakthrough_ratio":    0.0,
                        "breakthrough_ts":       0.0,
                        "n_players":             0,
                        "error":                 str(_exc129),
                    }

            # Tool #96 — Phase 128
            if name == "get_tournament_readiness_score":
                import time as _t128ba
                import json as _j128ba
                try:
                    _sep128 = float(getattr(self._cfg, "separation_ratio_current", 0.0))
                    _snaps128 = self._store.get_separation_ratio_status(limit=1)
                    if _snaps128:
                        _sep128 = float(_snaps128[0].get("pooled_ratio", _sep128))
                    _sep_s128 = min(1.0, _sep128)

                    _live128  = int(getattr(self._cfg, "live_feature_dim", 13))
                    _calib128 = int(getattr(self._cfg, "calibration_feature_dim", 12))
                    _l4_s128  = 1.0 if _live128 == _calib128 else 0.0

                    _dge128 = bool(getattr(self._cfg, "dual_primitive_gate_enabled", False))
                    try:
                        _glogs128 = self._store.get_vhp_dual_gate_log(limit=100)
                        _now128 = _t128ba.time()
                        _r128 = [lg for lg in _glogs128 if lg.get("eligible") and (_now128 - float(lg.get("created_at", 0))) < 86400.0]
                        _dg_s128 = 1.0 if _r128 else (0.5 if _dge128 else 0.0)
                    except Exception:
                        _dg_s128 = 0.5 if _dge128 else 0.0

                    _ewe128 = bool(getattr(self._cfg, "epoch_window_enabled", False))
                    _ews128 = float(getattr(self._cfg, "epoch_window_seconds", 86400.0))
                    try:
                        _ea128 = self._store.get_epoch_window_analytics(limit=1000)
                        _p95128 = float(_ea128.get("p95_age_seconds", 0.0))
                        if _p95128 <= 0 or _ea128.get("checked_count", 0) == 0:
                            _epoch_s128 = 0.5 if _ewe128 else 0.0
                        elif _p95128 < _ews128:
                            _epoch_s128 = 1.0
                        else:
                            _epoch_s128 = max(0.0, 1.0 - _p95128 / _ews128)
                    except Exception:
                        _epoch_s128 = 0.5 if _ewe128 else 0.0

                    _iome128 = bool(getattr(self._cfg, "ioswarm_vhp_mint_enabled", False))
                    if _iome128:
                        try:
                            _ml128 = self._store.get_ioswarm_vhp_mint_log(limit=1)
                            _ioswarm_s128 = 1.0 if (_ml128 and _ml128[0].get("authorized")) else 0.5
                        except Exception:
                            _ioswarm_s128 = 0.5
                    else:
                        _ioswarm_s128 = 0.0

                    _dry128 = bool(getattr(self._cfg, "agent_dry_run_mode", True))
                    _dry_s128 = 0.0 if _dry128 else 1.0

                    _score128 = round(min(1.0, max(0.0,
                        0.30 * _sep_s128 + 0.20 * _l4_s128 + 0.15 * _dg_s128
                        + 0.15 * _epoch_s128 + 0.10 * _ioswarm_s128 + 0.10 * _dry_s128
                    )), 4)

                    _cmet128 = sum([
                        _sep_s128 >= 1.0, _l4_s128 >= 1.0, _dg_s128 >= 1.0,
                        _epoch_s128 >= 1.0, _ioswarm_s128 >= 1.0, _dry_s128 >= 1.0,
                    ])

                    _breakdown128 = {
                        "separation_score": _sep_s128, "l4_score": _l4_s128,
                        "dual_gate_score": _dg_s128, "epoch_score": _epoch_s128,
                        "ioswarm_score": _ioswarm_s128, "dry_run_score": _dry_s128,
                    }
                    try:
                        self._store.insert_readiness_score(
                            score=_score128,
                            breakdown_json=_j128ba.dumps(_breakdown128),
                            conditions_met=_cmet128,
                        )
                    except Exception:
                        pass
                    return {
                        "score":            _score128,
                        "separation_score": _sep_s128,
                        "l4_score":         _l4_s128,
                        "dual_gate_score":  _dg_s128,
                        "epoch_score":      _epoch_s128,
                        "ioswarm_score":    _ioswarm_s128,
                        "dry_run_score":    _dry_s128,
                        "conditions_met":   _cmet128,
                        "timestamp":        _t128ba.time(),
                    }
                except Exception as exc:
                    return {
                        "score": 0.0, "separation_score": 0.0, "l4_score": 0.0,
                        "dual_gate_score": 0.0, "epoch_score": 0.0,
                        "ioswarm_score": 0.0, "dry_run_score": 0.0,
                        "conditions_met": 0, "error": str(exc),
                        "timestamp": _t128ba.time(),
                    }

            # Tool #95 — Phase 127
            if name == "run_tournament_preflight":
                import time as _t127ba
                import json as _j127ba
                try:
                    _sep_ratio127 = float(getattr(self._cfg, "separation_ratio_current", 0.0))
                    _snaps127 = self._store.get_separation_ratio_status(limit=1)
                    if _snaps127:
                        _sep_ratio127 = float(_snaps127[0].get("pooled_ratio", _sep_ratio127))
                    _separation_ok = _sep_ratio127 >= 1.0
                    _live_dim  = int(getattr(self._cfg, "live_feature_dim", 13))
                    _calib_dim = int(getattr(self._cfg, "calibration_feature_dim", 12))
                    _l4_ok     = (_live_dim == _calib_dim)
                    _gate_n127 = int(getattr(self._cfg, "validation_gate_n", 100))
                    _max_div127 = float(getattr(self._cfg, "validation_max_divergence_rate", 1.0))
                    _gate_s127 = self._store.get_validation_summary(_gate_n127, _max_div127)
                    _gate_ok127 = bool(_gate_s127.get("gate_passed", False))
                    _cert127  = self._store.get_latest_enforcement_certificate()
                    _cert_ok127 = bool(
                        _cert127 is not None
                        and _cert127.get("audit_valid")
                        and _t127ba.time() <= _cert127.get("expires_at", 0)
                    )
                    _audit127 = self._store.get_activation_audit_summary()
                    _audit_ok127 = bool(_audit127.get("audit_valid", False))
                    _dg_warn = not bool(getattr(self._cfg, "dual_primitive_gate_enabled", False))
                    _ew_warn = not bool(getattr(self._cfg, "epoch_window_enabled", False))
                    _is_warn = not bool(getattr(self._cfg, "ioswarm_vhp_mint_enabled", False))
                    _overall127 = _separation_ok and _l4_ok and _gate_ok127 and _cert_ok127 and _audit_ok127
                    _cond127 = {
                        "separation_ratio": _sep_ratio127,
                        "separation_ok": _separation_ok,
                        "l4_ok": _l4_ok,
                        "gate_ok": _gate_ok127,
                        "cert_ok": _cert_ok127,
                        "audit_ok": _audit_ok127,
                        "overall_pass": _overall127,
                    }
                    self._store.insert_tournament_preflight_log(
                        separation_ok=_separation_ok, l4_ok=_l4_ok, gate_ok=_gate_ok127,
                        cert_ok=_cert_ok127, audit_ok=_audit_ok127,
                        dual_gate_warned=_dg_warn, epoch_window_warned=_ew_warn,
                        ioswarm_warned=_is_warn, overall_pass=_overall127,
                        conditions_json=_j127ba.dumps(_cond127),
                    )
                    return {
                        "separation_ok":       _separation_ok,
                        "l4_ok":               _l4_ok,
                        "gate_ok":             _gate_ok127,
                        "cert_ok":             _cert_ok127,
                        "audit_ok":            _audit_ok127,
                        "dual_gate_warned":    _dg_warn,
                        "epoch_window_warned": _ew_warn,
                        "ioswarm_warned":      _is_warn,
                        "overall_pass":        _overall127,
                        "conditions":          _cond127,
                        "timestamp":           _t127ba.time(),
                    }
                except Exception as exc:
                    return {
                        "separation_ok": False, "l4_ok": False, "gate_ok": False,
                        "cert_ok": False, "audit_ok": False, "overall_pass": False,
                        "dual_gate_warned": True, "epoch_window_warned": True,
                        "ioswarm_warned": True, "conditions": {},
                        "error": str(exc), "timestamp": _t127ba.time(),
                    }

            # Tool #94 — Phase 126
            if name == "get_l4_router_status":
                import time as _t126ba
                try:
                    _enabled126 = bool(getattr(self._cfg, "l4_battery_threshold_enabled", False))
                    _logs126    = self._store.get_l4_router_log(limit=1000)
                    _total126   = len(_logs126)
                    _pb126      = sum(
                        1 for e in _logs126 if e.get("threshold_source") == "per_battery"
                    )
                    _gf126      = _total126 - _pb126
                    _last_bt126 = _logs126[0]["battery_type"] if _logs126 else ""
                    _last_src126 = _logs126[0]["threshold_source"] if _logs126 else ""
                    return {
                        "l4_battery_threshold_enabled": _enabled126,
                        "total_lookups":                _total126,
                        "per_battery_lookups":          _pb126,
                        "global_fallback_count":        _gf126,
                        "last_battery_type":            _last_bt126,
                        "last_source":                  _last_src126,
                        "timestamp":                    _t126ba.time(),
                    }
                except Exception as _exc126:
                    return {
                        "l4_battery_threshold_enabled": False,
                        "total_lookups":                0,
                        "per_battery_lookups":          0,
                        "global_fallback_count":        0,
                        "last_battery_type":            "",
                        "last_source":                  "",
                        "timestamp":                    0.0,
                        "error":                        str(_exc126),
                    }

            # Tool #93 — Phase 125
            if name == "apply_l4_battery_calibration":
                import time as _t125ba
                try:
                    _bt125      = str(inputs.get("battery_type", ""))
                    _anom125    = float(inputs.get("anomaly_threshold", 7.009))
                    _cont125    = float(inputs.get("continuity_threshold", 5.367))
                    _n125       = int(inputs.get("n_sessions", 0))
                    _live125    = int(getattr(self._cfg, "live_feature_dim", 13))
                    _caldim125  = int(inputs.get("calibration_feature_dim", _live125))
                    _notes125   = inputs.get("notes", None)
                    _tid125 = self._store.insert_l4_threshold_track(
                        battery_type=_bt125,
                        anomaly_threshold=_anom125,
                        continuity_threshold=_cont125,
                        n_sessions=_n125,
                        calibrated_at=_t125ba.time(),
                        active=True,
                    )
                    _rid125 = self._store.insert_l4_battery_calibration_run(
                        battery_type=_bt125,
                        anomaly_threshold=_anom125,
                        continuity_threshold=_cont125,
                        n_sessions=_n125,
                        calibration_feature_dim=_caldim125,
                        notes=_notes125,
                    )
                    object.__setattr__(self._cfg, "calibration_feature_dim", _caldim125)
                    _stale125 = _live125 != _caldim125
                    return {
                        "track_id":                _tid125,
                        "run_id":                  _rid125,
                        "battery_type":            _bt125,
                        "anomaly_threshold":       round(_anom125, 4),
                        "continuity_threshold":    round(_cont125, 4),
                        "n_sessions":              _n125,
                        "calibration_feature_dim": _caldim125,
                        "stale":                   _stale125,
                        "timestamp":               _t125ba.time(),
                    }
                except Exception as _exc125:
                    import time as _t125bb
                    return {
                        "track_id":                None,
                        "run_id":                  None,
                        "battery_type":            inputs.get("battery_type", ""),
                        "anomaly_threshold":       0.0,
                        "continuity_threshold":    0.0,
                        "n_sessions":              0,
                        "calibration_feature_dim": 13,
                        "stale":                   True,
                        "timestamp":               _t125bb.time(),
                        "error":                   str(_exc125),
                    }

            # Tool #92 — Phase 124
            if name == "get_l4_threshold_tracks":
                import time as _t124ba
                try:
                    _bt124      = inp.get("battery_type", None)
                    _ao124      = bool(inp.get("active_only", False))
                    _enabled124 = bool(getattr(self._cfg, "l4_battery_threshold_enabled", False))
                    _tracks124  = self._store.get_l4_threshold_tracks(
                        battery_type=_bt124, active_only=_ao124
                    )
                    return {
                        "l4_battery_threshold_enabled": _enabled124,
                        "track_count":                  len(_tracks124),
                        "active_count":                 sum(1 for t in _tracks124 if t["active"]),
                        "battery_types_tracked":        list({t["battery_type"] for t in _tracks124}),
                        "tracks":                       _tracks124,
                        "timestamp":                    _t124ba.time(),
                    }
                except Exception as _exc124:
                    import time as _t124bb
                    return {
                        "l4_battery_threshold_enabled": False,
                        "track_count":                  0,
                        "active_count":                 0,
                        "battery_types_tracked":        [],
                        "tracks":                       [],
                        "timestamp":                    _t124bb.time(),
                        "error":                        str(_exc124),
                    }

            # Tool #91 — Phase 123
            if name == "get_l4_calibration_status":
                import time as _t123ba
                try:
                    _live123  = int(getattr(self._cfg, "live_feature_dim", 13))
                    _cal123   = int(getattr(self._cfg, "calibration_feature_dim", 12))
                    _n123     = int(getattr(self._cfg, "calibration_n_sessions", 74))
                    _ts123    = float(getattr(self._cfg, "calibration_timestamp", 0.0))
                    _anom123  = float(getattr(self._cfg, "l4_anomaly_threshold", 7.009))
                    _cont123  = float(getattr(self._cfg, "l4_continuity_threshold", 5.367))
                    return {
                        "current_feature_dim":     _live123,
                        "calibration_feature_dim": _cal123,
                        "stale":                   _live123 != _cal123,
                        "anomaly_threshold":        round(_anom123, 4),
                        "continuity_threshold":     round(_cont123, 4),
                        "calibration_n_sessions":   _n123,
                        "calibration_timestamp":    _ts123,
                        "timestamp":               _t123ba.time(),
                    }
                except Exception as _exc123:
                    import time as _t123bb
                    return {
                        "current_feature_dim":     13,
                        "calibration_feature_dim": 12,
                        "stale":                   True,
                        "anomaly_threshold":        7.009,
                        "continuity_threshold":     5.367,
                        "calibration_n_sessions":   74,
                        "calibration_timestamp":    0.0,
                        "timestamp":               _t123bb.time(),
                        "error":                   str(_exc123),
                    }

            # Tool #90 — Phase 122
            if name == "get_confidence_score_multiplier_status":
                import time as _t122ba
                try:
                    _en122   = bool(getattr(self._cfg, "confidence_multiplier_enabled", False))
                    _floor122 = float(getattr(self._cfg, "confidence_multiplier_floor", 0.0))
                    _snaps122 = self._store.get_separation_ratio_status(limit=1)
                    _bt122    = _snaps122[0].get("bt_strat_ratio", -1.0) if _snaps122 else -1.0
                    _eff122   = (
                        max(_floor122, min(1.0, _bt122)) if _bt122 >= 0 else 1.0
                    )
                    _log122   = self._store.get_confidence_multiplier_log(limit=5)
                    return {
                        "multiplier_enabled":     _en122,
                        "current_bt_strat_ratio": round(_bt122, 4),
                        "effective_multiplier":   round(_eff122, 4),
                        "floor":                  _floor122,
                        "log_count":              len(_log122),
                        "recent_applications":    _log122,
                        "timestamp":              _t122ba.time(),
                    }
                except Exception as _exc122:
                    import time as _t122bb
                    return {
                        "multiplier_enabled":     False,
                        "current_bt_strat_ratio": -1.0,
                        "effective_multiplier":   1.0,
                        "floor":                  0.0,
                        "log_count":              0,
                        "recent_applications":    [],
                        "timestamp":              _t122bb.time(),
                        "error":                  str(_exc122),
                    }

            # Tool #89 — Phase 121
            if name == "get_separation_ratio_status":
                import time as _t121ba
                try:
                    _pooled121 = float(getattr(self._cfg, "separation_ratio_current", 1.261))
                    _snaps121  = self._store.get_separation_ratio_status(limit=1)
                    _bt121     = _snaps121[0].get("bt_strat_ratio", -1.0) if _snaps121 else -1.0
                    _ready121  = _pooled121 >= 1.0
                    return {
                        "pooled_ratio":             round(_pooled121, 4),
                        "battery_stratified_ratio": round(_bt121, 4) if _bt121 >= 0 else -1.0,
                        "tournament_blocker":       not _ready121,
                        "target_ratio":             1.0,
                        "gap_to_target":            round(max(0.0, 1.0 - _pooled121), 4),
                        "tournament_ready":         _ready121,
                        "timestamp":                _t121ba.time(),
                    }
                except Exception as _exc121:
                    import time as _t121bb
                    return {
                        "pooled_ratio":             0.0,
                        "battery_stratified_ratio": -1.0,
                        "tournament_blocker":       True,
                        "target_ratio":             1.0,
                        "gap_to_target":            1.0,
                        "tournament_ready":         False,
                        "timestamp":                _t121bb.time(),
                        "error":                    str(_exc121),
                    }

            # Tool #88 — Phase 120
            if name == "get_bt_transport_status":
                import time as _t120ba
                try:
                    _lim120   = int(inp.get("limit", 10))
                    _logs120  = self._store.get_bt_transport_status(limit=_lim120)
                    _en120    = bool(getattr(self._cfg, "bt_transport_enabled", False))
                    _addr120  = str(getattr(self._cfg, "bt_device_address", ""))
                    _hz120    = int(getattr(self._cfg, "bt_sampling_rate_hz", 250))
                    _rx120    = sum(r.get("frames_received", 0) for r in _logs120)
                    _drop120  = sum(r.get("frames_dropped", 0) for r in _logs120)
                    _avg120   = (
                        sum(r.get("avg_interval_ms", 0.0) for r in _logs120) / len(_logs120)
                        if _logs120 else 0.0
                    )
                    return {
                        "bt_transport_enabled": _en120,
                        "device_address":       _addr120,
                        "sampling_rate_hz":     _hz120,
                        "frames_received":      _rx120,
                        "frames_dropped":       _drop120,
                        "avg_interval_ms":      round(_avg120, 3),
                        "timestamp":            _t120ba.time(),
                    }
                except Exception as _exc120:
                    import time as _t120be
                    return {
                        "bt_transport_enabled": False,
                        "device_address":       "",
                        "sampling_rate_hz":     250,
                        "frames_received":      0,
                        "frames_dropped":       0,
                        "avg_interval_ms":      0.0,
                        "timestamp":            _t120be.time(),
                        "error":                str(_exc120),
                    }

            # Tool #87 — Phase 119
            if name == "revoke_device_epoch_override":
                import time as _t119b
                try:
                    _dev119b = str(inputs["device_id"])
                    _revoked = self._store.delete_device_epoch_override(_dev119b)
                    return {
                        "device_id": _dev119b,
                        "revoked":   _revoked,
                        "timestamp": _t119b.time(),
                    }
                except Exception as _exc119b:
                    return {
                        "device_id": inputs.get("device_id", ""),
                        "revoked":   False,
                        "timestamp": _t119b.time(),
                        "error":     str(_exc119b),
                    }

            # Tool #86 — Phase 119
            if name == "get_epoch_window_override_status":
                import time as _t119a
                try:
                    _ovrs119  = self._store.get_override_lifecycle_status()
                    _wmax119  = sum(1 for o in _ovrs119 if o.get("max_uses") is not None)
                    _en119    = bool(getattr(self._cfg, "epoch_window_enabled", False))
                    return {
                        "override_count":          len(_ovrs119),
                        "overrides_with_max_uses": _wmax119,
                        "overrides":               _ovrs119,
                        "epoch_window_enabled":    _en119,
                        "timestamp":               _t119a.time(),
                    }
                except Exception as _exc119a:
                    return {
                        "override_count":          0,
                        "overrides_with_max_uses": 0,
                        "overrides":               [],
                        "epoch_window_enabled":    False,
                        "timestamp":               _t119a.time(),
                        "error":                   str(_exc119a),
                    }

            # Tool #85 — Phase 118
            if name == "set_device_epoch_override":
                import time as _t118b
                try:
                    _dev118   = str(inputs["device_id"])
                    _win118   = float(inputs["window_seconds"])
                    _rsn118   = str(inputs.get("reason", ""))
                    _rid118   = self._store.insert_device_epoch_override(
                        device_id=_dev118, window_seconds=_win118, reason=_rsn118
                    )
                    return {
                        "device_id":               _dev118,
                        "override_window_seconds": _win118,
                        "reason":                  _rsn118,
                        "row_id":                  _rid118,
                        "timestamp":               _t118b.time(),
                    }
                except Exception as _exc118b:
                    return {
                        "device_id": inputs.get("device_id", ""),
                        "override_window_seconds": -1.0,
                        "reason": "",
                        "row_id": -1,
                        "timestamp": _t118b.time(),
                        "error": str(_exc118b),
                    }

            # Tool #84 — Phase 118
            if name == "get_epoch_window_auto_tune":
                import time as _t118a
                try:
                    _tn118   = int(inputs.get("top_n_overrides", 5))
                    _ana118  = self._store.get_epoch_window_analytics()
                    _devs118 = self._store.get_epoch_window_analytics_by_device()
                    _ovrs118 = self._store.get_all_device_epoch_overrides()
                    _ovr_ids = {o["device_id"] for o in _ovrs118}
                    _cands   = [d for d in _devs118 if d["device_id"] not in _ovr_ids][:_tn118]
                    _en118   = bool(getattr(self._cfg, "epoch_window_enabled", False))
                    _cur_win = float(getattr(self._cfg, "epoch_window_seconds", 86400.0))
                    return {
                        "epoch_window_enabled":       _en118,
                        "current_window_seconds":     _cur_win,
                        "recommended_window_seconds": _ana118.get("recommended_window_seconds", 86400.0),
                        "fleet_p95_age_seconds":      _ana118.get("p95_age_seconds", -1.0),
                        "override_count":             len(_ovrs118),
                        "override_candidates":        _cands,
                        "timestamp":                  _t118a.time(),
                    }
                except Exception as _exc118a:
                    return {
                        "epoch_window_enabled": False,
                        "current_window_seconds": 86400.0,
                        "recommended_window_seconds": 86400.0,
                        "fleet_p95_age_seconds": -1.0,
                        "override_count": 0,
                        "override_candidates": [],
                        "timestamp": _t118a.time(),
                        "error": str(_exc118a),
                    }

            # Tool #83 — Phase 117
            if name == "get_epoch_window_device_heatmap":
                import time as _t117
                try:
                    _lpd117 = int(inp.get("limit_per_device", 100))
                    _tn117  = int(inp.get("top_n", 20))
                    _devs117 = self._store.get_epoch_window_analytics_by_device(
                        limit_per_device=_lpd117, top_n=_tn117
                    )
                    _ew_en117  = bool(getattr(self._cfg, "epoch_window_enabled", False))
                    _ew_sec117 = float(getattr(self._cfg, "epoch_window_seconds", 86400.0))
                    return {
                        "epoch_window_enabled": _ew_en117,
                        "epoch_window_seconds": _ew_sec117,
                        "total_devices":        len(_devs117),
                        "devices":              _devs117,
                        "timestamp":            _t117.time(),
                    }
                except Exception as _exc117:
                    return {
                        "epoch_window_enabled": False,
                        "epoch_window_seconds": 86400.0,
                        "total_devices": 0,
                        "devices": [],
                        "timestamp": _t117.time(),
                        "error": str(_exc117),
                    }

            # Tool #82 — Phase 116
            if name == "get_epoch_window_analytics":
                import time as _t116
                try:
                    _lim116 = int(inp.get("limit", 1000))
                    _ana116 = self._store.get_epoch_window_analytics(limit=_lim116)
                    _ew_en  = bool(getattr(self._cfg, "epoch_window_enabled", False))
                    _ew_sec = float(getattr(self._cfg, "epoch_window_seconds", 86400.0))
                    return {
                        "epoch_window_enabled":   _ew_en,
                        "epoch_window_seconds":   _ew_sec,
                        **_ana116,
                        "timestamp": _t116.time(),
                    }
                except Exception as _exc116:
                    import time as _t116b
                    return {
                        "epoch_window_enabled": False,
                        "epoch_window_seconds": 86400.0,
                        "total_gate5_checks": 0, "staleness_blocked_count": 0,
                        "checked_count": 0, "p50_age_seconds": -1.0,
                        "p95_age_seconds": -1.0, "recommended_window_seconds": 86400.0,
                        "timestamp": _t116b.time(), "error": str(_exc116),
                    }

            # Tool #81 — Phase 114
            if name == "get_vhp_dual_gate_log":
                import time as _t114
                try:
                    _dev114  = inp.get("device_id") or None
                    _lim114  = int(inp.get("limit", 20))
                    _logs114 = self._store.get_vhp_dual_gate_log(device_id=_dev114, limit=_lim114)
                    _en114   = bool(getattr(self._cfg, "dual_primitive_gate_enabled", False))
                    return {
                        "dual_primitive_gate_enabled": _en114,
                        "total_checks":       len(_logs114),
                        "eligible_count":     sum(1 for r in _logs114 if r.get("eligible")),
                        "mint_allowed_count": sum(1 for r in _logs114 if r.get("mint_allowed")),
                        "recent_logs":        _logs114,
                        "timestamp":          _t114.time(),
                    }
                except Exception as _exc114:
                    return {
                        "dual_primitive_gate_enabled": False,
                        "total_checks": 0, "eligible_count": 0, "mint_allowed_count": 0,
                        "recent_logs": [], "timestamp": _t114.time(), "error": str(_exc114),
                    }

            # Tool #80 — Phase 113
            if name == "check_dual_eligibility":
                import time as _t113
                try:
                    _device_id = str(inp.get("device_id", ""))
                    _poad_hash = str(inp.get("poad_hash", ""))
                    _checks    = self._store.get_dual_eligibility_history(
                        device_id=_device_id, limit=1
                    )
                    if _checks:
                        _last = _checks[0]
                        return {
                            "eligible":   _last["eligible"],
                            "poac_valid": _last["poac_valid"],
                            "poad_valid": _last["poad_valid"],
                            "device_id":  _device_id,
                            "note": "last stored check result (use POST /agent/check-dual-eligibility for live query)",
                            "timestamp":  _t113.time(),
                        }
                    return {
                        "eligible": False, "poac_valid": False, "poad_valid": False,
                        "device_id": _device_id,
                        "note": "no prior check for this device — POST /agent/check-dual-eligibility",
                        "timestamp": _t113.time(),
                    }
                except Exception as _exc113:
                    return {
                        "eligible": False, "poac_valid": False, "poad_valid": False,
                        "device_id": inp.get("device_id", ""),
                        "error": str(_exc113),
                        "timestamp": _t113.time(),
                    }

            # Tool #79 — Phase 111
            if name == "get_adjudication_registry_status":
                import time as _t111
                try:
                    _poad_logs = self._store.get_poad_registry_log(limit=100)
                    _dv_count  = sum(1 for r in _poad_logs if r.get("dual_veto"))
                    _chain_cnt = sum(1 for r in _poad_logs if r.get("on_chain_tx"))
                    _addr      = getattr(self._cfg, "adjudication_registry_address", "")
                    _enabled   = bool(getattr(self._cfg, "poad_registry_enabled", False))
                    return {
                        "poad_registry_enabled":          _enabled,
                        "total_poad_count":               len(_poad_logs),
                        "dual_veto_poad_count":           _dv_count,
                        "on_chain_anchor_count":          _chain_cnt,
                        "adjudication_registry_address":  _addr,
                        "is_composable":                  bool(_addr and _enabled),
                        "timestamp":                      _t111.time(),
                    }
                except Exception as _exc111:
                    return {
                        "poad_registry_enabled": False,
                        "total_poad_count": 0,
                        "dual_veto_poad_count": 0,
                        "on_chain_anchor_count": 0,
                        "adjudication_registry_address": "",
                        "is_composable": False,
                        "timestamp": _t111.time(),
                        "error": str(_exc111),
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
                    sep  = float(getattr(self._cfg, "separation_ratio_current", 1.261))
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
