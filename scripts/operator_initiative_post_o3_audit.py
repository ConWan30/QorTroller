"""Operator Initiative POST-O3 ceremony verification audit.

Runs AFTER scripts/parallel_o3_act_anchor.py fires (operator-runtime
Day 15 ceremony). Verifies all post-ceremony assertions hold. Mirrors
the scripts/zkba_post_ceremony_audit.py D-TRACK2-G6 pattern:

  Section 1 — Local activation_log integrity:
    For each of the 3 agents (anchor_sentry / guardian / curator):
      (a) Most recent operator_agent_activation_log row exists
      (b) to_phase = "O3_ACTING" (FROZEN per Cedar VALID_PHASES)
      (c) bundle_path filename matches *_o3_acting_v1.json
      (d) operational_tx_hash + governance_tx_hash both populated
          (dual-anchor per INV-OPERATOR-AGENT-001)
      (e) Recomputed bundle Merkle == canonical pin (from
          _CANONICAL_BUNDLE_MERKLES in mythos_variants.py)

  Section 2 — On-chain scopeRoot verification (--include-chain-reads):
    For each agent: AgentScope.getScopeRoot(agent_id) returns the
    expected O3 ACTING Merkle. Pure eth_call; no tx; no gas; bypasses
    CHAIN_SUBMISSION_PAUSED per chain.py:_send_tx wrapper. NEVER fires
    a write tx — wallet-free even under --include-chain-reads.

  Section 3 — Mythos OpInit audit cross-reference:
    Re-runs the existing mythos_operator_initiative_audit() and asserts
    0 findings. Catches any new drift the ceremony might have introduced
    in the bundle files between pre-ceremony state and now.

  Section 4 — FSCA contradiction sweep:
    Queries fleet_coherence_log for any post-ceremony contradictions
    that fired in the last hour. Surfaces them as part of the audit
    record (informational; FSCA's own rules drive remediation).

Exit codes:
  0  All sections PASS; ceremony succeeded
  1  Section 1 FAIL (activation_log integrity)
  2  Section 2 FAIL (on-chain divergence)
  3  Section 3 FAIL (Mythos OpInit surfaced findings)
  4  Section 4 contradictions present (informational; exit non-zero
     to surface but the operator may decide it's expected)
  5  Script error

Operator usage:

    # Wallet-free local-only audit (safe; no RPC):
    python scripts/operator_initiative_post_o3_audit.py

    # Full audit including on-chain reads (still wallet-free; eth_call only):
    python scripts/operator_initiative_post_o3_audit.py --include-chain-reads

    # Machine-readable:
    python scripts/operator_initiative_post_o3_audit.py --json

This is also exposed as a Mythos variant (mythos_post_o3_ceremony_audit)
per operator directive 2026-05-15 — Mythos invokes this same function in
the post_ceremony cadence tier. Findings persist to mythos_finding_log
+ surface through the existing FSCA MYTHOS_FROZEN_REGION_DRIFT rule.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "bridge") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "bridge"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


# Canonical O3 ACTING bundle Merkle pins (pre-authored 2026-05-10 commit
# 3cb59f46; these are the values parallel_o3_act_anchor.py will write to
# chain when the operator fires the ceremony on Day 15).
_EXPECTED_O3_ACTING_MERKLES: Dict[str, str] = {
    "anchor_sentry":
        "0xc0bcdee8576e83f6b80e8c5ac89093cf08f153033037176cd03fc34fcedfd878",
    "guardian":
        "0x6f0fc77cc1dacaf3f79aeb0f27dd8c7b3d88e95b236f0806ad3588a06bb82225",
    "curator":
        "0xd9d760c8b7b1088f2edd165fbfa6441abcb3bc3f921e8ba75a3339c0825fec24",
}

_EXPECTED_BUNDLE_FILES: Dict[str, str] = {
    "anchor_sentry": "anchor_sentry_o3_acting_v1.json",
    "guardian":      "guardian_o3_acting_v1.json",
    "curator":       "curator_o3_acting_v1.json",
}


def _norm_hex(s) -> str:
    """Normalize bytes-or-str hex input to lowercase hex string sans 0x prefix.

    Defends against chain.get_agent_scope_root() returning raw bytes32
    (which it does per its ``-> bytes`` signature) vs Section 1 paths
    that pass hex strings. Both inputs converge to the same canonical
    form for equality comparison."""
    if s is None:
        return ""
    if isinstance(s, (bytes, bytearray)):
        s = s.hex()
    elif not isinstance(s, str):
        s = str(s)
    s = s.strip().lower()
    return s[2:] if s.startswith("0x") else s


def _section_1_activation_log(
    *, db_path: str, cfg, repo_root: Path
) -> Dict[str, Any]:
    """Verify activation_log has the expected 3 O3 ACTING rows.

    Each agent must have a most-recent activation row with:
      - to_phase = "O3_ACTING"
      - bundle_path basename ending in *_o3_acting_v1.json
      - operational_tx_hash + governance_tx_hash both populated
      - bundle file on disk parses + Merkle matches canonical pin
    """
    section = {
        "section": "activation_log_integrity",
        "per_agent": {},
        "all_pass": True,
        "error": None,
    }
    try:
        from vapi_bridge.store import Store
        from vapi_bridge.operator_initiative_advancement import (
            _AGENT_NAME_TO_ID_ATTR,
        )
        from vapi_bridge.cedar_parser import bundle_merkle_root
        store = Store(db_path=db_path)

        for agent_canonical, attr in _AGENT_NAME_TO_ID_ATTR.items():
            agent_q9 = getattr(cfg, attr, "") or ""
            entry: Dict[str, Any] = {
                "agent_q9_short": (agent_q9[:18] + "...") if agent_q9 else "",
                "checks": {},
                "pass": True,
            }
            latest = store.get_latest_operator_agent_activation(agent_q9)
            if latest is None:
                entry["pass"] = False
                entry["checks"]["activation_row_exists"] = False
                entry["checks"]["reason"] = (
                    "No activation_log row found for this agent — ceremony "
                    "did NOT fire OR DB does not reflect production state."
                )
                section["per_agent"][agent_canonical] = entry
                section["all_pass"] = False
                continue
            entry["checks"]["activation_row_exists"] = True

            to_phase = (latest.get("to_phase") or "").strip()
            # to_phase strings from cedar bundles use "O3_ACTING" (matches
            # Cedar VALID_PHASES); legacy "O3_ACT" also accepted.
            to_phase_ok = to_phase in ("O3_ACTING", "O3_ACT")
            entry["checks"]["to_phase"] = to_phase
            entry["checks"]["to_phase_ok"] = to_phase_ok
            if not to_phase_ok:
                entry["pass"] = False

            bundle_path = str(latest.get("bundle_path") or "")
            bundle_basename = bundle_path.replace("\\", "/").rsplit("/", 1)[-1]
            expected_bundle = _EXPECTED_BUNDLE_FILES[agent_canonical]
            bundle_ok = bundle_basename == expected_bundle
            entry["checks"]["bundle_basename"] = bundle_basename
            entry["checks"]["bundle_basename_ok"] = bundle_ok
            if not bundle_ok:
                entry["pass"] = False

            op_tx = (latest.get("operational_tx_hash") or "").strip()
            gov_tx = (latest.get("governance_tx_hash") or "").strip()
            dual_anchor_ok = bool(op_tx) and bool(gov_tx)
            entry["checks"]["dual_anchor_ok"] = dual_anchor_ok
            entry["checks"]["operational_tx_hash"] = op_tx
            entry["checks"]["governance_tx_hash"] = gov_tx
            if not dual_anchor_ok:
                entry["pass"] = False

            # Bundle Merkle recompute vs canonical pin
            bpath = repo_root / "bridge" / "vapi_bridge" / "cedar_bundles" / expected_bundle
            if bpath.is_file():
                try:
                    payload = json.loads(bpath.read_text(encoding="utf-8"))
                    live_merkle = bundle_merkle_root(payload).hex()
                    expected = _EXPECTED_O3_ACTING_MERKLES[agent_canonical]
                    merkle_ok = _norm_hex(live_merkle) == _norm_hex(expected)
                    entry["checks"]["merkle_live"] = "0x" + live_merkle
                    entry["checks"]["merkle_expected"] = expected
                    entry["checks"]["merkle_ok"] = merkle_ok
                    if not merkle_ok:
                        entry["pass"] = False
                except Exception as exc:  # noqa: BLE001
                    entry["checks"]["merkle_ok"] = False
                    entry["checks"]["merkle_error"] = str(exc)
                    entry["pass"] = False
            else:
                entry["checks"]["bundle_on_disk"] = False
                entry["pass"] = False

            section["per_agent"][agent_canonical] = entry
            if not entry["pass"]:
                section["all_pass"] = False

        return section
    except Exception as exc:  # noqa: BLE001
        section["error"] = f"{type(exc).__name__}: {exc}"
        section["all_pass"] = False
        return section


async def _section_2_chain_scope_root(
    *, cfg
) -> Dict[str, Any]:
    """For each agent, eth_call AgentScope.getScopeRoot(agentId) and
    compare to the expected O3 ACTING Merkle.

    Wallet-free: read-only eth_call only; no tx submission. Uses the
    bridge's existing chain wrapper.
    """
    section = {
        "section": "on_chain_scope_root",
        "per_agent": {},
        "all_pass": True,
        "error": None,
    }
    try:
        from vapi_bridge.chain import ChainClient
        from vapi_bridge.operator_initiative_advancement import (
            _AGENT_NAME_TO_ID_ATTR,
        )
        chain = ChainClient(cfg=cfg)

        for agent_canonical, attr in _AGENT_NAME_TO_ID_ATTR.items():
            agent_q9 = getattr(cfg, attr, "") or ""
            entry: Dict[str, Any] = {
                "agent_q9_short": agent_q9[:18] + "...",
                "pass": True,
                "expected": _EXPECTED_O3_ACTING_MERKLES[agent_canonical],
            }
            try:
                # chain.get_agent_scope_root is async; returns BYTES (per its
                # -> bytes signature). Normalize to hex string for both
                # storage in entry["live"] (rendered output) AND equality
                # comparison below. Defends against bytes-vs-str TypeError.
                live_raw = await chain.get_agent_scope_root(agent_q9)
                live_hex = "0x" + live_raw.hex() if isinstance(live_raw, (bytes, bytearray)) else (live_raw or "")
                entry["live"] = live_hex
                if not live_hex or live_hex == "0x" + "00" * 32:
                    entry["pass"] = False
                    entry["error"] = "getScopeRoot returned empty"
                else:
                    ok = _norm_hex(live_hex) == _norm_hex(entry["expected"])
                    entry["match"] = ok
                    if not ok:
                        entry["pass"] = False
            except Exception as exc:  # noqa: BLE001
                entry["pass"] = False
                entry["error"] = f"{type(exc).__name__}: {exc}"
            section["per_agent"][agent_canonical] = entry
            if not entry["pass"]:
                section["all_pass"] = False

        return section
    except Exception as exc:  # noqa: BLE001
        section["error"] = f"{type(exc).__name__}: {exc}"
        section["all_pass"] = False
        return section


async def _section_3_mythos_opinit(*, repo_root: Path) -> Dict[str, Any]:
    """Re-run Mythos OpInit audit + assert 0 findings."""
    section = {
        "section": "mythos_opinit_cross_reference",
        "finding_count": 0,
        "findings_brief": [],
        "all_pass": True,
        "error": None,
    }
    try:
        from vapi_bridge.mythos_variants import (
            mythos_operator_initiative_audit,
        )
        findings = await mythos_operator_initiative_audit(repo_root=repo_root)
        section["finding_count"] = len(findings)
        section["findings_brief"] = [
            {
                "severity": f.severity,
                "description": (f.description or "")[:140],
            }
            for f in findings
        ]
        if findings:
            section["all_pass"] = False
        return section
    except Exception as exc:  # noqa: BLE001
        section["error"] = f"{type(exc).__name__}: {exc}"
        section["all_pass"] = False
        return section


def _section_4_fsca_contradictions(*, db_path: str) -> Dict[str, Any]:
    """Query fleet_coherence_log for contradictions in the last hour.
    Surface them informationally; exit code reflects presence."""
    section = {
        "section": "fsca_contradictions_last_hour",
        "rows": [],
        "contradictions_present": False,
        "error": None,
    }
    try:
        import sqlite3
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute(
                "SELECT rule_name, severity, agents_involved_json, "
                "       explanation, created_at "
                "FROM fleet_coherence_log "
                "WHERE created_at > ? "
                "ORDER BY created_at DESC LIMIT 20",
                (time.time() - 3600,),
            ).fetchall()
            section["rows"] = [
                {
                    "rule": dict(r)["rule_name"],
                    "severity": dict(r)["severity"],
                    "agents": dict(r).get("agents_involved_json", ""),
                    "explanation": (dict(r).get("explanation") or "")[:140],
                    "created_at": dict(r)["created_at"],
                }
                for r in rows
            ]
            section["contradictions_present"] = len(section["rows"]) > 0
        except Exception:  # noqa: BLE001 — table may not exist; non-fatal
            pass
        con.close()
        return section
    except Exception as exc:  # noqa: BLE001
        section["error"] = f"{type(exc).__name__}: {exc}"
        return section


async def run_audit(
    *,
    db_path: str,
    include_chain_reads: bool,
    repo_root: Path,
) -> Dict[str, Any]:
    """Run all 4 sections; returns combined audit dict. Never raises."""
    audit: Dict[str, Any] = {
        "timestamp_iso": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time())
        ),
        "db_path": db_path,
        "include_chain_reads": include_chain_reads,
        "sections": {},
        "verdict": "UNKNOWN",
        "exit_code": 5,
    }
    try:
        from vapi_bridge.config import Config
        cfg = Config()

        audit["sections"]["section_1"] = _section_1_activation_log(
            db_path=db_path, cfg=cfg, repo_root=repo_root,
        )
        if not audit["sections"]["section_1"]["all_pass"]:
            audit["verdict"] = "SECTION_1_FAIL"
            audit["exit_code"] = 1
            # Don't early-return — operator wants to see all sections
        if include_chain_reads:
            audit["sections"]["section_2"] = await _section_2_chain_scope_root(
                cfg=cfg
            )
            if not audit["sections"]["section_2"]["all_pass"]:
                if audit["exit_code"] == 5:
                    audit["verdict"] = "SECTION_2_FAIL"
                    audit["exit_code"] = 2
        audit["sections"]["section_3"] = await _section_3_mythos_opinit(
            repo_root=repo_root,
        )
        if not audit["sections"]["section_3"]["all_pass"]:
            if audit["exit_code"] == 5:
                audit["verdict"] = "SECTION_3_FAIL"
                audit["exit_code"] = 3
        audit["sections"]["section_4"] = _section_4_fsca_contradictions(
            db_path=db_path,
        )
        if audit["sections"]["section_4"]["contradictions_present"]:
            if audit["exit_code"] == 5:
                audit["verdict"] = "SECTION_4_CONTRADICTIONS"
                audit["exit_code"] = 4

        # If all sections pass:
        if audit["exit_code"] == 5:
            audit["verdict"] = "PASS"
            audit["exit_code"] = 0
        return audit
    except Exception as exc:  # noqa: BLE001
        audit["verdict"] = "ERROR"
        audit["exit_code"] = 5
        audit["error"] = f"{type(exc).__name__}: {exc}"
        return audit


def _format_human(audit: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("Operator Initiative POST-O3 Ceremony Verification Audit")
    lines.append(f"  timestamp:           {audit['timestamp_iso']}")
    lines.append(f"  db_path:             {audit['db_path']}")
    lines.append(f"  include_chain_reads: {audit['include_chain_reads']}")
    lines.append("=" * 72)
    s = audit.get("sections", {})
    if "section_1" in s:
        s1 = s["section_1"]
        lines.append(f"Section 1 — activation_log_integrity   {'PASS' if s1['all_pass'] else 'FAIL'}")
        for agent, e in s1.get("per_agent", {}).items():
            mark = "✓" if e["pass"] else "✗"
            lines.append(f"  {mark} {agent:<14s} {e.get('agent_q9_short', '')}")
            for k, v in e.get("checks", {}).items():
                lines.append(f"      {k}: {v}")
        lines.append("")
    if "section_2" in s:
        s2 = s["section_2"]
        lines.append(f"Section 2 — on_chain_scope_root         {'PASS' if s2['all_pass'] else 'FAIL'}")
        for agent, e in s2.get("per_agent", {}).items():
            mark = "✓" if e["pass"] else "✗"
            lines.append(f"  {mark} {agent:<14s} expected={e['expected'][:18]}... live={(e.get('live') or '')[:18]}...")
            if "error" in e:
                lines.append(f"      error: {e['error']}")
        lines.append("")
    if "section_3" in s:
        s3 = s["section_3"]
        lines.append(f"Section 3 — mythos_opinit_cross_reference {'PASS' if s3['all_pass'] else 'FAIL'}  ({s3.get('finding_count', 0)} findings)")
        for f in s3.get("findings_brief", [])[:5]:
            lines.append(f"  [{f['severity']}] {f['description']}")
        lines.append("")
    if "section_4" in s:
        s4 = s["section_4"]
        lines.append(f"Section 4 — fsca_contradictions_last_hour  {'CLEAN' if not s4['contradictions_present'] else 'CONTRADICTIONS_PRESENT'}")
        for r in s4.get("rows", [])[:5]:
            lines.append(f"  [{r['severity']}] {r['rule']}: {r['explanation'][:80]}")
        lines.append("")
    lines.append(f"VERDICT:  {audit.get('verdict', 'UNKNOWN')}")
    lines.append(f"EXIT:     {audit.get('exit_code', 5)}")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator Initiative POST-O3 ceremony verification audit."
    )
    # 2026-05-19 path-discovery fix: default to canonical production DB
    # path (~/.vapi/bridge.db or $DB_PATH), NOT the stale sandbox at
    # bridge/vapi_store.db. See bridge/vapi_bridge/db_path_resolver.py.
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "bridge"))
        from vapi_bridge.db_path_resolver import resolve_canonical_db_path
        _default_db = resolve_canonical_db_path()
    except Exception:
        _default_db = str(PROJECT_ROOT / "bridge" / "vapi_store.db")
    parser.add_argument("--db", default=_default_db)
    parser.add_argument(
        "--include-chain-reads", action="store_true",
        help="Also eth_call AgentScope.getScopeRoot per agent (read-only; "
             "wallet-free; ~6 RPC calls)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    audit = asyncio.run(run_audit(
        db_path=args.db,
        include_chain_reads=args.include_chain_reads,
        repo_root=PROJECT_ROOT,
    ))
    if args.json:
        print(json.dumps(audit, indent=2, default=str))
    else:
        print(_format_human(audit))

    return int(audit.get("exit_code", 5))


if __name__ == "__main__":
    sys.exit(main())
