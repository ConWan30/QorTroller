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
        plans_path=tmp_path / "acp_plans.jsonl",
        devin_results_path=tmp_path / "acp_devin_results.jsonl",
        seals_path=tmp_path / "acp_sap_seals.jsonl",
        challenges_path=tmp_path / "acp_sap_challenges.jsonl",
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
        ("@EA failing tests", gw.TOOL_LIST_FAILING_TESTS),
        ("@EA failing", gw.TOOL_LIST_FAILING_TESTS),
        ("@EA repo health", gw.TOOL_REPO_HEALTH),
        ("@EA wp acp", gw.TOOL_SHOW_WP_STATUS),
        ("@EA workpackage vss", gw.TOOL_SHOW_WP_STATUS),
        ("@EA plan full check", gw.TOOL_PLAN),
        ("@EA plan investigate bridge lag", gw.TOOL_PLAN),
        ("@EA confirm plan abcdef", gw.TOOL_CONFIRM_PLAN),
        ("@EA diagnose status", gw.TOOL_DIAGNOSE_STATUS),
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
    # EA-ACP-1: priority defaults to normal, repo_sha_hint present in real repo
    assert record["priority"] == "normal"
    assert "repo_sha_hint" in record
    assert record["repo_sha_hint"]
    assert ["ticket", str(record["ts"])] in result.tags


def test_deep_diagnose_parses_acceptance_and_priority(cfg):
    intent = gw.parse_mention(
        "@EA diagnose failing vss tests | acceptance tests green | priority high", cfg
    )
    result = gw.execute(intent, cfg)
    record = json.loads(cfg.devin_queue_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["topic"] == "failing vss tests"
    assert record["acceptance"] == "tests green"
    assert record["priority"] == "high"
    assert "high" in [t[1] for t in result.tags if t[0] == "priority"]
    assert "acceptance: tests green" in result.summary


def test_deep_diagnose_keeps_unknown_pipe_segments_in_topic(cfg):
    intent = gw.parse_mention("@EA diagnose lag | please hurry", cfg)
    result = gw.execute(intent, cfg)
    assert result.ok is True
    record = json.loads(cfg.devin_queue_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["topic"] == "lag | please hurry"
    assert "acceptance" not in record
    assert record["priority"] == "normal"


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


# --- EA-ACP-2 engineering read tools -----------------------------------------

def test_list_failing_tests_no_cache(cfg, tmp_path: Path):
    # Use a clean temp repo so the real .pytest_cache is not visible.
    cfg = gw.GatewayConfig(
        operator_pubkeys=cfg.operator_pubkeys,
        rig_ops_channel=cfg.rig_ops_channel,
        audit_log_path=cfg.audit_log_path,
        devin_queue_path=cfg.devin_queue_path,
        repo_root=tmp_path,
    )
    result = gw.execute(gw.parse_mention("@EA failing", cfg), cfg)
    assert result.ok is True
    assert "no cache" in result.summary
    assert ["count", "0"] in result.tags


def test_list_failing_tests_with_cache(cfg, tmp_path: Path, monkeypatch):
    # Point repo_root to a temp tree so we can safely write a fake pytest cache.
    cfg = gw.GatewayConfig(
        operator_pubkeys=cfg.operator_pubkeys,
        rig_ops_channel=cfg.rig_ops_channel,
        audit_log_path=cfg.audit_log_path,
        devin_queue_path=cfg.devin_queue_path,
        repo_root=tmp_path,
    )
    cache = tmp_path / ".pytest_cache" / "v" / "cache" / "lastfailed"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"bridge/tests/test_x.py::test_a": 1}), encoding="utf-8")
    result = gw.execute(gw.parse_mention("@EA failing", cfg), cfg)
    assert result.ok is True
    assert "1" in result.summary
    assert "bridge/tests/test_x.py::test_a" in result.summary
    assert ["count", "1"] in result.tags


