"""Operator Initiative O3 expedite arc tests — preflight + seeding harness.

T-O3-EXPEDITE-1   Preflight runs against empty DB → exit code reflects state
T-O3-EXPEDITE-2   Preflight surfaces 4 cfg flags in cfg_flag_summary
T-O3-EXPEDITE-3   Preflight categorizes O3 blockers by type (calendar/draft/rate/cfg/other)
T-O3-EXPEDITE-4   Preflight verdict logic: cfg_flags_fully_set drives the rollup
T-O3-EXPEDITE-5   Preflight --strict mode returns non-zero unless ALL gates clear
T-O3-EXPEDITE-6   Preflight --json output is valid JSON
T-O3-EXPEDITE-7   Seeding harness triple-gate: NO env vars → dry-run
T-O3-EXPEDITE-8   Seeding harness triple-gate: --confirm without env vars → exit 1
T-O3-EXPEDITE-9   Seeding harness real seeding produces drafts at the target count
T-O3-EXPEDITE-10  Seeding harness --auto-accept drives disagreement_rate to 0.0
T-O3-EXPEDITE-11  Config has the 4 newly-promoted O3 cfg flag fields
"""
from __future__ import annotations

import json
import os
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


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-1
# ---------------------------------------------------------------------------

def test_t_o3_expedite_1_preflight_empty_db_exit_code():
    """Preflight against empty DB → exit code 1 (not READY-TO-FIRE, not
    CALENDAR-WAITING since cfg flags are all False)."""
    import operator_initiative_o3_preflight as mod
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        rc = mod.main(["--db", db])
        # Empty DB + default-False cfg flags → EXPEDITE-WORK-AVAILABLE → exit 1
        assert rc == 1


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-2
# ---------------------------------------------------------------------------

def test_t_o3_expedite_2_cfg_flag_summary_has_4_flags():
    """run_preflight must populate cfg_flag_summary with exactly the 4
    expected keys."""
    import operator_initiative_o3_preflight as mod
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        audit = mod.run_preflight(db, strict=False)
        assert set(audit["cfg_flag_summary"].keys()) == {
            "operator_dual_key_present",
            "kms_hsm_production_ready",
            "github_app_oauth_tokens_valid",
            "marketplace_curator_role_assigned",
        }
        # Defaults are all False (env-overridable but not set here)
        assert all(v is False for v in audit["cfg_flag_summary"].values())


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-3
# ---------------------------------------------------------------------------

def test_t_o3_expedite_3_blocker_categorization_keys():
    """Each per-agent entry has the 5 blocker-category keys, even if empty."""
    import operator_initiative_o3_preflight as mod
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        audit = mod.run_preflight(db, strict=False)
        for a in audit["per_agent"]:
            for cat in ("calendar", "draft", "rate", "cfg", "other"):
                key = f"o3_blockers_{cat}"
                assert key in a, f"per-agent dict missing {key}"
                assert isinstance(a[key], list)


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-4
# ---------------------------------------------------------------------------

def test_t_o3_expedite_4_cfg_flags_fully_set_drives_rollup():
    """When cfg_flags_fully_set is False, ceremony_ready_when_calendar_
    clears must also be False. Verified by inspecting the rollup."""
    import operator_initiative_o3_preflight as mod
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        audit = mod.run_preflight(db, strict=False)
        r = audit["rollup"]
        assert r["cfg_flags_fully_set"] is False
        assert r["ceremony_ready_when_calendar_clears"] is False
        assert r["all_non_calendar_gates_clear"] is False


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-5
# ---------------------------------------------------------------------------

def test_t_o3_expedite_5_strict_mode_exit_code():
    """--strict mode returns non-zero unless ceremony_ready_to_fire is True.
    Empty DB → exit 1."""
    import operator_initiative_o3_preflight as mod
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        rc = mod.main(["--db", db, "--strict"])
        assert rc == 1


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-6
# ---------------------------------------------------------------------------

