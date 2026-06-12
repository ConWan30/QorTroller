"""HWFL-1 Sensor B v0.1 — Supply-and-standards watch.

Pure-function assembler for the cycle's `audits/hardware-watch-<date>.md`
intelligence report. Tracks ATECC608A lifecycle, the three approved stick
modules (K-Silver JH16 HE / MIDAS 5-pin HE / Magneto TMR), ESP32-class
module certification status, IIP-64 PR #72 movement, and competitive
attested-input-controller landscape.

Architectural rails (D-HWFL-10, D-HWFL-11):
  - Module is pure-function. The network boundary lives in
    `scripts/run_sensor_b.py`. Fetched data is passed in as a dict;
    assembler never calls out. This makes tests deterministic and
    isolates the prompt-injection surface to one runner script.
  - 7 canonical sources for v0.1 (FROZEN per cycle; externalization
    is v0.2 cycle decision).
  - Every web-sourced claim renders with an explicit UNVERIFIED-EXTERNAL
    marker per the loop's master prompt discipline. STRUCTURED sources
    (e.g. IIP-64 PR via gh CLI JSON) get a FRESH state once fetched;
    MANUAL_NARRATIVE sources require operator-pasted text and land as
    PENDING-OPERATOR-NOTE in the absence of input.

State taxonomy (extends Sensor C's):
  FRESH                 — fetched this cycle, within freshness window
  STALE                 — last fetch outside freshness window
  PENDING-OPERATOR-NOTE — MANUAL_NARRATIVE source not yet populated
  UNVERIFIED-EXTERNAL   — narrative content present; not verifiable from repo state
  FETCH-ERROR           — fetcher tried and failed; full error preserved
"""
from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum


class FetchKind(str, Enum):
    STRUCTURED = "STRUCTURED"            # Deterministic source (e.g. GitHub PR via gh CLI)
    MANUAL_NARRATIVE = "MANUAL_NARRATIVE"  # Operator-pasted intelligence