def test_repo_health_composes_health_and_pvci(cfg, monkeypatch):
    def _tool_health_check(intent, c):
        return gw.ToolResult(
            gw.TOOL_HEALTH_CHECK, gw.HARNESS_GROK, True, "health — ea: ok", [["healthy", "true"]]
        )

    def _tool_invariant_gate(intent, c):
        return gw.ToolResult(
            gw.TOOL_INVARIANT_GATE,
            gw.HARNESS_GROK,
            True,
            "PV-CI PASS — 188 invariants",
            [["pv_ci", "188"], ["verdict", "PASS"]],
        )

    monkeypatch.setattr(gw, "_tool_health_check", _tool_health_check)
    monkeypatch.setattr(gw, "_tool_invariant_gate", _tool_invariant_gate)
    result = gw.execute(gw.parse_mention("@EA repo health", cfg), cfg)
    assert result.ok is True
    assert "health —" in result.summary
    assert "PV-CI PASS" in result.summary
    assert ["verdict", "PASS"] in result.tags


def test_repo_health_fail_if_either_part_fails(cfg, monkeypatch):
    def _tool_health_check(intent, c):
        return gw.ToolResult(
            gw.TOOL_HEALTH_CHECK, gw.HARNESS_GROK, True, "health — ea: ok", [["healthy", "true"]]
        )

    def _tool_invariant_gate(intent, c):
        return gw.ToolResult(
            gw.TOOL_INVARIANT_GATE,
            gw.HARNESS_GROK,
            False,
            "PV-CI FAIL — 187 invariants",
            [["pv_ci", "187"], ["verdict", "FAIL"]],
        )

    monkeypatch.setattr(gw, "_tool_health_check", _tool_health_check)
    monkeypatch.setattr(gw, "_tool_invariant_gate", _tool_invariant_gate)
    result = gw.execute(gw.parse_mention("@EA repo health", cfg), cfg)
    assert result.ok is False
    assert ["verdict", "FAIL"] in result.tags


def test_show_wp_status_reads_allowed_doc(cfg):
    result = gw.execute(gw.parse_mention("@EA wp acp", cfg), cfg)
    assert result.ok is True
    assert result.summary.startswith("wp acp:")
    assert ["found", "true"] in result.tags
    assert int(next(t[1] for t in result.tags if t[0] == "headings")) > 0


def test_show_wp_status_rejects_unknown_slug(cfg):
    rejection = gw.parse_mention("@EA wp ../../secret", cfg)
    assert isinstance(rejection, gw.Rejection)
    assert rejection.reason == gw.REJECT_BAD_TARGET


# --- EA-ACP-3 plan / confirm -------------------------------------------------

def test_plan_creates_a_pending_record(cfg):
    result = gw.execute(gw.parse_mention("@EA plan full check", cfg), cfg)
    assert result.ok is True
    plan_id = next(t[1] for t in result.tags if t[0] == "plan_id")
    assert len(plan_id) == 6
    lines = cfg.plans_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    assert record["plan_id"] == plan_id
    assert record["status"] == "pending"
    assert record["goal"] == "full check"
    assert len(record["steps"]) == 2


def test_plan_unknown_goal_falls_back_to_diagnose(cfg):
    result = gw.execute(gw.parse_mention("@EA plan investigate bridge lag", cfg), cfg)
    assert result.ok is True
    lines = cfg.plans_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    assert record["steps"][0]["tool"] == gw.TOOL_DEEP_DIAGNOSE
    assert record["steps"][0]["args"]["topic"] == "investigate bridge lag"


