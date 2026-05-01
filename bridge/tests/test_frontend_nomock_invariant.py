"""Frontend grind-critical hook `noMock` invariant test.

The 2026-04-26 dashboard audit found `useFleetCoherenceStatus` silently rendering
mock data because `/agent/fleet-coherence-status` (the path the hook called) was
404'd at the bridge — the `get()` helper's mock fallback path then activated and
fabricated values were shown during an active grind. Operators saw `chain_length`
flip-flopping between mock fakes and live values on every poll cycle.

The fix added `noMock: true` to nine grind-critical hooks in
`frontend/src/api/bridgeApi.js`. This test pins that fix: any future edit
that drops `noMock: true` from a known grind-critical path fails CI.

Mechanism: pure text-grep over `bridgeApi.js`. No vitest, no jsdom, no
toolchain expansion — runs in the existing pytest suite. Catches the
specific failure mode that already cost a production cycle. Does NOT
catch component-level regressions (banner display, retry behavior, etc.) —
those would require the heavier vitest + RTL toolchain and are deferred.

T-NM-1: every string-literal grind-critical path passes { noMock: true }
T-NM-2: at least one non-grind-critical path omits noMock (negative control)
T-NM-3: get() helper enforces the noMock short-circuit ordering
T-NM-4: useConsentStatus (dynamic path construction) passes { noMock: true }
"""
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BRIDGE_API = _REPO_ROOT / "frontend" / "src" / "api" / "bridgeApi.js"

# Frozen list of grind-critical bridge paths declared with STRING-LITERAL
# arguments to get(). A path is grind-critical when its data drives the
# GamerView/DeveloperView during an active grind and fabricated mock values
# would mislead the operator (the 2026-04-26 incident).
#
# Adding/removing from this list is a deliberate architectural decision —
# this test list and the `noMock: true` flags in bridgeApi.js must move
# together. The dynamic-path consent hook is asserted separately in T-NM-4.
_GRIND_CRITICAL_PATHS = frozenset({
    "/agent/fleet-coherence-summary",   # active contradiction count (FSCA)
    "/agent/auto-trigger-status",        # session boundary detector throttle
    "/bridge/capture-health",            # PCC live state
    "/bridge/grind-chain-status",        # GIC chain integrity
    "/agent/ait-separation-status",      # AIT corpus defensibility
    "/grind/analytics",                  # GIC_100 ETA + sessions/day
    "/grind/pcc-intelligence",           # BT contention episode counts
    "/operator/watchdog-status",         # WEC chain integrity
})


def _load_bridge_api_source() -> str:
    if not _BRIDGE_API.exists():
        pytest.skip(f"bridgeApi.js not found at {_BRIDGE_API}")
    return _BRIDGE_API.read_text(encoding="utf-8")


def _extract_get_calls(src: str):
    """Return [(bare_path, opts_text, full_match)] for each get('<lit>', ...) call.

    Matches both single-quote string literals and backtick templates whose
    first character is '/' (the bridge path prefix). Identifier-arg calls
    like `get(path, ...)` are not matched here — those are tested separately.
    """
    pattern = re.compile(
        r"get\(\s*"
        r"(?P<path>'[^']*'|`/[^`]*`)\s*,"      # path: string literal or template starting with /
        r"\s*'[^']*'"                           # mockKey: string literal
        r"(?:\s*,\s*\{(?P<opts>[^}]*)\})?"      # optional third arg: opts object
        r"\s*\)",
        re.MULTILINE,
    )
    out = []
    for m in pattern.finditer(src):
        raw = m.group("path").strip("'`")
        # Template literal — take static prefix before any ${ interpolation
        if "${" in raw:
            raw = raw.split("${")[0].rstrip("?&")
        bare = raw.split("?")[0]
        out.append((bare, m.group("opts") or "", m.group(0)))
    return out


# ---------------------------------------------------------------------------
# T-NM-1: every grind-critical path passes { noMock: true }
# ---------------------------------------------------------------------------

def test_t_nm_1_grind_critical_paths_have_nomock_true():
    src = _load_bridge_api_source()
    calls = _extract_get_calls(src)
    found_paths = {p for p, _, _ in calls}

    # Discovery sanity — every canonical path is actually present in the source
    missing = _GRIND_CRITICAL_PATHS - found_paths
    assert not missing, (
        f"Grind-critical paths declared in this test but absent from bridgeApi.js: "
        f"{sorted(missing)}. Either restore the canonical path name in bridgeApi.js, "
        f"or remove it from _GRIND_CRITICAL_PATHS with explicit reasoning."
    )

    # Invariant — every grind-critical call must pass noMock: true
    violations = []
    for path, opts, full in calls:
        if path not in _GRIND_CRITICAL_PATHS:
            continue
        normalized = re.sub(r"\s+", "", opts)
        if "noMock:true" not in normalized:
            violations.append((path, full.strip()[:140]))

    assert not violations, (
        "Grind-critical hooks missing `noMock: true`:\n"
        + "\n".join(f"  {p}\n    {snippet}" for p, snippet in violations)
        + "\n\nThis is the failure mode of the 2026-04-26 dashboard audit "
        "(useFleetCoherenceStatus silently rendered mock data because mock fallback "
        "fired on a transient bridge error). Either restore `noMock: true`, or move "
        "this path out of _GRIND_CRITICAL_PATHS with deliberate operator approval."
    )


