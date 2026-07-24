"""A2A-STEWARD-EVOLVE — PCRA evidence-loop Inc-1 runner (operator-invoked).

Runs Guardian PCRA and persists findings as reviewable audit-drafting drafts. This is the network/DB
boundary; the pure logic lives in `bridge/vapi_bridge/steward_pcra_draft.py`. Gated by cfg.pcra_enabled
(PCRA_ENABLED=1). 0-IOTX, no chain — drafts route to Guardian's LOCAL audit handler; the operator then
reviews each via the existing /operator/operator-agent-draft-review endpoint (accept/reject) → SEL label.

  PCRA_ENABLED=1 python scripts/run_pcra_draft.py                    # CEILING only (offline)
  PCRA_ENABLED=1 python scripts/run_pcra_draft.py --with-stale-anchor  # + live wallet/PV-CI/contract drift

CEILING is a local file scan (works offline). STALE_ANCHOR reuses the Sensor-A live oracles (network).
Fail-soft: a fetch/DB error degrades that source, never crashes the run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.steward_pcra import scan_repo  # noqa: E402
from bridge.vapi_bridge.steward_pcra_draft import persist_pcra_findings, stale_anchor_findings  # noqa: E402


def _stale_anchor_findings_live() -> list:
    """Reuse the Sensor-A live drift report; extract DRIFTED anchors → PCRA STALE_ANCHOR findings.
    Fail-soft: any error returns []."""
    try:
        from bridge.vapi_bridge.sensor_a_live_drift import DriftState, assemble_drift_report, LiveFetchResult
        from scripts.run_sensor_a_live import fetch_contract_count, fetch_wallet_balance, fetch_test_counts
        wallet_balance, wallet_err = fetch_wallet_balance()
        contract_count, contract_err = fetch_contract_count()
        test_counts, test_err = fetch_test_counts(skip_tests=True)
        fetch = LiveFetchResult(
            wallet_balance_iotx=wallet_balance, wallet_fetch_error=wallet_err,
            contract_count=contract_count, contract_fetch_error=contract_err,
            test_counts=test_counts, test_fetch_error=test_err,
        )
        claude_md = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        report = assemble_drift_report(claude_md, fetch)
        claimed, live = {}, {}
        for ln in report.lines:
            if ln.state == DriftState.DRIFTED:
                claimed[ln.probe_id] = ln.claimed_value
                live[ln.probe_id] = ln.live_value
        return stale_anchor_findings(claimed, live)
    except Exception as exc:  # noqa: BLE001
        print(f"[pcra] STALE_ANCHOR live fetch degraded ({exc!r}) — CEILING only")
        return []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PCRA drafting runner (Inc-1)")
    parser.add_argument("--with-stale-anchor", action="store_true",
                        help="also fetch live oracles for STALE_ANCHOR (network)")
    args = parser.parse_args(argv)

    try:
        from bridge.vapi_bridge.config import Config
        from bridge.vapi_bridge.store import Store
        from bridge.vapi_bridge.operator_agent_guardian_drafting import GuardianDraftGenerator
    except Exception as exc:  # noqa: BLE001
        print(f"[pcra] bridge import failed: {exc!r}")
        return 2

    cfg = Config()
    if not bool(getattr(cfg, "pcra_enabled", False)):
        print("[pcra] pcra_enabled=False — set PCRA_ENABLED=1 to run. (opt-in, default-OFF)")
        return 0

    store = Store()
    generator = GuardianDraftGenerator(cfg=cfg, store=store)

    ceiling = scan_repo(cfg, REPO_ROOT).get("findings", [])
    stale = _stale_anchor_findings_live() if args.with_stale_anchor else []
    findings = list(ceiling) + list(stale)

    summary = persist_pcra_findings(generator, findings, cfg=cfg)
    print(f"[pcra] CEILING={len(ceiling)} STALE_ANCHOR={len(stale)} "
          f"persisted={summary['n_persisted']}/{summary['n_findings']}")
    for uri in summary.get("draft_uris", []):
        print(f"[pcra]   draft: {uri}")
    print("[pcra] review each via /operator/operator-agent-draft-review (accept/reject) → SEL label (Inc-2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
