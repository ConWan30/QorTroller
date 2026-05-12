"""Phase O3-ZKBA-TRACK1 Track 2 post-ceremony audit — wallet-free observability.

Resolves Operator Decision Matrix D-TRACK2-G6 (per-agent live authority
verification) by producing a READ-ONLY audit report that cross-checks:

  1. Local v2 bundle Merkle roots recomputed from JSON vs. EXPECTED_MERKLES
     locks pinned in scripts/parallel_zkba_anchor.py
  2. (Optional via --include-chain-reads) On-chain AgentScope.getScopeRoot()
     state vs. expected v2 Merkle — eth_call only; no tx; no gas; no wallet
     impact; bypasses CHAIN_SUBMISSION_PAUSED per chain.py:4237
  3. Cedar v2 policy lane authority matrix — per-agent, per-action, per-lane
     permit/forbid evaluation. Verifies cross-fleet skill separation
     invariant (CFSS) at the v2 layer: each ZKBA lane is exclusive to
     exactly one agent.

D-TRACK2-G7 (Curator review readiness verification) is NOT covered by this
script — that requires LIVE bridge process + Curator agent observation
over time. §5 of the report surfaces the exact operator commands needed
to perform G7 verification on a running bridge.

WALLET-FREE CONTRACT:

  - No transaction submission paths invoked
  - eth_call reads only (when --include-chain-reads passed)
  - No env-var changes
  - No file mutation outside the audit report output
  - CHAIN_SUBMISSION_PAUSED state untouched

Run:

    # Local-only audit (no RPC; safe for CI):
    python scripts/zkba_post_ceremony_audit.py

    # Full audit including on-chain reads (requires bridge/.env):
    python scripts/zkba_post_ceremony_audit.py --include-chain-reads

    # Emit machine-readable JSON instead of human report:
    python scripts/zkba_post_ceremony_audit.py --json

Exit codes:
  0  All checks passed (local-only and/or chain-read variant)
  1  Local Merkle mismatch (v2 bundle file modified post-C6 ship?)
  2  On-chain root mismatch (chain state diverged from local Merkle)
  3  Cedar policy CFSS violation detected
  4  Configuration / RPC error (bridge unreachable, etc.)

Author: VAPI Architect (post-ceremony audit; commit ships 2026-05-12 per
Operator Decision Matrix D-TRACK2-G6 wallet-free observability work)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Constants — mirror scripts/parallel_zkba_anchor.py
# ---------------------------------------------------------------------------

AGENT_ANCHOR_ORDER = ("anchor_sentry", "guardian", "curator")

AGENT_BUNDLE_FILES = {
    "anchor_sentry": "anchor_sentry_o2_suggest_v2.json",
    "guardian":      "guardian_o2_suggest_v2.json",
    "curator":       "curator_o2_suggest_v2.json",
}

EXPECTED_MERKLES = {
    "anchor_sentry": "0x39e8b65f0a87671fc003c28c3f28a7afd7fae41b6c3505d1ddb3d05ff3db1f23",
    "guardian":      "0x6818a9ad49dab7898925e530526c50fcce515a889c3666f1434e6470c660a9a0",
    "curator":       "0x0ade0c92cf2aa0c5675701861ed535683f0dfd15873424a9838d402b60a80b3d",
}

# Cedar v2 lane authority matrix per C6 ship (commit 755fac33). Each row
# is one (agent, action, resource) tuple with its expected effect.
# CFSS invariant: each ZKBA lane permits exactly one agent + forbids the
# other two.
EXPECTED_LANE_MATRIX = [
    # (agent_id, action, resource_prefix, expected_effect)
    # Sentry owns zk_artifacts/
    ("anchor_sentry", "tool:zk-artifact-anchor",   "draft://zk_artifacts/*",   "permit"),
    ("anchor_sentry", "skill:read",                "lane://zk_artifacts/**",   "permit"),
    ("anchor_sentry", "tool:zk-audit-trail",       None,                       "forbid"),
    ("anchor_sentry", "tool:zk-marketplace-listing", None,                     "forbid"),
    # Guardian owns zk_verifications/
    ("guardian",      "tool:zk-audit-trail",       "draft://zk_verifications/*", "permit"),
    ("guardian",      "skill:read",                "lane://zk_verifications/**", "permit"),
    ("guardian",      "tool:zk-artifact-anchor",   None,                       "forbid"),
    ("guardian",      "tool:zk-marketplace-listing", None,                     "forbid"),
    # Curator owns zk_listings/
    ("curator",       "tool:zk-marketplace-listing", "draft://zk_listings/*",  "permit"),
    ("curator",       "skill:read",                "lane://zk_listings/**",    "permit"),
    ("curator",       "tool:zk-artifact-anchor",   None,                       "forbid"),
    ("curator",       "tool:zk-audit-trail",       None,                       "forbid"),
]


# ---------------------------------------------------------------------------
# Section 1 — Local Merkle recompute + lock verification
# ---------------------------------------------------------------------------

def section_1_local_merkles(bundle_dir: Path) -> tuple[bool, list, dict]:
    """Recompute Merkle root from each v2 bundle file + compare to lock.

    Returns (ok, findings, computed_dict)."""
    sys.path.insert(0, str(PROJECT_ROOT / "bridge"))
    from vapi_bridge.cedar_parser import parse_bundle  # type: ignore

    findings: list = []
    computed: dict = {}
    ok = True

    for agent_id in AGENT_ANCHOR_ORDER:
        fname = AGENT_BUNDLE_FILES[agent_id]
        path = bundle_dir / fname
        if not path.exists():
            findings.append({
                "agent": agent_id,
                "status": "MISSING",
                "detail": f"v2 bundle file not found: {path}",
            })
            ok = False
            continue
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            parsed = parse_bundle(raw)
            merkle = parsed.merkle_root
            merkle_hex = (
                "0x" + merkle.hex()
                if isinstance(merkle, (bytes, bytearray))
                else str(merkle)
            )
        except Exception as exc:
            findings.append({
                "agent": agent_id,
                "status": "PARSE_ERROR",
                "detail": str(exc)[:120],
            })
            ok = False
            continue

        computed[agent_id] = merkle_hex
        expected = EXPECTED_MERKLES[agent_id]
        match = merkle_hex.lower() == expected.lower()
        if not match:
            ok = False
        findings.append({
            "agent": agent_id,
            "status": "MATCH" if match else "DRIFT",
            "expected": expected,
            "computed": merkle_hex,
        })

    return ok, findings, computed


# ---------------------------------------------------------------------------
# Section 2 — On-chain AgentScope.getScopeRoot() reads (optional)
# ---------------------------------------------------------------------------

async def section_2_chain_reads(computed_merkles: dict) -> tuple[bool, list]:
    """For each agent, call AgentScope.getScopeRoot() via eth_call + compare
    against computed local Merkle.

    Returns (ok, findings). Requires bridge/.env configured + RPC reachable.
    """
    findings: list = []
    ok = True

    try:
        from bridge.vapi_bridge.config import Config
        from bridge.vapi_bridge.chain import ChainClient
        cfg = Config()
        chain = ChainClient(cfg)
    except Exception as exc:
        return False, [{
            "status": "CONFIG_ERROR",
            "detail": f"failed to construct ChainClient: {exc}",
        }]

    # Map canonical name → Q9 agent_id_hex via cfg
    agent_id_map = {
        "anchor_sentry": getattr(cfg, "operator_agent_anchor_sentry_id", ""),
        "guardian":      getattr(cfg, "operator_agent_guardian_id", ""),
        "curator":       getattr(cfg, "operator_agent_curator_id", ""),
    }

    for agent_id in AGENT_ANCHOR_ORDER:
        q9_hex = agent_id_map[agent_id]
        if not q9_hex:
            findings.append({
                "agent": agent_id,
                "status": "AGENT_ID_MISSING",
                "detail": f"cfg.operator_agent_{agent_id}_id is empty",
            })
            ok = False
            continue
        try:
            on_chain_bytes = await chain.get_agent_scope_root(q9_hex)
            on_chain_hex = "0x" + on_chain_bytes.hex()
        except Exception as exc:
            findings.append({
                "agent": agent_id,
                "status": "RPC_ERROR",
                "detail": str(exc)[:120],
            })
            ok = False
            continue

        local_merkle = computed_merkles.get(agent_id, "").lower()
        match = on_chain_hex.lower() == local_merkle
        if not match:
            ok = False
        findings.append({
            "agent": agent_id,
            "q9_hex_short": q9_hex[:18] + "...",
            "status": "MATCH" if match else "DRIFT",
            "expected_local_merkle": local_merkle,
            "on_chain_scope_root": on_chain_hex,
        })

    return ok, findings


# ---------------------------------------------------------------------------
# Section 3 — Cedar v2 lane authority matrix
# ---------------------------------------------------------------------------

def _bundle_policy_effect(bundle: dict, action: str, resource: str | None) -> str:
    """Walk bundle.policies for the (action, resource) tuple. Return one of
    'permit' / 'forbid' / 'absent'. Cedar semantics: forbid wins; if no
    explicit forbid AND a permit matches, it's permit; if no permit
    matches, default is denial — we report 'absent' so the audit can
    distinguish "no policy says anything" from "explicit forbid".

    When `resource is None` (wildcard-resource match), ANY policy on the
    action counts: forbid wins, otherwise permit if any permit exists.
    """
    found_permit = False
    for p in bundle.get("policies", []):
        if p.get("action") != action:
            continue
        eff = p.get("effect")
        if resource is None:
            # Wildcard resource match — both permits + forbids on the
            # action count; forbid wins immediately
            if eff == "forbid":
                return "forbid"
            if eff == "permit":
                found_permit = True
        else:
            # Exact-resource match for permit; wildcard for forbid
            if eff == "permit" and p.get("resource") == resource:
                found_permit = True
            elif eff == "forbid" and p.get("resource") in (resource, "*"):
                return "forbid"  # forbid wins
    if found_permit:
        return "permit"
    return "absent"


def section_3_lane_matrix(bundle_dir: Path) -> tuple[bool, list]:
    """For each row of EXPECTED_LANE_MATRIX, evaluate the corresponding
    bundle's policy + compare effect to expected. Returns (ok, findings).
    """
    findings: list = []
    ok = True

    # Pre-load all 3 bundles
    bundles: dict = {}
    for agent_id in AGENT_ANCHOR_ORDER:
        path = bundle_dir / AGENT_BUNDLE_FILES[agent_id]
        try:
            with open(path, encoding="utf-8") as f:
                bundles[agent_id] = json.load(f)
        except Exception as exc:
            findings.append({
                "status": "BUNDLE_LOAD_ERROR",
                "agent": agent_id,
                "detail": str(exc)[:120],
            })
            ok = False

    if not ok:
        return ok, findings

    for agent_id, action, resource, expected_effect in EXPECTED_LANE_MATRIX:
        actual = _bundle_policy_effect(bundles[agent_id], action, resource)
        match = actual == expected_effect
        if not match:
            ok = False
        findings.append({
            "agent": agent_id,
            "action": action,
            "resource": resource or "(any)",
            "expected": expected_effect,
            "actual": actual,
            "status": "OK" if match else "CFSS_VIOLATION",
        })

    return ok, findings


# ---------------------------------------------------------------------------
# Section 5 — Operator-driven D-TRACK2-G7 commands (live bridge required)
# ---------------------------------------------------------------------------

G7_OPERATOR_COMMANDS = """
D-TRACK2-G7 — Curator Review Readiness Verification (Operator-Driven)
======================================================================