# ---------------------------------------------------------------------------
# T-NM-2: negative control — non-grind-critical paths CAN omit noMock
# ---------------------------------------------------------------------------

def test_t_nm_2_non_critical_paths_can_omit_nomock():
    """If every hook were noMock: true, first-load discovery before the bridge
    is reachable would never show anything — mock fallback is the bootstrap UX.
    This test guards against an over-correction that would force noMock onto
    every hook and break that path."""
    src = _load_bridge_api_source()
    calls = _extract_get_calls(src)

    non_critical_without_nomock = [
        (p, full) for p, opts, full in calls
        if p not in _GRIND_CRITICAL_PATHS
        and "noMock" not in re.sub(r"\s+", "", opts)
    ]
    assert non_critical_without_nomock, (
        "Expected at least one non-grind-critical hook to omit noMock "
        "(needed for first-load discovery before bridge is reachable). "
        "Found none — either every path is now grind-critical (architectural "
        "shift requiring deliberate review), or the regex is over-matching."
    )


# ---------------------------------------------------------------------------
# T-NM-3: get() helper enforces the noMock short-circuit ordering
# ---------------------------------------------------------------------------

def test_t_nm_3_get_helper_short_circuit_ordering():
    """The single seam every grind-critical hook relies on. If `if (opts.noMock)
    throw err` is removed or moved AFTER `activateMock()`, the rethrow no longer
    short-circuits and mock fakes leak in despite the call-site flag."""
    src = _load_bridge_api_source()

    m = re.search(r"async function get\([^)]*\)\s*\{", src)
    assert m, "Could not locate `async function get(` in bridgeApi.js"
    body_start = m.end()

    # Take a generous window after the function start — enough to span the
    # try/catch but not so much that we cross into the next exported function.
    body_window = src[body_start:body_start + 2000]

    # Required: opts.noMock check appears
    nomock_match = re.search(r"if\s*\(\s*opts\.noMock\s*\)", body_window)
    assert nomock_match, (
        "get() helper missing `if (opts.noMock)` guard — the noMock invariant "
        "has no enforcement seam. Restore the rethrow path in the catch block."
    )

    # Required: activateMock() exists and comes AFTER the opts.noMock check.
    # Word boundary needed — `deactivateMock()` (the success-path reset call)
    # contains `activateMock()` as a substring and would match without \b.
    activate_match = re.search(r"\bactivateMock\(\)", body_window)
    assert activate_match, "get() helper missing activateMock() — mock fallback path absent"
    assert activate_match.start() > nomock_match.start(), (
        "activateMock() appears BEFORE the opts.noMock guard in get(). "
        "If reordered this way, the noMock rethrow no longer short-circuits "
        "and grind-critical hooks would still receive mock fakes on transient errors."
    )


# ---------------------------------------------------------------------------
# T-NM-4: useConsentStatus (dynamic path) passes { noMock: true }
# ---------------------------------------------------------------------------

def test_t_nm_4_use_consent_status_passes_nomock():
    """useConsentStatus builds its path dynamically from device_id + category,
    so it doesn't match T-NM-1's string-literal regex. Pinned separately by
    finding the function body and asserting both the canonical path prefix
    and `noMock: true` appear inside it."""
    src = _load_bridge_api_source()

    # Find the function body — from `function useConsentStatus(` to the matching
    # closing brace at column 0 (}). Tolerant of arg list formatting changes.
    m = re.search(
        r"function useConsentStatus\([^)]*\)\s*\{(?P<body>.*?)\n\}",
        src,
        re.DOTALL,
    )
    assert m, "useConsentStatus not found in bridgeApi.js"
    body = m.group("body")

    assert "/agent/gamer-consent-status" in body, (
        "useConsentStatus body no longer references /agent/gamer-consent-status. "
        "Either the canonical bridge path was renamed (update _GRIND_CRITICAL_PATHS "
        "and this test together) or the hook was deleted."
    )
    normalized = re.sub(r"\s+", "", body)
    assert "noMock:true" in normalized, (
        "useConsentStatus body no longer passes `noMock: true` to get(). "
        "Per-category consent state is privacy data; mock fakes would mislead. "
        "Restore noMock or move the hook out of grind-critical scope with "
        "deliberate operator approval."
    )
