"""Phase O1 C7 — Cedar bundle V&V CLI tests.

Tests the 4 subcommands of scripts/cedar_bundle_validate.py:

  T-O1-C7-1: validate succeeds on a valid bundle (backward compat preserved)
  T-O1-C7-2: diff produces meaningful output between two distinct bundles
  T-O1-C7-3: simulate handles empty shadow_log gracefully
  T-O1-C7-4: lint catches CRITICAL O1_SHADOW + permit-without-shadow-mode

The CLI is invoked via main(argv) in-process (avoids subprocess overhead +
gives access to exit codes deterministically).
"""

import io
import json
import sys
import tempfile
import types as _types
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))
sys.path.insert(0, str(BRIDGE_DIR.parent))  # repo root for `scripts.` import

# Stub heavy optional deps before bridge import (cedar_parser pulls store via path)
for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"


def _minimal_bundle(*, version=1, agent_id=SENTRY_ID, phase="O1_SHADOW",
                    policies=None, lane_prefixes=("wiki/", "events/")):
    """Build a minimal valid Cedar bundle dict."""
    return {
        "$schema":       "vapi-cedar-bundle-v1",
        "bundle_id":     "test_bundle_v1",
        "version":       version,
        "agent_id":      agent_id,
        "phase":         phase,
        "issued_at_iso": "2026-05-07T00:00:00Z",
        "lane_prefixes": list(lane_prefixes),
        "policies":      policies or [
            {
                "id":        "P-001",
                "effect":    "permit",
                "principal": {"agentId": agent_id},
                "action":    "skill:read-wiki",
                "resource":  "lane://wiki/**",
            },
        ],
    }


def _write_bundle(tmp_path: Path, payload: dict, name="bundle.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    """Invoke the CLI in-process. Returns (exit_code, stdout, stderr)."""
    from scripts.cedar_bundle_validate import main
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# T-O1-C7-1: validate
# ---------------------------------------------------------------------------

def test_t_o1_c7_1_validate_passes_on_valid_bundle(tmp_path):
    bundle = _write_bundle(tmp_path, _minimal_bundle())

    # Both forms must work: explicit subcommand + Phase O1 C1 backwards compat
    code, out, _ = _run_cli(["validate", str(bundle)])
    assert code == 0
    assert "VALID" in out
    assert "Merkle root:" in out

    code2, out2, _ = _run_cli([str(bundle)])
    assert code2 == 0
    assert "VALID" in out2


# ---------------------------------------------------------------------------
# T-O1-C7-2: diff
# ---------------------------------------------------------------------------

def test_t_o1_c7_2_diff_shows_lane_and_policy_delta(tmp_path):
    bundle_a = _write_bundle(tmp_path, _minimal_bundle(
        lane_prefixes=("wiki/",),
    ), name="a.json")

    # Bundle B: extra lane prefix + extra forbid policy + same agent_id
    payload_b = _minimal_bundle(lane_prefixes=("wiki/", "events/"))
    payload_b["policies"].append({
        "id":        "F-001",
        "effect":    "forbid",
        "principal": {"agentId": SENTRY_ID},
        "action":    "tool:kms-sign",
        "resource":  "draft://op/*",
    })
    bundle_b = _write_bundle(tmp_path, payload_b, name="b.json")

    code, out, _ = _run_cli(["diff", str(bundle_a), str(bundle_b)])
    assert code == 0
    assert "DIFF:" in out
    assert "events/" in out
    assert "F-001" in out
    assert "DIFFERENT" in out  # Merkle roots must differ


# ---------------------------------------------------------------------------
# T-O1-C7-3: simulate handles empty shadow_log gracefully
# ---------------------------------------------------------------------------

def test_t_o1_c7_3_simulate_empty_shadow_log(tmp_path):
    bundle = _write_bundle(tmp_path, _minimal_bundle())
    db_path = tmp_path / "empty.db"

    # Initialize Store schema, but don't populate shadow_log
    from vapi_bridge.store import Store
    Store(str(db_path))  # creates tables

    code, out, _ = _run_cli([
        "simulate", str(bundle), "--db", str(db_path), "--limit", "10",
    ])
    assert code == 0  # empty log is not an error
    # Should report either "NO HISTORICAL EVALUATIONS" or proceed with 0 rows
    assert ("NO HISTORICAL" in out) or ("replay count: 0" in out)


# ---------------------------------------------------------------------------
# T-O1-C7-4: lint catches CRITICAL O1_SHADOW + kms-sign without shadow_mode
# ---------------------------------------------------------------------------

def test_t_o1_c7_4_lint_catches_kms_sign_without_shadow_mode(tmp_path):
    # Permit kms-sign in O1_SHADOW without shadow_mode constraint = CRITICAL
    payload = _minimal_bundle(policies=[
        {
            "id":        "BAD-001",
            "effect":    "permit",
            "principal": {"agentId": SENTRY_ID},
            "action":    "tool:kms-sign",
            "resource":  "draft://kms/sign/*",
            # no constraint — this is the lint trigger
        },
    ])
    bundle = _write_bundle(tmp_path, payload)

    code, out, _ = _run_cli(["lint", str(bundle)])
    assert code == 1, "CRITICAL finding must produce exit code 1"
    assert "CRITICAL" in out
    assert "BAD-001" in out
    assert "shadow_mode" in out

    # Now add the shadow_mode constraint — lint should pass
    payload["policies"][0]["constraint"] = {"shadow_mode": True}
    bundle_ok = _write_bundle(tmp_path, payload, name="ok.json")
    code_ok, out_ok, _ = _run_cli(["lint", str(bundle_ok)])
    assert code_ok == 0
    assert "no findings" in out_ok or "clean" in out_ok