def test_t_o3_expedite_6_json_output(capsys):
    """--json output must parse as valid JSON with expected top-level keys."""
    import operator_initiative_o3_preflight as mod
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        mod.main(["--db", db, "--json"])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        for k in ("calendar_gate", "per_agent", "cfg_flag_summary",
                  "rollup", "expedite_path_status"):
            assert k in parsed, f"--json output missing key {k}"


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-7
# ---------------------------------------------------------------------------

def test_t_o3_expedite_7_seeding_dry_run_without_env(monkeypatch, capsys):
    """No env vars + no --confirm → harness defaults to dry-run."""
    import operator_initiative_seed_drafts as mod
    # Strip env to force gate-2 failure
    monkeypatch.delenv("OPERATOR_INITIATIVE_SEED_DRAFTS_AUTHORIZED",
                       raising=False)
    monkeypatch.delenv("CHAIN_SUBMISSION_PAUSED", raising=False)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        rc = mod.main(["--db", db, "--n", "3"])
        captured = capsys.readouterr()
        assert rc == 0  # dry-run completes successfully
        assert "DRY-RUN" in captured.out
        assert "would_seed" in captured.out


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-8
# ---------------------------------------------------------------------------

def test_t_o3_expedite_8_seeding_confirm_without_env(monkeypatch, capsys):
    """--confirm WITHOUT both env vars → exit 1 (authorization failed)."""
    import operator_initiative_seed_drafts as mod
    monkeypatch.delenv("OPERATOR_INITIATIVE_SEED_DRAFTS_AUTHORIZED",
                       raising=False)
    monkeypatch.delenv("CHAIN_SUBMISSION_PAUSED", raising=False)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        rc = mod.main(["--db", db, "--n", "3", "--confirm"])
        assert rc == 1


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-9
# ---------------------------------------------------------------------------

def test_t_o3_expedite_9_real_seeding_populates_drafts(monkeypatch):
    """Real seeding with triple-gate → each agent reaches the target count."""
    import operator_initiative_seed_drafts as mod
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "true")
    monkeypatch.setenv("OPERATOR_INITIATIVE_SEED_DRAFTS_AUTHORIZED", "true")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        report = mod.run_seeding(
            db_path=db, n_per_agent=4, auto_accept=False, dry_run=False,
        )
        assert report["error"] is None
        for agent_name, entry in report["per_agent"].items():
            assert entry["post_seed_draft_count"] == 4, (
                f"agent {agent_name} did not reach target: {entry}"
            )


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-10
# ---------------------------------------------------------------------------

def test_t_o3_expedite_10_auto_accept_drives_disagreement_to_zero(monkeypatch):
    """--auto-accept records operator_decision='accept' for every draft
    → compute_operator_agent_disagreement_rate returns 0.0."""
    import operator_initiative_seed_drafts as mod
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "true")
    monkeypatch.setenv("OPERATOR_INITIATIVE_SEED_DRAFTS_AUTHORIZED", "true")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        Store(db_path=db)
        report = mod.run_seeding(
            db_path=db, n_per_agent=3, auto_accept=True, dry_run=False,
        )
        for agent_name, entry in report["per_agent"].items():
            assert entry.get("disagreement_rate") == 0.0, (
                f"agent {agent_name} disagreement_rate != 0.0: {entry}"
            )
            assert entry.get("accepted") == 3


# ---------------------------------------------------------------------------
# T-O3-EXPEDITE-11
# ---------------------------------------------------------------------------

def test_t_o3_expedite_11_config_has_4_o3_flags():
    """Config must have the 4 O3 cfg fields (the expedite arc promoted 2
    of them — operator_dual_key_present + github_app_oauth_tokens_valid —
    from getattr-fallback to first-class fields)."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert hasattr(cfg, "operator_dual_key_present")
    assert hasattr(cfg, "kms_hsm_production_ready")
    assert hasattr(cfg, "github_app_oauth_tokens_valid")
    assert hasattr(cfg, "marketplace_curator_role_assigned")
    # Defaults are False (per the env-overridable pattern)
    assert cfg.operator_dual_key_present is False
    assert cfg.kms_hsm_production_ready is False
    assert cfg.github_app_oauth_tokens_valid is False
    assert cfg.marketplace_curator_role_assigned is False