class WatchState(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    PENDING_OPERATOR_NOTE = "PENDING-OPERATOR-NOTE"
    UNVERIFIED_EXTERNAL = "UNVERIFIED-EXTERNAL"
    VERIFIED_EXTERNAL = "VERIFIED-EXTERNAL"  # Cycle 6 / Sensor B v0.1.1 — MANUAL_NARRATIVE with all 3 structural verification preconditions met
    FETCH_ERROR = "FETCH-ERROR"


@dataclass(frozen=True, slots=True)
class WatchSource:
    """Canonical source definition — frozen at module load."""
    topic_id: str
    title: str
    primary_url: str
    fetch_kind: FetchKind
    freshness_days: int     # cycle-level freshness expectation
    spec_ref: str           # which Sensor C gate (if any) this source informs


@dataclass(slots=True)
class FetchResult:
    """Runner-provided fetch payload for one topic. Pass `summary=None` to
    explicitly request the PENDING-OPERATOR-NOTE state without an error.

    VERIFIED-EXTERNAL precondition fields (D-HWFL-18, Cycle 6 / v0.1.1):
    For a MANUAL_NARRATIVE entry to reach VERIFIED-EXTERNAL state, ALL
    three structural fields below must be present and non-empty:
      - verified_by:    non-empty str — who did the verification (operator name,
                        agent ID, third-party reviewer)
      - sources:        non-empty list[str] — sources verifier consulted
                        (URLs, document IDs, codebase paths; URLs NOT
                        required — any identifier-shaped string accepted)
      - verified_date:  ISO-8601 date (YYYY-MM-DD) — when verification happened

    Absence/partial-presence behavior (D-HWFL-20):
      - All 3 fields present, valid, within freshness window => VERIFIED-EXTERNAL
      - All 3 fields present, valid, outside freshness window => STALE
        (detail render retains verified_by/sources/verified_date so reviewer
        sees what WAS verified, just that verification is past freshness)
      - 0 of 3 fields present (Cycle 3-style JSON)            => silent downgrade
                                                                 to UNVERIFIED-EXTERNAL
                                                                 (backward compat)
      - 1 or 2 of 3 fields present                            => downgrade to
                                                                 UNVERIFIED-EXTERNAL
                                                                 + warning marker
                                                                 surfaced in summary
                                                                 (catches partial-
                                                                 verification typos)
      - 3 present but verified_date unparseable               => downgrade with warning
    """
    topic_id: str
    summary: str | None              # one-line headline; None => pending
    raw_excerpt: str = ""            # short data extract; rendered with html-escape
    fetched_at: str = ""             # ISO-8601 UTC; "" => never fetched
    error: str = ""                  # non-empty => FETCH-ERROR state
    # VERIFIED-EXTERNAL preconditions (all 3 required for VERIFIED state):
    verified_by: str = ""
    sources: list[str] = field(default_factory=list)
    verified_date: str = ""          # ISO-8601 date (YYYY-MM-DD)


@dataclass(slots=True)
class WatchLine:
    """Per-source resolution in the cycle's report."""
    source: WatchSource
    state: WatchState
    summary: str
    raw_excerpt: str
    fetched_at: str
    error: str
    # Verification structural fields surfaced when state is VERIFIED-EXTERNAL
    # OR when state was downgraded from VERIFIED-EXTERNAL to STALE (D-HWFL-19).
    verified_by: str = ""
    sources: list[str] = field(default_factory=list)
    verified_date: str = ""
    # Non-empty when partial-structure downgrade fires (D-HWFL-20 amendment).
    verification_warning: str = ""

    def to_markdown_row(self) -> str:
        # Defensive HTML-escape on every external-sourced field. Prevents a
        # malicious branch name / PR title / pasted narrative from breaking
        # the markdown table or injecting active content.
        def _e(s: str) -> str:
            return html.escape(s, quote=False).replace("|", "\\|").replace("\n", " ")
        return (
            f"| `{_e(self.source.topic_id)}` | "
            f"{_e(self.source.title)} | "
            f"`{self.state.value}` | "
            f"{_e(self.summary)} | "
            f"{_e(self.fetched_at)} |"
        )


# ---------------------------------------------------------------------------
# Canonical source registry — D-HWFL-11 confirmed 7-source v0.1 list.
# ---------------------------------------------------------------------------
_CANONICAL_SOURCES: tuple[WatchSource, ...] = (
    WatchSource(
        topic_id="S1.iip64-pr72",
        title="IIP-64 PR #72 movement",
        primary_url="https://github.com/iotexproject/iips/pull/72",
        fetch_kind=FetchKind.STRUCTURED,
        freshness_days=7,
        spec_ref="Sensor C G4.1 BLOCKED-ON-EXTERNAL",
    ),
    WatchSource(
        topic_id="S2.atecc608a-lifecycle",
        title="ATECC608A lifecycle / successor parts",
        primary_url="https://www.microchip.com/en-us/product/atecc608a",
        fetch_kind=FetchKind.MANUAL_NARRATIVE,
        freshness_days=30,
        spec_ref="docs/path-a-manufacturing-spec.md §2 Hardware Requirement",
    ),
    WatchSource(
        topic_id="S3.k-silver-jh16-he-stick",
        title="K-Silver JH16 Hall-effect stick module availability",
        primary_url="https://www.k-silver.com/",
        fetch_kind=FetchKind.MANUAL_NARRATIVE,
        freshness_days=30,
        spec_ref="Sensor C G2.5 Hall/TMR stick selection",
    ),
    WatchSource(
        topic_id="S4.midas-5pin-he-stick",
        title="MIDAS 5-pin Hall-effect stick module availability",
        primary_url="https://moddedzone.com/",
        fetch_kind=FetchKind.MANUAL_NARRATIVE,
        freshness_days=30,
        spec_ref="Sensor C G2.5 Hall/TMR stick selection",
    ),
    WatchSource(
        topic_id="S5.magneto-tmr-stick",
        title="Magneto TMR stick module availability",
        primary_url="https://www.battlebeavercustoms.com/",
        fetch_kind=FetchKind.MANUAL_NARRATIVE,
        freshness_days=30,
        spec_ref="Sensor C G2.5 Hall/TMR stick selection",
    ),
    WatchSource(
        topic_id="S6.esp32-cert-status",
        title="ESP32-class module certification status",
        primary_url="https://www.espressif.com/en/products/socs/esp32",
        fetch_kind=FetchKind.MANUAL_NARRATIVE,
        freshness_days=60,
        spec_ref="Sensor C G2.7 BLOCKED-ON-SENSOR-B (unblock candidate)",
    ),
    WatchSource(
        topic_id="S7.competitive-landscape",
        title="Competitive attested-input controller landscape",
        primary_url="",   # narrative survey; no single canonical URL
        fetch_kind=FetchKind.MANUAL_NARRATIVE,
        freshness_days=90,
        spec_ref="HWFL-1 master prompt; recurring intel surface",
    ),
)


# ---------------------------------------------------------------------------
# Assembler
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class WatchReport:
    cycle: int
    cycle_date: str
    generated_at: str
    lines: list[WatchLine]

    def state_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for line in self.lines:
            counts[line.state.value] = counts.get(line.state.value, 0) + 1
        return counts

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Sensor B — Hardware Watch Report (Cycle {self.cycle}, {self.cycle_date})\n")
        lines.append(
            "HWFL-1 Sensor B v0.1 — supply-and-standards watch. "
            "Pure-function assembler at "
            "`bridge/vapi_bridge/sensor_b_supply_watch.py`; network "
            "boundary lives at `scripts/run_sensor_b.py`. "
            f"Generated `{self.generated_at}`.\n"
        )

        lines.append("\n## Honesty rail\n")
        lines.append(
            "Every web-sourced claim in this report carries an "
            "**UNVERIFIED-EXTERNAL** posture by default. `FRESH` lines come "
            "from structured queries (e.g. `gh pr view` JSON) and the "
            "summary cell reproduces only directly-observable fields. "
            "`PENDING-OPERATOR-NOTE` lines are placeholders the operator "
            "fills in by reading the primary URL and pasting intelligence "
            "into the runner's `--narratives` JSON. The loop NEVER converts "
            "an external claim into a repo-code change without independent "
            "verification by the operator."
        )

        # Standing OPERATOR-ACTION box (consistent with Sensor C).
        lines.append("\n## Standing OPERATOR-ACTION box (loop never auto-touches)\n")
        lines.append("- [ ] **OA-1** Back up `~/.vapi/qortroller_foundation_mfg_ca.json` (517 B) — F-DECON-3.2 interim. Highest-leverage 5-min action.")
        lines.append("- [ ] **OA-2** Create `docs/disaster-recovery-runbook.private.md` with full AWS KMS ARNs.")
        lines.append("- [ ] **OA-3** IAM scope-down on bridge/.env AWS keys → `KMS:Sign` + `KMS:GetPublicKey` on the two specific key ARNs.")
        lines.append("- [ ] **OA-4** Long-term: HSM-backed ManufacturerRootCA + device re-issuance.")

        lines.append("\n## State summary\n")
        lines.append("| State | Count |")
        lines.append("|---|---|")
        counts = self.state_counts()
        for state in WatchState:
            n = counts.get(state.value, 0)
            if n:
                lines.append(f"| {state.value} | {n} |")
        lines.append(f"| **Total** | **{len(self.lines)}** |")

        lines.append("\n## Watch lines\n")
        lines.append("| Topic | Title | State | Summary | Fetched at |")
        lines.append("|---|---|---|---|---|")
        for line in self.lines:
            lines.append(line.to_markdown_row())

        # Detailed per-source sections so raw excerpts have room.
        lines.append("\n## Detail\n")
        for line in self.lines:
            src = line.source
            lines.append(f"### {src.topic_id} — {html.escape(src.title, quote=False)}")
            lines.append(f"- **state:** `{line.state.value}`")
            lines.append(f"- **fetch kind:** `{src.fetch_kind.value}`")
            lines.append(f"- **primary URL:** {src.primary_url or '_(narrative survey; no single canonical URL)_'}")
            lines.append(f"- **spec ref:** {src.spec_ref}")
            lines.append(f"- **freshness window:** {src.freshness_days} days")
            if line.summary:
                lines.append(f"- **summary:** {html.escape(line.summary, quote=False)}")
            else:
                lines.append("- **summary:** _PENDING-OPERATOR-NOTE — populate via runner `--narratives` JSON_")
            if line.raw_excerpt:
                # Code-fenced so any injected markdown stays inert.
                lines.append(f"- **raw excerpt:**\n```\n{line.raw_excerpt[:600]}\n```")
            if line.error:
                lines.append(f"- **error:** `{html.escape(line.error, quote=False)}`")
            if line.fetched_at:
                lines.append(f"- **fetched at:** `{line.fetched_at}`")
            # Verification structural fields — rendered whenever ANY are present so
            # both VERIFIED-EXTERNAL (3/3) AND STALE-from-verified (3/3 aged) AND
            # partial-structure-warning (1-2/3) surface them.
            if line.verified_by:
                lines.append(f"- **verified by:** {html.escape(line.verified_by, quote=False)}")
            if line.verified_date:
                lines.append(f"- **verified date:** `{html.escape(line.verified_date, quote=False)}`")
            if line.sources:
                lines.append("- **sources:**")
                for s in line.sources:
                    lines.append(f"  - {html.escape(s, quote=False)}")
            if line.verification_warning:
                # Render warning prominently — caught a partial-structure or malformed-date typo.
                lines.append(
                    f"- **VERIFICATION WARNING:** {html.escape(line.verification_warning, quote=False)}"
                )
            lines.append("")

        lines.append("\n## Provenance\n")
        lines.append(f"- Canonical source registry: `bridge/vapi_bridge/sensor_b_supply_watch.py::_CANONICAL_SOURCES` ({len(self.lines)} sources, FROZEN per cycle)")
        lines.append("- Network calls: `scripts/run_sensor_b.py` only (gh CLI for STRUCTURED, operator JSON for MANUAL_NARRATIVE)")
        lines.append("- Discipline: every external claim escaped + UNVERIFIED-EXTERNAL by default")
        return "\n".join(lines) + "\n"


def _resolve_state(
    source: WatchSource,
    fetched: FetchResult | None,
    now_utc: datetime,
) -> WatchLine:
    """Single state-decision site. Returns a fully-formed WatchLine.

    State-resolution order:
      1. fetched is None                 -> PENDING-OPERATOR-NOTE
      2. fetched.error non-empty         -> FETCH-ERROR
      3. fetched.summary is None         -> PENDING-OPERATOR-NOTE
      4. STRUCTURED + within freshness   -> FRESH
      5. STRUCTURED + outside freshness  -> STALE
      6. MANUAL_NARRATIVE + 3/3 verified fields + within freshness
                                         -> VERIFIED-EXTERNAL  (D-HWFL-18)
      7. MANUAL_NARRATIVE + 3/3 verified fields + outside freshness
                                         -> STALE  (D-HWFL-19; detail retains fields)
      8. MANUAL_NARRATIVE + 1-2/3 fields -> UNVERIFIED-EXTERNAL + warning (D-HWFL-20)
      9. MANUAL_NARRATIVE + 3/3 but verified_date unparseable
                                         -> UNVERIFIED-EXTERNAL + warning
     10. MANUAL_NARRATIVE + 0/3 fields   -> UNVERIFIED-EXTERNAL (Cycle 3 backward compat)
    """
    if fetched is None:
        return WatchLine(
            source=source, state=WatchState.PENDING_OPERATOR_NOTE,
            summary="", raw_excerpt="", fetched_at="", error="",
        )
    if fetched.error:
        return WatchLine(
            source=source, state=WatchState.FETCH_ERROR,
            summary=fetched.summary or "fetch failed",
            raw_excerpt=fetched.raw_excerpt,
            fetched_at=fetched.fetched_at,
            error=fetched.error,
        )
    if fetched.summary is None:
        return WatchLine(
            source=source, state=WatchState.PENDING_OPERATOR_NOTE,
            summary="", raw_excerpt=fetched.raw_excerpt,
            fetched_at=fetched.fetched_at, error="",
        )

    # Freshness check shared by FRESH and VERIFIED-EXTERNAL paths.
    def _is_within_freshness(iso_ts: str) -> tuple[bool, bool]:
        """Returns (within_window, parseable)."""
        if not iso_ts:
            return (True, True)  # No timestamp => don't punish; treat as fresh
        try:
            ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
            age_days = (now_utc - ts).total_seconds() / 86400.0
            return (age_days <= source.freshness_days, True)
        except ValueError:
            return (True, False)  # Malformed => keep FRESH/VERIFIED but flag

    fetched_at_within, _ = _is_within_freshness(fetched.fetched_at)

    if source.fetch_kind == FetchKind.STRUCTURED:
        state = WatchState.FRESH if fetched_at_within else WatchState.STALE
        return WatchLine(
            source=source, state=state,
            summary=fetched.summary, raw_excerpt=fetched.raw_excerpt,
            fetched_at=fetched.fetched_at, error="",
        )

    # MANUAL_NARRATIVE path — VERIFIED-EXTERNAL preconditions (D-HWFL-18/19/20).
    has_verified_by = bool(fetched.verified_by.strip())
    has_sources = bool(fetched.sources) and all(isinstance(s, str) and s.strip() for s in fetched.sources)
    has_verified_date = bool(fetched.verified_date.strip())
    present_count = has_verified_by + has_sources + has_verified_date

    if present_count == 0:
        # Cycle 3 backward compat: no verified_* fields at all => silent
        # downgrade to UNVERIFIED-EXTERNAL (no warning rendered).
        return WatchLine(
            source=source, state=WatchState.UNVERIFIED_EXTERNAL,
            summary=fetched.summary, raw_excerpt=fetched.raw_excerpt,
            fetched_at=fetched.fetched_at, error="",
        )

    if present_count < 3:
        # Partial structure => downgrade WITH warning (D-HWFL-20 amendment).
        missing = []
        if not has_verified_by:   missing.append("verified_by")
        if not has_sources:       missing.append("sources[non-empty]")
        if not has_verified_date: missing.append("verified_date")
        warning = (
            f"PARTIAL VERIFICATION STRUCTURE: missing {missing}. "
            f"For VERIFIED-EXTERNAL state, all 3 fields must be present "
            f"(verified_by + non-empty sources[] + verified_date). "
            f"Downgraded to UNVERIFIED-EXTERNAL."
        )
        return WatchLine(
            source=source, state=WatchState.UNVERIFIED_EXTERNAL,
            summary=fetched.summary, raw_excerpt=fetched.raw_excerpt,
            fetched_at=fetched.fetched_at, error="",
            verified_by=fetched.verified_by,
            sources=list(fetched.sources),
            verified_date=fetched.verified_date,
            verification_warning=warning,
        )

    # 3/3 fields present. Validate verified_date is parseable ISO date.
    try:
        date.fromisoformat(fetched.verified_date.strip())
    except ValueError:
        warning = (
            f"MALFORMED verified_date {fetched.verified_date!r} — expected "
            f"ISO-8601 (YYYY-MM-DD). Downgraded to UNVERIFIED-EXTERNAL."
        )
        return WatchLine(
            source=source, state=WatchState.UNVERIFIED_EXTERNAL,
            summary=fetched.summary, raw_excerpt=fetched.raw_excerpt,
            fetched_at=fetched.fetched_at, error="",
            verified_by=fetched.verified_by,
            sources=list(fetched.sources),
            verified_date=fetched.verified_date,
            verification_warning=warning,
        )

    # All preconditions satisfied. Apply unified freshness window using
    # verified_date as the anchor (D-HWFL-19): verified-and-aged-out => STALE
    # but retain all 3 fields in the WatchLine for detail rendering.
    try:
        vd = date.fromisoformat(fetched.verified_date.strip())
        age_days = (now_utc.date() - vd).days
        verified_within = age_days <= source.freshness_days
    except ValueError:
        verified_within = True  # Already guarded above; defensive belt-and-braces.

    state = WatchState.VERIFIED_EXTERNAL if verified_within else WatchState.STALE
    return WatchLine(
        source=source, state=state,
        summary=fetched.summary, raw_excerpt=fetched.raw_excerpt,
        fetched_at=fetched.fetched_at, error="",
        verified_by=fetched.verified_by,
        sources=list(fetched.sources),
        verified_date=fetched.verified_date,
    )


def assemble_watch_report(
    *,
    cycle: int,
    cycle_date: str | None = None,
    fetched: dict[str, FetchResult] | None = None,
) -> WatchReport:
    """Pure-function: takes fetched payloads keyed by topic_id, produces
    a `WatchReport`. Never raises (fetch errors materialize as
    FETCH-ERROR state in the report)."""
    now_utc = datetime.now(timezone.utc)
    iso_now = now_utc.isoformat(timespec="seconds")
    date = cycle_date or iso_now[:10]
    fetched = fetched or {}

    lines: list[WatchLine] = []
    for source in _CANONICAL_SOURCES:
        payload = fetched.get(source.topic_id)
        lines.append(_resolve_state(source, payload, now_utc))

    return WatchReport(
        cycle=cycle,
        cycle_date=date,
        generated_at=iso_now,
        lines=lines,
    )


def canonical_source_count() -> int:
    """Exposed for tests + audit assertions. v0.1 = 7."""
    return len(_CANONICAL_SOURCES)
