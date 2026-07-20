"""
Shared CLAUDE.md live-state parser for VAPI's three MCP servers
(server.py, knowledge_server.py, unified_server.py).

Why this exists (2026-07-20 MCP Tier-1 audit): each server previously carried
its own copy-pasted _parse_claude_md(), and the three copies had drifted —
same underlying facts, three different wrong answers, because a regex fix in
one file never propagated to the other two. This module is the single source
of truth; fixing a pattern here fixes it everywhere.

Anchor-first: prefers the machine-readable `<!-- SENSOR-A-LIVE:* -->` HTML
comments (added by HWFL-1 Cycle 10, D-HWFL-33) over prose regexes wherever an
anchor exists — "the anchor IS the canonical claim, not the prose around it."
Prose regexes remain as a fallback for facts that don't have an anchor yet
(phase headline, agent count, AIT ratio, PV-CI count, L4 thresholds).

Each MCP server keeps its own thin adapter around parse_claude_md() so
existing downstream call sites (which expect specific key names/types) don't
need to change — only the parsing logic underneath does.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_CACHE: dict = {"mtime": 0.0, "state": {}}


def parse_claude_md(project_root: Path) -> dict[str, Any]:
    """
    Parse CLAUDE.md into current protocol state. Mtime-cached — re-parsed
    only when the file actually changes. Falls back to last-known state on
    any read error; never raises.
    """
    claude_path = Path(project_root) / "CLAUDE.md"
    try:
        mtime = claude_path.stat().st_mtime
    except OSError:
        return _CACHE.get("state", {})

    if mtime <= _CACHE["mtime"] and _CACHE["state"]:
        return _CACHE["state"]

    try:
        text = claude_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return _CACHE.get("state", {})

    s: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Phase headline. May lag the NOTE log by weeks (the header is hand-
    # edited less often than NOTEs are appended) — both are surfaced so a
    # caller can see the honest gap rather than trusting one silently.
    # ------------------------------------------------------------------
    m = re.search(r"Current phase:\s*Phase\s*(\d+)", text)
    if m:
        s["phase_num"] = m.group(1)
        s["phase"] = f"{m.group(1)} COMPLETE"
    else:
        # Tolerates an optional "(...)" aside between the commit hash and the
        # em-dash headline — CLAUDE.md started inserting these around
        # 2026-05-31 and the old pattern silently stopped matching.
        mh = re.search(
            r"Current phase:\s*HEAD\s*`?([0-9a-f]{6,40})`?\s*(?:\([^)]*\)\s*)?"
            r"[—\-]+\s*\*{0,2}([^.\n]{5,160})",
            text,
        )
        if mh:
            s["phase_num"] = mh.group(1)[:8]
            s["phase"] = f"HEAD {mh.group(1)[:8]} — {mh.group(2).strip()}"
        else:
            s["phase_num"] = "unknown"
            s["phase"] = "unparseable — read CLAUDE.md 'Current phase:' line directly"

    # Freshest signal: the most recent NOTE: entry. NOTEs are appended
    # newest-first immediately below "Current phase:", and are updated far
    # more often than the phase header itself — surfacing this lets a caller
    # notice when the header has gone stale relative to actual recent work.
    mn = re.search(r"^NOTE:\s*(.{10,200}?)\s*—", text, re.MULTILINE)
    s["latest_note"] = mn.group(1).strip() if mn else None

    # ------------------------------------------------------------------
    # SENSOR-A-LIVE anchors (HWFL-1 Cycle 10, D-HWFL-33) — authoritative
    # when present. These exist specifically so downstream tooling doesn't
    # have to guess at prose shape.
    # ------------------------------------------------------------------
    m = re.search(
        r"<!--\s*SENSOR-A-LIVE:WALLET\s+balance_iotx=([0-9.]+)\s+as_of=([\d-]+)\s*-->", text
    )
    if m:
        s["wallet_balance_iotx"] = float(m.group(1))
        s["wallet_balance_as_of"] = m.group(2)

    m = re.search(
        r"<!--\s*SENSOR-A-LIVE:CONTRACTS\s+count=(\d+)\s+as_of=([\d-]+)\s*-->", text
    )
    if m:
        s["contracts_live"] = int(m.group(1))
        s["contracts_live_as_of"] = m.group(2)
        s["contracts_live_source"] = "anchor"

    m = re.search(
        r"<!--\s*SENSOR-A-LIVE:TESTS\s+bridge=(\d+)\s+sdk=(\d+)\s+"
        r"hardhat_regex_scan=(\d+)\s+as_of=([\d-]+)\s*-->",
        text,
    )
    if m:
        s["bridge"] = int(m.group(1))
        s["sdk"] = int(m.group(2))
        s["hardhat_regex_scan"] = int(m.group(3))
        s["tests_as_of"] = m.group(4)
        s["tests_source"] = "anchor"

    # ------------------------------------------------------------------
    # Prose fallbacks — used only when the matching anchor is absent
    # (e.g. an older CLAUDE.md snapshot, or if an anchor is ever dropped).
    # ------------------------------------------------------------------
    if "bridge" not in s:
        m = re.search(r"Bridge:\s*\*{0,2}(\d+)\s*(?:passing|collected)", text)
        s["bridge"] = int(m.group(1)) if m else 4330
        s.setdefault("tests_source", "prose_fallback" if m else "hardcoded_fallback")
    if "sdk" not in s:
        m = re.search(r"SDK:\s*\*{0,2}(\d+)\s*collected", text)
        s["sdk"] = int(m.group(1)) if m else 604

    # "Contract: N" is the `npx hardhat test` count, kept under the historical
    # key name `hardhat` for backward compatibility. Distinct from the
    # regex-scan proxy in the TESTS anchor (hardhat_regex_scan) — the two are
    # different precision regimes and must not be conflated (per HWFL-1
    # Cycle 13 D-HWFL-34 schema-honesty rename).
    m = re.search(r"Contract:\s*(\d+)", text)
    s["hardhat"] = int(m.group(1)) if m else 674

    m = re.search(r"Hardware:\s*(\d+)", text)
    s["hardware"] = int(m.group(1)) if m else 37
    m = re.search(r"E2E:\s*(\d+)", text)
    s["e2e"] = int(m.group(1)) if m else 14
    s["total_ci"] = s["bridge"] + s["hardhat"] + s["sdk"]

    if "contracts_live" not in s:
        # No anchor found — count addr-shaped keys in deployed-addresses.json
        # directly (mirrors what Sensor A itself does) rather than trusting
        # "N contracts ALL LIVE" prose, which only ever appears inside old
        # historical NOTE text and no longer reflects the current count.
        try:
            addr_path = Path(project_root) / "contracts" / "deployed-addresses.json"
            data = json.loads(addr_path.read_text(encoding="utf-8"))
            n = sum(
                1 for k, v in data.items()
                if not k.startswith("_") and isinstance(v, str) and v.startswith("0x")
            )
            s["contracts_live"] = n
            s["contracts_live_source"] = "deployed_addresses_json"
        except Exception:
            s["contracts_live"] = 46
            s["contracts_live_source"] = "hardcoded_fallback"

    # PV-CI invariant baseline — "**PV-CI: 184**" headline in the TESTS prose.
    m = re.search(r"PV-CI:\s*\*{0,2}(\d+)\*{0,2}", text)
    s["pv_ci_count"] = int(m.group(1)) if m else None

    # ------------------------------------------------------------------
    # Agent fleet count — max across three independent signal shapes.
    # Any one alone misses recent phases (prose transitions stop at 36;
    # "agent #N" references and "N-ID roster" mentions carry the latest).
    # ------------------------------------------------------------------
    arrows = re.findall(r"agents\s+(\d+)→(\d+)", text)
    agent_refs = re.findall(r"agent\s+#(\d+)", text)
    roster_refs = re.findall(r"(\d+)-ID roster", text)
    candidates = (
        [int(p[1]) for p in arrows] + [int(n) for n in agent_refs] + [int(n) for n in roster_refs]
    )
    s["agents"] = max(candidates) if candidates else 38

    # L4 thresholds
    m = re.search(r"L4 anomaly threshold:\s*\*\*([0-9.]+)\*\*", text)
    s["l4_anomaly"] = float(m.group(1)) if m else 7.009
    m = re.search(r"L4 continuity threshold:\s*\*\*([0-9.]+)\*\*", text)
    s["l4_continuity"] = float(m.group(1)) if m else 5.367

    # Legacy separation-ratio probes (touchpad_corners / tremor_resting).
    m = re.search(r"tremor_resting[^:]*:\s*\*\*([0-9.]+)\*\*[^N]*N=(\d+)", text)
    s["tremor_resting_ratio"] = float(m.group(1)) if m else 1.177
    s["tremor_resting_n"] = int(m.group(2)) if m else 27
    m = re.search(r"Separation ratio:\s*\*\*([0-9.]+)\*\*[^)]*diagonal\+LOO[^)]*N=(\d+)", text)
    s["touchpad_corners_ratio"] = float(m.group(1)) if m else 0.728
    s["touchpad_corners_n"] = int(m.group(2)) if m else 35

    # AIT — the CURRENT primary tournament-gate separation metric
    # (Phase 229-231; supersedes touchpad_corners/tremor_resting as the
    # headline gate per the 2026-05-09 policy adjustment). Absent from all
    # three servers prior to this fix.
    m = re.search(
        r"AIT probe[^:]*:\s*ratio=\*\*([0-9.]+)\*\*,\s*all_pairs_above_1=\*\*(True|False)\*\*",
        text,
    )
    if m:
        s["ait_ratio"] = float(m.group(1))
        s["ait_all_pairs_above_1"] = m.group(2) == "True"
    else:
        s["ait_ratio"] = None
        s["ait_all_pairs_above_1"] = None
    m = re.search(r"AIT corpus[^:]*:\s*N=(\d+)\s*total", text)
    s["ait_n"] = int(m.group(1)) if m else None
    m = re.search(r"ait_defensibility_ok=(True|False)", text)
    s["ait_defensibility_ok"] = (m.group(1) == "True") if m else None

    # Wallet address (balance comes from the SENSOR-A-LIVE:WALLET anchor above)
    m = re.search(r"Active wallet[^`]*`(0x[0-9a-fA-F]{40})`", text)
    s["wallet"] = m.group(1) if m else "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"

    # WIF corpus — count open entries (cheap heuristic, kept from the
    # knowledge_server.py copy of this parser).
    s["wif_open_count"] = len(re.findall(r"Status.*?OPEN", text))

    # ------------------------------------------------------------------
    # Recent phases: parse the "## Phase Summary" markdown TABLE (current
    # format). The old parser looked for "Phase NNN — COMPLETE (..." prose
    # lines, which stopped existing once the table format replaced them —
    # that regex has returned {} for every caller since the table shipped.
    # ------------------------------------------------------------------
    recent: dict[str, str] = {}
    tbl = re.search(r"## Phase Summary.*?\n((?:\|.*\n)+)", text, re.DOTALL)
    if tbl:
        for row in tbl.group(1).splitlines():
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) < 2 or not cells[0] or not re.match(r"^\d", cells[0]):
                continue  # skips header row, separator row, and the "..." / "<=229" archive rows
            recent[cells[0]] = cells[1][:160]
            if len(recent) >= 10:
                break
    s["recent_phases"] = recent

    _CACHE["mtime"] = mtime
    _CACHE["state"] = s
    return s
