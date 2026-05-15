"""Phase O5-MYTHOS-MINIMAL M.1 — Mythos cadence engine.

Opt-in background task that invokes registered Mythos variants on a
heartbeat and persists their findings to mythos_finding_log. Mirrors the
cedar_drift_sweeper pattern (Phase O1 C4) verbatim:

  - Opt-out by default (cfg.mythos_cadence_enabled defaults False).
  - Single async loop, cancellable, fail-open (catches all exceptions per
    iteration; never lets one bad variant crash the loop).
  - Variants are INJECTED via the get_pending_variants callable so M.1
    can ship infrastructure without M.2's variant implementations. When
    M.2 wires real variants, the cadence engine becomes load-bearing
    without re-shipping infrastructure.

Output routing (per the plan):
  - mythos_finding_log table — every finding (anti-replay via coherence_id
    UNIQUE constraint).
  - mythos_cadence_log table — every variant wakeup trace.
  - fleet_coherence_log (M.3 wires this) — FSCA picks up high-severity
    findings via 2 new contradiction rules.

Cadence schedule (MYTHOS_CADENCE_SCHEDULE) is a FROZEN constant — PV-CI
will pin it via INV-MYTHOS-CADENCE-001 in M.3.

FROZEN-region safety (INV-MYTHOS-FROZEN-PROTECTION-001, M.3): the store
helper insert_mythos_finding FORCES fix_authority_tier=3 (read-only)
whenever a finding has frozen_region=True, regardless of what the variant
declared. The variant CAN suggest tier-1 autofix, but the cadence engine /
store layer / PV-CI gate jointly prevent that suggestion from taking effect
on a FROZEN region. Mythos NEVER auto-fixes FROZEN material.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Iterable

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# MYTHOS_CADENCE_SCHEDULE — FROZEN constant; INV-MYTHOS-CADENCE-001 (M.3).
# --------------------------------------------------------------------------
# Each entry: cadence-tier-name -> list of variant identifiers that run at
# that tier. M.1 ships only the "daily" tier as a real cadence; other
# tiers are placeholder hooks for M.2/M.5 (full Mythos) to register
# variants under (per_pr from GitHub Actions hook; per_phase_close from
# explicit operator-runtime invocation; pre_ceremony from preflight
# script; post_incident from FSCA rule trigger).
MYTHOS_CADENCE_SCHEDULE: dict[str, list[str]] = {
    "daily":          ["frozen", "stability", "crypto", "corpus"],  # M.1+M.2+Priority-5
    "per_pr":         ["frozen", "crypto"],                         # Priority-5
    "per_phase_close":["methodology"],                              # Priority-5
    "pre_ceremony":   ["ceremony", "frozen", "operator_initiative"],
    "post_ceremony":  ["post_o3", "operator_initiative"],           # operator goal 2026-05-15
    "post_incident":  ["stability", "crypto"],
    "weekly":         ["operator_initiative", "methodology"],       # Priority-5
}


@dataclass(slots=True)
class MythosFindingResult:
    """One Mythos finding emitted by a variant. Per the plan's W1
    consensus-fallacy mitigation: evidence_sources MUST declare the corpus
    the variant audited so cross-variant independence can be scored later
    (Priority 5 ships the consensus-check table; M.1 just stores the
    field so it's available)."""

    variant: str                                # "frozen" | "stability" | ...
    severity: str                               # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    description: str                            # one-sentence finding
    recommended_fix: str                        # concrete action
    coherence_id: str                           # "mythos_<variant>_<sha256[:16]>" (anti-replay key)
    file_path: str | None = None
    line_number: int | None = None
    frozen_region: bool = False                 # touches FROZEN material?
    fix_risk: str = "low"                       # "low" | "medium" | "high"
    fix_authority_tier: int = 2                 # 1=autofix / 2=op-gated / 3=read-only
    evidence_sources: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    error: str = ""                             # fail-open contract


# A variant runner is an async callable that returns a list of findings.
# It MUST be self-contained, never raise (catch its own exceptions and
# return an error-tagged MythosFindingResult instead), and complete within
# the cadence interval.
VariantRunner = Callable[[], Awaitable[list[MythosFindingResult]]]


def record_mythos_finding(store, finding: MythosFindingResult) -> int:
    """Persist one MythosFindingResult to mythos_finding_log via the store
    helper. Returns row id (0 on dedup-collision or DB error). Fail-open."""
    try:
        return int(store.insert_mythos_finding(
            variant=finding.variant,
            severity=finding.severity,
            coherence_id=finding.coherence_id,
            description=finding.description,
            recommended_fix=finding.recommended_fix,
            file_path=finding.file_path,
            line_number=finding.line_number,
            frozen_region=finding.frozen_region,
            fix_authority_tier=finding.fix_authority_tier,
            evidence_sources=list(finding.evidence_sources),
        ))
    except Exception as exc:  # noqa: BLE001
        log.warning("record_mythos_finding: store insert raised: %s", exc)
        return 0


async def run_mythos_cadence_loop(
    *,
    cfg,
    store,
    get_pending_variants: Callable[[], Iterable[tuple[str, VariantRunner]]] | None = None,
) -> None:
    """Mirror of cedar_drift_sweeper.run_drift_sweep_loop. Opt-in via
    cfg.mythos_cadence_enabled. Runs variants returned by
    get_pending_variants() on cfg.mythos_cadence_interval_s heartbeat.

    Each variant's findings are recorded to mythos_finding_log; the
    cadence wakeup is recorded to mythos_cadence_log. Variant exceptions
    are caught + recorded (error column) but do NOT crash the loop.

    Returns silently when cfg.mythos_cadence_enabled is False (scaffold-
    only when not opted in)."""
    if not bool(getattr(cfg, "mythos_cadence_enabled", False)):
        return
    interval_s = float(getattr(cfg, "mythos_cadence_interval_s", 86400.0))
    log.info(
        "Phase O5-MYTHOS-MINIMAL: cadence loop started "
        "(interval=%.0fs, variants_callable=%s)",
        interval_s, get_pending_variants is not None,
    )
    while True:
        try:
            if get_pending_variants is not None:
                # Run each variant in this cycle's pending list. Variants
                # are dispatched serially (Mythos sweeps are cheap +
                # mostly-I/O; the cadence interval is 24h so wall-time
                # is non-binding).
                try:
                    variants_iter = list(get_pending_variants())
                except Exception as exc:  # noqa: BLE001
                    log.warning("mythos cadence: get_pending_variants raised: %s", exc)
                    variants_iter = []
                for vname, variant_fn in variants_iter:
                    t0 = time.monotonic()
                    findings: list[MythosFindingResult] = []
                    err: str | None = None
                    try:
                        findings = await variant_fn()
                    except Exception as exc:  # noqa: BLE001
                        err = str(exc)
                        log.warning("mythos variant %s raised: %s", vname, exc)
                    # Persist findings (each insert is independent; idempotent
                    # on duplicate coherence_id via UNIQUE constraint).
                    for f in findings:
                        record_mythos_finding(store, f)
                    duration_ms = int((time.monotonic() - t0) * 1000)
                    try:
                        store.insert_mythos_cadence_run(
                            variant=str(vname),
                            cadence="daily",
                            findings_count=len(findings),
                            duration_ms=duration_ms,
                            triggered_by="schedule",
                            error=err,
                        )
                    except Exception as exc2:  # noqa: BLE001
                        log.warning("mythos cadence log insert raised: %s", exc2)
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            log.info("Phase O5-MYTHOS-MINIMAL: cadence loop cancelled")
            return
        except Exception as exc:  # noqa: BLE001
            # Any unexpected error: log + continue (never crash the loop).
            log.warning("mythos cadence loop: unexpected error: %s", exc)
            try:
                await asyncio.sleep(interval_s)
            except asyncio.CancelledError:
                return
