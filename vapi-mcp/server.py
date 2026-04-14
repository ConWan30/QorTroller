"""
VAPI Model Context Protocol Server
====================================
Exposes VAPI's live protocol state, calibration tools, and agent fleet
directly to Claude Code as native MCP tools.

No more copy-pasting assessment documents. Claude Code reads live state.
No more guessing which phase added which endpoint. Claude Code queries directly.
No more manual MEMORY.md updates. Claude Code writes them from live data.

Architecture:
  Claude Code (MCP client)
    stdio transport
  VAPI MCP Server (this file)
    HTTP
  VAPI Bridge (localhost:8080)
    SQLite + IoTeX RPC
  43+ live contracts + 36 agents (counts read live from CLAUDE.md)

Usage:
  python vapi-mcp/server.py

Claude Code config (C:/Users/Contr/AppData/Roaming/Claude/claude_desktop_config.json
or Claude Code settings):
  {
    "mcpServers": {
      "vapi": {
        "command": "python",
        "args": ["C:/Users/Contr/vapi-pebble-prototype/vapi-mcp/server.py"],
        "env": {
          "VAPI_BRIDGE_URL": "http://localhost:8080",
          "VAPI_DB_PATH": "bridge/vapi_store.db",
          "VAPI_ROOT": "C:/Users/Contr/vapi-pebble-prototype"
        }
      }
    }
  }

Tools (10 total):
  vapi_protocol_state      Complete live protocol state — first call every session
  vapi_separation_ratio    Live ratio with history, gap analysis, fresh-run option
  vapi_separation_analysis Phase 137A/B analysis: --balance-corpus + --session-type
  vapi_run_calibration     Launch terminal calibration for any player + battery
  vapi_agent_fleet         All 16 agents, epistemic consensus, ioSwarm status
  vapi_sync_memory         Auto-generate MEMORY.md from live data
  vapi_tournament_preflight Run all P0 conditions atomically
  vapi_phase_context       Full context for any phase before implementing it
  vapi_what_if             VAPI-native W1/W2 analysis framework
  vapi_autoresearch_seed   Generate grounded hypothesis for next autoresearch cycle
"""

import asyncio
import json
import os
import sys
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

BRIDGE_URL   = os.environ.get("VAPI_BRIDGE_URL", "http://localhost:8080")
DB_PATH      = os.environ.get("VAPI_DB_PATH", "bridge/vapi_store.db")
PROJECT_ROOT = Path(os.environ.get("VAPI_ROOT", "."))

# ============================================================
# CLAUDE.md Live Parser — autonomous sync, never stale
# ============================================================
# CLAUDE.md is updated atomically every phase as part of the standard
# phase implementation workflow. By parsing it here with mtime-based
# caching, BOTH servers automatically reflect the current phase state
# without any manual sync step. Cost: one stat() call per tool invocation.

import re as _re

_CLAUDE_CACHE: dict = {"mtime": 0.0, "state": {}}

def _parse_claude_md() -> dict:
    """
    Parse CLAUDE.md and return current protocol state. Cached by file mtime —
    re-parsed automatically whenever CLAUDE.md changes (i.e., after every phase).
    Falls back to last known state on read error; never raises.
    """
    claude_path = PROJECT_ROOT / "CLAUDE.md"
    try:
        mtime = claude_path.stat().st_mtime
    except OSError:
        return _CLAUDE_CACHE.get("state", {})

    if mtime <= _CLAUDE_CACHE["mtime"] and _CLAUDE_CACHE["state"]:
        return _CLAUDE_CACHE["state"]

    try:
        text = claude_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return _CLAUDE_CACHE.get("state", {})

    s: dict = {}

    # Current phase: "Current phase: Phase 207 — COMPLETE (...)"
    m = _re.search(r"Current phase:\s*Phase\s*(\d+)", text)
    s["phase_num"] = m.group(1) if m else "207"
    s["phase"] = f"{s['phase_num']} COMPLETE"

    # Test counts: "Bridge: 2252 passing. Contract: 482. SDK: 448. Hardware: 37. E2E: 14."
    m = _re.search(r"Bridge:\s*(\d+)\s*passing", text)
    s["bridge"] = int(m.group(1)) if m else 2252
    m = _re.search(r"Contract:\s*(\d+)", text)
    s["hardhat"] = int(m.group(1)) if m else 482
    m = _re.search(r"SDK:\s*(\d+)", text)
    s["sdk"] = int(m.group(1)) if m else 448
    m = _re.search(r"Hardware:\s*(\d+)", text)
    s["hardware"] = int(m.group(1)) if m else 37
    m = _re.search(r"E2E:\s*(\d+)", text)
    s["e2e"] = int(m.group(1)) if m else 14
    s["total_ci"] = s["bridge"] + s["hardhat"] + s["sdk"]

    # Contracts: "43 contracts ALL LIVE on testnet"
    m = _re.search(r"(\d+)\s+contracts\s+ALL\s+LIVE", text)
    s["contracts_live"] = int(m.group(1)) if m else 43

    # Agent count: largest M in "agents N→M" transitions
    arrows = _re.findall(r"agents\s+(\d+)→(\d+)", text)
    if arrows:
        s["agents"] = max(int(pair[1]) for pair in arrows)
    else:
        agent_refs = _re.findall(r"agent\s+#(\d+)", text)
        s["agents"] = max((int(n) for n in agent_refs), default=36)

    # L4 thresholds
    m = _re.search(r"L4 anomaly threshold:\s*\*\*([0-9.]+)\*\*", text)
    s["l4_anomaly"] = float(m.group(1)) if m else 7.009
    m = _re.search(r"L4 continuity threshold:\s*\*\*([0-9.]+)\*\*", text)
    s["l4_continuity"] = float(m.group(1)) if m else 5.367

    # Recent phases: "Phase NNN — COMPLETE (desc...)"
    recent: dict = {}
    for pm in _re.finditer(r"Phase\s+(\d+)\s*[—-]\s*COMPLETE\s*\(([^)]{5,})", text):
        pn = pm.group(1)
        if pn not in recent:
            recent[pn] = pm.group(2).split(";")[0].strip()[:120]
    sorted_p = sorted(recent.keys(), key=lambda x: int(x), reverse=True)[:10]
    s["recent_phases"] = {p: recent[p] for p in sorted_p}

    # Separation ratio state
    m = _re.search(r"tremor_resting[^:]*:\s*\*\*([0-9.]+)\*\*[^N]*N=(\d+)", text)
    s["tremor_resting_ratio"] = float(m.group(1)) if m else 1.177
    s["tremor_resting_n"]     = int(m.group(2))    if m else 27

    m = _re.search(r"Separation ratio:\s*\*\*([0-9.]+)\*\*[^)]*diagonal\+LOO[^)]*N=(\d+)", text)
    s["touchpad_corners_ratio"] = float(m.group(1)) if m else 0.728
    s["touchpad_corners_n"]     = int(m.group(2))   if m else 35

    # Wallet
    m = _re.search(r"Active wallet[^`]*`(0x[0-9a-fA-F]{40})`", text)
    s["wallet"] = m.group(1) if m else "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"

    _CLAUDE_CACHE["mtime"] = mtime
    _CLAUDE_CACHE["state"] = s
    return s

# ============================================================
# MCP Protocol (stdio transport — no external dependency)
# ============================================================

def mcp_response(id_, result):
    return json.dumps({"jsonrpc": "2.0", "id": id_, "result": result})

def mcp_error(id_, code, message):
    return json.dumps({"jsonrpc": "2.0", "id": id_,
                       "error": {"code": code, "message": message}})

def write(msg: str):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

# ============================================================
# Tool Registry
# ============================================================

TOOLS = {}

def tool(name: str, description: str, schema: dict):
    def decorator(fn):
        TOOLS[name] = {"fn": fn, "description": description, "schema": schema}
        return fn
    return decorator

# ============================================================
# Bridge HTTP helper
# ============================================================

async def bridge_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{BRIDGE_URL}{path}")
        resp.raise_for_status()
        return resp.json()

