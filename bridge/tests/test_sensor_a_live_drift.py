"""HWFL-1 Sensor A v0.2 tests — live-state drift detection.

Pure-function module tests; runner not exercised (subprocess +
network are out of scope for the sensor module's contract).
"""
from __future__ import annotations

from bridge.vapi_bridge.sensor_a_live_drift import (
    DriftState,
    LiveFetchResult,
    assemble_drift_report,
    parse_anchors,
)


CLAUDE_MD_HAPPY = """
Some prose.

<!-- SENSOR-A-LIVE:WALLET balance_iotx=32.078372 as_of=2026-06-10 -->
<!-- SENSOR-A-LIVE:CONTRACTS count=49 as_of=2026-06-10 -->
<!-- SENSOR-A-LIVE:TESTS bridge=4330 sdk=604 hardhat_regex_scan=674 as_of=2026-06-10 -->

More prose.
"""


def _fetch_happy() -> LiveFetchResult:
    return LiveFetchResult(
        wallet_balance_iotx=32.078372,
        contract_count=49,
        test_counts={"bridge": 4330, "sdk": 604, "hardhat_regex_scan": 674},
    )


# ---------------------------------------------------------------------- T1
def test_parse_anchors_extracts_all_three():
    anchors = parse_anchors(CLAUDE_MD_HAPPY)
    assert set(anchors.keys()) == {"WALLET", "CONTRACTS", "TESTS"}
    assert anchors["WALLET"]["balance_iotx"] == "32.078372"
    assert anchors["WALLET"]["as_of"] == "2026-06-10"
    assert anchors["CONTRACTS"]["count"] == "49"
    assert anchors["TESTS"]["bridge"] == "4330"


# ---------------------------------------------------------------------- T2
def test_happy_path_all_aligned():
    report = assemble_drift_report(CLAUDE_MD_HAPPY, _fetch_happy())
    assert len(report.lines) == 3
    states = [ln.state for ln in report.lines]
    assert states == [DriftState.ALIGNED, DriftState.ALIGNED, DriftState.ALIGNED]


# ---------------------------------------------------------------------- T3
def test_wallet_within_tolerance_aligned():
    # 0.4 IOTX delta — under 0.5 tolerance, ALIGNED
    fetch = LiveFetchResult(
        wallet_balance_iotx=32.478372,
        contract_count=49,
        test_counts={"bridge": 4330, "sdk": 604, "hardhat_regex_scan": 674},
    )
    report = assemble_drift_report(CLAUDE_MD_HAPPY, fetch)
    wallet_line = next(ln for ln in report.lines if ln.probe_id == "P-WALLET")
    assert wallet_line.state == DriftState.ALIGNED


# ---------------------------------------------------------------------- T4
def test_wallet_beyond_tolerance_drifted():
    # 5 IOTX delta — well beyond tolerance, DRIFTED (F-HWFL-4-1 class)
    fetch = LiveFetchResult(
        wallet_balance_iotx=27.0,
        contract_count=49,
        test_counts={"bridge": 4330, "sdk": 604, "hardhat_regex_scan": 674},
    )
    report = assemble_drift_report(CLAUDE_MD_HAPPY, fetch)
    wallet_line = next(ln for ln in report.lines if ln.probe_id == "P-WALLET")
    assert wallet_line.state == DriftState.DRIFTED
    assert "exceeds" in wallet_line.evidence


# ---------------------------------------------------------------------- T5
def test_contract_off_by_one_drifted():
    fetch = LiveFetchResult(
        wallet_balance_iotx=32.078372,
        contract_count=50,  # +1 contract deployed since CLAUDE.md update
        test_counts={"bridge": 4330, "sdk": 604, "hardhat_regex_scan": 674},
    )
    report = assemble_drift_report(CLAUDE_MD_HAPPY, fetch)
    contract_line = next(ln for ln in report.lines if ln.probe_id == "P-CONTRACT")
    assert contract_line.state == DriftState.DRIFTED
    assert "delta=+1" in contract_line.evidence


