"""HWFL-1 Sensor B v0.2 (companion) — Multi-source URL reachability prober.

Closes F-HWFL-5-1: Cycle 5 vendor-catalog research failed 4/4 fetches
(Microchip 403, Wikipedia 404 ×2, Mouser 60s timeout, DigiKey 404).
The honest fix is not "make the runner auto-extract summary from
HTML" (requires an LLM, scope creep) but "give the operator
reachability data so they route around dead vendor pages BEFORE
manual intel-gathering."

This module is the pure-function half: it takes a list of candidate
URLs + an injected HEAD fetcher and returns a ReachabilityReport.
The network boundary lives in `scripts/probe_vendor_urls.py`.

Architectural rails (parallel Sensor B v0.1):
  - Pure-function module; no network calls; deterministic tests.
  - Fail-open: any fetcher exception => UNREACHABLE (never spurious
    REACHABLE).
  - HEAD-only by design — we want existence/status, not content;
    avoids the prompt-injection surface entirely (no body parsing).
  - State taxonomy mirrors HTTP status classes, NOT Sensor B's
    WatchState; this is a different telemetry shape (point-in-time
    reachability vs supply/standards narrative).

Scope for v0.2 (this cycle):
  - Standalone module + utility. Sensor B v0.1.1 byte-identical.
  - Integration into watch render path (e.g. WatchLine carries
    reachability summary inline) is a v0.2.1 future-cycle decision
    if/when operator wants the data inline rather than a separate
    artifact.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Iterable, Optional, Tuple


class ReachState(str, Enum):
    REACHABLE = "REACHABLE"      # HEAD returned a 2xx
    REDIRECTED = "REDIRECTED"    # HEAD returned a 3xx (follow-up may resolve)
    FORBIDDEN = "FORBIDDEN"      # HEAD returned 401/403 (anti-bot likely; operator may still reach via browser)
    NOT_FOUND = "NOT-FOUND"      # HEAD returned 404/410
    SERVER_ERROR = "SERVER-ERROR"  # HEAD returned 5xx
    TIMEOUT = "TIMEOUT"          # fetcher raised a timeout
    NETWORK_ERROR = "NETWORK-ERROR"  # fetcher raised any other exception
    UNREACHABLE = "UNREACHABLE"  # catch-all (status not in any of the above bins)


@dataclass(frozen=True)
class ProbeResult:
    """One probe outcome. The fetcher returns this; the module
    classifies the state. Pass status=None + error=<str> to signal
    a fetcher exception (TIMEOUT / NETWORK_ERROR depending on text)."""
    url: str
    status: Optional[int]
    error: Optional[str] = None
    elapsed_ms: Optional[int] = None


@dataclass(frozen=True)
class ReachabilityLine:
    url: str
    state: ReachState
    status: Optional[int]
    elapsed_ms: Optional[int]
    evidence: str


@dataclass(frozen=True)
class ReachabilityReport:
    ts_iso: str
    label: str  # e.g. "S2.atecc608a-lifecycle" — informs which Sensor B topic this informs
    lines: Tuple[ReachabilityLine, ...]

    def to_markdown(self) -> str:
        rows = [f"# Multi-source URL reachability — {_esc(self.label)}", ""]
        rows.append(f"- Timestamp: `{_esc(self.ts_iso)}`")
        rows.append(f"- URLs probed: {len(self.lines)}")
        from collections import Counter
        counts = Counter(ln.state.value for ln in self.lines)
        dist = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        rows.append(f"- Distribution: {dist}")
        rows.append("")
        rows.append("| URL | State | HTTP | Elapsed | Evidence |")
        rows.append("|-----|-------|------|---------|----------|")
        for ln in self.lines:
            rows.append(
                "| {url} | {state} | {http} | {elapsed} | {ev} |".format(
                    url=_esc(ln.url),
                    state=ln.state.value,
                    http=str(ln.status) if ln.status is not None else "—",
                    elapsed=f"{ln.elapsed_ms} ms" if ln.elapsed_ms is not None else "—",
                    ev=_esc(ln.evidence),
                )
            )
        rows.append("")
        return "\n".join(rows)


def _classify(probe: ProbeResult) -> Tuple[ReachState, str]:
    """Pure classification — never raises. Returns (state, evidence)."""
    if probe.error is not None:
        err = probe.error.lower()
        if "timeout" in err or "timed out" in err:
            return ReachState.TIMEOUT, f"fetcher reported timeout: {probe.error}"
        return ReachState.NETWORK_ERROR, f"fetcher exception: {probe.error}"
    if probe.status is None:
        return ReachState.UNREACHABLE, "fetcher returned no status and no error"
    s = probe.status
    if 200 <= s < 300:
        return ReachState.REACHABLE, f"HEAD {s}"
    if 300 <= s < 400:
        return ReachState.REDIRECTED, f"HEAD {s} (follow-up may resolve)"
    if s in (401, 403):
        return ReachState.FORBIDDEN, f"HEAD {s} (anti-bot likely; operator may reach via browser)"
    if s in (404, 410):
        return ReachState.NOT_FOUND, f"HEAD {s}"
    if 500 <= s < 600:
        return ReachState.SERVER_ERROR, f"HEAD {s}"
    return ReachState.UNREACHABLE, f"HEAD {s} (unclassified)"


def probe(
    urls: Iterable[str],
    label: str,
    fetcher: Callable[[str], ProbeResult],
    ts_iso: Optional[str] = None,
) -> ReachabilityReport:
    """Pure entry point. `fetcher(url)` must return a ProbeResult and
    must never raise — runner-side exceptions must be caught and
    materialized into a ProbeResult with error=<repr>."""
    if ts_iso is None:
        ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = []
    for url in urls:
        probe_result = fetcher(url)
        state, evidence = _classify(probe_result)
        lines.append(
            ReachabilityLine(
                url=probe_result.url,
                state=state,
                status=probe_result.status,
                elapsed_ms=probe_result.elapsed_ms,
                evidence=evidence,
            )
        )
    return ReachabilityReport(ts_iso=ts_iso, label=label, lines=tuple(lines))


def _esc(s: str) -> str:
    """Defensive: URL strings and error messages are external content.

    HTML/pipe escape so a malformed URL or evidence message cannot
    break the markdown table or inject active markup. Parallels the
    Sensor B v0.1 / Sensor A v0.2 discipline.
    """
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace("|", "\\|")
         .replace("\n", " ")
    )
