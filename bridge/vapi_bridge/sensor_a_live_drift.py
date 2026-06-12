"""HWFL-1 Sensor A v0.2 — Live-state-vs-CLAUDE.md drift detection.

Standalone module (D-HWFL-31) — separate from Sensor A v0.1 (the
mythos_path_a_spec_impl_parity variant #16, which is static
spec/impl parity at file+comment level). v0.2 is a different
telemetry shape: it compares live runtime values (wallet balance,
deployed-contract count, test counts) against the canonical claim
that CLAUDE.md makes about each.

Driven by F-HWFL-4-1 (Cycle 4): the wallet line carried a stale
~14.26 IOTX claim from 2026-05-21 through multiple Arc 5/6/7 NOTEs
unchecked; live balance was 32.078 IOTX. The session-end discipline
("eth_getBalance before stating") is brittle without a sensor that
mechanically catches drift the same way Sensor A v0.1 catches
spec/impl drift.

Output artifacts:
  - audits/live-state-drift-cycle-<N>-<YYYY-MM-DD>.md  (per-cycle proof)

State taxonomy (FROZEN for v0.2):
  ALIGNED      — live value matches CLAUDE.md anchor within tolerance
  DRIFTED      — live value differs beyond tolerance; CLAUDE.md is stale
  UNVERIFIABLE — fetch failed OR anchor missing/malformed; fail-open

Architectural rails (parallel Sensor B/C):
  - Pure-function module: never touches the network or subprocess.
    Live values arrive via an injected LiveFetchResult dataclass.
    Network/subprocess boundary lives in scripts/run_sensor_a_live.py.
  - Fail-open: any anchor-parse error or missing live value yields
    UNVERIFIABLE, never spurious DRIFTED. A future cycle that
    re-introduces drift is caught by the proof artifact, not by
    a sensor that lies about state it couldn't verify.
  - CLAUDE.md anchor shape (D-HWFL-33) is explicit HTML-comment
    blocks: <!-- SENSOR-A-LIVE:<ID> k=v k=v ... -->. Regex against
    natural prose was rejected as brittle.
  - Tolerance per probe is encoded in the verifier, not in the
    fetcher. P-WALLET tolerates 0.5 IOTX sub-deploy noise; P-CONTRACT
    and P-TESTS demand exact match.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Mapping, Optional, Tuple


class DriftState(str, Enum):
    ALIGNED = "ALIGNED"
    DRIFTED = "DRIFTED"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class LiveFetchResult:
    """Boundary dataclass — runner fills, module consumes.

    Any None field signals fetch error; the matching probe will
    render UNVERIFIABLE with the *_error string as evidence.
    """
    wallet_balance_iotx: Optional[float] = None
    wallet_fetch_error: Optional[str] = None
    contract_count: Optional[int] = None
    contract_fetch_error: Optional[str] = None
    test_counts: Optional[Mapping[str, int]] = None  # e.g. {"bridge": 4330, "sdk": 604, "hardhat": 674}
    test_fetch_error: Optional[str] = None


@dataclass(frozen=True)
class DriftLine:
    probe_id: str
    description: str
    state: DriftState
    live_value: str
    claimed_value: str
    evidence: str


@dataclass(frozen=True)
class DriftReport:
    ts_iso: str
    lines: Tuple[DriftLine, ...]

    def to_markdown(self) -> str:
        rows = []
        rows.append(f"# HWFL-1 Sensor A v0.2 — Live-state drift report")
        rows.append("")
        rows.append(f"- Timestamp: `{_escape_md(self.ts_iso)}`")
        rows.append(f"- Probes: {len(self.lines)}")
        aligned = sum(1 for ln in self.lines if ln.state == DriftState.ALIGNED)
        drifted = sum(1 for ln in self.lines if ln.state == DriftState.DRIFTED)
        unverifiable = sum(1 for ln in self.lines if ln.state == DriftState.UNVERIFIABLE)
        rows.append(f"- Distribution: ALIGNED={aligned} DRIFTED={drifted} UNVERIFIABLE={unverifiable}")
        rows.append("")
        rows.append("## Probes")
        rows.append("")
        rows.append("| Probe | Description | State | Live | Claimed | Evidence |")
        rows.append("|-------|-------------|-------|------|---------|----------|")
        for ln in self.lines:
            rows.append(
                "| {probe} | {desc} | {state} | {live} | {claimed} | {ev} |".format(
                    probe=_escape_md(ln.probe_id),
                    desc=_escape_md(ln.description),
                    state=ln.state.value,
                    live=_escape_md(ln.live_value),
                    claimed=_escape_md(ln.claimed_value),
                    ev=_escape_md(ln.evidence),
                )
            )
        rows.append("")
        return "\n".join(rows)


_ANCHOR_RE = re.compile(
    r"<!--\s*SENSOR-A-LIVE:(?P<id>[A-Z_-]+)\s+(?P<body>[^>]*?)-->"
)


def parse_anchors(claude_md_text: str) -> Dict[str, Dict[str, str]]:
    """Parse <!-- SENSOR-A-LIVE:<ID> k=v k=v ... --> blocks.

    Returns {anchor_id: {key: value}}. Last-write-wins on duplicate
    IDs (defensive — duplicate anchor is itself a finding, but parse
    must not raise). Malformed bodies yield empty dicts.
    """
    result: Dict[str, Dict[str, str]] = {}
    for match in _ANCHOR_RE.finditer(claude_md_text):
        anchor_id = match.group("id").strip()
        body = match.group("body").strip()
        kv: Dict[str, str] = {}
        for token in body.split():
            if "=" not in token:
                continue
            key, _, value = token.partition("=")
            key = key.strip()
            value = value.strip()
            if key and value:
                kv[key] = value
        result[anchor_id] = kv
    return result


_WALLET_TOLERANCE_IOTX = 0.5


def _verify_wallet(
    anchors: Mapping[str, Mapping[str, str]],
    fetch: LiveFetchResult,
) -> DriftLine:
    desc = "Bridge wallet IOTX balance vs CLAUDE.md SENSOR-A-LIVE:WALLET anchor"
    claimed_block = anchors.get("WALLET")
    if claimed_block is None:
        return DriftLine(
            probe_id="P-WALLET",
            description=desc,
            state=DriftState.UNVERIFIABLE,
            live_value="(skipped — anchor missing)",
            claimed_value="(missing)",
            evidence="SENSOR-A-LIVE:WALLET anchor not found in CLAUDE.md",
        )
    claimed_raw = claimed_block.get("balance_iotx", "")
    claimed_as_of = claimed_block.get("as_of", "?")
    try:
        claimed = float(claimed_raw)
    except (TypeError, ValueError):
        return DriftLine(
            probe_id="P-WALLET",
            description=desc,
            state=DriftState.UNVERIFIABLE,
            live_value="(skipped — claim unparseable)",
            claimed_value=claimed_raw or "(missing)",
            evidence=f"balance_iotx={claimed_raw!r} not float-parseable",
        )
    if fetch.wallet_balance_iotx is None:
        err = fetch.wallet_fetch_error or "fetch returned None with no error"
        return DriftLine(
            probe_id="P-WALLET",
            description=desc,
            state=DriftState.UNVERIFIABLE,
            live_value="(fetch error)",
            claimed_value=f"{claimed:.6f} IOTX as_of={claimed_as_of}",
            evidence=f"live fetch error: {err}",
        )
    live = fetch.wallet_balance_iotx
    delta = abs(live - claimed)
    live_str = f"{live:.6f} IOTX"
    claimed_str = f"{claimed:.6f} IOTX as_of={claimed_as_of}"
    if delta <= _WALLET_TOLERANCE_IOTX:
        return DriftLine(
            probe_id="P-WALLET",
            description=desc,
            state=DriftState.ALIGNED,
            live_value=live_str,
            claimed_value=claimed_str,
            evidence=f"|live - claimed| = {delta:.6f} IOTX <= {_WALLET_TOLERANCE_IOTX} IOTX tolerance",
        )
    return DriftLine(
        probe_id="P-WALLET",
        description=desc,
        state=DriftState.DRIFTED,
        live_value=live_str,
        claimed_value=claimed_str,
        evidence=f"|live - claimed| = {delta:.6f} IOTX exceeds {_WALLET_TOLERANCE_IOTX} IOTX tolerance",
    )


def _verify_contract_count(
    anchors: Mapping[str, Mapping[str, str]],
    fetch: LiveFetchResult,
) -> DriftLine:
    desc = "Deployed contract count vs CLAUDE.md SENSOR-A-LIVE:CONTRACTS anchor"
    claimed_block = anchors.get("CONTRACTS")
    if claimed_block is None:
        return DriftLine(
            probe_id="P-CONTRACT",
            description=desc,
            state=DriftState.UNVERIFIABLE,
            live_value="(skipped — anchor missing)",
            claimed_value="(missing)",
            evidence="SENSOR-A-LIVE:CONTRACTS anchor not found in CLAUDE.md",
        )
    claimed_raw = claimed_block.get("count", "")
    claimed_as_of = claimed_block.get("as_of", "?")
    try:
        claimed = int(claimed_raw)
    except (TypeError, ValueError):
        return DriftLine(
            probe_id="P-CONTRACT",
            description=desc,
            state=DriftState.UNVERIFIABLE,
            live_value="(skipped — claim unparseable)",
            claimed_value=claimed_raw or "(missing)",
            evidence=f"count={claimed_raw!r} not int-parseable",
        )
    if fetch.contract_count is None:
        err = fetch.contract_fetch_error or "fetch returned None with no error"
        return DriftLine(
            probe_id="P-CONTRACT",
            description=desc,
            state=DriftState.UNVERIFIABLE,
            live_value="(fetch error)",
            claimed_value=f"{claimed} as_of={claimed_as_of}",
            evidence=f"live fetch error: {err}",
        )
    live = fetch.contract_count
    live_str = str(live)
    claimed_str = f"{claimed} as_of={claimed_as_of}"
    if live == claimed:
        return DriftLine(
            probe_id="P-CONTRACT",
            description=desc,
            state=DriftState.ALIGNED,
            live_value=live_str,
            claimed_value=claimed_str,
            evidence="exact match",
        )
    return DriftLine(
        probe_id="P-CONTRACT",
        description=desc,
        state=DriftState.DRIFTED,
        live_value=live_str,
        claimed_value=claimed_str,
        evidence=f"delta={live - claimed:+d} contracts",
    )


_TEST_SUITES = ("bridge", "sdk", "hardhat")


def _verify_test_counts(
    anchors: Mapping[str, Mapping[str, str]],
    fetch: LiveFetchResult,
) -> DriftLine:
    desc = "Per-suite test counts vs CLAUDE.md SENSOR-A-LIVE:TESTS anchor"
    claimed_block = anchors.get("TESTS")
    if claimed_block is None:
        return DriftLine(
            probe_id="P-TESTS",
            description=desc,
            state=DriftState.UNVERIFIABLE,
            live_value="(skipped — anchor missing)",
            claimed_value="(missing)",
            evidence="SENSOR-A-LIVE:TESTS anchor not found in CLAUDE.md",
        )
    claimed_as_of = claimed_block.get("as_of", "?")
    claimed_counts: Dict[str, int] = {}
    for suite in _TEST_SUITES:
        raw = claimed_block.get(suite, "")
        try:
            claimed_counts[suite] = int(raw)
        except (TypeError, ValueError):
            return DriftLine(
                probe_id="P-TESTS",
                description=desc,
                state=DriftState.UNVERIFIABLE,
                live_value="(skipped — claim unparseable)",
                claimed_value=str(dict(claimed_block)),
                evidence=f"{suite}={raw!r} not int-parseable",
            )
    if fetch.test_counts is None:
        err = fetch.test_fetch_error or "fetch returned None with no error"
        claimed_str = " ".join(f"{s}={claimed_counts[s]}" for s in _TEST_SUITES) + f" as_of={claimed_as_of}"
        return DriftLine(
            probe_id="P-TESTS",
            description=desc,
            state=DriftState.UNVERIFIABLE,
            live_value="(fetch error)",
            claimed_value=claimed_str,
            evidence=f"live fetch error: {err}",
        )
    live_counts = dict(fetch.test_counts)
    deltas = []
    drifted = False
    for suite in _TEST_SUITES:
        live = live_counts.get(suite)
        claimed = claimed_counts[suite]
        if live is None:
            return DriftLine(
                probe_id="P-TESTS",
                description=desc,
                state=DriftState.UNVERIFIABLE,
                live_value=str(live_counts),
                claimed_value=" ".join(f"{s}={claimed_counts[s]}" for s in _TEST_SUITES),
                evidence=f"live fetch missing suite {suite!r}",
            )
        if live != claimed:
            drifted = True
        deltas.append(f"{suite}:{live - claimed:+d}")
    live_str = " ".join(f"{s}={live_counts[s]}" for s in _TEST_SUITES)
    claimed_str = " ".join(f"{s}={claimed_counts[s]}" for s in _TEST_SUITES) + f" as_of={claimed_as_of}"
    if not drifted:
        return DriftLine(
            probe_id="P-TESTS",
            description=desc,
            state=DriftState.ALIGNED,
            live_value=live_str,
            claimed_value=claimed_str,
            evidence="all suites exact match",
        )
    return DriftLine(
        probe_id="P-TESTS",
        description=desc,
        state=DriftState.DRIFTED,
        live_value=live_str,
        claimed_value=claimed_str,
        evidence="deltas " + " ".join(deltas),
    )


def assemble_drift_report(
    claude_md_text: str,
    fetch: LiveFetchResult,
    ts_iso: Optional[str] = None,
) -> DriftReport:
    """Pure entry point. Runner injects CLAUDE.md text + LiveFetchResult."""
    anchors = parse_anchors(claude_md_text)
    if ts_iso is None:
        ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = (
        _verify_wallet(anchors, fetch),
        _verify_contract_count(anchors, fetch),
        _verify_test_counts(anchors, fetch),
    )
    return DriftReport(ts_iso=ts_iso, lines=lines)


def _escape_md(s: str) -> str:
    """Defensive: anchor bodies + fetch error strings are external content.

    HTML/pipe escape so a malformed anchor or error message cannot
    break the markdown table or inject active markup. Parallels the
    Sensor B v0.1 discipline (HTML-escape + pipe-escape every
    external field) shipped in Cycle 3.
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