This step requires LIVE bridge process + live Curator agent observation
over time. The audit script CANNOT verify it from a single read pass;
it requires emerging behavior on a running fleet. Operator-driven.

Run on the operator's PowerShell with the bridge running:

  # 1. Verify Curator agent process is running + at O1_SHADOW (not yet O2_SUGGEST)
  curl -H "x-api-key: $env:OPERATOR_API_KEY" `
       http://localhost:8081/operator/operator-initiative-advancement

  # 2. Inspect recent Curator review activity (last 24h)
  curl -H "x-api-key: $env:OPERATOR_API_KEY" `
       "http://localhost:8081/operator/operator-agent-drafts?agent_id=curator&since_minutes=1440"

  # 3. Check Curator's marketplace-listing-review draft generator output
  python -c "
  from bridge.vapi_bridge.config import Config
  from bridge.vapi_bridge.store import Store
  s = Store(Config().db_path)
  rows = s.get_operator_agent_drafts(agent_id='curator', limit=10)
  for r in rows:
      print(r['action_name'], r['draft_uri'], r['operator_decision'])
  "

  # 4. Verify FSCA contradiction surface still clean
  curl -H "x-api-key: $env:OPERATOR_API_KEY" `
       "http://localhost:8081/operator/fsca/contradictions?severity=HIGH,CRITICAL"

  # 5. Curator readiness criterion (per VBDIP-0002 §16 G7): Curator can
  #    classify proof_weight + detect visual dishonesty + recommend
  #    quarantine WITHOUT mutating anchors or consent state.
  #    Verification: review 10+ marketplace_listing_review drafts produced
  #    by Curator over a 7-day observation window; verify
  #    operator_disagreement_reason is empty or operator_decision='accept'
  #    on >=9/10 (rejection rate < 5% per Phase O2 SUGGEST advancement gate).

Observation gates the next operator-track ladder rung (Curator O2 → O3 ACT
transition; tracked by Operator Initiative O3 watcher per Phase O1 D unified
advancement watcher).
""".strip()


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _render_human_report(
    *,
    s1: tuple[bool, list, dict],
    s2: tuple[bool, list] | None,
    s3: tuple[bool, list],
    chain_reads_requested: bool,
) -> str:
    s1_ok, s1_findings, _ = s1
    s3_ok, s3_findings = s3

    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("ZKBA Track 2 Post-Ceremony Audit (D-TRACK2-G6) — wallet-free observability")
    lines.append("=" * 78)
    lines.append("")
    lines.append("Section 1 — Local v2 Bundle Merkle Verification")
    lines.append("-" * 78)
    for f in s1_findings:
        status = f["status"]
        agent = f["agent"]
        if status == "MATCH":
            lines.append(f"  [OK]    {agent:<14s}  Merkle matches EXPECTED_MERKLES lock")
            lines.append(f"          {f['expected'][:18]}...{f['expected'][-8:]}")
        elif status == "DRIFT":
            lines.append(f"  [DRIFT] {agent:<14s}")
            lines.append(f"          expected: {f['expected']}")
            lines.append(f"          computed: {f['computed']}")
        else:
            lines.append(f"  [{status}] {agent}: {f.get('detail', '')}")
    lines.append("")
    lines.append(f"  Section 1 result: {'PASS' if s1_ok else 'FAIL'}")
    lines.append("")

    if chain_reads_requested:
        s2_ok, s2_findings = s2 or (False, [])
        lines.append("Section 2 — On-chain AgentScope.getScopeRoot() vs Local Merkle")
        lines.append("-" * 78)
        for f in s2_findings:
            status = f.get("status")
            agent = f.get("agent", "?")
            if status == "MATCH":
                lines.append(f"  [OK]    {agent:<14s}  on-chain matches local Merkle")
                lines.append(f"          agent_id  {f['q9_hex_short']}")
                lines.append(f"          on-chain  {f['on_chain_scope_root'][:18]}...{f['on_chain_scope_root'][-8:]}")
            elif status == "DRIFT":
                lines.append(f"  [DRIFT] {agent:<14s}")
                lines.append(f"          expected: {f['expected_local_merkle']}")
                lines.append(f"          on-chain: {f['on_chain_scope_root']}")
            else:
                lines.append(f"  [{status}] {agent}: {f.get('detail', '')}")
        lines.append("")
        lines.append(f"  Section 2 result: {'PASS' if s2_ok else 'FAIL'}")
        lines.append("")
    else:
        lines.append("Section 2 — On-chain reads SKIPPED")
        lines.append("-" * 78)
        lines.append("  Pass --include-chain-reads to verify AgentScope.getScopeRoot() state.")
        lines.append("  Chain reads are eth_call only; no tx; no gas; no wallet impact.")
        lines.append("")

    lines.append("Section 3 — Cedar v2 Lane Authority Matrix (CFSS)")
    lines.append("-" * 78)
    lines.append(f"  {'agent':<14s} {'action':<32s} {'resource':<32s} {'exp':<8s} {'act':<8s} status")
    for f in s3_findings:
        agent = f.get("agent", "?")
        action = f.get("action", "?")
        resource = (f.get("resource") or "(any)")
        if len(resource) > 30:
            resource = resource[:27] + "..."
        exp = f.get("expected", "?")
        act = f.get("actual", "?")
        st = f.get("status", "?")
        lines.append(f"  {agent:<14s} {action:<32s} {resource:<32s} {exp:<8s} {act:<8s} [{st}]")
    lines.append("")
    lines.append(f"  Section 3 result: {'PASS' if s3_ok else 'FAIL'}")
    lines.append("")

    lines.append("Section 4 — Overall Audit Result")
    lines.append("-" * 78)
    overall = s1_ok and s3_ok and (s2[0] if (chain_reads_requested and s2) else True)
    lines.append(f"  D-TRACK2-G6 audit: {'PASS' if overall else 'FAIL'}")
    if not chain_reads_requested:
        lines.append(f"  (Note: chain-read verification skipped; re-run with --include-chain-reads)")
    lines.append("")

    lines.append("Section 5 — D-TRACK2-G7 Operator-Driven Commands")
    lines.append("-" * 78)
    for line in G7_OPERATOR_COMMANDS.split("\n"):
        lines.append("  " + line)
    lines.append("")
    lines.append("=" * 78)
    lines.append("End of audit.")
    lines.append("=" * 78)
    return "\n".join(lines)


def _render_json_report(
    *,
    s1: tuple[bool, list, dict],
    s2: tuple[bool, list] | None,
    s3: tuple[bool, list],
    chain_reads_requested: bool,
) -> str:
    s1_ok, s1_findings, _ = s1
    s3_ok, s3_findings = s3
    out: dict = {
        "audit_id": "D-TRACK2-G6",
        "wallet_free": True,
        "sections": {
            "section_1_local_merkles": {
                "ok": s1_ok,
                "findings": s1_findings,
            },
            "section_3_lane_matrix": {
                "ok": s3_ok,
                "findings": s3_findings,
            },
        },
    }
    if chain_reads_requested and s2 is not None:
        s2_ok, s2_findings = s2
        out["sections"]["section_2_chain_reads"] = {
            "ok": s2_ok,
            "findings": s2_findings,
        }
    overall = s1_ok and s3_ok and (s2[0] if (chain_reads_requested and s2) else True)
    out["overall_pass"] = overall
    out["g7_operator_commands_required"] = True
    return json.dumps(out, indent=2)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

async def _run(args: argparse.Namespace) -> int:
    bundle_dir = PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"

    # Section 1 — local Merkles (always runs)
    s1 = section_1_local_merkles(bundle_dir)
    s1_ok = s1[0]

    # Section 2 — chain reads (optional)
    s2: tuple[bool, list] | None = None
    if args.include_chain_reads:
        s2 = await section_2_chain_reads(s1[2])

    # Section 3 — lane matrix (always runs)
    s3 = section_3_lane_matrix(bundle_dir)
    s3_ok = s3[0]

    # Render
    if args.json:
        print(_render_json_report(
            s1=s1, s2=s2, s3=s3, chain_reads_requested=args.include_chain_reads,
        ))
    else:
        print(_render_human_report(
            s1=s1, s2=s2, s3=s3, chain_reads_requested=args.include_chain_reads,
        ))

    # Exit code
    if not s1_ok:
        return 1
    if args.include_chain_reads and s2 is not None and not s2[0]:
        # Distinguish RPC config errors (return 4) from drift (return 2)
        for f in s2[1]:
            if f.get("status") in ("CONFIG_ERROR", "AGENT_ID_MISSING", "RPC_ERROR"):
                return 4
        return 2
    if not s3_ok:
        return 3
    return 0


def _main_cli() -> int:
    # Windows defaults stdout to cp1252 which can't encode the report's
    # em-dashes / section symbols / arrows. Reconfigure to UTF-8 with
    # 'replace' errors so the audit always emits cleanly. No-op on
    # platforms that already use UTF-8 stdout.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        # Older Python or non-reconfigurable stream — best effort.
        pass

    parser = argparse.ArgumentParser(
        description=(
            "Phase O3-ZKBA-TRACK1 Track 2 post-ceremony audit (D-TRACK2-G6). "
            "Wallet-free, read-only observability. Verifies local v2 bundle "
            "Merkle vs EXPECTED_MERKLES lock + (optional) on-chain "
            "AgentScope.getScopeRoot state + Cedar v2 lane authority matrix."
        )
    )
    parser.add_argument(
        "--include-chain-reads",
        action="store_true",
        help=(
            "Also call AgentScope.getScopeRoot() per agent via eth_call. "
            "Read-only; no tx; no gas; no wallet impact; bypasses "
            "CHAIN_SUBMISSION_PAUSED. Requires bridge/.env + RPC reachable."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable report.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(_main_cli())