def test_confirm_executes_staged_plan(cfg, monkeypatch):
    # Use a one-step plan with a mocked tool.
    def _fake_tool(intent, c):
        return gw.ToolResult(
            gw.TOOL_HEALTH_CHECK, gw.HARNESS_GROK, True, "health — ea: ok", [["healthy", "true"]]
        )

    monkeypatch.setattr(gw, "_tool_health_check", _fake_tool)
    plan_record = {
        "ts": 1,
        "plan_id": "abc123",
        "goal": "acp health",
        "status": "pending",
        "steps": [{"tool": gw.TOOL_HEALTH_CHECK, "args": {}}],
    }
    gw._append_jsonl(cfg.plans_path, plan_record)
    result = gw.execute(gw.parse_mention("@EA confirm plan abc123", cfg), cfg)
    assert result.ok is True
    assert ["status", "completed"] in result.tags
    assert ["steps_ok", "true"] in result.tags
    assert "health" in result.summary


def test_confirm_refuses_unknown_plan_id(cfg):
    result = gw.execute(gw.parse_mention("@EA confirm plan deadbeef", cfg), cfg)
    assert result.ok is False
    assert "not found" in result.summary


def test_diagnose_status_reads_local_results(cfg):
    result = gw.execute(gw.parse_mention("@EA diagnose status", cfg), cfg)
    assert result.ok is True
    assert "no results yet" in result.summary


def test_diagnose_status_shows_latest_results(cfg):
    cfg.devin_results_path.parent.mkdir(parents=True, exist_ok=True)
    gw._append_jsonl(
        cfg.devin_results_path,
        {
            "ts": 1,
            "topic": "vss helper",
            "status": "done",
            "pr_url": "https://github.com/ConWan30/QorTroller/pull/999",
            "summary": "fixed race",
        },
    )
    gw._append_jsonl(
        cfg.devin_results_path,
        {
            "ts": 2,
            "topic": "acp parser",
            "status": "done",
            "pr_url": "",
            "summary": "tightened regex",
        },
    )
    result = gw.execute(gw.parse_mention("@EA diagnose status", cfg), cfg)
    assert result.ok is True
    assert "acp parser" in result.summary
    assert "vss helper" in result.summary
    assert ["count", "2"] in result.tags


def test_parse_job_status(cfg):
    intent = gw.parse_mention("@EA job status sap_abc123", cfg)
    assert isinstance(intent, gw.Intent)
    assert intent.tool == gw.TOOL_GET_JOB_STATUS
    assert intent.args["job_id"] == "sap_abc123"


def test_parse_sap_status_alias(cfg):
    intent = gw.parse_mention("@EA sap status sap_xyz", cfg)
    assert isinstance(intent, gw.Intent)
    assert intent.tool == gw.TOOL_GET_JOB_STATUS
    assert intent.args["job_id"] == "sap_xyz"


def test_get_job_status_unknown_job(cfg):
    result = gw.execute(gw.parse_mention("@EA job status sap_nonexistent", cfg), cfg)
    assert result.ok is True
    assert "unknown job" in result.summary
    assert ["status", "unknown"] in result.tags


def test_get_job_status_shows_queue_result_and_seal(cfg):
    job_id = "sap_testjob001"
    gw._append_jsonl(cfg.devin_queue_path, {"ts": 1, "job_id": job_id, "topic": "capture lag", "status": "queued"})
    gw._append_jsonl(cfg.devin_results_path, {"ts": 2, "job_id": job_id, "topic": "capture lag", "status": "done", "pr_url": "https://github.com/ConWan30/QorTroller/pull/125", "summary": "fixed latency"})
    gw._append_jsonl(cfg.seals_path, {"ts": 3, "job_id": job_id, "verdict": "accept", "ref": "https://github.com/ConWan30/QorTroller/pull/125", "note": "merged", "operator": "local"})
    result = gw.execute(gw.parse_mention(f"@EA job status {job_id}", cfg), cfg)
    assert result.ok is True
    assert "queued" in result.summary
    assert "done" in result.summary
    assert "sealed: accept" in result.summary
    assert "pr:" in result.summary


