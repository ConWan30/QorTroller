"""Tests for the VSD session-attestation witness primitive (pure) + MCP read-tool smoke."""
from __future__ import annotations

import sys
from pathlib import Path

_VAULT = Path(__file__).resolve().parent.parent.parent / "vsd-vault"
sys.path.insert(0, str(_VAULT / ".vsd"))

import vsd_session_attest as A  # noqa: E402

_HEAD = "ab" * 32


def test_deterministic_and_verifies():
    r = A.compute_session_attestation(_HEAD, True, True, 100)
    assert r == A.compute_session_attestation(_HEAD, True, True, 100)
    assert len(r["stamp"]) == 64 and A.verify_session_attestation(r) is True


def test_sensitive_to_every_input():
    base = A.compute_session_attestation(_HEAD, True, True, 100)["stamp"]
    assert base != A.compute_session_attestation("cd" * 32, True, True, 100)["stamp"]   # head
    assert base != A.compute_session_attestation(_HEAD, False, True, 100)["stamp"]      # harness
    assert base != A.compute_session_attestation(_HEAD, True, False, 100)["stamp"]      # pv_ci
    assert base != A.compute_session_attestation(_HEAD, True, None, 100)["stamp"]       # not-checked
    assert base != A.compute_session_attestation(_HEAD, True, True, 101)["stamp"]       # ts


def test_empty_head_allowed_and_pv_ci_none():
    r = A.compute_session_attestation("", True, None, 5)
    assert len(r["stamp"]) == 64 and r["inputs"]["pv_ci_pass"] is None
    assert A.verify_session_attestation(r) is True


def test_bad_head_rejected():
    try:
        A.compute_session_attestation("deadbeef", True, True, 5)
        assert False, "should reject non-32-byte head"
    except ValueError:
        pass


def test_tamper_detected():
    r = A.compute_session_attestation(_HEAD, True, True, 100)
    r["inputs"]["harness_pass"] = False          # flip an input, keep the old stamp
    assert A.verify_session_attestation(r) is False
    r2 = A.compute_session_attestation(_HEAD, True, True, 100)
    r2["stamp"] = "00" + r2["stamp"][2:]         # flip the stamp
    assert A.verify_session_attestation(r2) is False


def test_attest_module_is_dependency_free():
    """Regression (live MCP env lacks cryptography): the witness primitive must stay pure
    stdlib so vsd_session_attestation works ambiently without the crypto dep."""
    import inspect
    src = inspect.getsource(A)
    assert "cryptography" not in src and "import " in src
    # only hashlib/struct expected
    assert "hashlib" in src and "struct" in src


def test_mcp_tools_registered():
    """The 4 read-only VSD tools register on the unified server."""
    import importlib
    sys.path.insert(0, str(_VAULT.parent / "vapi-mcp"))
    try:
        u = importlib.import_module("unified_server")
    except Exception as exc:
        import pytest
        pytest.skip(f"unified_server import unavailable: {exc}")
    vsd_tools = sorted(k for k in u.TOOLS if k.startswith("vsd_"))
    assert vsd_tools == ["vsd_harness_report", "vsd_session_attestation",
                         "vsd_state", "vsd_verify_chain", "vsd_vpm_label"]
