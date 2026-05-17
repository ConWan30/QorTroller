"""LayerZero VHP bridge readiness audit — wallet-free, read-only.

Scans contracts/contracts/VAPIVerifiedHumanProofBridge.sol for the
specific stub patterns documented in wiki/runbooks/
layerzero_vhp_mainnet_activation_runbook.md. Reports verdict:

  STUB          — current state: send() emits event only; no _lzSend
  OAPP_WIRED    — post-refactor: OApp inherited + _lzSend wired
  MAINNET_READY — post-deploy on both chains (cannot verify from source
                  alone; flagged for operator-runtime verification)

Run:

    python scripts/layerzero_vhp_bridge_audit.py
    python scripts/layerzero_vhp_bridge_audit.py --json

WALLET-FREE CONTRACT:
  - No transaction submission paths invoked
  - No bridge HTTP calls
  - No chain RPC reads
  - Pure file-content inspection of one Solidity source file
  - CHAIN_SUBMISSION_PAUSED state untouched

Exit codes:
  0  OAPP_WIRED or higher (production-ready code state)
  1  STUB (current state; deferred per v4 §15 tier #7)
  2  Contract source not found
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_SRC = (
    PROJECT_ROOT / "contracts" / "contracts" / "VAPIVerifiedHumanProofBridge.sol"
)


# FROZEN stub-state pattern indicators. Each tuple:
#   (pattern_regex, indicator_kind, description)
# kind: STUB_REQUIRED (must be absent for OAPP_WIRED) /
#       PRODUCTION_REQUIRED (must be present for OAPP_WIRED).
STUB_PATTERNS = [
    (
        r"This is an AssemblyScript stub",
        "STUB_REQUIRED",
        "Stub-only acknowledgment comment present",
    ),
    (
        r"//\s*Stub:\s*emit event only \(testnet mode\)",
        "STUB_REQUIRED",
        "send() emits event without actual LayerZero call",
    ),
    (
        r"//\s*Production:\s*bytes memory payload",
        "STUB_REQUIRED",
        "Production payload encoding is commented-out only",
    ),
    (
        r"contract VAPIVerifiedHumanProofBridge is Ownable\b",
        "STUB_REQUIRED",
        "Inherits Ownable only (production must inherit OApp + Ownable)",
    ),
]

PRODUCTION_PATTERNS = [
    (
        r"import.*@layerzerolabs/lz-evm-oapp",
        "PRODUCTION_REQUIRED",
        "LayerZero OApp package imported",
    ),
    (
        r"contract VAPIVerifiedHumanProofBridge is OApp\b",
        "PRODUCTION_REQUIRED",
        "Inherits OApp",
    ),
    (
        r"function _lzReceive\(",
        "PRODUCTION_REQUIRED",
        "_lzReceive() implemented",
    ),
    (
        r"_lzSend\(",
        "PRODUCTION_REQUIRED",
        "_lzSend() actually called (not just commented)",
    ),
    (
        r"receivedNonces\[",
        "PRODUCTION_REQUIRED",
        "Receive-side replay guard via receivedNonces mapping",
    ),
]


def scan(src_path: Path) -> dict:
    if not src_path.exists():
        return {
            "verdict": "SRC_NOT_FOUND",
            "exit_code": 2,
            "error": f"contract source not found: {src_path}",
        }

    source = src_path.read_text(encoding="utf-8")
    findings = []
    stub_indicators_found = 0
    production_indicators_found = 0

    for pat, kind, desc in STUB_PATTERNS:
        present = bool(re.search(pat, source, re.IGNORECASE))
        findings.append({
            "pattern": pat,
            "kind": kind,
            "description": desc,
            "present": present,
        })
        if present:
            stub_indicators_found += 1

    for pat, kind, desc in PRODUCTION_PATTERNS:
        present = bool(re.search(pat, source, re.IGNORECASE))
        findings.append({
            "pattern": pat,
            "kind": kind,
            "description": desc,
            "present": present,
        })
        if present:
            production_indicators_found += 1

    # Verdict logic:
    # STUB         = any STUB_REQUIRED present AND any PRODUCTION_REQUIRED absent
    # OAPP_WIRED   = all PRODUCTION_REQUIRED present AND zero STUB_REQUIRED present
    # Mixed (e.g. some stubs remain alongside some production) flags STUB.
    if production_indicators_found == len(PRODUCTION_PATTERNS) and \
       stub_indicators_found == 0:
        verdict = "OAPP_WIRED"
        exit_code = 0
        reason = (
            "All production patterns present; no stub indicators. "
            "OApp inheritance + _lzSend + _lzReceive + receivedNonces "
            "all present. Code state is ready for mainnet deploy "
            "ceremony per wiki/runbooks/"
            "layerzero_vhp_mainnet_activation_runbook.md."
        )
    else:
        verdict = "STUB"
        exit_code = 1
        reason = (
            f"Stub indicators found: {stub_indicators_found}/"
            f"{len(STUB_PATTERNS)}. "
            f"Production indicators found: {production_indicators_found}/"
            f"{len(PRODUCTION_PATTERNS)}. "
            f"Refactor required before mainnet deploy. See runbook."
        )

    return {
        "audit": "layerzero_vhp_bridge_readiness",
        "src_path": str(src_path),
        "verdict": verdict,
        "exit_code": exit_code,
        "reason": reason,
        "stub_indicators_found": stub_indicators_found,
        "stub_indicators_total": len(STUB_PATTERNS),
        "production_indicators_found": production_indicators_found,
        "production_indicators_total": len(PRODUCTION_PATTERNS),
        "findings": findings,
    }


def render_human(report: dict) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("LayerZero VHP Bridge Mainnet Readiness Audit")
    lines.append("=" * 70)
    if "error" in report:
        lines.append(f"ERROR: {report['error']}")
        lines.append(f"Exit code: {report['exit_code']}")
        return "\n".join(lines)

    lines.append(f"Source: {report['src_path']}")
    lines.append("")

    lines.append("Stub indicators (present => current testnet state):")
    for f in report["findings"]:
        if f["kind"] == "STUB_REQUIRED":
            mark = "  [PRESENT]" if f["present"] else "  [absent] "
            lines.append(f"{mark} {f['description']}")
    lines.append("")

    lines.append("Production indicators (present => OApp-wired refactor done):")
    for f in report["findings"]:
        if f["kind"] == "PRODUCTION_REQUIRED":
            mark = "  [PRESENT]" if f["present"] else "  [absent] "
            lines.append(f"{mark} {f['description']}")
    lines.append("")

    lines.append("=" * 70)
    lines.append(f"VERDICT: {report['verdict']}")
    lines.append(f"Reason: {report['reason']}")
    lines.append(f"Exit code: {report['exit_code']}")
    lines.append("=" * 70)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LayerZero VHP bridge readiness audit",
    )
    parser.add_argument(
        "--src", type=Path, default=BRIDGE_SRC,
        help=f"Path to VAPIVerifiedHumanProofBridge.sol (default: {BRIDGE_SRC})",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

    report = scan(args.src)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(render_human(report))
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
