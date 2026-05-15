"""Mythos PR Gate — CI wrapper for Mythos-Frozen + Mythos-Crypto variants.

Runs on every pull_request opened/synchronize/reopened against main via
.github/workflows/vapi-mythos-pr-gate.yml. Surfaces findings as GitHub
Actions annotations (::error / ::warning) so they appear inline in the
PR's Files Changed view.

Exit codes:
  0  No CRITICAL or HIGH frozen_region findings (PR may merge)
  1  At least one CRITICAL or HIGH frozen_region=True finding (blocks merge)
  2  Script error (variant import failure, unexpected exception)

Why only Frozen + Crypto on PR gate (vs all 7 Mythos variants):
  • Stability:    155 MEDIUM findings on current main are pre-existing
                  convention drift — would noise every PR. Runs on daily
                  cadence; not at PR time.
  • OpInit:       Doesn't change per-PR; expensive bundle Merkle recompute.
                  Runs on weekly + pre_ceremony cadence.
  • Methodology:  Methodology files rarely touched in PRs. Runs weekly.
  • Ceremony:     Checks operator env state (CHAIN_SUBMISSION_PAUSED, etc.);
                  varies between operators, not PR-relevant.
  • Corpus:       DB-bound; varies; not PR-relevant.

What the gate DOES catch at PR time:
  • Frozen (CRITICAL): any PV-CI invariant drift — patterns no longer
    matching, file digests changed without allowlist regen.
  • Crypto (CRITICAL): any FROZEN PATTERN-017 commitment-family domain
    tag missing from production code.
  • Crypto (HIGH):    any unknown b"VAPI-..." literal appearing in
    production source (potential new family without governance ceremony).

Wallet-free; no chain RPC; no DB writes (PR runner is ephemeral GH actions VM).
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "bridge") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "bridge"))


def _gh_annotation(finding) -> str:
    """Format a MythosFindingResult as a GitHub Actions annotation.

    CRITICAL / HIGH frozen_region=True → ::error (red badge, blocks).
    HIGH non-frozen / MEDIUM           → ::warning (yellow badge, informational).
    LOW                                → ::notice (blue badge).
    """
    level_by_sev = {
        "CRITICAL": "error",
        "HIGH":     "error" if finding.frozen_region else "warning",
        "MEDIUM":   "warning",
        "LOW":      "notice",
    }
    level = level_by_sev.get(finding.severity, "warning")
    fp = (finding.file_path or "").replace("\\", "/")
    fp_part = f"file={fp}," if fp else ""
    line_part = f"line={finding.line_number}," if finding.line_number else ""
    title = f"Mythos-{finding.variant}/{finding.severity}"
    # Escape newlines in description for GH annotation single-line format.
    msg = (finding.description or "").replace("\n", "%0A").replace("\r", "")
    return f"::{level} {fp_part}{line_part}title={title}::{msg}"


def _is_blocking(finding) -> bool:
    """Return True if this finding should block PR merge.

    Blocking rules (FROZEN — drift here changes the gate's effective
    enforcement):
      • CRITICAL severity            → ALWAYS blocks
      • HIGH severity + frozen_region=True → blocks (protocol-layer drift)
      • Anything else                → informational only
    """
    if finding.severity == "CRITICAL":
        return True
    if finding.severity == "HIGH" and bool(finding.frozen_region):
        return True
    return False


def _summarize(findings: List, gate_name: str) -> dict:
    sev_counts: dict[str, int] = {}
    blocking_count = 0
    for f in findings:
        sev_counts[f.severity] = sev_counts.get(f.severity, 0) + 1
        if _is_blocking(f):
            blocking_count += 1
    return {
        "gate":           gate_name,
        "total":          len(findings),
        "by_severity":    sev_counts,
        "blocking_count": blocking_count,
    }


async def _run() -> int:
    findings_all: List = []
    summaries: List[dict] = []

    try:
        from vapi_bridge.mythos_variants import (
            mythos_frozen_drift,
            mythos_crypto_drift,
        )
    except Exception as exc:  # noqa: BLE001 — exit-2 fail-open
        print(f"::error title=Mythos PR Gate Script Error::"
              f"Could not import vapi_bridge.mythos_variants: {exc}")
        return 2

    # --- Frozen gate ---
    try:
        fz = await mythos_frozen_drift(repo_root=PROJECT_ROOT)
        findings_all.extend(fz)
        summaries.append(_summarize(fz, "Mythos-Frozen"))
    except Exception as exc:  # noqa: BLE001
        print(f"::error title=Mythos-Frozen Variant Crashed::{exc}")
        return 2

    # --- Crypto gate ---
    try:
        cr = await mythos_crypto_drift(
            repo_root=PROJECT_ROOT, poll_npm_registry=False,
        )
        findings_all.extend(cr)
        summaries.append(_summarize(cr, "Mythos-Crypto"))
    except Exception as exc:  # noqa: BLE001
        print(f"::error title=Mythos-Crypto Variant Crashed::{exc}")
        return 2

    # Emit annotations (one per finding) — GH renders these inline in PR.
    for f in findings_all:
        print(_gh_annotation(f))

    # Summary line for the GH Actions log.
    total_blocking = sum(s["blocking_count"] for s in summaries)
    print("")
    print("=" * 72)
    print("Mythos PR Gate — summary")
    for s in summaries:
        print(f"  {s['gate']:<16s} total={s['total']:>3d}  by_severity={s['by_severity']}  blocking={s['blocking_count']}")
    print(f"  TOTAL_BLOCKING = {total_blocking}")
    print("=" * 72)

    # Emit GitHub Actions job summary if running in CI.
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write("## Mythos PR Gate Results\n\n")
                for s in summaries:
                    fh.write(
                        f"- **{s['gate']}**: {s['total']} finding(s); "
                        f"severity={s['by_severity']}; "
                        f"blocking={s['blocking_count']}\n"
                    )
                fh.write(f"\n**TOTAL_BLOCKING**: {total_blocking}\n\n")
                if total_blocking > 0:
                    fh.write(
                        "> Merge is BLOCKED. Restore drifted state from "
                        "git history OR invoke governance ceremony per the "
                        "Mythos recommended_fix in the inline annotations.\n"
                    )
                else:
                    fh.write(
                        "> No blocking findings. PR may merge.\n"
                    )
        except Exception:  # noqa: BLE001 — non-fatal
            pass

    return 1 if total_blocking > 0 else 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mythos PR Gate — runs Frozen + Crypto variants and "
                    "blocks merge on CRITICAL / HIGH frozen_region findings."
    )
    parser.add_argument(
        "--output",
        choices=["github", "human"],
        default="github",
        help="Output format. 'github' emits GHA annotations; 'human' prints "
             "findings as plain text.",
    )
    parser.parse_args(argv)  # parse for consistency; --output is a hint.
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