def test_parse_challenge_job(cfg):
    intent = gw.parse_mention("@EA challenge job sap_abc123 pytest bridge/tests/test_qortroller_acp_gateway.py", cfg)
    assert isinstance(intent, gw.Intent)
    assert intent.tool == gw.TOOL_CHALLENGE_JOB
    assert intent.args["job_id"] == "sap_abc123"
    assert "pytest" in intent.args["demand"]


def test_parse_challenge_without_job_keyword(cfg):
    intent = gw.parse_mention("@EA challenge sap_abc123 invariant", cfg)
    assert intent.tool == gw.TOOL_CHALLENGE_JOB
    assert intent.args["demand"] == "invariant"


def test_challenge_job_appends_record(cfg):
    result = gw.execute(
        gw.parse_mention("@EA challenge sap_abc123 pytest bridge/tests/test_qortroller_acp_gateway.py", cfg),
        cfg,
    )
    assert result.ok is True
    assert result.job_id == "sap_abc123"
    lines = cfg.challenges_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    assert record["job_id"] == "sap_abc123"
    assert record["demand"] == "pytest bridge/tests/test_qortroller_acp_gateway.py"
    assert record["status"] == "open"


def test_get_job_status_shows_plan_when_no_queue(cfg):
    job_id = "sap_planjob002"
    gw._append_jsonl(cfg.plans_path, {"ts": 1, "plan_id": "abc123", "job_id": job_id, "goal": "acp health", "status": "pending", "steps": []})
    result = gw.execute(gw.parse_mention(f"@EA job status {job_id}", cfg), cfg)
    assert result.ok is True
    assert "planned" in result.summary
    assert "acp health" in result.summary


def test_new_job_id_format():
    job_id = gw._new_job_id()
    assert job_id.startswith("sap_")
    parts = job_id.split("_")
    assert len(parts) == 3
    assert all(p for p in parts)


def test_diagnose_queue_record_has_job_id(cfg):
    gw.handle_message(OPERATOR, "@EA diagnose example topic", cfg)
    lines = cfg.devin_queue_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    assert record["job_id"].startswith("sap_")


def test_diagnose_audit_row_has_job_id(cfg):
    gw.handle_message(OPERATOR, "@EA diagnose example topic", cfg)
    lines = cfg.audit_log_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    assert record["job_id"].startswith("sap_")


def test_diagnose_reply_includes_job_tag(cfg):
    content, tags = gw.handle_message(OPERATOR, "@EA diagnose example topic", cfg)
    job_tag = next((t for t in tags if t[0] == "job"), None)
    assert job_tag is not None
    assert job_tag[1].startswith("sap_")
    assert "job:" in content


def test_plan_record_has_job_id(cfg):
    result = gw.execute(gw.parse_mention("@EA plan full check", cfg), cfg)
    plan_id = result.tags[[t[0] for t in result.tags].index("plan_id")][1]
    lines = cfg.plans_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[0])
    assert record["job_id"] == f"sap_{plan_id}"
    assert result.job_id == record["job_id"]


def test_confirm_plan_record_includes_job_id(cfg, monkeypatch):
    def _fake_tool(intent, c):
        return gw.ToolResult(
            gw.TOOL_HEALTH_CHECK, gw.HARNESS_GROK, True, "health — ea: ok", [["healthy", "true"]]
        )

    monkeypatch.setattr(gw, "_tool_health_check", _fake_tool)
    plan_record = {
        "ts": 1,
        "plan_id": "abc123",
        "job_id": "sap_abc123",
        "goal": "acp health",
        "status": "pending",
        "steps": [{"tool": gw.TOOL_HEALTH_CHECK, "args": {}}],
    }
    gw._append_jsonl(cfg.plans_path, plan_record)
    result = gw.execute(gw.parse_mention("@EA confirm plan abc123", cfg), cfg)
    assert result.job_id == "sap_abc123"
    lines = cfg.plans_path.read_text(encoding="utf-8").strip().splitlines()
    completed = json.loads(lines[-1])
    assert completed["status"] == "completed"
    assert completed["job_id"] == "sap_abc123"


