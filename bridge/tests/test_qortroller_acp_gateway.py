"""Phase 4 ACP Gateway — parsing, allow-list, routing, and reply discipline.

Covers docs/design/buzz-phase4-acp-grok-devin-addendum.md sections 3-6:
Grok Build is primary, Devin takes heavy work, everything outside the §5
allow-list is rejected, and no reply leaks secret-shaped text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import qortroller_acp_gateway as gw  # noqa: E402

OPERATOR = "abc123operatorpubkey"


@pytest.fixture
def cfg(tmp_path: Path) -> gw.GatewayConfig:
    return gw.GatewayConfig(
        operator_pubkeys=(OPERATOR,),
        rig_ops_channel="rig-ops-uuid",
        audit_log_path=tmp_path / "acp_gateway.jsonl",
        devin_queue_path=tmp_path / "acp_devin_queue.jsonl",
    )


# --- Parsing -----------------------------------------------------------------

def test_unaddressed_message_is_silent(cfg):
    assert gw.parse_mention("gg wp", cfg) is None
    assert gw.parse_mention("!status", cfg) is None


@pytest.mark.parametrize(
    "text,tool",
    [
        ("@EA status", gw.TOOL_RIG_STATUS),
        ("@EA rig status", gw.TOOL_RIG_STATUS),
        ("@EA invariant status", gw.TOOL_INVARIANT_GATE),
        ("@EA pv-ci", gw.TOOL_INVARIANT_GATE),
        ("@EA health", gw.TOOL_HEALTH_CHECK),
        ("@EA ceremony steps", gw.TOOL_CEREMONY_STEPS),
        ("@EA session", gw.TOOL_SESSION_SUMMARY),
        ("@EA session 581a836c", gw.TOOL_SESSION_SUMMARY),
        ("@EA diagnose retina oracle drift", gw.TOOL_DEEP_DIAGNOSE),
    ],
)
def test_allow_listed_intents_parse(cfg, text, tool):
    intent = gw.parse_mention(text, cfg)
    assert isinstance(intent, gw.Intent)
    assert intent.tool == tool
    assert intent.tool in gw.ALLOWED_TOOLS


def test_handle_match_is_case_insensitive(cfg):
    assert isinstance(gw.parse_mention("@ea HEALTH", cfg), gw.Intent)


def test_pytest_target_must_exist_under_an_allowed_root(cfg):
    ok = gw.parse_mention("@EA run pytest bridge/tests/test_qortroller_acp_gateway.py", cfg)
    assert isinstance(ok, gw.Intent)
    assert ok.args["target"] == "bridge/tests/test_qortroller_acp_gateway.py"

    for bad in (
        "@EA run pytest ../../etc/passwd",
        "@EA run pytest bridge/tests/does_not_exist.py",
        "@EA run pytest scripts/qortroller.py",
    ):
        rejection = gw.parse_mention(bad, cfg)
        assert isinstance(rejection, gw.Rejection)
        assert rejection.reason == gw.REJECT_BAD_TARGET


def test_session_id_is_sanitized(cfg):
    rejection = gw.parse_mention("@EA session ../../secret", cfg)
    assert isinstance(rejection, gw.Rejection)
    assert rejection.reason == gw.REJECT_BAD_TARGET


@pytest.mark.parametrize(
    "text",
    [
        "@EA run bash scripts/deploy.sh",
        "@EA exec rm -rf /",
        "@EA show me the wallet private key",
        "@EA deploy the controller NFT",
        "@EA dump raw hid for the last session",
        "@EA git push origin main",
    ],
)
def test_banned_surface_is_rejected(cfg, text):
    rejection = gw.parse_mention(text, cfg)
    assert isinstance(rejection, gw.Rejection)
    assert rejection.reason == gw.REJECT_BANNED


def test_unknown_command_is_rejected_not_guessed(cfg):
    rejection = gw.parse_mention("@EA make me a sandwich", cfg)
    assert isinstance(rejection, gw.Rejection)
    assert rejection.reason == gw.REJECT_UNKNOWN_INTENT


# --- Routing -----------------------------------------------------------------

def test_grok_is_primary_devin_takes_heavy_work():
    assert gw.route(gw.TOOL_RIG_STATUS) == gw.HARNESS_GROK
    assert gw.route(gw.TOOL_INVARIANT_GATE) == gw.HARNESS_GROK
    assert gw.route(gw.TOOL_RUN_PYTEST) == gw.HARNESS_GROK
    assert gw.route(gw.TOOL_DEEP_DIAGNOSE) == gw.HARNESS_DEVIN


def test_explicit_devin_keyword_routes_to_devin(cfg):
    intent = gw.parse_mention("@EA devin run pytest bridge/tests/test_qortroller_acp_gateway.py", cfg)
    assert isinstance(intent, gw.Intent)
    assert intent.explicit_devin is True
    assert intent.harness == gw.HARNESS_DEVIN


def test_read_only_tools_stay_on_grok_even_when_devin_is_named(cfg):
    intent = gw.parse_mention("@EA devin status", cfg)
    assert isinstance(intent, gw.Intent)
    assert intent.harness == gw.HARNESS_GROK


# --- Authorization -----------------------------------------------------------

def test_empty_operator_allow_list_is_fail_closed():
    assert gw.authorize(OPERATOR, gw.GatewayConfig()) is False


def test_only_allow_listed_pubkeys_are_authorized(cfg):
    assert gw.authorize(OPERATOR, cfg) is True
    assert gw.authorize(OPERATOR.upper(), cfg) is True
    assert gw.authorize("someone-else", cfg) is False


def test_unauthorized_pubkey_never_executes(cfg, monkeypatch):
    called: list[str] = []
    monkeypatch.setattr(gw, "execute", lambda intent, c: called.append(intent.tool))
    reply = gw.handle_message("stranger", "@EA health", cfg)
    assert reply is not None
    assert "rejected" in reply[0]
    assert called == []


# --- Execution ---------------------------------------------------------------

def test_ceremony_steps_are_checklist_only(cfg):
    intent = gw.parse_mention("@EA ceremony", cfg)
    result = gw.execute(intent, cfg)
    assert result.ok is True
    assert "operator-fired" in result.summary
    assert "estimate" in result.summary.lower()


def test_deep_diagnose_queues_for_devin_without_claiming_a_result(cfg):
    intent = gw.parse_mention("@EA diagnose bridge capture lag", cfg)
    result = gw.execute(intent, cfg)
    assert result.harness == gw.HARNESS_DEVIN
    assert "queued" in result.summary
    record = json.loads(cfg.devin_queue_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["status"] == "queued"
    assert record["topic"] == "bridge capture lag"


def test_execute_refuses_a_tool_outside_the_allow_list(cfg):
    result = gw.execute(gw.Intent("run_shell", {}), cfg)
    assert result.ok is False
    assert "not allow-listed" in result.summary


def test_dry_run_executes_nothing(cfg, monkeypatch):
    monkeypatch.setattr(
        gw, "_run", lambda *a, **k: pytest.fail("dry run must not spawn a process")
    )
    dry = gw.GatewayConfig(**{**cfg.__dict__, "dry_run": True})
    intent = gw.parse_mention("@EA invariant status", dry)
    result = gw.execute(intent, dry)
    assert result.ok is True
    assert "dry-run" in result.summary


def test_invariant_gate_reports_the_live_count(cfg, monkeypatch):
    monkeypatch.setattr(
        gw, "_run", lambda argv, c, t: (0, "[invariant_gate] PASS — 188 invariants verified.")
    )
    intent = gw.parse_mention("@EA invariant status", cfg)
    result = gw.execute(intent, cfg)
    assert result.ok is True
    assert result.summary == "PV-CI PASS — 188 invariants"
    assert ["pv_ci", "188"] in result.tags


def test_invariant_gate_failure_is_reported_honestly(cfg, monkeypatch):
    monkeypatch.setattr(gw, "_run", lambda argv, c, t: (1, "FAIL — 187 invariants verified."))
    result = gw.execute(gw.parse_mention("@EA invariant", cfg), cfg)
    assert result.ok is False
    assert "FAIL" in result.summary


def test_pytest_summary_extraction(cfg, monkeypatch):
    monkeypatch.setattr(
        gw,
        "_run",
        lambda argv, c, t: (0, "....\n16 passed, 1 skipped in 2.10s\n"),
    )
    intent = gw.parse_mention("@EA run pytest bridge/tests/test_qortroller_acp_gateway.py", cfg)
    result = gw.execute(intent, cfg)
    assert "16 passed" in result.summary


def test_run_uses_a_fixed_argv_without_a_shell(cfg, monkeypatch):
    seen: dict = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs

        class R:
            returncode = 0
            stdout = "1 passed in 0.01s"
            stderr = ""

        return R()

    monkeypatch.setattr(gw.subprocess, "run", fake_run)
    gw.execute(
        gw.parse_mention("@EA run pytest bridge/tests/test_qortroller_acp_gateway.py", cfg), cfg
    )
    assert seen["kwargs"]["shell"] is False
    assert isinstance(seen["argv"], list)
    assert seen["argv"][1:3] == ["-m", "pytest"]


# --- Reply discipline --------------------------------------------------------

def test_reply_is_scrubbed_and_bounded(cfg):
    secret = "BUZZ_PRIVATE_KEY=nsec1qqqqqqqqqqqqqqqqqqqqqqqq"
    result = gw.ToolResult(gw.TOOL_HEALTH_CHECK, gw.HARNESS_GROK, True, secret + " x" * 600)
    content, _ = gw.format_reply(result, cfg)
    assert "nsec1qqq" not in content
    assert "[redacted" in content
    assert len(content) <= cfg.max_reply_chars + len("[grok-build] ")


def test_reply_never_carries_a_caller_supplied_h_tag(cfg):
    result = gw.ToolResult(
        gw.TOOL_RIG_STATUS, gw.HARNESS_GROK, True, "rig: idle", [["h", "injected"]]
    )
    _, tags = gw.format_reply(result, cfg)
    assert all(tag[0] != "h" for tag in tags)
    assert ["acp", "1"] in tags
    assert ["harness", gw.HARNESS_GROK] in tags


# --- Audit trail -------------------------------------------------------------

def test_every_invocation_is_audited_locally(cfg):
    gw.handle_message(OPERATOR, "@EA ceremony", cfg)
    lines = cfg.audit_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["tool"] == gw.TOOL_CEREMONY_STEPS
    assert record["harness"] == gw.HARNESS_GROK
    assert record["pubkey"] == OPERATOR


def test_rejections_are_audited(cfg):
    gw.handle_message(OPERATOR, "@EA exec rm -rf /", cfg)
    record = json.loads(cfg.audit_log_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["rejected"] == gw.REJECT_BANNED


def test_audit_records_are_scrubbed(cfg):
    gw.handle_message(OPERATOR, "@EA BUZZ_PRIVATE_KEY=nsec1abcdefg", cfg)
    raw = cfg.audit_log_path.read_text(encoding="utf-8")
    assert "nsec1abcdefg" not in raw


def test_unaddressed_message_produces_no_audit_entry(cfg):
    assert gw.handle_message(OPERATOR, "just chatting", cfg) is None
    assert not cfg.audit_log_path.exists()