async def bridge_post(path: str, body: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BRIDGE_URL}{path}", json=body or {})
        resp.raise_for_status()
        return resp.json()

# ============================================================
# SQLite helper
# ============================================================

def db_query(sql: str, params=()) -> list:
    db = PROJECT_ROOT / DB_PATH
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()

# ============================================================
# TOOL IMPLEMENTATIONS
# ============================================================

# --- PROTOCOL STATE ---

@tool(
    name="vapi_protocol_state",
    description=(
        "Returns the complete live VAPI protocol state: current phase, test counts, "
        "separation ratio, L4 thresholds, agent fleet, contract addresses, TGE gate "
        "conditions, and infrastructure-complete features awaiting activation. "
        "Call this first in every VAPI session to ground Claude Code in current reality."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_protocol_state(**_):
    # Parse CLAUDE.md for current state — auto-refreshes when file changes (every phase)
    s = _parse_claude_md()
    state = {
        "phase": s.get("phase", "207 COMPLETE"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "test_counts": {
            "bridge":   s.get("bridge",   2252),
            "sdk":      s.get("sdk",       448),
            "hardhat":  s.get("hardhat",   482),
            "hardware": s.get("hardware",   37),
            "e2e":      s.get("e2e",        14),
            "total_ci": s.get("total_ci", 3182),
        },
        "separation_ratio": {},
        "l4_thresholds": {},
        "tge_gate": {},
        "agent_fleet": {},
        "contracts": {},
        "recent_phases": s.get("recent_phases", {}),
    }

    # Live bridge endpoints
    try:
        maturity = await bridge_get("/agent/protocol-maturity")
        state["pmi"] = maturity
    except Exception as e:
        state["pmi"] = {"error": str(e), "note": "bridge may be offline"}

    try:
        readiness = await bridge_get("/agent/tournament-readiness")
        state["tournament_readiness"] = readiness
    except Exception as e:
        state["tournament_readiness"] = {"error": str(e)}

    try:
        l4 = await bridge_get("/agent/l4-calibration-status")
        state["l4_thresholds"] = l4
    except Exception as e:
        state["l4_thresholds"] = {
            "current": {
                "anomaly": 7.009, "continuity": 5.367,
                "n_sessions": 74, "feature_dim": 12,
                "stale": True, "note": "live_dim=13 vs calib_dim=12"
            },
            "candidate_n127": {
                "anomaly": 6.613, "continuity": 5.143,
                "n_sessions": 127, "feature_dim": 13,
                "status": "NOT YET APPLIED — pending threshold_calibrator.py run"
            },
            "note": "bridge offline — using CLAUDE.md values"
        }

    # Separation ratio from DB (most recent snapshot)
    ratio_rows = db_query(
        "SELECT pooled_ratio, bt_strat_ratio, n_sessions, n_players, tournament_ready, created_at "
        "FROM separation_ratio_snapshots ORDER BY created_at DESC LIMIT 1"
    )
    if ratio_rows:
        r = ratio_rows[0]
        state["separation_ratio"] = {
            **r,
            "target": 1.0,
            "gap": round(1.0 - r["pooled_ratio"], 4),
            "status": "TOURNAMENT BLOCKER" if r["pooled_ratio"] < 1.0 else "CLEARED",
            "source": "live_db",
        }
    else:
        _s = _parse_claude_md()
        _tr = _s.get("tremor_resting_ratio", 1.177)
        _tc = _s.get("touchpad_corners_ratio", 0.728)
        state["separation_ratio"] = {
            "tremor_resting_ratio": _tr,
            "tremor_resting_n":     _s.get("tremor_resting_n", 27),
            "touchpad_corners_ratio": _tc,
            "touchpad_corners_n":   _s.get("touchpad_corners_n", 35),
            "touchpad_corners_phase143_best": 1.261,
            "all_pairs_p0_ok": False,
            "p1vp3_blocker": 0.032,
            "target": 1.0,
            "status": "ABOVE_1.0 but all_pairs_p0_ok FAILS" if _tr >= 1.0 else "TOURNAMENT BLOCKER",
            "note": "Parsed from CLAUDE.md — auto-updates every phase. No live DB snapshot.",
            "source": "claude_md_live",
        }

    tr_ratio = s.get("tremor_resting_ratio", 1.177)
    tr_n     = s.get("tremor_resting_n", 27)
    tc_ratio = s.get("touchpad_corners_ratio", 0.728)
    tc_n     = s.get("touchpad_corners_n", 35)
    state["tge_gate"] = {
        "separation_ratio_gt_1": tr_ratio >= 1.0 or tc_ratio >= 1.0,
        "note": (
            f"tremor_resting={tr_ratio} (N={tr_n}) — ABOVE 1.0 but all_pairs_p0_ok FAILS (P1vP3=0.032). "
            f"touchpad_corners={tc_ratio} (N={tc_n}) — BLOCKER. "
            "touchpad_corners Phase 143 best: 1.261 (N=11, diagonal+LOO, ALL pairs above 1.0). "
            "State read from CLAUDE.md — auto-updates every phase."
        ),
        "all_pairs_p0_ok": False,
        "n100_live_adjudications": False,
        "vhp_demonstrated_testnet": True,
        "smart_contract_audit": False,
        "non_negotiable": True,
        "auto_activate_on_breakthrough": "False PERMANENT — hardcoded in TournamentActivationChainAgent",
        "epistemic_threshold": "0.65 (Phase 147, hardened from 0.60); triage_prereq_required=True",
        "staged_graduation": "Phase 207 COMPLETE — P0 gate: staged_graduation_enabled + preflight_pass + non_convergence_clear",
        "wif_039": "CorpusRatioRegressionGuard OPEN — Phase 208 candidate",
    }

    state["contracts"] = {
        "total_live": s.get("contracts_live", 43),
        "network": "IoTeX Testnet 4690",
        "key_addresses": {
            "AdjudicationRegistry":    "0x44CF981f46a52ADE56476Ce894255954a7776fb4",
            "VAPIDualPrimitiveGate":   "0xd7b1465Aad8F815C67b24681c9c022CED24FB876",
            "VAPISwarmOperatorGate":   "0x969c0F1EFb28504a95Acf14331A59FBCb2944F98",
            "CeremonyAuditRegistry":   "0xb9164E6d74Dde1508df2a39b01d3702ACC8230C2",
            "SeparationRatioRegistry": "0xB39CeE732cf91c93539Bd064D9426642a095a026",
            "VHPReenrollmentBadge":    "0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C",
            "GateAttestationAnchor":   "0xA39d00D3FF8C579840Fa02C01Adf06162630a449",
            "ZK_ceremony_beacon":      "IoTeX block #41723255"
        },
        "wallet": s.get("wallet", "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"),
    }

    state["agent_fleet"] = {
        "total": s.get("agents", 36),
        "note": f"Fleet size read from CLAUDE.md (auto-synced). Bridge offline — live agent status unavailable.",
        "key_agents": {
            "16": "TournamentActivationChainAgent (auto_activate=False PERMANENT)",
            "19": "ControllerHardwareIntelligenceAgent (multi_controller_enabled=False)",
            "20": "EnrollmentAutoGuidanceAgent (1h poll, fires enrollment_complete)",
            "21": "FleetConsensusSnapshotAgent (PoFC hash)",
            "26": "ProtocolMaturityScoringAgent (maturity_score 0.0–1.0)",
            "29": "ReEnrollmentAttestationAgent (reauth_attestation_enabled=True)",
            "32": "BiometricStationarityOracleAgent (biometric_stationarity_enabled=False)",
            "35": "CorpusDataCuratorAgent (7-task data coherence)",
            "36": "FleetSignalCoherenceAgent (fleet_coherence_enabled=True DEFAULT)",
        },
        "dry_run": True,
        "ioswarm": "emulator_only (ioswarm_enabled=True in bridge/.env, 5-node seed=109/110)",
        "staged_graduation": "StagedDryRunGraduationAgent LIVE (Phase 207); staged_graduation_enabled=False",
    }

    return state


# --- SEPARATION RATIO ---

@tool(
    name="vapi_separation_ratio",
    description=(
        "Returns the current inter-person biometric separation ratio with full "
        "historical snapshots, battery-stratified breakdown, gap analysis, and "
        "Phase 137A/B findings. The single most important metric in VAPI — "
        "tournament launch gates on ratio > 1.0 across ALL player pairs. "
        "Optionally triggers a fresh full-corpus analysis run."
    ),
    schema={
        "type": "object",
        "properties": {
            "run_fresh_analysis": {
                "type": "boolean",
                "description": "If true, runs analyze_interperson_separation.py and returns results"
            },
            "battery_stratified": {
                "type": "boolean",
                "description": "If true, includes battery-stratified note"
            }
        },
        "required": []
    }
)
async def vapi_separation_ratio(run_fresh_analysis=False, battery_stratified=True, **_):
    result = {}

    # Historical snapshots from DB
    snapshots = db_query(
        "SELECT pooled_ratio, bt_strat_ratio, n_sessions, n_players, "
        "tournament_ready, created_at "
        "FROM separation_ratio_snapshots ORDER BY created_at DESC LIMIT 10"
    )
    result["snapshots"] = snapshots
    result["current_pooled"] = snapshots[0]["pooled_ratio"] if snapshots else 0.417
    result["target"] = 1.0
    result["gap"] = round(1.0 - result["current_pooled"], 4)
    result["status"] = "TOURNAMENT BLOCKER" if result["current_pooled"] < 1.0 else "CLEARED"

    result["phase_findings"] = {
        "143_CURRENT_BEST": {
            "ratio": 1.261,
            "method": "diagonal covariance (N/p=1.375<3.0, Phase 142 auto-fallback) + proper LOO (Phase 143)",
            "classification": "63.6% (7/11)",
            "pairs": {"P1vP2": 2.868, "P1vP3": 3.276, "P2vP3": 2.243},
            "intra": {"P1": 2.963, "P2": 1.976, "P3": 1.711},
            "note": "ALL pairs above 1.0; N=11 thin but honest estimate"
        },
        "138_P4_ELIMINATED": {
            "ratio": 1.552,
            "note": "SUPERSEDED — full Tikhonov covariance inflated; P1vP3=0.127 was noise. P4 confirmed=P3.",
            "action": "P4 terminal_cal sessions moved to terminal_cal_P3/; 3-player corpus now clean"
        },
        "140_probe_comparison": {
            "corners": 1.552, "freeform": 1.270, "swipes": 1.032,
            "classification": {"corners": "63.6%", "freeform": "63.6%", "swipes": "45.5%"},
            "note": "All probe types above 1.0 tournament gate"
        },
        "137A_wif007_confirmed": {
            "balanced_ratio": 1.611, "n_per_player": 3,
            "note": "P1's 53 sessions bias global covariance; balanced reveals true separability"
        },
        "full_corpus_pooled": {
            "ratio": 0.417, "n": 127, "players": "4 (pre-merge, 2026-03-29)",
            "status": "STALE — superseded by Phase 143; free-form gameplay plateau (WIF-009)"
        },
        "next_action": (
            "Capture >=10 touchpad_corners sessions per player (current P1=3, P2=4, P3=4). "
            "Run: python scripts/terminal_calibration_runner.py --player P1 --battery touchpad_corners"
        )
    }

    if battery_stratified:
        result["battery_note"] = (
            "Free-form gameplay reaches ~0.4 plateau (WIF-009). "
            "touchpad_corners: 1.261 (Phase 143 proper LOO, N=11, diagonal cov). "
            "All 3 probe types above 1.0 (Phase 140 comparison). "
            "Run --session-type touchpad_corners for structured analysis."
        )

    if run_fresh_analysis:
        try:
            proc = subprocess.run(
                [sys.executable,
                 str(PROJECT_ROOT / "scripts" / "analyze_interperson_separation.py")],
                capture_output=True, text=True, timeout=360,
                cwd=str(PROJECT_ROOT)
            )
            if proc.returncode == 0:
                # Extract the key ratio lines from output
                output_lines = proc.stdout.strip().split("\n")
                result["fresh_analysis_stdout"] = "\n".join(output_lines[-20:])
                result["fresh_analysis_status"] = "ok"
            else:
                result["fresh_analysis_error"] = proc.stderr[-500:]
        except subprocess.TimeoutExpired:
            result["fresh_analysis_error"] = "timeout (>360s) — run manually in terminal"
        except Exception as e:
            result["fresh_analysis_error"] = str(e)

    return result


# --- SEPARATION ANALYSIS (Phase 137A/B) ---

@tool(
    name="vapi_separation_analysis",
    description=(
        "Runs analyze_interperson_separation.py with Phase 137A/B flags: "
        "--session-type (touchpad_corners, touchpad_freeform, etc.) and "
        "--balance-corpus (WIF-007 imbalance correction). "
        "Returns a command to run in terminal (does not execute long-running analysis). "
        "Key insight: touchpad_corners alone gives ratio=1.469 (>1.0 gate). "
        "Balanced corpus gives ratio=1.611 (P1/P3/P4 cluster is real WIF-010 blocker)."
    ),
    schema={
        "type": "object",
        "properties": {
            "session_type": {
                "type": "string",
                "description": "Filter to session type before computing ratio",
                "enum": [
                    "touchpad_corners", "touchpad_freeform", "touchpad_swipes",
                    "trigger_rhythm", "button_sequence", "resting_baseline", "gameplay"
                ]
            },
            "balance_corpus": {
                "type": "boolean",
                "description": "Subsample each player to min(N_per_player) sessions (WIF-007 fix)"
            },
            "output_suffix": {
                "type": "string",
                "description": "Output file suffix (e.g. '-touchpad' produces interperson-separation-analysis-touchpad.md)"
            }
        },
        "required": []
    }
)
async def vapi_separation_analysis(session_type=None, balance_corpus=False,
                                    output_suffix="", **_):
    cmd_parts = [
        "python scripts/analyze_interperson_separation.py"
    ]
    if session_type:
        cmd_parts.append(f"--session-type {session_type}")
    if balance_corpus:
        cmd_parts.append("--balance-corpus")
    if output_suffix:
        cmd_parts.append(f"--output-suffix {output_suffix}")

    cmd = " ".join(cmd_parts)

    known_results = {
        "touchpad_corners_phase143": {
            "ratio": 1.261,
            "n": 11,
            "players": "P1=3, P2=4, P3=4 (3-player clean corpus, P4 eliminated)",
            "method": "diagonal covariance + proper LOO (Phase 143 honest estimate)",
            "classification": "63.6% (7/11)",
            "pairs": {"P1vP2": 2.868, "P1vP3": 3.276, "P2vP3": 2.243},
            "status": "ABOVE 1.0 — tournament gate cleared for this probe type",
            "caveat": "N=11 thin; need >=10/player for robust tournament defense"
        },
        "touchpad_probe_comparison": {
            "corners": {"ratio": 1.552, "classification": "63.6%"},
            "freeform": {"ratio": 1.270, "classification": "63.6%"},
            "swipes": {"ratio": 1.032, "classification": "45.5%"},
            "note": "Phase 140 result — all above 1.0; corners strongest"
        },
        "full_corpus_balanced": {
            "ratio": 1.611,
            "n_per_player": 3,
            "n_total": 12,
            "status": "WIF-007 confirmed: P1's 53 sessions bias covariance",
            "caveat": "n=3/player is too small for robust estimate; n>=10 needed"
        },
        "full_corpus_pooled": {
            "ratio": 0.417,
            "n": 127,
            "players": "4 (pre-P4-merge, 2026-03-29)",
            "status": "STALE — superseded by Phase 143; free-form plateau (WIF-009)"
        }
    }

    return {
        "command_to_run": cmd,
        "note": "Analysis takes <30s for terminal-cal sessions (Phase 139 fast-path). Run in terminal.",
        "known_results": known_results,
        "corpus_state": (
            "P4 ELIMINATED (Phase 138): P4 confirmed=P3 mislabeled; terminal_cal_P4/ merged into P3. "
            "3-player clean corpus: P1=53 sessions, P2=34, P3=33 (inc. 3 former P4 sessions)."
        ),
        "w1_risk": (
            "N=11 touchpad_corners is thin for tournament defense. "
            "Need >=10/player (current: P1=3, P2=4, P3=4) before publishing ratio to stakeholders."
        ),
        "w2_opportunity": (
            "ACIM agent #18 cross-validates calibration invariants independently every 15min. "
            "Hook ratio snapshot writes into ACIM self-test suite for live drift detection."
        )
    }


# --- CALIBRATION RUNNER ---

@tool(
    name="vapi_run_calibration",
    description=(
        "Returns the command to run a terminal calibration session for a specific "
        "player and battery type. Does NOT auto-execute (calibration is interactive, "
        "requires DualShock Edge connected via USB-C). "
        "separation_focused battery is fastest path to ratio > 1.0 (touchpad + bilateral). "
        "touchpad_corners is highest-leverage for P1/P3/P4 cluster separation (WIF-010)."
    ),
    schema={
        "type": "object",
        "properties": {
            "player": {
                "type": "string",
                "description": "Player ID: P1, P2, P3, or P4",
                "enum": ["P1", "P2", "P3", "P4"]
            },
            "battery": {
                "type": "string",
                "description": "Battery type to run",
                "enum": [
                    "touchpad", "touchpad_corners", "tremor", "trigger",
                    "button_sequence", "natural_grip", "resting_baseline",
                    "spectral_accel", "stick_sweeps", "trigger_rhythm",
                    "full", "separation_focused"
                ]
            }
        },
        "required": ["player", "battery"]
    }
)
async def vapi_run_calibration(player: str, battery: str, **_):
    cmd = (
        f"python scripts/terminal_calibration_runner.py "
        f"--player {player} --battery {battery}"
    )

    priority_note = ""
    if battery == "touchpad_corners":
        priority_note = (
            "HIGH PRIORITY: touchpad_corners closest to tournament defense. "
            "Need >=10 sessions per player. Current: P1=3, P2=4, P3=4. P4 ELIMINATED (=P3)."
        )
    elif battery == "separation_focused":
        priority_note = "Runs touchpad_corners + bilateral + resting_baseline in sequence."

    return {
        "command": cmd,
        "player": player,
        "battery": battery,
        "priority_note": priority_note,
        "instruction": (
            "Run this command in a terminal with the DualShock Edge connected via USB-C. "
            "After completion, check updated ratio with vapi_separation_ratio "
            "or run vapi_separation_analysis with session_type='touchpad_corners'."
        ),
        "sessions_needed": {
            "P1": ">=10 touchpad_corners (current: 3)",
            "P2": ">=10 touchpad_corners (current: 4 — closest to target)",
            "P3": ">=10 touchpad_corners (current: 4, inc. 3 former P4 sessions)",
            "P4": "ELIMINATED — confirmed same person as P3 (Phase 138 merge)"
        }
    }


# --- AGENT FLEET STATUS ---

@tool(
    name="vapi_agent_fleet",
    description=(
        "Returns live status of all 16 VAPI autonomous agents: name, phase introduced, "
        "active/inactive status, dry_run state, and ioSwarm emulation status. "
        "Includes recent adjudication log entries and epistemic consensus scores."
    ),
    schema={
        "type": "object",
        "properties": {
            "include_recent_rulings": {
                "type": "boolean",
                "description": "Include last 5 agent_rulings entries (dry_run=True by default)"
            }
        },
        "required": []
    }
)
async def vapi_agent_fleet(include_recent_rulings=True, **_):
    result = {}

    try:
        fleet = await bridge_get("/agent/edge-ai-profile")
        result["fleet"] = fleet
    except Exception:
        _s = _parse_claude_md()
        result["fleet"] = {
            "total_agents": _s.get("agents", 36),
            "agents": {
                "1-20":  "Core fleet phases 1-156 (all live, dry_run=True)",
                "21":    "FleetConsensusSnapshotAgent (PoFC hash, Phase 157)",
                "26":    "ProtocolMaturityScoringAgent (maturity_score, Phase 177)",
                "29":    "ReEnrollmentAttestationAgent (HMAC attestation, Phase 185)",
                "32":    "BiometricStationarityOracleAgent (drift classifier, Phase 188)",
                "35":    "CorpusDataCuratorAgent (7-task coherence, Phase 192)",
                "36":    "FleetSignalCoherenceAgent (CONTRADICTION+ORPHAN+INVERSION, Phase 193)",
                "207":   "StagedDryRunGraduationAgent (GRADUATION_SEQUENCE, Phase 207)",
            },
            "note": f"bridge offline — agent count ({_s.get('agents', 36)}) read from CLAUDE.md"
        }

    result["epistemic_consensus"] = {
        "weights_ioswarm_off": {
            "ClassJDetector": 0.40,
            "DivergenceTriageAgent": 0.40,
            "AgentSupervisor": 0.20
        },
        "weights_ioswarm_on": {
            "ClassJDetector": 0.35,
            "DivergenceTriageAgent": 0.35,
            "AgentSupervisor": 0.15,
            "IoSwarm": 0.15
        },
        "threshold": 0.65,
        "triage_prereq_required": True,
        "w1_status": (
            "CLOSED (Phase 147): threshold hardened 0.60→0.65; triage_prereq_required=True. "
            "ClassJ+Supervisor=0.60 no longer reaches threshold — held at HOLD until triage confirms."
        )
    }

    result["ioswarm"] = {
        "status": "emulator_only",
        "live_nodes": 0,
        "coordinators": {
            "consensus":    "ioswarm_enabled=False",
            "renewal":      "ioswarm_renewal_enabled=False",
            "adjudication": "ioswarm_adjudication_enabled=False",
            "mint":         "ioswarm_vhp_mint_enabled=False"
        },
        "quorum_config": {
            "BLOCK_QUORUM": 0.67,
            "MINT_QUORUM": 0.80,
            "note": "fail-CLOSED on VHP mint; fail-open on adjudication"
        }
    }

    if include_recent_rulings:
        # Correct table: agent_rulings (not adjudication_log)
        rulings = db_query(
            "SELECT device_id, verdict, confidence, dry_run, created_at "
            "FROM agent_rulings ORDER BY created_at DESC LIMIT 5"
        )
        result["recent_rulings"] = rulings
        result["ruling_count"] = db_query(
            "SELECT COUNT(*) as n FROM agent_rulings"
        )

    return result


# --- MEMORY SYNC ---

@tool(
    name="vapi_sync_memory",
    description=(
        "Reads live protocol state from the bridge and DB, then generates an updated "
        "MEMORY.md file reflecting current reality. Use instead of manually updating "
        "MEMORY.md — it pulls from live data, not stale remembered values. "
        "Includes Phase 137A/B findings and WIF-010 cluster blocker."
    ),
    schema={
        "type": "object",
        "properties": {
            "write_file": {
                "type": "boolean",
                "description": "If true, writes MEMORY.md. If false, returns content only."
            }
        },
        "required": []
    }
)
async def vapi_sync_memory(write_file=True, **_):
    # All values from CLAUDE.md — auto-refreshes every phase
    s = _parse_claude_md()
    state = await vapi_protocol_state()
    ratio_data = state.get("separation_ratio", {})
    now = datetime.utcnow().strftime("%Y-%m-%d")

    phase_num  = s.get("phase_num", "207")
    bridge     = s.get("bridge",    2252)
    sdk        = s.get("sdk",        448)
    hardhat    = s.get("hardhat",    482)
    hardware   = s.get("hardware",    37)
    e2e        = s.get("e2e",         14)
    total_ci   = s.get("total_ci",  3182)
    agents     = s.get("agents",      36)
    contracts  = s.get("contracts_live", 43)
    l4_anom    = s.get("l4_anomaly",  7.009)
    l4_cont    = s.get("l4_continuity", 5.367)
    tr_ratio   = s.get("tremor_resting_ratio",  1.177)
    tr_n       = s.get("tremor_resting_n",         27)
    tc_ratio   = s.get("touchpad_corners_ratio", 0.728)
    tc_n       = s.get("touchpad_corners_n",       35)

    # Prefer live DB ratio if available
    live_pooled = ratio_data.get("tremor_resting_ratio", tr_ratio)

    content = f"""# VAPI System State — Auto-synced {now}
# Generated by VAPI MCP Server (vapi-mcp/server.py) — source: CLAUDE.md (live parse)
# CLAUDE.md is updated every phase — this file reflects current state automatically.

## Current Phase: {phase_num} COMPLETE

## Test Counts (Phase {phase_num})
Bridge: {bridge:,} | SDK: {sdk} | Hardhat: {hardhat} | Hardware: {hardware} | E2E: {e2e} | Total CI: {total_ci:,}

## Separation Ratio (from CLAUDE.md)
tremor_resting: {tr_ratio} (N={tr_n}) — ABOVE 1.0 but all_pairs_p0_ok FAILS (P1vP3=0.032)
touchpad_corners: {tc_ratio} (N={tc_n}) — BLOCKER (ratio declined 1.261→{tc_ratio} with N growth)
touchpad_corners Phase 143 BEST: 1.261 (diagonal+LOO, N=11, ALL pairs above 1.0) — thin but defensible
P4 ELIMINATED (Phase 138): confirmed=P3 mislabeled; clean 3-player corpus
Target: > 1.0 ALL pairs AND all_pairs_p0_ok=True
WIF-039: CorpusRatioRegressionGuard OPEN — Phase 208 candidate

## L4 Thresholds
anomaly={l4_anom}, continuity={l4_cont} (N=74, 12-feat — stale: live_dim=13 vs calib_dim=12)
Candidate N=127: anomaly=6.613, continuity=5.143 (NOT YET APPLIED)

## TGE Gate (ALL NON-NEGOTIABLE)
separation_ratio > 1.0: CONDITIONAL — tremor_resting={tr_ratio} ABOVE 1.0; all_pairs_p0_ok FAILS
all_pairs_p0_ok: FAILS (P1vP3=0.032 < intra threshold)
N>=100 live adjudications: BLOCKED (dry_run=True; Phase 207 StagedDryRunGraduationGate COMPLETE)
VHP demonstrated: LIVE (testnet)
Contract security audit: NOT DONE
auto_activate_on_breakthrough: False PERMANENT
epistemic_threshold: 0.65 (Phase 147), triage_prereq_required=True

## Agent Fleet: {agents} ACTIVE
All agents live; dry_run=True across fleet
36: FleetSignalCoherenceAgent (fleet_coherence_enabled=True; 3 rules: CONTRADICTION/ORPHAN/INVERSION)
35: CorpusDataCuratorAgent (7-task data coherence + Provenance DAG)
26: ProtocolMaturityScoringAgent (9-component maturity_score 0.0–1.0)
21: FleetConsensusSnapshotAgent (PoFC hash — WIF-013)
16: TournamentActivationChainAgent (auto_activate=False PERMANENT)
207: StagedDryRunGraduationAgent (GRADUATION_SEQUENCE; staged_graduation_enabled=False)
ioSwarm: emulator_only (ioswarm_enabled=True bridge/.env; 5-node seed=109/110; 0 live nodes)

## Contracts: {contracts} ALL LIVE (IoTeX Testnet 4690)
AdjudicationRegistry:    0x44CF981f46a52ADE56476Ce894255954a7776fb4
VAPIDualPrimitiveGate:   0xd7b1465Aad8F815C67b24681c9c022CED24FB876
VAPISwarmOperatorGate:   0x969c0F1EFb28504a95Acf14331A59FBCb2944F98
CeremonyAuditRegistry:   0xb9164E6d74Dde1508df2a39b01d3702ACC8230C2
SeparationRatioRegistry: 0xB39CeE732cf91c93539Bd064D9426642a095a026
VHPReenrollmentBadge:    0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C

## Frozen Invariants
PoAC: 228B | SHA-256(raw[:164]) | Poseidon(8), C3, nPublic=5
Ceremony: IoTeX block #41723255
Thresholds: {l4_anom}/{l4_cont} (stable EMA only on NOMINAL sessions)
"""

    if write_file:
        memory_path = PROJECT_ROOT / "VAPI-WORKFLOW.v2" / "VAPI_MEMORY.md"
        # Prepend to existing VAPI_MEMORY.md rather than overwriting — preserves history
        existing = ""
        try:
            existing = memory_path.read_text(encoding="utf-8")
        except Exception:
            pass
        # Only write the state block; preserve everything below the first --- separator
        separator = "\n---\n"
        idx = existing.find(separator)
        tail = existing[idx:] if idx != -1 else ""
        memory_path.write_text(content + tail, encoding="utf-8")
        return {"written": True, "path": str(memory_path), "phase": phase_num,
                "bridge": bridge, "sdk": sdk, "agents": agents, "contracts": contracts}

    return {"content": content, "phase": phase_num, "bridge": bridge, "sdk": sdk}


# --- PREFLIGHT GATE ---

@tool(
    name="vapi_tournament_preflight",
    description=(
        "Runs the tournament pre-launch validation suite (Phase 127). "
        "Checks all P0 conditions atomically: separation_ratio>=1.0, L4 staleness cleared, "
        "gate_passed, cert_valid, audit_valid. Returns blocking conditions and advisory warnings. "
        "This is the canonical due diligence gate before any tournament announcement."
    ),
    schema={"type": "object", "properties": {}, "required": []}
)
async def vapi_tournament_preflight(**_):
    try:
        result = await bridge_post("/agent/run-tournament-preflight")
        return result
    except Exception:
        ratio_rows = db_query(
            "SELECT pooled_ratio FROM separation_ratio_snapshots "
            "ORDER BY created_at DESC LIMIT 1"
        )
        current_ratio = ratio_rows[0]["pooled_ratio"] if ratio_rows else 0.417

        return {
            "preflight_passed": False,
            "p0_conditions": {
                "separation_ratio_gte_1": {
                    "passed": current_ratio >= 1.0,
                    "current_pooled": current_ratio,
                    "current_touchpad_corners": 1.261,
                    "required": 1.0,
                    "blocking": False,
                    "note": "touchpad_corners=1.261 (Phase 143 proper LOO, N=11) — above gate but thin; need >=10/player"
                },
                "l4_calibration_fresh": {
                    "passed": False,
                    "note": "stale: 12-feat calibration on 13-feat live space (N=127 candidate not applied)",
                    "blocking": True
                },
                "dry_run_cleared": {
                    "passed": False,
                    "note": "dry_run=True — Phase 97 3-condition gate not passed",
                    "blocking": True
                }
            },
            "p1_advisory": {
                "epoch_window": "not activated (epoch_window_enabled=False)",
                "ioswarm_live_nodes": "0 registered (emulator_only)",
                "dual_gate": "deployed, not activated",
                "wif_010": "P1/P3/P4 cluster blocker — ratio is P2-outlier-driven"
            },
            "blocking_count": 3,
            "note": "Bridge offline — evaluated from local DB state"
        }


# --- PHASE CONTEXT ---

@tool(
    name="vapi_phase_context",
    description=(
        "Returns the full context for a specific VAPI phase: what was built, "
        "what it unlocked, test deltas, W1/W2 pairs, and what it depends on. "
        "Use before implementing any new phase to ground Claude Code in prior decisions."
    ),
    schema={
        "type": "object",
        "properties": {
            "phase": {
                "type": "string",
                "description": "Phase number or ID (e.g. '129', '137A', '137B')"
            }
        },
        "required": ["phase"]
    }
)
async def vapi_phase_context(phase: str, **_):
    PHASE_REGISTRY = {
        "136": {
            "name": "DualSense Audio Passthrough Router",
            "what_built": "audio_router.py Windows Core Audio COM vtable; ensure_game_audio() in dualshock_integration",
            "test_delta": "Bridge 1716->1734 +18; SDK 233 unchanged; Hardhat 462 unchanged",
        },
        "137A": {
            "name": "Balanced Corpus Subsampling (WIF-007 closure)",
            "what_built": "_compute_balanced_ratio() + --balance-corpus argparse flag in analyze_interperson_separation.py",
            "result": "balanced_ratio=1.611 (n=3/player, 4 players, seed=42) vs pooled=0.417",
            "wif_007_confirmed": "P1's 53 sessions bias global covariance toward P1 variance structure",
            "caveat": "n=3/player is small; n>=10 needed for reliable estimate",
            "test_delta": "Bridge 1734 unchanged; SDK 233 unchanged; Hardhat 462 unchanged (script-only change)",
        },
        "137B": {
            "name": "Session-Type Filter --session-type",
            "what_built": "_detect_session_type() + MIN_SESSIONS_FOR_TYPE_FILTER=3 + session_type_filter in run_analysis()",
            "result": "touchpad_corners ratio=1.469 (N=11) — FIRST crossing of >1.0 gate",
            "classification": "63.6% (7/11) — WEAK SEPARATION",
            "cluster_structure": "P2 outlier (P1 vs P2: 1.428); P1/P3/P4 cluster (P3 vs P4: 0.074)",
            "wif_010": "All pairs must separate for tournament defense; P1 vs P3=0.143 is the bottleneck",
            "test_delta": "Bridge 1734 unchanged; SDK 233 unchanged; Hardhat 462 unchanged",
        },
        "149": {
            "name": "Calibration Staleness Fixes",
            "what_built": [
                "calibration_agent.py: _CURRENT_PHASE=148 constant + _load_separation_from_db() reads separation_ratio_snapshots",
                "_count_players_from_dirs() scans terminal_cal_P*/ dirs + _compute_progress() DB-first ratio",
                "hardware_calibration_watcher.py: default ratio 0.362→1.261 + Phase 148 docstring",
                "calibration_intelligence_agent.py: _CALIB_SYSTEM_PROMPT Phase 148 + get_separation_analysis returns ratio=1.261",
                "scripts/CALIBRATE_SETUP.ps1: Phase 109→148"
            ],
            "test_delta": "Bridge 1798→1808 +10; SDK 237 unchanged; Hardhat 462 unchanged",
        },
        "148": {
            "name": "AgentCalibrationIntegrityMonitor ACIM + VAPI MCP Server",
            "what_built": [
                "Agent #18 (ACIM) runs 16 self-tests every 15min; cross-validates each agent's calibration invariant",
                "MCP server mcp_server_enabled=False (infrastructure-first)",
                "agent_calibration_health table; GET /agent/calibration-health; Tool #105 get_agent_calibration_health",
                "mcp_server.py NEW (6 MCP resources)"
            ],
            "test_delta": "Bridge 1790→1798 +8; SDK 233→237 +4; Hardhat 462 unchanged",
        },
        "147": {
            "name": "Epistemic Threshold Hardening",
            "what_built": "epistemic_consensus_threshold 0.60→0.65; epistemic_triage_prereq_required False→True (default)",
            "w1_closed": "Phase 98 W1: ClassJ+Supervisor=0.60 no longer reaches 0.65 threshold → HOLD",
            "test_delta": "Bridge 1782→1790 +8; SDK 233 unchanged; Hardhat 462 unchanged",
        },
        "144": {
            "name": "Per-Player Enrollment Quality Report",
            "what_built": "--player-quality-report CLI flag; _compute_player_quality_scores(); ENROLLMENT_STABILITY_THRESHOLD=0.70; ENROLLMENT_MIN_PROBE_TYPES=2",
            "current_status": "P1/P2/P3 all NOT READY (stability>0.70 or single probe type)",
            "test_delta": "Bridge 1774→1782 +8",
        },
        "143": {
            "name": "Proper LOO Classification",
            "what_built": "Each test session's centroid recomputed WITHOUT that session; eliminates centroid bias",
            "result": "63.6% (7/11, proper LOO) — honest estimate; combined with Phase 142 diagonal",
            "key_metric": "ratio=1.261 (diagonal+proper LOO, Phase 143 CURRENT BEST)",
            "test_delta": "Bridge 1766→1774 +8",
        },
        "142": {
            "name": "Small-N Covariance Auto-Fallback",
            "what_built": "COV_MIN_RATIO=3.0; when N/p<3.0 auto-uses diagonal covariance",
            "diagnosis": "P1 vs P3 suppression_ratio=0.032 (97% suppression by full Tikhonov) — was noise artifact",
            "test_delta": "Bridge 1758→1766 +8",
        },
        "141": {
            "name": "Per-Pair Feature Attribution Diagnostic",
            "what_built": "_compute_pair_attribution() per-pair standardized diff + suppression_ratio",
            "key_finding": "P1 vs P3 diagonal=3.925 >> full=0.127; suppression=0.032; touchpad_entropy top discriminator",
            "test_delta": "Bridge 1750→1758 +8",
        },
        "140": {
            "name": "Multi-Probe Comparison",
            "what_built": "--probe-comparison flag; runs corners/freeform/swipes with Phase 139 fast-path",
            "results": "corners=1.552/63.6%, freeform=1.270/63.6%, swipes=1.032/45.5% — ALL above 1.0",
            "test_delta": "Bridge 1742→1750 +8",
        },
        "139": {
            "name": "Analysis Fast-Path",
            "what_built": "_TERMINAL_CAL_ONLY_TYPES frozenset; skips 74 hw_* sessions when session_type_filter in terminal-cal-only set",
            "perf": "Reduces 120s+ to <30s per probe analysis",
            "test_delta": "Bridge 1734→1742 +8",
        },
        "138": {
            "name": "P4→P3 Corpus Merge + Clean 3-Player",
            "what_built": "P4 confirmed=P3 mislabeled; terminal_cal_P4/ (3 sessions) moved to terminal_cal_P3/",
            "result": "touchpad_corners clean 3-player: ratio=1.552 (full Tikhonov, biased) — superseded by Phase 143",
            "key_finding": "P4 ELIMINATED; remaining blocker is N=11 thin, not player identity",
            "test_delta": "Bridge 1734 unchanged; corpus restructure only",
        },
        "127": {
            "name": "Tournament Pre-Launch Validation Suite",
            "what_built": "POST /agent/run-tournament-preflight atomic gate, tournament_preflight_log",
            "w1": "commit-activation proceeds without preflight P0 gate — closed",
            "test_delta": "+9B +4S",
        },
        "129": {
            "name": "Full Covariance + Separation Breakthrough Monitor",
            "what_built": [
                "Tikhonov-regularized covariance (lambda=0.01*trace(Sigma)/n_features)",
                "SeparationRatioMonitorAgent #15 (300s poll, 2-snapshot confirmation, one-shot guard)"
            ],
            "w1": "Single outlier false breakthrough — 2-consecutive guard",
            "test_delta": "+9B +4S",
        },
        "130": {
            "name": "VAPISwarmOperatorGate + Tournament Hardening",
            "what_built": "VAPISwarmOperatorGate.sol (min 3 distinct stakers, 1.5x cap)",
            "w1_wif001": "ioSwarm node-pool homogeneity collapses quorum guarantee",
            "wallet_warning": "~0.35 IOTX — needs top-up before deploy",
            "test_delta": "+8B +4S +6H",
        },
        "135": {
            "name": "TournamentActivationChainAgent",
            "what_built": "Agent #16 — receives breakthrough event, notifies operator, does NOT auto-activate",
            "permanent_constraint": "auto_activate_on_breakthrough=False — hardcoded compile-time constant, NEVER remove",
            "test_delta": "Bridge 1708->1716 +8; SDK 229->233 +4",
        },
    }

    key = str(phase)
    if key in PHASE_REGISTRY:
        return {"phase": key, **PHASE_REGISTRY[key]}

    return {
        "phase": key,
        "note": f"Phase {key} not in MCP registry. Check CLAUDE.md or inspect codebase.",
        "available_phases": list(PHASE_REGISTRY.keys())
    }


# --- WHAT_IF GENERATOR ---

@tool(
    name="vapi_what_if",
    description=(
        "Generates a VAPI-native WHAT_IF analysis for a proposed change or next phase. "
        "W1: grounded failure mode (physically/cryptographically/economically rooted). "
        "W2: genuinely novel opportunity exclusive to VAPI. "
        "Returns the framework structure with current invariants loaded."
    ),
    schema={
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The change, phase, or decision to analyze"
            },
            "context": {
                "type": "string",
                "description": "Additional context (current state, what has been tried)"
            }
        },
        "required": ["topic"]
    }
)
async def vapi_what_if(topic: str, context: str = "", **_):
    # Load recent what_if corpus entries for context
    corpus_path = PROJECT_ROOT / "vapi-autoresearch" / "what_if_corpus"
    recent_wifs = []
    if corpus_path.exists():
        for wif_file in sorted(corpus_path.glob("wif_*.md"))[-3:]:
            try:
                content = wif_file.read_text(encoding="utf-8")[:400]
                recent_wifs.append({"file": wif_file.name, "preview": content})
            except Exception:
                pass

    return {
        "topic": topic,
        "context": context,
        "live_state": {
            "pooled_ratio": 0.417,
            "touchpad_corners_ratio": 1.469,
            "balanced_ratio": 1.611,
            "tge_gate": "BLOCKED (3 conditions)",
            "cluster_problem": "P1/P3/P4 inter-dist 0.074-0.143 (WIF-010)",
        },
        "framework": {
            "W1": {
                "label": "Grounded failure mode",
                "requirements": [
                    "Physically, cryptographically, OR economically rooted",
                    "Specific mechanism — not a generic 'server crash'",
                    "Impact on separation_ratio, VHP, ioSwarm, or TGE gate stated",
                    "Mitigation available with phase reference"
                ]
            },
            "W2": {
                "label": "Novel opportunity exclusive to VAPI",
                "requirements": [
                    "Not replicable without 228B PoAC + PITL stack",
                    "Concrete mechanism described",
                    "Phase candidate number specified",
                    "Connection to separation ratio or tournament launch stated"
                ]
            }
        },
        "invariants_to_preserve": [
            "228 bytes wire format",
            "SHA-256(raw[:164]) chain hash",
            "7.009/5.367 L4 thresholds (stable EMA on NOMINAL only)",
            "Poseidon(8), C3, nPublic=5",
            "ratio > 1.0 ALL pairs before TGE",
            "GSR_ENABLED=false until N>=30 per player",
            "dry_run=True default",
            "auto_activate_on_breakthrough=False PERMANENT",
            "Epistemic W1: threshold=0.60 reachable by ClassJ (0.40+0.20)",
            "ioswarm_enabled=false until live nodes registered",
        ],
        "recent_corpus": recent_wifs,
        "instruction": "Generate W1/W2 pair using this framework, grounded in live_state above"
    }


# --- AUTORESEARCH SEED ---

@tool(
    name="vapi_autoresearch_seed",
    description=(
        "Generates a grounded hypothesis for the next vapi-autoresearch cycle. "
        "Reads live protocol state, recent experiment log, and what_if corpus, "
        "then returns a structured seed that addresses the current highest-priority gap. "
        "Closes the 'stale hypothesis' problem: autoresearch now grounds proposals "
        "in live separation ratio, cluster structure, and blocking conditions. "
        "Designed to be called at the START of each autoresearch cycle."
    ),
    schema={
        "type": "object",
        "properties": {
            "priority": {
                "type": "string",
                "description": "Override the auto-detected priority for this cycle",
                "enum": [
                    "separation_ratio_pathways",
                    "wif010_cluster_resolution",
                    "l4_recalibration",
                    "phase_invariant_hardening",
                    "what_if_corpus_depth",
                    "class_k_definition"
                ]
            },
            "cycle_num": {
                "type": "integer",
                "description": "Current cycle number (for log context)"
            }
        },
        "required": []
    }
)
async def vapi_autoresearch_seed(priority: str = "", cycle_num: int = 0, **_):
    _s = _parse_claude_md()  # auto-synced from CLAUDE.md
    # Load autoresearch experiment log
    log_path = PROJECT_ROOT / "vapi-autoresearch" / "experiments" / "log.jsonl"
    recent_log = []
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8").strip().split("\n")
            for line in lines[-5:]:
                if line.strip():
                    recent_log.append(json.loads(line))
        except Exception:
            pass

    # Read current separation ratio from DB
    ratio_rows = db_query(
        "SELECT pooled_ratio, n_sessions, created_at FROM separation_ratio_snapshots "
        "ORDER BY created_at DESC LIMIT 1"
    )
    current_ratio = ratio_rows[0]["pooled_ratio"] if ratio_rows else 0.417

    # Auto-detect priority from recent history
    PRIORITIES = [
        "separation_ratio_pathways",     # P0: all_pairs_p0_ok FAILS (P1vP3=0.032); per-probe ensemble gate
        "phase_invariant_hardening",     # P1: WIF-039 CorpusRatioRegressionGuard (Phase 208)
        "l4_recalibration",              # P2: N=127 thresholds (6.613/5.143) not applied (live_dim=13 vs 12)
        "what_if_corpus_depth",          # P3: WIF-040 physiological pair similarity; WIF corpus at 39 entries
        "class_k_definition",            # P4: GSR spoofer (Class K) still undefined
        "acim_integration",              # P5: ACIM self-tests for separation ratio drift detection
    ]
    recent_priorities = [e.get("priority", "") for e in recent_log]
    auto_priority = priority
    if not auto_priority:
        for p in PRIORITIES:
            if p not in recent_priorities:
                auto_priority = p
                break
        if not auto_priority:
            auto_priority = PRIORITIES[0]

    # Count what_if corpus
    corpus_path = PROJECT_ROOT / "vapi-autoresearch" / "what_if_corpus"
    wif_count = len(list(corpus_path.glob("wif_*.md"))) if corpus_path.exists() else 0

    return {
        "cycle": cycle_num or len(recent_log) + 1,
        "auto_priority": auto_priority,
        "live_state": {
            "pooled_ratio_db": current_ratio,
            "tremor_resting_ratio": _s.get("tremor_resting_ratio", 1.177),
            "tremor_resting_n":     _s.get("tremor_resting_n", 27),
            "tremor_resting_p1vp3": 0.032,
            "touchpad_corners_ratio": _s.get("touchpad_corners_ratio", 0.728),
            "touchpad_corners_n":   _s.get("touchpad_corners_n", 35),
            "touchpad_corners_phase143_best": 1.261,
            "touchpad_corners_pairs_phase143": {"P1vP2": 2.868, "P1vP3": 3.276, "P2vP3": 2.243},
            "all_pairs_p0_ok": False,
            "p4_status": "ELIMINATED (Phase 138) — confirmed=P3 mislabeled; clean 3-player corpus",
            "corpus_tremor_resting": f"P1=9/P2=6/P3=12 — N=27; P1vP3=0.032 structural blocker",
            "tge_blockers": ["all_pairs_p0_ok=False(P1vP3)", "dry_run=True", "l4_stale", "no_audit", "wif039_open"],
            "l4_stale": "12-feat calibration on 13-feat live (N=127 candidate: 6.613/5.143)",
            "phase": _s.get("phase", "207 COMPLETE"),
            "agents": _s.get("agents", 36),
            "contracts": _s.get("contracts_live", 43),
            "epistemic": "threshold=0.65 (Phase 147 hardened); triage_prereq_required=True",
            "staged_graduation": "Phase 207 COMPLETE; staged_graduation_enabled=False pending all_pairs_p0_ok",
        },
        "seed_hypothesis": _seed_hypothesis(auto_priority),
        "what_if_corpus_size": wif_count,
        "recent_cycle_priorities": recent_priorities[-3:],
        "instructions": (
            "Use this seed to generate the improvement proposal for vapi_autoresearch.py. "
            "The seed.w1_grounded + seed.w2_novel are starting points — ground them further "
            "using live_state above before writing to what_if_corpus/."
        )
    }


def _seed_hypothesis(priority: str) -> dict:
    """Return a grounded W1/W2 seed for the given priority."""
    SEEDS = {
        "separation_ratio_n_expansion": {
            "w1_grounded": (
                "N=11 touchpad_corners sessions is below the minimum for stable Mahalanobis "
                "estimation (N/p=1.375 with p=8 features). With only 3 sessions per player, "
                "the centroid estimate has high variance — a single outlier session could "
                "reverse the ratio below 1.0. Tournament defense requires N>=10/player."
            ),
            "w1_mitigation": "Capture >=10 touchpad_corners per player before tournament announcement",
            "w2_novel": (
                "Per-session consistency score: compute session-level Mahalanobis distance "
                "from player centroid (LOO). Flag sessions where distance > 2σ intra-player — "
                "these are candidate outliers. Auto-filter before ratio computation for robust estimate."
            ),
            "w2_phase": "Phase 150 candidate — pure analysis, no hardware required"
        },
        "acim_integration": {
            "w1_grounded": (
                "ACIM (agent #18) runs 16 self-tests every 15min but cannot detect drift "
                "in the separation ratio itself — it validates agent calibration invariants, "
                "not biometric separation. A genuine ratio degradation from new sessions "
                "would not trigger ACIM."
            ),
            "w1_mitigation": "Add separation_ratio_check to ACIM self-test suite; compare DB snapshot vs threshold",
            "w2_novel": (
                "ACIM hook for ratio anomaly detection: if newly written separation_ratio_snapshot "
                "differs from previous by >0.1, ACIM flags it as calibration integrity event "
                "and logs to agent_calibration_health. Closes monitoring gap between "
                "SeparationRatioMonitorAgent (breakthrough only) and ACIM (invariant drift)."
            ),
            "w2_phase": "Phase 150 candidate — bridge-only, ACIM extension"
        },
        "separation_ratio_pathways": {
            "w1_grounded": (
                "Free-form gameplay accumulates intra-player variance faster than "
                "inter-player distance grows (WIF-009 plateau). N=127 pooled ratio "
                "plateau at 0.417 is structural — more free-form sessions won't help."
            ),
            "w1_mitigation": "Structured probe sessions (touchpad_corners, bilateral) only",
            "w2_novel": (
                "Cross-session consistency Mahalanobis: compute the variance RATIO "
                "(inter-player / intra-session-per-player) using ONLY the most "
                "recent 3 sessions per player. This auto-balances corpus imbalance "
                "AND uses the most calibrated (latest) sessions."
            ),
            "w2_phase": "Phase 138 candidate"
        },
        "l4_recalibration": {
            "w1_grounded": (
                "N=127 thresholds (anomaly=6.613, continuity=5.143) are 5-6% tighter "
                "than current stored values (7.009/5.367). Applying N=127 thresholds "
                "increases FPR from ~2.9% to ~5.4% (moving from 3σ toward 2.7σ). "
                "Must verify that human FPR remains <5% before applying."
            ),
            "w1_mitigation": "Run threshold_calibrator.py against N=127 with explicit FPR check",
            "w2_novel": (
                "Battery-stratified threshold tracks: touchpad sessions (low tremor) "
                "warrant tighter thresholds than free-form gameplay (high tremor). "
                "Per-battery tracks are already in Phase 124-126 infrastructure."
            ),
            "w2_phase": "Phase 138 L4 recalibration — apply N=127 candidates"
        },
        "what_if_corpus_depth": {
            "w1_grounded": (
                "WIF-010 (P1/P3/P4 cluster) is not yet in the skill's WHAT_IF Corpus. "
                "Future sessions that generate hypotheses about ratio>1.0 will miss "
                "the structural cluster problem and propose solutions that don't apply."
            ),
            "w1_mitigation": "Add WIF-010 to vapi.md WHAT_IF Corpus section",
            "w2_novel": (
                "Autoresearch cycle grounded by MCP: vapi_autoresearch_seed() reads "
                "live ratio + cluster state at the start of each cycle, ensuring "
                "hypotheses are grounded in current reality, not stale MEMORY.md."
            ),
            "w2_phase": "Current — MCP integration active (Phase 137A+"
        },
        "phase_invariant_hardening": {
            "w1_grounded": (
                "Phase 98 W1: epistemic threshold=0.60 reachable by ClassJ alone "
                "(0.40+0.20=0.60). In adversarial deployment with a ClassJ bypass, "
                "any session with ClassJ=HIGH and Supervisor=HIGH gets BLOCK regardless "
                "of Triage=CLEAR. threshold=0.65 closes this single-agent gate path."
            ),
            "w1_mitigation": (
                "Set epistemic_recommended_threshold=0.65 AND epistemic_triage_prereq_required=True "
                "in Phase 105 config before live mode activation."
            ),
            "w2_novel": (
                "Per-device adaptive threshold: devices with high consecutive_clean streak "
                "get threshold reduced (more tolerant of anomalies); new devices start at "
                "0.65. Closes false-positive risk for established players."
            ),
            "w2_phase": "Phase 138 candidate"
        },
        "class_k_definition": {
            "w1_grounded": (
                "Class K (GSR spoofer: synthetic EDA generator attached to grip pad) "
                "is an open gap. With GSR_ENABLED=False and N=0 calibration sessions, "
                "a synthetic EDA signal that mimics human sympathetic arousal pattern "
                "would pass L7 unchallenged. This is the primary remaining attack vector "
                "once hardware ships."
            ),
            "w1_mitigation": "Define Class K in SecurityReview mode; design anti-tamper challenge-response",
            "w2_novel": (
                "Hardware fingerprint as Class K gate: record the exact capacitance "
                "signature of Ag/AgCl electrode contact (impedance spectrum). "
                "Synthetic EDA generators use different electrode materials and fail "
                "impedance spectroscopy at 1kHz. Requires <=0.5 IOTX gas to anchor hash."
            ),
            "w2_phase": "Phase 141 candidate — requires GSR hardware"
        }
    }
    return SEEDS.get(priority, {
        "w1_grounded": "Unknown priority — use vapi_what_if tool with specific topic",
        "w2_novel": "Unknown priority",
        "w2_phase": "TBD"
    })


# ============================================================
# MCP Server Loop (stdio transport)
# ============================================================

async def handle(msg: dict) -> str:
    id_    = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {})

    # Notifications have no "id" — JSON-RPC 2.0 requires no response
    if "id" not in msg:
        return ""

    if method == "initialize":
        return mcp_response(id_, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "vapi-mcp", "version": f"1.1.0-phase{_parse_claude_md().get('phase_num', '207')}"},
            "capabilities": {"tools": {}}
        })

    if method == "tools/list":
        tools_list = [
            {
                "name": name,
                "description": info["description"],
                "inputSchema": info["schema"]
            }
            for name, info in TOOLS.items()
        ]
        return mcp_response(id_, {"tools": tools_list})

    if method == "tools/call":
        tool_name = params.get("name")
        args      = params.get("arguments", {})

        if tool_name not in TOOLS:
            return mcp_error(id_, -32601, f"Unknown tool: {tool_name}")

        try:
            result = await TOOLS[tool_name]["fn"](**args)
            return mcp_response(id_, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
            })
        except Exception as e:
            return mcp_error(id_, -32603, f"Tool error: {str(e)}")

    return mcp_error(id_, -32601, f"Unknown method: {method}")


async def main():
    # Windows ProactorEventLoop does not support connect_read_pipe on real pipe handles.
    # Use run_in_executor to read stdin line-by-line in a thread instead.
    loop = asyncio.get_event_loop()

    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            response = await handle(msg)
            if response:
                write(response)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            write(json.dumps({"jsonrpc": "2.0", "id": None,
                              "error": {"code": -32700, "message": str(e)}}))


if __name__ == "__main__":
    asyncio.run(main())