# ---------------------------------------------------------------------- T6
def test_tests_any_suite_off_is_drifted():
    fetch = LiveFetchResult(
        wallet_balance_iotx=32.078372,
        contract_count=49,
        test_counts={"bridge": 4335, "sdk": 604, "hardhat_regex_scan": 674},  # bridge +5
    )
    report = assemble_drift_report(CLAUDE_MD_HAPPY, fetch)
    test_line = next(ln for ln in report.lines if ln.probe_id == "P-TESTS")
    assert test_line.state == DriftState.DRIFTED
    assert "bridge:+5" in test_line.evidence


# ---------------------------------------------------------------------- T7
def test_missing_anchor_unverifiable_not_drifted():
    md = "no anchors here at all"
    report = assemble_drift_report(md, _fetch_happy())
    for ln in report.lines:
        assert ln.state == DriftState.UNVERIFIABLE
        assert "not found" in ln.evidence


# ---------------------------------------------------------------------- T8
def test_fetch_error_unverifiable_not_drifted():
    fetch = LiveFetchResult(
        wallet_balance_iotx=None,
        wallet_fetch_error="HTTP 502 from babel-api",
        contract_count=None,
        contract_fetch_error="deployed-addresses.json not found",
        test_counts=None,
        test_fetch_error="pytest timed out",
    )
    report = assemble_drift_report(CLAUDE_MD_HAPPY, fetch)
    for ln in report.lines:
        assert ln.state == DriftState.UNVERIFIABLE
        assert "fetch error" in ln.evidence


# ---------------------------------------------------------------------- T9
def test_malformed_anchor_value_unverifiable():
    md = """
<!-- SENSOR-A-LIVE:WALLET balance_iotx=not_a_number as_of=2026-06-10 -->
<!-- SENSOR-A-LIVE:CONTRACTS count=forty-nine as_of=2026-06-10 -->
<!-- SENSOR-A-LIVE:TESTS bridge=abc sdk=604 hardhat_regex_scan=674 as_of=2026-06-10 -->
"""
    report = assemble_drift_report(md, _fetch_happy())
    for ln in report.lines:
        assert ln.state == DriftState.UNVERIFIABLE
        assert "parseable" in ln.evidence


# ---------------------------------------------------------------------- T10
def test_adversarial_anchor_html_pipe_escape():
    # Adversarial anchor injection — should not break the markdown table.
    # The anchor regex stops at `>`, so a `>` inside the body terminates
    # early; we mainly verify that the *rendered* markdown is safe.
    md = """
<!-- SENSOR-A-LIVE:WALLET balance_iotx=32.0 as_of=2026|06|10 -->
<!-- SENSOR-A-LIVE:CONTRACTS count=49 as_of=2026-06-10 -->
<!-- SENSOR-A-LIVE:TESTS bridge=4330 sdk=604 hardhat_regex_scan=674 as_of=2026-06-10 -->
"""
    report = assemble_drift_report(md, _fetch_happy())
    md_out = report.to_markdown()
    # Pipe in as_of must be escaped in the rendered table cell
    assert "2026\\|06\\|10" in md_out
    # No unescaped active markup or unescaped pipe in cell content
    assert "<script>" not in md_out


# ---------------------------------------------------------------------- T11
def test_to_markdown_renders_distribution_summary():
    fetch = LiveFetchResult(
        wallet_balance_iotx=27.0,  # DRIFTED
        contract_count=49,         # ALIGNED
        test_counts=None,          # UNVERIFIABLE
        test_fetch_error="skipped",
    )
    report = assemble_drift_report(CLAUDE_MD_HAPPY, fetch)
    md = report.to_markdown()
    assert "ALIGNED=1" in md
    assert "DRIFTED=1" in md
    assert "UNVERIFIABLE=1" in md
    assert "| P-WALLET |" in md


# ---------------------------------------------------------------------- T12
def test_fail_open_never_spurious_drifted():
    # When everything is missing / errored, no probe must be DRIFTED.
    # DRIFTED requires positive evidence that live != claimed; absence
    # of either side is always UNVERIFIABLE.
    md_no_anchors = "nothing here"
    fetch_no_live = LiveFetchResult()
    report = assemble_drift_report(md_no_anchors, fetch_no_live)
    for ln in report.lines:
        assert ln.state != DriftState.DRIFTED
