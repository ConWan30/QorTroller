"""Day 15 ceremony dry-run rehearsal tests.

T-DAY15-1  Rehearsal completes against empty DB without raising
T-DAY15-2  Gate 1-3 evaluation correctly reflects env vars + --confirm
T-DAY15-3  Bundle validation passes (all 3 Merkles match canonical pins)
T-DAY15-4  Gate 4 watcher veto fires when agents are pre-O2 (empty DB)
T-DAY15-5  Expected post-anchor FRR is computed deterministically
T-DAY15-6  Ceremony plan has 6 steps in correct operational+governance order
T-DAY15-7  --strict mode exit code reflects readiness
T-DAY15-8  Rehearsal NEVER constructs a signed tx (static check)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


@pytest.fixture(autouse=True)
def _strip_cfg_env(monkeypatch):
    """Default kill-switch ARMED + O3 intent NOT set (matches the
    production-safe state). Gate 1 evaluates pause_env == "false" — so
    setting CHAIN_SUBMISSION_PAUSED=true makes Gate 1 fail (correct
    default state). Test T-2 explicitly overrides to verify the lifted
    state."""
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "true")
    monkeypatch.delenv("OPERATOR_INITIATIVE_O3_AUTHORIZED", raising=False)
    # Force the 4 cfg flag env vars to false for consistency
    for env_var in (
        "OPERATOR_DUAL_KEY_PRESENT",
        "KMS_HSM_PRODUCTION_READY",
        "GITHUB_APP_OAUTH_TOKENS_VALID",
        "MARKETPLACE_CURATOR_ROLE_ASSIGNED",
    ):
        monkeypatch.setenv(env_var, "false")
    yield


# ---------------------------------------------------------------------------
# T-DAY15-1
# ---------------------------------------------------------------------------

def test_t_day15_1_rehearsal_completes_against_empty_db():
    """Rehearsal must complete + return a dict with verdict + exit_code,
    never raising."""
    import parallel_o3_act_anchor_rehearsal as reh
    rehearsal = asyncio.run(reh.run_rehearsal(
        repo_root=ROOT, confirm=False,
        include_chain_reads=False, strict=False,
    ))
    assert isinstance(rehearsal, dict)
    assert "verdict" in rehearsal
    assert "exit_code" in rehearsal
    assert rehearsal["exit_code"] in (0, 1, 3, 4, 5, 7)


# ---------------------------------------------------------------------------
# T-DAY15-2
# ---------------------------------------------------------------------------

def test_t_day15_2_gates_1_2_3_reflect_env_and_confirm():
    """Gate 1-3 evaluation pre-condition matrix."""
    import parallel_o3_act_anchor_rehearsal as reh
    # No env, no --confirm → all 3 gates fail
    g = reh._check_gates_1_2_3(confirm=False)
    assert g["gate_1_chain_submission_unpaused"] is False
    assert g["gate_2_operator_o3_authorized"] is False
    assert g["gate_3_confirm_flag"] is False
    assert g["gates_1_2_3_all_pass"] is False
    # Set both env vars + --confirm → all 3 pass
    os.environ["CHAIN_SUBMISSION_PAUSED"] = "false"
    os.environ["OPERATOR_INITIATIVE_O3_AUTHORIZED"] = "true"
    try:
        g2 = reh._check_gates_1_2_3(confirm=True)
        assert g2["gate_1_chain_submission_unpaused"] is True
        assert g2["gate_2_operator_o3_authorized"] is True
        assert g2["gate_3_confirm_flag"] is True
        assert g2["gates_1_2_3_all_pass"] is True
    finally:
        os.environ["CHAIN_SUBMISSION_PAUSED"] = "false"
        os.environ.pop("OPERATOR_INITIATIVE_O3_AUTHORIZED", None)


# ---------------------------------------------------------------------------
# T-DAY15-3
# ---------------------------------------------------------------------------

def test_t_day15_3_bundle_validation_matches_canonical_pins():
    """All 3 O3 ACTING bundles on disk must have Merkles matching the
    canonical pins. If this test fails, ceremony fire on Day 15 would
    write the WRONG Merkles to AgentScope — protocol breach."""
    import parallel_o3_act_anchor_rehearsal as reh
    bv = reh._validate_bundles(repo_root=ROOT)
    assert bv["all_pass"] is True, (
        f"bundle validation FAILED — Day 15 fire would write wrong "
        f"Merkles. Details: {bv}"
    )
    for agent in reh._AGENT_ANCHOR_ORDER:
        entry = bv["per_agent"][agent]
        assert entry["pass"] is True
        assert entry["merkle_match"] is True
        assert entry["phase_ok"] is True


# ---------------------------------------------------------------------------
# T-DAY15-4
# ---------------------------------------------------------------------------

def test_t_day15_4_gate_4_watcher_veto_pre_o2():
    """Against empty DB (agents pre-O2), Gate 4 watcher veto must FAIL
    with agent_not_anchored blockers per agent."""
    import parallel_o3_act_anchor_rehearsal as reh
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        store = Store(db_path=db)
        from vapi_bridge.config import Config
        cfg = Config()
        g4 = asyncio.run(reh._check_gate_4_watcher(cfg=cfg, store=store))
        assert g4["gate_4_pass"] is False
        for agent in reh._AGENT_ANCHOR_ORDER:
            assert agent in g4["blockers_per_agent"]
            assert "agent_not_anchored" in g4["blockers_per_agent"][agent]


# ---------------------------------------------------------------------------
# T-DAY15-5
# ---------------------------------------------------------------------------

def test_t_day15_5_expected_frr_computed_deterministic():
    """Expected post-anchor FRR computation succeeds + has all required
    keys + the 3 agents in canonical sorted order."""
    import parallel_o3_act_anchor_rehearsal as reh
    from vapi_bridge.config import Config
    cfg = Config()
    fr = asyncio.run(reh._compute_expected_frr(cfg=cfg))
    assert fr["ok"] is True
    assert fr["domain_tag"] == "VAPI-FRR-v1"
    assert fr["phase_code_hex"] == "0x03"
    assert fr["frr_hex"].startswith("0x")
    assert len(fr["frr_hex"]) == 66  # 0x + 64 hex chars
    assert len(fr["agents"]) == 3
    # All 3 agents present with phase_code 0x03
    for a in fr["agents"]:
        assert a["phase_code"] == "0x03"
        assert a["agent_id"].startswith("0x")


# ---------------------------------------------------------------------------
# T-DAY15-6
# ---------------------------------------------------------------------------

def test_t_day15_6_ceremony_plan_6_steps_correct_ordering():
    """Ceremony plan has exactly 6 steps in operational+governance
    interleaved order: agent_1_op, agent_1_gov, agent_2_op, ..."""
    import parallel_o3_act_anchor_rehearsal as reh
    plan = reh._ceremony_step_plan()
    assert len(plan) == 6
    expected_pattern = [
        ("anchor_sentry", "operational"),
        ("anchor_sentry", "governance"),
        ("guardian",      "operational"),
        ("guardian",      "governance"),
        ("curator",       "operational"),
        ("curator",       "governance"),
    ]
    for step, (exp_agent, exp_leg) in zip(plan, expected_pattern):
        assert step["agent"] == exp_agent
        assert step["leg"] == exp_leg
        assert step["gas_buffer_multiplier"] == 1.25


# ---------------------------------------------------------------------------
# T-DAY15-7
# ---------------------------------------------------------------------------

def test_t_day15_7_strict_mode_exit_code():
    """--strict mode: empty DB → not READY_TO_FIRE → exit 1."""
    import parallel_o3_act_anchor_rehearsal as reh
    rehearsal = asyncio.run(reh.run_rehearsal(
        repo_root=ROOT, confirm=False,
        include_chain_reads=False, strict=True,
    ))
    assert rehearsal["exit_code"] == 1, (
        f"strict + not-ready should exit 1; got {rehearsal['exit_code']} "
        f"verdict={rehearsal['verdict']}"
    )


# ---------------------------------------------------------------------------
# T-DAY15-8
# ---------------------------------------------------------------------------

def test_t_day15_8_rehearsal_never_calls_send_tx():
    """STATIC CHECK: the rehearsal script must NOT contain any call to
    chain._send_tx OR chain.set_agent_scope_root OR chain.update_agent_
    scope_governance OR anchor.anchor_bundle. Wallet-free + tx-free
    invariant pinned by source inspection — Day 15 fire belongs to
    parallel_o3_act_anchor.py only."""
    script = ROOT / "scripts" / "parallel_o3_act_anchor_rehearsal.py"
    src = script.read_text(encoding="utf-8")
    # Forbidden patterns (any one of these in the rehearsal = wallet-risk)
    forbidden = [
        r"\._send_tx\(",
        r"\.set_agent_scope_root\(",
        r"\.update_agent_scope_governance\(",
        r"\.anchor_bundle\(",
        r"send_raw_transaction\(",
    ]
    for pat in forbidden:
        matches = re.findall(pat, src)
        # Filter docstring/comment lines containing these patterns
        # (the script's docstring references them by name)
        real_calls = [
            m for m in matches
            # Approximate: skip if the pattern appears in a code line that's
            # also a comment or docstring context. Since we're matching the
            # function-call pattern (with paren), real usage would be in
            # executable code. The docstring contains parens only in
            # references like "anchor.anchor_bundle()" — strict regex catches.
        ]
        # We can be strict: any real call is a violation. Strip the docstring
        # by checking module-level docstring + tolerating ZERO function calls.
        # Use source-line check: skip lines that are within triple-quoted strings.
        in_docstring = False
        violating_lines: list[str] = []
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith('"""') or stripped.endswith('"""'):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            if stripped.startswith("#"):
                continue
            if re.search(pat, line):
                violating_lines.append(line)
        assert not violating_lines, (
            f"REHEARSAL VIOLATION: pattern {pat!r} matched in executable "
            f"code:\n" + "\n".join(violating_lines[:3])
        )