def test_context_pack_script_emits_a_bundle(tmp_path: Path):
    queue = tmp_path / "audits" / "acp_devin_queue.jsonl"
    queue.parent.mkdir(parents=True, exist_ok=True)
    gw._append_jsonl(queue, {"ts": 1, "topic": "bridge lag", "status": "queued"})
    out = tmp_path / "pack.md"
    # Import the script and call main directly.
    import acp_devin_context_pack as pack
    pack.main(["--repo-root", str(tmp_path), "--topic", "bridge lag", "--output", str(out)])
    text = out.read_text(encoding="utf-8")
    assert "# Devin Context Pack" in text
    assert "bridge lag" in text
    assert "Verification commands" in text


def test_diagnose_status_scrubs_secrets_from_results(cfg):
    cfg.devin_results_path.parent.mkdir(parents=True, exist_ok=True)
    gw._append_jsonl(
        cfg.devin_results_path,
        {
            "ts": 1,
            "topic": "leaky summary",
            "status": "done",
            "pr_url": "",
            "summary": "BUZZ_PRIVATE_KEY=nsec1qqqqqqqqqqqq",
        },
    )
    result = gw.execute(gw.parse_mention("@EA diagnose status", cfg), cfg)
    assert "nsec1qqq" not in result.summary
    assert "[redacted" in result.summary


def test_confirm_refuses_already_completed_plan(cfg, monkeypatch):
    def _fake_tool(intent, c):
        return gw.ToolResult(
            gw.TOOL_HEALTH_CHECK, gw.HARNESS_GROK, True, "health — ea: ok", [["healthy", "true"]]
        )

    monkeypatch.setattr(gw, "_tool_health_check", _fake_tool)
    plan_record = {
        "ts": 1,
        "plan_id": "abc123",
        "goal": "acp health",
        "status": "pending",
        "steps": [{"tool": gw.TOOL_HEALTH_CHECK, "args": {}}],
    }
    gw._append_jsonl(cfg.plans_path, plan_record)
    first = gw.execute(gw.parse_mention("@EA confirm plan abc123", cfg), cfg)
    assert first.ok is True
    second = gw.execute(gw.parse_mention("@EA confirm plan abc123", cfg), cfg)
    assert second.ok is False
    assert "already completed" in second.summary


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


# --- Operator preflight (addendum §1 acceptance readiness) -------------------

def _rows(cfg):
    return {label: (ok, detail) for ok, label, detail in gw.preflight(cfg)}


def test_preflight_flags_empty_operator_allowlist(cfg, monkeypatch):
    monkeypatch.setattr(cfg, "operator_pubkeys", ())
    ok, detail = _rows(cfg)["ACP_OPERATOR_PUBKEYS"]
    assert ok is False
    assert "fail-closed" in detail


def test_preflight_reports_key_presence_without_the_value(cfg, monkeypatch):
    monkeypatch.setenv("BUZZ_PRIVATE_KEY", "nsec1supersecret")
    ok, detail = _rows(cfg)["BUZZ_PRIVATE_KEY"]
    assert ok is True
    assert "nsec1supersecret" not in detail


def test_preflight_requires_a_rig_ops_channel(cfg, monkeypatch):
    monkeypatch.setattr(cfg, "rig_ops_channel", "")
    assert _rows(cfg)["#rig-ops channel"][0] is False


def test_preflight_checks_the_local_tool_surface(cfg):
    assert _rows(cfg)["local tool surface"][0] is True


def test_preflight_publishes_nothing(cfg, monkeypatch):
    def _boom(*_a, **_k):
        raise AssertionError("preflight must not publish")

    monkeypatch.setattr(gw, "_publish", _boom)
    monkeypatch.setattr(gw.bot, "_publish_event", _boom)
    gw.preflight(cfg)
