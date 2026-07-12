"""TRL-1 R3 - witness-node ioID-registration readiness tests.

The check is pure (injected deployed-addrs + exists fn): all prerequisites present
-> all OK; a missing registry or file -> GAP. A subprocess run confirms READY on
the real repo (the identity path is genuinely deployed).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import witness_node_ioid_readiness as wn

_SCRIPT = REPO_ROOT / "scripts" / "witness_node_ioid_readiness.py"

_DEPLOYED = {
    "VAPIioIDRegistry": "0xF7885B588718b891B2234477D031607da4a7ACfe",
    "VAPIManufacturerDeviceRegistry": "0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0",
}
_ALL_FILES = lambda p: True   # noqa: E731 - all repo files present


def _oks(checks):
    return {name: ok for name, ok, _ in checks}


def test_all_present_is_ready():
    checks = wn.check_prerequisites(_DEPLOYED, _ALL_FILES)
    assert all(ok for _, ok, _ in checks)
    assert len(checks) == 5


def test_missing_ioid_registry_is_gap():
    checks = wn.check_prerequisites({"VAPIManufacturerDeviceRegistry": "0x2e"}, _ALL_FILES)
    assert _oks(checks)["ioID device-identity registry (deployed)"] is False


def test_missing_vmdr_is_gap():
    checks = wn.check_prerequisites({"VAPIioIDRegistry": "0xF7"}, _ALL_FILES)
    assert _oks(checks)["device birth registry (deployed)"] is False


def test_missing_registration_pattern_is_gap():
    checks = wn.check_prerequisites(_DEPLOYED,
                                    lambda p: "agent_registration" not in p)
    assert _oks(checks)["ioID registration pattern"] is False


def test_names_verifier_independence_rail():
    checks = wn.check_prerequisites(_DEPLOYED, _ALL_FILES)
    assert any("RP-7" in name for name, _, _ in checks)


def test_ascii_only_source():
    src = _SCRIPT.read_text(encoding="utf-8")
    non_ascii = sorted(set(c for c in src if ord(c) > 127))
    assert non_ascii == [], f"non-ASCII: {[hex(ord(c)) for c in non_ascii]}"


def test_runs_ready_on_real_repo():
    r = subprocess.run([sys.executable, str(_SCRIPT)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0                       # the identity path is genuinely deployed
    assert "READY" in r.stdout and "VAPIioIDRegistry" in r.stdout
